"""Integrity tests: the frozen-module discipline, automated.

The README promises the shim and codex32 modules are frozen with their
hashes pinned in SHIM_HASH, and that the wordlist is refused if tampered.
Until now that discipline was manual. This test makes it structural: it
FAILS if a frozen file changes without its pinned hash being re-recorded,
and proves the wordlist tamper-refusal path actually fires.
Run: python3 tests/test_integrity.py
"""
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = []

def ok(msg): print("ok  ", msg)
def fail(msg): fails.append(msg); print("FAIL", msg)

# 1. Every line in SHIM_HASH must match the current file content.
pins = {}
for line in (ROOT / "SHIM_HASH").read_text().splitlines():
    if line.strip():
        h, _, path = line.strip().partition("  ")
        pins[path] = h
expected_pinned = {"shim/bip39_shim.py", "corky/codex32.py",
                   "corky/seedqr.py"}
if set(pins) == expected_pinned:
    ok("SHIM_HASH pins exactly the three frozen Layer-1 modules")
else:
    fail(f"SHIM_HASH pins {set(pins)}, expected {expected_pinned}")
for path, pinned in pins.items():
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if actual == pinned:
        ok(f"{path} matches its pinned hash")
    else:
        fail(f"{path} CHANGED without re-pinning (frozen-module discipline "
             f"violated): pinned {pinned[:12]}.. actual {actual[:12]}..")

# 2. Wordlist matches the canonical BIP39 hash.
CANON = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
wl = hashlib.sha256((ROOT / "shim" / "english.txt").read_bytes()).hexdigest()
if wl == CANON:
    ok("english.txt matches the canonical BIP39 wordlist hash")
else:
    fail("english.txt does not match the canonical BIP39 hash")

# 3. Tamper-refusal actually fires: import the shim from a copy with a
#    modified wordlist and prove load_wordlist raises.
tmp = Path(tempfile.mkdtemp(prefix="shim-tamper-"))
try:
    shutil.copy(ROOT / "shim" / "bip39_shim.py", tmp / "bip39_shim.py")
    words = (ROOT / "shim" / "english.txt").read_text().splitlines()
    words[0] = "tampered"
    (tmp / "english.txt").write_text("\n".join(words) + "\n")
    sys.path.insert(0, str(tmp))
    import importlib
    tampered = importlib.import_module("bip39_shim")
    try:
        tampered.load_wordlist()
        fail("tampered wordlist was ACCEPTED")
    except ValueError:
        ok("tampered wordlist refused with ValueError")
    finally:
        sys.path.remove(str(tmp))
        sys.modules.pop("bip39_shim", None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    sys.exit(1)
print("\nINTEGRITY PASS")
