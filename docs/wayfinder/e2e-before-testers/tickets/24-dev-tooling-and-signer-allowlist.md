# 24 Developer tooling, and what the signer is allowed to carry

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: resolved 2026-09-05

## Question

Ben, 2026-09-05, from the website checklist: "Should we have a linter? Or
any of these: a formatter, linter, standardized code patterns, a singular
UI tool, type safety for everything that should or just everything, review
and reduce react context providers, state management library? I want to
ensure we have no wasted code, that the code we do have is concise, quality
and earns its keep." And: "tell me what will go on the pinned signer, ensure
that's in the readme or some instruction so we don't forget and leave
unneeded dependencies."

## Facts, measured before deciding

Run from a throwaway virtualenv, nothing installed on the machine:

| Tool | On the shipped code | Verified by hand |
|---|---|---|
| ruff, defaults | 30 findings, mostly cosmetic | the pyflakes rule F821 catches the undefined-name bug of 2026-09-05 in one second |
| ruff, waste rules | 6 unused parameters, 7 functions over complexity 10 | two of the parameters were on the review screen, never read |
| vulture | 5 candidates | 4 real: a colour never used, a logo helper never called, a scan loop only a test called, two dead parameters |
| mypy | silent, because 9 type hints exist in 3,700 lines | with `--check-untyped-defs`, 5 findings, all trivial |
| ruff format | would rewrite 4,117 lines | |
| by hand | 10 copies of one key cascade beside a helper that already did it | |

## Resolution (Ben, 2026-09-05)

Three of the seven items are React and CSS questions with no counterpart
in 3,700 lines of Python drawing on a panel. The rest, decided:

- **Linter: yes.** ruff, developer machine only, pinned in
  `requirements-dev.txt`, with a small rule set in `ruff.toml` chosen to
  find defects and waste rather than argue about style. It replaced the
  100-line scope checker written the night before, so it removed code.
- **Dead-code finder: yes.** vulture, same terms.
- **Formatter: no**, for now. A 4,117-line rewrite would swamp every diff
  and all blame on a tree with a board run pending. One commit before
  contributors arrive, if ever.
- **Standard patterns: already the strong form** (A-11, A-19, A-22, the
  glossary, the nine testing rules, the integrity guard). The one pattern
  that was written down but not enforced in code, every menu through
  `_pick`, is enforced now: six cascades collapsed into it.
- **Type safety: the seam, not everything.** `signer.py`'s public
  functions are annotated and mypy checks them in the fast suite.
  Annotations are lines, and the README counts lines as the trust metric.
- **One UI tool, context providers, state library: not applicable.**

**What the signer carries** is now one table in the README, "What runs on
the signer", with the source and the reason for every package, and a
matching allowlist in `tests/test_integrity.py` that fails the suite if a
shipped module imports anything not on it. `image/PINS` and
`image/README.md` point at the table. Two candidates for removal from the
release image are named there: `python3-pip`, which exists only to install
two packages Debian also ships, and `python3-zbar`, which probably does not
exist as a package at all. Both are checked on the board.

**What was removed today, all verified dead first:** the colour constant,
the logo helper, the review screen's two unread parameters and every
caller that computed them, the scan loop that moved to the test that used
it, the scope checker, and the six menu cascades. Shipped code went from
2,903 to 2,845 lines of code, with more behaviour, not less.

`run_tests.sh` runs ruff, vulture and mypy first when they are installed,
and says so when they are not, so their absence never reads as a pass.
