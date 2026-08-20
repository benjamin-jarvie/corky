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

# Every valid COMPACT entropy length (16/20/24/28/32 bytes) must decode.
# This pins the length tuple in decode_compact: an off-by-one on any
# boundary makes that length raise instead of producing a mnemonic.
for nbytes, nwords in [(16, 12), (20, 15), (24, 18), (28, 21), (32, 24)]:
    w = seedqr.decode(bytes(nbytes))
    assert len(w.split()) == nwords, f"{nbytes}-byte compact -> {w}"
print("ok   all compact entropy lengths (16/20/24/28/32) decode")

# Every valid STANDARD digit-stream length (48/60/72/84/96) must decode.
# Pins the length tuple in decode_standard.
for ndigits, nwords in [(48, 12), (60, 15), (72, 18), (84, 21), (96, 24)]:
    w = seedqr.decode("0000" * (ndigits // 4))
    assert len(w.split()) == nwords, f"{ndigits} digits -> {w}"
print("ok   all standard digit lengths (48/60/72/84/96) decode")

# The bytes-first routing must send EVERY entropy-sized all-ASCII-digit
# payload to decode_compact, not decode_standard. Pins the length tuple in
# decode(): if a boundary is dropped, that payload falls through to
# decode_standard, which rejects the (wrong) digit-stream length.
for nbytes, nwords in [(16, 12), (20, 15), (24, 18), (28, 21), (32, 24)]:
    payload = ("1" * nbytes).encode("ascii")
    assert len(payload) == nbytes
    w = seedqr.decode(payload)
    assert len(w.split()) == nwords, f"{nbytes} ascii-digit bytes -> {w}"
print("ok   all ASCII-digit byte lengths route to compact (bytes-first)")

print("\nSEEDQR PASS")
