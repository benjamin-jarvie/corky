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

echo "== radios off at every layer the OS controls"
# PLAN v1 promised this and nothing implemented it until 2026-09-05.
#
# Read the ladder in README "The freedom property" before trusting any of
# it: these layers stop the OS driving the radio. They do NOT prove the
# chip is unpowered. Raspberry Pi documents a hardware disable pin for the
# Compute Modules and not for the Zero 2 W, and `disable-wifi` disables the
# SDIO host controller while the chip keeps its power
# (docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md). Only
# removing the part is physics. This is everything short of that.
CFG="${CFG:-/boot/firmware/config.txt}"
for ov in disable-wifi disable-bt; do
    grep -q "^dtoverlay=$ov" "$CFG" || echo "dtoverlay=$ov" >> "$CFG"
done

# 2. The drivers cannot load, so nothing binds even if an overlay is lost.
cat > /etc/modprobe.d/corky-no-radio.conf <<'MODEOF'
# Corky: this device has no use for a radio.
blacklist brcmfmac
blacklist brcmutil
blacklist cfg80211
blacklist bluetooth
blacklist btbcm
blacklist hci_uart
blacklist btsdio
install brcmfmac /bin/false
install bluetooth /bin/false
install hci_uart /bin/false
MODEOF

# 3. No firmware, so the chip cannot be brought up even by a loaded driver.
#    Kept, not deleted, so the change is reversible and auditable.
if [ -d /lib/firmware/brcm ] && [ ! -d /lib/firmware/brcm.corky-disabled ]; then
    mv /lib/firmware/brcm /lib/firmware/brcm.corky-disabled
fi

# 4. Nothing tries to bring a network up.
for unit in wpa_supplicant bluetooth hciuart dhcpcd NetworkManager \
            systemd-networkd avahi-daemon triggerhappy; do
    systemctl disable --now "$unit" 2>/dev/null || true
    systemctl mask "$unit" 2>/dev/null || true
done

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
