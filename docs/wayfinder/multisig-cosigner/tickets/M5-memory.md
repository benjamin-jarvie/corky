# M5 How many multisig inputs will the board sign?

Type: `wayfinder:task`, AFK. **Blocked by M3, M9 (both closed).**

## Question

`MAX_SIGNABLE_INPUTS = 150` is measured, on the board, on SINGLE-SIG
PSBTs: 175 inputs passed at 114MB and 200 failed at 78MB headroom.

A multisig input is bigger. It carries a witness script and a derivation
entry per cosigner rather than one, so the same input count is a larger
PSBT and a larger decode. The charting session's 1-input 2-of-3 PSBT was
1232 base64 characters where a single-sig one is a few hundred.

The device refuses past 150 rather than dying mid-sign, and that refusal
is the only thing standing between a big batch and the OOM killer taking
bitcoind while it holds the only copy of a signature. If the real
multisig ceiling is lower, 150 is a promise the board cannot keep.

Measure it the way M0 measured the first one, with `m0/m0_gate.py` or its
descendant, on the Zero 2 W, swap off. Decide whether the cap becomes two
numbers or one conservative one.

**M3 made this worse and it is the reason to measure rather than
estimate.** The review screen now shows the threshold, which means
`witness_script` comes back out of `_REVIEW_DROPS`. That field was
dropped deliberately: dropping the review's unread fields took Corky's
own process from 56MB to 45MB. A witness script per input, at 150
inputs, is 150 scripts back in the decoded tree, on the board where the
headroom between 175 inputs and 200 was 36MB. Measure with the undrop in
place or the number is about a device nobody ships.


## What M9 measured, 2026-09-10, so this is a confirmation

M9 built the undrop and measured it on a real 150-input 2-of-3 PSBT,
516KB of base64, on the dev machine against Core 31.1:

| drop set | retained tree | peak |
|---|---|---|
| before, `witness_script` and `bip32_derivs` dropped | 0.06MB | 14.85MB |
| after, both kept | 0.35MB | 14.85MB |

**0.29MB retained, and the peak does not move.** The peak belongs to the
JSON text and the parse, not to what is kept afterwards, and
`non_witness_utxo` stays dropped.

So the paragraph above, written when "150 more scripts in the tree" was
an estimate, was pessimistic by about two orders of magnitude against
the 36MB band between 175 inputs and 200. **The number to measure on the
board is the 14.85MB peak, which this change does not move**, and the
question is whether the multisig ceiling differs from 150 at all.

One thing M9 added that this must include: `sign_at_told_paths` imports
a descriptor per branch and signs in a scratch wallet, so a multisig
sign now runs `decodepsbt` once more than a single-sig one. Measure the
whole signing run, not just the review.
