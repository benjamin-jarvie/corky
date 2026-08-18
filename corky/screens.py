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
    for i, (label, hint) in enumerate(
            [("Scan PSBT  (camera)", "QR"),
             ("Load PSBT  (USB / card)", "FILE"),
             ("Enter seed", "WORDS or SEEDQR")]):
        y = int(h * (0.50 + i * 0.14))
        d.text((int(w * 0.08), y), label, font=_font(int(h * 0.07)),
               fill=CREAM, anchor="lm")
        d.text((int(w * 0.92), y), hint, font=_font(int(h * 0.05)),
               fill=OCHRE, anchor="rm")
    d.text((w // 2, int(h * 0.95)), f"bitcoind ready · session RAM-only · {version}",
           font=_font(int(h * 0.045)), fill=GREY, anchor="mm")
    return img


def review(w, h, outputs, fee_btc, input_count, input_total_btc=None, warn=True):
    """The screen that matters. outputs: [(address, amount_btc), ...]"""
    img, d = _frame(w, h, "REVIEW  TRANSACTION")
    y = int(h * 0.18)
    for addr, amt in outputs[:3]:
        short = addr[:14] + "…" + addr[-6:] if len(addr) > 24 else addr
        d.text((int(w * 0.06), y), short, font=_font(int(h * 0.058)),
               fill=CREAM, anchor="lm")
        d.text((int(w * 0.94), y + int(h * 0.065)), f"{amt:.8f} BTC",
               font=_font(int(h * 0.065)), fill=CREAM, anchor="rm")
        y += int(h * 0.155)
    if len(outputs) > 3:
        d.text((int(w * 0.06), y), f"+ {len(outputs) - 3} more outputs…",
               font=_font(int(h * 0.055)), fill=GREY, anchor="lm")
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
    d.text((w // 2, int(h * 0.95)), "UP/DOWN · choose    A · accept    B · back",
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
