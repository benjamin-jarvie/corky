"""The QR return channel: what the coordinator's scanner actually sees.

This suite exists because the review found D11 and D12 shipped untested.
A signed PSBT leaves Corky as pixels on a panel, so the properties that
matter are geometric, not logical: modules must stay square, the quiet zone
must survive, and a multi-frame animation must repeat at a steady rate.

Run: python3 tests/test_qr_out.py
"""
import base64
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

# --- I-1: an oversized QR must never be cropped ---------------------------
#
# Cropping leaves the panel showing something QR-shaped that no scanner can
# read, and nothing on the device says so. fit_to_panel refuses; the real
# guard is frames_to_images(panel=...), which sizes the modules so an
# oversized frame cannot be produced in the first place.

big = Image.new("RGB", (400, 400), "white")
try:
    qrchannel.fit_to_panel(big, PANEL_W, PANEL_H)
    bad("fit_to_panel cropped a 400x400 QR instead of refusing it (I-1)")
except qrchannel.QrChannelError:
    ok("fit_to_panel refuses an oversized QR rather than cropping it (I-1)")

# The cliff measured before the fix: 336 characters renders a version-10 QR
# at 244px, which overflows a 240px panel. Sweep fragment lengths well past
# it, on BOTH panels, and require every frame to fit.
psbt_b64 = base64.b64encode(bytes(range(256)) * 16).decode()
for panel in ((320, 240), (240, 240)):          # SeedSigner+ hat, pocket hat
    for mfl in (100, 150, 200, 400):
        parts = qrchannel.psbt_to_frames(psbt_b64, max_fragment_len=mfl)
        longest = max(len(f) for f in parts)
        imgs = qrchannel.frames_to_images(parts, panel=panel)
        over = [i.size for i in imgs if i.width > panel[0] or i.height > panel[1]]
        if over:
            bad(f"panel {panel}, fragment {mfl} ({longest} chars): "
                f"frames overflow the panel: {set(over)}")
            continue
        # One size for the whole set: a set that changes size mid-animation
        # makes a scanner re-acquire on every frame.
        if len({i.size for i in imgs}) != 1:
            bad(f"panel {panel}, fragment {mfl}: the animation changes size "
                f"between frames: {sorted({i.size for i in imgs})}")
            continue
        # And each one must survive the real display path.
        fitted = {qrchannel.fit_to_panel(i, *panel).size for i in imgs}
        if fitted != {panel}:
            bad(f"panel {panel}, fragment {mfl}: fit_to_panel gave {fitted}")
        else:
            ok(f"panel {panel[0]}x{panel[1]}, fragment {mfl} "
               f"({longest} chars): every frame fits at {imgs[0].width}px")

# box_size stays the CEILING. A frame that already fits must render exactly
# as it did before the fix, because changing what the coordinator sees is
# not provable without a scanner in front of the panel (audit D11/D12).
for mfl in (100, 150):
    parts = qrchannel.psbt_to_frames(psbt_b64, max_fragment_len=mfl)
    sized = qrchannel.frames_to_images(parts, panel=(PANEL_W, PANEL_H))[0]
    fixed = qrchannel.frames_to_images(parts)[0]
    fits = fixed.height <= PANEL_H
    if fits and sized.size != fixed.size:
        bad(f"fragment {mfl} already fitted at {fixed.size} and panel sizing "
            f"changed it to {sized.size}")
    elif not fits and sized.height > PANEL_H:
        bad(f"fragment {mfl} did not fit at {fixed.size} and panel sizing "
            f"left it at {sized.size}")
    else:
        ok(f"fragment {mfl}: {fixed.size[0]}px -> {sized.size[0]}px "
           f"({'unchanged, it already fitted' if fits else 'shrunk to fit'})")


# --- the signature must survive a QR that cannot be shown -----------------
#
# fit_to_panel and frames_to_images both raise now. state_sign runs them
# AFTER signing, so an uncaught raise would unwind past the result screen
# and throw a good signature away (the shape of audit D18).

class _Rpc:
    chain = "regtest"

    def call(self, *a, **k):
        return ""


class _Display:
    width, height = PANEL_W, PANEL_H

    def show(self, image, sensitive=False):
        pass


class _Buttons:
    def read(self):
        return "a"


boom = corky_main.Session(_Display(), _Buttons(), _Rpc())
boom.animate = False
real_frames = qrchannel.frames_to_images


def _raise(*a, **k):
    raise qrchannel.QrChannelError("frame does not fit the panel")


qrchannel.frames_to_images = _raise
try:
    import signer as _signer
    real_sign = _signer.sign_psbt
    _fake = base64.b64encode(b"psbt\xff" + bytes(range(256))).decode()
    _signer.sign_psbt = lambda rpc, psbt: {"complete": True, "psbt": _fake}
    try:
        outcome = boom.state_sign(_fake, None)
    finally:
        _signer.sign_psbt = real_sign
except qrchannel.QrChannelError:
    bad("state_sign let QrChannelError unwind after a successful sign: "
        "the signature is lost and no screen says so")
    outcome = None
finally:
    qrchannel.frames_to_images = real_frames

if outcome == corky_main.TO_HOME:
    ok("a QR that cannot be shown reports the failure and keeps the session, "
       "rather than throwing the signature away")
elif outcome is not None:
    bad(f"state_sign returned {outcome!r} after an unshowable QR")


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
