"""One keyboard, one key map, on every screen that asks you to type.

Ben, on the board, 2026-09-18: "Is every keyboard for typing uniform
like this now? Entering, reentering, anywhere else?"

There are three screens and two loops. `_text_entry` drives a master
private key and a derivation path; `_check_entry` drives a paper backup
typed back in. Both render `screens.text_entry` and both handle the
same eight controls, and they are two bodies of code, so nothing but a
check keeps them the same. Every fix this week had to be made twice:
centre-is-select, the case toggle, the d-pad loop, the focus mark.

So this drives the SAME script into each screen and asserts the SAME
outcome. A rule that reaches one loop and not the other fails here.

Run: python3 tests/test_typing_uniform.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "coresigner"))
sys.path.insert(0, str(ROOT / "tests"))
import hal                              # noqa: E402
import main as coresigner_main          # noqa: E402
import screens                          # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


class Frames:
    """Keeps every frame unblanked, so a check can look at what was said."""

    width, height = 320, 240

    def __init__(self):
        self.shown = []

    def show(self, image, sensitive=False):
        self.shown.append(image)


def session(script):
    return coresigner_main.Session(Frames(), hal.DevButtons(script), None,
                                   animate=False, on_device=False)


#: The key the check screen compares against. The WHOLE key: the
#: check stopped paging on 2026-09-19, because a page you could not
#: leave until it was perfect was a page a person could not get past.
PAGE = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ss"
        "vpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")


def _entry(charset):
    """Drives _text_entry. Returns (result, frames)."""
    def run(script):
        sess = session(script)
        try:
            got = sess._text_entry("TYPE", charset)
        except hal.ScriptExhausted:
            return "ran out of presses", sess
        return got, sess
    return run


def _check(script):
    """Drives _check_entry, with the same shape of answer."""
    sess = session(script)
    try:
        typed, _made = sess._check_entry("KEY", PAGE, "")
    except hal.ScriptExhausted:
        return "ran out of presses", sess
    return typed, sess


#: Every screen a person types on, with the charset its grid shows.
#: "path" is behind screens.TYPED_PATH and off for the pilot; it is
#: here because the loop that drives it is the same loop, and a screen
#: that comes back on must come back uniform.
SCREENS = [("a master private key", "xprv", _entry("xprv")),
           ("a derivation path", "path", _entry("path")),
           ("a backup typed back in", "xprv", _check)]


def cells_of(charset):
    return screens.mode_cells(screens.modes(charset)[0][1])


def to_bar(charset):
    """Presses that take the grid cursor off the bottom, onto the bar."""
    cells, at, downs = cells_of(charset), 0, 1
    while coresigner_main._cell_move("d", cells, at) != at:
        at = coresigner_main._cell_move("d", cells, at)
        downs += 1
    return "d" * downs


# --- 1. DOWN reaches the bar, and LEFT then A leaves ---------------------
for label, charset, drive in SCREENS:
    got, _sess = drive(to_bar(charset) + "la")
    if got is None:
        ok(f"{label}: DOWN to the bar, LEFT, then A leaves")
    else:
        bad(f"{label}: DOWN, LEFT, A returned {got!r}, so the left-hand "
            "button is not reachable by going down")

# --- 2. DOWN from the bar loops back to the top of the grid --------------
for label, charset, drive in SCREENS:
    got, _sess = drive(to_bar(charset) + "d" + to_bar(charset) + "la")
    if got is None:
        ok(f"{label}: DOWN from the bar loops to the grid, and round again")
    else:
        bad(f"{label}: the d-pad does not loop through the bar; got {got!r}")

# --- 3. the centre press is SELECT, not an exit --------------------------
# One press of A and one of P on the first cell of the grid. Both type a
# character, so neither leaves, and the script runs out.
for label, _charset, drive in SCREENS:
    for press in ("a", "p"):
        got, _sess = drive(press)
        if got != "ran out of presses":
            bad(f"{label}: {press.upper()} on the grid returned {got!r} "
                "instead of selecting the character under the cursor")
            break
    else:
        ok(f"{label}: A and P both select the character, neither leaves")

# --- 4. B with nothing typed leaves ------------------------------------
for label, _charset, drive in SCREENS:
    got, _sess = drive("b")
    if got is None:
        ok(f"{label}: B with nothing typed leaves, as B does everywhere")
    else:
        bad(f"{label}: B with nothing typed returned {got!r}")

# --- 5. no button is marked while the grid has the focus -----------------
# The frame BEFORE the first press is the screen as it opens, which is
# the one Ben was reading when he decided ABORT could not be reached.
for label, charset, drive in SCREENS:
    _got, sess = drive("b")
    first = sess.display.shown[0]
    lit = screens.text_entry(320, 240, "TYPE", "", 0, charset, 0,
                             actions_sel=1)
    band = (0, int(240 * 0.87), 320, 240)
    if first.crop(band).tobytes() == lit.crop(band).tobytes():
        bad(f"{label}: a button is marked before the bar has the focus, "
            "so DOWN into the bar shows nothing")
    else:
        ok(f"{label}: nothing on the bar is marked until it has the focus")

# --- 6. one renderer, and every screen reaches it ------------------------
src = (ROOT / "coresigner" / "main.py").read_text()
renders = src.count("screens.text_entry(")
if renders != 2:
    bad(f"{renders} call sites render the keyboard, not 2. A third "
        "typing screen is a third place every rule has to reach.")
else:
    ok("two loops render one keyboard, and this suite drives both")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
