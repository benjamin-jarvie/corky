# N4 Sync butlers-playground before the file backup is only in history

Type: `wayfinder:task`. **Open, and it should be the next job.**

## Question

The encrypted file backup was cut from `corky` on 2026-09-05 (PLAN A-24).
It belongs in
[butlers-playground](https://github.com/benjamin-jarvie/butlers-playground),
the fork that exists to carry what the pure signer refuses.

I got this wrong first: I made a `cm4` branch on `corky` instead, and Ben
was right that the code would never be used there. The branch is deleted.

## Where things stand, measured

The fork last synced at `c696049`, the A-22 cut, on 2026-09-04. `corky`
has moved **26 commits** since. Its own README documents the process:

    git fetch pure && git merge pure/main

Attempted, and it is not a five-minute job: **50 conflict hunks across 12
files.**

| file | hunks |
|---|---|
| tests/e2e_session.py | 12 |
| corky/main.py | 9 |
| corky/screens.py | 8 |
| README.md | 6 |
| tests/test_ui_cost.py | 6 |
| tests/test_screen_fit.py | 3 |
| the other six | 1 each |

The merge was aborted rather than resolved badly at the end of a long
session, and nothing is lost: everything is in `corky`'s history at
`6fc6085`, the commit before the cut.

## What the job is

1. Merge `pure/main` at `6fc6085` into the fork, resolving the 50 hunks.
   The rule for nearly all of them is take corky's version and re-add the
   fork's extra rows, because the fork is corky PLUS codex32, SeedQR and
   the BIP39 shim. `corky/main.py` and `corky/screens.py` are the two that
   need real thought, because the fork has menu entries corky does not.
2. Run the fork's own suites, which need their own bitcoind.
3. Then merge the A-24 cut with `-s ours`, taking the ancestry and none of
   the tree, exactly as the A-22 cut is already recorded there. Without
   that step the next ordinary forward merge deletes the file backup from
   the fork too, which is the trap its README already warns about.
