"""Several keys in one session (map e2e-before-testers, tickets 03 and 10).
One Core wallet per key, up to five, the fingerprint names the key on
screen. Run: python3 tests/test_keys.py (needs bitcoind)
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

# The key every other suite uses (the old "abandon x11 about" on regtest).
XPRV_A = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def start_node():
    datadir = tempfile.mkdtemp(prefix="keys-")
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
    return daemon, rpc, datadir


def fresh_xprv(rpc):
    """A second key, born in Core and then thrown away as a wallet."""
    rpc.call("createwallet", "donor")
    descs = rpc.call("listdescriptors", True, wallet="donor")["descriptors"]
    text = descs[0]["desc"]
    key = text[text.rindex("(") + 1:]
    for stop in "/)":
        if stop in key:
            key = key[: key.index(stop)]
    rpc.call("unloadwallet", "donor")
    shutil.rmtree(rpc.wallet_dir / "donor", ignore_errors=True)
    return key


def test_wallet_dir_without_wallets_subdir():
    """Core keeps wallets directly in the datadir when no wallets/ directory
    exists, which is what the Zero 2 W's ramdisk datadir looks like. Seen on
    the board 2026-09-04: /run/corky/probe2, no /run/corky/wallets.
    _drop_wallet must delete the directory Core actually used."""
    datadir = Path(tempfile.mkdtemp(prefix="keys-dir-"))
    rpc = signer.Rpc(str(datadir), chain="regtest",
                     cli="false")     # every call fails as a refused RPC would
    root_style = datadir / "regtest" / "corky"
    root_style.mkdir(parents=True)
    (root_style / "wallet.dat").write_bytes(b"x")
    signer._drop_wallet(rpc, "corky")
    if not root_style.exists():
        ok("_drop_wallet deletes a wallet Core kept in the datadir root")
    else:
        bad("_drop_wallet missed the datadir-root wallet directory")
    sub_style = datadir / "regtest" / "wallets" / "corky"
    sub_style.mkdir(parents=True)
    (sub_style / "wallet.dat").write_bytes(b"x")
    signer._drop_wallet(rpc, "corky")
    if not sub_style.exists():
        ok("_drop_wallet deletes a wallet Core kept under wallets/")
    else:
        bad("_drop_wallet missed the wallets/ directory")
    shutil.rmtree(datadir, ignore_errors=True)


def main():
    test_wallet_dir_without_wallets_subdir()
    daemon, rpc, datadir = start_node()
    try:
        xprv_b = fresh_xprv(rpc)

        # 1. Two keys loaded: both listed, in load order, first keeps the
        #    historic wallet name so every older suite still finds it.
        name_a = signer.open_session_xprv(rpc, XPRV_A)
        name_b = signer.open_session_xprv(rpc, xprv_b)
        keys = signer.loaded_keys(rpc)
        names = [k.name for k in keys]
        xfps = [k.xfp for k in keys]
        if names == ["corky", "corky-2"] and name_a == "corky" and name_b == "corky-2":
            ok("two keys occupy slots corky and corky-2, in load order")
        else:
            bad(f"slots {names}, returned {name_a}, {name_b}")
        if len(set(xfps)) == 2 and all(len(x) == 8 for x in xfps):
            ok("each loaded key carries its own 8-hex fingerprint")
        else:
            bad(f"fingerprints {xfps}")

        # 2. The same key again is refused by name, and nothing changes.
        try:
            signer.open_session_xprv(rpc, XPRV_A)
            bad("duplicate key was loaded")
        except RuntimeError as exc:
            if xfps[0] in str(exc) and "already loaded" in str(exc):
                ok(f"duplicate refused, message names {xfps[0]}")
            else:
                bad(f"duplicate refused with the wrong message: {exc}")
        if signer.loaded_keys(rpc) == keys:
            ok("loaded keys unchanged after the refusal")
        else:
            bad(f"loaded keys changed: {signer.loaded_keys(rpc)}")

        # 3. The cap: five load, the sixth is refused, five remain.
        for _ in range(3):
            signer.open_session_xprv(rpc, fresh_xprv(rpc))
        five = signer.loaded_keys(rpc)
        try:
            signer.open_session_xprv(rpc, fresh_xprv(rpc))
            bad("a sixth key was loaded")
        except RuntimeError as exc:
            if "5 keys already loaded" in str(exc):
                ok("sixth key refused: " + str(exc))
            else:
                bad(f"sixth key refused with the wrong message: {exc}")
        if [k.name for k in five] == list(signer.SLOTS) and signer.loaded_keys(rpc) == five:
            ok("five keys fill the five slots and survive the refusal")
        else:
            bad(f"after the cap: {signer.loaded_keys(rpc)}")
        for k in five[2:]:
            signer.close_key(rpc, k.name)
        keys = signer.loaded_keys(rpc)
        if [k.name for k in keys] == ["corky", "corky-2"]:
            ok("close_key drops one key at a time; two remain")
        else:
            bad(f"after close_key: {keys}")

        # 4. A transaction names its key. Fund key A, build a PSBT from A's
        #    wallet, and Core's decodepsbt says whose inputs they are.
        a, b = keys
        rpc.call("createwallet", "miner")
        maddr = rpc.call("getnewaddress", wallet="miner")
        rpc.call("generatetoaddress", 101, maddr)
        rpc.call("sendtoaddress", rpc.call("getnewaddress", wallet=a.name), 1.0,
                 wallet="miner")
        rpc.call("generatetoaddress", 1, maddr)
        psbt = rpc.call("walletcreatefundedpsbt", [], [{maddr: 0.5}], 0,
                        {"fee_rate": 5}, True, wallet=a.name)["psbt"]
        owners = signer.owners(rpc, psbt)
        if owners == {a.xfp}:
            ok(f"owners() names key {a.xfp} and nobody else")
        else:
            bad(f"owners() gave {owners}, wanted {{{a.xfp!r}}}")
        if not signer.sign_psbt(rpc, psbt, wallet=b.name)["complete"]:
            ok("the other key cannot complete it")
        else:
            bad("the other key completed a transaction it does not own")
        if signer.sign_psbt(rpc, psbt, wallet=a.name)["complete"]:
            ok("the owning key completes it")
        else:
            bad("the owning key could not complete its own transaction")

        # 5. Generate takes the next free slot and keeps the loaded keys.
        name_c, xprv_c = signer.generate_wallet(rpc)
        after = signer.loaded_keys(rpc)
        if name_c == "corky-3" and [k.name for k in after] == ["corky", "corky-2", "corky-3"]:
            ok("generate_wallet took slot corky-3 and kept the other two")
        else:
            bad(f"generate gave {name_c}; loaded {after}")
        if xprv_c.startswith("tprv8ZgxMBicQKsP") and after[2].xfp == signer.master_fingerprint(rpc, wallet=name_c):
            ok("generated key is Core's depth-0 master, listed by its fingerprint")
        else:
            bad(f"generated key {xprv_c[:16]}… xfp {after[2].xfp}")

        # 6. close_session drops every slot and every directory.
        signer.close_session(rpc)
        left = signer.loaded_keys(rpc)
        dirs = [n for n in signer.SLOTS if (rpc.wallet_dir / n).exists()]
        if not left and not dirs:
            ok("close_session leaves no key loaded and no wallet directory")
        else:
            bad(f"after close_session: loaded {left}, dirs {dirs}")
    finally:
        try: rpc.call("stop")
        except Exception: pass
        daemon.wait(timeout=30)
        shutil.rmtree(datadir, ignore_errors=True)
    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
