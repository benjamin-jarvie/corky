# T5 The four bugs that need no redesign

Type: `wayfinder:task`, AFK. **Blocks nothing. Takeable now.**

## Question

Four of the six things Ben hit are wiring, not design, and none of them
waits on the alphabet or the box model:

1. **CHECK is not the default.** `_show_backup` opens the last page with
   `sel = 0`, which is DONE. A person who has just written 111
   characters down wants to check them, and the device should not make
   that the deliberate choice.
2. **The centre press finishes the page.** In the grid, `p` returns the
   typed text. With nothing typed, every character is marked wrong at
   once, which is what Ben saw.
3. **The centre press should type.** A does; the centre should too.
4. **Finishing needs the button bar.** Once 2 and 3 are done this falls
   out, and it should be asserted rather than assumed.

Doing these first means the next person to pick the device up is not
blocked while the rest of the map is decided. They are also the smallest
possible change to prove the test can see each defect: every one of
these shipped with a green suite.

## Done when

Each of the four has a check that fails against today's code, and the
backup check can be started, typed into and finished by somebody who has
not read this file.
