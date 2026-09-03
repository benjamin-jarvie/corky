"""How much margin Corky's own QR output has, measured.

legibility_rig.py asks whether Corky can read Sparrow. This asks the other
direction: whether a coordinator can read Corky. It found a real number, so it
lives here rather than in a scratch file.

Corky renders at MAX_FRAGMENT_LEN = 100, which produces 244-character UR frames,
which is a 49x49 QR. Add the 2-module quiet zone each side and that is 53
modules across. The 320x240 panel allows box_size = 240 // 53 = 4, so Corky
renders at exactly **4.0 pixels per module** and cannot go higher without
fewer modules.

4.0 is the line legibility_rig found for the inbound direction, and sitting on
a line is not the same as clearing it.

Run: tests/m1/run tests/m1/outbound_margin.py [trials]
"""
import base64
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import qrcode

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "corky"))
sys.path.insert(0, str(REPO / "hw" / "vendor"))
import qrchannel  # noqa: E402

SPARROW_BUILD = REPO / "tests/sparrow/.build"
JAVA = SPARROW_BUILD / "jdk-25.0.4.1+1/Contents/Home/bin/java"
PANEL = (320, 240)
SIGNED_P2TR_BYTES = 1430      # a 6-input signed taproot PSBT, measured


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    if not JAVA.exists():
        sys.exit("needs tests/sparrow/.build; run tests/sparrow/setup.sh")
    classpath = ((SPARROW_BUILD / "cp.txt").read_text().strip()
                 + ":" + str(SPARROW_BUILD / "out"))
    tmp = Path(tempfile.mkdtemp(prefix="outbound-"))
    rng = random.Random(7)          # fixed, so the number is reproducible

    total = misses = 0
    geometry = set()
    for trial in range(trials):
        psbt = base64.b64encode(
            bytes(rng.randrange(256) for _ in range(SIGNED_P2TR_BYTES))).decode()
        frames = qrchannel.psbt_to_frames(psbt)
        images = qrchannel.frames_to_images(frames, panel=PANEL)
        for i, img in enumerate(images):
            path = tmp / f"{trial}_{i}.png"
            qrchannel.fit_to_panel(img, *PANEL).save(path)
            total += 1
            qr = qrcode.QRCode(border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_L)
            qr.add_data(frames[i].upper())
            qr.make(fit=True)
            span = qr.modules_count + 2 * qr.border
            geometry.add((qr.modules_count, img.size[0], round(img.size[0] / span, 2)))
            r = subprocess.run([str(JAVA), "-cp", classpath, "SparrowQr",
                                "qrdecode", str(path)],
                               capture_output=True, text=True)
            if r.returncode:
                misses += 1

    print(f"trials      : {trials} PSBTs, {total} frames")
    for modules, px, per in sorted(geometry):
        print(f"geometry    : {modules}x{modules} modules, {px}px image, "
              f"{per} px per module")
    print(f"single pass : {total - misses}/{total} decoded "
          f"({misses} missed, {misses / total:.1%})")
    print()
    print("A miss is not a product failure. The display loops, so a coordinator")
    print("sees the same frame again on the next cycle. It IS the margin, and")
    print("the margin is thin: raising it means lowering MAX_FRAGMENT_LEN,")
    print("which means more frames and a slower transfer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
