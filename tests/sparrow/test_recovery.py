"""RECOVERY. Corky is gone; can the paper backup still spend the money?

Every other suite proves the export lands: a coordinator gets Corky's
PUBLIC descriptor and watches the right addresses. That is the happy path.
This one is the unhappy path, and it is the one the paper backup exists
for: the device is lost, broken, or in a river, and all that survives is
111 characters written by hand.

Nothing here uses Corky to recover. Sparrow Wallet's own library, out of
the sha256-verified 2.5.4 release, rebuilds a spending wallet from the
bare master private key through `Keystore.fromMasterPrivateExtendedKey`,
which is the call Sparrow's own "master private key" import drives. Then
Bitcoin Core funds it, Sparrow signs, and Core is asked whether the
signature is good enough to broadcast.

TESTING.md rule 8: where a counterpart is named, run the counterpart.

Run: python3 tests/sparrow/test_recovery.py
"""
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "tests" / "sparrow"))
import signer                                   # noqa: E402
from harness import Java, Regtest, Results      # noqa: E402

#: Corky's four policies, and what Sparrow calls each of them.
POLICIES = (("wpkh", "P2WPKH"), ("tr", "P2TR"),
            ("sh", "P2SH_P2WPKH"), ("pkh", "P2PKH"))


def main():
    java = Java()
    r = Results()
    with Regtest(mine=200) as net:
        # A key Bitcoin Core generated on this device, and the paper backup
        # of it: the same string the panel shows you to write down.
        made = signer.generate_wallet(net.rpc)
        paper = signer.master_xprv(net.rpc, wallet=made)
        r.record("the paper backup is Core's 111-character master key",
                 len(paper) == 111 and paper.startswith("tprv"),
                 f"{len(paper)} chars")

        for kind, script in POLICIES:
            core_addrs = signer.receive_addresses(net.rpc, made, kind, 3)

            # 1. Sparrow rebuilds the wallet from the paper alone.
            out = java("SparrowRecover", "REGTEST", script, paper,
                       "addresses", 3, tags=("INFO", "OUT"))
            got = [line.split("\t")[1] for line in out["OUT"]]
            r.record(f"{kind}: Sparrow rebuilds the wallet from the paper "
                     "backup and derives Core's addresses",
                     got == core_addrs,
                     f"{core_addrs[0][:20]}… x3" if got == core_addrs
                     else f"{got[:1]} != {core_addrs[:1]}")

            xfp = signer.master_fingerprint(net.rpc, wallet=made)
            r.record(f"{kind}: the recovered wallet is the same key",
                     f"fp={xfp}" in out["INFO"][0], out["INFO"][0])

            if got != core_addrs:
                continue

            # 2. Fund it, then spend THAT COIN with the recovered wallet.
            #
            # The input has to be named. The wallet accumulates a UTXO per
            # policy as this loop runs, and left to choose, Core spends
            # whichever it likes: the taproot round was handed a native
            # segwit coin from the round before, the taproot-only wallet
            # could not sign it, and that read as "taproot recovery is
            # broken" when taproot was fine. add_inputs=False keeps Core
            # from quietly adding the others back.
            addr = core_addrs[0]
            txid, vout, _raw = net.fund(addr, "0.01")
            net.mine(1)
            dest = net.new_address()
            funded = net.rpc.call(
                "walletcreatefundedpsbt",
                [{"txid": txid, "vout": vout}],
                [{dest: Decimal("0.005")}],
                0, {"fee_rate": 5, "add_inputs": False}, wallet=made)
            psbt = funded["psbt"]

            signed = java("SparrowRecover", "REGTEST", script, paper,
                          "sign", psbt, tags=("INFO", "OUT"))["OUT"][0]
            r.record(f"{kind}: the recovered wallet signed a real spend",
                     signed != psbt and len(signed) > 40,
                     f"{len(signed)} chars back")

            # 3. Core is the judge. A signature Corky's own node will not
            #    finalise is not a recovery, whatever Sparrow reports.
            final = net.rpc.call("finalizepsbt", signed)
            r.record(f"{kind}: Bitcoin Core finalises Sparrow's signature",
                     final.get("complete") is True, str(final.get("complete")))
            if not final.get("complete"):
                continue

            accept = net.rpc.call("testmempoolaccept", [final["hex"]])
            r.record(f"{kind}: the network would accept the recovered spend",
                     accept[0].get("allowed") is True,
                     accept[0].get("reject-reason", "allowed"))

        signer.close_key(net.rpc, made)

    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
