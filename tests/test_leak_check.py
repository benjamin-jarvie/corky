"""The leak check is the one report a hardened board is trusted on.

A hardened Core Signer has no SSH, so `Tools, Check for leaks` may be the only
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
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "image" / "leak-check.sh"
SRC = SCRIPT.read_text()

fails = []


def shim(**cmds):
    """A PATH directory that answers `id -u` with 0, plus what you name.

    Three of the checks below used to read the script's source and look
    for a string. TESTING.md rule 2 asks for the round trip, and the
    reason is in this file's own history: check 3 looked for the literal
    "exit $((FAIL + UNKNOWN))" and would have passed just as happily if
    that line were inside a comment, or in a branch nothing reaches.

    The script refuses to run for a non-root caller, which is the whole
    point of check 1, so the only way to exercise the rest of it on a
    dev machine is to answer `id -u` with 0.
    """
    d = Path(tempfile.mkdtemp(prefix="coresigner-leakshim-"))
    (d / "id").write_text('#!/bin/sh\n'
                          'if [ "$1" = "-u" ]; then echo 0\n'
                          'else exec /usr/bin/id "$@"; fi\n')
    for name, body in cmds.items():
        (d / name).write_text(f"#!/bin/sh\n{body}\n")
    for f in d.iterdir():
        f.chmod(0o755)
    return d


def run_as_root(shimdir):
    """Run the real script with that shim first on PATH."""
    env = dict(os.environ, PATH=f"{shimdir}{os.pathsep}{os.environ['PATH']}")
    r = subprocess.run(["bash", str(SCRIPT), "--porcelain"],
                       capture_output=True, text=True, timeout=120, env=env)
    rows = [ln.split("\t") for ln in r.stdout.splitlines() if "\t" in ln]
    return r.returncode, [row for row in rows if row[0] != "TOTAL"]


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
#    Both halves ask ONE pattern. They used to ask two that differed by
#    a `^\s*` anchor, so a mid-line `; if command -v foo` was reported as
#    a failure and as a pass in the same run (two-axis review,
#    2026-09-08).
conditional = re.findall(r"if\s+command -v (\w+)", SRC)
for tool in conditional:
    bad(f"a check is conditional on {tool} existing, so it vanishes "
        "on an image without it instead of reporting")
if not conditional:
    ok("no check disappears when a tool is missing")

# 3. An unanswerable check must not exit 0 or count as a pass.
#    Run the script twice against the same machine, changing one thing:
#    whether dmesg answers. Everything else stays constant, so the
#    difference between the two exit codes is what one UNKNOWN row is
#    worth. Reading the source for the literal "exit $((FAIL + UNKNOWN))"
#    proved only that the string was present somewhere.
blind_rc, blind = run_as_root(shim(dmesg="exit 0"))
seen_rc, seen = run_as_root(shim(dmesg='echo "[    0.000000] Linux version"'))
huhs = [r for r in blind if r[0] == "huh"]
if not huhs:
    bad("an unreadable dmesg produced no 'huh' row, so a check that could "
        "not look reported something else")
elif [r for r in seen if r[0] == "huh"]:
    bad("a readable dmesg still produced a 'huh' row, so the shim proves "
        "nothing about which input caused it")
elif blind_rc - seen_rc != len(huhs):
    bad(f"one unanswerable check moved the exit code by "
        f"{blind_rc - seen_rc}, not {len(huhs)}: a caller cannot tell "
        f"'I could not look' from 'clean'")
else:
    ok(f"one check that could not be answered raised the exit code "
       f"{seen_rc} -> {blind_rc}, so it never reads as clean")

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
#    The first version of this check read `&& ok ... || bad` on ONE line,
#    which missed the reverse order and every row split over several
#    lines. leak-check.sh writes most of its rows across three or four
#    (two-axis review, 2026-09-08). Flatten the continuations first, then
#    look for any reporter on both sides.
flat = re.sub(r"\\\n\s*", " ", SRC)              # backslash continuation
flat = re.sub(r"\n\s*(&&|\|\|)", r" \1", flat)     # leading && or ||
REPORTER = r"(?:ok|bad|huh|note)"
both = re.findall(rf"&&\s+{REPORTER}\s[^\n]*?\|\|\s+{REPORTER}\b", flat)
if both:
    bad(f"{len(both)} row(s) still use A && x || y, which can report "
        f"the same check two ways: {both[0][:60]!r}")
else:
    ok("no row can be reported as both passing and failing")

# 6. Whatever it prints, the device must be able to read it. main.py
#    drops any verdict it does not recognise, silently.
#    Drive the real screen, with the real script behind it. The earlier
#    version compared a regex over leak-check.sh against a regex over
#    main.py: two readings of two files, agreeing with each other while
#    neither had run. A verdict can also be lost AFTER the parser, and
#    reading `verdict in (...)` could never see that.
sys.path.insert(0, str(ROOT / "coresigner"))
import hal                          # noqa: E402
import main as coresigner_main           # noqa: E402
import screens                      # noqa: E402


class NullDisplay:
    width, height = 320, 240

    def show(self, image, sensitive=False):
        pass


class NullRpc:
    chain = "regtest"
    wallet_dir = Path("/nonexistent")

    def call(self, method, *a, **k):
        return ""


# dmesg silent, so the run carries a `huh` row as well as ok, FAIL and
# note. A round trip that only ever sees two of the four verdicts would
# not notice the other two being dropped.
d = shim(dmesg="exit 0")
rc, emitted_rows = run_as_root(d)
painted = []
real_report = screens.leak_report
screens.leak_report = lambda w, h, rows, cursor: (painted.append(rows),
                                                  real_report(w, h, rows,
                                                              cursor))[1]
os.environ["PATH"] = f"{d}{os.pathsep}{os.environ['PATH']}"
try:
    coresigner_main.Session(NullDisplay(), hal.DevButtons("a"), NullRpc(),
                       animate=False)._tool_leak_check()
finally:
    screens.leak_report = real_report

emitted = {r[0] for r in emitted_rows}
if not painted:
    bad("the leak report screen was never painted, so nothing the script "
        "said reached the panel")
else:
    on_panel = {(lbl, state) for lbl, state, _ in painted[0]}
    lost = [r for r in emitted_rows if (r[1], r[2]) not in on_panel]
    if lost:
        bad(f"{len(lost)} row(s) the script printed never reached the "
            f"panel, first: {lost[0]}")
    elif len(emitted) < 4:
        bad(f"the run only produced {sorted(emitted)}, so this check did "
            "not exercise every verdict the script can emit")
    else:
        ok(f"all {len(emitted_rows)} rows reach the panel, across "
           f"{', '.join(sorted(emitted))}")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
