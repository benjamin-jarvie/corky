"""COSIGNER. Does Sparrow take a Core Signer key as one member of a quorum?

Map multisig-cosigner, ticket M4. Every other Sparrow suite here proves
Core Signer's SINGLE-SIG export lands. This one proves the thing the map exists
for: a key Bitcoin Core generated, sitting in a multivendor quorum beside
keys that are not ours, signed for on this side of an air gap.

TESTING.md rule 8: an interop claim tested with your own tools is not an
interop claim. Sparrow's own drongo, out of the sha256-verified 2.5.4
release, parses the record Core Signer exports and derives the addresses. Core
derives them too, independently, and the two must agree.

Run: python3 tests/sparrow/test_cosigner.py
"""
import sys
from pathlib import Path

import harness
from harness import Java, Regtest, Results

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "coresigner"))
import signer  # noqa: E402

# Ordinary BIP48 for P2WSH, and a BLINDED path: 3 hardened levels of the
# shape buidl's secure_secret_path builds for Flaxman's protocol. Most
# hardware wallets refuse to sign on one; map M1 established Core does
# not, and this is where that stops being a claim.
PATHS = {
    "BIP48 P2WSH": "48h/1h/0h/2h",
    "blinded": "607137099h/1711870460h/1965312408h",
}


def main():
    java = Java()
    r = Results()
    with Regtest() as net:   # the default 250 blocks, so the miner can fund
        for label, path in PATHS.items():
            ours = signer.cosigner_key(net.rpc, net.wallet, path)

            # M7: Coldcard's key_expr.txt shape, which Sparrow and Nunchuk
            # both parse. Anything else is a format we invented.
            r.record(f"{label}: the record is a bare key expression",
                     ours.startswith("[") and "]" in ours
                     and not ours.endswith("/0/*")
                     and "wpkh(" not in ours,
                     ours[:46] + "…")
            xfp = ours[1:ours.index("/")]
            r.record(f"{label}: it carries an 8-hex origin and this path",
                     len(xfp) == 8 and path in ours,
                     f"[{xfp}/{path}]")

            # Two cosigners that are NOT ours, so the quorum is genuinely
            # multivendor rather than three keys off one seed. Core makes
            # them, we take the cosigner record, and the wallet goes: what
            # is left is somebody else's xpub, which is all a coordinator
            # ever has of a co-signer.
            others, other_xprvs = [], []
            for _ in range(2):
                w = signer.generate_wallet(net.rpc)
                others.append(signer.cosigner_key(net.rpc, w,
                                                  "48h/1h/0h/2h"))
                # Kept, because Sparrow signs with one of them below as
                # the other vendor in the quorum.
                other_xprvs.append(signer.master_xprv(net.rpc, w))
                signer._drop_wallet(net.rpc, w)
            # THE COORDINATOR APPENDS THE BRANCH. A cosigner record is a
            # key at the account level with no `/0/*` on it, which is
            # what Coldcard writes and what M7 chose. Assembling a quorum
            # from bare records gives an UN-RANGED descriptor, and Core
            # refuses a range on one: "Range should not be specified for
            # an un-ranged descriptor". So whoever builds the wallet adds
            # the receive branch, and this line is standing in for them.
            members = [f"{k}/0/*" for k in [ours] + others]
            desc = f"wsh(sortedmulti(2,{','.join(members)}))"
            info = net.rpc.call("getdescriptorinfo", desc, stdin=True)
            full = f"{desc}#{info['checksum']}"

            # Core's addresses, derived from the quorum it was handed.
            core_addrs = net.rpc.call("deriveaddresses", full, [0, 2])

            # Sparrow's, from the same string, through its own parser.
            out = java("SparrowDesc", "REGTEST", full, 3,
                       tags=("INFO", "OUT"))
            spar_addrs = [ln.split("\t")[1] for ln in out["OUT"]]
            r.record(f"{label}: Sparrow parses the quorum and agrees with "
                     "Core on the addresses",
                     spar_addrs == core_addrs,
                     f"{core_addrs[0][:22]}… x3" if spar_addrs == core_addrs
                     else f"sparrow {spar_addrs[:1]} != core {core_addrs[:1]}")
            seen = [ln for ln in out["INFO"] if ln.startswith("fp=")]
            r.record(f"{label}: Sparrow sees all three cosigners",
                     len(seen) == 3, f"{len(seen)} keystores")
            r.record(f"{label}: and ours is one of them, at the path we "
                     "asked for",
                     any(xfp in ln and path.replace("h", "'") in ln
                         for ln in seen),
                     next((ln for ln in seen if xfp in ln), "not found"))

            # --- and now the half the map exists for --------------------
            #
            # A coordinator that holds no private key at all builds the
            # transaction; Core Signer signs its share; Sparrow, holding a
            # DIFFERENT key of the same quorum, adds the second; and Core
            # is asked whether the network would take the result. Nothing
            # in this stretch is our own arithmetic: Core builds, Core
            # judges, and Sparrow's own drongo does the second signature.
            coord = f"coord{abs(hash(path)) % 9999}"
            net.rpc.call("createwallet", coord, True, True, "", False, True)
            for change in (0, 1):
                branch = [f"{k}/{change}/*" for k in [ours] + others]
                d = f"wsh(sortedmulti(2,{','.join(branch)}))"
                ck = net.rpc.call("getdescriptorinfo", d,
                                  stdin=True)["checksum"]
                net.rpc.call("importdescriptors",
                             [{"desc": f"{d}#{ck}", "active": True,
                               "internal": bool(change), "timestamp": "now",
                               "range": [0, 20]}], wallet=coord, stdin=True)
            addr = net.rpc.call("getnewaddress", wallet=coord)
            net.rpc.call("sendtoaddress", addr, 1.0, wallet=harness.MINER)
            net.mine(1)
            psbt = net.rpc.call("walletcreatefundedpsbt", [],
                                [{net.miner_addr: 0.5}], 0, {"fee_rate": 2},
                                wallet=coord)["psbt"]

            # THE SESSION WALLET, with no branch imported by hand. This
            # used to build a scratch wallet at `path` first, standing in
            # for M3's decision that the device reads the path out of the
            # PSBT. Map M9 built it, so the stand-in is gone and this is
            # now the flow the device runs.
            ours_signed = signer.sign_psbt(
                net.rpc, psbt, wallet=net.wallet,
                xfp=signer.master_fingerprint(net.rpc, net.wallet))

            # COUNT THE SIGNATURE, do not just check `complete`. The first
            # version of this asserted `complete is False`, which is also
            # true when Core Signer signs NOTHING, and it passed for exactly
            # that reason: net.wallet holds the four standard policies and
            # has no key at a BIP48 path at all. A check that cannot tell
            # "signed one of two" from "signed nothing" is not a check.
            def sigs(p):
                return net.rpc.call("decodepsbt", p, stdin=True)["inputs"][0]\
                    .get("partial_signatures", {})
            n_ours = len(sigs(ours_signed["psbt"]))
            r.record(f"{label}: Core Signer signs its share, and only its share",
                     n_ours == 1 and ours_signed["complete"] is False,
                     f"{n_ours} signature, complete={ours_signed['complete']}")

            # CHAINED, which is the air-gapped flow this device is for.
            # Sparrow sends the PSBT over, Core Signer signs it, the signed
            # PSBT comes back by QR, and Sparrow signs the SAME object on
            # top. Sparrow must keep a partial signature it did not make.
            # Nothing here proved that before: the first version of this
            # test read "1 signature" and blamed Sparrow, when the real
            # cause was Core Signer signing nothing.
            res = java("SparrowCosigner", "REGTEST", full, other_xprvs[0],
                       ours_signed["psbt"], tags=("INFO", "OUT"))
            chained = res["OUT"][0]
            n_chain = len(sigs(chained))
            fin_chain = net.rpc.call("finalizepsbt", chained, stdin=True)
            r.record(f"{label}: Sparrow signs on top of Core Signer and keeps "
                     "our signature",
                     n_chain == 2 and bool(fin_chain.get("complete")),
                     f"{n_chain} signatures, "
                     f"complete={bool(fin_chain.get('complete'))}; "
                     + "; ".join(res["INFO"]))

            # COMBINED, which is what a coordinator does when the shares
            # travel in parallel. Both signers work from the ORIGINAL and
            # Core merges. It must reach the same transaction as chaining.
            par = java("SparrowCosigner", "REGTEST", full, other_xprvs[0],
                       psbt, tags=("INFO", "OUT"))
            both = net.rpc.call("combinepsbt",
                                [ours_signed["psbt"], par["OUT"][0]],
                                stdin=True)
            n_both = len(sigs(both))
            final = net.rpc.call("finalizepsbt", both, stdin=True)
            r.record(f"{label}: combinepsbt merges the two shares and "
                     "finalises",
                     n_both == 2 and bool(final.get("complete")),
                     f"{n_both} signatures, "
                     f"complete={bool(final.get('complete'))}")
            if final.get("complete") and fin_chain.get("complete"):
                r.record(f"{label}: both routes reach the same signed "
                         "transaction",
                         final["hex"] == fin_chain["hex"],
                         "identical hex" if final["hex"] == fin_chain["hex"]
                         else "ROUTES DISAGREE")
            if final.get("complete"):
                chk = net.rpc.call("testmempoolaccept", [final["hex"]],
                                   stdin=True)
                r.record(f"{label}: the network would accept the quorum's "
                         "spend",
                         bool(chk[0].get("allowed")),
                         chk[0].get("reject-reason", "allowed"))
    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
