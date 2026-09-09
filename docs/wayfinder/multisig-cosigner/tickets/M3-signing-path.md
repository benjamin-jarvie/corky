# M3 What changes in the signing path?

Type: `wayfinder:grilling`, HITL. **Blocked by M1.**

## Question

Charting established that Core signs a quorum share with only the BIP48
branch imported as an ordinary single-sig descriptor, so the mechanism
is already there. What is undecided is everything the person sees.

- **The review screen.** `describe_psbt` already returns outputs, fee and
  input count for a multisig PSBT. It does not say that this input needs
  more signatures than yours, and `next_role` (`signer`) is on the screen
  nowhere. Signing something that then sits unspendable until two other
  people act is a different act from signing something final, and the
  screen currently cannot tell them apart.
- **What the result screen says.** Today a signature that completes says
  SIGNED. A partial signature is not complete and never will be on this
  device. `walletprocesspsbt` returns `complete: false`, which today
  reaches "wallet cannot complete this PSBT" and refuses. That refusal is
  correct for single-sig and wrong for a quorum.
- **Whether Corky says anything about the other cosigners.**
  `signer.owners` already reads all three fingerprints out of the PSBT.
  Showing them lets a person notice that a "2-of-3 with two friends" has
  two fingerprints they do not recognise. Corky cannot verify a quorum it
  does not hold, so this is the only check available, and whether it is
  worth a screen is a judgement.

Depends on M1 only for how many shapes have to work.
