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

### E-5 About 1% of export QRs are unreadable by Sparrow's own scanner

Found 2026-09-09, chasing what looked like a flake in
`tests/sparrow/test_export_interop.py`. It is not a flake. Measured
against Sparrow's own zxing, on descriptors Core really generated,
rendered exactly as `_export_qr` renders them:

| | |
|---|---|
| today's setting | **4 of 440 (0.9%)** |

It is **deterministic per descriptor**, not random. The same key fails on
both panels, because the code is the same 159px image either way. If your
key is one of the unlucky ones, that export QR never reads, however many
times you try.

**It cannot be tuned away.** Three things were tested and none of them is
the cause:

| tried | result |
|---|---|
| more pixels per module (3 to 4) | still ~1%, ECC M fails at both |
| lower error correction (M to L) | 5 of 440, no better |
| forcing each of the 8 mask patterns | every mask fails somewhere: 0,1,2,3,5,6,7 all failed in 180, and the encoder's own choice beat six of them |

The mechanism is the mask. For a failing descriptor, zxing reads **six of
the eight** mask patterns; the encoder picked one of the two it cannot.
Encoders choose a mask on a penalty heuristic tuned for print legibility,
not for any decoder, so roughly one time in a hundred it picks one zxing
will not take. No fixed mask is safer: mask 4 read 180 of 180, and so did
the encoder's own choice in that same sample, which we know fails ~1% on
a larger one.

The measurement is a lower bound. It decodes a perfect PNG. A coordinator
photographs a lit panel through a lens, which is strictly harder.

**Two fixes, both real work and both after the flash:**

1. Animate the descriptor as BC-UR, the way the PSBT path already goes
   out. Fountain redundancy means the coordinator sees several different
   codes and one bad mask stops mattering. This is the same answer ticket
   09 reached for the signing path after measuring the same class of
   failure at 4px per module.
2. Cheaper: let the user re-render. Six masks of eight work for any given
   descriptor, so one key press that re-rolls the mask fixes it, and the
   user already knows it failed because their coordinator did not scan.

**Not urgent, because the QR is one of three export routes.** Text to
type and wallet file both carry the same descriptor, so a user who hits
this is inconvenienced rather than stuck. That is the difference between
this and the signing path, where the frames are the only way out and are
animated for exactly this reason.

### E-4 The five coordinators are unproven on a device

The coordinator chooser was removed from the export because the research
says Sparrow, BlueWallet and Green all read the same plain descriptor QR
for `wpkh` and `tr`, Bull Bitcoin reads `wpkh` only, and Core reads no QR
at all and takes a file. The research is in
the e2e-before-testers map, tickets 19, 20 and 21 (archived; see docs/wayfinder/README.md), and it was
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

### QR is the only channel that closes a loop on the pocket build

Not a defect, and worth writing down because it changes what a tester
must be given. On a Zero 2 W the card is the boot device, so reading it
elsewhere means powering off and the tmpfs datadir dies with the session.
USB host genuinely works (`otg_mode=1`, `dtoverlay=dwc2,dr_mode=host`,
checked on the board 2026-09-06) but needs a micro-USB OTG adapter and a
cutout in the case.

So a tester with no adapter has exactly one way in and out: the camera
and the panel. The outbound margin is thin by construction, 4.0 pixels
per module with no room above it, and measured at 8 misses in 750 frames
on 2026-09-06. The panel loops, so a miss costs a cycle.

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
