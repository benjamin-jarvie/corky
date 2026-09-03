# Map: M1 QR, everything except the optics

Labels: wayfinder:map
Opened 2026-09-03. **COMPLETE 2026-09-03**: all eight tickets closed,
the route is walked. Reviewed the same day with `/mp-code-review`; the Spec
axis found ticket 08's resolution had been retro-fitted and two of its claims
were false. See that ticket's Amendment. Fifteen findings across both axes,
all fixed. Chasing one of them opened **ticket 09**: zxing, the decoder Sparrow
uses, cannot read about one frame in 125 of Corky's output, deterministically,
and looping does not help. The map is complete; 09 is a new defect it found.

## Destination

Every part of M1 that does not need a camera is built and proven, so that the
day the board is on the desk the only untested thing left is a real camera
reading a real screen. Camera bring-up is a separate effort and starts after
BB-20 passes.

## Notes

- Ben's instruction (2026-09-03): execution is carried in-map. Chart, then
  build.
- **Already decided. Do not reopen.** The decoder is `pyzbar` with `libzbar0`
  (`image/provision.sh:38-41`, and ticket 04 of the zero2w-m0-fixes map).
  The camera library is `picamera2`. The coordinator target is Sparrow.
- The `QrSource` contract already exists: `scan_key()` and
  `scan_psbt_frames()` (`corky/main.py:57`). `CameraQrSource` raises
  `camera not yet wired (M1)`. `DevQrSource` is the file stand-in.
- The display half is built and proven: `psbt_to_frames`, `frames_to_images`
  and `fit_to_panel` in `corky/qrchannel.py`. `tests/sparrow/test_qr_airgap.py`
  shows Sparrow's own zxing reading all of Corky's rendered PNGs, both
  script types, 20 checks green.
- Measured 2026-09-03 on a 6-input PSBT. Sparrow at its default `NORMAL`
  density emits frames up to **775 characters**; at `LOW`, up to 215.
  Corky's guard is `MAX_FRAME_CHARS = 3000`, so the guard is not the limit.
  Whether a camera can read 775 characters is the open question.
- The M1 gate is `PLAN.md:377`: fee and outputs on screen match Sparrow, and
  the signed PSBT broadcasts.
- Panels: 320x240 Display HAT Mini is the primary build, 240x240 ST7789 is
  the pocket build.
- Style: ASD-STE100. No em dashes in new prose.

## Decisions so far

- [01 The rig must use zbar, not zxing](tickets/01-pyzbar-on-the-dev-machine.md):
  pyzbar 0.1.9 over zbar 0.23.93 runs on the dev machine under Rosetta;
  `tests/m1/setup.sh` and `tests/m1/run`, nothing installed system-wide.
- [02 Can a camera read Sparrow at its default density](tickets/02-degradation-rig.md):
  measured. `NORMAL` is 81x81 modules and needs about 90 percent of the camera
  view to survive ordinary blur; `LOW` is 45x45 and decodes from anywhere. The
  working line is roughly 4 pixels per module. Rig at
  `tests/m1/legibility_rig.py`.
- [07 Do Corky's numbers match Sparrow's](tickets/07-review-parity-with-sparrow.md):
  yes. 16 new checks compare Corky's `describe_psbt` fee and outputs against
  Sparrow's own `WalletTransaction`, to the satoshi, across both script types
  and eight transaction shapes. `tests/sparrow` is now 38 checks.
- [03 What Corky does about oversized frames](tickets/03-density-policy.md):
  detect and advise. Setup docs say set Sparrow to Low; frames over about 400
  characters put one line on screen; nothing is refused. `MAX_FRAME_CHARS`
  stays as the separate hostile-input guard.
- [04 Where the assembler lives](tickets/04-scan-loop-contract.md): the source
  yields decoded strings, the caller owns `FrameAssembler`. Same shape as
  `DevQrSource`, so one set of tests covers both.
- [06 A deterministic stand-in for the camera](tickets/06-camera-free-replay-harness.md):
  `tests/m1/replay_source.py`, two sources on the ticket 04 contract, 8 checks
  green including 11 real PNGs through pyzbar. Found that Sparrow emits
  unbounded fountain parts while Corky loops one cycle, so a missed part
  recovers when Corky scans Sparrow.
- [05 When a scan never finishes](tickets/05-stall-and-abort.md): bad frames
  are counted and skipped, never fatal; give up after 20 seconds with no
  progress, measured from the last movement; a different UR sequence restarts
  the scan; a button aborts.
- [08 Build it](tickets/08-imageqrsource.md): done. `scan_psbt` in
  `qrchannel.py` holds every rule, `ImageQrSource` holds none, and
  `CameraQrSource` is four lines that need the board.
  `tests/m1/test_scan_loop.py`, 13 checks green.

## Not yet specified

- What the screen shows while a scan is in progress, beyond a percentage.
  `FrameAssembler.progress` exists; whether a fountain-code percentage is
  honest enough to display is a UX question that ticket 03 may reshape.
- Whether the pocket build's 240x240 panel changes any of this. The display
  half already takes a `panel` argument, so this is probably nothing, and it
  is not worth a ticket until the primary build is proven.
- Power and thermal behaviour of a continuous camera loop. Belongs to camera
  bring-up, and only becomes specifiable once that effort opens.

## Out of scope

- Camera bring-up itself: `picamera2` configuration, exposure, autofocus,
  frame rate, working distance, glare. It needs the board, and the
  destination stops short of it on purpose. It opens as its own effort after
  BB-20.
- `scan_key()` and the SeedQR, xprv and descriptor entry paths. Ben scoped
  this map to the PSBT channel. That code touches secret material and earns
  its own adversarial pass rather than riding along here.
- Anything in M2, M3 or M4.
