# C4 The words on the two new screens

Type: `wayfinder:prototype`, HITL. **Blocked by C1, C2.**
Claimed 2026-09-19.

## Question

C1 and C2 settled what the two new screens SAY. They did not settle the
words, and on this device the words are the product: a screen that says
something a person cannot act on has failed, however correct it is.

Two screens:

1. **The interruption.** Fires when a person tries to move forward with
   a wrong character. It has to carry the place (box 7, character 3),
   both characters, and the instruction to fix the PAPER rather than the
   screen, in the space a 240-pixel panel has.
2. **The corrections summary.** C2 fixed its content. Its shape on two
   panel sizes is not fixed, and neither is what it does when there are
   more corrections than fit.

**Ben's standing rule for this map, 2026-09-19:** sentences on any
disclaimer or screen text start with a capital letter. C5 applies that
to everything else; these two are written that way from the start.

Draft both at both panel sizes, render them, and put them in front of
Ben. Record what he changes.

## Not answered here

Whether a correction is counted per character or per box (the map's
**Not yet specified**). The summary's wording depends on it, so this
ticket picks one and says which.

## Answer

**CLOSED 2026-09-19.** Both screens are in `screens.py` as
`wrong_character` and `corrections`, drafted, rendered at both panel
sizes and put in front of Ben.

### The interruption

    BOX  7  ·  CHARACTER  3

    You typed        [ c ]      red
    The key is       [ C ]      gold

    Write C on your paper at box 7,
    character 3. I will fix it here.

              [ OK ]

Both characters large and boxed in their own colour, because telling
them apart is the entire job. "I will fix it here" is the device's own
voice and Ben's words: it fixes the scaffolding, the person fixes the
paper.

### The corrections summary, and why it is TWO screens

Prototyped as one screen first, with the list of places under the
claim. **The warning came out in grey type half the size of everything
else**, squeezed by the list, and the warning is the part that matters.
Measured, not argued: the render is in the charting session.

So page one carries the claim and the warning whole, and DOWN shows the
places:

    3  CORRECTIONS                    3  CORRECTIONS

    This key, with your 3             Box 7, character 3
    corrections, opens 73C5DA0A.      Box 14, character 1
                                      Box 22, character 4
    If you did not write those 3
    down and test them, you may
    not be able to recover this
    key or its funds.                 Write these on your paper.

    DOWN for the 3 places
          [ DONE ]                          [ DONE ]

The list scrolls past four, on the same bar every other paged screen
uses. It is the safety net for somebody who did not write the
corrections down one at a time on the way through.

### The counting, which the map left unspecified

**Per character, not per box.** It is what the interruption names and
what the person writes on their paper. A character can only be
corrected once, because the device overwrites it with the right one, so
nothing double-counts.

### Sentence case

Every sentence on both screens starts with a capital, per Ben's rule of
2026-09-19. C5 carries it to the rest of the device.
