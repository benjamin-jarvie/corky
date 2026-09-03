# 06 A deterministic stand-in for the camera

Labels: wayfinder:task (AFK)
Blocked by: 04

## Question

Every rule from ticket 05 needs a test, and none of them can wait for
hardware. Build a replay source that satisfies the ticket 04 contract and
feeds a scripted list of images or strings: in order, out of order, with
duplicates, with a foreign UR mixed in, with garbage, with a set that never
completes.

This is the harness the adversarial tests in ticket 08 run against. It also
becomes the thing camera bring-up is compared to later.

## Resolution (2026-09-03)

Built at `tests/m1/replay_source.py`. Two sources, both satisfying the ticket 04
contract, so the same caller drives them and the future `CameraQrSource`:

- `ReplaySource` yields a scripted list of strings. `repeat_each` reproduces
  zbar emitting the same code many times while the camera holds still. `loop`
  reproduces an animated coordinator screen.
- `ImageReplaySource` yields strings decoded from real PNG files with the same
  pyzbar the device runs, so the decode path is exercised with no camera.
  Undecodable images are skipped, exactly as a camera skips a blurred frame,
  and the caller cannot tell the difference.

Scripted awkward cases: `out_of_order`, `with_foreign` (a `ur:crypto-account`
appears), `with_garbage` (a shop receipt wanders into view), `OVERSIZE` (over
`MAX_FRAME_CHARS`), and a set missing a part.

**Self-test: 8 checks, all green.** In order, duplicated four times each, out of
order, garbage mid-scan, foreign UR mid-scan, oversize refused, missing part
does not complete, and 11 real PNGs through pyzbar with zero undecodable.

Two findings for ticket 05:

1. A garbage frame, a foreign UR and an oversize frame each raise one
   `QrChannelError` and the scan still completes if the caller keeps going. So
   "abort on one bad frame" and "ignore and continue" are both implementable,
   and the choice is genuinely open.
2. **Sparrow and Corky emit different things.** Sparrow's `UREncoder` runs
   unbounded, so parts past `seq_len` are genuine fountain parts and a missed
   part recovers on a later pass. Corky's `psbt_to_frames` returns exactly one
   cycle and the display loops it, so every pass is identical. This asymmetry
   only helps the direction ticket 05 cares about: Corky scanning Sparrow can
   recover a missed part by waiting.

Closed. Unblocks nothing on its own; ticket 08 runs against it.
