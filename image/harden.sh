#!/bin/bash
# Corky: turn a dev image into a signing image. ONE WAY.
#
#   sudo bash /opt/corky/image/harden.sh
#
# provision.sh builds a board you can work on: it keeps SSH, the radios and
# the serial console, because without them you cannot develop on it. That is
# the right trade for a board with no key on it, and the wrong one for a
# board that is about to hold yours.
#
# This script closes them. AFTER IT RUNS AND YOU REBOOT:
#   - there is no Wi-Fi and no Bluetooth, so there is no SSH
#   - there is no serial console on the GPIO header
#   - the only way in is the panel, the buttons and the camera
#
# To undo it you reflash the card. That is the point.
#
# What it does NOT do, and cannot: power the wireless chip down. The
# `disable-wifi` overlay disables the SDIO host controller and the chip
# keeps its power, and Raspberry Pi documents a hardware disable pin for the
# Compute Modules and not for the Zero 2 W. Only removing the part is
# physics. The radio on the Zero 2 W is a separate component beside the
# processor, so removal is possible. See
# docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run me as root"; exit 1; }

CFG0="${CFG0:-/boot/firmware/config.txt}"
[ -f "$CFG0" ] || CFG0=/boot/config.txt
CMDLINE="${CMDLINE:-/boot/firmware/cmdline.txt}"
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt

cat <<'WARN'
This removes network access to this board. You will not be able to log in
over SSH afterwards. The panel and the buttons become the only interface.
WARN
if [ "${ASSUME_YES:-}" != "1" ]; then
    printf "Type HARDEN to continue: "
    read -r reply
    [ "$reply" = "HARDEN" ] || { echo "nothing changed."; exit 1; }
fi

echo "== 1/5 firmware overlays"
for ov in disable-wifi disable-bt; do
    grep -q "^dtoverlay=$ov" "$CFG0" || echo "dtoverlay=$ov" >> "$CFG0"
done

echo "== 2/5 drivers cannot load"
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

echo "== 3/5 no firmware for the chip"
# Moved, not deleted, so the change is auditable and a reflash is not the
# only way to inspect what was there.
if [ -d /lib/firmware/brcm ] && [ ! -d /lib/firmware/brcm.corky-disabled ]; then
    mv /lib/firmware/brcm /lib/firmware/brcm.corky-disabled
fi

echo "== 4/5 nothing brings a network up, and nothing offers a login"
for unit in wpa_supplicant bluetooth hciuart dhcpcd NetworkManager \
            systemd-networkd avahi-daemon triggerhappy ssh sshd; do
    systemctl disable --now "$unit" 2>/dev/null || true
    systemctl mask "$unit" 2>/dev/null || true
done

echo "== 5/5 no console on the GPIO header"
sed -i 's/console=serial0,[0-9]*//g; s/console=ttyAMA0,[0-9]*//g; s/  */ /g' "$CMDLINE"
grep -q "^enable_uart=0" "$CFG0" || echo "enable_uart=0" >> "$CFG0"
for unit in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    systemctl disable --now "$unit" 2>/dev/null || true
    systemctl mask "$unit" 2>/dev/null || true
done

echo
echo "Done. REBOOT, then check it with:"
echo "  sudo bash /opt/corky/image/leak-check.sh"
echo "You will have to read that on the HDMI console or the panel, because"
echo "SSH is gone."
