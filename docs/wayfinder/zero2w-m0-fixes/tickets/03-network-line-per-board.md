# 03 Image docs say Ethernet; the Zero 2 W has none

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

image/README.md and image/prepare-sd.sh say "boot the Pi on an Ethernet
cable". That sentence was written for the CM4 carrier (Waveshare
CM4-IO-BASE-B, which has a Gigabit RJ45 per its wiki). The Pi Zero 2 W has
no Ethernet port, so the dev-image flow dead-ends on the pocket build.
What wording covers both boards?

Fix: both files state the network path per board. CM4 carrier: Ethernet
cable. Zero 2 W: WiFi set in Imager's settings before flashing, as
m0/FLASH.md already says.

## Resolution (2026-08-31)

Done. image/README.md step 2 and both the header comment and the final
echo of image/prepare-sd.sh now state the path per board: CM4 carrier =
Ethernet cable (RJ45 confirmed on the Waveshare CM4-IO-BASE-B wiki),
Zero 2 W = WiFi set in Imager before flashing. `bash -n` passes.

Closed. Trello BB-23.
