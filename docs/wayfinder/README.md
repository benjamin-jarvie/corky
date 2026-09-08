# Wayfinder maps

Charted efforts for this repo. Each is a `map.md` plus numbered decision
tickets, worked one at a time.

- **beta-audit** — **open, and the current one.** An evidenced go or
  no-go on a private beta: eleven tickets, every finding weighed as
  blocking or not blocking. Charted 2026-09-06.

## The closed maps are archived, not lost

Four maps are finished, and on 2026-09-07 they were taken out of the
repository to keep it lean. They were 78 files against the 7 that make up
the signer.

| map | what it settled |
|---|---|
| **e2e-before-testers** | the pure signer end to end: SeedSigner-shaped menus, several keys at once, export public key, the board run with Sparrow, the phone wallets |
| **export-and-policies** | all four of Core's script policies, the export flow, and the M0 memory work |
| **m1-qr-without-optics** | everything in M1 that did not need a camera. It found the frame zxing could not read, which is now TESTING.md rule 8 |
| **zero2w-m0-fixes** | what the M0 gate needed before it could run |

**Available on request.** The archive is
`corky-closed-wayfinder-maps-2026-09-07.tar.gz`, held outside this
repository, and every file is also in this repository's git history
before commit `08b27b9`.

Code and documents here still cite them by name, as "(map
e2e-before-testers, ticket 03)". That is provenance: it says which
decision a line came from, and the archive is where to read it. The
lessons that had to outlive the maps were moved before they went:
**TESTING.md** carries the testing rules, and **PLAN.md** carries the
amendments.

## Moved out

**key-provenance-and-backup** lives in
[butlers-playground](https://github.com/benjamin-jarvie/butlers-playground)
now. None of it applies here: PLAN A-22 left this repo with nothing that
transforms secret material.
