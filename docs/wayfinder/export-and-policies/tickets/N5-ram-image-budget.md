# N5 Will a RAM-resident image actually fit on the Zero 2 W

Type: `wayfinder:research`. **Closed 2026-09-05 with "not proven, and
tight enough to doubt".**

## Question

Ben: "so the image can run from ram on the zero 2w and we will be able to
remove the micro SD and use it?"

## Answer

**Not by moving what is on the card today.** Measured on the board:

| | |
|---|---|
| RAM the board reports as usable | 447 MB |
| current root filesystem in use | 3.6 GB |
| Debian package closure of what Corky runs | 644 MB installed |
| kernel modules | 64 MB |
| bitcoind binary | 16 MB |
| bitcoind peak RSS, 250-input stress | 128 MB |
| the gate's own process RSS | 57 MB |

644 MB of userland does not go into 447 MB of RAM, and that is before
bitcoind runs. So this is not a switch to flip on Raspberry Pi OS. It
needs a purpose-built minimal image, the way SeedSigner's is built.

## The budget for such an image, and this part is an ESTIMATE

TESTING.md rule 6 says a cost claim comes from a measurement. This is not
one yet, and it is labelled so. The package closure above is padded: it
counts documentation, locales, headers, the whole Python standard library
as bytecode, and it double-counts shared base packages through the
recursive walk. A stripped image is far smaller. SeedSigner's is roughly
100 MB for Python, Pillow, zbar and a camera stack, which is Corky's stack
minus bitcoind.

Guessing forward from that:

| | estimate |
|---|---|
| stripped userland, SeedSigner-class | 150 MB |
| bitcoind and bitcoin-cli | 19 MB |
| trimmed kernel modules | 20 MB |
| bitcoind at runtime | 128 MB |
| the Corky UI at runtime | 57 MB |
| **total** | **374 MB of 447** |

That leaves about 70 MB for page cache and the wallet ramdisk, on a stress
case that already fails the M0 gate by 19 MB with the dev services
stopped. It is not obviously impossible and it is not comfortable.

One item is worth naming because it is large and not obvious: **numpy is
19 MB installed and `picamera2` depends on it.** The camera is not
optional, so neither is numpy.

## What would make this a measurement

Build the image. There is no shortcut: the estimate turns on how much a
strip actually saves, and that is only knowable by doing it. PLAN A-12
already carries the fallback if it does not fit, which is that v1 ships QR
and USB and the removable-card channel waits for a bigger board.

## What this changes

It is the second time today the 512 MB ceiling has been the deciding
factor, after R6's M0 failure. The coordinator question turned out not to
be a reason to move to the CM4 (a udev rule fixed that). **This is.** A
2 GB CM4 makes both this and M0 vanish, and with eMMC there is no card to
remove in the first place.
