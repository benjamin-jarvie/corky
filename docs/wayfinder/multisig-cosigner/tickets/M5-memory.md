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

## Measured on the dev machine, 2026-09-11, before the board

TESTING.md rule 7: "before you write 'no test without hardware', name
the exact line that needs the board." For this ticket that line is
`mem_available_mb()` on 512MB with swap off. Everything else measures
here, and doing it first turns the board session into a confirmation
rather than a search.

**`m0/m0_gate.py` now measures a quorum**, so Friday is one command:

    python3 m0/m0_gate.py --inputs 150 --quorum 2-of-3

It builds a watch-only 2-of-3 holding Corky's cosigner key and two
strangers, funds it, and signs a share through the path that SHIPS:
`sign_psbt(..., xfp=…)` falls through to `sign_at_told_paths`, which
imports the branch the PSBT names into a scratch wallet. Corky's own
session wallet keeps the four standard policies, which is what a loaded
key really has.

### The decode, which is the term that matters

`describe_psbt` under `tracemalloc`, funding batch 100 (2778 bytes per
input, the exchange-batch worst case the cap was set against):

| case | PSBT | decode peak |
|---|---|---|
| single-sig 100 | 432KB | 15.29MB |
| single-sig 150 | 548KB | 19.27MB |
| 2-of-3 100 | 623KB | 18.74MB |
| 2-of-3 150 | 795KB | 23.69MB |

**A 2-of-3 costs 1.23x a single-sig decode at the same input count**,
and the ratio is the same at 100 and at 150. PSBT size scales at 1.45x.

So **a 2-of-3 at about 120 inputs costs the decode that single-sig costs
at 150**, which is where `MAX_SIGNABLE_INPUTS` sits.

### The prediction the board has to judge

The board measured single-sig: 175 inputs passed with 114MB headroom,
200 failed with 78MB, and the cap was set at 150. If the decode carries
the ratio, **the multisig ceiling is near 120 and 150 is a promise this
board cannot keep for a quorum.** That is the fear this ticket opened
with, now with a number on it.

Sample 100, 120, 150 and 175 with `--quorum 2-of-3` and find the floor.

### One correction to M9's number

M9 recorded the undrop as costing "0.29MB retained and nothing at the
peak", measured at 150 multisig inputs on a **516KB** PSBT. Today's
150-input multisig PSBT is **795KB**, because M9's fixture funded in
chunks of 50 and this gate funds in batches of 100, and the gate's own
comment says that is a factor of 7.3 on bytes per input. The undrop
conclusion stands, because it is about the RETAINED tree and that is
small either way. **The peak figures are not comparable**, and the board
must use the batch-100 case, which is what the cap was set against.
