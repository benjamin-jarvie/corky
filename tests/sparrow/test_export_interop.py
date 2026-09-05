"""Corky's exported public key, read by Sparrow's own library.

TESTING.md rule 8: an interop claim tested with your own tools is not an
interop claim. Corky's own decoder reads Corky's own QR by construction.
This suite renders the export exactly as the panel shows it, decodes it
with the zxing reader Sparrow uses, hands the decoded string to Sparrow's
OutputDescriptor, and compares the addresses with Core's.

Run: ./setup.sh once, then python3 test_export_interop.py
"""
import sys
import tempfile
from pathlib import Path

import harness
from harness import Java, Regtest, Results

sys.path.insert(0, str(harness.REPO / "corky"))
import qrchannel
import screens  # noqa: E402
import signer  # noqa: E402

PANELS = [("primary 320x240", (320, 240)), ("pocket 240x240", (240, 240))]


def main():
    java = Java()
    r = Results()
    work = Path(tempfile.mkdtemp(prefix="corky-export-interop-"))
    with Regtest(mine=1) as net:
        # Every policy this key HAS, not every policy Core can make. The
        # harness key arrives by import, and an imported key gets BIP84
        # and BIP86 only, while a key Core generates gets all four. That
        # asymmetry is map ticket D1; what this suite proves is that
        # whatever the key presents, Sparrow reads it.
        kinds = signer.available_kinds(net.rpc, net.wallet)
        r.record("the harness key presents the policies it was built with",
                 kinds == ("wpkh", "tr"), str(kinds))
        for kind in kinds:
            desc = signer.export_descriptor(net.rpc, net.wallet, kind)
            core_addrs = signer.receive_addresses(net.rpc, net.wallet, kind, 5)

            for panel_name, panel in PANELS:
                img = qrchannel.text_to_image(desc, panel=panel)
                r.record(f"{kind} QR fits the {panel_name} panel",
                         img.width <= panel[0] and img.height <= panel[1],
                         f"{img.width}x{img.height}")
                png = work / f"{kind}-{panel[0]}.png"
                # Caption the code the way the device does. The caption
                # sits in the letterbox, outside the quiet zone, and this
                # is the assertion that it stays there: nested segwit is
                # 61 modules against the others' 57, so its caption turns
                # sideways into the margin, and a caption that crept over
                # the code would show up here as a refusal.
                factor = min(panel[0] // img.width, panel[1] // img.height)
                screens.caption_qr(qrchannel.fit_to_panel(img, *panel),
                                   img.height * factor,
                                   screens.SCRIPT_LABELS[kind].upper()
                                   ).save(png)
                decoded = java("SparrowQr", "qrdecode", str(png))[0]
                r.record(f"{kind}: Sparrow's zxing reads the captioned "
                         f"{panel_name} QR",
                         decoded == desc,
                         "byte-identical" if decoded == desc
                         else f"got {decoded[:60]!r}")

            # Sparrow's own library must accept the string Core wrote.
            out = java("SparrowDesc", "REGTEST", desc, 5, tags=("INFO", "OUT"))
            info = "\n".join(out["INFO"])
            sparrow_addrs = [line.split("\t")[1] for line in out["OUT"]]
            r.record(f"{kind}: Sparrow parses Core's descriptor verbatim",
                     "policy=Single Signature HD" in info,
                     info.replace("\n", " | "))
            xfp = signer.master_fingerprint(net.rpc, wallet=net.wallet)
            r.record(f"{kind}: Sparrow reads the same fingerprint",
                     f"fp={xfp}" in info, xfp)
            r.record(f"{kind}: Sparrow derives Core's first five addresses",
                     sparrow_addrs == core_addrs,
                     f"{core_addrs[0][:18]}… x5" if sparrow_addrs == core_addrs
                     else f"{sparrow_addrs[:1]} != {core_addrs[:1]}")

        # The KEY scan, with real key material and a real decoder.
        # TESTING.md rule 1 wants real domain data through the surface, and
        # rule 8 wants the counterpart's decoder. test_keyscan.py drives the
        # stopping rules with stand-ins; this drives the bytes.
        sys.path.insert(0, str(harness.REPO / "corky"))
        import main as corky_main  # noqa: E402
        priv = [d["desc"] for d in
                net.rpc.call("listdescriptors", True,
                             wallet=net.wallet)["descriptors"]
                if d["desc"].startswith("wpkh(") and not d["internal"]][0]
        xprv = signer.master_xprv(net.rpc, wallet=net.wallet)
        session = corky_main.Session.__new__(corky_main.Session)

        for name, payload, want_kind in (("private descriptor", priv, "descriptor"),
                                         ("master xprv", xprv, "xprv")):
            png = work / f"key-{want_kind}.png"
            qrchannel.text_to_image(payload, panel=(320, 240)).save(png)
            decoded = java("SparrowQr", "qrdecode", str(png))[0]
            r.record(f"a real {name} survives render and zxing decode",
                     decoded == payload,
                     "byte-identical" if decoded == payload
                     else f"got {decoded[:40]!r}")
            r.record(f"the scan classifies a real {name} as {want_kind}",
                     corky_main._classify_qr(decoded) == want_kind,
                     corky_main._classify_qr(decoded))
            guarded = corky_main.Session._guard_key_payload(session, decoded)
            r.record(f"the A-11 guards pass a real {name} through unchanged",
                     guarded == payload, "unchanged")

        # And the guarded xprv really opens the key it came from: same
        # fingerprint, same addresses, from a wallet built out of the
        # string that came back through the camera path.
        before_xfp = signer.master_fingerprint(net.rpc, wallet=net.wallet)
        before_addrs = signer.receive_addresses(net.rpc, net.wallet, "wpkh", 3)
        signer.close_session(net.rpc)
        slot = signer.open_session_xprv(net.rpc, xprv)
        after_xfp = signer.master_fingerprint(net.rpc, wallet=slot)
        after_addrs = signer.receive_addresses(net.rpc, slot, "wpkh", 3)
        r.record("a scanned xprv opens the key it came from",
                 after_xfp == before_xfp and after_addrs == before_addrs,
                 f"{after_xfp}, {after_addrs[0][:16]}…")

        # The export must never carry a private key, whatever the panel.
        for kind in signer.available_kinds(net.rpc, slot):
            desc = signer.export_descriptor(net.rpc, slot, kind)
            r.record(f"{kind}: the exported string holds no private key",
                     "prv" not in desc, desc[:28] + "…")

        # A key CORE generated carries all four policies, and Sparrow's
        # zxing has to read every one of them captioned, because that is
        # what Ben puts in front of a coordinator. Nested segwit is the
        # awkward one: 61 modules against the others' 57, so its caption
        # turns sideways into the margin instead of sitting under the
        # code, and a caption drawn over the code fails here.
        signer.close_session(net.rpc)
        made = signer.generate_wallet(net.rpc)
        four = signer.available_kinds(net.rpc, made)
        r.record("a key Core generated carries all four policies",
                 four == ("wpkh", "tr", "sh", "pkh"), str(four))
        for kind in four:
            desc = signer.export_descriptor(net.rpc, made, kind)
            core_addrs = signer.receive_addresses(net.rpc, made, kind, 3)
            for panel_name, panel in PANELS:
                img = qrchannel.text_to_image(desc, panel=panel)
                factor = min(panel[0] // img.width, panel[1] // img.height)
                png = work / f"gen-{kind}-{panel[0]}.png"
                screens.caption_qr(qrchannel.fit_to_panel(img, *panel),
                                   img.height * factor,
                                   screens.SCRIPT_LABELS[kind].upper()
                                   ).save(png)
                decoded = java("SparrowQr", "qrdecode", str(png))[0]
                r.record(f"{kind}: zxing reads the captioned {panel_name} QR "
                         "of a Core-generated key",
                         decoded == desc,
                         "byte-identical" if decoded == desc
                         else f"got {decoded[:40]!r}")
            out = java("SparrowDesc", "REGTEST", desc, 3, tags=("INFO", "OUT"))
            sparrow_addrs = [line.split("\t")[1] for line in out["OUT"]]
            r.record(f"{kind}: Sparrow derives Core's first three addresses",
                     sparrow_addrs == core_addrs,
                     f"{core_addrs[0][:18]}… x3" if sparrow_addrs == core_addrs
                     else f"{sparrow_addrs[:1]} != {core_addrs[:1]}")
        signer.close_session(net.rpc)

    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
