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
# the e2e-before-testers map, research/pi-zero-radio.md (archived; see
# docs/wayfinder/README.md).
#
# --porcelain prints one tab-separated record per check and nothing else:
#     ok|FAIL <tab> what it is <tab> what it is doing
# The device's own Tools screen reads that. The checks are written once and
# read two ways.

PASS=0; FAIL=0; UNKNOWN=0
PORCELAIN=0
[ "${1:-}" = "--porcelain" ] && PORCELAIN=1

# ROOT, OR NOTHING. Half of what follows reads restricted sources: dmesg
# is gated by kernel.dmesg_restrict, swapon and lsmod answer thinly, and
# every one of those returns EMPTY rather than an error. Empty reads as
# "nothing found", which reads as a pass. A leak check that quietly turns
# into a clean bill of health because it could not look is worse than no
# leak check, so it refuses instead (audit of image/, 2026-09-08).
if [ "$(id -u)" -ne 0 ]; then
    if [ "$PORCELAIN" -eq 1 ]; then
        printf "FAIL\t%s\t%s\n" "leak check" "not run as root; nothing checked"
    else
        printf "%s\n" "Run this as root: sudo bash $0"
        printf "%s\n" "Without it dmesg, lsmod and swapon answer empty, and"
        printf "%s\n" "empty would be reported as clean."
    fi
    exit 2
fi
say()  { [ "$PORCELAIN" -eq 1 ] || printf "%s\n" "$1"; }
ok()   { PASS=$((PASS+1))
         if [ "$PORCELAIN" -eq 1 ]; then printf "ok\t%s\t%s\n" "$1" "$2"
         else printf "  ok    %-22s %s\n" "$1" "$2"; fi; }
bad()  { FAIL=$((FAIL+1))
         if [ "$PORCELAIN" -eq 1 ]; then printf "FAIL\t%s\t%s\n" "$1" "$2"
         else printf "  LEAK  %-22s %s\n" "$1" "$2"; fi; }
# Neither clean nor leaking: a fact worth showing that is not a verdict,
# and a check that could not be made. Counting either as a pass inflates
# "ALL N CLEAR", which is the one line a reader takes at face value.
note() { if [ "$PORCELAIN" -eq 1 ]; then printf "note\t%s\t%s\n" "$1" "$2"
         else printf "  --    %-22s %s\n" "$1" "$2"; fi; }
huh()  { UNKNOWN=$((UNKNOWN+1))
         if [ "$PORCELAIN" -eq 1 ]; then printf "huh\t%s\t%s\n" "$1" "$2"
         else printf "  ????  %-22s %s\n" "$1" "$2"; fi; }

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

if grep -q "^dtoverlay=disable-wifi" "$CFG" 2>/dev/null; then
    ok "Wi-Fi overlay" "disabled"
else
    bad "Wi-Fi overlay" "not set"
fi
if grep -q "^dtoverlay=disable-bt" "$CFG" 2>/dev/null; then
    ok "Bluetooth overlay" "disabled"
else
    bad "Bluetooth overlay" "not set"
fi

WIFI_MODS=$(lsmod 2>/dev/null | grep -cE "^(brcmfmac|brcmutil|cfg80211)")
if [ "$WIFI_MODS" -eq 0 ]; then ok "Wi-Fi driver" "not loaded"
else bad "Wi-Fi driver" "loaded"; fi
BT_MODS=$(lsmod 2>/dev/null | grep -cE "^(bluetooth|btbcm|hci_uart|btsdio)")
if [ "$BT_MODS" -eq 0 ]; then ok "Bluetooth driver" "not loaded"
else bad "Bluetooth driver" "loaded"; fi

if [ -f /etc/modprobe.d/corky-no-radio.conf ]; then
    ok "Driver blacklist" "installed"
else bad "Driver blacklist" "missing"; fi

if [ -d /lib/firmware/brcm ]; then bad "Radio firmware" "on the card"
else ok "Radio firmware" "removed"; fi

# The kernel marks a wireless interface with a `wireless` directory, so
# ask it rather than guessing from the name. The old test listed
# /sys/class/net and called anything not matching lo, usb or eth a radio,
# which flags a bridge, a tap or a predictably-named USB ethernet
# (enx0011...) as Wi-Fi. Crying wolf is the one thing this report must
# not do (audit of image/, 2026-09-08).
WIFI_IF=""
for _n in /sys/class/net/*; do
    [ -e "$_n/wireless" ] || [ -e "$_n/phy80211" ] || continue
    WIFI_IF="$WIFI_IF$(basename "$_n") "
done
if [ -z "$WIFI_IF" ]; then
    ok "Wi-Fi interface" "none"
else
    bad "Wi-Fi interface" "$(echo "$WIFI_IF" | tr -s ' ' | sed 's/ $//')"
fi

# Bluetooth devices from sysfs, which is always there. This used to need
# hciconfig and was wrapped in `if command -v`, so on an image without
# bluez the row SILENTLY DISAPPEARED: the reader counts rows and sees no
# Bluetooth line at all, which is not the same as being told there is no
# device.
if [ -d /sys/class/bluetooth ]; then
    BT_DEV=$(find /sys/class/bluetooth -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)
    if [ "$BT_DEV" -eq 0 ]; then
        ok "Bluetooth device" "none"
    else
        bad "Bluetooth device" "$BT_DEV present"
    fi
else
    ok "Bluetooth device" "no bluetooth class at all"
fi
service_row "Wi-Fi service" wpa_supplicant
service_row "Bluetooth service" bluetooth
service_row "Network manager" NetworkManager

# An unreadable dmesg produces no output, and no output matched nothing,
# and nothing matched used to read as "silent". That is a check passing
# because it could not look. Distinguish the two.
DMESG=$(dmesg 2>/dev/null)
if [ -z "$DMESG" ]; then
    huh "Radio at boot" "dmesg unreadable; cannot say"
elif printf "%s" "$DMESG" | grep -qiE "brcmfmac|Bluetooth: hci"; then
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
# zram is the other way swap comes back. It is off only if the generator
# config exists AND pins the size to zero; otherwise, if the generator
# binary is there at all, it can make swap at the next boot. Written as
# A && B || C this was correct and unreadable, which is its own defect in
# a file people audit.
ZRAM_PINNED_OFF=no
if [ -f /etc/systemd/zram-generator.conf ] &&
   grep -qE "zram-size *= *0" /etc/systemd/zram-generator.conf; then
    ZRAM_PINNED_OFF=yes
fi
if [ "$ZRAM_PINNED_OFF" = "no" ] &&
   [ -x /usr/lib/systemd/system-generators/zram-generator ]; then
    SWAP_BACK=yes
fi
if [ "$SWAP_BACK" = "no" ]; then ok "Swap at boot" "cannot return"
else bad "Swap at boot" "comes back"; fi

if [ -d /var/log/journal ]; then bad "Journal" "written to the card"
else ok "Journal" "in RAM only"; fi

say ""
say "PORTS AND CONSOLES"

if grep -qE "console=(serial0|ttyAMA0|ttyS0)" "$CMDLINE" 2>/dev/null; then
    bad "Serial console" "on the GPIO header"
else ok "Serial console" "off"; fi
GETTY=off
for unit in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    st=$(unit_state "$unit"); [ -n "$st" ] || st=not-found
    unit_off "$st" || GETTY=on
done
if [ "$GETTY" = "off" ]; then ok "Serial login" "off"
else bad "Serial login" "enabled"; fi

if [ -n "$(ls /sys/class/udc 2>/dev/null)" ]; then
    bad "USB device mode" "active, can pretend to be a disk"
else
    ok "USB device mode" "off, host only"
fi
if [ -f /etc/modprobe.d/corky-no-gadget.conf ]; then
    ok "USB gadget blacklist" "installed"
else bad "USB gadget blacklist" "missing"; fi

ATTACHED=$(grep -l "^connected" /sys/class/drm/*/status 2>/dev/null | wc -l)
if [ "$ATTACHED" -eq 0 ]; then
    note "HDMI" "nothing attached"
else
    note "HDMI" "a screen is plugged in"
fi

service_row "Remote login" ssh

say ""
say "BITCOIN CORE"
if grep -q "^networkactive=0" /etc/corky-bitcoin.conf 2>/dev/null; then
    ok "Core networking" "off"
else bad "Core networking" "on"; fi

say ""
say "==================================================================="
if [ "$FAIL" -eq 0 ] && [ "$UNKNOWN" -eq 0 ]; then
    say "OS SILENT: all $PASS checks pass."
    say ""
    say "The operating system is not driving any way off this board."
elif [ "$FAIL" -eq 0 ]; then
    # An unanswerable check is not a pass. Saying "all clear" while a row
    # reads "cannot say" is the false assurance this whole file exists to
    # avoid (audit of image/, 2026-09-08).
    say "$UNKNOWN check(s) could not be answered. $PASS passed, none failed."
    say ""
    say "This is NOT a clean run. Find out why those rows could not be"
    say "read before trusting the rest."
else
    say "$FAIL of $((PASS+FAIL)) checks found a way off this board."
    say ""
    say "A DEV image is expected to fail the radio and login rows, because"
    say "it keeps SSH so you can work on it. Run image/harden.sh when the"
    say "device is about to hold a real key. That step is one way: it takes"
    say "SSH away."
fi
# ---- is this board what the repository says it is? ------------------
# Not a leak, and it lives here because this is the one screen a person
# opens to ask whether the device is set up right. On 2026-09-05 the USB
# stick channel had never worked on the board: provision.sh installs a
# udev rule and a mount unit for it, and this board was flashed before
# those lines existed, so a stick would never have mounted and Bitcoin
# Core, which reads no QR, had no way to be given anything.
say ""
say "-- provisioning, is the board current --"
# All FIVE units, not four. corky-splash.service was missing from this
# list, and it is the one that paints the first thing anybody sees; a
# board without it boots to a dark panel for the length of a bitcoind
# start and looks broken (audit A7, 2026-09-06).
for f in /etc/systemd/system/corky.service \
         /etc/systemd/system/corky-bitcoind.service \
         /etc/systemd/system/corky-splash.service \
         /etc/systemd/system/corky-usb@.service \
         /etc/udev/rules.d/99-corky-usb.rules; do
    if [ -f "$f" ]; then
        ok "$(basename "$f")" "installed"
    else
        bad "$(basename "$f")" "MISSING, re-run provision.sh"
    fi
done

say ""
say "None of this says the wireless chip is unpowered. Only removing the"
say "part says that, and on the Zero 2 W the radio is a separate component"
say "beside the processor, so removal is possible."
say ""
say "What no script can check: the activity LED can be modulated, and the"
say "power line and the panel both emit. Those need a room, not a config."
say "==================================================================="
[ "$PORCELAIN" -eq 1 ] && printf "TOTAL\t%s\t%s\n" "$PASS" "$((FAIL+UNKNOWN))"
# A check that could not be answered exits non-zero like a failing one.
# Callers branch on this, and "I could not look" must not read as "clean".
exit $((FAIL + UNKNOWN))
