"""Corky's screens as pure PIL renders.

Resolution-independent: every screen takes (width, height) and lays out from
proportions, so the same code drives the primary 2.8" ST7789 (320x240) and the
1.3" ST7789 (240x240). On-device, frames go to the vendored drivers'
show_image(); on a dev machine they save as PNGs for review (see
tools/render_screens.py).

Palette follows the Corky/Kawanatanga artefact palette: ink ground, cream
text, Te Peeke red for the one number that matters on each screen.
"""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = "#1A1714"
CREAM = "#F5EFE0"
RED = "#9E2B25"
GREEN = "#2E4A3B"
GREY = "#B8B2A6"
OCHRE = "#C8912F"


@lru_cache(maxsize=None)
def _font(size):
    return ImageFont.load_default(size=size)


_ICON_TTF = (Path(__file__).resolve().parent.parent
             / "hw" / "vendor" / "fonts" / "fa-solid-subset.ttf")


@lru_cache(maxsize=None)
def _iconfont(size):
    return ImageFont.truetype(str(_ICON_TTF), size)


# Font Awesome Free Solid codepoints (see hw/vendor/fonts/NOTICE.md).
ICON = {"load": "\uf019", "key": "\uf084", "tools": "\uf7d9",
        "gear": "\uf013", "power": "\uf011", "about": "\uf05a"}


def _icon(d, cx, cy, size, name, col):
    d.text((cx, cy), ICON[name], font=_iconfont(size), fill=col, anchor="mm")


def _fit(d, xy, text, size, fill, anchor, maxw):
    """Draw text at `size`, shrinking until it fits `maxw`.

    The panel has no scrollbar: a string wider than the canvas is simply not
    there. Every screen that renders content it did not choose itself (an
    address, an error string, a wrapped warning) goes through here, so a
    longer string degrades in size instead of vanishing off the edge. If the
    floor size still overflows, the tail is cut to a visible ellipsis; backup
    key material never reaches that path (share_pages sizes each page, and
    test_screen_fit pins every string inside the canvas).
    """
    while True:
        font = _font(size)
        box = d.textbbox(xy, text, font=font, anchor=anchor)
        if box[2] - box[0] <= maxw or size <= 6:
            break
        size -= 1
    if box[2] - box[0] > maxw:
        while len(text) > 1:
            text = text[:-1]
            box = d.textbbox(xy, text + "…", font=font, anchor=anchor)
            if box[2] - box[0] <= maxw:
                break
        text += "…"
    d.text(xy, text, font=font, fill=fill, anchor=anchor)


def _wrap(d, text, size, maxw):
    """Break `text` into lines that fit `maxw` at `size`, on word boundaries.

    The alternative is shrinking the type, which is what _fit does and what
    the generate warning used to do. On a screen that already scrolls that
    is the wrong trade: height is free and legibility is not.
    """
    out, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if not cur or _width(d, trial, size, "mm", (0, 0)) <= maxw:
            cur = trial
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def _fit_block(d, lines, xs, size, fill, anchor, maxw):
    """Draw several lines of body copy at ONE shared size.

    _fit shrinks each string on its own, which is right for a single string
    the device did not choose and wrong for a paragraph: the long line comes
    out smaller than the short one and the block reads ragged. Found on the
    board, 2026-09-04, on the generate-a-seed warning.

    Picks the largest size at or below `size` where EVERY line fits, then
    draws them all at it. Falls back to _fit per line only at the floor, so
    a pathological string still degrades rather than running off the edge.
    """
    while size > 6:
        if all(_width(d, text, size, anchor, xs[0]) <= maxw for text in lines):
            break
        size -= 1
    font = _font(size)
    for text, xy in zip(lines, xs):
        if _width(d, text, size, anchor, xy) > maxw:
            _fit(d, xy, text, size, fill, anchor, maxw)   # floor reached
        else:
            d.text(xy, text, font=font, fill=fill, anchor=anchor)
    return size


def _width(d, text, size, anchor, xy):
    box = d.textbbox(xy, text, font=_font(size), anchor=anchor)
    return box[2] - box[0]


def _actions(d, w, h, labels, selected=1):
    """The bottom action bar (Ben, 2026-09-01): actions are visible,
    d-pad-toggleable options in one place, never key legends in corners.
    The gold box marks the active option; A activates it."""
    size = int(h * 0.05)
    box_h = int(h * 0.085)
    gap = int(w * 0.03)
    widths = [d.textbbox((0, 0), t, font=_font(size))[2] + int(w * 0.06)
              for t in labels]
    x = (w - sum(widths) - gap * (len(labels) - 1)) // 2
    cy = int(h * 0.93)
    for i, (t, bw) in enumerate(zip(labels, widths)):
        active = i == selected
        d.rounded_rectangle([x, cy - box_h // 2, x + bw, cy + box_h // 2],
                            radius=4, outline=OCHRE if active else GREY)
        d.text((x + bw // 2, cy), t, font=_font(size),
               fill=CREAM if active else GREY, anchor="mm")
        x += bw + gap


def _status_circle(img, d, w, h, label, colour):
    """A smooth status ring, drawn 4x and downsampled: a 3px ellipse at
    panel size aliases into stair-steps. Sized so the label breathes."""
    r = int(h * 0.23)
    cx, cy = w // 2, int(h * 0.32)
    ss = 4
    ring = Image.new("L", (2 * r * ss, 2 * r * ss), 0)
    ImageDraw.Draw(ring).ellipse(
        [2 * ss, 2 * ss, 2 * r * ss - 2 * ss, 2 * r * ss - 2 * ss],
        outline=255, width=3 * ss)
    img.paste(colour, (cx - r, cy - r), ring.resize((2 * r, 2 * r),
                                                    Image.LANCZOS))
    _fit(d, (cx, cy), label, int(h * 0.075), colour, "mm", int(r * 1.6))


def _frame(w, h, title=None):
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img)
    if title:
        _fit(d, (w // 2, int(h * 0.06)), title, int(h * 0.07), GREY, "mm",
             int(w * 0.92))
        d.line([(int(w * 0.06), int(h * 0.11)), (int(w * 0.94), int(h * 0.11))],
               fill=GREY, width=1)
    return img, d


# order: load key, key generation, tools, settings (Ben, 2026-09-01)
HOME_TILES = [("load key", "load"), ("key generation", "key"),
              ("tools", "tools"), ("settings", "gear")]


def home(w, h, selected=0, xfp=None):
    """SeedSigner-style 2x2 home: four tiles, each a Font Awesome icon and a
    title. Load key first, key generation second, tools, settings (which
    holds power off). No CORKY text. It is a KEY, not a wallet.

    `xfp` is the loaded wallet's master fingerprint, shown at the top in
    ochre (Ben, 2026-09-04). It is the one fact that tells you WHICH key is
    open, and a signer that cannot answer that invites signing with the
    wrong one. Absent when no key is loaded, so the header doubles as the
    "is anything open" indicator.
    """
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img)
    mx, my, gap = int(w * 0.06), int(h * 0.09), int(w * 0.04)
    if xfp:
        _fit(d, (w // 2, int(h * 0.055)), xfp.upper(), int(h * 0.062),
             OCHRE, "mm", int(w * 0.9))
        my = int(h * 0.125)
    bw = (w - 2 * mx - gap) // 2
    # Bottom margin stays at the original 0.09 so the tiles keep their
    # footing; only the top grows to make room for the fingerprint.
    bh = (h - my - int(h * 0.09) - gap) // 2
    for i, (label, icon) in enumerate(HOME_TILES):
        r, c = divmod(i, 2)
        x = mx + c * (bw + gap)
        y = my + r * (bh + gap)
        active = i == selected
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=6,
                            outline=OCHRE if active else "#3A352E",
                            width=2 if active else 1)
        _icon(d, x + bw // 2, y + int(bh * 0.36), int(bh * 0.44), icon,
              CREAM if active else GREY)
        d.text((x + bw // 2, y + int(bh * 0.80)), label,
               font=_font(int(h * 0.05)),
               fill=CREAM if active else GREY, anchor="mm")
    return img


def settings_menu(w, h, selected=0):
    """Settings holds power off, and grows over time. No legend."""
    img, d = _frame(w, h, "SETTINGS")
    icons = ["power", "about"]
    for i, label in enumerate(SETTINGS_OPTIONS):
        y = int(h * (0.34 + i * 0.20))
        active = i == selected
        if active:
            d.rounded_rectangle([int(w * 0.06), y - int(h * 0.075),
                                 int(w * 0.94), y + int(h * 0.075)],
                                radius=4, outline=OCHRE)
        _icon(d, int(w * 0.14), y, int(h * 0.06), icons[i],
              CREAM if active else GREY)
        d.text((int(w * 0.24), y), label, font=_font(int(h * 0.062)),
               fill=CREAM if active else GREY, anchor="lm")
    return img


def about(w, h):
    img, d = _frame(w, h, "ABOUT")
    d.text((w // 2, int(h * 0.34)), "CORKY", font=_font(int(h * 0.11)),
           fill=CREAM, anchor="mm")
    _fit_block(d, ["Core's keys, nothing kept",
                   "wallet brain: Bitcoin Core 31.1"],
               [(w // 2, int(h * 0.52)), (w // 2, int(h * 0.66))],
               int(h * 0.05), GREY, "mm", int(w * 0.9))
    _actions(d, w, h, ["BACK"], 0)
    return img


SETTINGS_OPTIONS = ["Power off", "About"]


def review(w, h, outputs, fee_btc, input_count, input_total_btc=None, warn=True,
           page=0, unseen_pages=False, actions_sel=1):
    """The screen that matters. outputs: [(address, amount_btc), ...]
    Two outputs per page (Ben, 2026-09-01): less going on per frame."""
    pages = max(1, (len(outputs) + 1) // 2)
    title = ("REVIEW  TRANSACTION" if pages == 1
             else f"REVIEW  ·  OUTPUTS {page + 1}/{pages}")
    img, d = _frame(w, h, title)
    y = int(h * 0.20)
    for addr, amt in outputs[page * 2:page * 2 + 2]:
        # SeedSigner-style short truncation so address and amount share
        # one line: first 8, ellipsis, last 4.
        short = addr[:8] + "…" + addr[-4:] if len(addr) > 13 else addr
        d.text((int(w * 0.06), y), short, font=_font(int(h * 0.055)),
               fill=CREAM, anchor="lm")
        d.text((int(w * 0.94), y), f"{amt:.8f}", font=_font(int(h * 0.055)),
               fill=CREAM, anchor="rm")
        y += int(h * 0.115)
    if pages > 1:
        d.text((w // 2, y + int(h * 0.01)), "UP/DOWN · more outputs",
               font=_font(int(h * 0.045)), fill=OCHRE, anchor="mm")
    ky = int(h * 0.58)
    d.line([(int(w * 0.06), ky), (int(w * 0.94), ky)], fill=GREY, width=1)
    d.text((int(w * 0.06), ky + int(h * 0.075)), "FEE",
           font=_font(int(h * 0.06)), fill=GREY, anchor="lm")
    d.text((int(w * 0.94), ky + int(h * 0.075)), f"{fee_btc:.8f} BTC",
           font=_font(int(h * 0.075)), fill=RED, anchor="rm")
    if input_total_btc is not None:
        d.text((int(w * 0.94), ky + int(h * 0.17)),
               f"inputs {input_total_btc:.8f} BTC",
               font=_font(int(h * 0.045)), fill=GREY, anchor="rm")
    if unseen_pages:
        _fit(d, (w // 2, int(h * 0.80)), "see every output before you sign",
             int(h * 0.045), OCHRE, "mm", int(w * 0.92))
    _actions(d, w, h, ["REJECT", "SIGN"], actions_sel)
    return img


def result(w, h, ok=True, detail="tx-a4f2-signed.psbt written",
           actions_sel=None):
    """The end of a signing run. When actions_sel is given, the screen
    offers SIGN ANOTHER / POWER OFF instead of ending the session."""
    img, d = _frame(w, h)
    _status_circle(img, d, w, h, "SIGNED" if ok else "FAILED",
                   OCHRE if ok else RED)
    _fit(d, (w // 2, int(h * 0.68)), detail, int(h * 0.055), CREAM, "mm",
         int(w * 0.92))
    if actions_sel is not None:
        _actions(d, w, h, ["SIGN ANOTHER", "POWER OFF"], actions_sel)
    return img






def busy(w, h, message="working…", phase=0):
    """The wait frame: the brand mark, turning while Core works. phase
    advances the rotation; the dev harness renders phase 0 only, the
    device animates from a thread (main._busy)."""
    img, d = _frame(w, h)
    r, ss = int(h * 0.16), 4
    cx, cy = w // 2, int(h * 0.34)
    arc = Image.new("L", (2 * r * ss, 2 * r * ss), 0)
    start = (phase * 45) % 360
    ImageDraw.Draw(arc).arc([2 * ss, 2 * ss, 2 * r * ss - 2 * ss,
                             2 * r * ss - 2 * ss],
                            start, start + 270, fill=255, width=3 * ss)
    img.paste(OCHRE, (cx - r, cy - r),
              arc.resize((2 * r, 2 * r), Image.LANCZOS))
    _fit(d, (w // 2, int(h * 0.72)), message, int(h * 0.055), CREAM, "mm",
         int(w * 0.92))
    return img


# PLAN A-22: the pure signer accepts only what Core itself understands. The
# codex32 and seed-word modes moved to the lab branch with the code that
# transformed them; nothing here converts anything.
SEED_MENU_OPTIONS = [
    ("Scan descriptor QR", "pure Core"),
    ("Scan xprv QR", "pure Core"),
    ("Type descriptor", "pure Core"),
    ("Type xprv", "pure Core"),
]


CHANNEL_OPTIONS = [("Scan QR", "camera"), ("USB stick", "/mnt/usb")]


def channel_menu(w, h, selected=0):
    """Pick the channel a PSBT arrives on (Ben, 2026-09-04).

    It used to poll both at once behind one vague line, "insert stick or
    show QR". Neither channel then got a screen of its own, so the camera
    ran while you were fetching a stick and the scan had nowhere to show
    what it could see.
    """
    img, d = _frame(w, h, "LOAD  TRANSACTION")
    for i, (label, note) in enumerate(CHANNEL_OPTIONS):
        y = int(h * (0.36 + i * 0.20))
        if i == selected:
            d.rounded_rectangle([int(w * 0.06), y - int(h * 0.085),
                                 int(w * 0.94), y + int(h * 0.085)],
                                radius=6, outline=OCHRE, width=2)
        _fit(d, (int(w * 0.12), y), label, int(h * 0.065),
             CREAM if i == selected else GREY, "lm", int(w * 0.55))
        _fit(d, (int(w * 0.88), y), note, int(h * 0.042),
             OCHRE if i == selected else GREY, "rm", int(w * 0.28))
    return img


# The camera sits at 90 degrees to the panel on this build, and Ben chose to
# fill the screen rather than keep the edges of the view (hw/HARDWARE.md).
VIEWFINDER_ROTATE = 90
VIEWFINDER_FILL = True


def scanning(w, h, frame, message, progress=0.0):
    """Live camera view with a caption. THE viewfinder.

    Measured on the board, 2026-09-04: aiming with no view on screen got 1
    read in 120s; the same target with a viewfinder got 53 in 90s, and time
    to first decode fell from 35.3s to 8.3s. A scan screen that shows
    nothing is asking the operator to aim a lens they cannot see through.
    """
    if frame is None:
        return busy(w, h, message)
    img = Image.fromarray(frame, mode="L").convert("RGB")
    if VIEWFINDER_ROTATE:
        img = img.rotate(VIEWFINDER_ROTATE, expand=True)
    if VIEWFINDER_FILL:
        scale = max(w / img.width, h / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.NEAREST)
        left, top = (img.width - w) // 2, (img.height - h) // 2
        img = img.crop((left, top, left + w, top + h))
    else:
        img.thumbnail((w, h), Image.NEAREST)
        canvas = Image.new("RGB", (w, h), INK)
        canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
        img = canvas
    d = ImageDraw.Draw(img)
    bar = int(h * 0.13)
    d.rectangle([0, h - bar, w, h], fill=INK)
    _fit(d, (w // 2, h - bar // 2), message, int(h * 0.05), CREAM, "mm",
         int(w * 0.94))
    if progress > 0:
        # PsbtScan.progress is the UR decoder's own estimate, 0 to 1. A bar
        # the operator can act on: it says keep going, this is working.
        pct = max(0.0, min(progress, 1.0))
        d.rectangle([int(w * 0.05), 2, int(w * 0.95), int(h * 0.035)],
                    outline=GREY)
        d.rectangle([int(w * 0.05), 2,
                     int(w * 0.05) + int(w * 0.9 * pct), int(h * 0.035)],
                    fill=OCHRE)
        _fit(d, (w // 2, int(h * 0.075)), f"{pct * 100:.0f}%",
             int(h * 0.042), OCHRE, "mm", int(w * 0.5))
    return img


def seed_menu(w, h, selected=0):
    """Choose the key input mode. A-22: only forms Core understands."""
    img, d = _frame(w, h, "LOAD  KEY")
    options = SEED_MENU_OPTIONS
    # Rows are pitched to fit the panel rather than a fixed 0.115.
    top, bottom = 0.155, 0.94
    pitch = (bottom - top) / max(len(options) - 1, 1)
    for i, (label, note) in enumerate(options):
        y = int(h * (top + i * pitch))
        if i == selected:
            d.rounded_rectangle([int(w * 0.04), y - int(h * pitch * 0.46),
                                 int(w * 0.96), y + int(h * pitch * 0.46)],
                                radius=4, outline=OCHRE)
        _fit(d, (int(w * 0.08), y), label, int(h * 0.052),
             CREAM if i == selected else GREY, "lm", int(w * 0.60))
        _fit(d, (int(w * 0.92), y), note, int(h * 0.04),
             OCHRE if i == selected else GREY, "rm", int(w * 0.28))
    return img




GENERATE_LINES = [
    # Ben, 2026-09-04: "we don't need all the slop of what it's not."
    # Three statements, each about what this does and what you get. The
    # honest caveat stays, because it changes the decision; the list of
    # things Corky is not does not.
    # The ochre headline above already says the entropy is Core's, so a
    # body line repeating it is more slop.
    "Software entropy cannot be audited as it runs. "
    "Cards or dice remain the verifiable default.",
    "Your backup is Core's master xprv: 111 characters to transcribe.",
]

#: Body copy never shrinks below this. The screen scrolls, so a long line
#: wraps instead (Ben, 2026-09-04: "the font is too small to read on that,
#: we already can scroll down"). Shrinking to fit the width buys nothing
#: when height is free.
MIN_BODY = 0.068          # fraction of panel height (16px at 240)
GEN_VISIBLE = 5           # wrapped lines on screen at once; U/D scroll


def _generate_body(d, w, h):
    """GENERATE_LINES wrapped to the panel at the minimum readable size.

    A blank line between each source line (Ben, 2026-09-04). Wrapping turns
    every sentence into one or two lines, and without a gap the paragraphs
    run together into a wall the eye cannot break up.
    """
    out = []
    for line in GENERATE_LINES:
        if out:
            out.append("")
        out.extend(_wrap(d, line, int(h * MIN_BODY), int(w * 0.90)))
    return out


def generate_scroll_max(w, h):
    """How far the body can scroll. main.py must ask, because wrapping
    means the line count depends on the panel, not on GENERATE_LINES."""
    img = Image.new("RGB", (w, h))
    return max(0, len(_generate_body(ImageDraw.Draw(img), w, h)) - GEN_VISIBLE)


def generate_warning(w, h, selected=1, scroll=0):
    """Shown before Core-RNG generation (PLAN A-19). The body scrolls with
    U/D so the font stays readable; L/R toggle the action; more below is
    marked with a down chevron."""
    img, d = _frame(w, h, "GENERATE  A  KEY")
    _fit(d, (w // 2, int(h * 0.22)), "Entropy comes from Bitcoin Core.",
         int(h * 0.065), OCHRE, "mm", int(w * 0.94))
    body = _generate_body(d, w, h)
    last = min(scroll + GEN_VISIBLE, len(body))
    visible = body[scroll:last]
    size = int(h * MIN_BODY)
    font = _font(size)
    # Left-aligned: this is a paragraph, and centring every wrapped line
    # gives a ragged left edge the eye has to re-find on each line.
    for row, text in enumerate(visible):
        d.text((int(w * 0.06), int(h * (0.35 + row * 0.077))), text,
               font=font, fill=CREAM, anchor="lm")
    if last < len(body):
        cx, cy, r = w // 2, int(h * 0.77), int(h * 0.02)
        d.polygon([(cx - r, cy - r), (cx + r, cy - r), (cx, cy + r)],
                  fill=OCHRE)
    _actions(d, w, h, ["BACK", "GENERATE"], selected)
    return img


def keymaterial_warning(w, h, kind="descriptor", selected=1):
    """Shown before accepting an xprv or descriptor (A-14): the QR IS the
    wallet — no passphrase layer protects it."""
    img, d = _frame(w, h, f"SCAN  {kind.upper()}")
    d.text((w // 2, int(h * 0.30)), "This QR IS the wallet.",
           font=_font(int(h * 0.075)), fill=RED, anchor="mm")
    lines = ["There is no passphrase layer on a raw " + kind + ".",
             "Anyone holding this code holds the funds.",
             "Scan it in private."]
    _fit_block(d, lines,
               [(w // 2, int(h * (0.46 + i * 0.09))) for i in range(len(lines))],
               int(h * 0.05), CREAM, "mm", int(w * 0.94))
    _actions(d, w, h, ["BACK", "SCAN"], selected)
    return img




# ---- text and grid entry --------------------------------------------------

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))


# One alphabet per job. A single 64-cell set could not serve all three:
# base58 drops B, I, O and 0 (so an xprv needs its own), descriptors need
# brackets and a star, and a BIP39 passphrase is arbitrary text that may
# contain B, I, O or a space. Grids page when they do not fit 32 cells.
CELLS_PER_PAGE = 32          # 8 columns x 4 rows, above the action bar
BASE58 = ("123456789abcdefghijkmnopqrstuvwxyz"
          "ABCDEFGHJKLMNPQRSTUVWXYZ")                      # 58: no 0, O, I, l
DESCRIPTOR_CHARSET = BASE58 + "0()[]'/*#hl"                 # 70


# A-22: the passphrase charset went with the BIP39 passphrase prompt. An
# xprv and a descriptor are the only things typed on this device now.
CHARSETS = {"xprv": BASE58,
            "descriptor": DESCRIPTOR_CHARSET}


def charset_pages(name):
    """The charset for a job, split into screenfuls."""
    cs = CHARSETS[name]
    return [cs[i:i + CELLS_PER_PAGE]
            for i in range(0, len(cs), CELLS_PER_PAGE)]


def text_entry(w, h, title, text, cursor=0, charset="xprv", page=0,
               secret=False, actions_sel=1):
    """Text on a paged 8x4 grid: passphrases (S2) and typed xprv or
    descriptor strings (S3). `secret=True` masks the echo, since a
    passphrase is shoulder-surfable and does not checksum. `cursor` indexes
    the CURRENT page. The action bar is selectable, so CANCEL really
    cancels."""
    img, d = _frame(w, h, title)
    shown = ("*" * len(text)) if secret else text[-30:]
    _fit(d, (w // 2, int(h * 0.16)), (shown or "") + "_",
         int(h * 0.06), CREAM, "mm", int(w * 0.92))
    pages = charset_pages(charset)
    page = max(0, min(page, len(pages) - 1))
    cells = pages[page]
    if len(pages) > 1:
        _fit(d, (w // 2, int(h * 0.235)),
             f"page {page + 1}/{len(pages)}   L/R past the end turns the page",
             int(h * 0.038), GREY, "mm", int(w * 0.92))
    cell_w, cell_h = w // 9, int(h * 0.135)
    x0, y0 = (w - 8 * cell_w) // 2, int(h * 0.29)
    for i, ch in enumerate(cells):
        r, c = divmod(i, 8)
        gx = x0 + c * cell_w + cell_w // 2
        gy = y0 + r * cell_h + cell_h // 2
        if i == cursor:
            d.rounded_rectangle([gx - cell_w // 2 + 2, gy - cell_h // 2 + 2,
                                 gx + cell_w // 2 - 2, gy + cell_h // 2 - 2],
                                radius=4, outline=OCHRE)
        label = "space" if ch == " " else ch
        _fit(d, (gx, gy), label, int(h * 0.055),
             CREAM if i == cursor else GREY, "mm", cell_w - 2)
    _actions(d, w, h, ["CANCEL", "DONE"], actions_sel)
    return img














GROUPS_PER_ROW = 3          # 4-char groups across one line
ROWS_PER_PAGE = 4           # rows between the title and the footer note
CHARS_PER_PAGE = GROUPS_PER_ROW * ROWS_PER_PAGE * 4


def share_pages(text):
    """Split a backup string into screenfuls, in order, losing nothing.

    Core's
    master xprv is 111 characters; both are three screenfuls. Drawing them as
    one column ran the last third off the bottom of the panel, so the user was
    asked to transcribe characters that never rendered.
    """
    return [text[i:i + CHARS_PER_PAGE]
            for i in range(0, max(len(text), 1), CHARS_PER_PAGE)]








_LOGO_MASK = None


def _logo_mask(target_h):
    """The brand mark as a binary stencil scaled to target_h pixels tall.
    Nearest-neighbour keeps it strictly two-tone at any panel size."""
    global _LOGO_MASK
    if _LOGO_MASK is None:
        _LOGO_MASK = Image.open(
            Path(__file__).resolve().parent.parent
            / "art" / "bb-logo-mask.png").convert("L")
    target_w = round(target_h * _LOGO_MASK.width / _LOGO_MASK.height)
    return _LOGO_MASK.resize((target_w, target_h), Image.NEAREST)


def splash(w, h):
    """The first frame the device paints, before bitcoind is up.

    Two tones only (ink ground, cream mark) and every string measured, so it
    survives a 1-bit render and both panel sizes. The mark is the Bitcoin
    Butlers infinity-hourglass, stenciled from art/bb-logo-mask.png (a binary
    silhouette extracted from the brand logo's alpha channel).
    """
    img, d = _frame(w, h)
    cx = w // 2
    _fit(d, (cx, int(h * 0.30)), "BITCOIN BUTLERS",
         int(h * 0.075), OCHRE, "mm", int(w * 0.90))
    _fit(d, (cx, int(h * 0.42)), "presents",
         int(h * 0.05), GREY, "mm", int(w * 0.90))
    _fit(d, (cx, int(h * 0.62)), "CORKY", int(h * 0.15), CREAM, "mm",
         int(w * 0.92))
    return img

# ---- backup display -------------------------------------------------
# These were named codex32_* because codex32 shares were the first
# thing paged across the panel. They are generic: A-22 keeps them for
# Core's master xprv, which is the pure signer's only backup.


def backup_page(w, h,
                          share="MS12NAMEA320ZYXRPP5QSRJG",
                          index=1, total=3, page=0, pages=1):
    """One screenful of a backup string. `share` is already one page's worth
    (see share_pages); `page`/`pages` drive the position line."""
    title = f"SHARE  {index} / {total}  ·  WRITE  IT  DOWN"
    if pages > 1:
        title = f"SHARE  {index}/{total}  ·  PART  {page + 1}/{pages}"
    img, d = _frame(w, h, title)
    groups = [share[i:i + 4] for i in range(0, len(share), 4)]
    for row_start in range(0, len(groups), GROUPS_PER_ROW):
        y = int(h * (0.26 + (row_start // GROUPS_PER_ROW) * 0.13))
        _fit(d, (w // 2, y),
             "  ".join(groups[row_start:row_start + GROUPS_PER_ROW]),
             int(h * 0.075), CREAM, "mm", int(w * 0.92))
    if pages > 1:
        _fit(d, (w // 2, int(h * 0.79)),
             f"characters {page * CHARS_PER_PAGE + 1}"
             f"-{page * CHARS_PER_PAGE + len(share)} of this share",
             int(h * 0.045), OCHRE, "mm", int(w * 0.92))
    else:
        _fit(d, (w // 2, int(h * 0.79)),
             "paper you keep, not this device",
             int(h * 0.045), OCHRE, "mm", int(w * 0.92))
    _actions(d, w, h,
             ["ABORT" if page == 0 else "BACK",
              "NEXT" if page + 1 < pages else "VERIFY"], 1)
    return img

def verified(w, h, kind="ok"):
    """`kind` may carry newlines; each line is fitted separately."""
    img, d = _frame(w, h)
    _status_circle(img, d, w, h, "VALID", OCHRE)
    for i, line in enumerate(kind.split("\n")):
        _fit(d, (w // 2, int(h * (0.64 + i * 0.065))), line,
             int(h * 0.06), CREAM, "mm", int(w * 0.92))
    _actions(d, w, h, ["DONE"], 0)
    return img
