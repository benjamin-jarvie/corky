"""Render every Corky screen at both v1 resolutions to PNG for design review.
Run: python3 tools/render_screens.py <outdir>"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
import screens  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "art/screens")
OUT.mkdir(parents=True, exist_ok=True)

DEMO_OUTPUTS = [
    ("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu", 0.215),
    ("bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr", 0.03444556),
]

for w, h, tag in [(320, 240, "ili9341"), (240, 240, "st7789")]:
    for name, img in {
        "1-home": screens.home(w, h),
        "2-seed-entry": screens.seed_entry(w, h),
        "3-busy": screens.busy(w, h),
        "4-review": screens.review(w, h, DEMO_OUTPUTS, 0.0000851, 3),
        "5-result": screens.result(w, h),
    }.items():
        img.resize((w * 2, h * 2), 0).save(OUT / f"{tag}-{name}.png")
print(f"rendered to {OUT}")
