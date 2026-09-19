# C6 Build it

Type: `wayfinder:task`, AFK. **Blocked by C1, C2, C3, C4, C5, C7.**
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
| `screens.py` | `backup_page` numbers its groups 1 to 28 (C7), and the type shrinks to pay for it. Measure how far. |

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

## Done

**CLOSED 2026-09-19**, with one thing owed: see below.

`_check_entry` is one loop with no state to manage. A character that
does not match goes red where it sits and the caret moves on, so at most
ONE can ever be outstanding, and `_wrong_at` is both the red marks and
the block. Adding another character while one is red calls `_fix_one`,
which paints `wrong_character`, waits for a press, puts the right
character in, and records `(box, character)`.

Deleted, as C3 said: `_next_gap`, `marked`, and the re-entry loop in
`_check_typed`. `_check_typed` is now four lines and a comment.

One thing C3 did not foresee: **DONE on a key that is not finished.**
The bar is reachable by going DOWN at any time, and pressing DONE with
40 characters still to type returned a short string that Core then
refused in Core's own words. DONE now puts you back where the typing
stopped.

`backup_page` numbers its groups 1 to 28. **Measured cost:** the
characters go from `h * 0.075` to `h * 0.068`, about a tenth, which is
what the number column costs.

The red mark moved onto the box border at the caret's thickness, top
and bottom, and the caret notch is drawn after it so a slot that is both
wrong and current reads as both.

### What proves it

`tests/test_backup_check.py`: a wrong character goes red and the caret
moves on; adding another stops and names the box and character; the
device puts the right character in and records where; three corrections
replace "Your paper opens key X" with the count and the warning; DONE on
an unfinished key puts you back in the grid.

Session K9 drives the whole thing against a real node, in three
segments, because that is three things a person does: type to the
mistake and on, dismiss, type the rest.

48 suites green. Typing a key in is 472 presses, checking one 469.

### Owed

**The house rule of this map is not yet satisfied.** The same drive,
with a mistake in it, has to run on the board against its own installed
copy. It passed on this machine; the board dropped off the network
mid-push and the run has not happened. `diag4.py` in the session
scratchpad is the script.
