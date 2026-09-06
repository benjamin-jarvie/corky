"""The boot splash, which had no test at all.

`corky/splash.py` is 27 lines and it is the FIRST thing the device runs:
`corky-splash.service` paints it before `corky-bitcoind.service` starts, so
the panel says something within seconds rather than staying dark through a
node launch. Nothing tested it, and it was in neither suite (audit A1,
2026-09-06).

What it must do is narrow, which is why it can be tested cheaply: import
almost nothing, paint one frame, and exit. The narrowness IS the design.
Its own docstring says the signing stack stays out on purpose so "a fault
in a signing-side module cannot dark the boot screen", and that claim is
worth a check, because it is the kind of claim that quietly stops being
true when somebody adds an import.

Run: python3 tests/test_splash.py (no bitcoind, no hardware)
"""
import ast
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLASH = ROOT / "corky" / "splash.py"

fails = []


def _child_env():
    """The environment the service gives it, plus the coverage hook.

    The env is built from scratch on purpose: the point of check 1 is that
    splash.py needs almost nothing, and inheriting a developer's shell
    would hide a missing dependency. But a scratch env also drops
    COVERAGE_PROCESS_START, so tools/coverage_run.sh reported this whole
    program as never executed while this very test was running it (audit
    A5, 2026-09-06). Pass the two coverage variables through when they are
    set, and nothing else.
    """
    import os
    env = {"PYTHONPATH": str(ROOT / "corky"), "PATH": "/usr/bin:/bin",
           "PYTHONDONTWRITEBYTECODE": "1"}
    hook = os.environ.get("COVERAGE_PROCESS_START")
    if hook:
        env["COVERAGE_PROCESS_START"] = hook
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    return env


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


# --- 1. it imports nothing from the signing side -----------------------
# The claim in its docstring, checked. hal and screens are the panel; the
# signer and the channels are what must stay out.

BANNED = {"signer", "filechannel", "qrchannel", "main"}
tree = ast.parse(SPLASH.read_text())
imported = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imported.add(node.module.split(".")[0])
reached = imported & BANNED
if reached:
    bad(f"splash imports the signing side: {sorted(reached)}. A fault "
        "there would now dark the boot screen, which is the thing its "
        "docstring says it avoids.")
else:
    ok(f"splash imports none of {sorted(BANNED)}, so a fault in the "
       "signing stack cannot dark the boot screen")


# --- 2. it paints one frame and exits ----------------------------------
# Run it the way the service does, in dev mode, and look at what landed.
# This is the whole program, end to end, which is cheap enough to do.

with tempfile.TemporaryDirectory() as tmp:
    out = subprocess.run(
        [sys.executable, str(SPLASH), "--dev", "--frames-dir", tmp],
        capture_output=True, text=True, timeout=60,
        env=_child_env())
    frames = sorted(Path(tmp).glob("frame-*.png"))
    if out.returncode != 0:
        bad(f"splash exited {out.returncode}: {out.stderr.strip()[:200]}")
    elif len(frames) != 1:
        bad(f"splash painted {len(frames)} frames, expected exactly one")
    else:
        ok(f"splash paints exactly one frame and exits 0 "
           f"({frames[0].stat().st_size} bytes)")

    # And the frame is the branded one, not an empty panel.
    if frames:
        sys.path.insert(0, str(ROOT / "corky"))
        import screens                          # noqa: E402
        from PIL import Image                   # noqa: E402
        want = screens.splash(320, 240)
        got = Image.open(frames[0])
        if got.size != want.size:
            bad(f"splash frame is {got.size}, the panel is {want.size}")
        elif got.convert("RGB").tobytes() != want.tobytes():
            bad("splash painted something other than screens.splash()")
        else:
            ok("the frame is screens.splash(), pixel for pixel")


print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
