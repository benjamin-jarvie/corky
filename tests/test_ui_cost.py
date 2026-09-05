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
    for name in ("home", "keys_menu", "result", "busy", "review",
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
         ("home", "keys_menu", "result", "busy", "review",
          "settings_menu")}
display = named_screens(RecordingDisplay())
# R,A opens the Keys tile. The list is flat now (Ben, 2026-09-05), so D
# moves from New key to Scan a key, A picks it, A accepts the warning, and
# the scan fails because this machine has no camera. ONE key dismisses the
# error. C leaves Keys for home, then D,R,A,A goes to settings and powers
# off. If the error is not held, the dismissing A falls through and the
# script runs out.
buttons = ScriptedButtons(["r", "a"] + ["d", "a"] + ["a"] + ["a"] +
                          ["c"] + ["d", "r", "a", "a"])
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
# The failure is SHOWN, and the screen after it is the one level UP from
# the menu that failed, not the menu itself. Before 2026-09-05 that was
# home, because Load a key was reached straight from the tile; now Keys
# sits between them, so Keys is where a failed load returns you.
elif not (painted[0] == "home"
          and "result" in painted
          and painted[painted.index("result") + 1] == "keys_menu"
          and painted.count("keys_menu") >= 2):
    bad(f"unexpected screen order after a failing key mode: {painted}")
else:
    ok("a failing key mode holds its error, then returns to Keys")

# --- the passphrase screen must not be a dead end -------------------------
# On the board 2026-09-05 the back button did nothing on an empty
# passphrase, because B deletes a character and there was nothing to
# delete, and DONE with nothing threw the user out to the key menu.
class Recorder:
    width, height = 320, 240

    def __init__(self):
        self.painted = []

    def show(self, image, sensitive=False):
        self.painted.append(image)


def entry(keys):
    sess = corky_main.Session(Recorder(), ScriptedButtons(keys), FakeRpc())
    return sess._text_entry("PASSPHRASE", "passphrase", secret=True)


if entry(["b"]) is None:
    ok("B on an empty passphrase goes back instead of doing nothing")
else:
    bad("B on an empty passphrase did not go back")

if entry(["a", "b", "b"]) is None:
    ok("B deletes what is there, then goes back when there is nothing")
else:
    bad("B did not fall through to back once the buffer was empty")

# DONE with nothing asks again, and only a deliberate confirmation makes an
# unencrypted backup.
sess = corky_main.Session(Recorder(), ScriptedButtons(
    ["p"] +            # DONE with an empty box
    ["b"] +            # back out of the no-passphrase warning
    ["a", "p"]         # type one character, DONE
), FakeRpc())
got = sess._ask_passphrase("PASSPHRASE")
if got and got != corky_main.Session.NO_PASSPHRASE:
    ok("an empty passphrase asks again instead of leaving the flow")
else:
    bad(f"_ask_passphrase returned {got!r} after the box was left empty")

sess = corky_main.Session(Recorder(), ScriptedButtons(
    ["p"] +            # DONE with an empty box
    ["r", "a"]         # move to NO PASSPHRASE and take it
), FakeRpc())
if sess._ask_passphrase("PASSPHRASE") == corky_main.Session.NO_PASSPHRASE:
    ok("no passphrase is possible, but only after a deliberate choice")
else:
    bad("the no-passphrase choice did not come back as such")

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
