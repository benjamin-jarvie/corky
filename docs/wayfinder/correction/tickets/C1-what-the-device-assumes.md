# C1 What may the device assume when the paper and the typing disagree?

Type: `wayfinder:grilling`, HITL. **Blocks C3, C4, C5.**
Claimed 2026-09-19. **CLOSED 2026-09-19.**

## Question

The device holds the key. The person types what their paper says. When
the two differ, the device knows only that they differ. It cannot know
whether the paper is wrong or the thumb slipped, and the two want
opposite responses: one means go and correct the paper, the other means
leave the paper alone.

Getting this wrong in the expensive direction sends a person to scribble
a correction onto a backup that was already right.

Decide what the device is allowed to assume, and what it does with a
mismatch.

## Answer

**Nothing. It shows both characters and lets the person decide.**

Ben, on the board, 2026-09-19: "Why can't we show what it should be and
what they typed? Who cares if they accidentally did it versus the paper
being wrong, if they go to add a new character, rather than deleting and
fixing, then we should show this pop up."

The device names the place and shows both characters. The person is
holding the paper, so they resolve it in a glance, and the device never
guesses. This deleted the two-button prompt the charting session had
proposed and every branch behind it.

**When it interrupts** is the other half of the answer, and it is what
makes the flow bearable:

| what you do | what happens |
|---|---|
| type a character that does not match | it goes red where it sits |
| press B and retype it | nothing else. A fat-finger costs nothing |
| try to move FORWARD with one still wrong | the screen stops you and names it |

Moving forward means typing the next character or pressing the
right-caret key. B never triggers it, because B is how you fix it.

**The device overwrites the typed character and moves on.** The typed
string is scaffolding and nobody keeps it; the paper is the artifact and
only the person can fix that.

**Blocking also catches a SKIPPED character**, which is the case nobody
raised while proposing this. A skip shifts every character after it, so
without blocking a person types to the end of the key and every
character after the skip is wrong. With blocking it is caught on the
next press.
