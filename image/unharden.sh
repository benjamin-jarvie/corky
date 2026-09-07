#!/bin/bash
# Undo image/harden.sh. The way back in when something goes wrong.
#
#   sudo bash /opt/corky/image/unharden.sh && sudo reboot
#
# harden.sh is one way BY DESIGN and this does not change that: you still
# need root on the board to run it, and the only ways to get root on a
# hardened board are the HDMI console, a rescue shell, or the card in your
# hand. All three mean physical possession, which the threat model already
# treats as game over. What this removes is not a barrier, it is the need
# to remember nine masked units and a moved firmware directory at the
# moment you are least able to.
#
# HOW TO GET ROOT ON A HARDENED BOARD, easiest first:
#
#   1. HDMI console. harden.sh does not touch getty@tty1, and the corky
#      user has a password, so a mini-HDMI adapter, a screen and a USB
#      keyboard get you a login. Verified on the board 2026-09-06.
#   2. Rescue shell. Put the card in any computer, open the FAT boot
#      partition, and append ` init=/bin/sh` to the single line in
#      cmdline.txt. It boots to a root shell with no login. Then:
#        mount -o remount,rw / && bash /opt/corky/image/unharden.sh
#      Take the init= back out afterwards.
#   3. A Linux machine. Mount the ext4 root partition and run this with
#      ROOT=/path/to/that/mount.
#   4. Reflash. Nothing is lost: the device keeps no state, keys live in
#      a tmpfs and die at power off. You lose the evidence of whatever
#      went wrong, which is usually the thing you wanted.
#
# BEFORE YOU HARDEN, take an image of the card. Restoring it is ten
# minutes and it keeps the broken card intact to look at.
set -u
ROOT=${ROOT:-}
CFG0="$ROOT/boot/firmware/config.txt"
[ -f "$CFG0" ] || CFG0="$ROOT/boot/config.txt"
CMDLINE="$ROOT/boot/firmware/cmdline.txt"
[ -f "$CMDLINE" ] || CMDLINE="$ROOT/boot/cmdline.txt"
say() { printf '%-6s %s\n' "$1" "$2"; }

# grep and a temp file, never `sed -i`. BSD sed takes the backup suffix
# as its next argument and GNU sed does not, so one `sed -i` cannot serve
# both, and config.txt is on the FAT partition a Mac CAN open. The first
# version used sed -i and silently changed nothing on macOS;
# tests/test_harden_reversible.py caught it on the first run.
drop_line() {
    grep -v "^$1\$" "$CFG0" > "$CFG0.corky-tmp" 2>/dev/null || true
    cat "$CFG0.corky-tmp" > "$CFG0"
    rm -f "$CFG0.corky-tmp"
}

echo "== 1/4 firmware overlays"
for ov in disable-wifi disable-bt; do
    if grep -q "^dtoverlay=$ov" "$CFG0" 2>/dev/null; then
        drop_line "dtoverlay=$ov"; say ok "removed dtoverlay=$ov"
    else
        say note "dtoverlay=$ov was not set"
    fi
done
if grep -q "^enable_uart=0" "$CFG0" 2>/dev/null; then
    drop_line "enable_uart=0"; say ok "removed enable_uart=0"
fi

echo "== 2/4 drivers may load again"
if [ -f "$ROOT/etc/modprobe.d/corky-no-radio.conf" ]; then
    rm -f "$ROOT/etc/modprobe.d/corky-no-radio.conf"
    say ok "removed the driver blacklist"
else
    say note "no driver blacklist to remove"
fi

echo "== 3/4 firmware for the chip"
if [ -d "$ROOT/lib/firmware/brcm.corky-disabled" ]; then
    if [ -d "$ROOT/lib/firmware/brcm" ]; then
        say note "both brcm and brcm.corky-disabled exist; leaving both"
    else
        mv "$ROOT/lib/firmware/brcm.corky-disabled" "$ROOT/lib/firmware/brcm"
        say ok "put the radio firmware back"
    fi
else
    say note "radio firmware was never moved"
fi

echo "== 4/4 services"
# The same list harden.sh masks. tests/test_harden_reversible.py fails if
# the two ever disagree, because a unit this forgets is a way in that
# stays shut with no message saying so.
for unit in wpa_supplicant bluetooth hciuart dhcpcd NetworkManager \
            systemd-networkd avahi-daemon triggerhappy ssh sshd \
            serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    if [ -n "$ROOT" ]; then
        # Offline: a mask is a symlink to /dev/null. Delete it by hand,
        # because systemctl cannot talk to a system that is not running.
        for d in "$ROOT/etc/systemd/system"; do
            for f in "$d/$unit" "$d/$unit.service"; do
                [ -L "$f" ] && [ "$(readlink "$f")" = "/dev/null" ] \
                    && rm -f "$f" && say ok "unmasked $unit"
            done
        done
    else
        systemctl unmask "$unit" >/dev/null 2>&1 && say ok "unmasked $unit"
    fi
done
if [ -z "$ROOT" ]; then
    systemctl enable ssh >/dev/null 2>&1 && say ok "ssh will start at boot"
fi

echo
echo "Now REBOOT. Then check what came back with:"
echo "  sudo bash /opt/corky/image/leak-check.sh"
echo "Expect the radio and remote-login rows to FAIL again. That is the"
echo "point: this board is a dev board again and must not hold a real key."
