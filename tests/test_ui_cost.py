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
sys.path.insert(0, str(ROOT / "shim"))
import main as corky_main  # noqa: E402
import screens  # noqa: E402
from bip39_shim import load_wordlist  # noqa: E402

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
    for name in ("home", "seed_menu", "result", "busy", "review",
                 "tools_menu", "seed_length", "settings_menu"):
        setattr(screens, name,
                (lambda n: lambda *a, **k: n)(name))
    return display


class FakeRpc:
    chain = "regtest"

    def call(self, *a, **k):
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
real_backup_screen = screens.codex32_share_display
try:
    screens.codex32_share_display = (
        lambda _w, _h, page_text, _index, _total, page, pages:
        backup_calls.append((page_text, page, pages)) or "backup")
    buttons = ScriptedButtons("aac")
    session = corky_main.Session(RecordingDisplay(), buttons, FakeRpc())
    completed = session._show_backup("x" * 97, 1, 1)
    abort_calls = list(backup_calls)

    backup_calls.clear()
    success_buttons = ScriptedButtons("aa")
    success_session = corky_main.Session(
        RecordingDisplay(), success_buttons, FakeRpc())
    succeeded = success_session._show_backup("y" * 49, 1, 1)
    success_calls = list(backup_calls)
finally:
    screens.codex32_share_display = real_backup_screen

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
         ("home", "seed_menu", "result", "busy", "review", "tools_menu",
          "seed_length", "settings_menu")}
display = named_screens(RecordingDisplay())
# A opens load key (top-left tile), six D then A -> "Scan SeedQR" (index 6
# of the eight load-key modes), which raises like the camera stub does; ONE
# key dismisses the error, then D,R,A,A goes home -> settings -> power off.
# If the error is not held, the dismissing A re-opens the menu instead.
buttons = ScriptedButtons(["a"] + ["d"] * 6 + ["a", "a"] +
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
elif not (painted[0] == "home" and "busy" in painted
          and "result" in painted
          and painted[painted.index("result") + 1] == "home"
          and painted.count("seed_menu") >= 1):
    bad(f"unexpected screen order after a failing seed mode: {painted}")
else:
    ok("a failing seed mode holds its error until a key is pressed")

# --- D9: the sign button explains its refusal -----------------------------
img_quiet = _real["review"](320, 240, [("bc1q", 1.0)], 0.0001, 1)
img_loud = _real["review"](320, 240, [("bc1q", 1.0)], 0.0001, 1,
                           unseen_pages=True)
if img_quiet.tobytes() == img_loud.tobytes():
    bad("review() renders the same frame whether or not SIGN was refused")
else:
    ok("review() says why it will not sign yet")

# --- entry cost budgets ---------------------------------------------------
WORDLIST = load_wordlist()


def word_presses(word):
    """Replays Session._collect_words as it is TODAY: an 8x4 letter grid.

    The dial this used to model died with audit item D4. A cost model that
    measures a UI the device no longer has reports a confident, meaningless
    number, which TESTING.md rule 4 exists to prevent.

    Per letter: u/d moves a row (wrapping mod 32), l/r moves a column, A
    types it. The word is taken with the centre press once it heads the
    candidate list.
    """
    prefix, total, cur = "", 0, 0
    while True:
        cands = [w for w in WORDLIST if w.startswith(prefix)][:3]
        if cands and cands[0] == word:
            return total + 1          # centre press takes the top candidate
        nxt = word[len(prefix)]
        t = screens.ALPHABET.index(nxt)
        rows = (t // 8 - cur // 8) % 4
        cols = (t % 8 - cur % 8) % 8
        total += min(rows, 4 - rows) + min(cols, 8 - cols) + 1
        cur = t
        prefix += nxt


import random  # noqa: E402  (test-only; never imported by device code)
random.seed(1)
sample = [random.choice(WORDLIST) for _ in range(24)]
cost = sum(word_presses(w) for w in sample)
# The grid replaced the dial (D4). The dial cost 546 presses for 24 words;
# the budget below is the grid's measured cost with headroom, and it must
# never drift back toward the dial's number.
BUDGET = 380
if cost > BUDGET:
    bad(f"24-word entry now costs {cost} presses, over the {BUDGET} budget")
else:
    ok(f"24-word entry costs {cost} presses on the grid "
       f"(budget {BUDGET}; the old dial cost 546)")

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


def passphrase_outcome(keys):
    sess = corky_main.Session(Rec(), ScriptedButtons(list(keys)), FakeRpc())
    return sess._ask_passphrase()


# NO is the default, so a single A must never open the text grid.
if passphrase_outcome("a") != "":
    bad("_ask_passphrase: A on the default NO did not return an empty string")
else:
    ok("_ask_passphrase: A on the default NO gives no passphrase")

if passphrase_outcome("b") != "":
    bad("_ask_passphrase: B did not decline")
else:
    ok("_ask_passphrase: B declines")

# YES opens the grid; typing z then centre-press returns it.
zi = screens.charset_pages("passphrase")
zpage = next(i for i, pg in enumerate(zi) if "z" in pg)
keys = ["r", "a"]                       # NO -> YES, then open the grid
cur, page = 0, 0
while page < zpage:                     # r past the end turns the page
    while cur < len(zi[page]) - 1:
        keys.append("r"); cur += 1
    keys.append("r"); page += 1; cur = 0
ti = zi[zpage].index("z")
while cur + 8 <= ti:
    keys.append("d"); cur = min(len(zi[page]) - 1, cur + 8)
while cur < ti:
    keys.append("r"); cur += 1
keys.append("a")                        # type it
keys.append("p")                        # centre press = done
if passphrase_outcome(keys) != "z":
    bad("_ask_passphrase: YES then typing 'z' did not return 'z'")
else:
    ok("_ask_passphrase: YES opens the grid and returns what was typed")

# CANCEL on the grid must give no passphrase, not the characters typed.
cancel_keys = ["r", "a", "a", "c", "a"]   # YES, type one char, C -> bar, A
# the bar lands on DONE, so move to CANCEL first: C then L then A
cancel_keys = ["r", "a", "a", "c", "l", "a"]
if passphrase_outcome(cancel_keys) != "":
    bad("_ask_passphrase: CANCEL on the grid kept the typed characters")
else:
    ok("_ask_passphrase: CANCEL on the grid discards what was typed")


print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
