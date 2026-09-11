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
sys.path.insert(0, str(ROOT / "coresigner"))
import hal                      # noqa: E402
import main as coresigner_main       # noqa: E402

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
    s = coresigner_main.Session(NullDisplay(), hal.DevButtons(script), NullRpc(),
                           animate=False, on_device=on_device,
                           stick_dir=stick, card_dir=card)
    return s


work = Path(tempfile.mkdtemp(prefix="coresigner-channels-"))
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

UNIT = ROOT / "image" / "coresigner-usb@.service"
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
# BOTH channels must exist, or state_load takes its single-channel
# branch, the first BACK returns TO_HOME, and the loop under test never
# runs at all. The first version of this check did exactly that: it
# consumed ONE of its four thousand presses, never entered _load_by_qr,
# and reported a "peak depth" measured over a single call. Two
# independent reviewers caught it on 2026-09-08; the fix it was written
# to protect was never exercised by it.
# "a" picks a channel at the menu, the loader then reads one press and
# backs out, and the menu comes round again: two presses per round trip.
# The menu opens on row 0, which is the QR channel, and the row is
# remembered, so a single "d" half way through moves every later round to
# the stick. Without it _load_by_stick is never entered at all and its
# recursion mutation survives (2026-09-08).
sess6 = coresigner_main.Session(NullDisplay(),
                           hal.DevButtons("ab" * 1000 + "d" + "ab" * 1000),
                           rpc=NullRpc(), animate=False, on_device=False,
                           stick_dir=stick6)
sess6.qr = type("Camera", (), {
    "available": True,           # so the CHANNEL MENU appears and loops
    "strings": lambda self: iter(()),
    "scan_psbt_frames": lambda self: iter(()),
})()
# Every depth seen, not the maximum. A threshold is the wrong assertion
# here: restoring the recursion in _load_by_stick makes the inner
# state_load reset the channel row, so the stick is entered ONCE and the
# stack grows by three frames, which no sensible threshold catches. What
# a loop guarantees and recursion cannot is that the depth never changes
# at all (2026-09-08).
depths = []
entered = {"stick": 0, "qr": 0}
real_stick = coresigner_main.Session._load_by_stick
real_qr = coresigner_main.Session._load_by_qr


def _watch(name, real):
    """Observe the REAL loader. Do not stand in for it.

    A first version returned BACK_TO_CHANNELS itself instead of calling
    through, so the recursion under test was replaced by the test and
    both mutations survived. Wrapping and delegating is the difference
    between measuring the code and measuring the mock (2026-09-08).

    Both real loaders return on the first "b" without sleeping, and an
    empty stick directory means neither finds anything, so each round
    trip costs exactly one press and no wall-clock.
    """
    def spy(self):
        entered[name] += 1
        depths.append(len(traceback.extract_stack()))
        return real(self)
    return spy


coresigner_main.Session._load_by_stick = _watch("stick", real_stick)
coresigner_main.Session._load_by_qr = _watch("qr", real_qr)
try:
    sess6.state_load()
    bad("state_load returned instead of looping until the presses ran out")
except RecursionError:
    bad(f"back is still recursive: RecursionError at depth "
        f"{max(depths) if depths else 0}")
except hal.ScriptExhausted:
    rounds = entered["stick"] + entered["qr"]
    if not (entered["qr"] and entered["stick"]):
        bad(f"only one channel was exercised: {entered}. A recursion left "
            "in the other loader would go unnoticed.")
    elif rounds < 100:
        bad(f"the loop ran only {rounds} times, so the presses were not "
            "spent on it and the depth below means little")
    elif len(set(depths)) != 1:
        bad(f"the stack depth changed across {rounds} back-outs: "
            f"{sorted(set(depths))[:6]}. A loop returns to the same frame "
            "every time; recursion does not.")
    else:
        ok(f"{rounds} back-outs across both channels "
           f"(qr {entered['qr']}, stick {entered['stick']}), every one at "
           f"the same stack depth of {depths[0]}")
finally:
    coresigner_main.Session._load_by_stick = real_stick
    coresigner_main.Session._load_by_qr = real_qr
    shutil.rmtree(stick6, ignore_errors=True)

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
