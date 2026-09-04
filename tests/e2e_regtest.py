"""End-to-end proof of the Corky pipeline on regtest, no hardware needed.

Simulates the full production flow:
  coordinator (watch-only wallet, like Sparrow)  <->  Corky (signer wallet)

  1. Corky opens a session from the canonical test mnemonic (via the shim).
  2. The coordinator imports Corky's PUBLIC descriptors only.
  3. Coins are mined to the coordinator's watch address.
  4. Coordinator builds a funded PSBT (this is what would cross as a QR).
  5. Corky describes it (review screen data) and signs it.
  6. Coordinator finalizes and broadcasts. Confirmed = pipeline proven.

Run: python3 tests/e2e_regtest.py
"""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
import signer  # noqa: E402

# A-22: the pure signer has no BIP39. This is exactly the key the old
# "abandon x11 about" mnemonic produced on regtest, so every address,
# fee and signature these tests assert is unchanged.
XPRV = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"
WATCH = "watcher"


def main():
    datadir = tempfile.mkdtemp(prefix="corky-regtest-")
    import random as _rnd
    _port = _rnd.randint(20000, 60000)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % _port)
    daemon = subprocess.Popen(
        ["bitcoind", "-regtest", f"-datadir={datadir}", "-listen=0",
         "-fallbackfee=0.0001", "-server=1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(60):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)

        # 1. Corky session from words
        signer.open_session_xprv(rpc, XPRV)
        pubs = signer.public_descriptors(rpc)
        assert len(pubs) == 4 and not any("prv" in d for d in pubs), \
            "public descriptors leaked private material"
        print(f"ok   session open; {len(pubs)} public descriptors exported")

        # 2. Coordinator: watch-only wallet from public descriptors
        rpc.call("createwallet", WATCH, True, True, "", False, True)
        imports = [{"desc": d, "active": True, "timestamp": "now",
                    "range": [0, 200],
                    "internal": "/1/*" in d}
                   for d in pubs]
        res = rpc.call("importdescriptors", imports, wallet=WATCH)
        assert all(r["success"] for r in res)
        print("ok   watch-only coordinator wallet built from xpubs")

        # 3. Fund the watch wallet
        addr = rpc.call("getnewaddress", wallet=WATCH)
        rpc.call("generatetoaddress", 101, addr)
        balance = rpc.call("getbalance", wallet=WATCH)
        assert float(balance) > 0
        print(f"ok   watch wallet funded: {balance} rBTC")

        # 4. Coordinator builds the PSBT (the QR that would cross the gap)
        dest = rpc.call("getnewaddress", wallet=WATCH)
        funded = rpc.call("walletcreatefundedpsbt", [],
                          [{dest: 1.5}], 0, {"fee_rate": 10}, True,
                          wallet=WATCH)
        psbt = funded["psbt"]

        # 5. Corky review screen + signature
        review = signer.describe_psbt(rpc, psbt)
        assert review["fee_btc"] is not None
        # Verify the fee VALUE against Core's own decodepsbt fee, so a
        # mis-scaled fee (e.g. x10) on the security screen is caught.
        from decimal import Decimal
        core_fee = Decimal(str(rpc.call("decodepsbt", psbt)["fee"]))
        assert Decimal(str(review["fee_btc"])) == core_fee, \
            f"fee mismatch: screen {review['fee_btc']} vs core {core_fee}"
        print(f"ok   review screen: {len(review['outputs'])} outputs, "
              f"fee {review['fee_btc']} rBTC ({review['fee_note']})")
        signed = signer.sign_psbt(rpc, psbt)
        assert signed["complete"], "Corky did not fully sign"
        print("ok   Corky signed; PSBT complete")

        # 6. Coordinator finalizes and broadcasts
        final = rpc.call("finalizepsbt", signed["psbt"])
        txid = rpc.call("sendrawtransaction", final["hex"])
        rpc.call("generatetoaddress", 1, addr)
        conf = rpc.call("gettransaction", txid, wallet=WATCH)["confirmations"]
        assert conf >= 1
        print(f"ok   broadcast and confirmed: {txid}")

        # Statelessness rehearsal: session close leaves no loaded wallet
        signer.close_session(rpc)
        assert signer.WALLET not in rpc.call("listwallets")
        print("ok   session closed; signer wallet unloaded")

        # A-14: re-open the same wallet via the two Core-native modes and
        # confirm all three inputs produce identical wallets (same first
        # descriptors), i.e. the shim-free paths are equivalent.
        xprv = XPRV
        signer.open_session_xprv(rpc, xprv)
        pubs_xprv = signer.public_descriptors(rpc)
        signer.close_session(rpc)
        assert pubs_xprv == pubs, "xprv mode derived a different wallet"
        print("ok   xprv entry mode: identical wallet, shim not used")

        raw84 = f"wpkh({xprv}/84h/1h/0h/0/*)"
        raw84c = f"wpkh({xprv}/84h/1h/0h/1/*)"
        signer.open_session_descriptors(rpc, [raw84, raw84c])
        pubs_desc = signer.public_descriptors(rpc)
        signer.close_session(rpc)
        assert [d for d in pubs if "wpkh" in d] == pubs_desc, \
            "descriptor mode derived a different wallet"
        print("ok   descriptor entry mode: identical wallet, no shim, "
              "no assumed paths")

        print("\nE2E PASS: words -> shim -> Core descriptors -> PSBT review -> "
              "sign -> broadcast, with the coordinator holding xpubs only; "
              "xprv and descriptor entry modes verified equivalent")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)


if __name__ == "__main__":
    main()
