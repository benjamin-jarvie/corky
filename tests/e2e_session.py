"""Full-device dress rehearsal on the dev HAL: boots bitcoind, runs main.py's
state machine end to end with a scripted keypad, PSBT via the file channel.
Run: python3 tests/e2e_session.py"""

import base64
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"


def main():
    datadir = tempfile.mkdtemp(prefix="corky-sess-")
    stick = Path(tempfile.mkdtemp(prefix="corky-sess-stick-"))
    frames = Path(tempfile.mkdtemp(prefix="corky-sess-frames-"))
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

        # Coordinator side: watch wallet funded, writes a PSBT to the stick
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
        dest = rpc.call("getnewaddress", wallet="watch")
        funded = rpc.call("walletcreatefundedpsbt", [], [{dest: 2.0}],
                          0, {"fee_rate": 10}, True, wallet="watch")
        (stick / "hui.psbt").write_bytes(base64.b64decode(funded["psbt"]))

        # The device: home -> select (a) -> auto seed -> stick found ->
        # review -> sign (a)
        run = subprocess.run(
            [sys.executable, str(ROOT / "corky" / "main.py"), "--dev",
             f"--datadir={datadir}", "--chain=regtest", "--script=aa",
             f"--stick-dir={stick}", f"--frames-dir={frames}"],
            capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, f"main.py failed:\n{run.stderr}"

        signed_file = stick / "hui-signed.psbt"
        assert signed_file.exists(), "signed PSBT not written to stick"
        final = rpc.call("finalizepsbt",
                         base64.b64encode(signed_file.read_bytes()).decode())
        txid = rpc.call("sendrawtransaction", final["hex"])
        rpc.call("generatetoaddress", 1, addr)
        assert rpc.call("gettransaction", txid, wallet="watch")["confirmations"] >= 1
        shots = sorted(frames.glob("frame-*.png"))
        assert len(shots) >= 4, "expected home/busy/review/result frames"
        print(f"ok   session ran: {len(shots)} screen frames captured")
        print(f"ok   signed PSBT from stick broadcast and confirmed: {txid[:16]}…")
        print("\nSESSION PASS: scripted keypad drove the real state machine "
              "through seed -> load -> review -> sign -> broadcast")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        for d in (datadir, stick, frames):
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
