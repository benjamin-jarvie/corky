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
    cd /tmp
    curl -fSLO "$CORE_URL"
    curl -fSLO "$(dirname "$CORE_URL")/SHA256SUMS"
    if [ "$CORE_SHA256" = "UNPINNED_UNTIL_FIRST_FLASH" ]; then
        # SHA256SUMS from the same server proves nothing (checksum theater).
        # Refuse to install: verify out-of-band, pin, re-run.
        echo "!! CORE_SHA256 is unpinned. Tarball hash is:"
        sha256sum "$CORE_TARBALL"
        echo "!! Verify it against SHA256SUMS + the Guix attestation GPG keys"
        echo "!! on a trusted machine, record it in image/PINS, re-run."
        exit 1
    fi
    echo "$CORE_SHA256  $CORE_TARBALL" | sha256sum -c -
    tar xzf "$CORE_TARBALL"
    install -m 755 "bitcoin-$CORE_VERSION/bin/bitcoind" "bitcoin-$CORE_VERSION/bin/bitcoin-cli" /usr/local/bin/
fi
bitcoind --version | head -1

echo "== 2/5 system packages"
apt-get update -qq
# libzbar0: pyzbar (in PIP_PINS) dlopens it at import; pip cannot provide it.
apt-get install -y -qq python3-pil python3-rpi.gpio python3-spidev \
    python3-picamera2 python3-zbar libzbar0 python3-pip 2>/dev/null \
  || apt-get install -y -qq python3-pil python3-rpi.gpio python3-spidev libzbar0 python3-pip
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
# The USB PSBT channel's mount point. Mounting the stick here is the
# operator's step; until it is mounted the directory is simply empty.
mkdir -p /mnt/usb
systemctl daemon-reload
echo "   enable boot-to-corky with: sudo systemctl enable --now corky"

# SPI for the display hat
raspi-config nonint do_spi 0 || true

echo
echo "PROVISION DONE (dev image). Sanity check:"
echo "  cd /opt/corky && python3 shim/test_shim.py && python3 m0/m0_gate.py"
