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
        d.text((w // 2, int(h * 0.06)), title, font=_font(int(h * 0.07)),
               fill=GREY, anchor="mm")
        d.line([(int(w * 0.06), int(h * 0.11)), (int(w * 0.94), int(h * 0.11))],
               fill=GREY, width=1)
    return img, d


# order: load key, key generation, tools, settings (Ben, 2026-09-01)
HOME_TILES = [("load key", "load"), ("key generation", "key"),
              ("tools", "tools"), ("settings", "gear")]


def home(w, h, selected=0):
    """SeedSigner-style 2x2 home: four tiles, each a Font Awesome icon and a
    title. Load key first, key generation second, tools, settings (which
    holds power off). No CORKY text. It is a KEY, not a wallet."""
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img)
    mx, my, gap = int(w * 0.06), int(h * 0.09), int(w * 0.04)
    bw = (w - 2 * mx - gap) // 2
    bh = (h - 2 * my - gap) // 2
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
    _fit(d, (w // 2, int(h * 0.52)), "Core's keys, nothing kept",
         int(h * 0.05), GREY, "mm", int(w * 0.9))
    _fit(d, (w // 2, int(h * 0.66)), "wallet brain: Bitcoin Core 31.1",
         int(h * 0.048), GREY, "mm", int(w * 0.9))
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


ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def seed_entry(w, h, word_index, total_words, prefix, candidates, grid_cur=0):
    """A-Z grid word entry (Ben, 2026-09-01): d-pad moves, A types the
    letter, the candidate list narrows, center-press picks the top word.
    Same grid model as codex32 entry; ~180 presses for a 24-word seed."""
    img, d = _frame(w, h, f"SEED  WORD  {word_index} / {total_words}")
    d.text((int(w * 0.06), int(h * 0.155)), (prefix or "").upper() + "_",
           font=_font(int(h * 0.075)), fill=CREAM, anchor="lm")
    # Candidates: the top one sits in a gold box (center-press takes it).
    cx = int(w * 0.60)
    for i, word in enumerate(candidates[:3]):
        y = int(h * (0.135 + i * 0.072))
        if i == 0:
            d.rounded_rectangle([cx - int(w * 0.02), y - int(h * 0.03),
                                 int(w * 0.97), y + int(h * 0.03)],
                                radius=4, outline=OCHRE)
        d.text((cx, y), word, font=_font(int(h * 0.05)),
               fill=CREAM if i == 0 else GREY, anchor="lm")
    # 8x4 letter grid.
    cell_w, cell_h = w // 9, int(h * 0.135)
    x0, y0 = (w - 8 * cell_w) // 2, int(h * 0.36)
    for i, ch in enumerate(ALPHABET):
        r, c = divmod(i, 8)
        gx = x0 + c * cell_w + cell_w // 2
        gy = y0 + r * cell_h + cell_h // 2
        if i == grid_cur:
            d.rounded_rectangle([gx - cell_w // 2 + 2, gy - cell_h // 2 + 2,
                                 gx + cell_w // 2 - 2, gy + cell_h // 2 - 2],
                                radius=4, outline=OCHRE)
        d.text((gx, gy), ch.upper(), font=_font(int(h * 0.06)),
               fill=CREAM if i == grid_cur else GREY, anchor="mm")
    d.text((w // 2, int(h * 0.955)), "center · pick word",
           font=_font(int(h * 0.04)), fill=GREY, anchor="mm")
    return img


def busy(w, h, message="checking words, deriving in Core…", phase=0):
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


SEED_MENU_OPTIONS = [
    ("Scan descriptor QR", "pure Core"),
    ("Scan xprv QR", "pure Core"),
    ("Type descriptor", "pure Core"),
    ("Type xprv", "pure Core"),
    ("Scan codex32", "BIP32-native"),
    ("Type codex32 share(s)", "BIP32-native"),
    ("Scan SeedQR", "words via Corky"),
    ("Type seed words", "words via Corky"),
]


def seed_menu(w, h, selected=0):
    """Choose the seed input mode (A-14's modes + SeedQR + codex32/A-18)."""
    img, d = _frame(w, h, "LOAD  KEY")
    options = SEED_MENU_OPTIONS
    # Eight modes now (typed xprv/descriptor joined the scanned ones), so
    # the rows are pitched to fit the panel rather than a fixed 0.115.
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


def tools_menu(w, h, selected=0):
    """Utilities: verify a share, back up a seed, generate one from Core.
    No sub-lines, no footer legend (Ben, 2026-09-01)."""
    img, d = _frame(w, h, "TOOLS")
    options = ["Verify a codex32 share", "Back up seed as codex32"]
    for i, label in enumerate(options):
        y = int(h * (0.30 + i * 0.18))
        if i == selected:
            d.rounded_rectangle([int(w * 0.04), y - int(h * 0.065),
                                 int(w * 0.96), y + int(h * 0.065)],
                                radius=4, outline=OCHRE)
        d.text((int(w * 0.08), y), label, font=_font(int(h * 0.058)),
               fill=CREAM if i == selected else GREY, anchor="lm")
    return img


GENERATE_LINES = [
    "Core's own RNG makes this key, not Corky and not a vendor.",
    "It is software. You cannot audit it as it runs.",
    "Cards or dice stay the verifiable option, and the default.",
    "Choose this if you trust Core's RNG more than any other.",
    "Core cannot make BIP39 words. Corky will not invent them.",
    "Your backup is a codex32 string, or k-of-n shares.",
]
GEN_VISIBLE = 4   # body lines on screen at once; U/D scroll the rest


def generate_warning(w, h, selected=1, scroll=0):
    """Shown before Core-RNG generation (PLAN A-19). The body scrolls with
    U/D so the font stays readable; L/R toggle the action; more below is
    marked with a down chevron."""
    img, d = _frame(w, h, "GENERATE  A  SEED")
    _fit(d, (w // 2, int(h * 0.22)), "Entropy comes from Bitcoin Core.",
         int(h * 0.065), OCHRE, "mm", int(w * 0.94))
    last = min(scroll + GEN_VISIBLE, len(GENERATE_LINES))
    for row, i in enumerate(range(scroll, last)):
        _fit(d, (w // 2, int(h * (0.36 + row * 0.10))), GENERATE_LINES[i],
             int(h * 0.05), CREAM, "mm", int(w * 0.94))
    if last < len(GENERATE_LINES):
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
    for i, line in enumerate(lines):
        _fit(d, (w // 2, int(h * (0.46 + i * 0.09))), line,
             int(h * 0.05), CREAM, "mm", int(w * 0.94))
    _actions(d, w, h, ["BACK", "SCAN"], selected)
    return img


def seed_length(w, h, selected=0):
    img, d = _frame(w, h, "SEED  LENGTH")
    for i, label in enumerate(["12 words", "24 words"]):
        y = int(h * (0.35 + i * 0.18))
        if i == selected:
            d.rounded_rectangle([int(w * 0.30), y - int(h * 0.07),
                         int(w * 0.70), y + int(h * 0.07)], radius=4, outline=OCHRE)
        d.text((w // 2, y), label, font=_font(int(h * 0.08)),
               fill=CREAM if i == selected else GREY, anchor="mm")
    return img


# ---- codex32 (BIP93) screens — v1.1, map ticket #5 -------------------------

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from codex32 import CHARSET as BECH32_CHARSET  # single source of truth


TEXT_CHARSET = ("abcdefghijklmnopqrstuvwxyz0123456789"
                "ACDEFGHJKLMNPQRSTUVWXYZ/'[]#")   # 64 cells, 8x8


def text_entry(w, h, title, text, cursor=0, hint="", secret=False):
    """Free text on an 8x8 grid: passphrases (S2) and typed xprv or
    descriptor strings (S3). `secret=True` masks the echo, since a
    passphrase is shoulder-surfable and does not checksum."""
    img, d = _frame(w, h, title)
    shown = ("*" * len(text)) if secret else text[-28:]
    _fit(d, (w // 2, int(h * 0.15)), (shown or "") + "_",
         int(h * 0.06), CREAM, "mm", int(w * 0.92))
    if hint:
        _fit(d, (w // 2, int(h * 0.225)), hint, int(h * 0.04), GREY, "mm",
             int(w * 0.92))
    # 8 rows must clear the action bar at 0.93h, so the pitch is tight.
    cell_w, cell_h = w // 9, int(h * 0.074)
    x0, y0 = (w - 8 * cell_w) // 2, int(h * 0.265)
    for i, ch in enumerate(TEXT_CHARSET):
        r, c = divmod(i, 8)
        gx = x0 + c * cell_w + cell_w // 2
        gy = y0 + r * cell_h + cell_h // 2
        if i == cursor:
            d.rounded_rectangle([gx - cell_w // 2 + 2, gy - cell_h // 2 + 2,
                                 gx + cell_w // 2 - 2, gy + cell_h // 2 - 2],
                                radius=4, outline=OCHRE)
        d.text((gx, gy), ch, font=_font(int(h * 0.05)),
               fill=CREAM if i == cursor else GREY, anchor="mm")
    _actions(d, w, h, ["CANCEL", "DONE"], 1)
    return img


def passphrase_prompt(w, h, selected=0):
    """BIP39 passphrase is optional and changes the wallet completely."""
    img, d = _frame(w, h, "PASSPHRASE")
    _fit(d, (w // 2, int(h * 0.30)), "Add a BIP39 passphrase?",
         int(h * 0.065), OCHRE, "mm", int(w * 0.94))
    for i, line in enumerate([
            "A passphrase makes a different wallet.",
            "The same words with no passphrase open",
            "a different one. Nothing checks it."]):
        _fit(d, (w // 2, int(h * (0.44 + i * 0.075))), line,
             int(h * 0.045), CREAM, "mm", int(w * 0.94))
    _actions(d, w, h, ["NO", "YES"], selected)
    return img


def codex32_scan(w, h):
    img, d = _frame(w, h, "SCAN  CODEX32  SHARE")
    d.rectangle([w // 2 - int(h * 0.18), int(h * 0.22),
                 w // 2 + int(h * 0.18), int(h * 0.22) + int(h * 0.36)],
                outline=GREY)
    d.text((w // 2, int(h * 0.40)), "QR", font=_font(int(h * 0.09)),
           fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.66)), "Codex32QR/v1-48 · 128-bit shares",
           font=_font(int(h * 0.05)), fill=OCHRE, anchor="mm")
    d.text((w // 2, int(h * 0.74)), "256-bit shares: type them instead",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    _actions(d, w, h, ["BACK", "TYPE INSTEAD"], 1)
    return img


def codex32_entry(w, h, entered="MS12NAMEA320ZYXRPP", cursor=14, caret=None):
    """bech32 charset as a 4x8 grid; d-pad moves, A writes at the caret.
    The echo shows a window of the string around the caret (the character
    being written or edited), highlighted, so a long share still shows the
    part you are working on. No legend: the grid is the instruction."""
    img, d = _frame(w, h, "TYPE  SHARE")
    if caret is None:
        caret = len(entered)
    # A 16-char window that keeps the caret in view on a long share.
    start = max(0, min(caret - 8, len(entered) - 16))
    end = min(start + 16, len(entered))
    size = int(h * 0.07)
    xs = w // 2 - (end - start) * int(w * 0.028)
    for i in range(start, end + 1):
        ch = entered[i] if i < len(entered) else "_"
        edit = i == caret
        _fit(d, (xs, int(h * 0.17)), ch.upper(), size,
             OCHRE if edit else CREAM, "mm", int(w * 0.06))
        xs += int(w * 0.056)
    d.text((w // 2, int(h * 0.255)),
           f"{len(entered)} chars · pos {caret - 2}",
           font=_font(int(h * 0.04)), fill=GREY, anchor="mm")
    cell_w, cell_h = w // 9, int(h * 0.13)
    x0, y0 = (w - 8 * cell_w) // 2, int(h * 0.34)
    for i, ch in enumerate(BECH32_CHARSET):
        r, c = divmod(i, 8)
        cx = x0 + c * cell_w + cell_w // 2
        cy = y0 + r * cell_h + cell_h // 2
        if i == cursor:
            d.rounded_rectangle([cx - cell_w // 2 + 2, cy - cell_h // 2 + 2,
                         cx + cell_w // 2 - 2, cy + cell_h // 2 - 2],
                        radius=4, outline=OCHRE)
        d.text((cx, cy), ch.upper(), font=_font(int(h * 0.06)),
               fill=CREAM if i == cursor else GREY, anchor="mm")
    return img


def codex32_shares(w, h, have_ids=("A", "C"), k=3):
    img, d = _frame(w, h, "COLLECT  SHARES")
    d.text((w // 2, int(h * 0.30)), f"{len(have_ids)} of {k}",
           font=_font(int(h * 0.14)), fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.48)),
           "held: " + "  ".join(have_ids),
           font=_font(int(h * 0.06)), fill=OCHRE, anchor="mm")
    d.text((w // 2, int(h * 0.62)), "each share checksums on entry;",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.69)), "duplicates are refused",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    _actions(d, w, h, ["ABORT", "ADD SHARE"], 1)
    return img


def codex32_error(w, h, detail="checksum failed at position 31"):
    img, d = _frame(w, h)
    _status_circle(img, d, w, h, "INVALID", RED)
    _fit(d, (w // 2, int(h * 0.64)), detail, int(h * 0.055), CREAM, "mm",
         int(w * 0.92))
    d.text((w // 2, int(h * 0.72)), "detection only: this device never",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.78)), "guesses corrections to key material",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    _actions(d, w, h, ["BACK", "RE-ENTER"], 1)
    return img


def codex32_split_choice(w, h, selected=0):
    img, d = _frame(w, h, "BACKUP  AS  CODEX32")
    options = [("One string", "whole seed, one line"),
               ("Split k-of-n", "2-of-3 · shares to guardians")]
    for i, (label, note) in enumerate(options):
        y = int(h * (0.28 + i * 0.17))
        if i == selected:
            d.rounded_rectangle([int(w * 0.06), y - int(h * 0.07),
                         int(w * 0.94), y + int(h * 0.07)], radius=4, outline=OCHRE)
        d.text((int(w * 0.10), y), label, font=_font(int(h * 0.065)),
               fill=CREAM if i == selected else GREY, anchor="lm")
        d.text((int(w * 0.90), y), note, font=_font(int(h * 0.045)),
               fill=OCHRE if i == selected else GREY, anchor="rm")
    return img


GROUPS_PER_ROW = 3          # 4-char groups across one line
ROWS_PER_PAGE = 4           # rows between the title and the footer note
CHARS_PER_PAGE = GROUPS_PER_ROW * ROWS_PER_PAGE * 4


def share_pages(text):
    """Split a backup string into screenfuls, in order, losing nothing.

    A 64-byte BIP39 seed encodes to a 127-character codex32 secret and Core's
    master xprv is 111 characters; both are three screenfuls. Drawing them as
    one column ran the last third off the bottom of the panel, so the user was
    asked to transcribe characters that never rendered.
    """
    return [text[i:i + CHARS_PER_PAGE]
            for i in range(0, max(len(text), 1), CHARS_PER_PAGE)]


def codex32_share_display(w, h,
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
             "the codex32 kit worksheets own paper",
             int(h * 0.045), OCHRE, "mm", int(w * 0.92))
    _actions(d, w, h,
             ["ABORT" if page == 0 else "BACK",
              "NEXT" if page + 1 < pages else "VERIFY"], 1)
    return img


def address_lines(address, per_line=22):
    """An address broken across lines that fit the panel. Returned as one
    string with newlines so callers stay simple."""
    return "\n".join(address[i:i + per_line]
                      for i in range(0, len(address), per_line))


def codex32_verified(w, h, kind="share 2 of 3"):
    """`kind` may carry newlines (see address_lines); each line is fitted."""
    img, d = _frame(w, h)
    _status_circle(img, d, w, h, "VALID", OCHRE)
    for i, line in enumerate(kind.split("\n")):
        _fit(d, (w // 2, int(h * (0.64 + i * 0.065))), line,
             int(h * 0.06), CREAM, "mm", int(w * 0.92))
    _actions(d, w, h, ["DONE"], 0)
    return img


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
