# A10 What the earlier maps left open

Type: `wayfinder:task`, HITL. **Needs the board and Ben's phone.**

**Blocked by:** Nothing, and it needs the board and Ben's phone.

## Question

Two maps are still open and their items are beta blockers, not
housekeeping. This ticket is where they get weighed rather than
duplicated: read them, decide which block a beta, and record that.

From `export-and-policies`:

- **N1**, the card cannot be removed because the OS is on it, which is M3.
- **N4**, `butlers-playground` is 26 commits behind, so the encrypted file
  backup exists only in this repo's history. 50 conflict hunks.
- **N5**, whether a RAM image fits at all: 374MB estimated of 447.
- **R6**, M0 fails at 81MB against 100 required.
- **T1, T2, T3**, whether each coordinator's camera reads our QR and
  whether the address matches. The board is on and Ben has the phone.

From `e2e-before-testers`:

- **18**, the board run with the Sparrow laptop.
- **22**, the phone proofs.
- **23**, docs, PINS and the review for testers.

R6 is the one that decides the shape of the beta. 81MB of headroom on a
250-input stress case either gets fixed by the hardened image or the beta
ships with a stated input limit.

---

## Answer (2026-09-06)

R6 is the one that decides the shape of the beta, so it was re-measured
rather than carried forward on trust.

### R6: confirmed, and worse than recorded

Three runs on the board today, 250 inputs each. The first shows why the
other two stopped Corky's own services: otherwise the gate's bitcoind
competes with the device's.

| run | funding shape | headroom | verdict |
|---|---|---|---|
| Corky running beside it | exchange batches | 13MB | not a fair number |
| Corky stopped | exchange batches | **74MB** | **FAIL**, needs 100MB |
| Corky stopped | ordinary payments | **187MB** | PASS |

PLAN A-21 measured the same split on 2026-09-03 and got 226MB and 97MB.
R6 measured 81MB on 2026-09-05. **Both figures are lower today and the
failing one is further below the line, not nearer it.** Three independent
on-board runs now agree the batch shape fails.

Every input carries the whole transaction that paid it, so the funding
shape sets the PSBT size per input: 378 bytes against 2,778, a factor of
7.3. An ordinary payment is nowhere near the limit. A consolidation of
250 exchange-batch outputs can take this board out of memory.

**The README said only the passing half.** Its Status section led with
"M0 passed on the Pi Zero 2 W: 226MB of headroom signing 250 ordinary
inputs" and the milestone table said **PASSED**, with no mention anywhere
of the shape that fails. Both were accurate in what they said and
misleading in what they omitted, which is the A8 defect in its quietest
form. Both now state the split and today's numbers.

### The rest, weighed rather than duplicated

| item | blocks a beta? |
|---|---|
| **N1** the card cannot be removed, the OS is on it | **No.** M3. A tester keeps the card in; nothing in the beta asks them to pull it. |
| **N4** `butlers-playground` is 26 commits behind | **No.** It is the fork's problem and no beta artefact comes from it. PLAN A-24 has since deleted the encrypted backup that ticket was preserving, so what it was protecting no longer exists here either. |
| **N5** whether a RAM image fits, 374MB of 447 | **No.** M3. The beta runs from the card. |
| **R6** M0's batch-withdrawal shape | **Yes**, and it is the one thing on this list that shapes the beta. |
| **T1, T2, T3** each coordinator's camera | **Partly.** See below. |
| **18** the board with the Sparrow laptop | **Yes**, and it needs Ben. |
| **22** the phone proofs | **Yes**, and it needs Ben. |
| **23** docs, PINS and the review for testers | **Done**, by A7, A8 and A9. |

### What Sparrow's suites do and do not settle

`tests/sparrow/` runs **132 checks against Sparrow 2.5.4's own library**,
out of its sha256-verified release: the PSBTs Corky signs are the ones
Sparrow really builds, the exported descriptor is one Sparrow really
parses, and a wallet rebuilt from the paper backup signs a spend the
network accepts. That is a real interop proof and it is not a proof about
a **camera**.

T1, T2, T3, 18 and 22 all ask the same physical question: does a
coordinator's camera, pointed at this panel, read this QR, and does the
address on that screen match this one. Nothing in software answers it.
`tests/m1` has the two legibility rigs built for exactly this and they
need a lens and a screen.

### What is left for Ben, in one list

Combining what A4 and this ticket both end at:

1. **A stick pulled while a signed transaction is being written**, to
   test the mount's `flush` claim.
2. **A panel connected but blank**, which only eyes can distinguish from
   a black screen.
3. **Sparrow on the laptop reading the panel**, and the address matching.
4. **The two phone wallets**, BlueWallet and Green, the same question.
5. **Bull Bitcoin**, which the research says takes `wpkh` and not
   taproot.
6. **`harden.sh` run and the leak check watched from 13 to 0**, from A7.

Six things, all physical, none blocking each other. A11 weighs them.
