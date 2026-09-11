# M9 Build M3: deliver the signature, and make review say what it is

Type: `wayfinder:task`, AFK. **Blocked by M3 (closed), M4 (closed).**
Claimed 2026-09-10.

## Question

M3 decided three things on 2026-09-09. None of them is built, so the
device cannot do what M4 proved is possible. M4's test stands in for the
device by importing the branch into a scratch wallet.

What the code says today:

| M3 decision | Today |
|---|---|
| A partial signature is delivered | `main.py:1765` refuses: "wallet cannot complete this PSBT" |
| Review says the threshold | `witness_script` is in `_REVIEW_DROPS` |
| Review names the cosigners | `signer.owners()` exists, no screen reads it |

M5 is blocked behind this in practice. Its own ticket says to measure
with the undrop in place, or the number describes a device nobody ships.

## Seams

Agreed before any test, per `/mp-tdd`:

1. **`signer.describe_psbt`'s returned dict.** Gains the quorum and the
   path. Every number stays Core's, so PLAN A-11 holds: Core Signer reads
   `type` and the threshold Core already reports and parses no script.
2. **`screens.review`'s image.** Renders the quorum line and the
   cosigner fingerprints, and still fits 240x240. `tests/test_screen_fit.py`
   is the judge.
3. **`main.Session._sign_and_deliver`'s outcome.** A partial signature
   reaches the SIGNED screen rather than the refusal.

`signer.owners()` is unchanged, as M3 said.

## The memory question this must answer

M3 recorded the consequence for M5 as "150 more scripts in the tree".
That was an estimate. `drop` prunes by NAME during the JSON parse, and
the 20.7MB it was built for was `non_witness_utxo`, which stays dropped.
A 2-of-3 witness script is about 210 hex characters and a derivation
entry about 150, so 150 inputs looks like roughly 100KB rather than
megabytes.

**Measure it here, on the dev machine, and record the number.** M5 then
confirms on the board rather than discovering it there. If the real cost
is small, M5 is a confirmation. If it is not, M3's decision 2 gets
reopened with the number in hand.

## Done when

The three seams are built, `/mp-tdd` red-to-green for each, every check
mutation-verified, the full suite green, and `tests/sparrow/test_cosigner.py`
no longer needs its scratch-wallet stand-in.

## Measured, 2026-09-10, dev machine, Core 31.1

A real 150-input 2-of-3 PSBT, 516KB of base64, decoded twice:

| drop set | retained tree | peak |
|---|---|---|
| M3's, `witness_script` and `bip32_derivs` dropped | 0.06MB | 14.85MB |
| M9's, both kept | 0.35MB | 14.85MB |

**The undrop costs 0.29MB retained and nothing at the peak.** The peak
is the same number to two decimal places, because it belongs to the JSON
text and the parse, not to what is kept afterwards. `non_witness_utxo`
stays dropped and it was always the expensive one.

So M3's "150 more scripts in the tree" was pessimistic by about two
orders of magnitude against the 36MB headroom M5 is worried about. M5
becomes a confirmation on the board rather than a risk, and the number
to watch there is the 14.85MB peak, which this change does not move.

## Answer, 2026-09-10. Built, and the device now does what M4 proved.

`tests/test_multisig_review.py`, 11 checks, plus
`tests/sparrow/test_cosigner.py` with its stand-in REMOVED: the Sparrow
suite now signs through the device's own path, on an ordinary BIP48 path
and on a blinded one. Twelve mutations across the three seams, all
caught.

### Seam 1: `signer.describe_psbt`

Gains two fields, both read out of what Core already decoded.

- **`quorum`**: `None`, `(threshold, total)`, or the string `"mixed"`.
  The third case is the one worth having. Reading the first input and
  printing "2 of 3" over a transaction that also spends a single-sig
  utxo states something untrue on the one screen this project exists to
  keep truthful, so `_quorum` compares every input and refuses to say
  when they disagree.
- **`cosigners`**: `[(fingerprint, account path), ...]`, every input,
  deduped. The account path is the derivation with a trailing
  `/change/index` removed, because those two steps differ for every
  address in one wallet and say nothing about WHICH wallet, which is the
  only thing M1 decision 2 wants the path to say.

`_REVIEW_DROPS` loses `witness_script`, `bip32_derivs` and `asm`.
`non_witness_utxo` stays dropped, and it was always the expensive one.

### Seam 2: `screens.review`

Three new arguments, `quorum`, `cosigners` and `ours`. Two lines between
the outputs and the fee: `2 of 3 · m/48h/1h/0h/2h`, then the
fingerprints with this device's in cream and the others in grey. Colour
marks ours rather than a prefix character, because width is the scarce
thing on a 240x240 panel.

**A defect the fit suite caught before it shipped.** P2WSH allows up to
20 keys, and 20 fingerprints do not fit at any legible size: eight of a
15-key quorum rendered off both edges of the panel, where a string
simply is not there. A quorum too wide to name now shows
`<ours> · N more keys`, which is true and readable.

Five cases added to `tests/test_screen_fit.py`, including the worst case
of all of it at once: the widest amount, a paged transaction, unseen
pages and a blinded path.

### Seam 3: signing

- **`sign_psbt` gains `added`.** `complete` could not carry M3 decision
  1, because `complete: False` is true for one signature of two AND for
  none at all. Without this, SIGNED would appear over a PSBT the device
  never touched. That is not hypothetical: it is the bug M4's test
  nearly shipped.
- **`sign_at_told_paths`** runs when a plain sign adds nothing. It reads
  the derivations the PSBT names for this fingerprint, imports one
  ranged descriptor per branch into a scratch wallet, signs, and drops
  the wallet in a `finally`. This is M1 decision 2 built: the device
  derives where it is told.
- `main._sign_and_deliver` now refuses on `not added` rather than on
  `not complete`, with "this key signed nothing on that PSBT".

**The cost, recorded because it was paid knowingly.** A descriptor is
the only way Core imports a derivation, and a descriptor needs the key,
so signing at a told path pulls the master xprv into Core Signer for the
length of one signature. `generate_wallet` refuses to hand it back for
exactly this reason. The exposure is kept narrow: it runs only when the
loaded policies signed nothing, the branch goes to a scratch wallet and
never the session's, and that wallet is dropped whether or not the
signing worked. A-24 is untouched, because nothing is written: the
datadir is tmpfs and the wallet is gone before the call returns.

### Two facts for the map

- **`analyzepsbt` DOES answer "did this device add a signature".** The
  map records that its `next` field cannot tell a finished PSBT from an
  unfinished one, which is true. `missing.signatures` is a different
  field and it shrinks as signatures land.
- **Core returns the IDENTICAL base64 string when it signs nothing.** A
  free second reading of the same fact. The count is what the code
  relies on, because it stays right if a later Core adds metadata
  without signing.
