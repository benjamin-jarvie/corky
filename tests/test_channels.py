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
import re
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

# --- 5. the mount unit is what makes filechannel safe -------------------
# filechannel.find_unsigned trusts a filename off a stick and calls
# is_file(), which follows symlinks. That is only safe while removable
# media is mounted as a filesystem with no symlinks. The two files never
# mentioned each other until the A1 audit; this is the check that keeps
# them in step.

UNIT = ROOT / "image" / "corky-usb@.service"
SYMLINKLESS = {"vfat", "exfat", "msdos"}

unit = UNIT.read_text()
# EVERY ExecStart, not just the first: a second, unqualified mount line
# would have slipped past a check that read one (devil's advocate,
# 2026-09-06).
mounts = [ln for ln in unit.splitlines()
          if ln.startswith("ExecStart=") and "/bin/mount" in ln]
if len(mounts) != 1:
    bad(f"{UNIT.name}: expected exactly one mount command, found "
        f"{len(mounts)}. Each one needs its own -t restriction.")
mount_line = mounts[0] if mounts else ""
m = re.search(r"-t\s+([a-z0-9,]+)", mount_line)
if not m:
    bad(f"{UNIT.name}: no -t filesystem restriction on the mount at all, "
        "so filechannel is trusting names on a filesystem that may have "
        "symlinks")
else:
    kinds = set(m.group(1).split(","))
    extra = kinds - SYMLINKLESS
    if extra:
        bad(f"{UNIT.name} now mounts {sorted(extra)}, which can carry "
            "symlinks. filechannel.find_unsigned calls is_file() on names "
            "off the stick and must stop trusting them.")
    else:
        ok(f"removable media is mounted {sorted(kinds)} only, none of which "
           "has symlinks, which is what makes find_unsigned safe")

# And the flags have to be OPTIONS, not merely characters somewhere on
# the line: "nodev" appears inside "nodevice" and a substring test would
# have accepted that.
opts = re.search(r"-o\s+([a-z0-9=,]+)", mount_line)
given = set(opts.group(1).split(",")) if opts else set()
for flag in ("noexec", "nosuid", "nodev"):
    if flag in given:
        ok(f"the mount still passes {flag} as an option")
    else:
        bad(f"the mount no longer passes {flag} as an option: got "
            f"{sorted(given) or 'no -o at all'}")


# --- 6. BACK does not grow the stack ------------------------------------
# state_load offers a channel; the channel loader used to return
# self.state_load() when B was pressed, which is mutual recursion. The
# stack grew one frame per press and RecursionError arrived at about 500,
# measured 2026-09-07. It takes the UI down, and the restart that follows
# clears the loaded key, so a fidgeting thumb could end a session.
#
# 4,000 presses here: well past where the old code died, fast because
# nothing is drawn.
import traceback                                       # noqa: E402

stick6 = tempfile.mkdtemp()
sess6 = corky_main.Session(NullDisplay(), hal.DevButtons("b" * 4000),
                           rpc=NullRpc(), animate=False, on_device=False,
                           stick_dir=stick6)
sess6.qr = type("NoCamera", (), {
    "available": False,
    "strings": lambda self: iter(()),
    "scan_psbt_frames": lambda self: iter(()),
})()
deepest = [0]
real_stick = corky_main.Session._load_by_stick


def _watch_depth(self):
    deepest[0] = max(deepest[0], len(traceback.extract_stack()))
    return real_stick(self)


corky_main.Session._load_by_stick = _watch_depth
try:
    sess6.state_load()
    ok(f"4,000 back presses do not grow the stack (peak depth "
       f"{deepest[0]})")
except RecursionError:
    bad(f"back is still recursive: RecursionError at depth {deepest[0]}")
except hal.ScriptExhausted:
    bad("the loader stopped reading presses, so this proves nothing")
finally:
    corky_main.Session._load_by_stick = real_stick
    shutil.rmtree(stick6, ignore_errors=True)

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
