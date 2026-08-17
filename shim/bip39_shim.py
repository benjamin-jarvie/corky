"""Corky's one piece of non-Core code: BIP39 words -> BIP32 xprv.

Bitcoin Core does not read seed words and never will. This file is the
translator. It is the ONLY code in Corky that touches secret material
outside Bitcoin Core, so it is held to three rules:

  1. Python standard library only. No third-party imports, ever.
  2. No elliptic-curve math. Hashing and encoding only. Every key
     operation (derivation, signing) happens inside Bitcoin Core.
  3. Frozen. Changes require re-running test_shim.py against the
     official BIP32/BIP39 vectors and updating the hash in README.md.

The two transformations, per the standards:
  BIP39: seed = PBKDF2-HMAC-SHA512(words, "mnemonic"+passphrase, 2048 rounds)
  BIP32: HMAC-SHA512(key=b"Bitcoin seed", seed) -> 32-byte key + 32-byte
         chain code, serialized with the xprv version bytes and a
         double-SHA256 checksum in Base58.
"""

import hashlib
import hmac
import unicodedata
from pathlib import Path

_WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def load_wordlist():
    raw = (Path(__file__).parent / "english.txt").read_bytes()
    if hashlib.sha256(raw).hexdigest() != _WORDLIST_SHA256:
        raise ValueError("wordlist file does not match the canonical BIP39 hash")
    return raw.decode("ascii").split()


def validate_mnemonic(mnemonic: str) -> str:
    """Check words against the list and verify the BIP39 checksum.

    Returns the normalized mnemonic. Raises ValueError on any defect,
    naming the bad word so the user can fix a typo on the device.
    """
    words = unicodedata.normalize("NFKD", mnemonic).strip().lower().split()
    if len(words) not in (12, 15, 18, 21, 24):
        raise ValueError(f"{len(words)} words; expected 12, 15, 18, 21 or 24")
    wordlist = load_wordlist()
    index = {w: i for i, w in enumerate(wordlist)}
    bits = ""
    for w in words:
        if w not in index:
            raise ValueError(f"'{w}' is not a BIP39 word")
        bits += format(index[w], "011b")
    checksum_len = len(words) // 3
    entropy_bits, checksum = bits[:-checksum_len], bits[-checksum_len:]
    entropy = int(entropy_bits, 2).to_bytes(len(entropy_bits) // 8, "big")
    expected = format(hashlib.sha256(entropy).digest()[0], "08b")[:checksum_len]
    if checksum != expected:
        raise ValueError("checksum mismatch: one or more words are wrong")
    return " ".join(words)


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    mnemonic = unicodedata.normalize("NFKD", mnemonic)
    salt = "mnemonic" + unicodedata.normalize("NFKD", passphrase)
    return hashlib.pbkdf2_hmac("sha512", mnemonic.encode(), salt.encode(), 2048)


def _base58check(payload: bytes) -> str:
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(payload + checksum, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58_ALPHABET[r] + out
    for byte in payload:
        if byte:
            break
        out = "1" + out
    return out


def seed_to_xprv(seed: bytes, mainnet: bool = True) -> str:
    i = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    key, chain_code = i[:32], i[32:]
    version = bytes.fromhex("0488ade4" if mainnet else "04358394")
    payload = version + b"\x00" + b"\x00" * 4 + b"\x00" * 4 + chain_code + b"\x00" + key
    return _base58check(payload)


def mnemonic_to_xprv(mnemonic: str, passphrase: str = "", mainnet: bool = True) -> str:
    """The one call Corky's front end makes. Validates, then converts."""
    normalized = validate_mnemonic(mnemonic)
    return seed_to_xprv(mnemonic_to_seed(normalized, passphrase), mainnet)
