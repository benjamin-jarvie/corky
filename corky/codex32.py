"""codex32 (BIP93): checksummed, shareable master seed strings.

This module encodes, splits, recovers and verifies BIP-0032 master seeds
in the codex32 format. Together with shim/bip39_shim.py it is the only
code in Corky that touches secret material outside Bitcoin Core, so it is
held to the same three rules:

  1. Python standard library only. No third-party imports, ever.
  2. No elliptic-curve math. GF(32) share arithmetic, hashing and
     encoding only. Every key operation happens inside Bitcoin Core.
  3. Frozen. Changes require re-running tests/test_codex32.py against
     the official BIP93 vectors and updating the hash in SHIM_HASH.

The checksum functions are the reference implementation from BIP93,
taken verbatim: they are the spec. This module DETECTS errors only; it
never corrects a string. The device supplies all randomness: split()
takes explicit entropy bytes and this module never generates any.

Trust statement: every byte in this file is auditable against the BIP93
text with no dependency beyond the Python standard library.
"""

import hashlib
import hmac


class Codex32Error(ValueError):
    """Any defect in a codex32 string or share set."""


# ---- BIP93 reference implementation (verbatim) -------------------------

MS32_CONST = 0x10CE0795C2FD1E62A


def ms32_polymod(values):
    GEN = [
        0x19DC500CE73FDE210,
        0x1BFAE00DEF77FE529,
        0x1FBD920FFFE7BEE52,
        0x1739640BDEEE3FDAD,
        0x07729A039CFC75F5A,
    ]
    residue = 0x23181B3
    for v in values:
        b = residue >> 60
        residue = (residue & 0x0FFFFFFFFFFFFFFF) << 5 ^ v
        for i in range(5):
            residue ^= GEN[i] if ((b >> i) & 1) else 0
    return residue


def ms32_verify_checksum(data):
    if len(data) >= 96:  # See Long codex32 Strings
        return ms32_verify_long_checksum(data)
    if len(data) <= 93:
        return ms32_polymod(data) == MS32_CONST
    return False


def ms32_create_checksum(data):
    if len(data) > 80:  # See Long codex32 Strings
        return ms32_create_long_checksum(data)
    values = data
    polymod = ms32_polymod(values + [0] * 13) ^ MS32_CONST
    return [(polymod >> 5 * (12 - i)) & 31 for i in range(13)]


MS32_LONG_CONST = 0x43381E570BF4798AB26


def ms32_long_polymod(values):
    GEN = [
        0x3D59D273535EA62D897,
        0x7A9BECB6361C6C51507,
        0x543F9B7E6C38D8A2A0E,
        0x0C577EAECCF1990D13C,
        0x1887F74F8DC71B10651,
    ]
    residue = 0x23181B3
    for v in values:
        b = residue >> 70
        residue = (residue & 0x3FFFFFFFFFFFFFFFFF) << 5 ^ v
        for i in range(5):
            residue ^= GEN[i] if ((b >> i) & 1) else 0
    return residue


def ms32_verify_long_checksum(data):
    return ms32_long_polymod(data) == MS32_LONG_CONST


def ms32_create_long_checksum(data):
    values = data
    polymod = ms32_long_polymod(values + [0] * 15) ^ MS32_LONG_CONST
    return [(polymod >> 5 * (14 - i)) & 31 for i in range(15)]


CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def ms32_encode(data):
    combined = data + ms32_create_checksum(data)
    return "ms" + "1" + "".join([CHARSET[d] for d in combined])


def ms32_decode(codex):
    if (any(ord(x) < 33 or ord(x) > 126 for x in codex)) or (
        codex.lower() != codex and codex.upper() != codex
    ):
        return None
    codex = codex.lower()
    pos = codex.rfind("1")
    if pos < 2 or not (48 <= len(codex) <= 127):
        return None
    if not all(x in CHARSET for x in codex[pos + 1 :]):
        return None
    if (
        codex[:pos] != "ms"
        or codex[pos + 1].isalpha()
        or codex[pos + 1] == "0"
        and codex[pos + 6] != "s"
    ):
        return None
    data = [CHARSET.index(x) for x in codex[pos + 1 :]]
    if not ms32_verify_checksum(data):
        return None
    return data[:-13 if len(data) < 94 else -15]  # See Long codex32 Strings


BECH32_INV = [
    0, 1, 20, 24, 10, 8, 12, 29, 5, 11, 4, 9, 6, 28, 26, 31,
    22, 18, 17, 23, 2, 25, 16, 19, 3, 21, 14, 30, 13, 7, 27, 15,
]


def bech32_mul(a, b):
    res = 0
    for i in range(5):
        res ^= a if ((b >> i) & 1) else 0
        a *= 2
        a ^= 41 if (32 <= a) else 0
    return res


def bech32_lagrange(l, x):
    n = 1
    c = []
    for i in l:
        n = bech32_mul(n, i ^ x)
        m = 1
        for j in l:
            m = bech32_mul(m, (x if i == j else i) ^ j)
        c.append(m)
    return [bech32_mul(n, BECH32_INV[i]) for i in c]


def ms32_interpolate(l, x):
    w = bech32_lagrange([s[5] for s in l], x)
    res = []
    for i in range(len(l[0])):
        n = 0
        for j in range(len(l)):
            n ^= bech32_mul(w[j], l[j][i])
        res.append(n)
    return res


def ms32_recover(shares):
    return ms32_interpolate(shares, 16)


# ---- Corky API ---------------------------------------------------------

_S_INDEX = CHARSET.index("s")  # 16
# Fresh-share indexes in the order BIP93 gives: letters alphabetical,
# skipping "s" (the secret), then the digits.
SHARE_INDEXES = "acdefghjklmnpqrtuvwxyz023456789"


def _payload_ok(data):
    """data is threshold+id+index+payload (checksum stripped)."""
    payload = len(data) - 6
    bits = payload * 5
    return 16 <= bits // 8 <= 64 and bits % 8 <= 4


def validate(s: str) -> str:
    """Verify a codex32 string. DETECTION only, never correction.

    Returns the lowercase normalized string. Raises Codex32Error on any
    defect: bad charset, mixed case, bad prefix, bad threshold, bad
    length, or checksum failure.
    """
    if not isinstance(s, str) or not s:
        raise Codex32Error("empty string")
    data = ms32_decode(s.strip())
    if data is None:
        raise Codex32Error("not a valid codex32 string (checksum or format)")
    if not _payload_ok(data):
        raise Codex32Error("payload length does not encode a 16-64 byte seed")
    return s.strip().lower()


def _parse(s: str):
    """validate, then -> (data_values, threshold_char, identifier, index_char)."""
    norm = validate(s)
    data = ms32_decode(norm)
    body = norm[norm.rfind("1") + 1 :]
    return data, body[0], body[1:5], body[5]


def _payload_to_bytes(values) -> bytes:
    bits = 0
    acc = 0
    out = bytearray()
    for v in values:
        acc = (acc << 5) | v
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    return bytes(out)  # incomplete group (<= 4 bits) discarded per BIP93


def _bytes_to_payload(seed: bytes):
    values = []
    acc = 0
    bits = 0
    for byte in seed:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            values.append((acc >> bits) & 31)
    if bits:
        values.append((acc << (5 - bits)) & 31)  # pad with zero bits
    return values


def decode_secret(s: str):
    """Decode a codex32 secret -> (identifier, seed_bytes)."""
    data, threshold, ident, index = _parse(s)
    if index != "s":
        raise Codex32Error(f"share index '{index}': not a codex32 secret")
    return ident, _payload_to_bytes(data[6:])


def encode_secret(identifier: str, seed_bytes: bytes, threshold: int = 0) -> str:
    """Encode a master seed as a codex32 secret string (index 's')."""
    if threshold != 0 and not 2 <= threshold <= 9:
        raise Codex32Error("threshold must be 0 or 2-9")
    identifier = identifier.lower()
    if len(identifier) != 4 or not all(c in CHARSET for c in identifier):
        raise Codex32Error("identifier must be 4 bech32 characters")
    if not 16 <= len(seed_bytes) <= 64:
        raise Codex32Error("seed must be 16-64 bytes")
    data = (
        [CHARSET.index(str(threshold))]
        + [CHARSET.index(c) for c in identifier]
        + [_S_INDEX]
        + _bytes_to_payload(seed_bytes)
    )
    return ms32_encode(data)


def recover(shares) -> str:
    """Recover the codex32 secret from exactly k valid shares."""
    if not shares:
        raise Codex32Error("no shares given")
    parsed = [_parse(s) for s in shares]
    thresholds = {p[1] for p in parsed}
    if len(thresholds) != 1:
        raise Codex32Error("shares have different thresholds")
    threshold = thresholds.pop()
    if threshold == "0":
        raise Codex32Error("threshold 0 strings are unshared secrets")
    k = int(threshold)
    if len({p[2] for p in parsed}) != 1:
        raise Codex32Error("shares have different identifiers")
    if len({len(p[0]) for p in parsed}) != 1:
        raise Codex32Error("shares have different lengths")
    indexes = [p[3] for p in parsed]
    if "s" in indexes:
        raise Codex32Error("index 's' is the secret, not a share")
    if len(set(indexes)) != len(indexes):
        raise Codex32Error("duplicate share index")
    if len(parsed) < k:
        raise Codex32Error(f"need {k} shares, got {len(parsed)}")
    if len(parsed) > k:
        raise Codex32Error(f"threshold is {k}; give exactly {k} shares")
    secret_data = ms32_recover([p[0] for p in parsed])
    return validate(ms32_encode(secret_data))


def derive_identifier(seed: bytes) -> str:
    """Deterministic 4-char bech32 identifier for a seed. Layer 1: this
    computes on secret material, so it lives in the frozen module rather
    than in the UI (README layer discipline). Stdlib hashing only."""
    digest = hashlib.sha256(b"corky-id" + seed).digest()[:4]
    return "".join(CHARSET[b % 32] for b in digest)


def derive_split_entropy(seed: bytes, k: int, n: int) -> bytes:
    """Deterministic split randomness, domain-separated, derived from the
    seed itself: Corky has no RNG and never generates entropy (PLAN A-18).
    Shares therefore re-derive identically. Stdlib hashing only."""
    need = 32 * max(1, k - 1) * max(1, n)
    out = b""
    counter = 0
    while len(out) < need:
        out += hmac.new(seed, b"corky-split-v1" + bytes([counter]),
                        hashlib.sha512).digest()
        counter += 1
    return out[:need]


def split(secret, k: int, n: int, identifier: str, rand_bytes: bytes):
    """Split a seed into n codex32 shares with threshold k.

    secret is a codex32 secret string or raw seed bytes. rand_bytes is
    explicit entropy from the device; this module never generates any.
    Returns a list of n share strings. Any k of them recover the secret.
    """
    if not 2 <= k <= 9:
        raise Codex32Error("k must be 2-9")
    if not k <= n <= len(SHARE_INDEXES):
        raise Codex32Error(f"n must be between k and {len(SHARE_INDEXES)}")
    if isinstance(secret, (bytes, bytearray)):
        secret_str = encode_secret(identifier, bytes(secret), k)
    else:
        ident, seed = decode_secret(secret)
        secret_str = encode_secret(identifier, seed, k)
    secret_data = ms32_decode(secret_str)
    payload_len = len(secret_data) - 6
    need = (k - 1) * payload_len  # 5-bit values of entropy required
    pool = []
    acc = 0
    bits = 0
    for byte in rand_bytes:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            pool.append((acc >> bits) & 31)
    if len(pool) < need:
        raise Codex32Error(f"need {(need * 5 + 7) // 8} bytes of entropy")
    head = secret_data[:5]  # threshold + identifier
    initial = [secret_data]
    for i in range(k - 1):
        idx = CHARSET.index(SHARE_INDEXES[i])
        payload = pool[i * payload_len : (i + 1) * payload_len]
        initial.append(head + [idx] + payload)
    shares = []
    for i in range(n):
        idx = CHARSET.index(SHARE_INDEXES[i])
        if i < k - 1:
            data = initial[i + 1]
        else:
            data = ms32_interpolate(initial, idx)
        shares.append(validate(ms32_encode(data)))
    return shares


def to_xprv(seed_bytes: bytes, mainnet: bool = True) -> str:
    """Convert a decoded master seed to an xprv via the frozen shim."""
    import sys
    from pathlib import Path

    shim_dir = str(Path(__file__).resolve().parent.parent / "shim")
    if shim_dir not in sys.path:
        sys.path.insert(0, shim_dir)
    from bip39_shim import seed_to_xprv

    return seed_to_xprv(seed_bytes, mainnet)
