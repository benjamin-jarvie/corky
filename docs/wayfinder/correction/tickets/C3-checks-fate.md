# C3 Does CHECK survive?

Type: `wayfinder:grilling`, HITL. **Blocked by C1.**
Claimed 2026-09-19. **CLOSED 2026-09-19.**

## Question

C1 says a wrong character cannot pass. That has a consequence nobody
asked for: by the time the 111th character is typed, every one of them
has already been compared and found right, so there is nothing left for
CHECK to check and it can never fail.

A button that cannot fail is a button that does nothing. Decide whether
it stays.

## Answer

**No. It becomes DONE.**

And the machinery behind it goes too, because a wrong character can no
longer survive long enough to need any of it:

- `marked`, the flag that turned red on only after the first CHECK
- `_next_gap`, which walked the cursor from one mistake to the next
- the loop in `_check_typed` that re-entered the grid with the mistakes
  marked and the cursor on the first one

All of that exists to manage a page with several mistakes in it at once,
and under C1 that page cannot exist. Roughly 60 lines.

**Rejected in charting:** a SKIP button on the interruption, leaving one
character wrong and carrying on. It keeps CHECK a job and keeps the
fix-walking, and it is the behaviour that let a whole key be typed in
the wrong case in the first place.
