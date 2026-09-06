# A7 The image a tester flashes

Type: `wayfinder:task`, AFK. **Needs the board to confirm.**

**Blocked by:** Nothing, and it needs the board to confirm a flash.

## Question

A tester does not get this repository. They get a card. Nothing has
audited what is on it.

`image/` holds `provision.sh`, `harden.sh`, `prepare-sd.sh`,
`leak-check.sh`, three systemd units, a udev rule and a mount unit.
`tests/test_image_contents.py` checks the archive carries what
`provision.sh` reaches for, and that is the only automated check there is.

It is also demonstrably not enough: on 2026-09-05 the board had never had
the USB mount rule installed, because it was provisioned before those
lines existed, and every suite stayed green while the file channel could
not work at all. The repo was right and the board was wrong, and nothing
compared them.

Answer:

- what a fresh flash actually produces, run end to end, not read;
- whether `harden.sh` closes what it claims: 13 of 22 leak rows fail on
  the dev image and nobody has watched them go to zero;
- what `provision.sh` does when a step fails halfway, since it is a shell
  script with no transaction;
- whether the pinned Core hash is checked on the device or only on the
  builder;
- what a tester can verify for themselves without trusting either of us.
