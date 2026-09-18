# T3 Rebuild the typing screen on the box model

Type: `wayfinder:task`, AFK. **Blocked by T2.**

## Question

The check screen draws a flat echo line with a caret. The backup screen
draws numbered 4-character groups. A person is comparing one to the
other, and the mismatch is what made box 8 impossible to find.

Build the entry screen to look like the display screen:

1. **Numbered boxes of 4 characters**, 3 per row, the same shape
   `screens.backup_page` already draws.
2. **One cursor** (Ben, 2026-09-18). LEFT and RIGHT step one character
   and cross box edges by themselves; UP and DOWN jump a row. The boxes
   and their numbers are read, never navigated into.
3. **A and the centre press both type** the highlighted character.
   Neither finishes the page.
4. **Finishing means reaching the button bar.** No centre shortcut past
   it. DOWN off the bottom already gets there and the d-pad loops.
5. **The separate caret mode goes.** One cursor means there is nothing
   to switch into, and `C` stops being the only way to move.

`tests/test_ui_cost.py` measures the route, and Ben asked for no bloat,
so the press count for a whole key is part of the answer.

## Done when

The check flow runs end to end in `tests/test_backup_check.py` with the
new model, the press cost is measured and recorded, and every check that
pinned the old caret behaviour is either updated or gone with a reason.
