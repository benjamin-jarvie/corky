"""E2E for the file channel: a temp directory stands in for the USB stick.

Coordinator (watch-only) writes tx.psbt in BOTH formats Sparrow can emit
(binary and base64 text); Corky reads each opaquely, signs, writes
tx-signed.psbt; coordinator finalizes and broadcasts both.

Run: python3 tests/e2e_filechannel.py
"""

import base64
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
import signer  # noqa: E402
import filechannel  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"


def main():
    datadir = tempfile.mkdtemp(prefix="corky-fc-")
    import random as _rnd
    _port = _rnd.randint(20000, 60000)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % _port)
    stick = Path(tempfile.mkdtemp(prefix="corky-stick-"))
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

        signer.open_session(rpc, MNEMONIC)
        rpc.call("createwallet", "watch", True, True, "", False, True)
        imports = [{"desc": d, "active": True, "timestamp": "now",
                    "range": [0, 200], "internal": "/1/*" in d}
                   for d in signer.public_descriptors(rpc)]
        assert all(r["success"] for r in
                   rpc.call("importdescriptors", imports, wallet="watch"))
        addr = rpc.call("getnewaddress", wallet="watch")
        rpc.call("generatetoaddress", 101, addr)

        for fmt in ("binary", "base64"):
            dest = rpc.call("getnewaddress", wallet="watch")
            funded = rpc.call("walletcreatefundedpsbt", [], [{dest: 1.0}],
                              0, {"fee_rate": 10}, True, wallet="watch")
            name = f"tx-{fmt}.psbt"
            if fmt == "binary":
                (stick / name).write_bytes(base64.b64decode(funded["psbt"]))
            else:
                (stick / name).write_text(funded["psbt"])

            found = filechannel.find_unsigned(stick)
            target = [p for p in found if p.name == name][0]
            psbt = filechannel.read_psbt(target)
            review = signer.describe_psbt(rpc, psbt)
            assert review["fee_btc"] is not None
            signed = signer.sign_psbt(rpc, psbt)
            assert signed["complete"]
            out = filechannel.write_signed(target, signed["psbt"])
            assert out.name == f"tx-{fmt}-signed.psbt"

            # signed file must not reappear as work
            assert out not in filechannel.find_unsigned(stick)

            # coordinator picks the signed file up and broadcasts
            reread = filechannel.read_psbt(out)
            final = rpc.call("finalizepsbt", reread)
            txid = rpc.call("sendrawtransaction", final["hex"])
            rpc.call("generatetoaddress", 1, addr)
            assert rpc.call("gettransaction", txid,
                            wallet="watch")["confirmations"] >= 1
            print(f"ok   {fmt} PSBT file: read -> review -> sign -> "
                  f"write -> broadcast ({txid[:16]}...)")

        # size-cap sanity
        big = stick / "huge.psbt"
        big.write_bytes(b"\x00" * (filechannel.MAX_PSBT_BYTES + 1))
        try:
            filechannel.read_psbt(big)
            print("FAIL size cap not enforced")
            sys.exit(1)
        except filechannel.FileChannelError:
            print("ok   oversized file refused")

        print("\nFILE CHANNEL PASS: both Sparrow file formats, opaque, "
              "signed and broadcast")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)
        shutil.rmtree(stick, ignore_errors=True)


if __name__ == "__main__":
    main()
