"""Boot splash: paint the brand frame, say what the card is, then exit.

The dedicated entrypoint imports only hal and screens. The signing stack
(signer, the channels) stays out on purpose: the frame lands
seconds earlier on the single-core Pi, and a fault in a signing-side
module cannot dark the boot screen. coresigner-splash.service runs this
before coresigner-bitcoind.service; the session itself is coresigner/main.py.

WHAT THE CARD IS, read off the running system rather than off a marker
some script left behind. A marker says what was intended; a listening
socket says what is true. docs/TESTER-PACK.md warns that an unhardened
card has SSH and both radios live, and until 2026-09-23 the only way to
find that out was to remember to run a script.
"""

import argparse
import time
from pathlib import Path

import hal
import screens

#: How long a development card holds its warning. Coinkite's reason, for
#: a device with a bootloader that can enforce one: "Development
#: firmware gets a warning and forced delay on every boot. It cannot
#: quietly pass as factory firmware." Long enough to read, short enough
#: that nobody disables it.
DEV_HOLD_SECONDS = 4.0

#: Where provision.sh records what the card was built from. Written by
#: the OS at install time, because hashing is a thing this package does
#: not do (PLAN A-22, tests/test_integrity.py).
BUILD_FILE = Path(__file__).resolve().parent.parent / "BUILD"


def listening(port, root=Path("/")):
    """True when something is listening on `port`, from /proc alone.

    State 0A is TCP_LISTEN, and the local address ends in the port as
    four hex digits. Read rather than asked, so this needs no subprocess
    and no systemd on the single-core boot path.
    """
    want = f":{port:04X}"
    for name in ("net/tcp", "net/tcp6"):
        try:
            rows = (root / "proc" / name).read_text().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            cols = row.split()
            if len(cols) > 3 and cols[3] == "0A" and cols[1].endswith(want):
                return True
    return False


def dev_reasons(root=Path("/")):
    """Why this is a development card, in as few words as the panel has.

    LIVE STATE, not what harden.sh wrote. A card hardened but not yet
    rebooted still has its radio up, and that is the card in the room.
    """
    why = []
    if any((root / "sys/class/net" / n).exists()
           for n in ("wlan0", "wlan1")):
        why.append("radio up")
    if listening(22, root):
        why.append("SSH live")
    return why


def build_id():
    """What provision.sh recorded, or None on a card it never ran on."""
    try:
        return BUILD_FILE.read_text().strip()[:32] or None
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--frames-dir", default="frames")
    ap.add_argument("--root", default="/",
                    help="filesystem root the card's state is read from")
    args = ap.parse_args()
    display = (hal.DevDisplay(args.frames_dir) if args.dev
               else hal.DeviceDisplay())
    why = dev_reasons(Path(args.root))
    display.show(screens.splash(display.width, display.height,
                                build=build_id(), dev=tuple(why)))
    if why and not args.dev:
        # The forced delay. Nothing stops a person editing this file,
        # so this buys no security. What it buys is a card that says
        # what it is, instead of one a tester has to interrogate.
        time.sleep(DEV_HOLD_SECONDS)


if __name__ == "__main__":
    main()
