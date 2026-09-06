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
