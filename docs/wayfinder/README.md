# Wayfinder maps

Charted efforts for this repo. Each is a `map.md` plus numbered decision
tickets, worked one at a time with `/mp-wayfinder`.

- **beta-audit** — **open, and the current one.** An evidenced go or no-go
  on a private beta: eleven tickets, every finding weighed as blocking or
  not. Charted 2026-09-06 on Ben's call that scope is everything and the
  board is on.
- **m1-qr-without-optics** — **closed.** Everything in M1 that did not need
  a camera. Nine tickets, and it found the defect where zxing could not
  read one frame in 125 of Corky's output (PLAN A-20, and TESTING.md rule
  8, which is where that lesson lives now).
- **zero2w-m0-fixes** — **closed.** What the M0 gate needed before it could
  run. Five tickets. Cited by `m0/m0_gate.py`.
- **e2e-before-testers** — **closed.** The pure signer end to end before
  outsiders test it: SeedSigner-shaped menus, several keys, export public
  key, the board run with Sparrow, and the three phone wallets. Charted
  2026-09-04; seven decisions closed in charting. Its ticket on Core's own
  encrypted file backup was reversed the next day by PLAN A-24, which
  deleted the feature: the private key now leaves on paper and no other
  way.

## Moved out

**key-provenance-and-backup** lives in
[butlers-playground](https://github.com/benjamin-jarvie/butlers-playground)
now. It charts codex32 splitting, BIP-85 in Tools, and getting a watch-only
descriptor out. Five of its seven tickets are resolved. None of it applies
here: PLAN A-22 left this repo with nothing that transforms secret material,
so there is no seed to split and no words to derive.
