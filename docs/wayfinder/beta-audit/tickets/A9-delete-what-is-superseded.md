# A9 Delete what is superseded

Type: `wayfinder:task`, AFK. Ben's call, 2026-09-06.

**Blocked by:** A8, which says what the old documents are still load-bearing for.

## Question

Ben: delete the superseded, git keeps it. The reasoning is A8's: a
document nobody has checked is worse than no document, and two false
claims reached him from stale ones in a single evening.

The candidates, with what each is:

- `docs/audit/ui-and-branding.md`, 390 lines from 2026-09-01. Its fifteen
  items are closed and it describes screens that no longer exist. It is
  the source of the D, S and I numbering that ISSUES.md still uses, so
  check what that numbering is still load-bearing for before deleting.
- `docs/wayfinder/m1-qr-without-optics/`, 9 tickets, all closed.
- `docs/wayfinder/zero2w-m0-fixes/`, 5 tickets, all closed.
- `ISSUES.md`'s two "Fixed" sections, 112 lines of history, and its "Open"
  section, which is empty.

What has to survive: anything a later document cites, and anything that
records WHY rather than WHAT. The A-19a amendment is only comprehensible
because the tradeoff screen it removed is described somewhere.

Decide per artefact, delete in one commit, and say in the commit message
what a reader should read instead.
