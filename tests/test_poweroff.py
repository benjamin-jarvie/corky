"""POWER OFF must actually power the device off (issue I-2).

Before this suite existed, choosing POWER OFF returned from Python and
nothing else: bitcoind kept running under its own systemd unit, /run/corky
stayed mounted, and the ST7789 held the signed-result screen, so the
operator read POWER OFF on a live device.

The halt commands are the only part that needs real hardware, so they are
the only part faked. Sessions here set animate AND on_device, because
main() sets both from `not args.dev`, so the threaded busy frame is the one
under test (TESTING.md rule 3).

Run: python3 tests/test_poweroff.py
"""
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))
import signer                       # noqa: E402
import main as corky_main           # noqa: E402
import hal                          # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


class FakeRpc:
    """Answers RPC until 'stop', then refuses, like a node shutting down."""

    chain = "regtest"
    wallet_dir = Path("/nonexistent")

    def __init__(self, replies_after_stop=2):
        self.calls = []
        self.left = replies_after_stop
        self.stopped = False

    def call(self, method, *params, **kw):
        self.calls.append(method)
        if method == "stop":
            self.stopped = True
            return "Bitcoin Core stopping"
        if self.stopped:
            if self.left > 0:
                self.left -= 1
                return 12          # still answering: uptime in seconds
            raise RuntimeError(f"{method}: connection refused")
        return ""


class RecordingDisplay:
    width, height = 320, 240

    def __init__(self, events):
        self.events = events
        self.shown = []
        self.lock = threading.Lock()

    def show(self, image, sensitive=False):
        with self.lock:
            self.shown.append(image)
            self.events.append("show")


MISSING = "missing"      # systemctl is not installed: FileNotFoundError
FAILS = "fails"          # systemctl runs and exits non-zero
WORKS = "works"


def run_power_off(on_device, rpc=None, systemctl=WORKS, halt=WORKS):
    """Run the real power_off body with only the halt commands faked."""
    events = []
    rpc = rpc or FakeRpc()
    display = RecordingDisplay(events)
    session = corky_main.Session(display, hal.DevButtons("a"), rpc,
                                 animate=on_device, on_device=on_device)
    real_run = corky_main.subprocess.run

    def fake_run(cmd, **kw):
        cmd = list(cmd)
        events.append(("run", cmd))
        mode = systemctl if cmd == corky_main.HALT_CMD else halt
        if mode == MISSING:
            raise FileNotFoundError(2, "No such file or directory", cmd[0])

        class R:
            returncode = 0 if mode == WORKS else 1
        return R()

    real_call = rpc.call

    def traced(method, *params, **kw):
        events.append(("rpc", method))
        return real_call(method, *params, **kw)

    rpc.call = traced
    corky_main.subprocess.run = fake_run
    try:
        session.power_off()
    finally:
        corky_main.subprocess.run = real_run
    return events, display, rpc


# --- 1. signer.stop_node waits for the node to go ------------------------

rpc = FakeRpc(replies_after_stop=3)
if signer.stop_node(rpc, timeout=5, poll=0.01) is not True:
    bad("stop_node returned False for a node that did shut down")
elif rpc.calls[0] != "stop":
    bad(f"stop_node did not ask the node to stop first: {rpc.calls[:2]}")
elif rpc.calls.count("uptime") != 4:
    bad(f"stop_node did not poll until refusal: {rpc.calls}")
else:
    ok("stop_node calls stop, then polls until the node refuses RPC")


class NeverStops(FakeRpc):
    def call(self, method, *params, **kw):
        self.calls.append(method)
        return "" if method == "stop" else 12      # answers uptime for ever


t0 = time.monotonic()
if signer.stop_node(NeverStops(), timeout=0.3, poll=0.01) is not False:
    bad("stop_node reported success for a node that stayed up")
elif time.monotonic() - t0 > 1.0:
    bad("stop_node overran its 0.3s timeout")
else:
    ok("stop_node returns False, bounded by its timeout, if the node stays up")

down = FakeRpc()
down.call = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("refused"))
if signer.stop_node(down, timeout=1) is not True:
    bad("stop_node did not treat an already-dead node as stopped")
else:
    ok("stop_node treats an already-dead node as stopped")


# --- 2. under systemd: cover the screen, then halt ------------------------
#
# systemctl poweroff stops corky-bitcoind.service by that unit's own
# ExecStop, so the session must NOT also stop the node. Calling stop twice
# makes the unit's ExecStop fail against a node that has already gone.

events, display, rpc = run_power_off(on_device=True)

runs = [e[1] for e in events if e[0] == "run"]
if not runs:
    bad("power_off never halted the board: the device stays powered on")
elif runs != [corky_main.HALT_CMD]:
    bad(f"power_off ran {runs}, not exactly {[corky_main.HALT_CMD]}")
else:
    ok(f"power_off halts the board with {corky_main.HALT_CMD}, once")

if "stop" in rpc.calls:
    bad("power_off stopped the node itself; corky-bitcoind.service's own "
        "ExecStop already does that during the systemd shutdown")
else:
    ok("power_off leaves the node to systemd when systemd answers")

first_paint = next((i for i, e in enumerate(events) if e == "show"), None)
first_halt = next((i for i, e in enumerate(events) if e[0] == "run"), None)
if first_paint is None:
    bad("power_off painted nothing: the result screen stays on the panel")
elif first_paint > first_halt:
    bad("power_off halted before covering the result screen, which leaves "
        "an address and an amount on a panel that holds its last frame")
else:
    ok("the result screen is covered before the halt begins")

if len(display.shown) < 1 or display.shown[0].size != (320, 240):
    bad("the covering frame is not a full panel")
else:
    ok("the covering frame fills the panel")


# --- 2b. no systemd at all: stop the node here, then halt directly --------
#
# subprocess.run(check=False) suppresses a non-zero exit but still raises
# FileNotFoundError, so a missing systemctl is the case the fallback exists
# for and the case that used to skip it.

events, display, rpc = run_power_off(on_device=True, systemctl=MISSING)
runs = [e[1] for e in events if e[0] == "run"]
if "stop" not in rpc.calls:
    bad("systemctl is missing and power_off did not stop bitcoind: the node "
        "outlives the session and keeps writing to the ramdisk")
elif runs[-1] != corky_main.FALLBACK_HALT_CMD:
    bad(f"systemctl is missing and the fallback halt did not run: {runs}")
else:
    order = [e for e in events
             if e == ("rpc", "stop") or e == ("run", corky_main.FALLBACK_HALT_CMD)]
    if order[0] != ("rpc", "stop"):
        bad("the fallback halted before stopping the node")
    else:
        ok(f"a missing systemctl still stops the node, then runs "
           f"{corky_main.FALLBACK_HALT_CMD}")

events, display, rpc = run_power_off(on_device=True, systemctl=FAILS)
if "stop" not in rpc.calls:
    bad("systemctl exited non-zero and power_off did not stop bitcoind")
else:
    ok("a failing systemctl also falls back to stopping the node")


# --- 3. a board that is still running must say so (D16, D17) -------------

events, display, rpc = run_power_off(on_device=True, systemctl=MISSING,
                                     halt=MISSING)
if not display.shown:
    bad("both halts failed and the panel says nothing")
elif display.shown[-1] == display.shown[0]:
    bad("both halts failed and the panel still reads 'powering off' on a "
        "device that is still running: that is audit D16 again")
else:
    ok("both halts failed and the last frame reports it, so the operator "
       "knows to remove power")


class StubbornRpc(FakeRpc):
    """The halt works but the node refuses to stop."""

    def call(self, method, *params, **kw):
        self.calls.append(method)
        return "" if method == "stop" else 12


events, display, rpc = run_power_off(on_device=True, rpc=StubbornRpc(),
                                     systemctl=MISSING)
if display.shown[-1] == display.shown[0]:
    bad("the node never stopped and the panel did not report it")
else:
    ok("a node that will not stop is reported, not discarded")


# --- 4. the dev harness must not be touched ------------------------------
#
# Every scripted session shares one bitcoind. A session that stopped it, or
# halted the Mac, would fail every session after it.

events, display, rpc = run_power_off(on_device=False)
if rpc.calls:
    bad(f"power_off touched the node in dev mode: {rpc.calls}")
elif any(e[0] == "run" for e in events if isinstance(e, tuple)):
    bad("power_off tried to halt the machine in dev mode")
else:
    ok("power_off is inert in dev mode: no node stop, no halt")


# --- 5. a crash must NOT halt --------------------------------------------
#
# corky.service restarts on failure. Halting on a crash would turn a
# recoverable fault into a dead device in the user's hand.

events = []
display = RecordingDisplay(events)
session = corky_main.Session(display, hal.DevButtons("a"), FakeRpc(),
                             animate=True, on_device=True)
session.state_home = lambda: (_ for _ in ()).throw(RuntimeError("driver"))
real_run = corky_main.subprocess.run
corky_main.subprocess.run = lambda cmd, **kw: events.append(("run", list(cmd)))
try:
    session.run()
except RuntimeError:
    pass
finally:
    corky_main.subprocess.run = real_run

if any(e[0] == "run" for e in events if isinstance(e, tuple)):
    bad("a crash halted the board; systemd can no longer restart the unit")
else:
    ok("a crash propagates without halting, so systemd restarts the session")


print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
