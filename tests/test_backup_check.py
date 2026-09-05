"""Typing a paper backup back in, and being told exactly what is wrong.

The last backup page offered VERIFY for months and then just returned to
the menu (Ben, on the board, 2026-09-05). This is the flow it now runs.

These checks are in-process rather than in an end-to-end session because
every screen in the flow shows key material, so hal.DevDisplay blanks the
frames a scripted session writes: the session can prove the flow COMPLETES
but cannot see what it said. Here the screens are rendered directly and the
loop is driven with a scripted keypad, so the wrong character is visible.

Run: python3 tests/test_backup_check.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "tests"))
import hal                              # noqa: E402
import main as corky_main               # noqa: E402
import screens                          # noqa: E402
from e2e_keys import grid_presses, text_keys   # noqa: E402

# A real regtest master private key, the one every other suite signs with.
KEY = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ss"
       "vpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")
LABEL = "KEY  73C5DA0A"

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


class Frames:
    """Keeps every frame, unblanked, so a check can look at what was said."""

    width, height = 320, 240

    def __init__(self):
        self.shown = []

    def show(self, image, sensitive=False):
        self.shown.append(image)


def session(script):
    return corky_main.Session(Frames(), hal.DevButtons(script), None,
                              animate=False, on_device=False)


def run_page(script, want):
    sess = session(script)
    try:
        return sess, sess._check_page(LABEL, 0, 3, want)
    except hal.ScriptExhausted:
        return sess, "ran out of presses"


def drew(sess, image):
    want = image.tobytes()
    return any(f.tobytes() == want for f in sess.display.shown)


PAGES = screens.text_pages(KEY)

# --- 1. a page typed correctly is accepted ------------------------------

sess, got = run_page(text_keys("xprv", PAGES[0]) + "a", PAGES[0])
if got != PAGES[0]:
    bad(f"a correctly typed page was not accepted: {got!r}")
elif not drew(sess, screens.check_result(320, 240, PAGES[0], set(),
                                         LABEL, 0, 3)):
    bad("the verdict for a correct page was never drawn")
else:
    ok("a page typed back correctly is accepted, and says so")

# --- 2. one wrong character is named, and only that one -----------------
# Rule 1: the wrong character is chosen from the real key, not invented,
# and the check asserts WHICH position was marked.

AT = 5
RIGHT = PAGES[0][AT]
TYPO = "2" if RIGHT != "2" else "3"
BAD_PAGE = PAGES[0][:AT] + TYPO + PAGES[0][AT + 1:]

sess, got = run_page(text_keys("xprv", BAD_PAGE) + "la", PAGES[0])
if got is not None:
    bad(f"ABORT on a failed check did not leave the flow: {got!r}")
elif not drew(sess, screens.check_result(320, 240, BAD_PAGE, {AT},
                                         LABEL, 0, 3)):
    bad(f"the verdict did not mark position {AT} and only that position")
else:
    ok(f"one wrong character is marked at position {AT}, alone")

# The screen must actually differ from the all-correct one, or marking
# proves nothing (a render that ignores `wrong` would pass the check above
# only by accident of the text differing too).
if (screens.check_result(320, 240, PAGES[0], {AT}, LABEL, 0, 3).tobytes()
        == screens.check_result(320, 240, PAGES[0], set(), LABEL, 0, 3)
        .tobytes()):
    bad("check_result draws the same frame whether or not a character is wrong")
else:
    ok("the verdict screen looks different when a character is wrong")

# --- 3. FIX lands on the wrong character and overwrites it in place -----
# This is the whole point of the caret: correcting position 5 must not
# cost the 42 characters after it.

fix = (text_keys("xprv", BAD_PAGE)          # type it wrong
       + "a"                                 # verdict: FIX is pre-selected
       + grid_presses("xprv", RIGHT) + "p"   # overwrite AT the caret, CHECK
       + "a")                                # verdict: matches
sess, got = run_page(fix, PAGES[0])
if got != PAGES[0]:
    bad(f"FIX did not correct the character in place: {got!r}")
else:
    ok("FIX lands on the wrong character and overwrites it in place")

# A short character count proves it overwrote rather than inserted.
if got is not None and len(got) != len(PAGES[0]):
    bad(f"FIX changed the page length to {len(got)}")

# --- 4. a short page is wrong, and every missing position is named ------

short = PAGES[0][:10]
sess, got = run_page(text_keys("xprv", short) + "la", PAGES[0])
missing = set(range(10, len(PAGES[0])))
if got is not None:
    bad("a page that stops early was accepted")
elif not drew(sess, screens.check_result(320, 240, short, missing,
                                         LABEL, 0, 3)):
    bad("a page that stops early did not name the characters still missing")
else:
    ok("a page that stops early is refused, and the gap is named")

# --- 5. the caret walks the typed text, which is what C is for ----------
# L and R in text focus move the caret; B there deletes the character
# under it. Without this a mistake 40 characters back costs 40 deletions.

sess = session("c" + "ll" + "b" + "p")   # to the text, back 2, delete, done
typed, caret = sess._check_entry(LABEL, 0, 3, 48, "abcde", 5)
if typed != "abce":
    bad(f"C then L,L then B deleted the wrong character: {typed!r}")
elif caret != 3:
    bad(f"the caret ended at {caret}, not on the gap it made")
else:
    ok("C moves focus to the text, L/R walk the caret, B deletes there")

# --- 6. ABORT on the entry screen leaves, and B on an empty page leaves -

sess = session("ccla")               # to the bar, to ABORT, take it
typed, _ = sess._check_entry(LABEL, 0, 3, 48, "", 0)
if typed is not None:
    bad(f"ABORT on the check entry returned {typed!r} instead of leaving")
else:
    ok("ABORT on the check entry leaves the flow")

sess = session("b")
typed, _ = sess._check_entry(LABEL, 0, 3, 48, "", 0)
if typed is not None:
    bad("B with nothing typed did not leave the check entry")
else:
    ok("B with nothing typed leaves, like B everywhere else")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
