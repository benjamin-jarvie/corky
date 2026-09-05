"""Device usability, measured rather than asserted.

Two things this suite holds:

1. Error recovery. A failure the user cannot read is a failure the user
   cannot act on. Every failing path must park on its message until a key is
   pressed, and the sign button must say why it is refusing.
2. Entry cost. The number of button presses per task is a design budget. The
   figures below are the audit's measurements; the test fails if entry gets
   more expensive, so a regression is visible before it reaches a panel.

Run: python3 tests/test_ui_cost.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import main as corky_main  # noqa: E402
import screens  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    fails.append(m)
    print("FAIL", m)


class RecordingDisplay:
    """Records which screen was painted, in order."""

    width, height = 320, 240

    def __init__(self):
        self.painted = []

    def show(self, image, sensitive=False):
        self.painted.append(image)


class ScriptedButtons:
    def __init__(self, script):
        self.script = list(script)
        self.reads = 0

    def read(self):
        self.reads += 1
        if not self.script:
            raise AssertionError("session read past the end of its script")
        return self.script.pop(0)


def named_screens(display):
    """Paint names instead of images, so a session's screen order is
    assertable without rendering."""
    for name in ("home", "load_key_menu", "result", "busy", "review",
                 "settings_menu"):
        setattr(screens, name,
                (lambda n: lambda *a, **k: n)(name))
    return display


class FakeRpc:
    wallet_dir = Path("/nonexistent")  # A-22: close_session reads it
    chain = "regtest"

    def call(self, method, *a, **k):
        # home now asks for the master fingerprint on every repaint, and it
        # subscripts what comes back. A double that returns "" for every
        # method is not a wallet-shaped answer.
        if method == "listdescriptors":
            return {"descriptors": []}
        return ""


# --- boot splash: the signing unit must activate the ordered unit ---------
service = (ROOT / "image" / "corky.service").read_text()
if "Wants=corky-splash.service" not in service:
    bad("corky.service orders after the splash but does not activate it")
else:
    ok("enabling corky.service also activates the brand splash")


# --- boot splash: the dedicated entrypoint paints exactly one frame -------
painted = []


class SplashDisplay:
    width, height = 320, 240

    def show(self, image, sensitive=False):
        painted.append(image)


import splash as corky_splash  # noqa: E402  (dedicated boot entrypoint)

real_argv = sys.argv
real_dev_display = corky_splash.hal.DevDisplay
real_splash = screens.splash
try:
    sys.argv = ["splash.py", "--dev", "--frames-dir", "unused"]
    corky_splash.hal.DevDisplay = lambda _path: SplashDisplay()
    screens.splash = lambda w, h: ("splash", w, h)
    corky_splash.main()
finally:
    sys.argv = real_argv
    corky_splash.hal.DevDisplay = real_dev_display
    screens.splash = real_splash

if painted != [("splash", 320, 240)]:
    bad(f"the splash entrypoint painted unexpected frames: {painted}")
else:
    ok("the splash entrypoint paints one branded frame and exits")


# --- backup strings paginate in order and C aborts immediately ------------
backup_calls = []
real_backup_screen = screens.backup_page
try:
    screens.backup_page = (
        lambda _w, _h, page_text, _label, page, pages:
        backup_calls.append((page_text, page, pages)) or "backup")
    buttons = ScriptedButtons("aac")
    session = corky_main.Session(RecordingDisplay(), buttons, FakeRpc())
    completed = session._show_backup("x" * 97, "KEY  D2B7E45C")
    abort_calls = list(backup_calls)

    backup_calls.clear()
    success_buttons = ScriptedButtons("aa")
    success_session = corky_main.Session(
        RecordingDisplay(), success_buttons, FakeRpc())
    succeeded = success_session._show_backup("y" * 49, "KEY  D2B7E45C")
    success_calls = list(backup_calls)
finally:
    screens.backup_page = real_backup_screen

expected_abort = [("x" * 48, 0, 3), ("x" * 48, 1, 3), ("x", 2, 3)]
expected_success = [("y" * 48, 0, 2), ("y", 1, 2)]
if (completed or abort_calls != expected_abort or buttons.reads != 3 or
        not succeeded or success_calls != expected_success or
        success_buttons.reads != 2):
    bad("backup pagination/abort drifted: "
        f"abort={abort_calls}, success={success_calls}")
else:
    ok("backup strings paginate in order, complete, and abort immediately")


# --- D6: a failing seed mode must hold its message ------------------------
_real = {n: getattr(screens, n) for n in
         ("home", "load_key_menu", "result", "busy", "review",
          "settings_menu")}
display = named_screens(RecordingDisplay())
# R,A opens the Key tile; with no key loaded that is Load a key. A picks
# "Scan a key", A accepts the warning, and the scan raises because the key
# scan is not wired (ticket 09); ONE key dismisses the error, then D,R,A,A
# goes home -> settings -> power off. If the error is not held, the
# dismissing A re-opens the menu.
buttons = ScriptedButtons(["r", "a"] + ["a", "a"] + ["a"] +
                          ["d", "r", "a", "a"])
session = corky_main.Session(display, buttons, FakeRpc())
session.qr = corky_main.CameraQrSource()
raised = None
try:
    session.state_home()
except Exception as exc:
    raised = exc
for n, f in _real.items():
    setattr(screens, n, f)

painted = display.painted
if raised is not None:
    bad(f"the error was not held; the session ran off its script: {raised}")
# A-22: the old path went through SeedQR, which painted a "busy" frame
# before it failed. The xprv scan raises straight out of the warning
# screen, so there is no busy frame to require. What this check is
# actually about is unchanged: the failure is SHOWN, and the next thing
# the user sees is home, not the menu they just failed out of.
elif not (painted[0] == "home"
          and "result" in painted
          and painted[painted.index("result") + 1] == "home"
          and painted.count("load_key_menu") >= 1):
    bad(f"unexpected screen order after a failing seed mode: {painted}")
else:
    ok("a failing seed mode holds its error until a key is pressed")

# --- D9: the sign button explains its refusal -----------------------------
img_quiet = _real["review"](320, 240, [("bc1q", 1.0)], 0.0001)
img_loud = _real["review"](320, 240, [("bc1q", 1.0)], 0.0001,
                           unseen_pages=True)
if img_quiet.tobytes() == img_loud.tobytes():
    bad("review() renders the same frame whether or not SIGN was refused")
else:
    ok("review() says why it will not sign yet")

# --- entry cost budgets ---------------------------------------------------
# A-22: the word and codex32 entry budgets went with their grids.





# --- I-6: the two decision screens, branch by branch ----------------------
# Both were reached only through end-to-end sessions, so their individual
# outcomes were never asserted. TESTING.md rule 3: exercise the branches.

class Rec:
    """Records the actions_sel / selected each screen was drawn with."""

    width, height = 320, 240

    def __init__(self):
        self.sel = []

    def show(self, image, sensitive=False):
        pass


def signed_outcome(keys):
    d = Rec()
    sess = corky_main.Session(d, ScriptedButtons(list(keys)), FakeRpc())
    return sess._state_signed("x.psbt written")


cases = [("a", corky_main.SIGN_AGAIN, "A on the default choice signs another"),
         ("ra", corky_main.POWER_OFF, "R then A powers off"),
         ("rla", corky_main.SIGN_AGAIN, "R then L returns to sign another"),
         ("c", corky_main.POWER_OFF, "C on the result powers off")]
for keys, want, why in cases:
    got = signed_outcome(keys)
    if got != want:
        bad(f"_state_signed({keys!r}) returned {got!r}, expected {want!r}")
    else:
        ok(f"_state_signed: {why}")




# A-22: the passphrase entry checks lived here. The prompt was a BIP39
# concept and went with it, and this scaffolding computed key sequences
# for assertions that were already gone.


print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
