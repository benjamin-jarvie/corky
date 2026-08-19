"""BIP93 official test vectors for corky/codex32.py. Run: python3 test_codex32.py

Sources:
  bitcoin/bips bip-0093.mediawiki: all 5 valid vector families and all
  64 invalid strings, transcribed exactly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))

import codex32
from codex32 import (
    Codex32Error,
    CHARSET,
    decode_secret,
    encode_secret,
    ms32_decode,
    ms32_interpolate,
    recover,
    split,
    to_xprv,
    validate,
)

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}\n  got:  {got}\n  want: {want}")
        print(f"FAIL {name}")
    else:
        print(f"ok   {name}")


def check_raises(name, fn, *args):
    try:
        fn(*args)
    except Codex32Error:
        print(f"ok   {name}")
    else:
        FAILURES.append(f"{name}: accepted, expected Codex32Error")
        print(f"FAIL {name}")


# ---- Test vector 1: unshared 128-bit secret ----------------------------

TV1 = "ms10testsxxxxxxxxxxxxxxxxxxxxxxxxxx4nzvca9cmczlw"
check("tv1 validate", validate(TV1), TV1)
ident, seed = decode_secret(TV1)
check("tv1 identifier", ident, "test")
check("tv1 seed", seed.hex(), "318c6318c6318c6318c6318c6318c631")
check(
    "tv1 xprv",
    to_xprv(seed),
    "xprv9s21ZrQH143K3taPNekMd9oV5K6szJ8ND7vVh6fxicRUMDcChr3bFFzuxY8qP3x"
    "FFBL6DWc2uEYCfBFZ2nFWbAqKPhtCLRjgv78EZJDEfpL",
)

# ---- Test vector 2: k=2, uppercase, derive + recover -------------------

TV2_A = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"
TV2_C = "MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN"
TV2_D = "MS12NAMEDLL4F8JLH4E5VDVULDLFXU2JHDNLSM97XVENRXEG"
TV2_S = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"

check("tv2 validate uppercase", validate(TV2_A), TV2_A.lower())
derived_d = codex32.ms32_encode(
    ms32_interpolate([ms32_decode(TV2_A), ms32_decode(TV2_C)], CHARSET.index("d"))
)
check("tv2 derived share d", derived_d, TV2_D.lower())
check("tv2 recover", recover([TV2_A, TV2_C]), TV2_S.lower())
ident2, seed2 = decode_secret(recover([TV2_C, TV2_D]))
check("tv2 identifier", ident2, "name")
check("tv2 seed", seed2.hex(), "d1808e096b35b209ca12132b264662a5")
check(
    "tv2 xprv",
    to_xprv(seed2),
    "xprv9s21ZrQH143K2NkobdHxXeyFDqE44nJYvzLFtsriatJNWMNKznGoGgW5UMTL4fy"
    "WtajnMYb5gEc2CgaKhmsKeskoi9eTimpRv2N11THhPTU",
)

# ---- Test vector 3: k=3 split of an existing 128-bit seed --------------

TV3_SEED = "ffeeddccbbaa99887766554433221100"
TV3_S = "ms13cashsllhdmn9m42vcsamx24zrxgs3qqjzqud4m0d6nln"
TV3_A = "ms13casha320zyxwvutsrqpnmlkjhgfedca2a8d0zehn8a0t"
TV3_C = "ms13cashcacdefghjklmnpqrstuvwxyz023949xq35my48dr"
TV3_D = "ms13cashd0wsedstcdcts64cd7wvy4m90lm28w4ffupqs7rm"
TV3_E = "ms13casheekgpemxzshcrmqhaydlp6yhms3ws7320xyxsar9"
TV3_F = "ms13cashf8jh6sdrkpyrsp5ut94pj8ktehhw2hfvyrj48704"

check("tv3 encode_secret zero pad", encode_secret("cash", bytes.fromhex(TV3_SEED), 3), TV3_S)
for idx, want in (("d", TV3_D), ("e", TV3_E), ("f", TV3_F)):
    got = codex32.ms32_encode(
        ms32_interpolate(
            [ms32_decode(TV3_S), ms32_decode(TV3_A), ms32_decode(TV3_C)],
            CHARSET.index(idx),
        )
    )
    check(f"tv3 derived share {idx}", got, want)
for combo in ((TV3_A, TV3_C, TV3_D), (TV3_C, TV3_E, TV3_F), (TV3_A, TV3_D, TV3_F)):
    check(f"tv3 recover {''.join(s[8] for s in combo)}", recover(list(combo)), TV3_S)
check("tv3 seed", decode_secret(TV3_S)[1].hex(), TV3_SEED)
check(
    "tv3 xprv",
    to_xprv(bytes.fromhex(TV3_SEED)),
    "xprv9s21ZrQH143K266qUcrDyYJrSG7KA3A7sE5UHndYRkFzsPQ6xwUhEGK1rNuyyA5"
    "7Vkc1Ma6a8boVqcKqGNximmAe9L65WsYNcNitKRPnABd",
)

# tv3 padding variants: all valid, all decode to the same seed
TV3_PADS = [
    "ms13cashsllhdmn9m42vcsamx24zrxgs3qqjzqud4m0d6nln",
    "ms13cashsllhdmn9m42vcsamx24zrxgs3qpte35dvzkjpt0r",
    "ms13cashsllhdmn9m42vcsamx24zrxgs3qzfatvdwq5692k6",
    "ms13cashsllhdmn9m42vcsamx24zrxgs3qrsx6ydhed97jx2",
]
for i, s in enumerate(TV3_PADS):
    check(f"tv3 padding variant {i} seed", decode_secret(s)[1].hex(), TV3_SEED)

# ---- Test vector 4: unshared 256-bit secret, 16 padding variants -------

TV4_SEED = "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"
TV4 = "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqqtum9pgv99ycma"
check("tv4 encode_secret zero pad", encode_secret("leet", bytes.fromhex(TV4_SEED), 0), TV4)
check(
    "tv4 xprv",
    to_xprv(decode_secret(TV4)[1]),
    "xprv9s21ZrQH143K3s41UCWxXTsU4TRrhkpD1t21QJETan3hjo8DP5LFdFcB5eaFtV8"
    "x6Y9aZotQyP8KByUjgLTbXCUjfu2iosTbMv98g8EQoqr",
)
TV4_PAD_SUFFIXES = [
    "qqtum9pgv99ycma", "qpj82dp34u6lqtd", "qzsrs4pnh7jmpj5", "qrfcpap2w8dqezy",
    "qy5tdvphn6znrf0", "q9dsuypw2ragmel", "qx05xupvgp4v6qx", "q8k0h5p43c2hzsk",
    "qgum7hplmjtr8ks", "qf9q0lpxzt5clxq", "q28y48pyqfuu7le", "qt7ly0paesr8x0f",
    "qvrvg7pqydv5uyz", "qd6hekpea5n0y5j", "qwcnrwpmlkmt9dt", "q0pgjxpzx0ysaam",
]
TV4_STEM = "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzy"
for i, suffix in enumerate(TV4_PAD_SUFFIXES):
    check(f"tv4 padding variant {i} seed", decode_secret(TV4_STEM + suffix)[1].hex(), TV4_SEED)

# ---- Test vector 5: long codex32, 512-bit seed -------------------------

TV5 = (
    "MS100C8VSM32ZXFGUHPCHTLUPZRY9X8GF2TVDW0S3JN54KHCE6MUA7LQPZYGSFJD6AN"
    "074RXVCEMLH8WU3TK925ACDEFGHJKLMNPQRSTUVWXY06FHPV80UNDVARHRAK"
)
TV5_SEED = (
    "dc5423251cb87175ff8110c8531d0952d8d73e1194e95b5f19d6f9df7c01111104"
    "c9baecdfea8cccc677fb9ddc8aec5553b86e528bcadfdcc201c17c638c47e9"
)
check("tv5 validate long", validate(TV5), TV5.lower())
check("tv5 identifier", decode_secret(TV5)[0], "0c8v")
check("tv5 seed", decode_secret(TV5)[1].hex(), TV5_SEED)
check(
    "tv5 xprv",
    to_xprv(bytes.fromhex(TV5_SEED)),
    "xprv9s21ZrQH143K4UYT4rP3TZVKKbmRVmfRqTx9mG2xCy2JYipZbkLV8rwvBXsUbEv"
    "9KQiUD7oED1Wyi9evZzUn2rqK9skRgPkNaAzyw3YrpJN",
)

# ---- Invalid vectors: all 64 must raise --------------------------------

INVALID_CHECKSUM = [
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxve740yyge2ghq",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxve740yyge2ghp",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxlk3yepcstwr",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx6pgnv7jnpcsp",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxx0cpvr7n4geq",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxm5252y7d3lr",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxrd9sukzl05ej",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxc55srw5jrm0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxgc7rwhtudwc",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx4gy22afwghvs",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxe8yfm0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxvm597d",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxme084q0vpht7pe0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxme084q0vpht7pew",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxqyadsp3nywm8a",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxzvg7ar4hgaejk",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxcznau0advgxqe",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxch3jrc6j5040j",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx52gxl6ppv40mcv",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx7g4g2nhhle8fk",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx63m45uj8ss4x8",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxy4r708q7kg65x",
]

WRONG_CHECKSUM_FOR_SIZE = [
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxurfvwmdcmymdufv",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxcsyppjkd8lz4hx3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxu6hwvl5p0l9xf3c",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxwqey9rfs6smenxa",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxv70wkzrjr4ntqet",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3hmlrmpa4zl0v",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxrfggf88znkaup",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxpt7l4aycv9qzj",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxus27z9xtyxyw3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxcwm4re8fs78vn",
]

IMPROPER_LENGTH = [
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxw0a4c70rfefn4",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxk4pavy5n46nea",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx9lrwar5zwng4w",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxr335l5tv88js3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxvu7q9nz8p7dj68v",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxpq6k542scdxndq3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxkmfw6jm270mz6ej",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxzhddxw99w7xws",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxx42cux6um92rz",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxarja5kqukdhy9",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxky0ua3ha84qk8",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx9eheesxadh2n2n9",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx9llwmgesfulcj2z",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx02ev7caq6n9fgkf",
]

OTHER_INVALID = [
    "ms10fauxxxxxxxxxxxxxxxxxxxxxxxxxxxx0z26tfn0ulw3p",
    "ms1fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxda3kr3s0s2swg",
    "0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "m10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "s10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxhkd4f70m8lgws",
    "10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxhkd4f70m8lgws",
    "m10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxx8t28z74x8hs4l",
    "s10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxh9d0fhnvfyx3x",
    "Ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "mS10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "MS10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10FAUXsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10fauxSxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10fauxsXXXXXXXXXXXXXXXXXXXXXXXXXXuqxkk05lyf3x2",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxUQXKK05LYF3X2",
]

ALL_INVALID = INVALID_CHECKSUM + WRONG_CHECKSUM_FOR_SIZE + IMPROPER_LENGTH + OTHER_INVALID
check("invalid vector count", len(ALL_INVALID), 64)
for i, s in enumerate(ALL_INVALID):
    check_raises(f"invalid vector {i:02d}", validate, s)

# ---- Edge cases and API behavior ---------------------------------------

# The 94-95 data-character gap: valid regular checksum on 94 data chars
# must be rejected (never legal per BIP93).
gap = codex32.ms32_polymod
gap_data = [CHARSET.index("q")] * 81  # 81 data + 13 checksum = 94 chars
gap_str = "ms1" + "".join(CHARSET[d] for d in gap_data)
polymod = codex32.ms32_polymod(gap_data + [0] * 13) ^ codex32.MS32_CONST
gap_str += "".join(CHARSET[(polymod >> 5 * (12 - i)) & 31] for i in range(13))
check_raises("94-char data gap rejected", validate, gap_str)

# Split then recover round trip with fixed entropy.
ENTROPY = bytes(range(1, 34))
shares = split(bytes.fromhex(TV3_SEED), 3, 5, "c0rk", ENTROPY)
check("split share count", len(shares), 5)
check("split indexes", "".join(s[8] for s in shares), "acdef")
rec = recover([shares[0], shares[2], shares[4]])
check("split/recover seed", decode_secret(rec)[1].hex(), TV3_SEED)
check("split determinism", split(bytes.fromhex(TV3_SEED), 3, 5, "c0rk", ENTROPY), shares)

# Split reproduces TV3 exactly when the entropy encodes the TV3 shares.
tv3_vals = [CHARSET.index(c) for c in "320zyxwvutsrqpnmlkjhgfedca" + "acdefghjklmnpqrstuvwxyz023"]
acc = 0
for v in tv3_vals:
    acc = (acc << 5) | v
acc <<= 4  # pad 260 bits to 33 bytes
tv3_entropy = acc.to_bytes(33, "big")
check(
    "split reproduces tv3",
    split(bytes.fromhex(TV3_SEED), 3, 5, "cash", tv3_entropy),
    [TV3_A, TV3_C, TV3_D, TV3_E, TV3_F],
)

# Refusals.
check_raises("duplicate share rejected", recover, [TV3_A, TV3_A, TV3_C])
check_raises("too few shares rejected", recover, [TV3_A, TV3_C])
check_raises("too many shares rejected", recover, [TV3_A, TV3_C, TV3_D, TV3_E])
check_raises("mixed identifier rejected", recover, [TV3_A, TV3_C, "ms13cormd" + TV3_D[9:]])
check_raises("secret in share set rejected", recover, [TV3_S, TV3_A, TV3_C])
check_raises("decode_secret on a share", decode_secret, TV3_A)
check_raises("bad threshold in encode", encode_secret, "test", bytes(16), 1)
check_raises("short seed in encode", encode_secret, "test", bytes(15), 0)
check_raises("insufficient entropy", split, bytes.fromhex(TV3_SEED), 3, 5, "c0rk", b"\x00" * 8)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURES")
    for f in FAILURES:
        print(f)
    sys.exit(1)
print("all codex32 tests passed")
