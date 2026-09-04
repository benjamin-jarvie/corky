"""Every string on every screen must land inside the panel.

The device has 320x240 pixels and no scrollbar: a string drawn past the edge
is simply not there, and the user is asked to write down a backup whose last
third never rendered. This suite instruments ImageDraw.text, renders every
screen at both v1 resolutions with worst-case content, and fails on any
bounding box outside the canvas.

Run: python3 tests/test_screen_fit.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
from PIL import ImageDraw  # noqa: E402
import screens  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    fails.append(m)
    print("FAIL", m)


_orig_text = ImageDraw.ImageDraw.text
_ctx = {"w": 0, "h": 0, "name": "", "over": []}


def _measured_text(self, xy, text, *a, **kw):
    box = self.textbbox(xy, text, font=kw.get("font"),
                        anchor=kw.get("anchor", "la"))
    w, h = _ctx["w"], _ctx["h"]
    if box[0] < 0 or box[1] < 0 or box[2] > w or box[3] > h:
        _ctx["over"].append((text, [int(v) for v in box]))
    return _orig_text(self, xy, text, *a, **kw)


ImageDraw.ImageDraw.text = _measured_text

# Worst case in every field the flows can actually produce.
XPRV = ("xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvv"
        "NKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi")          # 111 chars
ADDR = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"
OUTPUTS = [(ADDR, 0.03444556), ("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
                                21.21212121), (ADDR, 0.1), (ADDR, 0.2)]

CASES = {
    "splash": lambda w, h: screens.splash(w, h),
    "home": lambda w, h: screens.home(w, h, 1),
    "review-1page": lambda w, h: screens.review(w, h, OUTPUTS[:2], 0.0000851, 3,
                                                input_total_btc=21.3),
    "review-paged": lambda w, h: screens.review(w, h, OUTPUTS, 0.0000851, 9,
                                                input_total_btc=21.3, page=1),
    "review-refused": lambda w, h: screens.review(w, h, OUTPUTS, 0.0000851, 9,
                                                  input_total_btc=21.3,
                                                  unseen_pages=True),
    "result-ok": lambda w, h: screens.result(w, h),
    "result-fail": lambda w, h: screens.result(
        w, h, ok=False, detail="PSBT lacks input data; fee unknown"),
    "seed-menu": lambda w, h: screens.seed_menu(w, h, 4),
    "busy": lambda w, h: screens.busy(w, h, "Bitcoin Core is generating your key…"),
    "generate-warning": lambda w, h: screens.generate_warning(w, h),
    "keymaterial-warning": lambda w, h: screens.keymaterial_warning(w, h,
                                                                    "descriptor"),
}

for w, h in [(320, 240), (240, 240)]:
    for name, render in CASES.items():
        _ctx.update(w=w, h=h, name=name, over=[])
        render(w, h)
        if _ctx["over"]:
            for text, box in _ctx["over"]:
                bad(f"{w}x{h} {name}: {text[:40]!r} at {box} escapes {w}x{h}")
        else:
            ok(f"{w}x{h} {name} fits")

# Branding must survive a one-bit or inverted panel without depending on
# colour. Capture the requested drawing colours rather than antialiased pixel
# blends, which naturally contain intermediate RGB values.
used_splash_colours = []
draw_methods = {name: getattr(ImageDraw.ImageDraw, name)
                for name in ("text", "line", "polygon", "rectangle")}
try:
    for name, method in draw_methods.items():
        def capture(self, *args, _method=method, **kwargs):
            used_splash_colours.extend(
                colour for colour in (kwargs.get("fill"), kwargs.get("outline"))
                if colour is not None)
            return _method(self, *args, **kwargs)
        setattr(ImageDraw.ImageDraw, name, capture)
    screens.splash(320, 240)
finally:
    for name, method in draw_methods.items():
        setattr(ImageDraw.ImageDraw, name, method)

# Ben (2026-09-01): the splash names the brand, "Bitcoin Butlers" in gold.
# It is no longer monochrome; it must still use only brand tokens, never a
# stray colour.
allowed = {screens.CREAM, screens.OCHRE, screens.GREY}
unexpected = set(used_splash_colours) - allowed
if unexpected:
    bad(f"splash requests non-brand foreground colours: {unexpected}")
else:
    ok("splash requests only brand tokens (cream, gold, grey)")

# The backup screens carry strings the flows really produce: a 127-character
# A-22: only Core's 111-character master xprv now; the codex32 string
# went to the lab with the module that made it.
# Neither fits one page, so the screen must paginate rather than overrun.
for w, h in [(320, 240), (240, 240)]:
    for label, payload in (("xprv", XPRV),):
        pages = screens.share_pages(payload)
        if len(pages) < 2:
            bad(f"{label}: share_pages did not split a {len(payload)}-char string")
            continue
        if "".join(pages) != payload:
            bad(f"{label}: share_pages loses or reorders characters")
            continue
        for i, page in enumerate(pages):
            _ctx.update(w=w, h=h, name=f"share-{label}-{i}", over=[])
            screens.backup_page(w, h, page, 1, 1,
                                          page=i, pages=len(pages))
            for text, box in _ctx["over"]:
                bad(f"{w}x{h} share {label} page {i}: {text[:32]!r} at {box}")
        ok(f"{w}x{h} {label} paginates into {len(pages)} pages that fit")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
