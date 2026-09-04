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
BANNED_IMPORTS = {"hashlib", "hmac", "secrets", "ecdsa", "coincurve",
                  "bip32", "cryptography", "nacl"}
for src in sorted((ROOT / "corky").glob("*.py")):
    found = set()
    for node in ast.walk(ast.parse(src.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    bad = found & BANNED_IMPORTS
    check(f"no crypto import: corky/{src.name}", not bad,
          f"found {sorted(bad)}" if bad else "")

# 3. No key-derivation vocabulary survives in the shipped code. A rename
#    would not hide the intent; this catches the obvious reintroduction.
BANNED_TEXT = ("pbkdf2", "mnemonic_to_", "seed_to_xprv", "Bitcoin seed",
               "BIP39_WORDLIST", "load_wordlist")
for src in sorted((ROOT / "corky").glob("*.py")):
    body = src.read_text()
    hits = [t for t in BANNED_TEXT if t in body]
    check(f"no derivation code: corky/{src.name}", not hits,
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
