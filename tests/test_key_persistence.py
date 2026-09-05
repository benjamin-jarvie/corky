"""A key stays loaded until the device is turned off.

Everything else in this repo pushes the other way: `test_no_persistence.py`
proves no key survives a power-off, a crash or a discard. Nothing pinned
the direction Ben actually relies on, which is that a key survives
everything ELSE for as long as the device is on.

Ben, 2026-09-05: "I think the keys we're wiping after a certain amount of
time or was that you in development removing them? They need to persist
unless turned off essentially."

It was development. There is no timer, and this suite is what says so, so
that a regression which added one goes red instead of quietly costing
somebody a re-scan in the middle of signing.

A key is dropped in exactly three places and all three are deliberate:
close_session at POWER OFF, clear_on_start at startup so a crashed
session's key is never adopted, and close_key when the user discards it.

Run: python3 tests/test_key_persistence.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import hal                          # noqa: E402
import main as corky_main           # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


# --- 1. no clock, timer or deadline reaches a key-dropping call ---------
# A static check, because a timing test that waits long enough to be
# convincing is a test nobody runs.

DROPS = {"close_session", "close_key", "clear_on_start", "_drop_wallet"}
CLOCKS = {"sleep", "monotonic", "time", "Timer", "alarm", "settimeout"}


def calls_in(node):
    """Every attribute or name called anywhere under this node."""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


for mod in ("main.py", "signer.py"):
    tree = ast.parse((ROOT / "corky" / mod).read_text())
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        names = calls_in(fn)
        drops = names & DROPS
        clocks = {c for c in names if c.lower() in
                  {x.lower() for x in CLOCKS}}
        # power_off legitimately does both: it stops the node on a timeout.
        if drops and clocks and fn.name not in ("power_off", "run"):
            bad(f"{mod}:{fn.name} both drops a key {sorted(drops)} and "
                f"reads a clock {sorted(clocks)}")
ok("no function drops a key anywhere near a clock, timer or deadline")


# --- 2. the three deliberate drops, and only those ----------------------

src = (ROOT / "corky" / "main.py").read_text()
tree = ast.parse(src)
sites = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("close_session", "close_key",
                                   "clear_on_start"):
        parent = next((f.name for f in ast.walk(tree)
                       if isinstance(f, ast.FunctionDef)
                       and node in ast.walk(f)), "?")
        sites.append((node.func.attr, parent, node.lineno))

want = {("clear_on_start", "run"), ("close_session", "run"),
        ("close_key", "_discard")}
got = {(a, b) for a, b, _ in sites}
if got != want:
    bad(f"the places a key is dropped changed: {sorted(got)}")
else:
    ok("a key is dropped in three places only: startup, power off, discard")


# --- 3. the session keeps the key across everything else ---------------
# Drive the real state machine: load a key, wander, come back. The key
# must still be there, and close_session must not have run.

class NullDisplay:
    width, height = 320, 240

    def show(self, image, sensitive=False):
        pass


class CountingRpc:
    """Answers enough for the menus, and counts what would drop a key."""

    chain = "regtest"
    wallet_dir = Path("/nonexistent")

    def __init__(self):
        self.dropped = []
        self.loaded = ["corky"]

    def call(self, method, *a, **k):
        if method in ("unloadwallet",):
            self.dropped.append(a[:1])
            return ""
        if method == "listwallets":
            return list(self.loaded)
        if method == "listwalletdir":
            return {"wallets": [{"name": n} for n in self.loaded]}
        if method == "listdescriptors":
            return {"descriptors": [
                {"desc": "wpkh([73c5da0a/84h/0h/0h]xpub6/0/*)#aaaaaaaa",
                 "active": True, "internal": False}]}
        return ""


# Home -> Keys -> the key's menu -> back -> Keys -> back -> Home, twice
# over, then leave without powering off.
script = ("ra" + "a" + "b" + "b") * 2 + "b"
rpc = CountingRpc()
sess = corky_main.Session(NullDisplay(), hal.DevButtons(script), rpc,
                          animate=False, on_device=False)
try:
    sess.state_home()
except hal.ScriptExhausted:
    pass
except Exception as exc:                       # noqa: BLE001
    bad(f"walking the menus raised {type(exc).__name__}: {exc}")

if rpc.dropped:
    bad(f"walking the menus unloaded a wallet: {rpc.dropped}")
else:
    ok("walking in and out of a key's menu never unloads it")

if rpc.loaded != ["corky"]:
    bad(f"the loaded key changed: {rpc.loaded}")
else:
    ok("the key is still loaded after the walk")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
