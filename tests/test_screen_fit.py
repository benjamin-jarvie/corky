"""Every string on every screen must land inside the panel.

The device has 320x240 pixels and no scrollbar: a string drawn past the edge
is simply not there, and the user is asked to write down a backup whose last
third never rendered. This suite instruments ImageDraw.text, renders every
screen at both v1 resolutions with worst-case content, and fails on any
bounding box outside the canvas.

Run: python3 tests/test_screen_fit.py
"""
import ast
import base64
import inspect
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
from PIL import ImageDraw  # noqa: E402
import screens  # noqa: E402
import qrchannel  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    fails.append(m)
    print("FAIL", m)


_orig_text = ImageDraw.ImageDraw.text
_ctx = {"w": 0, "h": 0, "name": "", "over": [], "drawn": []}


def _measured_text(self, xy, text, *a, **kw):
    box = self.textbbox(xy, text, font=kw.get("font"),
                        anchor=kw.get("anchor", "la"))
    w, h = _ctx["w"], _ctx["h"]
    if box[0] < 0 or box[1] < 0 or box[2] > w or box[3] > h:
        _ctx["over"].append((text, [int(v) for v in box]))
    _ctx["drawn"].append((str(text), tuple(int(v) for v in box)))
    return _orig_text(self, xy, text, *a, **kw)


def collisions(drawn):
    """Pairs of DIFFERENT strings whose boxes intersect.

    Escaping the panel was checked; two strings painted on top of each
    other inside it was not. The review screen drew its address and its
    amount with a bare d.text, neither bounded by the other, and on the
    240x240 pocket panel they overlapped from about 100,000 BTC: two
    unreadable strings on the screen the user signs from (found reading
    screens.py, 2026-09-08).

    Two exclusions, both real rather than convenient:

      the same string twice is `_fit(bold=True)`, which draws a word a
      second time one pixel right to thicken its stems;

      two SINGLE characters are `_tracked`, which draws letter by letter
      and lets adjacent glyph boxes share a pixel of bearing.

    A single character against a longer string is still a collision, so
    neither exclusion opens a hole.
    """
    def hits(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0]
                    or a[3] <= b[1] or b[3] <= a[1])

    return [(x, y) for i, x in enumerate(drawn) for y in drawn[i + 1:]
            if x[0] != y[0] and len(x[0]) + len(y[0]) > 2 and hits(x[1], y[1])]


ImageDraw.ImageDraw.text = _measured_text

# Worst case in every field the flows can actually produce.
XPRV = ("xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvv"
        "NKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi")          # 111 chars
ADDR = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"
OUTPUTS = [(ADDR, 0.03444556), ("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
                                21.21212121), (ADDR, 0.1), (ADDR, 0.2)]

COSIGNERS = [("a1b2c3d4", "m/48h/0h/0h/2h"), ("e5f6a7b8", "m/48h/0h/0h/2h"),
             ("09c1d2e3", "m/48h/0h/0h/2h")]
# A blinded path, which is what M4 proved Core signs on: three hardened
# levels of 31 bits each, so the longest path this device can be told.
BLINDED = [(f"{i:08x}", "m/607137099h/1711870460h/1965312408h")
           for i in (0x4513369e, 0x73c5da0a, 0xbeb4fc29)]
# A quorum too wide to name key by key. P2WSH allows up to 20 pubkeys in
# a CHECKMULTISIG, and 20 eight-character fingerprints do not fit on 240
# pixels at any size a person can read.
WIDE = [(f"{i:08x}", "m/48h/0h/0h/2h") for i in range(0x10000000, 0x10000014)]

CASES = {
    "splash": lambda w, h: screens.splash(w, h),
    "home": lambda w, h: screens.home(w, h, 1),
    "review-1page": lambda w, h: screens.review(w, h, OUTPUTS[:2], 0.0000851,
                                                input_total_btc=21.3),
    "review-paged": lambda w, h: screens.review(w, h, OUTPUTS, 0.0000851,
                                                input_total_btc=21.3, page=1),
    "review-refused": lambda w, h: screens.review(w, h, OUTPUTS, 0.0000851,
                                                  input_total_btc=21.3,
                                                  unseen_pages=True),
    # The widest string the format can produce. 21,000,000.00000000 is
    # every bitcoin there will ever be, so no real transaction is wider,
    # and the pocket panel had the address and the amount overlapping from
    # about a twentieth of that (2026-09-08). The fixture above tops out
    # at 21.21212121, which is why nothing saw it.
    "review-whole-supply": lambda w, h: screens.review(
        w, h, [(ADDR, Decimal("20999999.99999999")),
               (ADDR, Decimal("21000000"))],
        Decimal("20999999.99999999"),
        input_total_btc=Decimal("21000000")),
    # The multisig review (map M9). Three eight-character fingerprints
    # and a path on the screen you sign from is the most crowded this
    # screen gets, and the worst case is all of it at once: the widest
    # amount, a paged transaction, unseen pages, and a blinded path,
    # which is longer than any BIP48 one and is the case Corky can sign
    # that most vendors cannot.
    "review-quorum": lambda w, h: screens.review(
        w, h, OUTPUTS[:2], Decimal("20999999.99999999"),
        input_total_btc=Decimal("21000000"),
        quorum=(2, 3), cosigners=COSIGNERS, ours=COSIGNERS[1][0]),
    "review-quorum-paged": lambda w, h: screens.review(
        w, h, OUTPUTS, 0.0000851, input_total_btc=21.3, page=1,
        unseen_pages=True, quorum=(2, 3), cosigners=BLINDED,
        ours=BLINDED[0][0]),
    "review-quorum-wide": lambda w, h: screens.review(
        w, h, OUTPUTS[:2], 0.0000851, input_total_btc=21.3,
        quorum=(11, 15), cosigners=WIDE, ours=WIDE[7][0]),
    "review-mixed": lambda w, h: screens.review(
        w, h, OUTPUTS[:2], 0.0000851, input_total_btc=21.3,
        quorum="mixed", cosigners=COSIGNERS, ours=None),
    "review-solo-path": lambda w, h: screens.review(
        w, h, OUTPUTS[:2], 0.0000851, input_total_btc=21.3,
        cosigners=[("a1b2c3d4", "m/84h/0h/0h")], ours="a1b2c3d4"),
    # Six screens had no case at all until 2026-09-08, so neither the fit
    # check nor the collision check had ever rendered them. The guard
    # below fails if a seventh appears.
    "about": lambda w, h: screens.about(w, h),
    # These two were in MENUS below, which checks menu GEOMETRY and does
    # not run the fit or collision checks. Rendered for one purpose and
    # never for the other, which reads as covered and is not.
    "settings-menu": lambda w, h: screens.settings_menu(w, h, 1),
    "channel-menu": lambda w, h: screens.channel_menu(w, h, 1),
    "scanning": lambda w, h: screens.scanning(
        w, h, None, "hold the QR in view", 0.42),
    "scanning-advisory": lambda w, h: screens.scanning(
        w, h, None, "large frames: set Sparrow to Low density", 0.0),
    # The outbound PSBT frame, on the same card as the export since
    # 2026-09-08. Sized against the card's budget, which is what the
    # device does, so this case fails if the card ever starts costing the
    # code its size.
    "qr-frame": lambda w, h: screens.qr_frame(
        w, h, qrchannel.frames_to_images(
            qrchannel.psbt_to_frames(
                base64.b64encode(b"psbt\xff" + b"\x01\x02\x03" * 400).decode()),
            panel=(min(w, h) - 2 * (screens.QR_CARD_PAD + screens.STROKE),) * 2)[0]),
    "qr-export": lambda w, h: screens.qr_export(
        w, h, qrchannel.text_to_image(
            "wpkh([73c5da0a/84h/0h/0h]" + "x" * 90 + "/0/*)#kwx0dvhr",
            panel=(w, min(h, screens.QR_MAX_PX))),
        "73c5da0a", "wpkh", "m/84h/0h/0h"),
    "text-entry": lambda w, h: screens.text_entry(
        w, h, "BIP32  EXTENDED  PRIVATE  KEY", "tprv8ZgxMBicQKsPe", 7,
        secret=True, caret=17),
    "check-result-pass": lambda w, h: screens.check_result(
        w, h, XPRV[:48], set(), "KEY  D2B7E45C", page=0, pages=3),
    "check-result-fail": lambda w, h: screens.check_result(
        w, h, XPRV[:48], {3, 11, 40}, "KEY  D2B7E45C", page=1, pages=3),
    "verified": lambda w, h: screens.verified(
        w, h, "key 73C5DA0A\nowns this address"),
    "result-ok": lambda w, h: screens.result(w, h),
    "result-fail": lambda w, h: screens.result(
        w, h, ok=False, detail="PSBT lacks input data; fee unknown"),

    "keys-menu": lambda w, h: screens.keys_menu(
        w, h, [("corky", "d2b7e45c"), ("corky-2", "668b2262"),
               ("corky-3", "1df2e0b2"), ("corky-4", "73c5da0a"),
               ("corky-5", "ba4c8bd5")], 5),
    "keys-menu-empty": lambda w, h: screens.keys_menu(w, h, [], 0),
    "key-menu": lambda w, h: screens.key_menu(w, h, "d2b7e45c", 3),
    "tools-menu": lambda w, h: screens.tools_menu(w, h, 1),
    "leak-clear": lambda w, h: screens.leak_report(
        w, h, [("Wi-Fi driver", "not loaded", "normal")] * 24, 0),
    "leak-failures": lambda w, h: screens.leak_report(
        w, h, [("Wi-Fi overlay", "not set", "leak"),
               ("Bluetooth driver", "loaded", "leak"),
               ("Swap", "ON, key pages reach the card", "leak"),
               ("Serial console", "on the GPIO header", "leak"),
               ("USB device mode", "active, can be a disk", "leak"),
               ("Core networking", "off", "normal")], 3),
    "export-text": lambda w, h: screens.export_text(
        w, h, "wpkh([73c5da0a/84h/1h/0h]tpubDDRDHYNXyuoRVQwotDQHr", 1, 3),
    "address-taproot": lambda w, h: screens.address_page(w, h, 2, "bcrt1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr", "tr"),
    "address-segwit": lambda w, h: screens.address_page(
        w, h, 0, "bc1q635yhaml2afumm27jxsjmqayczf5nf0xmm9zh0", "wpkh"),
    "choose-channel": lambda w, h: screens.choose_channel(
        w, h, ["stick", "card"], 1),
    "confirm-discard": lambda w, h: screens.confirm_discard(w, h, "d2b7e45c", 1),
    "export-options": lambda w, h: screens.export_options(w, h, 0),
    "script-menu": lambda w, h: screens.script_menu(
        w, h, ("wpkh", "tr", "sh", "pkh"), 0),
    "choose-key": lambda w, h: screens.choose_key(
        w, h, [("corky", "d2b7e45c"), ("corky-2", "668b2262"),
               ("corky-3", "1df2e0b2"), ("corky-4", "73c5da0a"),
               ("corky-5", "ba4c8bd5")], {"1df2e0b2"}, 2),
    "busy": lambda w, h: screens.busy(w, h, "Bitcoin Core is generating your key…"),
    "keymaterial-warning": lambda w, h: screens.keymaterial_warning(w, h,
                                                                    "descriptor"),
}

# ---- every menu starts in the same place, and below its own divider ----
# Found on the board 2026-09-05: the selection box on a four-row menu was
# drawn through the title and the line under it, and two menus had their own
# geometry so each one began at a different height. This looks for the
# highlight colour above the divider, which is what that bug looks like in
# pixels, and pins that the first row lands identically on every menu.
MENUS = {
    "keys": lambda w, h: screens.keys_menu(w, h, [("corky", "d2b7e45c")], 0),
    "key": lambda w, h: screens.key_menu(w, h, "d2b7e45c", 0),
    "tools": lambda w, h: screens.tools_menu(w, h, 0),
    "settings": lambda w, h: screens.settings_menu(w, h, 0),
    "channel": lambda w, h: screens.channel_menu(w, h, 0),
    "export options": lambda w, h: screens.export_options(w, h, 0),
    "script type": lambda w, h: screens.script_menu(
        w, h, ("wpkh", "tr", "sh", "pkh"), 0),
}


def _ochre_rows(img):
    """Rows carrying the selection box's top or bottom edge.

    It used to be any row carrying the colour, which stopped working when
    the title turned gold too (Ben, 2026-09-05). Looking at both edges of
    the row was not enough either: a long title fitted to 92% of a 240px
    panel spans the same x range the box does.

    What separates them is that the box's edge is a SOLID horizontal run
    and text is not, however wide the text gets. So a row counts when its
    longest unbroken run of gold covers more than 60% of the width.
    """
    want = tuple(int(screens.OCHRE[i:i + 2], 16) for i in (1, 3, 5))
    px = img.load()
    rows = set()
    for y in range(img.height):
        run = best = 0
        for x in range(img.width):
            run = run + 1 if px[x, y] == want else 0
            best = max(best, run)
        if best > img.width * 0.6:
            rows.add(y)
    return rows


for w, h in [(320, 240), (240, 240)]:
    # The divider is gone; what the first row must clear is the title,
    # which sits centred in the space above MENU_TOP.
    title_bottom = int(h * screens.MENU_TOP / 2) + int(h * 0.035)
    tops = {}
    for name, render in MENUS.items():
        rows = _ochre_rows(render(w, h))
        if not rows:
            bad(f"{w}x{h} {name}: nothing is highlighted at all")
            continue
        top = min(rows)
        tops[name] = top
        if top <= title_bottom:
            bad(f"{w}x{h} {name}: the selection box reaches y={top}, "
                f"through the title, which ends near y={title_bottom}")
    if len(set(tops.values())) == 1:
        ok(f"{w}x{h}: all {len(tops)} menus start their first row at "
           f"y={next(iter(tops.values()))}, clear of the title")
    else:
        bad(f"{w}x{h}: menus start at different heights: {tops}")


# EVERY screen must have a case, or the two checks above are reporting on
# whatever somebody remembered to add. Six had none until 2026-09-08:
# about, scanning, qr_export, text_entry, check_result and verified,
# which between them are the export card, the viewfinder, the keyboard a
# key is typed into and the screen that says a paper backup is good.
#
# A screen is a public function in screens.py whose first two parameters
# are w and h. That leaves out scrollbar (which draws onto a canvas it is
# handed), and charset_pages, echo_window and text_pages, which return
# data rather than a frame.
_tree = ast.parse((ROOT / "corky" / "screens.py").read_text())
_screens = [n.name for n in _tree.body
            if isinstance(n, ast.FunctionDef)
            and not n.name.startswith("_")
            and [a.arg for a in n.args.args][:2] == ["w", "h"]]
#: Screens checked by a loop of their own further down rather than by a
#: CASES entry, and why. Named here rather than found by searching the
#: whole file, because MENUS renders two screens for a geometry check that
#: runs neither of the checks above: a mention is not a check.
CHECKED_ELSEWHERE = {
    "backup_page": "paginated per page in the text_pages loop below",
}
_source_of_cases = "".join(
    inspect.getsource(fn) for fn in CASES.values())
_uncovered = [n for n in _screens
              if f"screens.{n}(" not in _source_of_cases
              and n not in CHECKED_ELSEWHERE]
if _uncovered:
    bad(f"{len(_uncovered)} screen(s) that no case renders, so nothing "
        f"checks whether they fit or overlap: {_uncovered}")
else:
    ok(f"all {len(_screens)} screens have a case in this file")

for w, h in [(320, 240), (240, 240)]:
    for name, render in CASES.items():
        _ctx.update(w=w, h=h, name=name, over=[], drawn=[])
        render(w, h)
        clashes = collisions(_ctx["drawn"])
        if _ctx["over"]:
            for text, box in _ctx["over"]:
                bad(f"{w}x{h} {name}: {text[:40]!r} at {box} escapes {w}x{h}")
        elif clashes:
            for x, y in clashes:
                bad(f"{w}x{h} {name}: {x[0][:28]!r} at {x[1]} is painted "
                    f"over {y[0][:28]!r} at {y[1]}")
        else:
            ok(f"{w}x{h} {name} fits, and nothing is painted over "
               f"anything else")

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
        pages = screens.text_pages(payload)
        if len(pages) < 2:
            bad(f"{label}: text_pages did not split a {len(payload)}-char string")
            continue
        if "".join(pages) != payload:
            bad(f"{label}: text_pages loses or reorders characters")
            continue
        for i, page in enumerate(pages):
            _ctx.update(w=w, h=h, name=f"backup-{label}-{i}", over=[],
                        drawn=[])
            screens.backup_page(w, h, page, "KEY  D2B7E45C",
                                page=i, pages=len(pages))
            for text, box in _ctx["over"]:
                bad(f"{w}x{h} backup {label} page {i}: {text[:32]!r} at {box}")
            # This loop checked the panel edge and not the overlap, which
            # is how backup_page reached 2026-09-08 half-checked while
            # reading as covered. It carries the key a user writes down.
            for x, y in collisions(_ctx["drawn"]):
                bad(f"{w}x{h} backup {label} page {i}: {x[0][:20]!r} at "
                    f"{x[1]} is painted over {y[0][:20]!r} at {y[1]}")
        ok(f"{w}x{h} {label} paginates into {len(pages)} pages that fit")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
