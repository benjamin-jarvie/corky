"""A-19 exact-Core generation: key gen and usage exactly as a Core wallet.
Run: python3 tests/test_generate.py (needs bitcoind)
"""
import subprocess
import sys
import tempfile
import time
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)

def main():
    import random as _r  # test harness only, for the rpc port
    datadir = tempfile.mkdtemp(prefix="gen-")
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % _r.randint(20000, 60000))
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-regtest", "-networkactive=0",
         "-listen=0", "-server=1", "-fallbackfee=0.0001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(120):
            try: rpc.call("getblockcount"); break
            except RuntimeError: time.sleep(0.5)

        # 1. Core generates; the returned key is Core's depth-0 master.
        _, xprv = signer.generate_wallet(rpc)
        if xprv.startswith("tprv8ZgxMBicQKsP") or xprv.startswith("xprv9s21ZrQH143K"):
            ok("master xprv is depth-0 (Core's own master key)")
        else:
            bad(f"unexpected master key prefix: {xprv[:16]}")

        # 2. Usage exactly as Core: the SAME wallet Core created signs.
        descs = rpc.call("listdescriptors", True, wallet=signer.WALLET)["descriptors"]
        masters = set()
        for d in descs:
            k = d["desc"][d["desc"].rindex("(") + 1:]
            for stop in "/)":
                if stop in k: k = k[:k.index(stop)]
            masters.add(k)
        ok("all Core descriptors share the one master") if masters == {xprv} else \
            bad(f"descriptor masters {len(masters)} != returned key")

        addr = rpc.call("getnewaddress", wallet=signer.WALLET)
        rpc.call("createwallet", "miner")
        maddr = rpc.call("getnewaddress", wallet="miner")
        rpc.call("generatetoaddress", 101, maddr)
        rpc.call("sendtoaddress", addr, 1.0, wallet="miner")
        rpc.call("generatetoaddress", 1, maddr)
        dest = rpc.call("getnewaddress", wallet="miner")
        funded = rpc.call("walletcreatefundedpsbt", [], [{dest: 0.5}],
                          0, {"fee_rate": 5}, True, wallet=signer.WALLET)
        signed = signer.sign_psbt(rpc, funded["psbt"])
        ok("Core-generated wallet signs a PSBT to completion") if signed["complete"] else \
            bad("PSBT incomplete")

        # 3. Restore path: the xprv backup opens an equivalent 84h wallet.
        w1_addr = rpc.call("deriveaddresses",
                           next(d["desc"] for d in rpc.call("listdescriptors", wallet=signer.WALLET)["descriptors"]
                                if d["desc"].startswith("wpkh(") and not d["internal"]),
                           [0, 0])[0]
        signer.close_session(rpc)
        signer.open_session_xprv(rpc, xprv)
        w2 = rpc.call("listdescriptors", wallet=signer.WALLET)["descriptors"]
        w2_addr = rpc.call("deriveaddresses",
                           next(d["desc"] for d in w2
                                if d["desc"].startswith("wpkh(") and not d["internal"]),
                           [0, 0])[0]
        ok("xprv restore derives the same BIP84 addresses") if w1_addr == w2_addr else \
            bad(f"restore mismatch {w1_addr} vs {w2_addr}")

        # 4. Statelessness: close deletes.
        signer.close_session(rpc)
        ok("session wallet deleted after close") if \
            signer.WALLET not in rpc.call("listwallets") else bad("wallet lingers")

        # 5. No Python RNG in shipped modules (screens excepted: Pillow
        # imports random internally; screens never sees entropy).
        # A-22: codex32 and seedqr left main with the rest of Layer 1.
        for mod in ["signer", "filechannel", "qrchannel", "main", "hal"]:
            src = (ROOT / ("corky/%s.py" % mod)).read_text()
            for bad_import in ["os.urandom", "import random", "import secrets"]:
                if bad_import in src:
                    bad(f"{mod}.py contains {bad_import}")
        # A-22: shim/ is gone. There is no shipped module outside corky/.
        ok("no Python RNG in any shipped module")
    finally:
        try: rpc.call("stop"); daemon.wait(timeout=30)
        except Exception: daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)

    if fails:
        sys.exit(1)
    print("\nGENERATE PASS (exact-Core)")

if __name__ == "__main__":
    main()
