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
import base64
import shutil
import time
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


def _no_key_in_argv(method, params, stdin):
    """A private key may never travel as a command-line argument.

    Rpc.call's own rule: "Callers that pass an xprv or a private
    descriptor MUST set it (S4)", because argv is visible in a process
    listing. The rule was documented and every caller obeyed it, and then
    `signer.identity_of_key` shipped without it on 2026-09-05, carrying
    the master private key twice per paper check. The two-axis review
    found it; nothing in this suite did, because the only stdin assertion
    here named three PSBT methods.

    So the check is on the ARGUMENT rather than the method name. Any call
    is refused if a parameter contains a private-key prefix and stdin is
    off, whatever the method is called, including one that does not exist
    yet.
    """
    if stdin:
        return
    for p in params:
        if isinstance(p, str) and any(x in p for x in signer.XPRV_PREFIXES):
            raise AssertionError(
                f"{method} put key material in argv, where a process "
                f"listing shows it. Pass stdin=True (Rpc.call, S4).")


class FakeRpc:
    """Returns canned decodepsbt/analyzepsbt; exercises the Decimal path."""
    def __init__(self, decoded, analysis):
        self._decoded = decoded
        self._analysis = analysis

    def call(self, method, *params, wallet=None, stdin=False, drop=()):
        # stdin is not optional for a PSBT-carrying call: on Linux a PSBT
        # is too long to pass as one argv entry (I-10). The double asserts
        # it rather than accepting it, so a regression fails here on the
        # dev machine, where the real execve limit cannot be reached.
        if method in ("decodepsbt", "analyzepsbt", "walletprocesspsbt"):
            assert stdin, f"{method} must pass the PSBT through stdin"
        # Same shape of rule, same reason. decodepsbt's answer holds the
        # whole previous transaction for every input, and building all of
        # them cost 20.7MB of a 21.1MB tree at 250 batch-funded inputs.
        # That only matters on a 512MB board, so it cannot be felt here
        # and has to be asserted here instead (TESTING.md rule 9).
        if method == "decodepsbt":
            assert "non_witness_utxo" in drop, (
                "decodepsbt must drop non_witness_utxo: it is 20.7MB of "
                "previous transactions the review screen never reads")
        _no_key_in_argv(method, params, stdin)
        if method == "decodepsbt":
            return self._decoded
        if method == "analyzepsbt":
            return self._analysis
        raise AssertionError(method)


# --- every signer entry point that takes key material ------------------
# The generic guard above only fires for calls that actually happen, and
# the property tests never touch the key paths. So walk them explicitly:
# hand each one a real private key and assert it never reached argv.

KEY = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ss"
       "vpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")


class ArgvWatcher:
    """Answers enough for the key paths, and refuses key material in argv."""

    chain = "regtest"

    def __init__(self):
        self.methods = []

    def call(self, method, *params, wallet=None, stdin=False, drop=()):
        self.methods.append(method)
        _no_key_in_argv(method, params, stdin)
        if method == "getdescriptorinfo":
            return {"checksum": "aaaaaaaa",
                    "descriptor": "wpkh(tpubDEADBEEF)#aaaaaaaa"}
        if method == "importdescriptors":
            return [{"success": True}]
        if method == "listwallets":
            return []
        if method == "listwalletdir":
            return {"wallets": []}
        if method == "listdescriptors":
            return {"descriptors": []}
        return ""


def prop_amounts_never_become_floats():
    """A BTC amount reaches Core as a string, never a binary float.

    `signer._json_decimal` is what makes that true, and audit A5 found it
    had never executed: every test happened to pass amounts that were
    already strings. It guards the review screen, which is where a user
    decides whether to sign, and a float there is how 0.1 + 0.2 becomes
    0.30000000000000004 on the one screen that must not lie.
    """
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw.get("input")

        class R:
            returncode, stdout, stderr = 0, '"ok"', ""
        return R()

    real = signer.subprocess.run
    signer.subprocess.run = fake_run
    try:
        rpc = signer.Rpc("/nonexistent", chain="regtest")
        # The shape walletcreatefundedpsbt takes: a list of {address: amount}
        rpc.call("walletcreatefundedpsbt", [],
                 [{"bcrt1qexample": Decimal("0.1")},
                  {"bcrt1qother": Decimal("21000000.00000001")}])
        blob = " ".join(str(a) for a in seen["cmd"])
        assert "0.1" in blob, f"the amount never reached Core: {blob[-120:]}"
        assert "21000000.00000001" in blob, \
            "a 21-million-BTC amount lost precision on the way to Core"
        assert "0.10000000000000000555" not in blob and "e-" not in blob, \
            f"an amount was rendered as a float: {blob[-120:]}"
        # And a type it does not know must be refused, not silently coerced.
        try:
            rpc.call("anything", object())
            raise AssertionError("_json_decimal accepted an unknown type")
        except TypeError:
            pass
    finally:
        signer.subprocess.run = real


def prop_rpc_routes_keys_itself():
    """Rpc.call keeps key material off argv without being asked.

    The check below this one drives FAKES, so it asserts what CALLERS do.
    This one drives the real Rpc and asserts what the MODULE does, which
    is the difference between a rule written in a docstring and a rule
    that holds. Only subprocess.run is replaced, so the command Corky
    would have executed is the thing under test.
    """
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw.get("input")

        class R:
            returncode, stdout, stderr = 0, '"ok"', ""
        return R()

    real = signer.subprocess.run
    signer.subprocess.run = fake_run
    try:
        rpc = signer.Rpc("/nonexistent", chain="regtest")
        # A caller that forgets. This is the 2026-09-05 defect exactly.
        rpc.call("getdescriptorinfo", f"wpkh({KEY})")
        assert not any(KEY in str(a) for a in seen["cmd"]), \
            "Rpc.call let a private key onto argv"
        assert KEY in (seen["input"] or ""), \
            "Rpc.call dropped the key instead of routing it to stdin"
        # And a call with nothing secret in it is left alone, so the
        # protection costs nothing everywhere else.
        rpc.call("getblockcount")
        assert "-stdin" not in seen["cmd"], \
            "Rpc.call used -stdin for a call with no key material"
    finally:
        signer.subprocess.run = real


def prop_no_key_in_argv():
    """Every signer entry point that takes key material uses stdin."""
    for name, run in (
            ("build_descriptors",
             lambda r: signer.build_descriptors(r, KEY)),
            ("opens_wallet",
             lambda r: signer.opens_wallet(r, "w", KEY)),
            ("open_session_descriptors",
             lambda r: signer.open_session_descriptors(
                 r, [f"wpkh({KEY}/84h/1h/0h/0/*)"])),
    ):
        try:
            run(ArgvWatcher())
        except AssertionError:
            raise
        except Exception as exc:                   # noqa: BLE001
            # A fake this thin cannot satisfy every path. What matters is
            # that no key reached argv before it gave up, and _no_key_in_argv
            # raises AssertionError, which is re-raised above.
            if "argv" in str(exc):
                raise AssertionError(f"{name}: {exc}") from None


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


def prop_a_slow_node_does_not_freeze_the_device():
    """A node that never answers must become an error, not a hang.

    Absent bitcoind fails fast, so every suite covered that and none
    covered the middle case: a node holding its socket and answering
    nothing. `subprocess.run` had NO timeout, so the call blocked for
    ever and the panel stayed on a busy screen with no way out and no
    shell to fix it from. Measured with SIGSTOP on a live node (audit A4,
    2026-09-06); it was still blocked after 45 seconds.

    Faked here with a `bitcoin-cli` that sleeps, because the property
    under test is the timeout and not the node. RuntimeError is the
    required type: it is what `Session.HANDLED` catches, so the panel
    shows a message it can dismiss.
    """
    import subprocess as sp
    import tempfile
    sleeper = Path(tempfile.mkdtemp()) / "bitcoin-cli"
    sleeper.write_text("#!/bin/sh\nsleep 60\n")
    sleeper.chmod(0o755)
    rpc = signer.Rpc("/nonexistent", chain="regtest", cli=str(sleeper))
    was = signer.RPC_TIMEOUT
    signer.RPC_TIMEOUT = 1.0
    t0 = time.monotonic()
    try:
        rpc.call("getblockchaininfo")
        raise AssertionError("a node that never answers returned normally")
    except RuntimeError as exc:
        took = time.monotonic() - t0
        assert "did not answer" in str(exc), f"wrong message: {exc}"
        assert took < 10, f"gave up after {took:.0f}s, not about 1s"
    except sp.TimeoutExpired:
        raise AssertionError(
            "TimeoutExpired reaches the caller. Session.HANDLED does not "
            "catch it, so this ends the process instead of painting an "
            "error") from None
    finally:
        signer.RPC_TIMEOUT = was
        shutil.rmtree(sleeper.parent, ignore_errors=True)
    # And the cap has to stay far above real work, or it breaks the
    # working case: the slowest call measured on the board is 4.4s.
    assert was >= 60, f"RPC_TIMEOUT is {was}s, too close to real work"


def prop_too_many_inputs_is_refused_not_signed():
    """A PSBT past the board's memory limit is refused, and one under it
    is not.

    Measured on a Zero 2 W: 250 batch-funded inputs leave 72MB where
    100MB is required, and the kernel then kills whichever process asks
    for the next page. That can be bitcoind, holding the only copy of a
    signature. Refusing on a screen beats dying half way through.

    Driven through the real `state_review`, with a Core that answers as
    Core does, because the point is the wiring and not the arithmetic.
    The limit itself cannot be reached on a dev machine, so it is
    asserted here instead (TESTING.md rule 9).
    """
    import hal
    import main as corky_main
    import screens

    class Painted:
        width, height = 320, 240

        def __init__(self):
            self.shown = []

        def show(self, image, sensitive=False):
            self.shown.append(image)

    class Answers:
        chain = "regtest"

        def __init__(self, n):
            self.n = n

        def call(self, method, *params, wallet=None, stdin=False, drop=()):
            if method == "decodepsbt":
                return {"tx": {"vout": [{"value": Decimal("1"),
                                         "scriptPubKey": {"address": "bcrt1q"}}],
                               "vin": [{}] * self.n},
                        "fee": Decimal("0.0001"),
                        "inputs": [{}] * self.n}
            if method == "analyzepsbt":
                return {"next": "signer"}
            if method == "listdescriptors":
                return {"descriptors": [{"desc": "wpkh([73c5da0a/84h/1h/0h]x)"}]}
            if method == "walletprocesspsbt":
                # Reached only by the UNDER-limit run, which is the half
                # that proves the guard does not refuse real work.
                return {"psbt": base64.b64encode(b"psbt\xffsigned").decode(),
                        "complete": True}
            return ""

    limit = corky_main.MAX_SIGNABLE_INPUTS
    # Pin the VALUE against the board, not just the wiring. Reading the
    # constant and testing limit+1 follows the code wherever it goes:
    # setting it to 1 passed this check until the band below was added.
    # 200 inputs measured 78MB of headroom against 100MB required, and
    # 175 measured 114MB, so anything from 200 up ships a known failure
    # and anything under 100 refuses transactions the board can hold.
    if not 100 <= limit < 200:
        raise AssertionError(
            f"MAX_SIGNABLE_INPUTS is {limit}. The board was measured at "
            "114MB of headroom on 175 inputs and 78MB on 200, against "
            "100MB required, so the limit belongs between 100 and 199")
    for n, want_refusal in ((limit + 1, True), (limit, False)):
        disp = Painted()
        sess = corky_main.Session(disp, hal.DevButtons("a" * 40),
                                  rpc=Answers(n), animate=False,
                                  on_device=False)
        sess.keys = [corky_main.LoadedKey("corky-73c5da0a", "73c5da0a")] \
            if hasattr(corky_main, "LoadedKey") else []
        sess._key_for = lambda _psbt: "corky-73c5da0a"
        try:
            sess.state_review("cHNidP8B", None)
        except hal.ScriptExhausted:
            pass
        refusal = screens.result(
            320, 240, ok=False,
            detail=f"{n} inputs; this board signs up to {limit}")
        drew = any(f.tobytes() == refusal.tobytes() for f in disp.shown)
        if want_refusal and not drew:
            raise AssertionError(
                f"{n} inputs is past the {limit} the board can hold, and "
                "the device did not refuse it")
        if not want_refusal and drew:
            raise AssertionError(
                f"{n} inputs is within the limit and was refused anyway; "
                "a guard that refuses real work is worse than no guard")


def main():
    checks = [
        ("qr feed no-crash fuzz", prop_qr_feed_no_crash),
        ("read_psbt no-crash fuzz", prop_read_psbt_no_crash),
        ("fee Decimal exact", prop_fee_decimal_exact),
        ("no key material in argv", prop_no_key_in_argv),
        ("Rpc routes keys to stdin itself", prop_rpc_routes_keys_itself),
        ("amounts never become floats", prop_amounts_never_become_floats),
        ("a slow node does not freeze the device",
         prop_a_slow_node_does_not_freeze_the_device),
        ("too many inputs is refused, not signed",
         prop_too_many_inputs_is_refused_not_signed),
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
