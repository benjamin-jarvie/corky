# D5 Does the boot microSD become a channel

Type: `wayfinder:grilling`, HITL. Blocked by: T3.

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
