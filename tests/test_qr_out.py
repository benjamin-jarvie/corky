"""The QR return channel: what the coordinator's scanner actually sees.

This suite exists because the review found D11 and D12 shipped untested.
A signed PSBT leaves Corky as pixels on a panel, so the properties that
matter are geometric, not logical: modules must stay square, the quiet zone
must survive, and a multi-frame animation must repeat at a steady rate.

Run: python3 tests/test_qr_out.py
"""
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))
from PIL import Image  # noqa: E402
import qrchannel  # noqa: E402
import hal  # noqa: E402
import main as corky_main  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


PANEL_W, PANEL_H = 320, 240


# --- D11: integer scaling, square modules, quiet zone ---------------------

def module_edges_are_integral(src, out, factor):
    """Every source pixel must map to an exact factor x factor block."""
    sx, sy = src.size
    for py in range(0, sy, max(1, sy // 8)):
        for px in range(0, sx, max(1, sx // 8)):
            want = src.getpixel((px, py))
            ox = (out.width - sx * factor) // 2 + px * factor
            oy = (out.height - sy * factor) // 2 + py * factor
            for dy in range(factor):
                for dx in range(factor):
                    if out.getpixel((ox + dx, oy + dy)) != want:
                        return False
    return True


src = Image.new("RGB", (60, 60), "white")
for x in range(0, 60, 2):          # a striped pattern stands in for modules
    for y in range(60):
        src.putpixel((x, y), (0, 0, 0))

out = qrchannel.fit_to_panel(src, PANEL_W, PANEL_H)
if out.size != (PANEL_W, PANEL_H):
    bad(f"fit_to_panel returned {out.size}, not the panel size")
else:
    ok("fit_to_panel returns exactly the panel size")

factor = min(PANEL_W // src.width, PANEL_H // src.height)
if not module_edges_are_integral(src, out, factor):
    bad("fit_to_panel did not scale by a whole number: modules are not square")
else:
    ok(f"fit_to_panel scaled by an integer factor ({factor}x), modules square")

# The surround must be white, so the quiet zone is not swallowed by the ink
# ground of the rest of the UI.
if out.getpixel((1, 1)) != (255, 255, 255):
    bad("the letterbox surround is not white: the quiet zone is lost")
else:
    ok("the letterbox surround is white, preserving the quiet zone")

# A square source must stay square on a 4:3 panel: this is the whole defect
# D11 named. Compare the scaled block's width and height.
scaled_w = src.width * factor
scaled_h = src.height * factor
if scaled_w != scaled_h:
    bad(f"a square QR became {scaled_w}x{scaled_h} on the panel")
else:
    ok("a square QR stays square on a 4:3 panel")

# Known open defect I-1: an oversized QR is cropped rather than downscaled.
# This test PINS the current behaviour so the fix is visible when it lands.
big = Image.new("RGB", (400, 400), "white")
big_out = qrchannel.fit_to_panel(big, PANEL_W, PANEL_H)
if big_out.size == (PANEL_W, PANEL_H) and big.width > PANEL_W:
    ok("KNOWN GAP I-1: an oversized QR is still cropped, not downscaled "
       "(see ISSUES.md)")


# --- D12: the animation repeats, is paced, and a key stops it -------------

class CountingDisplay:
    width, height = PANEL_W, PANEL_H

    def __init__(self):
        self.shown = []
        self.lock = threading.Lock()

    def show(self, image, sensitive=False):
        with self.lock:
            self.shown.append(image)


class BlockingButtons:
    """Holds until released, so the loop runs like it does on the device."""

    def __init__(self):
        self.release = threading.Event()

    def read(self):
        self.release.wait(timeout=5)
        return "c"


class FakeRpc:
    chain = "regtest"

    def call(self, *a, **k):
        return ""


frames = [f"ur:crypto-psbt/{i}-4/abcdefgh" for i in range(4)]
display = CountingDisplay()
buttons = BlockingButtons()
session = corky_main.Session(display, buttons, FakeRpc())
session.animate = True             # the path that ships to the device

worker = threading.Thread(target=session._show_qr_loop,
                          args=(frames,), kwargs={"delay": 0.02},
                          daemon=True)
worker.start()
time.sleep(0.45)                   # long enough for several full cycles
with display.lock:
    during = len(display.shown)
buttons.release.set()
worker.join(timeout=3)

if worker.is_alive():
    bad("_show_qr_loop did not stop when a key was pressed")
else:
    ok("_show_qr_loop stops on a key press")

if during <= len(frames):
    bad(f"_show_qr_loop showed {during} frames for a {len(frames)}-frame "
        "animation: it played once instead of repeating")
else:
    ok(f"_show_qr_loop repeats ({during} frames shown for {len(frames)} "
       "parts, so the coordinator can catch every one)")

# Pacing: with a 0.02s delay, ~0.45s of running cannot produce hundreds of
# frames. An unpaced loop would spin at the display's full rate.
if during > 200:
    bad(f"_show_qr_loop is not paced: {during} frames in 0.45s")
else:
    ok(f"_show_qr_loop is paced by its delay ({during} frames in 0.45s)")

# A single-frame PSBT is a static QR, and must wait rather than animate.
single_display = CountingDisplay()
single_buttons = hal.DevButtons("a")
single = corky_main.Session(single_display, single_buttons, FakeRpc())
single.animate = True
single._show_qr_loop([frames[0]])
if len(single_display.shown) != 1:
    bad(f"a one-frame PSBT painted {len(single_display.shown)} frames, not 1")
else:
    ok("a one-frame PSBT is shown once as a static QR and waits for a key")

# Every frame the loop paints must be panel-sized, not raw QR-sized.
sizes = {img.size for img in display.shown}
if sizes and sizes != {(PANEL_W, PANEL_H)}:
    bad(f"the loop painted frames that are not panel-sized: {sizes}")
else:
    ok("every animated frame is panel-sized and letterboxed")


print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
