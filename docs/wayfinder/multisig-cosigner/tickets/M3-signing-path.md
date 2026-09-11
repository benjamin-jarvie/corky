# M3 What changes in the signing path?

Type: `wayfinder:grilling`, HITL. **Blocked by M1 (closed).**
Claimed 2026-09-09.

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
- **Whether Core Signer says anything about the other cosigners.**
  `signer.owners` already reads all three fingerprints out of the PSBT.
  Showing them lets a person notice that a "2-of-3 with two friends" has
  two fingerprints they do not recognise. Core Signer cannot verify a quorum it
  does not hold, so this is the only check available, and whether it is
  worth a screen is a judgement.

Depends on M1 only for how many shapes have to work.

---

## Answer, 2026-09-09. Ben's call, three decisions.

### 1. A partial signature is delivered on today's screen

`complete: false` stops being a refusal. A partial signature is the
correct and FINAL outcome for a cosigner: it will never be complete on
this device, so refusing it would close this map's destination.

The result screen is unchanged: `SIGNED`, and the PSBT goes out by QR or
file exactly as a finished one does.

**The trade, recorded because it was made knowingly.** That screen says
SIGNED for a transaction nobody can broadcast yet. This project spent its
audit removing screens that told people something was true when it was
not, A6 above all. What makes it acceptable here is decision 2: the
REVIEW screen, which the person reads before approving, states the
threshold. So the flow does say the transaction needs other signatures;
it says it before you sign rather than after. If the review screen ever
loses that, this decision has to be reopened with it.

### 2. Review says the quorum and the threshold

Stop dropping `witness_script` in `_REVIEW_DROPS`. Core already reports
`type: "multisig"` and an `asm` beginning with the threshold, so Core Signer
can show "2 of 3" without parsing a script itself, which keeps PLAN A-11
intact.

    REVIEW  ·  OUTPUTS 1/1
      bc1q…x8fy         0.50000000
      2 of 3  ·  m/48'/0'/0'/2'
      FEE               0.00000378

The path is already there from M1. The threshold joins it, and together
they are what tells a person this signature does not finish anything.

Note the memory consequence for M5: `witness_script` comes back into the
decode, and it was dropped for a reason. At 150 inputs that is 150 more
scripts in the tree.

### 3. Review names the cosigners

`signer.owners()` already reads every fingerprint out of the PSBT and
needs no change. Three eight-character fingerprints on the review screen,
this device's marked.

It is the only check Core Signer can offer here. It cannot verify a quorum it
does not hold, so the whole of what it can do is show you who else is in
this one and let you notice two fingerprints you do not recognise.

Whether four lines fit a 240x240 panel is not a judgement: `test_screen_fit`
renders both panels and its collision check will say. If they do not
fit, the fingerprints are the line to move, not the fee.

### What this does not decide

The count of signatures still needed is NOT shown, because
`analyzepsbt` reports `next: signer` both before and after our
signature and cannot distinguish them. Deriving "1 of 2 present" would
mean counting `partial_signatures`, which `_REVIEW_DROPS` also drops.
Nobody asked for it and it is not in this answer.
