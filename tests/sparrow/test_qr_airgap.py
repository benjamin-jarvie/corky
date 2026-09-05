"""The air gap itself: Sparrow's QR out, Corky's QR back.

test_sparrow_interop.py passes base64 PSBTs between the two, which skips the
channel. This one drives the real one:

  Sparrow UREncoder    upper-cased ur:crypto-psbt parts, exactly as
                       QRDisplayDialog animates them
  Corky PsbtScan       reassembles under the real scan rules, Corky signs
  Corky frames_to_images  real PNG QR codes at the SeedSigner+ hat's panel size
  Sparrow zxing        reads those PNGs
  Sparrow URDecoder    reassembles
  Sparrow drongo PSBT  parses and counts signatures
  Bitcoin Core         finalizes and broadcasts

The scan direction stops at the string. Corky's camera is the M1 deliverable
and CameraQrSource yields nothing until it lands, so there is no capture path
on the device to test. Everything the device does with a frame once it has one
is covered here and in tests/m1.
"""
import sys
import tempfile
from pathlib import Path

import harness
from harness import Java, Regtest, Results

sys.path.insert(0, str(harness.REPO / "hw" / "vendor"))
import qrchannel  # noqa: E402

PANEL = (320, 240)   # SeedSigner+ hat, the primary control surface (PLAN A-15c)


def main():
    java = Java()
    R = Results()
    tmp = Path(tempfile.mkdtemp(prefix="corky-qr-png-"))

    with Regtest() as net:
        for script_type, _ in harness.SCRIPT_TYPES:
            fp, path, xpub = net.account(script_type)
            print(f"\n=== {script_type} ===")

            # a 6-input PSBT, big enough that Sparrow must fragment it
            addrs = [line.split("\t")[1] for line in
                     java("SparrowGen", "addresses", "REGTEST", script_type,
                          xpub, fp, path, 6, "RECEIVE")]
            utxos = [(i, *net.fund(a)) for i, a in enumerate(addrs)]
            net.mine()
            java.chain_height = net.height()
            dest = net.new_address()
            psbt = java("SparrowGen", "psbt", "REGTEST", script_type, xpub, fp,
                        path, 2.0, f"p={dest},5000000,false",
                        *[f"u=RECEIVE,{i},{t},{v},1000000,{java.chain_height},{r}"
                          for i, t, v, r in utxos])[0]
            print(f"     Sparrow PSBT: {len(psbt)} base64 chars, 6 inputs")

            # 1 + 2. Sparrow animates it; Corky's scan rules read it back
            for density, maxfrag in (("NORMAL", 400), ("LOW", 80)):
                parts = java("SparrowQr", "urencode", psbt, maxfrag)
                R.record(f"{script_type} Sparrow emits {len(parts)} UR parts "
                         f"at density {density}", len(parts) >= 1,
                         f"max {max(len(p) for p in parts)} chars, "
                         f"upper-cased={all(p == p.upper() for p in parts)}")
                scan = qrchannel.PsbtScan()
                for p in parts:
                    if scan.feed(p):
                        break
                R.record(f"{script_type} Corky reads Sparrow's {density} frames",
                         scan.psbt_b64 == psbt,
                         "byte-identical PSBT" if scan.psbt_b64 == psbt
                         else "assembled but differs" if scan.psbt_b64
                         else "never completed")

            # 3. Corky signs what came off the wire
            scan = qrchannel.PsbtScan()
            for p in java("SparrowQr", "urencode", psbt, 400):
                if scan.feed(p):
                    break
            signed = harness.signer.sign_psbt(net.rpc, scan.psbt_b64)
            R.record(f"{script_type} Corky signs the QR-delivered PSBT",
                     signed["complete"])

            # 4. Corky renders its answer as real QR images
            frames = qrchannel.psbt_to_frames(signed["psbt"])
            images = qrchannel.frames_to_images(frames, panel=PANEL)
            paths = []
            for n, img in enumerate(images):
                q = tmp / f"{script_type}_{n:03d}.png"
                qrchannel.fit_to_panel(img, *PANEL).save(q)
                paths.append(str(q))
            R.record(f"{script_type} Corky renders {len(frames)} frames onto a "
                     f"{PANEL[0]}x{PANEL[1]} panel", len(paths) == len(frames),
                     f"{images[0].size[0]}px QR, letterboxed")

            # 5. Sparrow's scanner reads those images.
            #
            # Not every frame will decode. Corky renders at exactly 4.0 pixels
            # per module and about 1 in 125 frames is deterministically
            # unreadable by zxing, which is Sparrow's decoder (ticket 09,
            # measured by tests/m1/outbound_margin.py). pyzbar reads the same
            # images, so this is a zxing limit, not a rendering fault.
            #
            # The promise is not that every frame is readable. It is that the
            # transfer completes anyway, because psbt_to_frames now emits
            # fountain parts past the pure cycle. So assert what is promised:
            # whatever zxing got must be enough to rebuild the PSBT.
            texts, missed = [], []
            for n, path in enumerate(paths):
                try:
                    texts.append(java("SparrowQr", "qrdecode", path)[0])
                except RuntimeError:
                    missed.append(n)
            R.record(f"{script_type} Sparrow's zxing reads enough of Corky's "
                     f"{len(frames)} frames", len(texts) >= len(frames) // 2,
                     f"{len(texts)}/{len(frames)} decoded"
                     + (f", {len(missed)} unreadable, fountain parts cover it"
                        if missed else ""))

            # 6 + 7. Sparrow reassembles, parses, and Core broadcasts
            back = java("SparrowQr", "urdecode", *texts)[0]
            R.record(f"{script_type} Sparrow's URDecoder rebuilds the signed PSBT",
                     back == signed["psbt"],
                     "byte-identical" if back == signed["psbt"]
                     else "differs from what Corky signed")
            info = java("SparrowQr", "inspect", back)[0]
            R.record(f"{script_type} Sparrow's drongo parses it and sees the "
                     f"signatures", "signed=6" in info, info)

            final = net.rpc.call("finalizepsbt", back)
            txid = net.rpc.call("sendrawtransaction", final["hex"])
            net.mine()
            conf = net.rpc.call("getrawtransaction", txid, True)["confirmations"]
            R.record(f"{script_type} round-tripped transaction confirms",
                     conf >= 1, f"tx {txid[:12]}")

    return R.summary()


if __name__ == "__main__":
    sys.exit(main())
