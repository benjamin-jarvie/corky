# M4 Does Sparrow accept Corky's cosigner export?

Type: `wayfinder:task`, AFK. **Blocked by M1, M2.**

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
