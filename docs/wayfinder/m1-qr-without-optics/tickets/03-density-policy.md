# 03 What Corky does about oversized frames

Labels: wayfinder:grilling (HITL)
Blocked by: 02

## Question

Given ticket 02's numbers, what does Corky do when the coordinator sends
frames it cannot reliably read?

The candidates, to put to Ben with the measurements in hand:

- Say nothing, and let the scan simply take longer or stall.
- Put "set Sparrow to Low density" in the setup instructions and leave the
  device silent.
- Detect a frame longer than some threshold and say so on screen, so the user
  learns the cause rather than watching a stalled percentage.
- Refuse frames above the threshold outright.

The choice sets a threshold constant, a screen string, and one line of setup
documentation. It also decides whether `MAX_FRAME_CHARS = 3000` is still the
right guard or whether a second, lower, advisory limit is needed beside it.

## Resolution (2026-09-03, Ben)

**Detect the frame length and say so on screen.** Three parts:

1. Setup documentation tells the user to set Sparrow to `Low` density.
2. Corky measures the length of the frames it decodes. Frames longer than the
   threshold raise one line on screen: the frames are large, set Sparrow to Low
   density.
3. Nothing is refused. `NORMAL` decodes fine when the QR fills about 90 percent
   of the camera view, so a user who ignores the message and simply moves
   closer still succeeds.

Threshold: about **400 characters**, sitting between Sparrow's measured `LOW`
maximum of 215 and its `NORMAL` maximum of 775. `MAX_FRAME_CHARS = 3000` stays
as the hostile-input guard. The new limit is advisory and separate, and the two
must not be confused: 3000 refuses, 400 only advises.

Rejected, with reasons:

- **Documentation only.** At 60 percent fill a `NORMAL` frame fails under
  ordinary hand blur (ticket 02). The user then watches a percentage that never
  moves with nothing on screen naming the cause.
- **Refuse over the threshold.** It turns a workable case into a hard stop.
  `NORMAL` at 90 percent fill decoded every frame under every condition tested.
- **Defer until the camera exists.** It leaves ticket 08 with no rule to build,
  and the numbers are already good enough to choose.

Implementation belongs to ticket 08, including the setup documentation line.

Closed.
