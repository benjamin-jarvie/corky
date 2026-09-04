"""README truth test: fails when the README's numeric claims drift.

The frozen-hash discipline is already mechanical (test_integrity.py), but
the README's line counts and campaign figures were prose — and prose rots.
This asserts every counted claim against the tree itself, so a
test-writing burst can no longer leave the README quietly wrong.
Run: python3 tests/test_readme_claims.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = []

def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)

def code_lines(path):
    """Functional lines: no blanks, no comments, no docstrings."""
    n, indoc = 0, False
    for ln in Path(path).read_text().splitlines():
        s = ln.strip()
        if not s:
            continue
        if indoc:
            if s.endswith('"""') or s.endswith("'''"):
                indoc = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            if not ((s.endswith('"""') or s.endswith("'''")) and len(s) > 3):
                indoc = True
            continue
        if s.startswith("#"):
            continue
        n += 1
    return n

README = (ROOT / "README.md").read_text()

# A-22: Layer 1 is empty on main. tests/test_integrity.py is the guard
# that keeps it empty; this file only has to stop claiming otherwise.
LAYER1 = []
LAYER2 = ["corky/main.py", "corky/screens.py", "corky/splash.py",
          "corky/hal.py"]
LAYER3 = ["corky/signer.py", "corky/filechannel.py", "corky/qrchannel.py"]

def claimed(pattern, label):
    m = re.search(pattern, README)
    if not m:
        bad(f"README no longer states {label} (pattern missing)")
        return None
    return int(m.group(1).replace(",", ""))

# Layer totals
for files, pat, label in [
    (LAYER1, r"transforms secret material\. ([\d,]+) lines", "layer 1 total"),
    (LAYER2, r"sees secrets, computes nothing with them\. ([\d,]+) lines", "layer 2 total"),
    (LAYER3, r"never touches secrets at all\. ([\d,]+) lines", "layer 3 total"),
]:
    actual = sum(code_lines(ROOT / f) for f in files)
    c = claimed(pat, label)
    if c is None:
        continue
    if c == actual:
        ok(f"{label}: README {c} == actual {actual}")
    else:
        bad(f"{label}: README says {c}, actual {actual}")

# Per-file counts in the layer-1 table and layer-2/3 inline figures
for f in LAYER1 + LAYER2 + LAYER3:
    name = f.split("/")[-1]
    actual = code_lines(ROOT / f)
    hits = re.findall(rf"{re.escape(name)}\)[^|\n]*[|(] ?([\d,]+)", README)
    if not hits:
        bad(f"{name}: no line count found in README")
        continue
    if any(int(h.replace(",", "")) == actual for h in hits):
        ok(f"{name}: README count matches actual {actual}")
    else:
        bad(f"{name}: README says {hits}, actual {actual}")

# Total functional
# The raw total was unpinned until 2026-09-02 and had drifted by 95 lines
# while the functional total stayed exact (TESTING.md rule 4).
raw = sum(len((ROOT / f).read_text().splitlines())
          for f in LAYER1 + LAYER2 + LAYER3)
rc = claimed(r"\(([\d,]+) with blanks/comments\)", "raw total")
if rc is not None:
    ok(f"raw total: {rc} == {raw}") if rc == raw else \
        bad(f"raw total: README {rc}, actual {raw}")

total = sum(code_lines(ROOT / f) for f in LAYER1 + LAYER2 + LAYER3)
c = claimed(r"\*\*Total functional code: ([\d,]+) lines\*\*", "total functional")
if c is not None:
    ok(f"total functional: {c} == {total}") if c == total else \
        bad(f"total functional: README {c}, actual {total}")

# Test lines
tests = sorted((ROOT / "tests").glob("*.py"))
tl = sum(code_lines(f) for f in tests)
c = claimed(r"\*\*Test code: ([\d,]+) lines", "test code")
if c is not None:
    ok(f"test code: {c} == {tl}") if c == tl else \
        bad(f"test code: README {c}, actual {tl}")

# Vendored lines (total incl. comments, as the README states them)
vend = sum(len(f.read_text().splitlines())
           for f in (ROOT / "hw" / "vendor").rglob("*.py"))
c = claimed(r"Vendored, not ours: ([\d,]+) lines", "vendored")
if c is not None:
    ok(f"vendored: {c} == {vend}") if c == vend else \
        bad(f"vendored: README {c}, actual {vend}")

# Every file the README links must exist
broken = [l for l in set(re.findall(r"\]\((?!http)([^)#]+)\)", README))
          if not (ROOT / l).exists()]
for l in broken:
    bad(f"README links a missing path: {l}")
if not broken:
    ok("every relative README link resolves")

# Prose figures the README asserts about the test campaign.
import subprocess
# Count the session markers themselves. The old rule matched only
# `print("ok   X:` with a single-letter label, so it silently ignored
# sessions named D3, H3/H4, R3 or T2 and undercounted by a third.
sess = len(re.findall(r"^\s*# ---- Session ",
                      (ROOT / "tests" / "e2e_session.py").read_text(), re.M))
c = claimed(r"([\d]+) scripted device sessions", "device sessions")
if c is not None:
    ok(f"device sessions: {c} == {sess}") if c == sess else \
        bad(f"device sessions: README {c}, actual {sess}")
adv = (ROOT / "tests" / "test_adversarial.py").read_text()
n_attacks = len(re.findall(r"^# *\d+\.|^ATTACK", adv, re.M)) or adv.count("attack(")
c = claimed(r"([\d]+) adversarial\s*\n?checks", "adversarial checks")
if c is not None and n_attacks:
    ok(f"adversarial: README {c} vs {n_attacks} labelled attacks (informational)")
if fails:
    print("\n" + "\n".join(fails))
    sys.exit(1)
print("\nREADME CLAIMS PASS")
