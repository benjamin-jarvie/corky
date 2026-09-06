# A8 Every claim the documents make

Type: `wayfinder:task`, AFK.

**Blocked by:** Nothing. Takeable now, and it is the cheapest.

## Question

The README is the security argument. It is also 700 lines that nobody
verifies except `tests/test_readme_claims.py`, which checks line counts
and link targets.

In one evening, two of its claims were false and both had been true once:
that cards and dice were the default generation path, when the code to do
that had been deleted months earlier; and that a `lab` branch held the
removed modules, when no such branch existed. A third contradicted itself
across forty lines about how many script policies v1 supports.

Stale documentation in this project is not untidiness. It is the mechanism
by which wrong things get believed, and it has already produced wrong
statements to Ben twice.

Walk every factual claim in `README.md`, `PLAN.md`, `TESTING.md`,
`CONTEXT.md` and `hw/HARDWARE.md`, and mark each: verified, false, or
unverifiable. For the verified ones, say what verifies them and whether
that check runs. For the false ones, fix them. For the unverifiable ones,
say so in the document itself.

The measurements are the ones to be hardest on. TESTING.md rule 6 exists
because an estimate sat in a docstring as a fact, and it happened again on
2026-09-05 with a press count that no test produced.

---

## Answer (2026-09-06)

2,108 lines across five documents. The findings below are the false ones;
everything else checked out or is now checked by the suite.

### The security argument cited evidence that does not exist

`README.md` has a two-row table headed **"Claim | What proves it"**. The
first row said the OS is silent, proved by **`radio-check.sh` on the
device**. No file of that name has ever existed in this repository. The
tool is `leak-check.sh`, named correctly eleven lines above.

This is the exact mechanism the ticket describes, in the one table whose
whole job is to say what the evidence is.

**Now mechanical.** `tests/test_readme_claims.py` walks every backticked
path and every `module.symbol` in all five documents and fails when one
does not exist. Two SeedSigner citations were flagged and are legitimate,
so the documents now say whose files they are, and a line naming
SeedSigner is exempt. `PLAN.md` is a dated log and a forward spec, so it
is the one document allowed to name what it deleted or proposes, but it
must say so within three lines in one of: superseded, post-v1, not
written, deleted, removed. Two entries did not and now do.

### The first security claim was one-third enforced

> no `os.urandom`, no `random`, no `secrets`, **enforced by a test**

Probed by adding each to a shipped module and running
`tests/test_integrity.py`:

| named | was it caught |
|---|---|
| `import secrets` | yes |
| `import random` | **no** |
| `os.urandom` | **no** |

`random` was absent from `BANNED_IMPORTS`, and `urandom` is an attribute
on a permitted stdlib module so no import scan can see it. A device RNG
is the single thing PLAN A-19 forbids outright, and two thirds of the
sentence claiming it was prevented were decoration. `random` is banned
now and `urandom` joined the banned-text list. All three probes are
caught.

### Three hardcoded counts, all wrong, for the same suites

| where | said | measured |
|---|---|---|
| `README.md` | 86 Sparrow checks | **132** |
| `run_tests.sh` | 81 Sparrow checks | **132** |
| both | 28 in `tests/m1` | **20** |

The README also described the Sparrow set as two suites when it is four;
the 53 export checks and the 21 recovery checks were missing from a total
that claimed to be complete. `run_tests.sh` now sums the count each suite
prints and reports what it observed, so this cannot drift again. Rule 6:
a measurement, not a number written down.

### The icon count disagreed with itself twenty-six lines apart

`README.md:823` said a **six**-glyph subset; the supply-chain table at
`README.md:849` said **seven**; the font's own NOTICE said **seven**.
`screens.ICON` holds seven. The sign tile changed from a QR to a
signature on 2026-09-05 (Ben) and one of the three was not updated. Now
pinned: the test reads `len(screens.ICON)` and checks every written
statement of it, in the README and in the NOTICE. Adding an eighth glyph
fails the suite.

### CONTEXT.md defined a thing that no longer exists

The glossary still defined **file backup** as a live term, "a wallet file
encrypted by Core with a passphrase", and asserted that **only** the file
backup can be restored on another computer. PLAN A-24 deleted the
encrypted backup on 2026-09-05, and the README's own recovery section
says the paper backup opens in both Core and Sparrow, proved by 21
checks against Sparrow's library. The glossary was therefore wrong twice
in one entry, and a glossary is the document other documents are
supposed to be checked against.

`PLAN.md`'s A-23 had the matching problem: its text still reads as the
current rule ("...is allowed. The README states it plainly"), one day
before A-24 reversed it. Marked superseded, in PLAN's own convention.

### The board on the desk is not either documented build

Both README and `hw/HARDWARE.md` pair the panel with the compute module:
primary build is the CM4 with the 2.8" 320×240 hat, pocket build is the
Zero 2 W with the 1.3" 240×240. Asked directly, on the board, on
2026-09-06:

```
$ ssh corky-zero 'python3 -c "...hal.DeviceDisplay()..."'
panel 320 x 240
```

A Zero 2 W with the 320×240 panel is neither. Nothing is broken by it:
every screen is written for both sizes and `test_screen_fit.py` renders
both. What is wrong is the wording, and a tester reading it would flash
the wrong expectations. Recorded as a measurement in `hw/HARDWARE.md`
and in the glossary; **naming the third combination is Ben's call, not
mine**, so no build was invented here.

### Verified, and by what

- No cryptographic primitive imported in `corky/`: `test_integrity.py`,
  29 checks, runs in `run_tests.sh`.
- Vendored 2,251 lines: counted by `test_readme_claims.py` every run.
- Core 31.1, sha256 `dcf1873f…`, 11 GPG signatures: `image/PINS`,
  verified out of band 2026-09-03. Not re-verified here.
- The paper backup opens in Sparrow: `tests/sparrow/test_recovery.py`,
  21 checks, measured this session.
- Nothing persists: `test_no_persistence.py`, and A6's deletion sweep
  confirmed it notices when clearing or redaction is removed.

### Unverifiable, and now said so in the document

- `OS_IMAGE_SHA256="UNPINNED_UNTIL_FIRST_FLASH"`,
  `DEV_IMAGE_SHA256="RECORDED_AFTER_PROVISION"` and
  `CORKY_COMMIT="HEAD"` in `image/PINS`. The README already describes the
  OS hash as "recorded on first flash", which is honest, but a tester's
  image cannot be reproduced from this file as it stands. That is A7's
  and A11's problem, not prose.
- "The radio cannot transmit" rests on the part being physically absent.
  No test can reach that; the table says so.
