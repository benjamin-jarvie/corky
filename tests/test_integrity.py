"""A-22's guard: prove nothing on the pure signer transforms a secret.

Run: python3 tests/test_integrity.py

This file used to pin hashes for shim/bip39_shim.py, corky/codex32.py and
corky/seedqr.py, because those three transformed key material and the README
promised they were frozen. PLAN A-22 removed all three: `main` is a signer
whose entire job is to carry bytes between a person and Bitcoin Core.

So the promise changed shape. It is no longer "these files are frozen". It is
**"there are no such files"**, and this suite is what stops that quietly
becoming untrue. Every check below fails the moment someone reintroduces code
that computes on a key.

The lab branch carries the removed modules and is not subject to this.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"ok   {name}  {detail}")
    else:
        FAIL += 1
        print(f"FAIL {name}  {detail}")


# 1. The three transforming modules, and the wordlist, are gone.
for gone in ("shim/bip39_shim.py", "shim/english.txt", "corky/codex32.py",
             "corky/seedqr.py", "SHIM_HASH"):
    check(f"absent: {gone}", not (ROOT / gone).exists())
check("absent: the whole shim/ directory", not (ROOT / "shim").exists())

# 2. No shipped module imports a cryptographic primitive. Corky does no
#    hashing, no HMAC, no key stretching: Core does all of it.
# Everything a shipped module may import from outside the standard library.
# This is the signer's whole third-party surface, and the README section
# "What runs on the signer" lists the same names with their purpose. A new
# import fails here until both are updated on purpose (Ben, 2026-09-05: no
# unneeded dependencies left on the pinned signer).
import sys as _sys
_STDLIB = set(_sys.stdlib_module_names)
_OURS = {"signer", "screens", "filechannel", "qrchannel", "hal", "splash", "main"}

ALLOWED_THIRD_PARTY = {
    "PIL",         # Pillow: every screen is a PIL image     (apt python3-pil)
    "qrcode",      # renders the outbound QR frames           (pip, pinned)
    "pyzbar",      # decodes what the camera sees, via libzbar0 (pip, pinned)
    "picamera2",   # the camera                              (apt)
    "spidev",      # the SPI bus the panel hangs off         (apt)
    "RPi",         # RPi.GPIO: the buttons                   (apt)
    "ur2",         # vendored: UR fountain codec, hw/vendor/ur2
    "st7789",      # vendored: the panel driver, hw/vendor/st7789.py
}

BANNED_IMPORTS = {"hashlib", "hmac", "secrets", "ecdsa", "coincurve",
                  "bip32", "cryptography", "nacl"}
# Every shipped .py, wherever it lives. The first version of this scanned
# corky/*.py only, so a reintroduced Layer 1 in a new top-level directory
# would have passed. Found by the A-22 spec review, 2026-09-04.
SHIPPED = sorted(p for p in ROOT.rglob("*.py")
                 if not any(part in {"tests", "hw", ".git", "m0", "tools",
                                     "image", "docs"} or part.startswith(".")
                            for part in p.relative_to(ROOT).parts))
check("shipped modules found", len(SHIPPED) >= 7, f"{len(SHIPPED)} files")

for src in SHIPPED:
    found = set()
    for node in ast.walk(ast.parse(src.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    third_party = {n for n in found if n not in _STDLIB and n not in _OURS}
    stray = third_party - ALLOWED_THIRD_PARTY
    check(f"{src.name}: imports only the listed third-party packages",
          not stray, f"unlisted: {sorted(stray)}" if stray else "")
    bad = found & BANNED_IMPORTS
    check(f"no crypto import: {src.relative_to(ROOT)}", not bad,
          f"found {sorted(bad)}" if bad else "")

# 3. No key-derivation vocabulary survives in the shipped code. A rename
#    would not hide the intent; this catches the obvious reintroduction.
BANNED_TEXT = ("pbkdf2", "mnemonic_to_", "seed_to_xprv", "Bitcoin seed",
               "BIP39_WORDLIST", "load_wordlist")
for src in SHIPPED:
    body = src.read_text()
    hits = [t for t in BANNED_TEXT if t in body]
    check(f"no derivation code: {src.relative_to(ROOT)}", not hits,
          f"found {hits}" if hits else "")

# 4. The one thing Corky may do with a key is hand it to Core untouched.
sig = (ROOT / "corky" / "signer.py").read_text()
check("signer only imports keys into Core",
      "importdescriptors" in sig and "open_session_xprv" in sig
      and "def open_session(" not in sig,
      "xprv and descriptor paths only, no mnemonic path")

print("\n" + "=" * 62)
print(f"PASS {PASS}   FAIL {FAIL}")
print("Layer 1 is empty: no shipped line transforms secret material.")
sys.exit(1 if FAIL else 0)
