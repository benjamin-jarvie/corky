"""Corky's session flow: everything between seed entry and signed PSBT.

This module performs no cryptography. It converts the seed via the shim,
then drives Bitcoin Core over RPC. Core does all key derivation, all PSBT
parsing, all fee arithmetic and all signing. Every function here is plumbing.

The front end (screen/camera) calls exactly four things per session:
    open_session(mnemonic, passphrase)  -> wallet loaded in Core
    describe_psbt(psbt_b64)             -> dict for the review screen
    sign_psbt(psbt_b64)                 -> signed PSBT (base64)
    close_session()                     -> wallet unloaded (ramdisk wipe is
                                           the real teardown at power-off)
"""

import hashlib
import hmac
import json
import shutil
from decimal import Decimal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
from bip39_shim import mnemonic_to_xprv  # noqa: E402  (the one non-Core step)

def _json_decimal(obj):
    if isinstance(obj, Decimal):
        return str(obj)  # Core accepts string amounts; never re-floated
    raise TypeError


WALLET = "corky"
GEN_WALLET = "corky-gen"     # throwaway; exists only inside core_entropy()

# Account-level derivation, hardened, per BIP84/BIP86. Coin type 0' mainnet,
# 1' for test networks, per SLIP-44.
PURPOSES = (84, 86)


class Rpc:
    """Minimal bitcoin-cli wrapper. chain: 'main', 'test', 'regtest', 'signet'."""

    def __init__(self, datadir, chain="main", cli="bitcoin-cli"):
        flag = {"main": [], "test": ["-testnet"], "regtest": ["-regtest"],
                "signet": ["-signet"]}[chain]
        self.base = [cli, f"-datadir={datadir}", *flag]
        self.chain = chain
        subdir = {"main": "", "test": "testnet3", "regtest": "regtest",
                  "signet": "signet"}[chain]
        self.wallet_dir = Path(datadir) / subdir / "wallets"

    def call(self, method, *params, wallet=None):
        cmd = list(self.base)
        if wallet:
            cmd.append(f"-rpcwallet={wallet}")
        cmd += [method,
                *[p if isinstance(p, str) else json.dumps(p, default=_json_decimal)
                  for p in params]]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"{method}: {out.stderr.strip()}")
        text = out.stdout.strip()
        try:
            # parse_float=Decimal: BTC amounts must never pass through binary
            # floats — the review screen is the device's security boundary.
            return json.loads(text, parse_float=Decimal)
        except json.JSONDecodeError:
            return text


def build_descriptors(rpc, xprv):
    """BIP84 + BIP86 receive/change descriptors, checksummed by Core."""
    coin = 0 if rpc.chain == "main" else 1
    descs = []
    for purpose in PURPOSES:
        func = "wpkh" if purpose == 84 else "tr"
        for change in (0, 1):
            raw = f"{func}({xprv}/{purpose}h/{coin}h/0h/{change}/*)"
            # getdescriptorinfo's "checksum" field covers the descriptor as
            # given (private form); its "descriptor" field is the public form.
            checksum = rpc.call("getdescriptorinfo", raw)["checksum"]
            descs.append(_desc_entry(f"{raw}#{checksum}", internal=bool(change)))
    return descs


def _desc_entry(desc, internal):
    return {"desc": desc, "active": True, "internal": internal,
            "timestamp": "now", "range": [0, 200]}


def _import(rpc, descriptors):
    rpc.call("createwallet", WALLET, False, True, "", False, True)
    result = rpc.call("importdescriptors", descriptors, wallet=WALLET)
    failures = [r for r in result if not r.get("success")]
    if failures:
        raise RuntimeError(f"importdescriptors failed: {failures}")


def open_session(rpc, mnemonic, passphrase=""):
    """Input mode 3 (default): BIP39 words. The only path that uses the shim."""
    xprv = mnemonic_to_xprv(mnemonic, passphrase, mainnet=(rpc.chain == "main"))
    _import(rpc, build_descriptors(rpc, xprv))


def open_session_xprv(rpc, xprv):
    """Input mode 2: a raw BIP32 xprv (typed or from a static QR).
    Pure Core from the first byte; Corky applies the BIP84/86 paths."""
    _import(rpc, build_descriptors(rpc, xprv.strip()))


def open_session_descriptors(rpc, descriptors):
    """Input mode 1: Core-native private descriptors (from a static QR).
    Fully self-describing; no shim, no assumed derivation paths.
    Accepts one or more descriptor strings; each becomes an active
    receive/change pair according to its own content."""
    imports = []
    for desc in descriptors:
        desc = desc.strip()
        if "multi" in desc:
            # v1 scope is frozen to single-sig (README); multisig descriptors
            # are refused here rather than silently imported.
            raise RuntimeError("multisig descriptors are out of v1 scope")
        # Re-checksum via Core (accepts descriptors with or without one).
        info = rpc.call("getdescriptorinfo", desc)
        bare = desc.split("#")[0]
        # Heuristic: a trailing /1/* branch is the change chain. Documented
        # limitation: multipath/nonstandard descriptors may need explicit
        # marking; Core accepts either labeling for signing purposes.
        imports.append(_desc_entry(f"{bare}#{info['checksum']}",
                                   internal=bare.endswith("/1/*)")))
    _import(rpc, imports)


def public_descriptors(rpc):
    """What the coordinator needs: the watch-only (xpub) descriptors."""
    listed = rpc.call("listdescriptors", wallet=WALLET)["descriptors"]
    return [d["desc"] for d in listed if d["active"]]


def describe_psbt(rpc, psbt_b64):
    """Everything the review screen shows. All numbers are Core's.

    The fee is computed by Core from coordinator-supplied input amounts;
    an air-gapped signer cannot verify those amounts against the chain.
    The screen must say so.
    """
    decoded = rpc.call("decodepsbt", psbt_b64)
    analysis = rpc.call("analyzepsbt", psbt_b64)
    outputs = [
        {"address": vout["scriptPubKey"].get("address", "(non-standard)"),
         "amount_btc": vout["value"]}
        for vout in decoded["tx"]["vout"]
    ]
    # Total input value, from the coordinator-supplied UTXO data that Core
    # parsed out of the PSBT (A-5: show fee AND total input sum).
    input_total = Decimal(0)
    complete_inputs = True
    for i, txin in enumerate(decoded["inputs"]):
        amount = None
        witness = txin.get("witness_utxo")
        if witness is not None:
            amount = witness.get("amount")
        else:
            # Legacy input: non_witness_utxo is the whole previous tx as
            # decoded by Core; the spent output's value sits at the vout
            # index named by this input in the unsigned tx.
            prev = txin.get("non_witness_utxo")
            if prev is not None:
                vout_n = decoded["tx"]["vin"][i]["vout"]
                outs = prev.get("vout", [])
                if vout_n < len(outs):
                    amount = outs[vout_n].get("value")
        if amount is None:
            complete_inputs = False
        else:
            input_total += Decimal(str(amount))
    return {
        "outputs": outputs,
        "fee_btc": decoded.get("fee"),          # None if inputs incomplete
        "input_total_btc": input_total if complete_inputs else None,
        "input_count": len(decoded["inputs"]),
        "next_role": analysis.get("next"),
        "fee_note": "fee computed from coordinator-supplied input amounts",
    }


def sign_psbt(rpc, psbt_b64):
    result = rpc.call("walletprocesspsbt", psbt_b64, wallet=WALLET)
    return {"psbt": result["psbt"], "complete": result["complete"]}


def core_entropy(rpc, length=64):
    """Entropy from Bitcoin Core's own RNG (PLAN A-19). Opt-in only.

    Core seeds a fresh descriptor wallet from GetStrongRandBytes. We create
    a throwaway wallet, read its PRIVATE descriptors back with
    `listdescriptors true`, and extract `length` bytes from them. The
    randomness is entirely Core's. Corky contains no RNG of its own and
    reaches for none of Python's; tests/test_generate.py enforces that
    statically and at import time.

    The extraction step is a domain-separated HMAC-SHA512 stream over the
    concatenated private descriptors, so it is deterministic given Core's
    output and adds no entropy of its own. The throwaway wallet is unloaded
    and deleted before this function returns, on every path.
    """
    if not 16 <= length <= 64:
        raise ValueError("length must be 16-64 bytes (BIP32/BIP93 range)")
    try:
        rpc.call("createwallet", GEN_WALLET, False, False, "", False, True)
        listed = rpc.call("listdescriptors", True, wallet=GEN_WALLET)
        keyed = sorted({d["desc"] for d in listed["descriptors"]
                        if "prv" in d["desc"]})
        # Sanity, not verification: Core must have given us several DISTINCT
        # private descriptors. A stuck RNG returning one constant fails here.
        if len(keyed) < 2:
            raise RuntimeError("Core returned no distinct private key material")
        material = "\n".join(keyed).encode()
    finally:
        _drop_wallet(rpc, GEN_WALLET)
    out, counter = b"", 0
    while len(out) < length:
        out += hmac.new(material, b"corky-core-rng-v1" + bytes([counter]),
                        hashlib.sha512).digest()
        counter += 1
    return out[:length]


def _drop_wallet(rpc, name):
    """Unload and delete a wallet, ignoring the not-loaded case."""
    try:
        rpc.call("unloadwallet", name)
    except RuntimeError:
        pass
    shutil.rmtree(rpc.wallet_dir / name, ignore_errors=True)


def close_session(rpc):
    """Unload AND delete the session wallet. On the device the datadir is a
    ramdisk and power-off is the real teardown; deleting here keeps every
    environment (and every test) as stateless as the hardware."""
    _drop_wallet(rpc, WALLET)
