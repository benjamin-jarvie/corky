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

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
from bip39_shim import mnemonic_to_xprv  # noqa: E402  (the one non-Core step)

WALLET = "corky"

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
                *[p if isinstance(p, str) else json.dumps(p) for p in params]]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"{method}: {out.stderr.strip()}")
        text = out.stdout.strip()
        try:
            return json.loads(text)
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
            descs.append({
                "desc": f"{raw}#{checksum}",
                "active": True,
                "internal": bool(change),
                "timestamp": "now",
                "range": [0, 200],
            })
    return descs


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
        # Re-checksum via Core (accepts descriptors with or without one).
        info = rpc.call("getdescriptorinfo", desc)
        bare = desc.split("#")[0]
        imports.append({
            "desc": f"{bare}#{info['checksum']}",
            "active": True,
            "internal": "/1/*" in bare,
            "timestamp": "now",
            "range": [0, 200],
        })
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
    return {
        "outputs": outputs,
        "fee_btc": decoded.get("fee"),
        "input_count": len(decoded["inputs"]),
        "next_role": analysis.get("next"),
        "fee_note": "fee computed from coordinator-supplied input amounts",
    }


def sign_psbt(rpc, psbt_b64):
    result = rpc.call("walletprocesspsbt", psbt_b64, wallet=WALLET)
    return {"psbt": result["psbt"], "complete": result["complete"]}


def close_session(rpc):
    """Unload AND delete the session wallet. On the device the datadir is a
    ramdisk and power-off is the real teardown; deleting here keeps every
    environment (and every test) as stateless as the hardware."""
    rpc.call("unloadwallet", WALLET)
    shutil.rmtree(rpc.wallet_dir / WALLET, ignore_errors=True)
