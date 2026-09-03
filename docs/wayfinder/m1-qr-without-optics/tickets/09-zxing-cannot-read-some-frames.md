# 09 Sparrow cannot read about one frame in 125

Labels: wayfinder:grilling (HITL)
Blocked by: none
Opened 2026-09-03, from the `/mp-code-review` pass.

## Question

Corky's outbound QR has no margin, and the consequence is worse than a slow
scan: some transfers can never complete.

Measured with `tests/m1/outbound_margin.py`, 375 frames from 25 signed
taproot-sized PSBTs:

- Corky renders 244-character UR frames as a **49x49 QR**, 53 modules with the
  quiet zone. The 320x240 panel allows `box_size = 240 // 53 = 4`, so Corky
  renders at exactly **4.0 pixels per module** and cannot go higher without
  fewer modules.
- **3 of 375 frames (0.8%) could not be decoded by zxing.**

Three facts make this a defect rather than a tolerance:

1. **It is deterministic.** The same image fails 5 attempts out of 5.
2. **`psbt_to_frames` emits exactly one cycle** and the display loops it, so
   every pass shows the identical image. Waiting does not help.
3. **zxing is Sparrow's decoder.** `pyzbar` reads the same image without
   trouble, so Corky's own inbound path is unaffected and this is invisible to
   every test that does not use Sparrow's own reader.

At 13 to 21 frames per PSBT, the chance that a transfer contains at least one
permanently unreadable frame is roughly **one in seven**. Observed directly:
2 of 5 runs of `test_qr_airgap.py`.

`tests/sparrow/test_qr_airgap.py` now fails when it happens, on purpose.

## The options

- **Emit real fountain parts past one cycle**, which is what Sparrow's own
  `UREncoder` does. A bad pure part is then recoverable from later mixed parts.
  Fixes the whole class, not just the marginal cases, and makes Corky's output
  as robust as Sparrow's. Costs a change to `psbt_to_frames`, which currently
  promises "one full cycle", and to anything that assumes a fixed frame list.
- **Lower `MAX_FRAGMENT_LEN`** so the module count drops and `box_size` rises
  to 5. Raises the margin, more frames, slower transfer. Does not remove the
  class, only makes it rarer.
- **Both.**
- **Accept it** and document that a stuck transfer needs a restart. Cheapest,
  and it asks the user to diagnose something they cannot see.

Ben decides.

## Resolution (2026-09-03, Ben)

**Emit real fountain parts past one cycle**, which is what Sparrow's own
`UREncoder` does when it sends to us.

`psbt_to_frames` now returns `seq_len * FOUNTAIN_REDUNDANCY` frames, with
`FOUNTAIN_REDUNDANCY = 2`. Parts 1 to `seq_len` are the pure fragments; every
part after that is a fountain part, an XOR of a random subset, and any of them
can stand in for a pure part the scanner never got. A single-frame PSBT is
still a single static QR.

Proved, not assumed. `tests/m1/test_scan_loop.py` drops each pure part in turn
and checks the rest still assembles: **11 of 11 individually droppable.**

`tests/sparrow/test_qr_airgap.py` now asserts the promise that actually
matters. Not "every frame is readable", which was never true and is not what
the fix buys, but "whatever the scanner got is enough to rebuild the PSBT".
Six consecutive runs pass. Three of them logged one or two unreadable frames
and completed anyway, which is the fix doing its job in the open rather than
the failure merely becoming rarer.

**The cost is transfer time.** The frame count doubles: 21 to 42 for a
six-input P2WPKH PSBT, 13 to 26 for P2TR. At the display's frame rate that is
twice as long for a scanner that reads everything first time. Lowering
`MAX_FRAGMENT_LEN` was rejected for this reason as well as the main one: it
would have added frames too, and only made the failure rarer rather than
recoverable.

The unreadable frames themselves are unchanged and still about 1 in 125.
`tests/m1/outbound_margin.py` keeps measuring that, because the day it gets
worse is a day worth noticing.

Closed.
