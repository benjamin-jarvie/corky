#!/bin/bash
# Corky: every way data could leave this board, and what the OS can prove.
#
# Run this ON THE DEVICE, as root:   sudo bash /opt/corky/image/leak-check.sh
# On the device itself it is Tools, Check for leaks.
#
# READ THIS BEFORE YOU TRUST THE RESULT.
#
# Every check below asks the operating system whether it is driving a way
# off this board. A clean run means the OS has no driver bound, no firmware
# to load, no service trying, no swap, no journal on the card, no console on
# the header and no USB device mode. It does NOT mean the wireless chip has
# no power. Raspberry Pi documents a hardware disable pin for the Compute
# Modules and not for the Zero 2 W, and the `disable-wifi` overlay disables
# the SDIO host controller while the chip keeps its power.
#
# So there are two claims, and they are not the same claim:
#   OS silent    - this script can check it. That is what a PASS means.
#   Radio absent - only removing the part proves it. No script can.
#
# The Zero 2 W's radio is a separate component beside the processor, not
# inside it, so removal is possible. See
# docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md.
#
# --porcelain prints one tab-separated record per check and nothing else:
#     ok|FAIL <tab> what it is <tab> what it is doing
# The device's own Tools screen reads that. The checks are written once and
# read two ways.

PASS=0; FAIL=0
PORCELAIN=0
[ "${1:-}" = "--porcelain" ] && PORCELAIN=1
say()  { [ "$PORCELAIN" -eq 1 ] || printf "%s\n" "$1"; }
ok()   { PASS=$((PASS+1))
         if [ "$PORCELAIN" -eq 1 ]; then printf "ok\t%s\t%s\n" "$1" "$2"
         else printf "  ok    %-22s %s\n" "$1" "$2"; fi; }
bad()  { FAIL=$((FAIL+1))
         if [ "$PORCELAIN" -eq 1 ]; then printf "FAIL\t%s\t%s\n" "$1" "$2"
         else printf "  LEAK  %-22s %s\n" "$1" "$2"; fi; }

# systemctl prints its answer on stdout AND exits non-zero for a unit that
# does not exist, so the answer must be read as one line and the exit code
# ignored. Getting this wrong reported "not-found\nabsent" and failed every
# check (found on the board, 2026-09-05).
unit_state()  { systemctl is-enabled "$1" 2>/dev/null | head -1 | tr -d '\r'; }
unit_active() { systemctl is-active "$1" 2>/dev/null | head -1; }
# A unit that cannot run is as good as one that is masked. "static" means
# the unit has no enable switch, which is normal and says nothing either way.
unit_off()    { case "$1" in masked|disabled|not-found|""|absent) return 0 ;;
                            *) return 1 ;; esac; }

# One service, one row: is it running, and can it come back?
service_row() {
    local label="$1" unit="$2" state active
    active=$(unit_active "$unit"); state=$(unit_state "$unit")
    [ -n "$state" ] || state=not-found
    if [ "$active" = "active" ]; then
        bad "$label" "running"
    elif unit_off "$state"; then
        ok "$label" "off"
    else
        bad "$label" "starts at boot"
    fi
}

CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
CMDLINE=/boot/firmware/cmdline.txt
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt

say "Corky leak check, $(date -u '+%Y-%m-%d %H:%M UTC') on $(hostname)"
say ""
say "RADIO"

grep -q "^dtoverlay=disable-wifi" "$CFG" 2>/dev/null \
    && ok "Wi-Fi overlay" "disabled" || bad "Wi-Fi overlay" "not set"
grep -q "^dtoverlay=disable-bt" "$CFG" 2>/dev/null \
    && ok "Bluetooth overlay" "disabled" || bad "Bluetooth overlay" "not set"

WIFI_MODS=$(lsmod 2>/dev/null | grep -cE "^(brcmfmac|brcmutil|cfg80211)")
[ "$WIFI_MODS" -eq 0 ] && ok "Wi-Fi driver" "not loaded" \
                       || bad "Wi-Fi driver" "loaded"
BT_MODS=$(lsmod 2>/dev/null | grep -cE "^(bluetooth|btbcm|hci_uart|btsdio)")
[ "$BT_MODS" -eq 0 ] && ok "Bluetooth driver" "not loaded" \
                     || bad "Bluetooth driver" "loaded"

[ -f /etc/modprobe.d/corky-no-radio.conf ] \
    && ok "Driver blacklist" "installed" || bad "Driver blacklist" "missing"

[ -d /lib/firmware/brcm ] && bad "Radio firmware" "on the card" \
                          || ok "Radio firmware" "removed"

WIFI_IF=$(ls /sys/class/net 2>/dev/null | grep -vE '^(lo|usb|eth)' | tr '\n' ' ')
[ -z "$WIFI_IF" ] && ok "Wi-Fi interface" "none" \
                  || bad "Wi-Fi interface" "$(echo "$WIFI_IF" | tr -d ' ')"
if command -v hciconfig >/dev/null 2>&1; then
    [ -z "$(hciconfig 2>/dev/null)" ] && ok "Bluetooth device" "none" \
                                      || bad "Bluetooth device" "present"
fi
service_row "Wi-Fi service" wpa_supplicant
service_row "Bluetooth service" bluetooth
service_row "Network manager" NetworkManager

if dmesg 2>/dev/null | grep -qiE "brcmfmac|Bluetooth: hci"; then
    bad "Radio at boot" "brought up"
else
    ok "Radio at boot" "silent"
fi

say ""
say "THE CARD"

if [ -n "$(swapon --show 2>/dev/null)" ]; then
    bad "Swap" "ON, key pages can reach the card"
else
    ok "Swap" "off"
fi
SWAP_BACK=no
for unit in dphys-swapfile dev-zram0.swap; do
    st=$(unit_state "$unit"); [ -n "$st" ] || st=not-found
    unit_off "$st" || SWAP_BACK=yes
done
[ -f /etc/systemd/zram-generator.conf ] \
    && grep -qE "zram-size *= *0" /etc/systemd/zram-generator.conf || {
        [ -x /usr/lib/systemd/system-generators/zram-generator ] && SWAP_BACK=yes; }
[ "$SWAP_BACK" = "no" ] && ok "Swap at boot" "cannot return" \
                        || bad "Swap at boot" "comes back"

[ -d /var/log/journal ] && bad "Journal" "written to the card" \
                        || ok "Journal" "in RAM only"

say ""
say "PORTS AND CONSOLES"

grep -qE "console=(serial0|ttyAMA0|ttyS0)" "$CMDLINE" 2>/dev/null \
    && bad "Serial console" "on the GPIO header" \
    || ok "Serial console" "off"
GETTY=off
for unit in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    st=$(unit_state "$unit"); [ -n "$st" ] || st=not-found
    unit_off "$st" || GETTY=on
done
[ "$GETTY" = "off" ] && ok "Serial login" "off" || bad "Serial login" "enabled"

if [ -n "$(ls /sys/class/udc 2>/dev/null)" ]; then
    bad "USB device mode" "active, can pretend to be a disk"
else
    ok "USB device mode" "off, host only"
fi
[ -f /etc/modprobe.d/corky-no-gadget.conf ] \
    && ok "USB gadget blacklist" "installed" \
    || bad "USB gadget blacklist" "missing"

ATTACHED=$(grep -l "^connected" /sys/class/drm/*/status 2>/dev/null | wc -l)
[ "$ATTACHED" -eq 0 ] && ok "HDMI" "nothing attached" \
                      || ok "HDMI" "a screen is plugged in"

service_row "Remote login" ssh

say ""
say "BITCOIN CORE"
grep -q "^networkactive=0" /etc/corky-bitcoin.conf 2>/dev/null \
    && ok "Core networking" "off" || bad "Core networking" "on"

say ""
say "==================================================================="
if [ "$FAIL" -eq 0 ]; then
    say "OS SILENT: all $PASS checks pass."
    say ""
    say "The operating system is not driving any way off this board."
else
    say "$FAIL of $((PASS+FAIL)) checks found a way off this board."
    say ""
    say "A DEV image is expected to fail the radio and login rows, because"
    say "it keeps SSH so you can work on it. Run image/harden.sh when the"
    say "device is about to hold a real key. That step is one way: it takes"
    say "SSH away."
fi
say ""
say "None of this says the wireless chip is unpowered. Only removing the"
say "part says that, and on the Zero 2 W the radio is a separate component"
say "beside the processor, so removal is possible."
say ""
say "What no script can check: the activity LED can be modulated, and the"
say "power line and the panel both emit. Those need a room, not a config."
say "==================================================================="
[ "$PORCELAIN" -eq 1 ] && printf "TOTAL\t%s\t%s\n" "$PASS" "$FAIL"
exit $FAIL
