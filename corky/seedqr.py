"""SeedQR decode: SeedSigner's QR format for BIP39 seeds (A-1).

Two variants, both pure text/bit manipulation — no cryptography:
  Standard SeedQR: a digit stream, 4 digits per word (zero-padded wordlist
    index 0000-2047), 48 digits = 12 words, 96 = 24.
  CompactSeedQR: raw entropy bytes (16 or 32); the checksum word is
    reconstructed per BIP39 from the entropy.

Output is always a mnemonic string, which then flows through the shim's
validate_mnemonic like typed words — this module never touches keys.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
from bip39_shim import load_wordlist  # noqa: E402


class SeedQrError(Exception):
    pass


def decode_standard(digits: str) -> str:
    digits = digits.strip()
    if not digits.isdigit() or len(digits) not in (48, 60, 72, 84, 96):
        raise SeedQrError(f"not a SeedQR digit stream ({len(digits)} chars)")
    wordlist = load_wordlist()
    words = []
    for i in range(0, len(digits), 4):
        idx = int(digits[i:i + 4])
        if idx > 2047:
            raise SeedQrError(f"word index {idx} out of range")
        words.append(wordlist[idx])
    return " ".join(words)


def decode_compact(entropy: bytes) -> str:
    if len(entropy) not in (16, 20, 24, 28, 32):
        raise SeedQrError(f"bad entropy length {len(entropy)}")
    wordlist = load_wordlist()
    checksum_bits = len(entropy) * 8 // 32
    check = format(hashlib.sha256(entropy).digest()[0], "08b")[:checksum_bits]
    bits = "".join(format(b, "08b") for b in entropy) + check
    return " ".join(wordlist[int(bits[i:i + 11], 2)]
                    for i in range(0, len(bits), 11))


def decode(payload) -> str:
    """Accept either a scanned digit string or raw bytes; return words."""
    if isinstance(payload, bytes):
        # Entropy-sized byte payloads are compact FIRST: 16/32 bytes of
        # entropy that happen to be all ASCII digits must not be misread
        # as a (wrong-length) digit stream.
        if len(payload) in (16, 20, 24, 28, 32):
            return decode_compact(payload)
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError:
            return decode_compact(payload)
        if text.strip().isdigit():
            return decode_standard(text)
        return decode_compact(payload)
    return decode_standard(payload)
