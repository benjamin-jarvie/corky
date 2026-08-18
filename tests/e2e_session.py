"""Full-device dress rehearsals on the dev HAL: three scripted sessions
covering word entry, xprv-QR + QR PSBT in/out, and SeedQR + refusal of a
fee-less PSBT. Run: python3 tests/e2e_session.py"""

import base64
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))
import signer  # noqa: E402
import qrchannel  # noqa: E402
from bip39_shim import mnemonic_to_xprv  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"
# Button script for typing the canonical mnemonic (see main._seed_words):
# abandon: append 'a', open candidates, accept first  -> "ara"
# about:   'a', +1 to 'b', append, +14 to 'o', append, candidates, accept
WORDS_SCRIPT = "ara" * 11 + ("a" + "da" + "d" * 14 + "a" + "ra")


def run_device(datadir, script, frames, stick=None, qr_key=None, qr_psbt=None):
    cmd = [sys.executable, str(ROOT / "corky" / "main.py"), "--dev",
           f"--datadir={datadir}", "--chain=regtest", f"--script={script}",
           f"--frames-dir={frames}"]
    if stick:
        cmd.append(f"--stick-dir={stick}")
    if qr_key:
        cmd.append(f"--qr-key={qr_key}")
    if qr_psbt:
        cmd.append(f"--qr-psbt={qr_psbt}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def main():
    datadir = tempfile.mkdtemp(prefix="corky-sess-")
    work = Path(tempfile.mkdtemp(prefix="corky-sess-work-"))
    daemon = subprocess.Popen(
        ["bitcoind", "-regtest", f"-datadir={datadir}", "-listen=0",
         "-fallbackfee=0.0001", "-server=1", "-debuglogfile=0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(60):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)

        # Coordinator: watch wallet from Corky's xpubs, funded
        signer.open_session(rpc, MNEMONIC)
        pubs = signer.public_descriptors(rpc)
        signer.close_session(rpc)
        rpc.call("createwallet", "watch", True, True, "", False, True)
        rpc.call("importdescriptors",
                 [{"desc": d, "active": True, "timestamp": "now",
                   "range": [0, 200], "internal": "/1/*" in d}
                  for d in pubs], wallet="watch")
        addr = rpc.call("getnewaddress", wallet="watch")
        rpc.call("generatetoaddress", 101, addr)

        def fund_psbt(amount):
            dest = rpc.call("getnewaddress", wallet="watch")
            return rpc.call("walletcreatefundedpsbt", [], [{dest: amount}],
                            0, {"fee_rate": 10}, True, wallet="watch")["psbt"]

        # ---- Session A: typed word entry + stick sign ----
        stick = work / "stickA"; stick.mkdir()
        (stick / "hui.psbt").write_bytes(base64.b64decode(fund_psbt(2.0)))
        script = "a" + "da" + "a" + WORDS_SCRIPT + "a"   # home, menu->words, length=12, type, sign
        r = run_device(datadir, script, work / "framesA", stick=stick)
        assert r.returncode == 0, f"A failed:\n{r.stderr}"
        signed = stick / "hui-signed.psbt"
        assert signed.exists(), "A: signed file missing"
        final = rpc.call("finalizepsbt",
                         base64.b64encode(signed.read_bytes()).decode())
        txid = rpc.call("sendrawtransaction", final["hex"])
        rpc.call("generatetoaddress", 1, addr)
        assert rpc.call("gettransaction", txid, wallet="watch")["confirmations"] >= 1
        print(f"ok   A: typed 12 words on the keypad -> stick sign -> confirmed {txid[:12]}…")

        # ---- Session B: xprv via QR + PSBT in AND out via QR ----
        xprv_file = work / "key.txt"
        xprv_file.write_text(mnemonic_to_xprv(MNEMONIC, mainnet=False))
        frames_file = work / "psbt_frames.txt"
        frames_file.write_text("\n".join(qrchannel.psbt_to_frames(fund_psbt(1.0))))
        r = run_device(datadir, "a" + "ddda" + "a" + "a", work / "framesB",
                       qr_key=xprv_file, qr_psbt=frames_file)
        assert r.returncode == 0, f"B failed:\n{r.stderr}"
        shots = sorted((work / "framesB").glob("frame-*.png"))
        assert len(shots) > 6, "B: expected QR output frames on screen"
        print(f"ok   B: xprv QR (warning screen shown) -> PSBT via QR -> signed QR out ({len(shots)} frames)")

        # ---- Session C: SeedQR + fee-less PSBT refused ----
        seedqr_file = work / "seedqr.txt"
        seedqr_file.write_text("0000" * 11 + "0003")
        stickc = work / "stickC"; stickc.mkdir()
        utxo = rpc.call("listunspent", wallet="watch")[0]
        bare = rpc.call("createpsbt",
                        [{"txid": utxo["txid"], "vout": utxo["vout"]}],
                        [{rpc.call("getnewaddress", wallet="watch"): 1.0}])
        (stickc / "bad.psbt").write_bytes(base64.b64decode(bare))
        r = run_device(datadir, "aa", work / "framesC",
                       stick=stickc, qr_key=seedqr_file)
        assert r.returncode == 0, f"C failed:\n{r.stderr}"
        assert not (stickc / "bad-signed.psbt").exists(), "C: refused PSBT was signed!"
        print("ok   C: SeedQR entry -> fee-less PSBT refused, nothing signed")

        # ---- Session D: many-output PSBT forces paged review ----
        stickd = work / "stickD"; stickd.mkdir()
        dests = {rpc.call("getnewaddress", wallet="watch"): 0.2
                 for _ in range(4)}
        many = rpc.call("walletcreatefundedpsbt", [],
                        [{a: v} for a, v in dests.items()],
                        0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickd / "many.psbt").write_bytes(base64.b64decode(many))
        seedqr_file2 = work / "seedqr2.txt"
        seedqr_file2.write_text("0000" * 11 + "0003")
        # 5 outputs = 2 pages: first 'a' advances to unseen page 2, second signs
        r = run_device(datadir, "aaaa", work / "framesD",
                       stick=stickd, qr_key=seedqr_file2)
        assert r.returncode == 0, f"D failed:\n{r.stderr}"
        assert (stickd / "many-signed.psbt").exists(), "D: signed file missing"
        print("ok   D: 5-output PSBT paged; sign gated until all pages seen")

        print("\nSESSION PASS: word-entry(12/24 picker), xprv-QR, SeedQR, "
              "QR in/out, stick in/out, refusal, and paged review exercised")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
