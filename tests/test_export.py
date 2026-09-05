"""Export the public key (map e2e-before-testers, ticket 12).

What a coordinator needs, in the forms it can read, with nothing secret in
any of them. Run: python3 tests/test_export.py (needs bitcoind)
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

XPRV_A = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def start_node(prefix):
    datadir = tempfile.mkdtemp(prefix=prefix)
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


def main():
    daemon, rpc, datadir = start_node("export-")
    other, orpc, odir = start_node("laptop-")   # "a laptop running Core"
    work = Path(tempfile.mkdtemp(prefix="export-work-"))
    try:
        name = signer.open_session_xprv(rpc, XPRV_A)

        # 1. Only the two script types Corky hands out addresses from ever
        #    leave the device. A Core-generated wallet also carries legacy
        #    pkh and sh(wpkh) descriptors, and those must not be exported.
        gen_name, _ = signer.generate_wallet(rpc)
        pubs = signer.export_descriptors(rpc, gen_name)
        kinds = sorted({d.split("(")[0] for d in pubs})
        if kinds == ["tr", "wpkh"]:
            ok(f"export offers only wpkh and tr, not {len(pubs)} mixed kinds")
        else:
            bad(f"export offered {kinds}")
        if any("prv" in d for d in pubs):
            bad("an exported descriptor carries a private key")
        else:
            ok("no exported descriptor carries a private key")
        signer.close_key(rpc, gen_name)

        # 2. The descriptor Corky exports is Core's own string, byte for
        #    byte, with its checksum.
        desc = signer.export_descriptor(rpc, name, "wpkh")
        core = [d["desc"] for d in
                rpc.call("listdescriptors", wallet=name)["descriptors"]
                if d["desc"].startswith("wpkh(") and not d["internal"]][0]
        if desc == core:
            ok("the exported descriptor is Core's own string, checksum included")
        else:
            bad(f"export rewrote the descriptor:\n  {desc}\n  {core}")
        if signer.export_descriptor(rpc, name, "tr").startswith("tr("):
            ok("taproot exports too")
        else:
            bad("the taproot export is not a tr() descriptor")

        # 3. Addresses shown for comparison come from deriveaddresses, which
        #    is side-effect free. getnewaddress would advance the wallet's
        #    index every time the screen was drawn.
        before = rpc.call("getwalletinfo", wallet=name)["keypoolsize"]
        addrs = signer.receive_addresses(rpc, name, "wpkh", 3)
        after = rpc.call("getwalletinfo", wallet=name)["keypoolsize"]
        want = rpc.call("deriveaddresses", core, [0, 2])
        if addrs == want and len(addrs) == 3:
            ok(f"the first three addresses match Core: {addrs[0][:14]}…")
        else:
            bad(f"addresses {addrs} != Core's {want}")
        if before == after:
            ok(f"drawing the address screen does not move the keypool ({after})")
        else:
            bad(f"the keypool moved from {before} to {after}")

        # 3b. Browsing past the first block keeps deriving, and never
        #     repeats an address. Receive branch only, by decision.
        first = signer.receive_addresses(rpc, name, "wpkh", 10, 0)
        second = signer.receive_addresses(rpc, name, "wpkh", 10, 10)
        if len(set(first + second)) == 20 and first[:3] == addrs:
            ok("address browsing pages on without repeating (20 derived)")
        else:
            bad("address paging repeats or does not continue")
        change_desc = signer.export_descriptor(rpc, name, "wpkh", branch=1)
        change = rpc.call("deriveaddresses", change_desc, [0, 2])
        if not set(change) & set(first):
            ok("the change branch is a different set, and is not browsed")
        else:
            bad("a change address appeared in the receive list")

        # 4. Bitcoin Core has no QR reader, so its export is a watch-only
        #    wallet file made by Core's own backupwallet. A second Core
        #    restores it, owns the same addresses, and holds no private key.
        out = signer.write_watch_only(rpc, name, work)
        if out.exists() and out.stat().st_size > 0:
            ok(f"watch-only wallet file written: {out.name}")
        else:
            bad("no watch-only wallet file was written")
        orpc.call("restorewallet", "fromcorky", str(out))
        info = orpc.call("getwalletinfo", wallet="fromcorky")
        if info.get("private_keys_enabled") is False:
            ok("the restored wallet has no private keys")
        else:
            bad(f"the restored wallet reports private_keys_enabled="
                f"{info.get('private_keys_enabled')}")
        mine = orpc.call("getaddressinfo", addrs[0], wallet="fromcorky")
        if mine.get("ismine") and not mine.get("isscript", False):
            ok("the restored wallet owns Corky's first receive address")
        else:
            bad("the restored wallet does not own Corky's first address")
        # And the file itself carries no secret.
        from test_no_persistence import _key_bytes
        blob = out.read_bytes()
        if any(n in blob for n in _key_bytes(XPRV_A).values()):
            bad("the exported wallet file contains key material")
        else:
            ok("the exported wallet file contains no key material")

        # 4b. The screen that lists backups reads the fingerprint out of a
        #     filename, so its two constants must agree with signer's.
        sys.path.insert(0, str(ROOT / "corky"))
        import screens  # noqa: E402
        # Build the probe from a filename signer actually WROTE, not from
        # the screen's own constants, or the check could never see them
        # drift apart.
        real = signer.backup_encrypted(rpc, name, "probe passphrase", work)
        xfp = signer.master_fingerprint(rpc, wallet=name)
        if screens.fingerprint_of_backup(real.name) == xfp:
            ok(f"the restore screen reads {xfp} out of {real.name}")
        else:
            bad(f"the screen read {screens.fingerprint_of_backup(real.name)!r} "
                f"out of {real.name}, wanted {xfp}")

        # 5. Exporting must not disturb the session: the key still signs and
        #    no extra wallet is left behind.
        left = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        if left == [name]:
            ok("export leaves exactly the loaded key, no scratch wallet")
        else:
            bad(f"after export the loaded keys are {left}")
    finally:
        for r, d in ((rpc, daemon), (orpc, other)):
            try:
                r.call("stop")
            except Exception:
                pass
            d.wait(timeout=30)
        shutil.rmtree(datadir, ignore_errors=True)
        shutil.rmtree(odir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
