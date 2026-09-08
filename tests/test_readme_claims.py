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
# signer.py moved from layer 3 to layer 2 on 2026-09-05, after the two-axis
# review pointed out that it takes an xprv (open_session_xprv,
# build_descriptors, master_xprv, identity_of_key) as parameters. The
# passphrase pair went with PLAN A-24. CONTEXT.md: "Layer 2 sees secrets and
# carries them as strings. Layer 3 is opaque to secrets." It always carried
# the xprv; the README said otherwise for longer than it should have.
LAYER2 = ["corky/main.py", "corky/screens.py", "corky/splash.py",
          "corky/hal.py", "corky/signer.py"]
LAYER3 = ["corky/filechannel.py", "corky/qrchannel.py"]

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

# Per-file counts were dropped from the README on 2026-09-07: seven
# numbers that had to be corrected on almost every commit and that no
# reader was checking. The three LAYER TOTALS stay, because "layer 1 is
# zero lines" is the security claim this project rests on, and a total
# that drifts is the claim quietly becoming false. This test's job is to
# keep stated claims true, not to force claims to be stated.

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
broken = [link for link in set(re.findall(r"\]\((?!http)([^)#]+)\)", README))
          if not (ROOT / link).exists()]
for link in broken:
    bad(f"README links a missing path: {link}")
if not broken:
    ok("every relative README link resolves")

# Prose figures the README asserts about the test campaign.
# Count the session markers themselves. The old rule matched only
# `print("ok   X:` with a single-letter label, so it silently ignored
# sessions named D3, H3/H4, R3 or T2 and undercounted by a third.
# Across EVERY suite that holds sessions, not one named file. The marker
# was made drift-proof and the search was not: e2e_keys.py was added with
# eleven more sessions and this counter never saw one of them, so the
# README said 9 while the tree held 20 (audit A6, 2026-09-06). That is
# the same defect as the label pattern, one level up.
sess = sum(len(re.findall(r"^\s*# ---- Session ", p.read_text(), re.M))
           for p in sorted((ROOT / "tests").glob("*.py")))
c = claimed(r"([\d]+) scripted device sessions", "device sessions")
if c is not None:
    ok(f"device sessions: {c} == {sess}") if c == sess else \
        bad(f"device sessions: README {c}, actual {sess}")
# The attacks, counted from the one marker that cannot drift: their own
# def line. The previous pattern looked for "# 1." or "ATTACK" headings
# that no longer exist, matched exactly one thing, and reported the
# mismatch as "informational", so it could never fail. A metric nobody
# can fail is decoration (TESTING.md rule 4).
adv = (ROOT / "tests" / "test_adversarial.py").read_text()
n_attacks = len(re.findall(r"^def attack_", adv, re.M))
c = claimed(r"([\d]+) adversarial attack scenarios", "adversarial attacks")
if c is not None:
    ok(f"adversarial attacks: {c} == {n_attacks}") if c == n_attacks else \
        bad(f"adversarial attacks: README {c}, actual {n_attacks}")
# Every file and every module.symbol the documents NAME must exist.
#
# Audit A8 (2026-09-06) found the security argument citing
# `radio-check.sh` as the proof that "the OS is silent". No such file has
# ever existed; the tool is `leak-check.sh`, named correctly eleven lines
# above. A table of claims whose evidence column points at nothing is the
# exact mechanism this project has already been bitten by twice, so it is
# mechanical from here.
#
# PLAN.md is a dated LOG of amendments and a forward spec, so it is the
# one document that legitimately names things that do not exist: what an
# amendment deleted, and what a post-v1 note proposes. It may do that,
# but it has to SAY so within three lines, in one of the words below. An
# entry that quietly names a deleted module reads as current, which is
# how the shim looked alive for two days after A-22 removed it.
import ast                                            # noqa: E402

DOCS = ["README.md", "TESTING.md", "CONTEXT.md", "hw/HARDWARE.md"]
SHIPPED = ("signer", "screens", "hal", "qrchannel", "filechannel",
           "main", "splash")

defined = set()
for py in sorted(ROOT.rglob("*.py")):
    if any(part in (".git", "vendor", ".build") for part in py.parts):
        continue
    try:
        tree = ast.parse(py.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.Attribute):
            defined.add(node.attr)

EXCUSED = ("superseded", "post-v1", "not written", "deleted", "removed")
SYM = re.compile(r"`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`")
FILE = re.compile(r"`([\w./-]+\.(?:py|sh|service|rules|conf))`")
ghost_paths, ghost_syms = [], []
for doc in DOCS + ["PLAN.md"]:
    lines = (ROOT / doc).read_text().splitlines()
    for n, line in enumerate(lines, 1):
        window = " ".join(lines[n - 1:n + 2]).lower()
        if doc == "PLAN.md" and any(w in window for w in EXCUSED):
            continue
        # A line that names SeedSigner is citing THEIR source, not ours.
        # Corky vendors their drivers and steals their ideas, and a
        # reader has to be able to tell which tree a path lives in.
        external = "SeedSigner" in line or "seedsigner" in line
        for m in FILE.finditer(line):
            named = m.group(1)
            if external:
                continue
            if not (ROOT / named).exists() and \
                    not any(ROOT.rglob(named.split("/")[-1])):
                ghost_paths.append(f"{doc}:{n} {named}")
        if doc == "PLAN.md":
            continue                     # a log may name what it removed
        for m in SYM.finditer(line):
            mod, _, attr = m.group(1).rpartition(".")
            if mod in SHIPPED and attr not in defined:
                ghost_syms.append(f"{doc}:{n} {m.group(1)}")

# config.txt is the Pi's boot file on the card, not a file in this repo.
ghost_paths = [g for g in ghost_paths if "config.txt" not in g]
if ghost_paths:
    bad(f"documents name {len(ghost_paths)} file(s) that do not exist: "
        + "; ".join(ghost_paths))
else:
    ok("every file the documents name exists")
if ghost_syms:
    bad(f"documents name {len(ghost_syms)} symbol(s) that do not exist: "
        + "; ".join(ghost_syms))
else:
    ok("every module.symbol the documents name exists")

# The icon count, in the three places it is written. It was six in the
# README, seven in the README's own supply-chain table two dozen lines
# later, and seven in the font's NOTICE. The sign tile changed from a QR
# to a signature on 2026-09-05 and one of the three was not updated
# (audit A8, 2026-09-06).
sys.path.insert(0, str(ROOT / "corky"))
import screens                                        # noqa: E402
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10}
real_icons = len(screens.ICON)
said = []
for doc in ("README.md", "hw/vendor/fonts/NOTICE.md"):
    for n, line in enumerate((ROOT / doc).read_text().splitlines(), 1):
        for m in re.finditer(r"\b(\w+)[- ]glyph\b", line):
            word = m.group(1).lower()
            if word in WORDS:
                said.append((f"{doc}:{n}", WORDS[word]))
        for m in re.finditer(r"\b(\w+) home and settings glyphs\b", line):
            word = m.group(1).lower()
            if word in WORDS:
                said.append((f"{doc}:{n}", WORDS[word]))
wrong = [w for w in said if w[1] != real_icons]
if not said:
    bad("no document states the icon count any more; the check is blind")
elif wrong:
    bad(f"screens.ICON holds {real_icons} glyphs, documents say "
        + ", ".join(f"{n} at {w}" for w, n in wrong))
else:
    ok(f"all {len(said)} statements of the icon count say {real_icons}")

if fails:
    print("\n" + "\n".join(fails))
    sys.exit(1)
print("\nREADME CLAIMS PASS")
