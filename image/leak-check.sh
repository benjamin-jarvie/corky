#!/bin/bash
# Corky: every way data could leave this board, and what the OS can prove.
#
# Run this ON THE DEVICE, as root:   sudo bash /opt/corky/image/leak-check.sh
#
# READ THIS BEFORE YOU TRUST THE RESULT.
#
# Every check below asks the operating system whether it is driving the
# wireless hardware. A clean run means the OS has no driver bound, no
# firmware to load, no service trying, and no interface up. It does NOT
# mean the chip has no power. Raspberry Pi documents a hardware disable
# pin for the Compute Modules and not for the Zero 2 W, and the
# `disable-wifi` overlay disables the SDIO host controller while the chip
# keeps its power.
#
# So there are two claims, and they are not the same claim:
#   OS silent    - this script can check it. That is what a PASS means.
#   Radio absent - only removing the part proves it. No script can.
#
# The Zero 2 W's radio is a separate component beside the processor, not
# inside it, so removal is possible. See
# docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md.

PASS=0; FAIL=0
ok()   { printf "  ok    %s\n" "$1"; PASS=$((PASS+1)); }
bad()  { printf "  FAIL  %s\n" "$1"; FAIL=$((FAIL+1)); }
note() { printf "        %s\n" "$1"; }

echo "Corky leak check, $(date -u '+%Y-%m-%d %H:%M UTC') on $(hostname)"
echo
echo "1. Firmware overlays"
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
for ov in disable-wifi disable-bt; do
    if grep -q "^dtoverlay=$ov" "$CFG" 2>/dev/null; then
        ok "$CFG sets dtoverlay=$ov"
    else
        bad "$CFG does NOT set dtoverlay=$ov"
    fi
done

echo
echo "2. Kernel drivers"
for mod in brcmfmac brcmutil cfg80211 bluetooth btbcm hci_uart; do
    if lsmod 2>/dev/null | grep -qw "^$mod"; then
        bad "module $mod is LOADED"
    else
        ok "module $mod is not loaded"
    fi
done
if [ -f /etc/modprobe.d/corky-no-radio.conf ]; then
    ok "the blacklist file is installed"
else
    bad "no /etc/modprobe.d/corky-no-radio.conf"
fi

echo
echo "3. Firmware blobs"
if [ -d /lib/firmware/brcm ]; then
    bad "/lib/firmware/brcm is present, so a driver could bring the chip up"
    note "$(find /lib/firmware/brcm -type f 2>/dev/null | wc -l) files"
else
    ok "/lib/firmware/brcm is absent"
    [ -d /lib/firmware/brcm.corky-disabled ] && \
        note "kept at /lib/firmware/brcm.corky-disabled, so this is reversible"
fi

echo
echo "4. Interfaces"
IFACES=$(ls /sys/class/net 2>/dev/null | grep -vE '^(lo|usb|eth)' | tr '\n' ' ')
if [ -z "$IFACES" ]; then
    ok "no wireless interface exists"
else
    bad "interfaces present: $IFACES"
fi
if command -v rfkill >/dev/null 2>&1; then
    RF=$(rfkill list 2>/dev/null)
    if [ -z "$RF" ]; then ok "rfkill lists no radio"; else bad "rfkill sees a radio"; note "$RF"; fi
fi
if command -v hciconfig >/dev/null 2>&1; then
    if [ -z "$(hciconfig 2>/dev/null)" ]; then
        ok "hciconfig lists no Bluetooth device"
    else
        bad "hciconfig sees a Bluetooth device"
    fi
fi

echo
echo "5. Services"
for unit in wpa_supplicant bluetooth hciuart dhcpcd NetworkManager systemd-networkd; do
    STATE=$(systemctl is-enabled "$unit" 2>/dev/null || echo absent)
    ACTIVE=$(systemctl is-active "$unit" 2>/dev/null || echo inactive)
    if [ "$ACTIVE" = "active" ]; then
        bad "$unit is RUNNING"
    elif [ "$STATE" = "masked" ] || [ "$STATE" = "absent" ] || [ "$STATE" = "disabled" ]; then
        ok "$unit is $STATE"
    else
        bad "$unit is $STATE"
    fi
done

echo
echo "6. What the kernel saw at boot"
if dmesg 2>/dev/null | grep -qiE "brcmfmac|bluetooth|hci0"; then
    bad "the kernel log mentions the radio; read it with: dmesg | grep -i brcm"
else
    ok "the kernel log has no radio bring-up"
fi

echo
echo "7. Swap, the worst path off this board"
if [ -n "$(swapon --show 2>/dev/null)" ]; then
    bad "SWAP IS ON. Key pages can be written to the card."
    note "$(swapon --show 2>/dev/null | tail -n +2)"
else
    ok "no swap is active"
fi
for unit in dphys-swapfile dev-zram0.swap swap.target; do
    STATE=$(systemctl is-enabled "$unit" 2>/dev/null || echo absent)
    case "$STATE" in
        masked|absent|disabled) ok "$unit is $STATE" ;;
        *) bad "$unit is $STATE and could bring swap back at reboot" ;;
    esac
done
if grep -qE '\sswap\s' /etc/fstab 2>/dev/null; then
    bad "/etc/fstab still has a swap entry"
else
    ok "/etc/fstab has no swap entry"
fi

echo
echo "8. The journal, which keeps a record of sessions"
if [ -d /var/log/journal ]; then
    bad "/var/log/journal exists, so the journal is written to the card"
else
    ok "no persistent journal directory"
fi
if grep -rqs "Storage=volatile" /etc/systemd/journald.conf.d/ /etc/systemd/journald.conf; then
    ok "journald is set to keep the log in RAM"
else
    bad "journald is not set to Storage=volatile"
fi

echo
echo "9. Consoles and ports that are not the panel"
CMDLINE=/boot/firmware/cmdline.txt
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt
if grep -qE "console=(serial0|ttyAMA0|ttyS0)" "$CMDLINE" 2>/dev/null; then
    bad "a serial console is on the GPIO header: three wires is a root shell"
else
    ok "no serial console in $CMDLINE"
fi
for unit in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    STATE=$(systemctl is-enabled "$unit" 2>/dev/null || echo absent)
    case "$STATE" in
        masked|absent|disabled) ok "$unit is $STATE" ;;
        *) bad "$unit is $STATE" ;;
    esac
done
if [ -e /sys/class/udc ] && [ -n "$(ls /sys/class/udc 2>/dev/null)" ]; then
    bad "a USB device controller is active: this board can pretend to be a"
    note "network card, a serial port or a disk to any computer it is plugged into"
else
    ok "no USB device controller: the port is a host, not a device"
fi
if [ -f /etc/modprobe.d/corky-no-gadget.conf ]; then
    ok "the USB gadget drivers are blacklisted"
else
    bad "no USB gadget blacklist"
fi
if command -v tvservice >/dev/null 2>&1 || [ -d /sys/class/drm ]; then
    ATTACHED=$(grep -l "^connected" /sys/class/drm/*/status 2>/dev/null | wc -l)
    if [ "$ATTACHED" -eq 0 ]; then
        ok "no display is attached over HDMI"
    else
        note "$ATTACHED HDMI output(s) connected. The panel is SPI, so HDMI"
        note "carries only the boot console. Unplug it for a signing session."
    fi
fi

echo
echo "10. Bitcoin Core's own networking"
CONF=/etc/corky-bitcoin.conf
if grep -q "^networkactive=0" "$CONF" 2>/dev/null; then
    ok "$CONF sets networkactive=0"
else
    bad "$CONF does not set networkactive=0"
fi

echo
echo "==================================================================="
if [ "$FAIL" -eq 0 ]; then
    echo "OS SILENT: $PASS checks passed."
else
    echo "$FAIL of $((PASS+FAIL)) checks FAILED. The OS can still drive a radio."
fi
echo
echo "This says the operating system is not driving any way off this board:"
echo "no radio, no swap to the card, no journal on the card, no console on"
echo "the header, and no USB device mode."
echo
echo "It does NOT say the wireless chip is unpowered. Only removing the"
echo "part says that, and on the Zero 2 W the radio is a separate component"
echo "beside the processor, so removal is possible. A device that has to be"
echo "silent by physics is a device with the part taken off."
echo
echo "What no script can check: the activity LED can be modulated, and the"
echo "power line and the panel both emit. Those need a room, not a config."
echo "==================================================================="
exit $FAIL
