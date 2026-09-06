#!/bin/bash
# What is actually on this device, against what the repository says.
#
# Audit A7 exists because the repo and the board can diverge silently and
# nothing compared them. On 2026-09-05 the board had never had the USB
# mount rule installed, and every suite stayed green while the file
# channel could not work at all. On 2026-09-06 this script found two more
# on the same board: corky.service had no --card-dir, so the card channel
# did not exist, and bitcoin.conf still carried debuglogfile=0, which
# Core reads as a FILENAME and which had written 5,736 bytes of log to a
# file called `0` in the ramdisk.
#
# Run it on the device:  sudo bash /opt/corky/image/verify-install.sh
#
# It reads only. It changes nothing. A tester can run it and check this
# device against the repository they can read on GitHub, without taking
# anybody's word for what was flashed.
set -u
REPO=${REPO:-/opt/corky}
FAILED=0
say() { printf '%-6s %s\n' "$1" "$2"; }
bad() { say FAIL "$1"; FAILED=1; }

echo "== files installed from the repository"
# repo path : installed path
PAIRS="
image/corky.service:/etc/systemd/system/corky.service
image/corky-bitcoind.service:/etc/systemd/system/corky-bitcoind.service
image/corky-splash.service:/etc/systemd/system/corky-splash.service
image/corky-usb@.service:/etc/systemd/system/corky-usb@.service
image/99-corky-usb.rules:/etc/udev/rules.d/99-corky-usb.rules
m0/bitcoin.conf:/etc/corky-bitcoin.conf
"
for pair in $PAIRS; do
    src="$REPO/${pair%%:*}"; dst="${pair##*:}"
    if [ ! -f "$src" ]; then bad "$src is not in the repository"; continue; fi
    if [ ! -f "$dst" ]; then bad "$dst is NOT INSTALLED"; continue; fi
    a=$(sha256sum "$src" | cut -d' ' -f1)
    b=$(sha256sum "$dst" | cut -d' ' -f1)
    if [ "$a" = "$b" ]; then say ok "$dst"
    else bad "$dst DIFFERS from $src"; diff "$src" "$dst" | sed 's/^/       /'
    fi
done

echo
echo "== Bitcoin Core"
# The REPOSITORY's pins, not PINS.installed. The whole point is to compare
# the device against something a tester can read for themselves on GitHub,
# and PINS.installed is a copy of whatever this device was built from, so
# checking against it would be asking the suspect for an alibi. Found by
# running this script on the board: the device's own copy predated the
# binary pins and reported "no hash pinned" for both (A7, 2026-09-06).
# shellcheck disable=SC1091
. "$REPO/image/PINS"
for b in bitcoind:"${CORE_BIN_SHA256:-}" bitcoin-cli:"${CLI_BIN_SHA256:-}"; do
    name="${b%%:*}"; want="${b##*:}"
    path=$(command -v "$name" 2>/dev/null)
    if [ -z "$path" ]; then bad "$name is not installed"; continue; fi
    if [ -z "$want" ] || [ "$want" = "UNPINNED_UNTIL_FIRST_FLASH" ]; then
        bad "$name at $path: no hash pinned to check it against"; continue
    fi
    got=$(sha256sum "$path" | cut -d' ' -f1)
    if [ "$got" = "$want" ]; then say ok "$name matches the pinned binary"
    else bad "$name at $path is NOT the pinned binary
       want $want
       got  $got"
    fi
done
bitcoind --version 2>/dev/null | head -1 | sed 's/^/       /'

echo
echo "== the channels, as the device sees them"
for d in /mnt/usb /boot/firmware; do
    if [ ! -d "$d" ]; then say note "$d does not exist"
    elif mountpoint -q "$d"; then say ok "$d is mounted, so it is offered"
    else say note "$d is not a mountpoint, so it is correctly NOT offered"
    fi
done

echo
echo "== the ramdisk holds no log"
DATADIR=/run/corky
if [ -d "$DATADIR" ]; then
    # `0` is the file debuglogfile=0 produces. Anything ending .log too.
    strays=$(find "$DATADIR" -maxdepth 1 \( -name 0 -o -name '*.log' \) 2>/dev/null)
    if [ -n "$strays" ]; then
        bad "Core is writing a log into the ramdisk:"
        # shellcheck disable=SC2086
        ls -la $strays | sed 's/^/       /'
        echo "       Core's own first log line warns it may hold private data."
        echo "       The fix is nodebuglogfile=1 in /etc/corky-bitcoin.conf."
    else
        say ok "no log file in $DATADIR"
    fi
else
    say note "$DATADIR does not exist; the node is not running"
fi

echo
if [ "$FAILED" -eq 0 ]; then
    echo "PASS  this device matches the repository at $REPO"
else
    echo "FAIL  this device does NOT match the repository at $REPO"
fi
exit $FAILED
