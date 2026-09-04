"""Property-based and fuzz tests for Corky. Run: python3 tests/test_property.py

Uses hypothesis (property-based) plus simple fuzz loops. Five properties:

  1. SHIM round-trip and cross-check against an independent oracle
     (bip-utils on arm64) over random valid BIP39 entropy.
  2. codex32 round-trip, split/recover, k-1 failure and checksum properties.
  3. SeedQR decode/re-encode consistency and out-of-range rejection.
  4. PSBT boundary fuzz: FrameAssembler.feed and read_psbt never raise an
     uncaught exception on garbage input, only their controlled errors.
  5. Fee/amount Decimal arithmetic in describe_psbt is exact.

Oracle used: bip-utils (Bip39SeedGenerator + Bip32Slip10Secp256k1) on arm64.
"""
import hashlib
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))

import bip39_shim
import codex32
import seedqr
import qrchannel
import filechannel
import signer

from bip_utils import Bip39SeedGenerator, Bip32Slip10Secp256k1

EXAMPLES = 200
_WORDLIST = bip39_shim.load_wordlist()


def entropy_to_mnemonic(entropy: bytes) -> str:
    """Build a checksummed BIP39 mnemonic from entropy (16/20/24/28/32 bytes)."""
    checksum_bits = len(entropy) * 8 // 32
    check = format(hashlib.sha256(entropy).digest()[0], "08b")[:checksum_bits]
    bits = "".join(format(b, "08b") for b in entropy) + check
    return " ".join(_WORDLIST[int(bits[i:i + 11], 2)]
                    for i in range(0, len(bits), 11))


# ---- Property 1: SHIM round-trip and cross-check -----------------------

@given(entropy=st.binary(min_size=16, max_size=32).filter(
    lambda b: len(b) in (16, 20, 24, 28, 32)))
@settings(max_examples=EXAMPLES, deadline=None)
def prop_shim_crosscheck(entropy):
    mnemonic = entropy_to_mnemonic(entropy)
    # Corky's shim.
    xprv = bip39_shim.mnemonic_to_xprv(mnemonic, mainnet=True)
    # Independent oracle: bip-utils.
    seed = Bip39SeedGenerator(mnemonic).Generate()
    ref_xprv = Bip32Slip10Secp256k1.FromSeed(seed).PrivateKey().ToExtended()
    assert xprv == ref_xprv, f"xprv mismatch\n corky={xprv}\n ref  ={ref_xprv}"
    # And the shim's own seed matches the oracle's seed.
    assert bip39_shim.mnemonic_to_seed(mnemonic) == seed


# ---- Property 2: codex32 round-trip, split/recover, checksum ------------

_IDENT = st.text(alphabet=codex32.CHARSET, min_size=4, max_size=4)


@given(seed=st.binary(min_size=16, max_size=32).filter(
           lambda b: len(b) in (16, 32)),
       ident=_IDENT)
@settings(max_examples=EXAMPLES, deadline=None)
def prop_codex32_secret_roundtrip(seed, ident):
    s = codex32.encode_secret(ident, seed)
    got_ident, got_seed = codex32.decode_secret(s)
    assert got_seed == seed
    assert got_ident == ident.lower()
    assert codex32.validate(s) == s.lower()


@given(seed=st.binary(min_size=16, max_size=32).filter(
           lambda b: len(b) in (16, 32)),
       ident=_IDENT,
       kn=st.tuples(st.integers(2, 9), st.integers(2, 9)).map(
           lambda t: (min(t), max(t))),
       rand=st.binary(min_size=300, max_size=600),
       subset_seed=st.integers(min_value=0, max_value=2**32))
@settings(max_examples=EXAMPLES, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
def prop_codex32_split_recover(seed, ident, kn, rand, subset_seed):
    k, n = kn
    shares = codex32.split(seed, k, n, ident, rand)
    assert len(shares) == n
    # Deterministic k-subset from subset_seed.
    import random
    rng = random.Random(subset_seed)
    chosen = rng.sample(shares, k)
    recovered = codex32.recover(chosen)
    _, rseed = codex32.decode_secret(recovered)
    assert rseed_eq(rseed=rseed, seed=seed)
    # k-1 shares must be rejected (wrong count) for this threshold.
    try:
        codex32.recover(chosen[:k - 1])
        assert False, "recover accepted k-1 shares"
    except codex32.Codex32Error:
        pass


def rseed_eq(rseed, seed):
    return rseed == seed


@given(seed=st.binary(min_size=16, max_size=16),
       ident=_IDENT,
       pos=st.integers(min_value=0),
       repl=st.integers(min_value=0, max_value=31))
@settings(max_examples=EXAMPLES, deadline=None)
def prop_codex32_flip_breaks_checksum(seed, ident, pos, repl):
    s = codex32.encode_secret(ident, seed)
    # Flip one payload/checksum char after the 'ms1' + header prefix.
    body_start = s.index("1") + 1
    idx = body_start + (pos % (len(s) - body_start))
    new_c = codex32.CHARSET[repl]
    if new_c == s[idx]:
        new_c = codex32.CHARSET[(repl + 1) % 32]
    flipped = s[:idx] + new_c + s[idx + 1:]
    if flipped == s:
        return
    try:
        codex32.validate(flipped)
        # A valid checksum after a single-char flip is a checksum failure
        # of the property only if it actually decodes; ms32 detects all
        # single-char substitutions, so this must raise.
        assert False, f"flipped char passed validate: {flipped}"
    except codex32.Codex32Error:
        pass


# ---- Property 3: SeedQR decode/re-encode ------------------------------

@given(indices=st.lists(st.integers(0, 2047), min_size=12, max_size=24)
       .filter(lambda x: len(x) in (12, 15, 18, 21, 24)))
@settings(max_examples=EXAMPLES, deadline=None)
def prop_seedqr_roundtrip(indices):
    digits = "".join(f"{i:04d}" for i in indices)
    words = seedqr.decode_standard(digits)
    # Re-encode words back to indices and compare.
    index = {w: i for i, w in enumerate(_WORDLIST)}
    re_digits = "".join(f"{index[w]:04d}" for w in words.split())
    assert re_digits == digits


@given(bad=st.integers(2048, 9999),
       tail=st.lists(st.integers(0, 2047), min_size=11, max_size=11))
@settings(max_examples=EXAMPLES, deadline=None)
def prop_seedqr_out_of_range_raises(bad, tail):
    digits = f"{bad:04d}" + "".join(f"{i:04d}" for i in tail)
    try:
        seedqr.decode_standard(digits)
        assert False, f"accepted out-of-range group {bad}"
    except seedqr.SeedQrError:
        pass


# ---- Property 4: PSBT boundary fuzz (no crash) ------------------------

_UR_PREFIXES = ["", "ur:crypto-psbt/", "ur:crypto-psbt/1-3/", "UR:CRYPTO-PSBT/",
                "ur:crypto-seed/", "ur:", "ur:crypto-psbt"]


@given(prefix=st.sampled_from(_UR_PREFIXES),
       body=st.text(min_size=0, max_size=400))
@settings(max_examples=EXAMPLES * 3, deadline=None)
def prop_qr_feed_no_crash(prefix, body):
    fa = qrchannel.FrameAssembler()
    frame = prefix + body
    try:
        result = fa.feed(frame)
        assert isinstance(result, bool)
    except qrchannel.QrChannelError:
        pass  # controlled failure is allowed


@given(data=st.binary(min_size=0, max_size=500))
@settings(max_examples=EXAMPLES * 3, deadline=None)
def prop_read_psbt_no_crash(data):
    with tempfile.NamedTemporaryFile(suffix=".psbt", delete=False) as f:
        f.write(data)
        p = Path(f.name)
    try:
        try:
            out = filechannel.read_psbt(p)
            assert isinstance(out, str)
        except filechannel.FileChannelError:
            pass  # controlled failure (empty/oversize) is allowed
    finally:
        p.unlink(missing_ok=True)


# ---- Property 5: fee/amount Decimal arithmetic ------------------------

class FakeRpc:
    """Returns canned decodepsbt/analyzepsbt; exercises the Decimal path."""
    def __init__(self, decoded, analysis):
        self._decoded = decoded
        self._analysis = analysis

    def call(self, method, *params, wallet=None, stdin=False):
        # stdin is not optional for a PSBT-carrying call: on Linux a PSBT
        # is too long to pass as one argv entry (I-10). The double asserts
        # it rather than accepting it, so a regression fails here on the
        # dev machine, where the real execve limit cannot be reached.
        if method in ("decodepsbt", "analyzepsbt", "walletprocesspsbt"):
            assert stdin, f"{method} must pass the PSBT through stdin"
        if method == "decodepsbt":
            return self._decoded
        if method == "analyzepsbt":
            return self._analysis
        raise AssertionError(method)


def sats_to_btc(sats: int) -> Decimal:
    return (Decimal(sats) / Decimal(10**8)).quantize(Decimal("0.00000001"))


@given(inputs=st.lists(st.integers(1, 21_000_000 * 10**8), min_size=1, max_size=8),
       out_frac=st.integers(1, 999))
@settings(max_examples=EXAMPLES, deadline=None)
def prop_fee_decimal_exact(inputs, out_frac):
    input_total_sats = sum(inputs)
    # One output taking a fraction; the remainder is the fee.
    out_sats = max(1, input_total_sats * out_frac // 1000)
    if out_sats >= input_total_sats:
        out_sats = input_total_sats - 1
    fee_sats = input_total_sats - out_sats
    input_total_btc = sum(sats_to_btc(s) for s in inputs)
    out_btc = sats_to_btc(out_sats)
    fee_btc = input_total_btc - out_btc

    decoded = {
        "tx": {"vout": [{"scriptPubKey": {"address": "bcrt1qtest"},
                         "value": out_btc}],
               "vin": [{} for _ in inputs]},
        "inputs": [{"witness_utxo": {"amount": sats_to_btc(s)}} for s in inputs],
        "fee": fee_btc,
    }
    analysis = {"next": "signer"}
    result = signer.describe_psbt(FakeRpc(decoded, analysis), "dummy")

    # describe_psbt sums witness amounts via Decimal(str(amount)); assert exact.
    assert result["input_total_btc"] == input_total_btc
    # Fee equals inputs_total - outputs_total exactly (Decimal, no loss).
    assert result["fee_btc"] == input_total_btc - out_btc
    assert result["fee_btc"] == fee_btc
    # Cross-check against integer-sat arithmetic (the ground truth).
    assert result["fee_btc"] == sats_to_btc(fee_sats)


# ---- Runner -----------------------------------------------------------

def main():
    tests = [
        ("shim cross-check (bip-utils oracle)", prop_shim_crosscheck),
        ("codex32 secret round-trip", prop_codex32_secret_roundtrip),
        ("codex32 split/recover + k-1 fails", prop_codex32_split_recover),
        ("codex32 single-flip breaks checksum", prop_codex32_flip_breaks_checksum),
        ("seedqr decode/re-encode round-trip", prop_seedqr_roundtrip),
        ("seedqr >2047 group raises", prop_seedqr_out_of_range_raises),
        ("qr feed no-crash fuzz", prop_qr_feed_no_crash),
        ("read_psbt no-crash fuzz", prop_read_psbt_no_crash),
        ("fee Decimal exact", prop_fee_decimal_exact),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"\nPROPERTY TESTS FAILED ({failed}/{len(tests)})")
        sys.exit(1)
    print(f"\nPROPERTY TESTS PASS ({len(tests)}/{len(tests)}, {EXAMPLES}+ examples each)")


if __name__ == "__main__":
    main()
