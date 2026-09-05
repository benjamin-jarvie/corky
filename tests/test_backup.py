"""The file backup, made by Core's own commands (ticket 13).

encryptwallet then backupwallet, restored on another computer running Core
with restorewallet and walletpassphrase. Corky's part is one passphrase
screen and the calls. Run: python3 tests/test_backup.py (needs bitcoind)
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
sys.path.insert(0, str(ROOT / "tests"))
import signer  # noqa: E402
from test_no_persistence import _key_bytes  # noqa: E402

XPRV_A = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"
PASSPHRASE = "correct horse battery staple"

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def start_node(prefix):
    datadir = tempfile.mkdtemp(prefix=prefix)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % random.randint(20000, 60000))
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-regtest", "-listen=0",
         "-server=1", "-fallbackfee=0.0001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    for _ in range(120):
        try:
            rpc.call("getblockcount"); break
        except RuntimeError:
            time.sleep(0.5)
    return daemon, rpc, datadir


def main():
    daemon, rpc, datadir = start_node("backup-")
    other, orpc, odir = start_node("laptop2-")     # another computer, Core
    work = Path(tempfile.mkdtemp(prefix="backup-work-"))
    try:
        name = signer.open_session_xprv(rpc, XPRV_A)
        addr0 = signer.receive_addresses(rpc, name, "wpkh", 1)[0]

        # 1. The backup is written, named by fingerprint.
        out = signer.backup_encrypted(rpc, name, PASSPHRASE, work)
        xfp = signer.master_fingerprint(rpc, wallet=name)
        if out.exists() and xfp in out.name:
            ok(f"backup written and named by fingerprint: {out.name}")
        else:
            bad(f"backup file wrong: {out}")

        # 2. It is really encrypted: none of the key's bytes are in it.
        blob = out.read_bytes()
        present = [form for form, n in _key_bytes(XPRV_A).items() if n in blob]
        if not present:
            ok("no part of the key appears in the backup file")
        else:
            bad(f"the backup file exposes the {present} in plain form")

        # 3. Making a backup must not change the key you are using. The
        #    session wallet stays unencrypted and keeps signing with no
        #    passphrase, because the encryption happens on a scratch copy.
        info = rpc.call("getwalletinfo", wallet=name)
        if "unlocked_until" not in info:
            ok("the loaded key is untouched: still unencrypted")
        else:
            bad("making a backup encrypted the key the user is signing with")
        left = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        if left == [name]:
            ok("no scratch wallet is left behind")
        else:
            bad(f"wallets after backup: {left}")

        # 4. Another computer running Core restores it and can spend, but
        #    only after the passphrase.
        rname = signer.restore_encrypted(orpc, out, PASSPHRASE)
        rinfo = orpc.call("getwalletinfo", wallet=rname)
        if rinfo.get("private_keys_enabled") and "unlocked_until" in rinfo:
            ok(f"restored into slot {rname}: has private keys, is encrypted")
        else:
            bad(f"restored wallet is wrong shape: {rinfo.get('walletname')}")
        if orpc.call("getaddressinfo", addr0, wallet=rname)["ismine"]:
            ok("the restored key owns the address Corky showed")
        else:
            bad("the restored key does not own Corky's first address")

        # 5. It really signs, on the other machine, through the same path
        #    Corky uses.
        orpc.call("createwallet", "miner2")
        maddr = orpc.call("getnewaddress", wallet="miner2")
        orpc.call("generatetoaddress", 101, maddr, wallet="miner2")
        orpc.call("sendtoaddress", addr0, 1.0, wallet="miner2")
        orpc.call("generatetoaddress", 1, maddr, wallet="miner2")
        psbt = orpc.call("walletcreatefundedpsbt", [], [{maddr: 0.5}], 0,
                         {"fee_rate": 5}, True, wallet=rname)["psbt"]
        if signer.sign_psbt(orpc, psbt, wallet=rname)["complete"]:
            ok("the restored key signs a transaction to completion")
        else:
            bad("the restored key could not sign")

        # 6. A wrong passphrase is refused, and leaves nothing loaded.
        before = [w for w in orpc.call("listwallets") if w in signer.SLOTS]
        try:
            signer.restore_encrypted(orpc, out, "not the passphrase")
            bad("a wrong passphrase was accepted")
        except RuntimeError as exc:
            if "passphrase" in str(exc).lower():
                ok(f"wrong passphrase refused: {exc}")
            else:
                bad(f"wrong passphrase gave an unhelpful error: {exc}")
        after = [w for w in orpc.call("listwallets") if w in signer.SLOTS]
        if before == after:
            ok("a failed restore leaves no half-loaded key behind")
        else:
            bad(f"a failed restore left {set(after) - set(before)}")

        # 7. A file that is not a wallet is refused without a crash
        #    (TESTING.md rule 1: feed the surface real, wrong data).
        junk = work / "notawallet.dat"
        junk.write_bytes(b"this is not a wallet\x00" * 40)
        try:
            signer.restore_encrypted(orpc, junk, PASSPHRASE)
            bad("a junk file was accepted as a wallet")
        except RuntimeError as exc:
            ok(f"a junk file is refused: {str(exc)[:60]}")

        # 8. The watch-only export cannot be restored as a key: it holds
        #    none, and restoring it would give a wallet that cannot sign.
        watch = signer.write_watch_only(rpc, name, work)
        try:
            signer.restore_encrypted(orpc, watch, PASSPHRASE)
            bad("the watch-only export was accepted as a key backup")
        except RuntimeError as exc:
            if "private key" in str(exc):
                ok("the watch-only export is refused as a key backup")
            else:
                bad(f"unclear refusal for the watch-only file: {exc}")
    finally:
        for r, d in ((rpc, daemon), (orpc, other)):
            try:
                r.call("stop")
            except Exception:
                pass
            d.wait(timeout=30)
        for path in (datadir, odir, work):
            shutil.rmtree(path, ignore_errors=True)
    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
