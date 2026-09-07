"""harden.sh closes the ways in; unharden.sh must open every one again.

Two shell scripts, and nothing joins them. That is TESTING.md rule 11 in
another costume: the list of units lives in both files and they drift the
moment somebody adds one to the first. A unit harden masks and unharden
forgets is a door that stays shut with no message saying so, on a board
whose only other way in is a screen and a keyboard.

This reads both scripts and asserts the second reverses the first. It
also runs unharden against a FAKE ROOT, so the reversal is executed and
not merely read.

Run: python3 tests/test_harden_reversible.py   (no board, no bitcoind)
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARDEN = (ROOT / "image" / "harden.sh").read_text()
UNHARDEN = (ROOT / "image" / "unharden.sh").read_text()

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


def units(text):
    """Every unit named in a `for unit in ... ; do` list."""
    found = set()
    for block in re.findall(r"for unit in (.*?);\s*do", text, re.S):
        found |= set(block.replace("\\\n", " ").split())
    return found


# 1. Every unit harden.sh masks, unharden.sh unmasks.
h, u = units(HARDEN), units(UNHARDEN)
if not h:
    bad("harden.sh names no units at all; this check reads nothing")
missing = sorted(h - u)
if missing:
    bad(f"harden.sh shuts these and unharden.sh never reopens them: "
        f"{missing}")
else:
    ok(f"all {len(h)} units harden.sh masks are unmasked again")

# 2. Every config.txt line harden.sh adds, unharden.sh removes.
added = set(re.findall(r'echo "(dtoverlay=[a-z-]+)"', HARDEN))
added |= set(re.findall(r'echo "(enable_uart=0)"', HARDEN))
for line in sorted(added):
    key = line.split("=")[-1]
    if key not in UNHARDEN:
        bad(f"harden.sh adds {line} to config.txt and unharden.sh "
            "never takes it out")
    else:
        ok(f"{line} is removed again")

# 3. The moved firmware comes back.
if "brcm.corky-disabled" in HARDEN and "brcm.corky-disabled" not in UNHARDEN:
    bad("harden.sh moves the radio firmware and unharden.sh leaves it moved")
else:
    ok("the radio firmware is put back")

# 4. harden.sh must NOT take the local console away, because that is the
#    way back in. If this ever changes, the recovery path in
#    unharden.sh's header stops being true and has to be rewritten.
if re.search(r"getty@tty1|getty@tty\b", HARDEN):
    bad("harden.sh now touches the HDMI console, which is the documented "
        "way back into a hardened board. unharden.sh's header says it is "
        "untouched; one of the two is now wrong.")
else:
    ok("harden.sh leaves the HDMI console alone, which is the way back in")

# 5. Run it. A fake root with everything harden.sh leaves behind.
fake = Path(tempfile.mkdtemp())
(fake / "boot" / "firmware").mkdir(parents=True)
(fake / "etc" / "modprobe.d").mkdir(parents=True)
(fake / "etc" / "systemd" / "system").mkdir(parents=True)
(fake / "lib" / "firmware" / "brcm.corky-disabled").mkdir(parents=True)
(fake / "boot" / "firmware" / "config.txt").write_text(
    "gpu_mem=32\ndtoverlay=disable-wifi\ndtoverlay=disable-bt\n"
    "enable_uart=0\n")
(fake / "boot" / "firmware" / "cmdline.txt").write_text("root=/dev/mmcblk0p2\n")
(fake / "etc" / "modprobe.d" / "corky-no-radio.conf").write_text("blacklist x\n")
for unit in sorted(h):
    name = unit if unit.endswith(".service") else unit + ".service"
    os.symlink("/dev/null", fake / "etc" / "systemd" / "system" / name)

run = subprocess.run(["bash", str(ROOT / "image" / "unharden.sh")],
                     capture_output=True, text=True,
                     env={**os.environ, "ROOT": str(fake)}, timeout=60)
if run.returncode != 0:
    bad(f"unharden.sh exited {run.returncode}: {run.stderr[-200:]}")

cfg = (fake / "boot" / "firmware" / "config.txt").read_text()
if "disable-wifi" in cfg or "disable-bt" in cfg or "enable_uart=0" in cfg:
    bad(f"config.txt still carries the overlays after unharden:\n{cfg}")
else:
    ok("run against a fake root: the overlays are gone from config.txt")
if "gpu_mem=32" not in cfg:
    bad("unharden.sh deleted a config.txt line that was not its business")
else:
    ok("and it left the lines that were not its business alone")
if (fake / "etc" / "modprobe.d" / "corky-no-radio.conf").exists():
    bad("the driver blacklist survived unharden.sh")
else:
    ok("the driver blacklist is gone")
if not (fake / "lib" / "firmware" / "brcm").is_dir():
    bad("the radio firmware was not put back")
else:
    ok("the radio firmware is back at lib/firmware/brcm")
left = sorted(p.name for p in (fake / "etc" / "systemd" / "system").iterdir()
              if p.is_symlink() and os.readlink(p) == "/dev/null")
if left:
    bad(f"still masked after unharden.sh: {left}")
else:
    ok(f"all {len(h)} masks are gone")

import shutil                                        # noqa: E402
shutil.rmtree(fake, ignore_errors=True)
print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
