# A6 Do the tests measure what they claim

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A5, whose coverage tells this one where to look first.

## Question

4,473 lines of tests, and in one evening three of them were found to be
measuring nothing: an assertion guarded by a condition that is never true,
a cost claim citing a number no test produces, and a stdin rule asserted
against fakes that could never have caught the defect it existed for.

That is three in one diff. This ticket asks how many more there are.

For every suite, ask the two questions that found those three:

- does each assertion actually execute, on every run, with the values it
  claims? An assertion behind a false guard is a comment.
- does it assert the round trip, or does it assert what the code already
  believes? TESTING.md rule 2 exists because a helper written from the
  code's own mental model agrees with it and is still wrong.

Then the cheap structural check: is there a suite whose failure mode is
"passes when the feature is deleted"?

---

## Answer (2026-09-06)

Two mechanical sweeps, because reading 5,000 lines of test looking for
assertions that do not fire is exactly the job that produced the three
defects in the first place.

**Sweep 1: measure the suites themselves.** `SOURCE=tests
tools/coverage_run.sh` reports coverage of `tests/`, so an assertion
behind a guard that is never true shows up as an uncovered line. Most
uncovered lines are failure branches not taken, which is health, not
rot; the residue is the finding.

**Sweep 2: delete the feature, run everything.** Five guarantees were
removed one at a time and the whole fast suite run against each.

### Sweep 2, and the one result that mattered

| deleted | noticed by |
|---|---|
| the scrollbar is drawn | `test_scroll` |
| key material goes on stdin | `test_property` |
| secrets are redacted | `test_no_persistence` |
| keys are cleared at startup | `test_no_persistence` |
| **the paper backup is checked against Core** | **nothing** |

A caveat on the method: `test_readme_claims` failed on four of the five,
because it counts lines and any edit changes them. Those are false
catches and were discarded.

**The paper backup check could not fail.** `_check_page` only returns a
page when the typed text matches the backup character for character. So
by the time `_confirm_typed_key` asked Core to confirm the whole key, it
was comparing Corky's copy of a string with Corky's copy of the same
string. Deleting the comparison outright left every suite green.

The screen says **"your paper opens key X"**. That is the strongest
claim the device makes about a backup, and the evidence behind it was a
string equalling itself. This is check 1c's defect from A5, in the
product rather than in a test.

**Fixed by asking the wallet instead.** `signer.opens_wallet` has Core
derive receive addresses from the typed key, has Core report the
addresses the loaded wallet hands out, and compares the two lists Core
returned. The derivation path is read out of the wallet's own descriptor
rather than rebuilt from the script type, so it follows the key wherever
Core put it, including regtest's coin type 1. `identity_of_key` had no
caller left and is deleted; the redaction it was credited with lives in
`Rpc.call`, where every error passes.

Now: making `opens_wallet` always return true fails K9. Making
`_confirm_typed_key` ignore its answer fails `test_backup_check`. The
refusal branch is still unreachable through the UI by construction, and
that is stated where it is tested rather than left to be discovered.

### Sweep 1, and the rest

- **`test_readme_claims` counted sessions in one file.** TESTING.md rule
  4 exists because this counter undercounted once already. The marker
  was made drift-proof and the *search* was not: `e2e_keys.py` arrived
  with eleven more sessions and the counter only ever read
  `e2e_session.py`. The README said 9; there are 21. It now globs every
  suite.
- **Its adversarial count could not fail.** The pattern looked for
  headings that no longer exist, matched exactly one thing, and printed
  the mismatch as "informational". It now counts `^def attack_`, gets 6,
  and fails on disagreement. The README said 15.
- **Two suites nothing ran and nothing mentioned.** `m4lite_mainnet.py`
  and `m4lite_taproot.py`, 152 statements at 0%, absent from
  `run_tests.sh` in every form including its not-run list. They spend
  real mainnet sats so they cannot join a suite; the fix is that the run
  now names them, with what they need and when they last ran.
- **Dead helpers in `tests/e2e_session.py`.** `grid_keys` and `BECH32`
  are codex32 leftovers, gone with the screen under A-22; `_pub` had no
  caller. `vulture` only ever looked at `corky/`, so nothing was
  watching. Deleted.
- **`run_device(card=...)` had never been passed.** The channel chooser
  had only ever been asked with one row, which is the case where the
  answer cannot be wrong. Session **K13** gives the device a stick AND a
  card, picks the card, and asserts the file is on the card and not the
  stick. Making the chooser always take the first medium fails it.
- **The Sparrow block threw its output away.** `>/dev/null 2>&1`, so a
  failure printed a name and nothing else. One flake was seen during
  this ticket and could not be diagnosed; it did not recur in four runs.
  The block now keeps its log and prints the tail, as the main loop
  already did. This is recorded as unexplained, not as fixed.

### What stays open

The Sparrow interop flake above. One occurrence, no diagnosis, and the
next one will leave evidence.
