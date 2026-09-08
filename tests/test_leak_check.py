"""The leak check is the one report a hardened board is trusted on.

A hardened Corky has no SSH, so `Tools, Check for leaks` may be the only
place anybody can ask whether the radios are off. That makes the failure
mode that matters a FALSE PASS: a check that could not look, reporting
nothing found, reading as clean.

Audited 2026-09-08 and four ways to produce one were found:

  - nothing required root, and dmesg, lsmod and swapon all answer EMPTY
    without it rather than failing;
  - the Bluetooth device row was wrapped in `if command -v hciconfig`, so
    on an image without bluez the row silently vanished;
  - an unreadable dmesg produced no output, matched nothing, and was
    reported as "silent";
  - the Wi-Fi interface row called anything not named lo, usb or eth a
    radio, so a bridge or a predictably-named USB ethernet cried wolf.

Run: python3 tests/test_leak_check.py   (no board, no bitcoind)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "image" / "leak-check.sh"
SRC = SCRIPT.read_text()

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


# 1. Unprivileged, it must refuse rather than report.
run = subprocess.run(["bash", str(SCRIPT), "--porcelain"],
                     capture_output=True, text=True, timeout=60)
if run.returncode == 0:
    bad("an unprivileged run exited 0, so a caller reads it as clean")
elif "not run as root" not in run.stdout:
    bad(f"an unprivileged run said {run.stdout[:70]!r}, which does not say "
        "why it cannot be trusted")
elif re.search(r"^ok\t", run.stdout, re.M):
    bad("an unprivileged run reported a PASSING row; it checked nothing")
else:
    ok(f"unprivileged it refuses, exits {run.returncode}, and passes nothing")

# 2. No check may be wrapped in a test for a tool being installed. A row
#    that disappears is worse than one that fails: the reader counts rows.
for m in re.finditer(r"if command -v (\w+)", SRC):
    bad(f"a check is conditional on {m.group(1)} existing, so it vanishes "
        "on an image without it instead of reporting")
if not re.search(r"^\s*if command -v", SRC, re.M):
    ok("no check disappears when a tool is missing")

# 3. An unanswerable check must not exit 0 or count as a pass.
if "UNKNOWN" not in SRC:
    bad("there is no way to report a check that could not be answered")
elif "exit $((FAIL + UNKNOWN))" not in SRC:
    bad("an unanswerable check does not affect the exit code, so a caller "
        "cannot tell it apart from a clean run")
else:
    ok("a check that cannot be answered exits non-zero, like a failing one")

# 4. Wireless interfaces come from the kernel's own marker, not from
#    guessing at names.
if re.search(r"grep -vE '\^\(lo\|usb\|eth\)'", SRC):
    bad("Wi-Fi interfaces are still detected by excluding known names, "
        "which flags bridges and USB ethernet as radios")
elif "wireless" not in SRC or "phy80211" not in SRC:
    bad("Wi-Fi detection no longer asks the kernel which interfaces are "
        "wireless")
else:
    ok("wireless interfaces come from /sys/class/net/*/wireless")

# 5. `A && ok ... || bad ...` reports a row BOTH ways if ok's printf ever
#    fails. Not one may remain in the file whose output is trusted.
both = re.findall(r"&&\s+ok\s+.*\|\|\s+bad", SRC)
if both:
    bad(f"{len(both)} row(s) still use A && ok || bad, which can report "
        "the same check as passing and failing at once")
else:
    ok("no row can be reported as both passing and failing")

# 6. Whatever it prints, the device must be able to read it. main.py
#    drops any verdict it does not recognise, silently.
main_src = (ROOT / "corky" / "main.py").read_text()
handled = set(re.findall(r'verdict in \(([^)]*)\)', main_src))
known = {v for grp in handled for v in re.findall(r'"(\w+)"', grp)}
emitted = set(re.findall(r'printf "(\w+)\\t%s\\t%s', SRC))
# TOTAL is the summary line, not a check, and main.py is right to ignore
# it: three fields, but the first is a count and not a verdict.
emitted -= {"TOTAL"}
lost = emitted - known
if lost:
    bad(f"leak-check emits verdicts main.py never renders: {sorted(lost)}. "
        "The row is dropped and the panel shows nothing.")
else:
    ok(f"every verdict it emits ({', '.join(sorted(emitted))}) reaches "
       "the panel")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
