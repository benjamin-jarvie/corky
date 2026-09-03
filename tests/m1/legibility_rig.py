"""Can Corky's camera read Sparrow's screen? Answered without a camera.

Corky's stream is ~512x384 at ~10fps into pyzbar (hw/HARDWARE.md:75). Sparrow
at its default NORMAL density emits UR frames up to 775 characters, which is a
large QR. This rig renders Sparrow's real frames, degrades them the way a cheap
camera does, and decodes with the same pyzbar 0.1.9 and zbar the device runs.

Frames in sparrow_frames.json come from Sparrow's own UREncoder, captured by
tests/sparrow. Both Sparrow and Corky render at error correction level L, so
the module count here is the module count on the real screen.

Run: tests/m1/run tests/m1/legibility_rig.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import qrcode
from PIL import Image, ImageFilter
from pyzbar import pyzbar

STREAM = (512, 384)          # hw/HARDWARE.md:75
FILL = (0.90, 0.75, 0.60, 0.50)   # how much of the frame height the QR occupies


def render(frame_text, pixels):
    """The QR as it appears on the coordinator's screen, at `pixels` square."""
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(frame_text.upper())      # Sparrow upper-cases: QRDisplayDialog:245
    qr.make(fit=True)
    span = qr.modules_count + 2 * qr.border
    img = qr.make_image(fill_color="black", back_color="white").convert("L")
    return img.resize((pixels, pixels), Image.NEAREST), qr.modules_count, span


def on_sensor(qr_img, fill):
    """Place the QR in a 512x384 frame, centred, on a grey-ish background."""
    h = int(STREAM[1] * fill)
    qr = qr_img.resize((h, h), Image.LANCZOS)
    canvas = Image.new("L", STREAM, 200)
    canvas.paste(qr, ((STREAM[0] - h) // 2, (STREAM[1] - h) // 2))
    return canvas


def tilt(img, degrees):
    """Perspective, as when the device is not square to the screen."""
    w, h = img.size
    d = int(w * degrees / 100.0)
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(d, 0), (w, 0), (w - d, h), (0, h)]
    # solve the 8-coefficient perspective transform
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    coeffs = np.linalg.solve(np.array(A, dtype=float), np.array(B, dtype=float))
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=200)


def noise(img, sigma):
    a = np.asarray(img, dtype=np.float32)
    a += np.random.default_rng(0).normal(0, sigma, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def contrast(img, factor):
    a = np.asarray(img, dtype=np.float32)
    return Image.fromarray(np.clip(128 + (a - 128) * factor, 0, 255).astype(np.uint8))


CONDITIONS = [
    ("clean",              lambda i: i),
    ("blur 0.8px",         lambda i: i.filter(ImageFilter.GaussianBlur(0.8))),
    ("blur 1.5px",         lambda i: i.filter(ImageFilter.GaussianBlur(1.5))),
    ("motion blur",        lambda i: i.filter(ImageFilter.BoxBlur((2, 0)))),
    ("tilt 15",            lambda i: tilt(i, 15)),
    ("tilt 15 + blur 1px", lambda i: tilt(i, 15).filter(ImageFilter.GaussianBlur(1.0))),
    ("noise s=12",         lambda i: noise(i, 12)),
    ("low contrast 0.45",  lambda i: contrast(i, 0.45)),
    ("dim + blur 1px",     lambda i: contrast(i, 0.55).filter(ImageFilter.GaussianBlur(1.0))),
]


def main():
    here = Path(__file__).resolve().parent
    fixtures = json.loads((here / "sparrow_frames.json").read_text())

    print(f"Corky stream {STREAM[0]}x{STREAM[1]}, pyzbar 0.1.9 over zbar, "
          f"error correction L\n")
    verdicts = {}

    for script_type, sets in sorted(fixtures.items()):
        for density in ("NORMAL", "LOW"):
            frames = sets[density]
            longest = max(frames, key=len)
            _, modules, span = render(longest, 100)
            print(f"=== {script_type} / Sparrow density {density} ===")
            print(f"    {len(frames)} frames, longest {len(longest)} chars, "
                  f"{modules}x{modules} modules ({span} with quiet zone)")

            header = "    fill   px/module  " + "  ".join(f"{n[:11]:>11}" for n, _ in CONDITIONS)
            print(header)
            for fill in FILL:
                qr_px = int(STREAM[1] * fill)
                per_module = qr_px / span
                cells = []
                for _, fn in CONDITIONS:
                    hits = 0
                    for f in frames:
                        img, _, _ = render(f, 900)
                        got = pyzbar.decode(fn(on_sensor(img, fill)))
                        if got and got[0].data.decode() == f.upper():
                            hits += 1
                    cells.append(f"{hits}/{len(frames)}")
                row = f"    {fill:.0%}    {per_module:6.2f}     " + \
                      "  ".join(f"{c:>11}" for c in cells)
                print(row)
                verdicts[(script_type, density, fill)] = cells
            print()

    # the one number that decides ticket 03
    print("=" * 78)
    for density in ("NORMAL", "LOW"):
        worst = []
        for (st, d, fill), cells in verdicts.items():
            if d != density or fill < 0.60:
                continue
            worst += [c for c in cells]
        full = sum(1 for c in worst if c.split("/")[0] == c.split("/")[1])
        print(f"density {density:<7} at 60% fill and better: "
              f"{full}/{len(worst)} condition-sets decoded every frame")


if __name__ == "__main__":
    sys.exit(main())
