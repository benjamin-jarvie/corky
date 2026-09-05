# T1 Which policies Sparrow accepts from Corky's QR

Type: `wayfinder:task`, HITL. Blocked by: T0.

## Question

Ben has the Sparrow laptop. For each of the four policies, show the
descriptor QR on the board and try to import it into Sparrow as a new
watch-only wallet.

Record, per policy: does Sparrow accept the QR at all; what wallet type
does it call it; does the first receive address it derives match the
address the board shows under Receiving addresses for that same policy.

The address comparison is the check that matters. Sparrow accepting a
string proves it parsed it; matching addresses proves it parsed it the
same way Core did. TESTING.md rule 8: run the counterpart, do not model it.

Sparrow's own library already parses Core's `wpkh` and `tr` descriptors
verbatim and derives identical addresses, proved on 2026-09-04 in
`tests/sparrow/test_export_interop.py`. That is the library. This ticket
is the application, driven by hand, which is a different claim.
