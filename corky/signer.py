"""Corky's session flow: everything between loading a key and a signed PSBT.

This module performs no cryptography. It hands Core what the user supplied,
then drives Bitcoin Core over RPC. Core does all key derivation, all PSBT
parsing, all fee arithmetic and all signing. Every function here is plumbing.

The front end (screen/camera) calls exactly four things per session:
    open_session_xprv(xprv) / open_session_descriptors(descs)
    describe_psbt(psbt_b64)             -> dict for the review screen
    sign_psbt(psbt_b64)                 -> signed PSBT (base64)
    close_session()                     -> wallet unloaded (ramdisk wipe is
                                           the real teardown at power-off)
"""

import contextlib
import json
import re
import shutil
import time
from collections import namedtuple
from decimal import Decimal
import subprocess
from pathlib import Path


# Anything that looks like an extended private key, in any network's
# prefix. Core quotes the offending key back in its own error messages
# (verified against 31.1 on 2026-09-05: getdescriptorinfo answers
# "wpkh(): key 'tprv8Zgx...' is not valid"), and Corky puts Core's message
# on the panel. Unredacted, that message also reaches stderr, which systemd
# captures into the journal on the SD card. A key on the card is the one
# thing this device must never do.
#: Every prefix a BIP32 extended PRIVATE key can carry, across networks and
#: SLIP-132 script types. One list, so the redactor and the scan classifier
#: cannot disagree about what a private key looks like.
XPRV_PREFIXES = ("xprv", "tprv", "yprv", "zprv", "vprv", "uprv")

#: A WIF private key, which carries no word-shaped prefix at all: one
#: character for network and compression, then 50 or 51 base58 characters.
#: 5 and 9 are the uncompressed forms, K, L and c the compressed ones.
#:
#: Corky never asks for a WIF, but a person typing a key on a five-way pad
#: can paste or mistype one, and Core echoes what it refused: "key
#: 'cVjzvdHG…' is not valid" reached the panel and the journal in full
#: until audit A2 (2026-09-06). Redaction is defence in depth, so it
#: covers key forms this device does not accept as well as the ones it
#: does.
_WIF_RE = r"\b[59KLc][1-9A-HJ-NP-Za-km-z]{50,51}\b"

_SECRET_RE = re.compile(
    r"\b(?:%s)[1-9A-HJ-NP-Za-km-z]{20,}|%s"
    % ("|".join(XPRV_PREFIXES), _WIF_RE))


def redact(text: str) -> str:
    """Strip key material out of text bound for a screen, a log or the
    journal. This is string handling, not key handling: nothing here
    computes on a key, it only refuses to repeat one (PLAN A-22)."""
    return _SECRET_RE.sub("<key redacted>", text)


def _json_decimal(obj):
    if isinstance(obj, Decimal):
        return str(obj)  # Core accepts string amounts; never re-floated
    raise TypeError


WALLET = "corky"

# Several keys in one session (map e2e-before-testers, ticket 03): one Core
# wallet per key, up to MAX_KEYS. The first key keeps the historic wallet
# name; the rest take numbered slots. The fingerprint, not the slot, names a
# key on screen. Measured on the Zero 2 W: about 3MB of bitcoind RSS per key.
MAX_KEYS = 5
SLOTS = (WALLET,) + tuple(f"{WALLET}-{i}" for i in range(2, MAX_KEYS + 1))

#: A loaded key: the Core wallet that holds it, and the fingerprint that
#: names it to the user.
Key = namedtuple("Key", "name xfp")

# Account-level derivation, hardened, per BIP84/BIP86. Coin type 0' mainnet,
# 1' for test networks, per SLIP-44.
#: The BIP purpose and descriptor function for each of Core's four script
#: policies, in the order the panel walks them. A key that arrives by scan
#: or by typing is built with ALL of these, so it presents what a key Core
#: generated presents.
#:
#: It was (84, 86) until 2026-09-05, which meant restoring your own paper
#: backup gave you two of the four policies the key controls. Coins on a
#: legacy or nested address were still the key's and still spendable by
#: anyone who imported the right descriptor, and Corky showed neither the
#: address nor the balance. Measured on the board: four pairs is a 44kB
#: wallet against 20kB for two, and the node's RSS does not move. 24kB per
#: key against 512MB of RAM is not a reason to hide half a wallet.
#: How long any one bitcoin-cli call may take before the device gives up.
#:
#: Measured on the Zero 2 W, 2026-09-06, with the M0 gate: opening a key
#: (importdescriptors, eight descriptors) takes **4.4s**, and building,
#: reviewing and signing a 60-input PSBT takes **1.5s**. This cap is 27x
#: the slowest of those, so it cannot fire on a healthy node doing real
#: work; it exists only to turn "frozen for ever" into a message.
RPC_TIMEOUT = 120.0

PURPOSE_FUNCS = ((44, "pkh({key})"),
                 (49, "sh(wpkh({key}))"),
                 (84, "wpkh({key})"),
                 (86, "tr({key})"))


class Rpc:
    """Minimal bitcoin-cli wrapper. chain: 'main', 'test', 'regtest', 'signet'."""

    def __init__(self, datadir, chain="main", cli="bitcoin-cli"):
        flag = {"main": [], "test": ["-testnet"], "testnet4": ["-testnet4"],
                "regtest": ["-regtest"], "signet": ["-signet"]}[chain]
        self.base = [cli, f"-datadir={datadir}", *flag]
        self.chain = chain
        # Verified against Core 31.1: -testnet still writes testnet3/,
        # and -testnet4 writes testnet4/.
        subdir = {"main": "", "test": "testnet3", "testnet4": "testnet4",
                  "regtest": "regtest", "signet": "signet"}[chain]
        self.net_dir = Path(datadir) / subdir

    @property
    def wallet_dir(self):
        """Where Core keeps this node's wallets, decided the way Core decides
        it: the wallets/ directory when one exists, else the datadir itself.
        On the Zero 2 W's ramdisk datadir there is no wallets/ directory, so
        the board's wallets sit at /run/corky/<name>. A fixed wallets/ path
        would have left every wallet directory behind on close (seen
        2026-09-04)."""
        sub = self.net_dir / "wallets"
        return sub if sub.is_dir() else self.net_dir

    def call(self, method: str, *params, wallet: "str | None" = None, stdin: bool = False):
        """Run one bitcoin-cli command.

        stdin=True sends the parameters through bitcoin-cli's -stdin instead
        of argv, so key material never appears in a process listing.

        **Callers no longer have to remember.** This used to read "callers
        that pass an xprv or a private descriptor MUST set it (S4)", which
        put a correctness rule in the caller's head and enforced it
        nowhere. On 2026-09-05 a caller forgot and a master private key
        went into argv twice per paper check; a two-axis review found it,
        not the suite. An invariant a module can check for itself does not
        belong in its interface, so this one checks: any argument carrying
        a private key goes through stdin whether it was asked for or not.
        Passing stdin=True still works and is still right for a PSBT.

        Callers that pass a PSBT should set it, for a second reason.
        Linux caps any SINGLE argument at MAX_ARG_STRLEN, 32 pages, which
        is 128KB, separately from the 2MB ARG_MAX total. A PSBT carries a
        whole previous transaction per input, so a many-input PSBT passes
        that cap and execve fails with E2BIG. macOS has no per-argument
        cap, so this cannot reproduce on the dev machine (I-10).
        """
        cmd = list(self.base)
        if wallet:
            cmd.append(f"-rpcwallet={wallet}")
        args = [p if isinstance(p, str)
                else json.dumps(p, default=_json_decimal) for p in params]
        # The module knows what key material looks like; the caller should
        # not have to. An empty argument list stays on argv, because
        # -stdin with nothing to read is a blank line bitcoin-cli has no
        # use for.
        if args and any(any(x in a for x in XPRV_PREFIXES) for a in args):
            stdin = True
        feed = None
        if stdin:
            # bitcoin-cli -stdin reads the EXTRA ARGUMENTS from stdin, one
            # per line; the method itself stays in argv. Verified against
            # bitcoin-cli 31.1's own -stdin help text.
            cmd.append("-stdin")
            cmd.append(method)
            feed = "\n".join(args) + "\n"
        else:
            cmd += [method, *args]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 input=feed, timeout=RPC_TIMEOUT)
        except subprocess.TimeoutExpired:
            # A node that is SLOW rather than dead is the case the suites
            # never had: absent bitcoind fails fast, but one that holds the
            # socket and never answers used to block here for ever. There
            # was no timeout at all, so the panel froze on a busy screen
            # with no way out and no shell to fix it from (audit A4,
            # 2026-09-06, measured with SIGSTOP on a live node).
            #
            # RuntimeError, because that is what Session.HANDLED catches
            # and what every other Core failure raises. The panel gets an
            # error it can dismiss instead of nothing, for ever.
            raise RuntimeError(
                f"{method}: Bitcoin Core did not answer in "
                f"{RPC_TIMEOUT:.0f}s") from None
        if out.returncode != 0:
            raise RuntimeError(f"{method}: {redact(out.stderr.strip())}")
        text = out.stdout.strip()
        try:
            # parse_float=Decimal: BTC amounts must never pass through binary
            # floats — the review screen is the device's security boundary.
            return json.loads(text, parse_float=Decimal)
        except json.JSONDecodeError:
            return text


def build_descriptors(rpc: "Rpc", xprv: str) -> list[dict]:
    """All four policies, receive and change, checksummed by Core.

    BIP44 legacy, BIP49 nested segwit, BIP84 native segwit and BIP86
    taproot, which is what `createwallet` makes, so a key that arrives by
    scan or by typing presents the same wallet as one Core generated.
    """
    coin = 0 if rpc.chain == "main" else 1
    descs = []
    for purpose, shape in PURPOSE_FUNCS:
        for change in (0, 1):
            raw = shape.format(
                key=f"{xprv}/{purpose}h/{coin}h/0h/{change}/*")
            # getdescriptorinfo's "checksum" field covers the descriptor as
            # given (private form); its "descriptor" field is the public form.
            checksum = rpc.call("getdescriptorinfo", raw,
                                stdin=True)["checksum"]
            descs.append(_desc_entry(f"{raw}#{checksum}", internal=bool(change)))
    return descs


def _desc_entry(desc, internal):
    return {"desc": desc, "active": True, "internal": internal,
            "timestamp": "now", "range": [0, 200]}


def loaded_keys(rpc: "Rpc") -> list[Key]:
    """Every key in the session, in slot order, with its fingerprint."""
    loaded = set(rpc.call("listwallets"))
    return [Key(name, master_fingerprint(rpc, wallet=name))
            for name in SLOTS if name in loaded]


def _next_slot(rpc: "Rpc") -> str:
    """The first free wallet slot, or a refusal at the cap.

    Free means free on disk as well as unloaded. A slot whose directory
    survives without the wallet being loaded is invisible to `listwallets`,
    so picking it made `createwallet` fail with Core's raw "Database
    already exists", and no key could be loaded until the board rebooted
    (found 2026-09-05 by auditing every createwallet call site).
    """
    taken = set(_corky_wallets(rpc))
    for name in SLOTS:
        if name not in taken:
            return name
    raise RuntimeError(f"{MAX_KEYS} keys already loaded; discard one first")


def _import(rpc: "Rpc", descriptors: list[dict]) -> str:
    name = _next_slot(rpc)
    rpc.call("createwallet", name, False, True, "", False, True)
    result = rpc.call("importdescriptors", descriptors, wallet=name,
                      stdin=True)
    failures = [r for r in result if not r.get("success")]
    if failures:
        _drop_wallet(rpc, name)
        raise RuntimeError(f"importdescriptors failed: {failures}")
    # The fingerprint is only knowable once Core holds the key:
    # getdescriptorinfo's public form keeps hardened steps on the xpub and
    # carries no origin. So a duplicate is found after the import and the
    # new wallet is dropped again, leaving the session as it was.
    xfp = master_fingerprint(rpc, wallet=name)
    if any(k.xfp == xfp for k in loaded_keys(rpc) if k.name != name):
        _drop_wallet(rpc, name)
        raise RuntimeError(f"key {xfp} is already loaded")
    return name


def open_session_xprv(rpc: "Rpc", xprv: str) -> str:
    """Input mode 2: a raw BIP32 xprv (typed or from a static QR).
    Pure Core from the first byte; Corky applies the BIP84/86 paths.
    Returns the wallet name of the new key."""
    return _import(rpc, build_descriptors(rpc, xprv.strip()))


def open_session_descriptors(rpc: "Rpc", descriptors: list[str]) -> str:
    """Input mode 1: Core-native private descriptors (from a static QR).
    Fully self-describing; no assumed derivation paths.
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
        info = rpc.call("getdescriptorinfo", desc, stdin=True)
        bare = desc.split("#")[0]
        # Heuristic: a trailing /1/* branch is the change chain. Documented
        # limitation: multipath/nonstandard descriptors may need explicit
        # marking; Core accepts either labeling for signing purposes.
        imports.append(_desc_entry(f"{bare}#{info['checksum']}",
                                   internal=bare.endswith("/1/*)")))
    return _import(rpc, imports)


def public_descriptors(rpc: "Rpc", wallet: str = WALLET) -> list[str]:
    """What the coordinator needs: the watch-only (xpub) descriptors."""
    listed = rpc.call("listdescriptors", wallet=wallet)["descriptors"]
    return [d["desc"] for d in listed if d["active"]]


# What a coordinator may be given. Core creates all four of these per
# wallet and always has, verified against v31.1 on regtest 2026-09-05:
# pkh at 44h (legacy), sh(wpkh) at 49h (nested segwit), wpkh at 84h
# (native segwit) and tr at 86h (taproot). One master private key opens
# all four, so a paper backup covers them whatever the export shows.
#
# Corky offered two of the four until T0 of the export map, which meant
# coins sent to a legacy or nested address of this wallet were spendable
# by this key and invisible on the panel. Which of the four the SHIPPED
# flow offers is map ticket D1, decided once T1 to T3 say what each
# coordinator actually accepts. This table is what the device CAN emit.
#
# `sh` must be matched before `pkh` is read: the prefixes are distinct
# under startswith, but the order below is the order LEFT and RIGHT cycle
# on the panel, and native segwit stays first because it is the default.
EXPORT_KINDS = {"wpkh": "wpkh(", "tr": "tr(",
                "sh": "sh(wpkh(", "pkh": "pkh("}

#: The order LEFT and RIGHT walk on the export and address screens.
EXPORT_ORDER = ("wpkh", "tr", "sh", "pkh")


def export_descriptors(rpc: "Rpc", wallet: str = WALLET) -> list[str]:
    """Every public descriptor a coordinator may be given for this key:
    all four script policies, receive and change, as Core wrote them."""
    return [d for d in public_descriptors(rpc, wallet=wallet)
            if any(d.startswith(p) for p in EXPORT_KINDS.values())]


def origin_of(descriptor: str) -> "tuple[str, str]":
    """The master fingerprint and derivation path Core wrote into a
    descriptor, as `("73c5da0a", "m/84h/0h/0h")`.

    Read out of Core's own string rather than rebuilt from the script
    type, so the panel shows the path this key actually uses instead of
    the one BIP44 says it should. Returns empty strings if Core wrote no
    origin, which a bare descriptor can lack.
    """
    m = re.search(r"\[([0-9a-fA-F]{8})((?:/\d+[h']?)+)\]", descriptor)
    return (m.group(1).lower(), "m" + m.group(2)) if m else ("", "")


def available_kinds(rpc: "Rpc", wallet: str = WALLET) -> tuple[str, ...]:
    """The script policies THIS key actually has, in EXPORT_ORDER.

    Every key Corky opens has all four now: `createwallet` makes them and
    `build_descriptors` builds them, so a key restored from its own paper
    backup presents what the key that made it presented (map ticket D6).

    The function stays because a wallet is not obliged to hold four. One
    imported as a bare descriptor holds exactly what that descriptor
    described, and exporting a policy a wallet has not got should be
    something the panel cannot offer rather than an error the user reaches.
    """
    have = export_descriptors(rpc, wallet=wallet)
    return tuple(k for k in EXPORT_ORDER
                 if any(d.startswith(EXPORT_KINDS[k]) for d in have))


def export_descriptor(rpc: "Rpc", wallet: str, kind: str, branch: int = 0) -> str:
    """One public descriptor, Core's own string with its checksum.

    Sparrow's own library parses this verbatim and derives the same
    addresses Core does, for wpkh and tr (proved 2026-09-04). BlueWallet,
    Green and Bull Bitcoin are desk research only (tickets 19, 20, 21);
    what any of them does with legacy or nested segwit is unproven, which
    is what map tickets T1 to T3 are for.
    """
    prefix = EXPORT_KINDS[kind]
    want = f"/{branch}/*"
    for desc in export_descriptors(rpc, wallet=wallet):
        if desc.startswith(prefix) and want in desc:
            return desc
    raise RuntimeError(f"this key has no {kind} descriptor")


def receive_addresses(rpc: "Rpc", wallet: str, kind: str, count: int, start: int = 0) -> list[str]:
    """The first `count` receive addresses, derived by Core.

    `deriveaddresses` is side-effect free; `getnewaddress` advances the
    wallet's address index every time it is called, which is wrong for a
    screen that may be redrawn (verified against 31.1: keypool unmoved).
    """
    desc = export_descriptor(rpc, wallet, kind, branch=0)
    return rpc.call("deriveaddresses", desc, [start, start + count - 1])


#: What the watch-only wallet file is called. It carries no private key,
#: which is why it is the one file the private-key-on-paper rule (A-24)
#: still allows off this device.
WATCH_PREFIX = "corky-"


def write_watch_only(rpc: "Rpc", wallet: str, dest_dir: "str | Path") -> Path:
    """A watch-only wallet file for a laptop running Bitcoin Core.

    Core has no QR reader, so its half of the air gap is a file. Core's own
    `backupwallet` writes it, from a wallet made with `disable_private_keys`
    that holds nothing but the public descriptors, so no code of ours shapes
    the format and no secret can be in it. The scratch wallet is deleted
    again, so the session is left exactly as it was found.

    The file is named by the key's fingerprint. Returns its path.
    """
    xfp = master_fingerprint(rpc, wallet=wallet) or "unknown"
    descs = [_desc_entry(d, internal="/1/*" in d)
             for d in export_descriptors(rpc, wallet=wallet)]
    scratch = f"{wallet}-watch"
    _drop_wallet(rpc, scratch)
    # disable_private_keys=True, blank=True: a wallet that CANNOT hold a key.
    rpc.call("createwallet", scratch, True, True, "", False, True)
    try:
        result = rpc.call("importdescriptors", descs, wallet=scratch)
        failures = [r for r in result if not r.get("success")]
        if failures:
            raise RuntimeError(f"watch-only import failed: {failures}")
        out = Path(dest_dir) / f"{WATCH_PREFIX}{xfp}-watch.dat"
        rpc.call("backupwallet", str(out), wallet=scratch)
        return out
    finally:
        _drop_wallet(rpc, scratch)


def describe_psbt(rpc: "Rpc", psbt_b64: str) -> dict:
    """Everything the review screen shows. All numbers are Core's.

    The fee is computed by Core from coordinator-supplied input amounts;
    an air-gapped signer cannot verify those amounts against the chain.
    The screen must say so.
    """
    decoded = rpc.call("decodepsbt", psbt_b64, stdin=True)
    analysis = rpc.call("analyzepsbt", psbt_b64, stdin=True)
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


def owners(rpc: "Rpc", psbt_b64: str) -> set[str]:
    """The master fingerprints Core finds on the transaction's inputs.

    decodepsbt lists bip32_derivs on every input a coordinator described,
    and taproot_bip32_derivs on taproot inputs. Each carries the master
    fingerprint of the key that owns it. That is how a transaction names
    its key (ticket 03); Corky matches, Core decides.
    """
    decoded = rpc.call("decodepsbt", psbt_b64, stdin=True)
    found = set()
    for txin in decoded["inputs"]:
        for field in ("bip32_derivs", "taproot_bip32_derivs"):
            for deriv in txin.get(field, []):
                xfp = deriv.get("master_fingerprint")
                if xfp:
                    found.add(xfp.lower())
    return found


def sign_psbt(rpc: "Rpc", psbt_b64: str, wallet: str = WALLET) -> dict:
    result = rpc.call("walletprocesspsbt", psbt_b64, wallet=wallet,
                      stdin=True)
    return {"psbt": result["psbt"], "complete": result["complete"]}


def generate_wallet(rpc: "Rpc") -> str:
    """A-19: seed generation and usage EXACTLY as a Bitcoin Core wallet.

    `createwallet` makes Core generate its master key with its own RNG
    (GetStrongRandBytes) and derive the standard descriptor set, exactly
    as any Core wallet is born. Corky then simply USES that wallet, and
    the backup shown to the user is Core's own master xprv, read verbatim
    out of the descriptors Core wrote. Nothing of ours sits between
    Core's RNG and the backup: no extraction, no hashing, no reshaping.

    Returns the wallet name, and NOTHING ELSE (Ben, 2026-09-05). It used to
    return the master xprv too, so a key Core had just made was pulled back
    out into Corky's memory at the moment of birth, whether or not anyone
    ever asked to see it. A key generated here and backed up to an
    encrypted file is now never read out of Core at all. `master_xprv` is
    still there for the paper backup, which asks for it when the user
    chooses to look at it.

    The new key takes the next free slot beside the keys already loaded
    (ticket 03); at the cap the slot lookup refuses with a message the home
    screen can show. Raises if the descriptors do not all share one master
    key (they always do for Core-generated wallets; the check is a sanity
    assertion, not entropy verification).
    """
    name = _next_slot(rpc)
    rpc.call("createwallet", name)
    try:
        # One read, discarded immediately: it is the sanity check that all
        # the descriptors share a master, not a value anyone keeps.
        master_xprv(rpc, name)
    except RuntimeError:
        _drop_wallet(rpc, name)
        raise
    return name


def master_xprv(rpc: "Rpc", wallet: str = WALLET) -> str:
    """The wallet's master xprv, read verbatim from the private descriptors
    Core wrote. This is the paper backup (ticket 07): Core's own string,
    nothing of ours between Core and the page. Raises if the descriptors
    do not share one master key."""
    descs = rpc.call("listdescriptors", True, wallet=wallet)["descriptors"]
    masters = set()
    for d in descs:
        text = d["desc"]
        # innermost key expression: text after the LAST '(' up to '/' or ')'
        key = text[text.rindex("(") + 1:]
        for stop in "/)":
            if stop in key:
                key = key[: key.index(stop)]
        masters.add(key)
    if len(masters) != 1:
        raise RuntimeError(
            f"expected one master key across descriptors, got {len(masters)}")
    return masters.pop()


def opens_wallet(rpc: "Rpc", wallet: str, key: str, count: int = 2) -> bool:
    """Does this private key derive the addresses this wallet hands out?

    The question "does my paper open this wallet" asked the only way that
    can answer it: Core derives receive addresses from the TYPED key, Core
    reports the addresses the LOADED wallet gives, and Corky compares two
    lists of strings Core returned (PLAN A-11).

    Audit A6 (2026-09-06) found the check it replaces could not fail.
    `_check_page` only accepts a page when it matches the backup character
    for character, so by the time the flow asked Core to confirm, it was
    asking whether a string equalled itself. The screen said "your paper
    opens key X" on the strength of that. Deleting the whole comparison
    left every suite green, which is how it was found.

    The derivation path is read out of the wallet's OWN descriptor rather
    than rebuilt from the script type, so this follows the key wherever
    Core actually put it, including regtest's coin type 1.

    Nothing is created and nothing is written: `getdescriptorinfo` and
    `deriveaddresses` are both side-effect free. The key goes through
    `-stdin`, never argv, which is Rpc.call's standing rule for anything
    carrying an xprv. Core refuses a mistyped key at base58's own
    checksum, long before anything cryptographic happens, and Rpc.call
    redacts the key out of that error before it reaches a screen.
    """
    kind = available_kinds(rpc, wallet)[0]
    shapes = {shape.split("(")[0]: shape for _purpose, shape in PURPOSE_FUNCS}
    if kind not in shapes:
        raise RuntimeError(f"no descriptor shape for {kind}")
    _xfp, path = origin_of(export_descriptor(rpc, wallet, kind))
    if not path:
        raise RuntimeError("this wallet's descriptor carries no origin")
    want = receive_addresses(rpc, wallet, kind, count)
    raw = shapes[kind].format(key=f"{key}{path[1:]}/0/*")
    checksum = rpc.call("getdescriptorinfo", raw, stdin=True)["checksum"]
    got = rpc.call("deriveaddresses", f"{raw}#{checksum}",
                   [0, count - 1], stdin=True)
    return got == want


def _drop_wallet(rpc: "Rpc", name: str) -> None:
    """Unload and delete a wallet, ignoring the not-loaded case."""
    with contextlib.suppress(RuntimeError):
        rpc.call("unloadwallet", name)
    shutil.rmtree(rpc.wallet_dir / name, ignore_errors=True)


def master_fingerprint(rpc: "Rpc", wallet: str = WALLET) -> "str | None":
    """The wallet's master key fingerprint (XFP), or None if no wallet.

    Read from the PUBLIC descriptors: listdescriptors without the private
    flag, so nothing secret is fetched to draw a header. Core writes the
    origin as [XXXXXXXX/84h/...] at the front of every descriptor, and all
    of a wallet's descriptors share one master key.
    """
    try:
        descs = rpc.call("listdescriptors", wallet=wallet)["descriptors"]
    except (RuntimeError, KeyError, TypeError):
        return None                      # no wallet loaded: no fingerprint
    for d in descs:
        m = re.search(r"\[([0-9a-fA-F]{8})/", d.get("desc", ""))
        if m:
            return m.group(1).lower()
    return None


def _corky_wallets(rpc: "Rpc") -> list[str]:
    """Every wallet on this node that belongs to Corky, loaded or not.

    The five key slots, and also the scratch wallets the export and the
    file backup build (`corky-watch`, `corky-2-backup`, ...). A scratch
    holds the PRIVATE descriptors between `createwallet` and the `finally`
    that deletes it, so a crash in that window used to leave a plaintext
    key on the ramdisk that nothing ever dropped: not close_session, not
    the next session's clear_on_start, because both walked SLOTS only.
    Found by the two-axis review, 2026-09-05, and reproduced.

    Ownership is by name: `corky`, or anything beginning `corky-`. On the
    device Corky owns the whole node; in the test harness the
    coordinator's wallets are named otherwise and must survive.
    """
    names = set()
    with contextlib.suppress(RuntimeError):
        names.update(rpc.call("listwallets"))
    with contextlib.suppress(RuntimeError, KeyError, TypeError):
        names.update(w["name"] for w in rpc.call("listwalletdir")["wallets"])
    return sorted(n for n in names
                  if n == WALLET or n.startswith(WALLET + "-"))


def clear_on_start(rpc: "Rpc") -> list[str]:
    """Drop every key Corky did not load in THIS session, before the first
    screen is drawn. Returns the slot names it dropped.

    bitcoind runs under its own systemd unit (`corky-bitcoind.service`) and
    keeps running when `corky.service` restarts. `Restart=on-failure` means
    a crashed session comes straight back, and the ramdisk and the node
    both survive it, so without this the new session would adopt a key its
    user never entered and show it as loaded on the home screen.

    Only Corky's own wallets are dropped, slots and scratches alike. On the
    device the datadir is a fresh tmpfs at every boot, so no other wallet
    can be there; in the test harness the coordinator's wallets share the
    datadir and must survive.
    """
    dropped = _corky_wallets(rpc)
    for name in dropped:
        _drop_wallet(rpc, name)
    return dropped


def close_key(rpc: "Rpc", name: str) -> None:
    """Discard one key: unload its wallet and delete its directory."""
    _drop_wallet(rpc, name)


def close_session(rpc: "Rpc") -> None:
    """Unload AND delete every wallet Corky owns: the key slots and any
    scratch left by an export or a backup. On the device the datadir is a
    ramdisk and power-off is the real teardown; deleting here keeps every
    environment (and every test) as stateless as the hardware."""
    for name in _corky_wallets(rpc):
        _drop_wallet(rpc, name)


def stop_node(rpc: "Rpc", timeout: float = 30.0, poll: float = 0.2) -> bool:
    """Ask bitcoind to shut down, and wait until it stops answering.

    POWER OFF must leave nothing running (I-2). bitcoind holds the ramdisk
    datadir open, so a halt during a write can tear wallet.dat on any build
    that is not fully RAM-resident. Returns True if the node has gone, False
    if it outlived the timeout. The caller must show the False case: a
    device that says it is off while its node runs is audit defect D16.
    """
    try:
        rpc.call("stop")
    except RuntimeError:
        return True                    # already down, or never came up
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            rpc.call("uptime")
        except RuntimeError:
            return True                # RPC refused: the node has gone
        time.sleep(poll)
    return False
