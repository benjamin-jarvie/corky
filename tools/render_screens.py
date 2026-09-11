"""Render every Core Signer screen at both v1 resolutions to PNG for design review.
Run: python3 tools/render_screens.py <outdir>"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coresigner"))
import screens  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "art/screens")
OUT.mkdir(parents=True, exist_ok=True)

DEMO_OUTPUTS = [
    ("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu", 0.215),
    ("bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr", 0.03444556),
]

# Both panels are ST7789. The 320x240 set was tagged "ili9341" until
# 2026-09-08, which named a controller Core Signer has never driven: the
# primary build is the 2.8" ST7789 Plus hat (HARDWARE.md, PLAN A-13b).
for w, h, tag in [(320, 240, "st7789-320"), (240, 240, "st7789-240")]:
    for name, img in {
        "0-splash": screens.splash(w, h),
        "1-home": screens.home(w, h),
        "2-key-entry": screens.text_entry(w, h, "BIP32  EXTENDED  PRIVATE  KEY",
                                          "tprv8ZgxMBicQKsPe", 7, "xprv"),
        "3-busy": screens.busy(w, h),
        "4-review": screens.review(w, h, DEMO_OUTPUTS, 0.0000851),
        "6-load-key-menu": screens.load_key_menu(w, h),
        "7-tools": screens.tools_menu(w, h),
        "8-export": screens.export_menu(w, h),
        "9-address": screens.address_page(
            w, h, 0, "bc1q635yhaml2afumm27jxsjmqayczf5nf0xmm9zh0", "wpkh"),
        "a-keys": screens.keys_menu(w, h, [("coresigner", "73c5da0a")]),
        "b-key": screens.key_menu(w, h, "73c5da0a"),
        "5-result": screens.result(w, h),
    }.items():
        img.resize((w * 2, h * 2), 0).save(OUT / f"{tag}-{name}.png")
print(f"rendered to {OUT}")
