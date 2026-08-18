"""SeedQR decode tests. Run: python3 tests/test_seedqr.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
import seedqr
from bip39_shim import validate_mnemonic

# abandon x11 + about: indices 0*11 then 3
std = "0000" * 11 + "0003"
words = seedqr.decode(std)
assert words == "abandon " * 11 + "about", words
validate_mnemonic(words)
print("ok   standard SeedQR 12-word decode + checksum valid")

# Compact: entropy 00*16 -> same mnemonic
words2 = seedqr.decode(bytes(16))
assert words2 == words, words2
print("ok   compact SeedQR (16-byte entropy) matches")

for bad in ["123", "9999" + "0000" * 11, "abcd" * 12]:
    try:
        seedqr.decode(bad)
        print("FAIL accepted", bad[:12]); sys.exit(1)
    except seedqr.SeedQrError:
        pass
print("ok   malformed streams rejected")
print("\nSEEDQR PASS")
