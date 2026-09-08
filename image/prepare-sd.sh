#!/bin/bash
# Corky dev-image step 1 of 2 — run on the Mac AFTER flashing the SD with
# Raspberry Pi Imager (OS per image/PINS: Raspberry Pi OS Lite 64-bit;
# enable SSH + set a user in Imager's settings).
#
# Copies the provisioning payload onto the SD's boot partition so the Pi
# can finish its own setup over the network (CM4 carrier: Ethernet cable;
# Zero 2 W: WiFi set in Imager, the board has no Ethernet port).
#
# Usage: ./image/prepare-sd.sh [/Volumes/bootfs]
set -euo pipefail

BOOT="${1:-/Volumes/bootfs}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$BOOT" ] || { echo "boot partition not found at $BOOT (flash first, reinsert SD)"; exit 1; }
[ -f "$BOOT/config.txt" ] || { echo "$BOOT does not look like a Pi boot partition"; exit 1; }

# git archive packs the COMMITTED tree. Edit a file, forget to commit,
# and the card gets the previous version while you read the new one on
# screen. Say so rather than letting somebody test the wrong code.
if ! git -C "$REPO" diff-index --quiet HEAD -- 2>/dev/null; then
    echo "!! The working tree has uncommitted changes."
    echo "!! git archive packs HEAD, so those changes will NOT be on the card."
    echo "!! Commit them, or re-run with ALLOW_DIRTY=1 to card HEAD anyway."
    git -C "$REPO" status --short | sed 's/^/     /'
    [ "${ALLOW_DIRTY:-0}" = "1" ] || exit 1
fi

COMMIT="$(git -C "$REPO" rev-parse HEAD)"
echo "-- packing corky @ ${COMMIT:0:12}"
# Only what the device runs. `git archive HEAD` shipped the whole
# repository: 56 documentation files, 48 test files, and 38 Python files
# that never execute on the signer. A signer should carry the program and
# nothing else, and every extra file is one more thing to audit.
# tests/test_image_contents.py pins this list against provision.sh.
git -C "$REPO" archive --format=tar.gz -o "$BOOT/corky.tar.gz" HEAD \
    corky hw/vendor hw/HARDWARE.md image m0/bitcoin.conf LICENSE

# What went on the card, so the device can check it and a tester can say
# which Corky they are running. provision.sh refuses a tarball whose hash
# does not match; without this the signer's OWN CODE was the one thing
# provisioning never verified, while Bitcoin Core was verified twice
# (audit of image/, 2026-09-08).
TARBALL_SHA="$(shasum -a 256 "$BOOT/corky.tar.gz" 2>/dev/null \
                 || sha256sum "$BOOT/corky.tar.gz")"
TARBALL_SHA="${TARBALL_SHA%% *}"
sed -e "s/^CORKY_COMMIT=.*/CORKY_COMMIT=\"$COMMIT\"/" \
    "$REPO/image/PINS" > "$BOOT/corky-PINS"
printf '\n# Written by prepare-sd.sh for this card.\nCORKY_TARBALL_SHA256="%s"\n' \
    "$TARBALL_SHA" >> "$BOOT/corky-PINS"
echo "   corky.tar.gz sha256 ${TARBALL_SHA:0:16}…, commit pinned in corky-PINS"
cp "$REPO/image/provision.sh" "$BOOT/corky-provision.sh"
cp "$REPO/image/corky.service" "$BOOT/corky.service"
cp "$REPO/image/corky-bitcoind.service" "$BOOT/corky-bitcoind.service"
cp "$REPO/image/corky-splash.service" "$BOOT/corky-splash.service"

echo "-- done. Next:"
echo "   1. Eject, insert into the Pi, power on. Network: CM4 carrier ="
echo "      Ethernet cable; Zero 2 W = WiFi from Imager (no Ethernet port)."
echo "   2. ssh <user>@corky.local"
echo "   3. sudo bash /boot/firmware/corky-provision.sh"
