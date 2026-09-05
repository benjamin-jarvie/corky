#!/bin/bash
# Corky dev-image step 2 of 2 — run ON THE PI over SSH (or HDMI+keyboard):
#   sudo bash /boot/firmware/corky-provision.sh
#
# Idempotent: safe to re-run. Builds the DEV image (SSH stays on).
# The RELEASE image hardening (network stack removal, read-only root,
# reproducible build) is M3 work and deliberately not here.
set -euo pipefail

BOOT=/boot/firmware
PINS="$BOOT/corky-PINS"
[ -f "$PINS" ] || { echo "corky-PINS missing from $BOOT — run prepare-sd.sh first"; exit 1; }
# shellcheck disable=SC1090
source "$PINS"

echo "== 1/5 Bitcoin Core $CORE_VERSION"
if ! command -v bitcoind >/dev/null || ! bitcoind --version | grep -q "v$CORE_VERSION"; then
    if [ "$CORE_SHA256" = "UNPINNED_UNTIL_FIRST_FLASH" ]; then
        # Refuse before downloading. The hash has to come from a trusted
        # machine anyway: SHA256SUMS served by the host that served the
        # binary proves nothing, so there is nothing useful to learn here.
        echo "!! CORE_SHA256 is unpinned, refusing to install Bitcoin Core."
        echo "!! On a trusted machine, verify the tarball against SHA256SUMS"
        echo "!! and the builder GPG keys from the guix.sigs repo, then record"
        echo "!! the hash in image/PINS and re-run."
        exit 1
    fi
    # NOT /tmp. On Trixie /tmp is a tmpfs sized at half of RAM, which is
    # 208MB on a Zero 2 W. The tarball is 82MB and unpacks to more than
    # that, so the extract dies part-written, and filling that tmpfs eats
    # the very RAM the M0 gate exists to measure. Work on disk instead.
    work="$(mktemp -d /var/tmp/corky-core.XXXXXX)"
    trap 'rm -rf "$work"' EXIT
    curl -fSL -o "$work/$CORE_TARBALL" "$CORE_URL"
    echo "$CORE_SHA256  $work/$CORE_TARBALL" | sha256sum -c -
    # Only the two binaries Corky runs. bitcoin-qt and test_bitcoin are most
    # of the archive by size and neither is ever executed.
    tar xzf "$work/$CORE_TARBALL" -C "$work" \
        "bitcoin-$CORE_VERSION/bin/bitcoind" "bitcoin-$CORE_VERSION/bin/bitcoin-cli"
    install -m 755 "$work/bitcoin-$CORE_VERSION/bin/bitcoind" \
                   "$work/bitcoin-$CORE_VERSION/bin/bitcoin-cli" /usr/local/bin/
    rm -rf "$work"
    trap - EXIT
fi
bitcoind --version | head -1

echo "== 2/5 system packages"
apt-get update -qq
# Every package the device needs, each installed on its own line, so a
# name that does not exist in this release cannot take another package
# down with it. The old form asked for seven at once and fell back to a
# list that quietly dropped python3-picamera2, so an unavailable
# python3-zbar would have cost the camera and said nothing until a scan
# failed on the board.
# libzbar0: pyzbar (in PIP_PINS) dlopens it at import; pip cannot provide it.
REQUIRED_PKGS="python3-pil python3-rpi.gpio python3-spidev python3-picamera2 libzbar0 python3-pip"
for pkg in $REQUIRED_PKGS; do
    apt-get install -y -qq "$pkg" || {
        echo "!! required package $pkg did not install. Stopping."
        echo "!! The signer needs all of: $REQUIRED_PKGS"
        exit 1
    }
done
# python3-zbar may not exist in this release. pyzbar comes from pip and
# only needs libzbar0 above, so this is a convenience, not a requirement.
apt-get install -y -qq python3-zbar 2>/dev/null \
  || echo "   (python3-zbar unavailable; pyzbar from pip covers it)"
# shellcheck disable=SC2086
python3 -m pip install --quiet --break-system-packages $PIP_PINS

echo "== 3/5 corky -> /opt/corky"
rm -rf /opt/corky      # stale files from a prior provision must not survive
mkdir -p /opt/corky
tar xzf "$BOOT/corky.tar.gz" -C /opt/corky
cp "$BOOT/corky-PINS" /opt/corky/PINS.installed

echo "== 4/5 ramdisk datadir + bitcoin.conf"
mkdir -p /run/corky
grep -q "corky-ramdisk" /etc/fstab || \
    echo "tmpfs /run/corky tmpfs rw,nosuid,nodev,size=128m,mode=0700 0 0 # corky-ramdisk" >> /etc/fstab
mount /run/corky 2>/dev/null || true
install -m 644 /opt/corky/m0/bitcoin.conf /etc/corky-bitcoin.conf

echo "== 5/5 systemd units (installed, NOT enabled on the dev image)"
install -m 644 "$BOOT/corky.service" /etc/systemd/system/corky.service
install -m 644 "$BOOT/corky-bitcoind.service" /etc/systemd/system/corky-bitcoind.service
install -m 644 "$BOOT/corky-splash.service" /etc/systemd/system/corky-splash.service
# The USB PSBT channel mounts itself (map e2e-before-testers, ticket 15).
install -m 644 /opt/corky/image/corky-usb@.service /etc/systemd/system/corky-usb@.service
install -m 644 /opt/corky/image/99-corky-usb.rules /etc/udev/rules.d/99-corky-usb.rules
udevadm control --reload-rules || true
# The USB PSBT channel's mount point. A stick that is plugged in mounts
# itself here through the udev rule above; until one is, it is empty.
mkdir -p /mnt/usb
systemctl daemon-reload
echo "   enable boot-to-corky with: sudo systemctl enable --now corky"

CFG0="${CFG0:-/boot/firmware/config.txt}"
[ -f "$CFG0" ] || CFG0=/boot/config.txt

echo "== nothing writes secrets to the card, and no console leaves the board"
# SWAP. This is the worst leak path on the device and it was open until
# 2026-09-05. Raspberry Pi OS enables swap by default, so the Python heap
# holding a key can be paged to the SD card, which defeats the whole
# "nothing persists" claim. m0/FLASH.md told the operator to run
# `swapoff -a` by hand for the gate, and noted it comes back at reboot.
# A signer must never have swap at all.
systemctl disable --now dphys-swapfile 2>/dev/null || true
systemctl mask dphys-swapfile 2>/dev/null || true
apt-get purge -y -qq dphys-swapfile 2>/dev/null || true
# Trixie: systemd-zram-generator owns dev-zram0.swap and recreates it.
systemctl mask dev-zram0.swap swap.target 2>/dev/null || true
rm -f /etc/systemd/zram-generator.conf
printf '[swap]\nzram-size = 0\n' > /etc/systemd/zram-generator.conf
swapoff -a 2>/dev/null || true
sed -i '/\sswap\s/d' /etc/fstab 2>/dev/null || true

# THE JOURNAL. Core quotes keys back in its errors and Corky redacts them,
# but a journal on the card is still a permanent record of a session.
# Keep it in RAM, where it dies with the power like everything else.
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/corky-volatile.conf <<'JEOF'
[Journal]
Storage=volatile
RuntimeMaxUse=16M
JEOF
rm -rf /var/log/journal

# THE SERIAL CONSOLE. Raspberry Pi OS puts a login console on GPIO pins 8
# and 10 by default. Three wires and physical access is a root shell on a
# device holding a key. The panel is the only interface this device has.
CMDLINE="${CMDLINE:-/boot/firmware/cmdline.txt}"
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt
if [ -f "$CMDLINE" ]; then
    sed -i 's/console=serial0,[0-9]*//g; s/console=ttyAMA0,[0-9]*//g; s/  */ /g' "$CMDLINE"
fi
systemctl disable --now serial-getty@ttyAMA0.service serial-getty@ttyS0.service 2>/dev/null || true
systemctl mask serial-getty@ttyAMA0.service serial-getty@ttyS0.service 2>/dev/null || true
grep -q "^enable_uart=0" "$CFG0" 2>/dev/null || echo "enable_uart=0" >> "${CFG0:-/boot/firmware/config.txt}"

# USB. The Zero's port can be a HOST or a DEVICE. As a device it can
# enumerate to a computer as a network card, a serial port or a disk, all
# of which are ways off this board. Force host mode and refuse the gadget
# drivers.
grep -q "^dtoverlay=dwc2,dr_mode=host" "${CFG0:-/boot/firmware/config.txt}" || \
    echo "dtoverlay=dwc2,dr_mode=host" >> "${CFG0:-/boot/firmware/config.txt}"
cat > /etc/modprobe.d/corky-no-gadget.conf <<'GEOF'
# Corky: this device is a USB host. It is never a USB device.
blacklist g_ether
blacklist g_serial
blacklist g_mass_storage
blacklist g_multi
blacklist libcomposite
blacklist usb_f_ecm
blacklist usb_f_rndis
GEOF

# The radios, the serial console and SSH are NOT touched here. This script
# builds the DEV image, and the dev image keeps them so you can work on the
# board over the network. Taking them away is image/harden.sh, which is a
# one-way step you run when the device is about to hold a real key.
echo "== dev image: radios and SSH stay. Run image/harden.sh before real keys."

# SPI for the display hat
raspi-config nonint do_spi 0 || true

# Corky is headless: the panel is a 320x240 ST7789 on SPI, driven by
# hw/vendor/st7789.py, so the firmware's GPU split buys nothing.
#
# Measured on a Zero 2 W, 2026-09-03, one reboot per row:
#
#   config                    total  avail  vc_sm    err lines
#   stock (vc4 on, split 64)   415    276   OK        0
#   vc4 OFF, split 64          414    281   OK        0
#   vc4 on,  split 32          447    307   OK        0
#   vc4 off, split 32          446    309   OK        0
#   vc4 off, split 48          430    294   OK        0
#   vc4 off, split 16          462    334   BROKEN    5
#
# Two things that table settles. Disabling the vc4 KMS overlay gains
# nothing at all (414 against 415), so it is left alone and the HDMI
# console keeps working. And 16 is below the floor: the VideoCore
# services die with "vc_sm_cma_vchi_init: failed to open VCHI service",
# which takes bcm2835_isp with them, and that is the ISP libcamera uses.
# 32 is the smallest split that keeps them healthy.
CFG=/boot/firmware/config.txt
if ! grep -q "^gpu_mem=" "$CFG"; then
    cp -n "$CFG" "$CFG.pre-corky"     # one file to put the stock split back
    printf '\n# Corky: headless signer. 32 is the floor; 16 starves the\n# VideoCore services that bcm2835_isp needs.\ngpu_mem=32\n' >> "$CFG"
    echo "   gpu_mem=32, +32MB of RAM (takes effect on reboot)"
fi

echo
echo "PROVISION DONE (dev image). Sanity check:"
echo "  the suites do not ship; run them from a clone on the dev machine"
