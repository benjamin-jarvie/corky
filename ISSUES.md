# Known issues

Open defects and gaps, recorded so they are not lost between sessions.
**Fixed items leave this file and live in the git history instead.** That
rule was written at the top of this file and then broken: on 2026-09-06
it held 112 lines of fixed history and an "Open" section where six of
eight items had already been fixed. Audit A9 emptied it.

Where a fixed item taught something, the lesson is in
[TESTING.md](TESTING.md) as a numbered rule, which is the document that
gets read. Where it changed a decision, it is a PLAN amendment. Neither
needs a copy here.

Last reviewed 2026-09-06, audit A9. Every claim below was checked against
the source on that date.

## Open

### E-4 The five coordinators are unproven on a device

The coordinator chooser was removed from the export because the research
says Sparrow, BlueWallet and Green all read the same plain descriptor QR
for `wpkh` and `tr`, Bull Bitcoin reads `wpkh` only, and Core reads no QR
at all and takes a file. The research is in
`docs/wayfinder/e2e-before-testers/tickets/` 19, 20 and 21, and it was
read out of each project's source.

**None of it is proven on a device.** Tickets 18 and 22 are the proofs,
and both need Ben, a phone and the Sparrow laptop. Sparrow's half is now
covered by `tests/sparrow/`, which drives Sparrow 2.5.4's own library out
of its verified release, so what is left is the two phone wallets and
Bull Bitcoin.

Carried into the beta audit as
[A10](docs/wayfinder/beta-audit/tickets/A10-carry-forward.md).

### The build the board actually is

Both `README.md` and `hw/HARDWARE.md` pair the panel with the compute
module: the primary build is the CM4 with a 2.8" 320×240 hat, the pocket
build is the Zero 2 W with a 1.3" 240×240. Asked on the board on
2026-09-06, a Zero 2 W answered 320×240, which is neither.

Nothing is broken by it. Every screen is written for both sizes and
`tests/test_screen_fit.py` renders both. The wording is wrong, and
naming the third combination is Ben's call. Recorded in
`hw/HARDWARE.md` and `CONTEXT.md` as a measurement in the meantime
(audit A8).

### The image a tester would flash is not pinned

`image/PINS` carries `OS_IMAGE_SHA256="UNPINNED_UNTIL_FIRST_FLASH"`,
`DEV_IMAGE_SHA256="RECORDED_AFTER_PROVISION"` and
`CORKY_COMMIT="HEAD"`. The README describes the OS hash honestly as
"recorded on first flash", so this is a gap and not a false claim, but a
tester's card cannot be reproduced from that file as it stands. Audit
A7 owns it.

## Standing hardware-blocked work

Not defects. Recorded so the list above is not confused with them.

- M1: camera QR capture on the board. The dev harness and `tests/m1`
  cover the scan rules; the lens has not been pointed at a coordinator.
- M2: display and GPIO bring-up beyond what the board already runs.
- M3: RAM-resident release image, radio kill verification, reproducible
  build.

M0 passed on the Pi Zero 2 W on 2026-09-03: 226MB of headroom signing 250
ordinary inputs (PLAN A-21).

## What was here, and where it went

- **I-1 to I-11**, the two-axis reviews of 2026-09-02 and 2026-09-03, and
  the test gaps they found. All fixed. The rules they produced are
  TESTING.md 1 to 11; the cropped-QR and silent-power-off pair is rule 7,
  and the zxing frame that Corky's own decoder could read is rule 8.
- **D17** (teardown failure is silent) and **D18** (load, review and
  signing errors bypass UI recovery). Both fixed. `Session.run` reports a
  failed teardown as "key not cleared" instead of discarding it, and
  `Session.HANDLED` catches `RuntimeError`, `OSError`,
  `FileChannelError` and `QrChannelError` around every flow the home
  screen dispatches. Sessions K7 and K8 drive the file-error path.
- **E-1** (no scroll bars). Fixed: six screens draw one and
  `tests/test_scroll.py` asserts that every screen taking a page or an
  index has one.
- **E-2** (the export was four screens deep with no map) and **E-3**
  ("PUBLIC KEY" is not what the screen holds). Both fixed on the board
  with Ben on 2026-09-05: the flow is script type, then how it leaves,
  then the key, then the addresses, and the QR carries its fingerprint,
  policy and derivation path underneath.
- **E-5** (Core's file had nowhere to go). Fixed: `--card-dir` exists and
  session K13 gives the device a stick and a card and proves the file
  lands on the one chosen.
- **E-6** (two of Core's four script policies). Fixed: all four are
  exported and browsable, LEFT and RIGHT walk them, and session K12
  proves each policy's own addresses reach the panel.
