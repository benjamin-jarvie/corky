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

## Decision, 2026-09-11. Ben's call: two numbers, not one.

The ticket asked "whether the cap becomes two numbers or one
conservative one". **Two.** One low cap for everything would refuse
ordinary single-sig batches this board has already been measured
signing, which is work a person loses for no reason, and
`describe_psbt` already reports whether the inputs are a quorum, so the
device picks without guessing.

    MAX_SIGNABLE_INPUTS           150   measured on the board
    MAX_SIGNABLE_MULTISIG_INPUTS  120   PROVISIONAL, from the ratio above

`state_review` applies the lower one when `quorum` is set OR `timelocks`
is, because a miniscript policy carries a witness script per input the
same way. That second case is NOT measured, and refusing early is the
safe side.

**The 120 is an estimate and rule 6 says that is not good enough for a
cost claim.** It stands because the alternative is worse: 150 for a
quorum is a promise the board probably cannot keep, and the failure mode
is the OOM killer taking bitcoind while it holds the only copy of a
signature. `tests/test_property.py` pins the value in a band and checks
that each shape is judged against its OWN ceiling, so a quorum cannot
quietly get the single-sig number.

**This ticket is not closed.** The board replaces 120 with a measurement:

    python3 m0/m0_gate.py --inputs 100 --quorum 2-of-3
    python3 m0/m0_gate.py --inputs 120 --quorum 2-of-3
    python3 m0/m0_gate.py --inputs 150 --quorum 2-of-3
    python3 m0/m0_gate.py --inputs 175 --quorum 2-of-3

Swap must be off or the gate refuses to give a verdict. Pass is
MemAvailable never below 100MB.

## Answer, 2026-09-11. Measured on the Zero 2 W. The cap stays 120.

Ben turned the board on, so this stopped being a prediction. Run on a
Pi Zero 2 W Rev 1.0, 447MB, swap off (`/proc/swaps` empty), the device's
own `corky`, `corky-bitcoind` and `corky-splash` stopped for the
measurement and started again after. No key was loaded; `/run/corky` was
empty, so nothing was discarded. SoC peaked at 42.9C and
`vcgencmd get_throttled` read `0x0` throughout.

`m0/m0_gate.py --inputs N [--quorum 2-of-3]`, funding batch 100:

| case | PSBT | bitcoind RSS | gate RSS | MemAvailable | verdict |
|---|---|---|---|---|---|
| 2-of-3 100 | 623KB | 106MB | 32MB | **146MB** | PASS |
| 2-of-3 120 | 658KB | 108MB | 33MB | **129MB** | PASS |
| 2-of-3 150 | 795KB | 117MB | 38MB | **107MB** | PASS |
| 2-of-3 175 | 985KB | 123MB | 44MB | **92MB** | **FAIL** |
| single-sig 150 | 548KB | 97MB | 32MB | 139MB | PASS |
| single-sig 175 | 681KB | 107MB | 37MB | 123MB | PASS |

### A 2-of-3 at 150 passes, and the cap is still 120

The ticket feared 150 was "a promise the board cannot keep" for a
quorum. It can keep it, with 7MB to spare. That is not a margin worth
shipping. The single-sig cap of 150 sits 39MB above the line, and its
own comment says the cliff "is 36MB, so the line is drawn below it
rather than on it". The quorum cliff from 150 to 175 is 15MB. **120
leaves 29MB**, which is the same kind of margin, so 120 stands, now
measured rather than guessed.

### Where the dev estimate was right and where it was crude

The dev machine put a 2-of-3 decode at **1.23x** single-sig. The board
agrees: bitcoind's RSS at 150 inputs is 97MB single-sig against 117MB
for a quorum, which is 1.21x.

What was wrong was the inference. That measurement was turned into a cap
by dividing the OTHER cap by the ratio, 150/1.23, and landing on 120.
A cap follows from where the 100MB line falls, not from scaling another
cap. The number was right by luck and is now right by measurement, which
is the difference TESTING.md rule 6 is about.

### M3's undrop cost nothing the board can see

M9 undropped `witness_script` and `bip32_derivs` for the review screen
and M5 existed partly to find what that cost. At 150 single-sig inputs
the board holds 139MB, where the pre-undrop measurement that set the cap
held 114MB at 175. The undrop is not visible against run-to-run
variation. M9's dev figure, 0.29MB retained, was the right order.
