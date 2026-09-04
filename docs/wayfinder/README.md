# Wayfinder maps

Charted efforts for this repo. Each is a `map.md` plus numbered decision
tickets, worked one at a time with `/mp-wayfinder`.

- **m1-qr-without-optics** — everything in M1 that did not need a camera.
  Complete: nine tickets, and it found the defect where zxing could not read
  one frame in 125 of Corky's output (PLAN A-20, ISSUES I-9).
- **zero2w-m0-fixes** — what the M0 gate needed before it could run.

## Moved out

**key-provenance-and-backup** lives in
[butlers-playground](https://github.com/benjamin-jarvie/butlers-playground)
now. It charts codex32 splitting, BIP-85 in Tools, and getting a watch-only
descriptor out. Five of its seven tickets are resolved. None of it applies
here: PLAN A-22 left this repo with nothing that transforms secret material,
so there is no seed to split and no words to derive.
