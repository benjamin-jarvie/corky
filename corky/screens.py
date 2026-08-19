"""Corky's screens as pure PIL renders.

Resolution-independent: every screen takes (width, height) and lays out from
proportions, so the same code drives the 2.4" ILI9341 (320x240) and the 1.3"
ST7789 (240x240). On-device, frames go to the vendored drivers' show_image();
on a dev machine they save as PNGs for review (see tools/render_screens.py).

Palette follows the Corky/Kawanatanga artefact palette: ink ground, cream
text, Te Peeke red for the one number that matters on each screen.
"""

from PIL import Image, ImageDraw, ImageFont

INK = "#1A1714"
CREAM = "#F5EFE0"
RED = "#9E2B25"
GREEN = "#2E4A3B"
GREY = "#B8B2A6"
OCHRE = "#C8912F"


def _font(size):
    return ImageFont.load_default(size=size)


def _frame(w, h, title=None):
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img)
    if title:
        d.text((w // 2, int(h * 0.06)), title, font=_font(int(h * 0.07)),
               fill=GREY, anchor="mm")
        d.line([(int(w * 0.06), int(h * 0.11)), (int(w * 0.94), int(h * 0.11))],
               fill=GREY, width=1)
    return img, d


def home(w, h, version="v0"):
    img, d = _frame(w, h)
    d.text((w // 2, int(h * 0.22)), "CORKY", font=_font(int(h * 0.16)),
           fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.34)), "Core's keys, nothing kept",
           font=_font(int(h * 0.06)), fill=GREY, anchor="mm")
    for i, line in enumerate(
            ["1 · open a wallet (words, SeedQR, xprv, descriptor)",
             "2 · load a PSBT (QR or USB stick)",
             "3 · review, sign, hand it back"]):
        y = int(h * (0.50 + i * 0.12))
        d.text((int(w * 0.08), y), line, font=_font(int(h * 0.055)),
               fill=CREAM, anchor="lm")
    d.text((w // 2, int(h * 0.88)), "A · begin        C · nothing to do",
           font=_font(int(h * 0.05)), fill=OCHRE, anchor="mm")
    d.text((w // 2, int(h * 0.95)), f"bitcoind ready · session RAM-only · {version}",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def review(w, h, outputs, fee_btc, input_count, input_total_btc=None, warn=True, page=0):
    """The screen that matters. outputs: [(address, amount_btc), ...]"""
    pages = max(1, (len(outputs) + 2) // 3)
    title = ("REVIEW  TRANSACTION" if pages == 1
             else f"REVIEW  ·  OUTPUTS {page + 1}/{pages}")
    img, d = _frame(w, h, title)
    y = int(h * 0.18)
    for addr, amt in outputs[page * 3:page * 3 + 3]:
        short = addr[:14] + "…" + addr[-6:] if len(addr) > 24 else addr
        d.text((int(w * 0.06), y), short, font=_font(int(h * 0.058)),
               fill=CREAM, anchor="lm")
        d.text((int(w * 0.94), y + int(h * 0.065)), f"{amt:.8f} BTC",
               font=_font(int(h * 0.065)), fill=CREAM, anchor="rm")
        y += int(h * 0.155)
    if pages > 1:
        d.text((int(w * 0.06), y), "UP/DOWN · more outputs",
               font=_font(int(h * 0.05)), fill=OCHRE, anchor="lm")
        y += int(h * 0.09)
    d.line([(int(w * 0.06), y), (int(w * 0.94), y)], fill=GREY, width=1)
    total = (f"in {input_total_btc:.8f}" if input_total_btc is not None
             else f"{input_count} inputs")
    d.text((int(w * 0.06), y + int(h * 0.07)), f"FEE  ({total})",
           font=_font(int(h * 0.055)), fill=GREY, anchor="lm")
    d.text((int(w * 0.94), y + int(h * 0.07)), f"{fee_btc:.8f} BTC",
           font=_font(int(h * 0.075)), fill=RED, anchor="rm")
    if warn:
        d.text((w // 2, int(h * 0.90)),
               "fee per coordinator's input amounts",
               font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((int(w * 0.06), int(h * 0.97)), "KEY3 · reject",
           font=_font(int(h * 0.05)), fill=GREY, anchor="lm")
    d.text((int(w * 0.94), int(h * 0.97)), "KEY1 · SIGN",
           font=_font(int(h * 0.05)), fill=CREAM, anchor="rm")
    return img


def result(w, h, ok=True, detail="tx-a4f2-signed.psbt written"):
    img, d = _frame(w, h)
    d.ellipse([w // 2 - int(h * 0.14), int(h * 0.22), w // 2 + int(h * 0.14),
               int(h * 0.22) + int(h * 0.28)],
              outline=GREEN if ok else RED, width=3)
    d.text((w // 2, int(h * 0.36)), "SIGNED" if ok else "FAILED",
           font=_font(int(h * 0.08)), fill=GREEN if ok else RED, anchor="mm")
    d.text((w // 2, int(h * 0.62)), detail, font=_font(int(h * 0.055)),
           fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.78)), "power off when done —",
           font=_font(int(h * 0.05)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.85)), "nothing is kept",
           font=_font(int(h * 0.05)), fill=GREY, anchor="mm")
    return img


def seed_entry(w, h, word_index, total_words, partial, candidates):
    img, d = _frame(w, h, f"SEED  WORD  {word_index} / {total_words}")
    d.text((w // 2, int(h * 0.25)), partial + "_", font=_font(int(h * 0.13)),
           fill=CREAM, anchor="mm")
    for i, c in enumerate(candidates[:4]):
        y = int(h * (0.44 + i * 0.11))
        sel = i == 0
        if sel:
            d.rectangle([int(w * 0.28), y - int(h * 0.048),
                         int(w * 0.72), y + int(h * 0.048)], outline=OCHRE)
        d.text((w // 2, y), c, font=_font(int(h * 0.065)),
               fill=CREAM if sel else GREY, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "U/D · letter   A · add   R · words   B · del   C · quit",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def busy(w, h, message="checking words, deriving in Core…"):
    img, d = _frame(w, h)
    d.text((w // 2, int(h * 0.42)), "●  ●  ●", font=_font(int(h * 0.09)),
           fill=OCHRE, anchor="mm")
    d.text((w // 2, int(h * 0.58)), message, font=_font(int(h * 0.055)),
           fill=CREAM, anchor="mm")
    return img


def seed_menu(w, h, selected=0):
    """Choose the seed input mode (A-14's three modes + SeedQR)."""
    img, d = _frame(w, h, "OPEN  WALLET")
    options = [
        ("Scan SeedQR", "words via shim"),
        ("Type seed words", "words via shim"),
        ("Scan descriptor QR", "pure Core, no shim"),
        ("Scan xprv QR", "pure Core, no shim"),
    ]
    for i, (label, note) in enumerate(options):
        y = int(h * (0.24 + i * 0.14))
        if i == selected:
            d.rectangle([int(w * 0.04), y - int(h * 0.055),
                         int(w * 0.96), y + int(h * 0.055)], outline=OCHRE)
        d.text((int(w * 0.08), y), label, font=_font(int(h * 0.062)),
               fill=CREAM if i == selected else GREY, anchor="lm")
        d.text((int(w * 0.92), y), note, font=_font(int(h * 0.045)),
               fill=OCHRE if i == selected else GREY, anchor="rm")
    d.text((w // 2, int(h * 0.95)), "UP/DOWN · choose    A · select    B · back",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def keymaterial_warning(w, h, kind="descriptor"):
    """Shown before accepting an xprv or descriptor (A-14): the QR IS the
    wallet — no passphrase layer protects it."""
    img, d = _frame(w, h, f"SCAN  {kind.upper()}")
    d.text((w // 2, int(h * 0.30)), "This QR IS the wallet.",
           font=_font(int(h * 0.075)), fill=RED, anchor="mm")
    lines = ["There is no passphrase layer on a raw " + kind + ".",
             "Anyone holding this code holds the funds.",
             "Scan it in private."]
    for i, line in enumerate(lines):
        d.text((w // 2, int(h * (0.46 + i * 0.09))), line,
               font=_font(int(h * 0.05)), fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "A · I understand, scan    B · back",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def seed_length(w, h, selected=0):
    img, d = _frame(w, h, "SEED  LENGTH")
    for i, label in enumerate(["12 words", "24 words"]):
        y = int(h * (0.35 + i * 0.18))
        if i == selected:
            d.rectangle([int(w * 0.30), y - int(h * 0.07),
                         int(w * 0.70), y + int(h * 0.07)], outline=OCHRE)
        d.text((w // 2, y), label, font=_font(int(h * 0.08)),
               fill=CREAM if i == selected else GREY, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "UP/DOWN · choose    A · select",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


# ---- codex32 (BIP93) screens — v1.1, map ticket #5 -------------------------

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


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
    d.text((w // 2, int(h * 0.95)), "A · type instead    B · back",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def codex32_entry(w, h, entered="MS12NAMEA320ZYXRPP", cursor=14):
    """bech32 charset as a 4x8 grid; d-pad moves, A picks, B deletes.
    The string echo shows the last chars; checksum judges at the end."""
    img, d = _frame(w, h, "TYPE  SHARE")
    # Echo in 4-char groups with gaps, matching the write-it-down screen,
    # so what you type reads like what you wrote.
    tail = entered[-16:]
    grouped = " ".join(tail[i:i + 4] for i in range(0, len(tail), 4))
    d.text((w // 2, int(h * 0.17)), grouped + "_",
           font=_font(int(h * 0.065)), fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.245)), f"{len(entered)} chars",
           font=_font(int(h * 0.04)), fill=GREY, anchor="mm")
    cell_w, cell_h = w // 9, int(h * 0.115)
    x0, y0 = (w - 8 * cell_w) // 2, int(h * 0.32)
    for i, ch in enumerate(BECH32_CHARSET):
        r, c = divmod(i, 8)
        cx = x0 + c * cell_w + cell_w // 2
        cy = y0 + r * cell_h + cell_h // 2
        if i == cursor:
            d.rectangle([cx - cell_w // 2 + 2, cy - cell_h // 2 + 2,
                         cx + cell_w // 2 - 2, cy + cell_h // 2 - 2],
                        outline=OCHRE)
        d.text((cx, cy), ch.upper(), font=_font(int(h * 0.06)),
               fill=CREAM if i == cursor else GREY, anchor="mm")
    d.text((w // 2, int(h * 0.95)),
           "d-pad · move    A · pick    B · delete    C · done",
           font=_font(int(h * 0.042)), fill=GREY, anchor="mm")
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
    d.text((w // 2, int(h * 0.95)), "A · add next share    C · abort",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def codex32_error(w, h, detail="checksum failed at position 31"):
    img, d = _frame(w, h)
    d.text((w // 2, int(h * 0.32)), "SHARE  REFUSED",
           font=_font(int(h * 0.085)), fill=RED, anchor="mm")
    d.text((w // 2, int(h * 0.50)), detail,
           font=_font(int(h * 0.055)), fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.64)), "detection only: this device never",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.71)), "guesses corrections to key material",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "A · re-enter    B · back",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def codex32_split_choice(w, h, selected=0):
    img, d = _frame(w, h, "BACKUP  AS  CODEX32")
    options = [("One string", "whole seed, one line"),
               ("Split k-of-n", "2-of-3 · shares to guardians")]
    for i, (label, note) in enumerate(options):
        y = int(h * (0.28 + i * 0.17))
        if i == selected:
            d.rectangle([int(w * 0.06), y - int(h * 0.07),
                         int(w * 0.94), y + int(h * 0.07)], outline=OCHRE)
        d.text((int(w * 0.10), y), label, font=_font(int(h * 0.065)),
               fill=CREAM if i == selected else GREY, anchor="lm")
        d.text((int(w * 0.90), y), note, font=_font(int(h * 0.045)),
               fill=OCHRE if i == selected else GREY, anchor="rm")
    d.text((w // 2, int(h * 0.70)), "some practitioners discourage splitting",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.77)), "seeds; shares are optional, never required",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "UP/DOWN · choose    A · select    B · back",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def codex32_share_display(w, h,
                          share="MS12NAMEA320ZYXRPP5QSRJG",
                          index=1, total=3):
    img, d = _frame(w, h, f"SHARE  {index} / {total}  ·  WRITE  IT  DOWN")
    groups = [share[i:i + 4] for i in range(0, len(share), 4)]
    for row in range(0, len(groups), 3):
        y = int(h * (0.26 + (row // 3) * 0.13))
        d.text((w // 2, y), "  ".join(groups[row:row + 3]),
               font=_font(int(h * 0.075)), fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.72)), "checksum re-verifies before you leave",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.79)), "the codex32 kit worksheets own paper",
           font=_font(int(h * 0.045)), fill=OCHRE, anchor="mm")
    d.text((w // 2, int(h * 0.95)), "A · I wrote it, verify me    C · abort",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def codex32_verified(w, h, kind="share 2 of 3"):
    img, d = _frame(w, h)
    d.ellipse([w // 2 - int(h * 0.13), int(h * 0.20),
               w // 2 + int(h * 0.13), int(h * 0.20) + int(h * 0.26)],
              outline=GREEN, width=3)
    d.text((w // 2, int(h * 0.33)), "VALID", font=_font(int(h * 0.075)),
           fill=GREEN, anchor="mm")
    d.text((w // 2, int(h * 0.58)), kind, font=_font(int(h * 0.06)),
           fill=CREAM, anchor="mm")
    d.text((w // 2, int(h * 0.72)), "verified without exposing the seed",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    d.text((w // 2, int(h * 0.79)), "to any other device",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img
