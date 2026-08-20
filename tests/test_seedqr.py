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

# Boundary: index 2047 is the last valid word; 2048 must be rejected.
last = seedqr.decode("2047" + "0000" * 10 + "0000")
assert last.split()[0] == seedqr.load_wordlist()[2047]
print("ok   index 2047 (last valid word) decodes")
for bad in ["123", "9999" + "0000" * 11, "abcd" * 12,
            "2048" + "0000" * 11]:
    try:
        seedqr.decode(bad)
        print("FAIL accepted", bad[:12]); sys.exit(1)
    except seedqr.SeedQrError:
        pass
print("ok   malformed streams rejected")

# L56 In->NotIn: an entropy-sized byte payload that is ALSO all ASCII
# digits must be read as COMPACT (16 raw bytes), not misparsed as a digit
# stream. 16 ASCII digits are 16 bytes -> compact -> a valid mnemonic.
# Under the mutation this falls through to decode_standard and raises.
digit_entropy = b"1234567890123456"  # exactly 16 bytes
assert len(digit_entropy) == 16
words3 = seedqr.decode(digit_entropy)
assert len(words3.split()) == 12, words3
validate_mnemonic(words3)
print("ok   16 ASCII-digit bytes decode as compact (In branch)")

# A 17-byte payload is not a valid compact entropy length -> must raise.
try:
    seedqr.decode(bytes(17))
    print("FAIL accepted 17-byte entropy"); sys.exit(1)
except seedqr.SeedQrError:
    print("ok   17-byte entropy length rejected")

print("\nSEEDQR PASS")
