# 05 README radios paragraph: removal is the instruction

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

README's radios paragraph presents hardware removal as an optional extra
("for hardware-level assurance") on the pocket build. Ben's decision
(2026-08-31): the pocket build must explicitly say remove the wireless
hardware, and that this is soldering work; the CM4 was chosen because it
has no radio silicon to remove. What does the paragraph say now?

Fix: rewrite the "Radios" paragraph in README.md. Removal is the
instruction, soldering named as the skill required, firmware disable
demoted to a backup layer, CM4 stated as the build for people who will
not solder.

## Resolution (2026-08-31)

Done. README's radios paragraph now says: the pocket build instruction is
to remove the wireless hardware (desolder the wireless front-end
component), this is soldering work, and people who will not solder build
the CM4 version, which was chosen because it has no wireless silicon.
Firmware disable and driver blacklist are named as backup layers that do
not replace removal. The claim "air-gapped by physics" stays reserved for
the CM4 build. PLAN.md untouched per the map's out-of-scope rule.

## Amended (2026-08-31, Ben's answer)

Ben chose a two-tier claim ladder for the Zero 2 W: front-end removal =
radio-removed; removing the whole wireless chip as well = air-gapped by
physics, the same property the CM4 has by manufacture. README updated.

Closed. Trello BB-25.
