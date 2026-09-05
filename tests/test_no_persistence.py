"""No key material survives a discard, a close, a crash or a restart.

This is the product. Corky's claim is that the device holds nothing, so
this suite treats the whole datadir as one blob of bytes and refuses to
find a key in it. Map e2e-before-testers, ticket 08.

The first check is the one that makes the rest mean anything: while a key
IS loaded, the search must FIND it. A search that can never hit proves
nothing when it misses.

Run: python3 tests/test_no_persistence.py (needs bitcoind)
"""
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402

XPRV_A = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def _key_bytes(xprv):
    """The secret bytes behind a base58check xprv.

    Core does NOT store the xprv as text. `wallet.dat` holds the PUBLIC
    descriptor (a tpub) plus the raw private key in its own record, so a
    text search for "tprv..." finds nothing and would pass every check in
    this file while the key sat on disk. Verified against Core 31.1 on
    2026-09-05: the 32-byte private key appears in `wallet.dat` and in
    `wallet.dat-journal`.

    BIP32 serialisation, 78 bytes: 4 version, 1 depth, 4 parent
    fingerprint, 4 child number, 32 chain code, 33 key data (0x00 then the
    32-byte private key).
    """
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in xprv:
        n = n * 58 + alphabet.index(ch)
    ser = n.to_bytes(82, "big")[:-4]
    return {"private key": ser[46:78], "chain code": ser[13:45],
            "xprv text": xprv.encode()}


def hits(root: Path, xprv):
    """Every (file, form) under `root` that holds any part of the key."""
    needles = _key_bytes(xprv)
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for form, needle in needles.items():
            if needle in blob:
                found.append(f"{path.relative_to(root)} ({form})")
    return found


def start_node(datadir=None):
    datadir = datadir or tempfile.mkdtemp(prefix="nopersist-")
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % random.randint(20000, 60000))
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-regtest", "-networkactive=0",
         "-listen=0", "-server=1", "-fallbackfee=0.0001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    for _ in range(120):
        try:
            rpc.call("getblockcount"); break
        except RuntimeError:
            time.sleep(0.5)
    return daemon, rpc, Path(datadir)


def test_production_conf():
    """The conf the device ships with must not write a log file. Core reads
    `debuglogfile=0` as a FILENAME and writes the log to a file called `0`
    (seen on the board 2026-09-04), and its own first line warns the log
    may contain privacy-sensitive information."""
    conf = (ROOT / "m0" / "bitcoin.conf").read_text()
    live = [ln.strip() for ln in conf.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    if any(ln.startswith("debuglogfile") for ln in live):
        bad("m0/bitcoin.conf sets debuglogfile, which NAMES a log file")
    elif "nodebuglogfile=1" not in live:
        bad("m0/bitcoin.conf does not turn the debug log off")
    else:
        ok("the shipped bitcoin.conf writes no log file")


def main():
    test_production_conf()
    daemon, rpc, datadir = start_node()
    try:
        # 1. SANITY. While the key is loaded, the search finds it. Without
        #    this every later check could pass by being blind.
        name = signer.open_session_xprv(rpc, XPRV_A)
        live = hits(datadir, XPRV_A)
        if live:
            ok(f"while loaded, the key is on disk in {len(live)} file(s): "
               f"{live[0]}")
        else:
            bad("the search cannot find a LOADED key; every other check "
                "in this suite is meaningless")

        # 2. Discard one key: not one byte of it is left.
        signer.close_key(rpc, name)
        left = hits(datadir, XPRV_A)
        if not left:
            ok("after close_key, the key is in no file under the datadir")
        else:
            bad(f"close_key left the key in {left}")

        # 3. Core's own log must never carry key material.
        logs = [p for p in datadir.rglob("*") if p.is_file()
                and p.name in ("debug.log", "0")]
        leaky = [p.relative_to(datadir) for p in logs
                 if any(n in p.read_bytes()
                        for n in _key_bytes(XPRV_A).values())]
        if not leaky:
            ok(f"Core's log files ({len(logs)} found) carry no key material")
        else:
            bad(f"a Core log file carries the key: {leaky}")

        # 4. A generated key, discarded, leaves nothing either. Its xprv
        #    was never typed by anyone, so this covers the A-19 path.
        gen_name, gen_xprv = signer.generate_wallet(rpc)
        if hits(datadir, gen_xprv):
            ok("sanity: the generated key is on disk while loaded")
        else:
            bad("the generated key was not found on disk while loaded")
        signer.close_key(rpc, gen_name)
        if not hits(datadir, gen_xprv):
            ok("after close_key, the generated key is gone from the datadir")
        else:
            bad(f"a generated key survived close_key: {hits(datadir, gen_xprv)}")

        # 5. close_session clears every slot, not just the current one.
        keys = []
        for _ in range(3):
            n, x = signer.generate_wallet(rpc)
            keys.append(x)
        signer.close_session(rpc)
        survivors = [x[:12] for x in keys if hits(datadir, x)]
        if not survivors:
            ok("close_session leaves none of three keys anywhere on disk")
        else:
            bad(f"close_session left keys behind: {survivors}")
        dirs = [n for n in signer.SLOTS if (rpc.wallet_dir / n).exists()]
        if not dirs:
            ok("close_session leaves no wallet directory behind")
        else:
            bad(f"wallet directories survived close_session: {dirs}")

        # 6. A key loaded by anything other than this session must not
        #    survive into it. bitcoind runs under its own systemd unit and
        #    keeps running when corky.service restarts, so a crashed
        #    session leaves its wallet loaded in Core.
        signer.open_session_xprv(rpc, XPRV_A)
        loaded_before = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        signer.clear_on_start(rpc)
        loaded_after = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        if loaded_before and not loaded_after and not hits(datadir, XPRV_A):
            ok("clear_on_start drops a key left loaded by an earlier session")
        else:
            bad(f"a stray key survived startup: loaded {loaded_after}, "
                f"files {hits(datadir, XPRV_A)}")

        # 6b. A scratch wallet is Corky's too. backup_encrypted holds the
        #     PRIVATE descriptors in `<slot>-backup` between createwallet
        #     and the finally that deletes it. A crash in that window used
        #     to leave a plaintext key that neither close_session nor the
        #     next clear_on_start dropped, because both walked the five
        #     slots only. Found by the two-axis review, 2026-09-05.
        slot = signer.open_session_xprv(rpc, XPRV_A)
        descs = rpc.call("listdescriptors", True, wallet=slot)["descriptors"]
        rpc.call("createwallet", f"{slot}-backup", False, True, "", False, True)
        rpc.call("importdescriptors",
                 [signer._desc_entry(d["desc"], internal=d.get("internal", False))
                  for d in descs], wallet=f"{slot}-backup", stdin=True)
        if hits(datadir, XPRV_A):
            ok("sanity: the abandoned scratch holds the key on disk")
        else:
            bad("the scratch wallet did not hold the key; check is blind")
        signer.close_session(rpc)
        if not hits(datadir, XPRV_A):
            ok("close_session drops an abandoned scratch wallet too")
        else:
            bad(f"a scratch wallet survived close_session: "
                f"{hits(datadir, XPRV_A)}")
        rpc.call("createwallet", f"{slot}-backup", False, True, "", False, True)
        rpc.call("importdescriptors",
                 [signer._desc_entry(d["desc"], internal=d.get("internal", False))
                  for d in descs], wallet=f"{slot}-backup", stdin=True)
        signer.clear_on_start(rpc)
        if not hits(datadir, XPRV_A):
            ok("clear_on_start drops an abandoned scratch wallet too")
        else:
            bad(f"a scratch survived startup: {hits(datadir, XPRV_A)}")

        # 7. The teardown the device really runs: a key is loaded, the
        #    session closes it, and only then does bitcoind stop. This is
        #    the sequence in Session.run's finally and the node unit's
        #    ExecStop, and it is the last moment a key could reach a card
        #    on a build whose datadir is not a ramdisk.
        signer.open_session_xprv(rpc, XPRV_A)
        signer.close_session(rpc)

        # 8. Core must not echo key material into an error message, which
        #    would put it on screen and into stderr.
        try:
            signer.open_session_xprv(rpc, XPRV_A[:-1] + "x")
            bad("a corrupt xprv was accepted")
        except RuntimeError as exc:
            if XPRV_A[:20] in str(exc):
                bad(f"Core's error message echoes the key: {str(exc)[:90]}")
            elif "<key redacted>" not in str(exc):
                bad(f"the key was not redacted, and not present either: "
                    f"{str(exc)[:90]}")
            else:
                ok("a rejected key is redacted out of the error message")

        # 8b. The same redaction must hold for every prefix and for text
        #     that merely contains a key, since this is what reaches the
        #     systemd journal on the card.
        for prefix in ("xprv", "tprv", "yprv", "zprv", "vprv", "uprv"):
            probe = prefix + XPRV_A[4:]
            out = signer.redact(f"error: key '{probe}' is not valid")
            if probe in out or "redacted" not in out:
                bad(f"redact() let a {prefix} through: {out[:70]}")
                break
        else:
            ok("redact() removes every extended-private-key prefix")
        if signer.redact("wpkh(tpubD6NzVbkrYhZ4XYa9MoLt4BiMZ4gkt2faZ4Bcm)") \
                != "wpkh(tpubD6NzVbkrYhZ4XYa9MoLt4BiMZ4gkt2faZ4Bcm)":
            bad("redact() damaged a public key, which the screen needs")
        else:
            ok("redact() leaves public keys alone")
    finally:
        try:
            rpc.call("stop")
        except Exception:
            pass
        daemon.wait(timeout=30)
        # 9. And the stop itself writes nothing back (step 7 set this up).
        after_stop = hits(datadir, XPRV_A)
        if not after_stop:
            ok("bitcoind's own shutdown writes no key back to the datadir")
        else:
            bad(f"shutdown wrote the key back: {after_stop}")
        shutil.rmtree(datadir, ignore_errors=True)

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
