# 05 When a scan never finishes

Labels: wayfinder:grilling (HITL)
Blocked by: 04

## Question

UR fountain codes are unbounded. The encoder emits parts forever, so a scan
that is going wrong looks exactly like a scan that is going slowly. Corky
needs rules for four cases:

- The user points the camera at a different PSBT halfway through. Two UR
  sequences interleave. `FrameAssembler` feeds both to one decoder today.
- The user points it at a `ur:crypto-account` or a plain text QR.
  `FrameAssembler.feed` already raises on a wrong prefix; whether one bad
  frame should abort a whole scan is undecided.
- Frames arrive but the percentage does not move.
- The user wants to give up. There is no abort today.

Decide the timeout, whether a wrong frame aborts or is ignored, how a second
UR sequence is detected, and what the button does.

## Resolution (2026-09-03, Ben)

**Ignore bad frames. Time out on no progress. Restart on a new sequence.**

| Case | Rule |
|---|---|
| Garbage QR, foreign UR type, oversize frame | Count it, skip it, keep scanning. One stray code must never discard a half-finished PSBT. Ticket 06 proved the scan completes through all three. |
| Progress stops moving | Give up after 20 seconds with no change in the completion percentage, and say so on screen. |
| A different PSBT appears | Detect the new UR sequence, drop the old assembler, start a fresh one, say so on screen. Pointing the camera at another transaction is almost always deliberate. |
| The user wants out | A button aborts at any point. |

The timer measures **time since the last progress**, not total elapsed time. A
10-input PSBT at Sparrow's `Low` density is 23 or more frames and is slow but
healthy; a wall-clock timer would punish exactly that case.

Rejected: abort on the first bad frame. On a cluttered desk a stray code drifts
through view often, and each one would cost a restart.

Rejected: no timeout. A fountain scan has no natural end, so the screen can sit
at 60 percent forever with nothing saying it will never finish.

Rejected: feeding two interleaved sequences to one assembler, which is today's
behaviour. The result is unpredictable, and unpredictable is the worst outcome
on a device whose whole claim is that you can trust what it shows you.

Closed. Unblocks 08.
