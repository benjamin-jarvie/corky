"""A file channel is a place a file really goes.

Found on the board (Ben, 2026-09-05): a watch-only wallet file sat in
/mnt/usb with no USB stick attached. `/mnt/usb` is an ordinary directory on
the boot card when nothing is mounted there, and `_file_channels` tested
for a directory, so the device offered "stick", wrote to the SD card's root
filesystem, and reported success without naming a place.

The wrong word is the small half. The same chooser carries the ENCRYPTED
KEY BACKUP, so a user who believed they had chosen a removable stick would
have left an encrypted key on the boot card. PLAN A-23 allows a key on the
card only when the user asks for the card.

The mount test only runs on the device, so this suite runs it the way
TESTING.md rule 3 asks: by setting on_device and faking the one syscall
that needs real hardware.

Run: python3 tests/test_channels.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import hal                      # noqa: E402
import main as corky_main       # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


class NullDisplay:
    width, height = 320, 240

    def show(self, image, sensitive=False):
        pass


class NullRpc:
    chain = "regtest"
    wallet_dir = Path("/nonexistent")

    def call(self, method, *a, **k):
        return ""


def session(on_device, stick=None, card=None, script="a"):
    s = corky_main.Session(NullDisplay(), hal.DevButtons(script), NullRpc(),
                           animate=False, on_device=on_device,
                           stick_dir=stick, card_dir=card)
    return s


work = Path(tempfile.mkdtemp(prefix="corky-channels-"))
stick = work / "usb"
stick.mkdir()
card = work / "card"
card.mkdir()

# --- 1. on the device, an unmounted directory is not a channel ----------

real_ismount = os.path.ismount
try:
    os.path.ismount = lambda p: False
    got = session(True, stick, card)._file_channels()
    if got:
        bad(f"an unmounted directory was offered as a channel: {got}")
    else:
        ok("on the device, a directory with nothing mounted is not a channel")

    # And the flow that uses it says so rather than writing somewhere.
    sess = session(True, stick, card)
    if sess._choose_channel() is not None:
        bad("_choose_channel returned a destination with nothing mounted")
    else:
        ok("with nothing mounted, the device says there is nowhere to write")

    # --- 2. when something IS mounted, the channel is offered ----------
    os.path.ismount = lambda p: Path(p) == stick
    got = session(True, stick, card)._file_channels()
    if got != [("stick", stick)]:
        bad(f"a mounted stick was not the only channel offered: {got}")
    else:
        ok("a mounted stick is offered, and the unmounted card is not")

    os.path.ismount = lambda p: True
    got = [n for n, _p in session(True, stick, card)._file_channels()]
    if got != ["stick", "card"]:
        bad(f"both mounted channels were not offered in order: {got}")
    else:
        ok("both channels are offered, stick first, when both are mounted")
finally:
    os.path.ismount = real_ismount

# --- 3. off the device there is nothing mounted anywhere ---------------
# The dev and test flows pass ordinary temp directories, so the mount rule
# is the device's alone. Assert that explicitly rather than leaving it to
# be discovered when every suite goes red.

got = [n for n, _p in session(False, stick, card)._file_channels()]
if got != ["stick", "card"]:
    bad(f"off the device, plain directories are not channels: {got}")
else:
    ok("off the device, a directory is a channel, as every suite assumes")

# --- 4. a channel that does not exist at all is never offered ----------

got = session(False, work / "nope", None)._file_channels()
if got:
    bad(f"a missing directory was offered as a channel: {got}")
else:
    ok("a directory that does not exist is not a channel")

import shutil  # noqa: E402
shutil.rmtree(work, ignore_errors=True)

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
