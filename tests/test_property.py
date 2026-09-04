"""Property-based and fuzz tests for Corky. Run: python3 tests/test_property.py

A-22 cut this suite from five properties to three. The shim, codex32 and
SeedQR properties went with the modules they tested: the pure signer has no
code that transforms secret material, so there is nothing left to
cross-check against an oracle.

What remains guards the two things Corky still does with untrusted input,
and the one number it computes:

  1. PSBT boundary fuzz: FrameAssembler.feed and read_psbt never raise an
     uncaught exception on garbage, only their controlled errors.
  2. Fee and amount Decimal arithmetic in describe_psbt is exact.
"""
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))

import qrchannel      # noqa: E402
import filechannel    # noqa: E402
import signer         # noqa: E402

EXAMPLES = 200


# ---- Property 1: PSBT boundary fuzz (no crash) ------------------------

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


def sats_to_btc(sats: int) -> Decimal:
    return (Decimal(sats) / Decimal(10**8)).quantize(Decimal("0.00000001"))


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


def main():
    checks = [
        ("qr feed no-crash fuzz", prop_qr_feed_no_crash),
        ("read_psbt no-crash fuzz", prop_read_psbt_no_crash),
        ("fee Decimal exact", prop_fee_decimal_exact),
    ]
    failed = 0
    for name, fn in checks:
        try:
            fn()
            print(f"ok   {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\nPROPERTY TESTS {'PASS' if not failed else 'FAILED'} "
          f"({len(checks) - failed}/{len(checks)}, {EXAMPLES}+ examples each)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
