# How Corky is tested, and the rules that came from being wrong

`./run_tests.sh` runs the fast suites. `RUN_NODE=1 ./run_tests.sh` adds the
suites that need a real `bitcoind`. Both must be green before a commit.

This file exists because on 2026-09-02 a two-axis review found a feature that
had shipped in a state where it could not work, past a full green suite. The
rules below are what that failure taught. They are not style preferences.

## Rule 1: every input surface needs a real-data round-trip test

**A test that renders a screen proves nothing about whether the screen can
express real data.**

Typed key entry (audit item S3) shipped with a 64-cell character grid that
omitted base58's `B` and omitted `(`, `)` and `*`. About 85% of real xprvs
contain a `B`, and every descriptor needs brackets, so neither typed mode
could ever have worked. The screen rendered correctly, fit both panels, and
passed every suite, because no test ever asked it to type an actual key.

The paths that did NOT have this bug are the ones that already followed this
rule: codex32 grid entry had `grid_keys` plus frozen vectors, and word entry
had `WORDS_SCRIPT` built from real BIP39 words.

So, for any surface that accepts input:

1. Take **real** domain data. Ask Bitcoin Core for it where possible
   (`listdescriptors`, a derived xprv, a funded PSBT), rather than writing a
   plausible-looking literal. A literal encodes the author's assumptions,
   which are exactly what is under test.
2. Compute the key sequence programmatically from the navigation rules
   (`text_keys`, `grid_keys`, `word_keys` in `tests/e2e_session.py`).
3. Assert the device reconstructs the input **exactly**, and where the input
   is key material, that it opens a key which signs a real transaction.

Sessions T and T2 in `tests/e2e_session.py` are the reference shape.

## Rule 2: the helper must not share the code's assumptions

A key-sequence helper written from the same mental model as the navigation
loop will agree with it and still be wrong. When `text_keys` and
`_text_entry` were both written by the same author in the same hour, they
desynchronised the moment paging entered the picture, and only a round-trip
assertion (`got == want`) exposed it.

Assert the round trip, never the key count.

## Rule 3: test the path that ships, not the path that is convenient

`_show_qr_loop` guards its paced, repeating animation behind
`if not self.animate:`. Every scripted session takes the one-pass dev branch,
so for the whole of its life the loop that actually reaches a coordinator's
scanner had never executed in a test.

If a branch exists only for the device, a test must set the flag and run it.
`tests/test_qr_out.py` does this with a threaded display and a blocking
button source.

## Rule 4: a metric that counts wrongly is worse than no metric

`test_readme_claims` counted scripted device sessions with a pattern that
matched only single-letter labels, so it ignored D3, H3/H4, R3 and T2 and
undercounted by a third while reporting a confident number. Prefer counting
a marker that cannot drift (`# ---- Session `) over inferring from prose.

## Rule 5: run the two-axis review, because the suite cannot find these

The suite is written by whoever wrote the code, so it inherits their blind
spots. Two of the three most serious defects found in the 2026-09-02 review
were invisible to a green suite:

- a charset that could not express its own domain (Spec axis);
- a backup tool that used a passphrase it never asked for, and so could
  encode a backup for a different wallet than the words open (Standards
  axis).

Run `/mp-code-review <fixed-point>` before each milestone gate and after any
change to an input path, a screen's meaning, or `signer.py`. It runs two
independent sub-agents:

- **Standards** — does the diff obey the repo's documented laws (PLAN A-11's
  opaque-bytes rule, the three-layer model, the no-device-RNG doctrine) plus
  the Fowler smell baseline?
- **Spec** — does the diff implement what the originating audit item or PLAN
  amendment actually asked for, and nothing more?

Report the two axes separately. Merging or reranking them lets one mask the
other, which is the whole reason they are separate.

**Verify the findings before acting on them.** In this project, three
separate claims from automated reviewers did not survive checking: a "17/17
suites pass" that matched no version of the repo, a set of fixes reported as
landed that were never in the tree, and an S5 "bug" that was correct code.
Reproduce a finding against the source before you change anything for it.

## Rule 6: a cost claim must come from a measurement, not an estimate

When the letter grid replaced the dial (audit D4) the design note claimed
"about 180 presses for a 24-word seed". The measured figure is **352**,
against the dial's 546. The estimate was never wrong on the direction, only
on the size, and it sat in a docstring as if it were a fact.

`tests/test_ui_cost.py` measures entry cost by replaying the real navigation
rules, and fails if the cost drifts. When a UI changes, that model must
change with it: after D4 it still modelled the dial for a while, so it
reported a confident 546 for a device that no longer worked that way.

## What is still thin

See `ISSUES.md`, items I-3 to I-6.
