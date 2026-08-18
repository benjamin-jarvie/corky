#!/bin/bash
# Corky dev-image step 1 of 2 — run on the Mac AFTER flashing the SD with
# Raspberry Pi Imager (OS per image/PINS: Raspberry Pi OS Lite 64-bit;
# enable SSH + set a user in Imager's settings).
#
# Copies the provisioning payload onto the SD's boot partition so the Pi
# can finish its own setup over the Ethernet cable.
#
# Usage: ./image/prepare-sd.sh [/Volumes/bootfs]
set -euo pipefail

BOOT="${1:-/Volumes/bootfs}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$BOOT" ] || { echo "boot partition not found at $BOOT (flash first, reinsert SD)"; exit 1; }
[ -f "$BOOT/config.txt" ] || { echo "$BOOT does not look like a Pi boot partition"; exit 1; }

echo "-- packing corky @ $(git -C "$REPO" rev-parse --short HEAD)"
git -C "$REPO" archive --format=tar.gz -o "$BOOT/corky.tar.gz" HEAD

cp "$REPO/image/PINS" "$BOOT/corky-PINS"
cp "$REPO/image/provision.sh" "$BOOT/corky-provision.sh"
cp "$REPO/image/corky.service" "$BOOT/corky.service"
cp "$REPO/image/corky-bitcoind.service" "$BOOT/corky-bitcoind.service"

echo "-- done. Next:"
echo "   1. Eject, insert into the Pi, connect Ethernet, power on."
echo "   2. ssh <user>@corky.local"
echo "   3. sudo bash /boot/firmware/corky-provision.sh"
