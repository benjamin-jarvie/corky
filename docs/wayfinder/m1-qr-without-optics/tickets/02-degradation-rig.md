# 02 Can a camera read Sparrow at its default density

Labels: wayfinder:prototype (HITL)
Blocked by: 01

## Question

Sparrow's default `NORMAL` density emits UR frames up to 775 characters. That
is roughly a version-16 QR, about 85 modules across. A camera wants three or
four pixels per module, so the code needs 255 to 340 pixels of sensor. On a
cheap module at arm's length that is marginal.

Answer it without hardware. Take Sparrow's real frames, render them, then
degrade them the way a camera does: downscale to sensor resolution, gaussian
blur, motion blur, perspective tilt, reduced contrast, sensor noise. Decode
each with zbar from ticket 01 and measure the rate.

Produce a table of decode rate against density and degradation, for both
`NORMAL` (400) and `LOW` (80). The numbers are the deliverable; ticket 03
turns them into a decision.

## Resolution (2026-09-03)

Built at `tests/m1/legibility_rig.py`, run with `tests/m1/run`. Frames are
Sparrow's own, captured from its `UREncoder` into
`tests/m1/sparrow_frames.json`. Both Sparrow and Corky render at error
correction level L, so the module counts here are the module counts on a real
screen. The sensor frame is 512x384 per `hw/HARDWARE.md:75`.

**The answer is that density decides it, and the margin is thin at NORMAL.**

Sparrow `NORMAL`: longest frame 775 characters, **81x81 modules**, 85 with the
quiet zone.

| QR fills | px per module | clean | blur 0.8px | blur 1.5px | motion blur | tilt 15 + blur |
|---|---|---|---|---|---|---|
| 90% | 4.06 | all | all | all | all | all |
| 75% | 3.39 | all | all | **none** | all | all |
| 60% | 2.71 | all | all | **none** | **none** | **none** |
| 50% | 2.26 | all | **1 of 5** | **none** | **none** | **none** |

Sparrow `LOW`: longest frame 215 characters, **45x45 modules**, 49 with the
quiet zone. Every frame decoded under every condition at 90, 75 and 60 percent
fill, and all but one at 50 percent.

Summary across both script types, at 60 percent fill and better:

    NORMAL   44 of 54 condition-sets decoded every frame
    LOW      54 of 54

So the working line is about **4 pixels per module**. Below 3.4 ordinary blur
starts taking whole frames out. At `NORMAL` the user must fill roughly 90
percent of the camera view and hold still. At `LOW` framing barely matters.

**These numbers are optimistic.** The rig renders a perfect QR. A real screen
adds moiré against the sensor grid, refresh banding and glare, none of which
are modelled. Treat `NORMAL` at 90 percent fill as the ceiling, not the
expectation.

Closed. Feeds ticket 03.
