# M4 Does Sparrow accept Corky's cosigner export?

Type: `wayfinder:task`, AFK. **Blocked by M1, M2 (both closed).**
Claimed and resolved 2026-09-10.

## Question

TESTING.md rule 8: an interop claim tested with your own tools is not an
interop claim. Charting proved Sparrow's library builds a quorum from a
Core MASTER key. It has not been asked whether it accepts the cosigner
descriptor Corky would actually export.

Drive Sparrow's own library, out of the verified 2.5.4 release already in
`tests/sparrow/`:

1. Corky exports its cosigner descriptor for each script type M1 picked.
2. Sparrow imports it as one keystore of a 2-of-3.
3. The addresses Sparrow derives match the ones Core derives for the same
   quorum.
4. The coordinator builds a PSBT, Corky signs its share, Sparrow's
   library combines and finalises with a second key, and Core says the
   network would accept it.

Resolved when that runs green in `tests/sparrow/`. The answer records
which format Sparrow took and which it refused, because that is the fact
M2 was guessing at.


## Answer

**Sparrow accepts it, signs beside it, and keeps our signature.**
`tests/sparrow/test_cosigner.py`, 20 checks green, driving Sparrow's own
drongo out of the verified 2.5.4 release. Run against Core 31.1 on
regtest, for TWO paths: ordinary `48h/1h/0h/2h`, and a 93-bit blinded
path of the shape buidl's `secure_secret_path` builds.

### The format Sparrow took

The one M7 picked, unchanged: a bare key expression on one line,
`[73c5da0a/48h/1h/0h/2h]tpub…`, with the `/0/*` suffix stripped. Nothing
was refused, so M7's answer needs no correction. `signer.cosigner_key()`
produces it by the scratch-wallet round trip `write_watch_only` already
uses.

### What runs green

1. The record is a bare key expression carrying an 8-hex origin and the
   path asked for.
2. Sparrow builds the 2-of-3 and derives the same addresses Core does,
   independently, for both paths.
3. Sparrow sees three keystores and finds ours among them, at our path.
4. Corky signs **one** share and does not finish the PSBT.
5. **Chained**: Sparrow signs on top of Corky's PSBT and keeps our
   signature. Two signatures, finalised.
6. **Combined**: both sign the original, `combinepsbt` merges. Two
   signatures, finalised.
7. **Both routes reach identical transaction hex.**
8. `testmempoolaccept` allows the spend.

### The chained route is the finding

Point 5 is the one that matters for an air-gapped device, and it was not
on the ticket. Corky's real flow is chained: the coordinator sends a
PSBT, Corky signs it, the signed PSBT returns by QR, and the coordinator
signs the SAME object on top. That only works if Sparrow preserves a
partial signature it did not make. It does. `wallet.sign(psbt)` signs in
place and adds to what is there.

Both routes producing identical hex says the two are interchangeable, so
a coordinator can use either and Corky does not care which.

### The bug this ticket nearly shipped

The first version of check 4 asserted `complete is False` and passed
while Corky signed **nothing**. `complete is False` is also true for zero
signatures. The cause: `sign_psbt` was called with the session wallet,
which holds the four standard policies and has no key at a BIP48 path at
all. The test then read "1 signature" after Sparrow and blamed Sparrow
for dropping ours, when the count was Sparrow's own signature alone.

Both checks now **count `partial_signatures`**. Five mutations confirm
they bite, including the original bug replayed exactly, which reports
`0 signature` and fails.

### The one thing this does NOT prove

The test imports Corky's BIP48 branch into a scratch wallet before
signing. That stands in for M3's decision that the device reads the path
out of the PSBT and imports it, which is **not built**. So M4 proves the
interop and the format. It does not prove the device's flow, and M3's
build is still what closes that gap.
