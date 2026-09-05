# D5 Does the boot microSD become a channel

Type: `wayfinder:grilling`. **Closed 2026-09-05.**

## Question

Ben: "This then asks for usb only - does core not accept USB? Could we not
use microSD?"

The USB-only prompt is not about Core. It is Corky's channel chooser, and
it offered one channel because the systemd unit sets `--stick-dir=/mnt/usb`
and no `--card-dir`.

Related defect, already fixed and not reopened here: `/mnt/usb` is an
ordinary directory on the boot card when no stick is in the port, so the
device offered "stick" with no stick and wrote to the SD card. On the
device a channel now needs a real mount (commit da16b1c,
`tests/test_channels.py`).

To decide: does the boot microSD become a named channel, at which path,
and what does the panel call it? PLAN A-23 permits a key on the card when
the user asks for the card, so this is a rule change, not a config change.
The M3 plan makes the card removable while the OS runs from RAM, which
changes what "the card" means; that interaction belongs in this ticket.

**Closed 2026-09-05.**

## Decision

**Yes, and it is now the primary file channel rather than a convenience.
It cannot happen until the OS runs from RAM.**

Ben's workflow, in his words: "take microSD out, use a different one with
PSBT, sign and put back into coordinator". That is SeedSigner's model and
it is the right one for a device with one card slot and no USB host port
worth trusting.

## The blocker, measured on the board

The operating system is ON the card. `lsblk` shows `mmcblk0p2` mounted at
`/`, and there is one usable slot. Pull the card on the image running
today and the system dies at the next disk touch.

So every part of Ben's workflow depends on the RAM-resident image, which
was M3 and was scheduled last:

- keep running with the card out;
- say "you can safely remove the microSD now";
- accept a blank card to export a key to;
- accept a different card carrying a PSBT.

**M3 is therefore a prerequisite for this ticket, not a successor to it.**
That is a change to the plan's order and it is the single most important
thing this map found.

## What does not need M3

The `--card-dir` half is separate and small: naming a mounted card as a
channel beside the stick. But on a one-slot board with the OS on that
card, the only card that could be named is the boot card, which is what
PLAN A-23 was careful about. There is nothing worth shipping here before
M3.
