# 07 Do Corky's numbers match Sparrow's

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

The M1 gate (`PLAN.md:377`) is "fee and outputs on screen match Sparrow".
That is testable today with no camera and no board.

`tests/sparrow/` already builds PSBTs with Sparrow's own library. Extend it:
for every case in the matrix, compare Corky's `describe_psbt` output against
the fee, output addresses and output amounts that Sparrow itself computes
from the same `WalletTransaction`. Any disagreement is a gate failure found
months before the gate.

Note the known asymmetry. Corky's fee comes from coordinator-supplied input
amounts and the README already says an air-gapped signer cannot verify them.
This ticket checks agreement, not independent verification.

## Resolution (2026-09-03)

Done, and green. `SparrowGen` now also emits `FEE` and `VOUT` marker lines
taken from `WalletTransaction.getFee()` and `getOutputs()`, which is what
Sparrow puts on its own review screen. `test_sparrow_interop.py` compares them
against Corky's `describe_psbt` for every case in the matrix.

**16 new checks, all passing.** Fee agrees to the satoshi and the output set
agrees by address and amount, across both script types and all eight
transaction shapes: 1, 2, 3 and 10 inputs, change-branch input, mixed
branches, two payments, and send-max with no change.

The suite is now 38 checks.

Amounts are compared as integer satoshis. Corky's `describe_psbt` keeps BTC as
`Decimal` on purpose (`signer.py` parses with `parse_float=Decimal`), so the
conversion is exact and no binary float enters the comparison.

The known asymmetry stands and is unchanged by this ticket. Corky's fee is
computed by Core from coordinator-supplied input amounts. An air-gapped signer
cannot verify those against the chain, and the README says so. This ticket
proves the two agree, which is what the M1 gate asks. It does not prove either
is independently true.

Closed. The M1 gate's first half is met months before the gate.
