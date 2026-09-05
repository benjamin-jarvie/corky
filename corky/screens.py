"""Corky's screens as pure PIL renders.

Resolution-independent: every screen takes (width, height) and lays out from
proportions, so the same code drives the primary 2.8" ST7789 (320x240) and the
1.3" ST7789 (240x240). On-device, frames go to the vendored drivers'
show_image(); on a dev machine they save as PNGs for review (see
tools/render_screens.py).

Palette follows the Corky/Kawanatanga artefact palette: ink ground, cream
text, Te Peeke red for the one number that matters on each screen.
"""

import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signer  # noqa: E402 - needs the path above

INK = "#1A1714"
CREAM = "#F5EFE0"
RED = "#9E2B25"
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
        "gear": "\uf013", "power": "\uf011", "about": "\uf05a",
        "qrcode": "\uf029"}


def _icon(d, cx, cy, size, name, col):
    d.text((cx, cy), ICON[name], font=_iconfont(size), fill=col, anchor="mm")


def _fit(d, xy, text, size, fill, anchor, maxw):
    """Draw text at `size`, shrinking until it fits `maxw`.

    The panel has no scrollbar: a string wider than the canvas is simply not
    there. Every screen that renders content it did not choose itself (an
    address, an error string, a wrapped warning) goes through here, so a
    longer string degrades in size instead of vanishing off the edge. If the
    floor size still overflows, the tail is cut to a visible ellipsis; backup
    key material never reaches that path (text_pages sizes each page, and
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
    for text, xy in zip(lines, xs, strict=True):
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
    for i, (t, bw) in enumerate(zip(labels, widths, strict=True)):
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


# SeedSigner's four: Scan, Seeds, Tools, Settings (Ben, 2026-09-04, map
# e2e-before-testers ticket 02). Key generation lives under Tools, where
# SeedSigner keeps "New seed".
# Tiles are jobs, not devices (Ben, 2026-09-05). The camera is a means:
# Sign uses it for a transaction, Keys for a key, Tools to check an
# address. Naming the first tile after the camera made it the place
# everything happened, and then no word fitted it.
HOME_TILES = [("sign", "qrcode"), ("keys", "key"),
              ("tools", "tools"), ("settings", "gear")]


def home(w, h, selected=0, xfp=None):
    """SeedSigner-style 2x2 home: four tiles, each a Font Awesome icon and a
    title. Scan, Key, Tools, Settings (which holds power off). No CORKY
    text. It is a KEY, not a wallet.

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
    return _menu(w, h, "SETTINGS",
                 [(label, "", "normal") for label in SETTINGS_OPTIONS],
                 selected, icons=["power", "about"])


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


def review(w, h, outputs, fee_btc, input_total_btc=None,
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


CHANNEL_OPTIONS = [("Scan QR", "camera"), ("USB stick", "/mnt/usb")]


def channel_menu(w, h, selected=0):
    """Pick the channel a PSBT arrives on (Ben, 2026-09-04).

    It used to poll both at once behind one vague line, "insert stick or
    show QR". Neither channel then got a screen of its own, so the camera
    ran while you were fetching a stick and the scan had nowhere to show
    what it could see.
    """
    return _menu(w, h, "LOAD  TRANSACTION",
                 [(label, note, "normal") for label, note in CHANNEL_OPTIONS],
                 selected)


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


# Every list screen puts the top of its first row here, whatever it holds
# (Ben, 2026-09-05, from the board). The divider under the title sits at
# 0.11, and the old geometry put a four-row selection box at 0.063, so the
# highlight drew straight through the title and the line under it. Two
# menus had their own geometry as well and started at 0.34 and 0.36, so
# every menu began at a different height.
MENU_TOP = 0.16          # top edge of the first row's box, on every menu
MENU_BOTTOM = 0.95       # bottom edge the last row may not pass
MENU_PITCH = 0.135       # one row's height, fixed, so two rows sit together
MENU_ROWS = 6            # rows on screen at once; a longer list scrolls


def _menu(w, h, title, rows, selected, icons=None):
    """One list screen for every menu: rows of (label, note, tone), tone
    "normal" or "red". `icons` optionally names one glyph per row.

    Rows have a FIXED height and start at MENU_TOP, so a two-row menu sits
    together at the top instead of being flung to the corners of the panel
    (Ben, on the board, 2026-09-05: "new key sits nicely below but then
    check for leaks is a long way below"). A list longer than MENU_ROWS
    scrolls with the cursor, and a bar on the right says where you are.
    """
    img, d = _frame(w, h, title)
    n = max(len(rows), 1)
    # The rows ON SCREEN set the pitch, not the length of the whole list.
    # Using n crammed a 34-row report into the top 70 pixels.
    pitch = min(MENU_PITCH, (MENU_BOTTOM - MENU_TOP) / min(n, MENU_ROWS))
    first_top = int(h * MENU_TOP)
    box_h = int(pitch * 0.82 * h)
    # The window follows the cursor and never moves further than it must.
    start = 0
    if n > MENU_ROWS:
        start = max(0, min(selected - MENU_ROWS + 2, n - MENU_ROWS))
        start = max(0, min(start, selected)) if selected >= 0 else 0
    visible = rows[start:start + MENU_ROWS]
    for i, (label, note, tone) in enumerate(visible):
        box_top = first_top + int(i * pitch * h)
        y = box_top + box_h // 2
        active = (start + i) == selected
        if active:
            d.rounded_rectangle([int(w * 0.04), box_top,
                                 int(w * 0.96), box_top + box_h],
                                radius=4, outline=OCHRE)
        # Three tones. "red" paints the LABEL, for an action that destroys
        # something. "leak" paints the STATE on the right, because there the
        # thing is innocent and what it is doing is the alarm (Ben,
        # 2026-09-05). Both columns are the same size: the right one was
        # smaller and unreadable on the panel.
        colour = CREAM if active else GREY
        note_colour = OCHRE if active else GREY
        if tone == "red":
            colour = RED if not active else "#D9433B"
        elif tone == "leak":
            note_colour = "#D9433B" if active else RED
        x = int(w * 0.08)
        if icons:
            _icon(d, int(w * 0.11), y, int(h * 0.055), icons[start + i], colour)
            x = int(w * 0.20)
        size = int(h * 0.052)
        _fit(d, (x, y), label, size, colour, "lm",
             int(w * 0.52) - (x - int(w * 0.08)))
        _fit(d, (int(w * 0.92), y), note, size, note_colour, "rm",
             int(w * 0.36))
    if n > MENU_ROWS:
        # Where you are in the list, on the right edge, like any scrollbar.
        track_top, track_h = first_top, int(MENU_ROWS * pitch * h)
        bar_h = max(int(track_h * MENU_ROWS / n), 6)
        bar_y = track_top + int(track_h * start / n)
        d.rectangle([w - 4, track_top, w - 3, track_top + track_h], fill="#3A352E")
        d.rectangle([w - 5, bar_y, w - 2, bar_y + bar_h], fill=OCHRE)
    return img


# SeedSigner's per-seed menu, in Core's words (ticket 07).
# Four things that belong to a key. Sign transaction left on 2026-09-05:
# the Sign tile does it, from the camera or a stick, and a second door to
# the same room only made you choose which door.
KEY_MENU_OPTIONS = [
    ("Export public key", "for a coordinator"),
    ("Receiving addresses", "Core derives"),
    ("Backup key", "paper or file"),
    ("Discard key", "Core forgets it"),
]

TOOLS_OPTIONS = [("Check for leaks", ""),
                 ("Check an address", "")]


def leak_report(w, h, rows, cursor=0):
    """What image/leak-check.sh found, one thing and its state per row.

    The device may be the only place this can be read: a hardened board has
    no SSH. Leaks come first, because they are what you opened this for.
    It is the same list screen as every other menu, so the d-pad scrolls it
    and A, B or C leaves, and there is no action bar inventing a second way
    to do the same thing (Ben, 2026-09-05).
    """
    leaks = sum(1 for _label, _state, tone in rows if tone == "leak")
    title = "LEAK  CHECK"
    if rows:
        title = (f"LEAK  CHECK  ·  {leaks} OF {len(rows)}" if leaks
                 else f"LEAK  CHECK  ·  ALL {len(rows)} CLEAR")
    return _menu(w, h, title, rows, cursor)


# What the KEYS screen offers below the loaded keys, flat (Ben,
# 2026-09-05: "so we don't have to nest"). New key first, then every way
# to bring an existing one in. The LOAD A KEY screen it replaces held four
# rows, and one of them was always the one you wanted.
# No notes. Each row is a plain thing you can do, and a three-word note
# beside it either repeated the row or tried to explain a screen that
# explains itself properly a press later (Ben, 2026-09-05).
#
# Type descriptor is gone: a descriptor lives as a printed QR, not as
# words on steel, so Scan a key covers it, and typing 111 characters on a
# five-way pad to avoid holding up a card is not a trade anyone makes.
# Type xprv stays because it is the only way back from a paper backup.
KEYS_ACTIONS = [
    ("New key", ""),
    ("Scan a key", ""),
    ("Type xprv", ""),
    ("Restore from file", ""),
]


def keys_menu(w, h, keys, selected=0):
    """The loaded keys by fingerprint, then what you can do about keys.

    One screen, one title, whether or not a key is loaded. It used to jump
    straight past this into a differently titled LOAD A KEY when the device
    held nothing, so the same button gave you two different screens.
    `keys` are (wallet name, fingerprint) pairs in slot order.
    """
    rows = [((xfp or "????????").upper(), "loaded", "normal")
            for _n, xfp in keys]
    rows += [(label, note, "normal") for label, note in KEYS_ACTIONS]
    return _menu(w, h, "KEYS", rows, selected)


def key_menu(w, h, xfp, selected=0):
    """What one key can do. The title names it by fingerprint."""
    rows = [(label, note, "red" if label == "Discard key" else "normal")
            for label, note in KEY_MENU_OPTIONS]
    return _menu(w, h, f"KEY  {(xfp or '').upper()}", rows, selected)


def tools_menu(w, h, selected=0):
    return _menu(w, h, "TOOLS",
                 [(label, note, "normal") for label, note in TOOLS_OPTIONS],
                 selected)


# Where a public key can go (ticket 06). All five are listed; the three
# phones are marked untested until ticket 22 proves them on a real handset.
# The third field is the script types that target can read: Bull Bitcoin's
# parser throws on 86h, so it is offered native segwit only (ticket 21).
EXPORT_TARGETS = [
    ("Sparrow", "descriptor QR", ("wpkh", "tr")),
    ("Bitcoin Core", "wallet file", ()),
    ("BlueWallet", "untested", ("wpkh", "tr")),
    ("Green", "untested", ("wpkh", "tr")),
    ("Bull Bitcoin", "untested, segwit", ("wpkh",)),
]

SCRIPT_LABELS = {"wpkh": "Native segwit", "tr": "Taproot"}


def export_menu(w, h, selected=0):
    """Which coordinator is going to read this, as SeedSigner asks."""
    return _menu(w, h, "EXPORT  TO",
                 [(name, note, "normal") for name, note, _k in EXPORT_TARGETS],
                 selected)


def export_script_menu(w, h, kinds, selected=0):
    return _menu(w, h, "SCRIPT  TYPE",
                 [(SCRIPT_LABELS[k], "BIP84" if k == "wpkh" else "BIP86",
                   "normal") for k in kinds],
                 selected)


def _groups(text):
    return [text[i:i + 4] for i in range(0, len(text), 4)]


ADDR_GROUPS_PER_ROW = 4


def address_page(w, h, index, address, kind):
    """One receive address, in full, for comparison against a coordinator.

    Ben's rule: never truncate, group in fours, colour the first and last
    group differently from the middle. The middle keeps the same size and
    weight, and the footer asks for every group, because matching only the
    ends is the shortcut address-replacement malware relies on.
    """
    img, d = _frame(w, h, f"RECEIVE  {index}  ·  {SCRIPT_LABELS[kind].upper()}")
    groups = _groups(address)
    rows = [groups[i:i + ADDR_GROUPS_PER_ROW]
            for i in range(0, len(groups), ADDR_GROUPS_PER_ROW)]
    size = int(h * 0.075)
    top = 0.26 if len(rows) <= 3 else 0.22
    step = 0.13 if len(rows) <= 3 else 0.105
    # One row is measured whole, then drawn group by group at that spacing,
    # so the first and last group carry their colour IN PLACE. Colouring
    # them anywhere else would not help the eye track the comparison.
    widest = max(len(" ".join(r)) for r in rows)
    while size > int(h * 0.03):
        if d.textlength("W" * widest, font=_font(size)) <= int(w * 0.92):
            break
        size -= 1
    font = _font(size)
    space = d.textlength(" ", font=font)
    for r, row in enumerate(rows):
        y = int(h * (top + r * step))
        line_w = d.textlength(" ".join(row), font=font)
        x = (w - line_w) / 2
        for g, group in enumerate(row):
            first = r == 0 and g == 0
            last = r == len(rows) - 1 and g == len(row) - 1
            d.text((x, y), group, font=font,
                   fill=OCHRE if (first or last) else CREAM, anchor="lm")
            x += d.textlength(group, font=font) + space
    _fit(d, (w // 2, int(h * 0.90)), "compare every group", int(h * 0.045),
         GREY, "mm", int(w * 0.6))
    return img


def export_text(w, h, chunk, page=0, pages=1, title="PUBLIC  KEY"):
    """One screenful of the descriptor, in four-character groups, for
    someone typing it into a coordinator by hand. Public: no blanking."""
    head = title if pages == 1 else f"{title}  ·  PART  {page + 1}/{pages}"
    img, d = _frame(w, h, head)
    groups = _groups(chunk)
    for row_start in range(0, len(groups), GROUPS_PER_ROW):
        y = int(h * (0.26 + (row_start // GROUPS_PER_ROW) * 0.13))
        _fit(d, (w // 2, y),
             "  ".join(groups[row_start:row_start + GROUPS_PER_ROW]),
             int(h * 0.075), CREAM, "mm", int(w * 0.92))
    _actions(d, w, h, ["BACK", "NEXT" if page + 1 < pages else "DONE"], 1)
    return img


# Read from signer so the screen and the writer cannot drift apart.
BACKUP_PREFIX = signer.BACKUP_PREFIX
BACKUP_SUFFIX = signer.BACKUP_SUFFIX

BACKUP_OPTIONS = [
    ("On paper", "the master xprv"),
    ("To a file", "encrypted by Core"),
]


def backup_menu(w, h, selected=0):
    """Two backups, and they are not alternatives. The paper one is the key
    itself; the file one is what another computer running Core restores."""
    return _menu(w, h, "BACKUP  KEY",
                 [(label, note, "normal") for label, note in BACKUP_OPTIONS],
                 selected)


def fingerprint_of_backup(filename):
    """The key a backup file holds, by the fingerprint in its name. One
    place, so the screen and signer.BACKUP_SUFFIX cannot drift apart."""
    stem = filename[:-len(BACKUP_SUFFIX)] if filename.endswith(BACKUP_SUFFIX) \
        else filename
    return stem[len(BACKUP_PREFIX):] if stem.startswith(BACKUP_PREFIX) else stem


def restore_menu(w, h, names, selected=0):
    """The backup files found on the medium, by the fingerprint in the
    name, so the user picks a key rather than a filename."""
    rows = [(fingerprint_of_backup(n).upper(), "Core backup", "normal")
            for n in names]
    return _menu(w, h, "RESTORE  A  KEY", rows or [("none found", "", "normal")],
                 selected)


# CONTEXT.md calls these channels: how bytes cross the air gap. QR is the
# third; only the two file channels can carry a file.
FILE_CHANNELS = {"stick": ("USB stick", "/mnt/usb"),
                 "card": ("boot card", "/boot/firmware")}


def choose_channel(w, h, channels, selected=0):
    """Which file channel a file goes to. Asked every time (ticket 04)."""
    return _menu(w, h, "WRITE  IT  WHERE",
                 [(FILE_CHANNELS[c][0], FILE_CHANNELS[c][1], "normal")
                  for c in channels], selected)


def confirm_discard(w, h, xfp, selected=0):
    """Discard asks first. BACK is pre-selected; DISCARD must be chosen."""
    img, d = _frame(w, h, "DISCARD  KEY")
    _fit(d, (w // 2, int(h * 0.32)), (xfp or "").upper(), int(h * 0.11),
         CREAM, "mm", int(w * 0.9))
    _fit_block(d, ["Core forgets this key now.",
                   "Your backup is the only copy."],
               [(w // 2, int(h * 0.55)), (w // 2, int(h * 0.65))],
               int(h * 0.05), GREY, "mm", int(w * 0.92))
    _actions(d, w, h, ["BACK", "DISCARD"], selected)
    return img




def choose_key(w, h, keys, owners, selected=0):
    """Which key signs (map e2e-before-testers, ticket 03). Shown only when
    more than one key is loaded. `keys` are (wallet name, fingerprint)
    pairs in slot order; `owners` are the fingerprints Core found on the
    transaction's inputs. The owner is pre-selected by the caller; a key
    that owns nothing is greyed, because Core will not complete it."""
    img, d = _frame(w, h, "WHICH  KEY")
    top, bottom = 0.18, 0.80
    pitch = (bottom - top) / max(len(keys) - 1, 1)
    for i, (_name, xfp) in enumerate(keys):
        y = int(h * (top + i * pitch))
        owns = xfp in owners
        if i == selected:
            d.rounded_rectangle([int(w * 0.04), y - int(h * min(pitch, 0.2) * 0.46),
                                 int(w * 0.96), y + int(h * min(pitch, 0.2) * 0.46)],
                                radius=4, outline=OCHRE)
        _fit(d, (int(w * 0.08), y), (xfp or "????????").upper(), int(h * 0.065),
             CREAM if owns else GREY, "lm", int(w * 0.50))
        _fit(d, (int(w * 0.92), y), "owns the inputs" if owns else "not this one",
             int(h * 0.04), OCHRE if owns else GREY, "rm", int(w * 0.38))
    _actions(d, w, h, ["BACK", "SIGN WITH IT"], 1)
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
# A passphrase is the user's own string, so the grid must be able to type
# anything a person would pick. 84 characters, three pages of 32.
PASSPHRASE_CHARSET = ("abcdefghijklmnopqrstuvwxyz"
                      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                      "0123456789"
                      " .,-_!?@#$%&*+=/:;()")

CHARSETS = {"xprv": BASE58,
            "descriptor": DESCRIPTOR_CHARSET,
            "passphrase": PASSPHRASE_CHARSET}


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


def text_pages(text):
    """Split a backup string into screenfuls, in order, losing nothing.

    Core's
    master xprv is 111 characters; both are three screenfuls. Drawing them as
    one column ran the last third off the bottom of the panel, so the user was
    asked to transcribe characters that never rendered.
    """
    return [text[i:i + CHARS_PER_PAGE]
            for i in range(0, max(len(text), 1), CHARS_PER_PAGE)]








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


def backup_page(w, h, chunk, label, page=0, pages=1):
    """One screenful of the key, on its way to paper.

    `chunk` is already one page's worth (see text_pages). `label` names the
    key, "KEY  D2B7E45C", so the paper says which key it opens.
    """
    title = f"{label}  ·  WRITE  IT  DOWN"
    if pages > 1:
        title = f"{label}  ·  PART  {page + 1}/{pages}"
    img, d = _frame(w, h, title)
    groups = _groups(chunk)
    for row_start in range(0, len(groups), GROUPS_PER_ROW):
        y = int(h * (0.26 + (row_start // GROUPS_PER_ROW) * 0.13))
        _fit(d, (w // 2, y),
             "  ".join(groups[row_start:row_start + GROUPS_PER_ROW]),
             int(h * 0.075), CREAM, "mm", int(w * 0.92))
    if pages > 1:
        _fit(d, (w // 2, int(h * 0.79)),
             f"characters {page * CHARS_PER_PAGE + 1}"
             f"-{page * CHARS_PER_PAGE + len(chunk)} of the key",
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
