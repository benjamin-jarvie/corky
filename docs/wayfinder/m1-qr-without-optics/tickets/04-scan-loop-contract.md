# 04 Where the assembler lives

Labels: wayfinder:grilling (HITL)
Blocked by: none

## Question

`CameraQrSource.scan_psbt_frames()` returns an iterator and currently yields
nothing. Two shapes are possible and they put the errors in different places.

- **The source yields decoded strings.** `FrameAssembler` stays in the caller.
  The source stays dumb and testable, and every `QrChannelError` surfaces in
  one place. The caller has to run the loop and decide when to stop.
- **The source owns the assembler** and yields progress, then a finished PSBT.
  The screen code gets simpler. Errors are now raised from inside a generator,
  which is harder to test and harder to show on a 320x240 screen.

The answer fixes the contract that tickets 05, 06 and 08 all build against,
so it comes first.

## Resolution (2026-09-03, Ben)

**The source yields decoded strings. The caller owns the assembler.**

`scan_psbt_frames()` yields one decoded QR payload at a time and does nothing
else. `FrameAssembler` stays where it already is, in the caller. Consequences,
all of them wanted:

- The source stays dumb, so it is trivial to fake and trivial to test.
- Every `QrChannelError` surfaces in one place that screen code already
  handles, rather than from inside a generator.
- `DevQrSource` already behaves this way, so the camera source and the file
  source keep the same shape and the same tests apply to both.
- The caller runs the loop, which means the stopping rules from ticket 05 live
  in one place rather than being split across the source and the screen.

Rejected: a source that owns the assembler and yields progress. It simplifies
the screen code and costs testability, and it would make the two sources
behave differently.

Rejected: shipping both shapes with a wrapper helper. Two supported contracts
to keep tested, for a saving of a few lines at one call site.

Closed. Unblocks 05 and 06.
