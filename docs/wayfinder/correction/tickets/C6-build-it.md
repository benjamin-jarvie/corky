# C6 Build it

Type: `wayfinder:task`, AFK. **Blocked by C1, C2, C3, C4, C5.**
Unclaimed.

## Question

Build what C1, C2 and C3 settled, in the words C4 approves, under C5's
rule.

The shape of the work, from the charting session:

| | |
|---|---|
| `main.py` | the typing branch of `_check_entry`: red on mismatch, interrupt on moving forward, overwrite and advance |
| `main.py` | delete `marked`, `_next_gap`, and the re-entry loop in `_check_typed` (C3, about 60 lines) |
| `main.py` | count the corrections and carry them to the last screen |
| `screens.py` | the interruption screen |
| `screens.py` | the corrections summary |
| `screens.py` | the red mark moves ONTO the box border at the caret's thickness (Ben, 2026-09-19), so it stops taking interior space |
| `main.py` | CHECK becomes DONE |

## How it is proven

**The house rule of this map.** The box-numbering defect was reported
three times and missed twice, both times because it was diagnosed by
reading the loop rather than by typing a key the way a person types one.

So: a check that drives the real flow with a WRONG character in it, and
asserts a person cannot get past it; a check that the interruption names
the right box and character; a check that the last screen's sentence
matches the number of corrections actually made. Then the same run on
the board, against its own installed copy, before it is handed back.

`tests/test_typing_uniform.py` must stay green, or the two typing
screens have drifted apart again.
