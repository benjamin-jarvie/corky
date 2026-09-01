# Map: Zero 2 W fixes before the M0 gate run

Labels: wayfinder:map
Status: COMPLETE 2026-08-31. All five tickets closed; the route is walked.

## Destination

Five fixes land in the repo before Ben runs the M0 gate on the Pi Zero 2 W
(Friday 2026-09-04, Trello BB-20): a gate that cannot give a false verdict,
image docs that match the board, and a README that states the pocket-build
radio policy the way Ben decided it.

## Notes

- Ben's instruction (2026-08-31): execution is carried in-map. All five
  tickets are `wayfinder:task` (AFK); this effort fixes them, it does not
  only decide them.
- Domain words from README.md: "primary build" = CM4 Lite on the Waveshare
  carrier; "pocket build" = Pi Zero 2 W. The gate is m0/m0_gate.py; its
  verdict rule lives in PLAN.md A-2.
- Ben's radio decision (2026-08-31, chat): the pocket build must explicitly
  instruct removal of the wireless hardware, soldering required. The CM4
  was chosen because it has no radio silicon. Firmware disable stays as a
  backup layer only.
- Style: ASD-STE100. No em dashes in new prose.

## Decisions so far

- [01 Swap invalidates the gate](tickets/01-swap-invalidates-the-gate.md) —
  gate exits 2 on active swap; FLASH.md opens with `sudo swapoff -a`.
- [02 MemAvailable needs a sampler thread](tickets/02-memavailable-sampler.md) —
  200ms daemon-thread floor merged with the two spot samples.
- [03 Image docs say Ethernet](tickets/03-network-line-per-board.md) —
  per-board network line in image/README.md and prepare-sd.sh; CM4
  carrier RJ45 confirmed against the Waveshare wiki.
- [04 pyzbar needs libzbar0](tickets/04-libzbar0-missing.md) — libzbar0 on
  both apt lines; pip cannot provide a shared library.
- [05 README radios paragraph](tickets/05-radios-paragraph.md) — removal
  is the instruction, soldering named; CM4 stated as the no-solder build;
  firmware disable demoted to backup layer. Amended: two-tier claim
  ladder (front-end off = radio-removed; whole chip off = air-gapped by
  physics).

## Not yet specified

- Whether `python3-zbar` exists as a package in RPi OS Bookworm. If it does
  not, provision.sh's first apt line never succeeds and python3-picamera2
  only installs by luck of the fallback. The first real provision run
  (dev image, after M0) answers this.

## Out of scope

- M3 release-image hardening (radio kill verification, no network stack,
  read-only root). PLAN.md owns that; nothing here touches it.
- PLAN.md's own radio wording. PLAN is the planning record; README.md is
  the document users read, and only it changes here.
