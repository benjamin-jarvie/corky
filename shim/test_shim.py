"""Official test vectors for the shim. Run: python3 test_shim.py

Sources:
  BIP39 vectors: bitcoin/bips bip-0039 (Trezor vectors, passphrase "TREZOR")
  BIP32 vector 1: bitcoin/bips bip-0032
  The abandon-x11+about xprv (empty passphrase) is the canonical test wallet
  (master fingerprint 73c5da0a) used across the ecosystem.
"""

import sys
from bip39_shim import (
    validate_mnemonic,
    mnemonic_to_seed,
    seed_to_xprv,
    mnemonic_to_xprv,
)

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}\n  got:  {got}\n  want: {want}")
        print(f"FAIL {name}")
    else:
        print(f"ok   {name}")


ABANDON12 = "abandon " * 11 + "about"

# BIP39 Trezor vector 1: entropy 00*16, passphrase TREZOR
check(
    "bip39 vector 1 seed (TREZOR passphrase)",
    mnemonic_to_seed(ABANDON12, "TREZOR").hex(),
    "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f"
    "09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04",
)

# BIP32 vector 1: seed 000102030405060708090a0b0c0d0e0f -> master xprv
check(
    "bip32 vector 1 master xprv",
    seed_to_xprv(bytes.fromhex("000102030405060708090a0b0c0d0e0f")),
    "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNK"
    "mPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi",
)

# End to end: canonical test mnemonic, empty passphrase
check(
    "abandon-about master xprv (empty passphrase)",
    mnemonic_to_xprv(ABANDON12),
    "xprv9s21ZrQH143K3GJpoapnV8SFfukcVBSfeCficPSGfubmSFDxo1kuHnLisriDvSn"
    "RRuL2Qrg5ggqHKNVpxR86QEC8w35uxmGoggxtQTPvfUu",
)

# Validation catches a wrong word
try:
    validate_mnemonic(ABANDON12.replace("about", "abandon"))
    FAILURES.append("checksum: bad mnemonic accepted")
    print("FAIL checksum rejection")
except ValueError:
    print("ok   checksum rejection")

# Validation catches a non-list word
try:
    validate_mnemonic(ABANDON12.replace("about", "aotearoa"))
    FAILURES.append("wordlist: unknown word accepted")
    print("FAIL unknown-word rejection")
except ValueError:
    print("ok   unknown-word rejection")

if FAILURES:
    print("\n" + "\n".join(FAILURES))
    sys.exit(1)
print("\nall vectors pass")
