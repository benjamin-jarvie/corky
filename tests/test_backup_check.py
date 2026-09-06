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
import signer                           # noqa: E402
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

# --- 7. every screen that can show a key is marked sensitive ------------
# hal.DevDisplay blanks a frame shown with sensitive=True, which is what
# stops key material landing as a PNG on a developer's disk. That property
# rests on call sites in main.py, and until audit A2 only one was covered,
# incidentally: session K3 counts blank frames and would have noticed the
# backup pages going unmarked.
#
# The first version of this check was VACUOUS for two of its four cases. A
# script of twenty presses never leaves the entry screen, so the verdict
# was never painted and the same 21 entry frames were counted twice; a
# devil's advocate dropped a flag and watched it still pass (2026-09-06).
# Each case below now drives the screen it names, with the arguments the
# real caller uses, and says how many frames it saw so a vacuous run shows
# up as a suspiciously small number.

class FlagWatcher:
    """Records the sensitive flag for every frame, and what was painted."""

    width, height = 320, 240

    def __init__(self):
        self.flags = []
        self.kinds = []

    def show(self, image, sensitive=False):
        self.flags.append(sensitive)
        self.kinds.append(image.size)


def flags_for(what, script, run, want_at_least=1):
    w = FlagWatcher()
    sess = corky_main.Session(w, hal.DevButtons(script), None,
                              animate=False, on_device=False)
    try:
        run(sess)
    except hal.ScriptExhausted:
        pass
    if len(w.flags) < want_at_least:
        bad(f"{what}: painted {len(w.flags)} frames, expected at least "
            f"{want_at_least}. The check did not reach the screen it names.")
    elif not all(w.flags):
        bad(f"{what}: {w.flags.count(False)} of {len(w.flags)} frames were "
            "NOT marked sensitive, so DevDisplay wrote key material to disk")
    else:
        ok(f"{what}: all {len(w.flags)} frames marked sensitive")


# The real caller passes no secret=, so neither does this.
flags_for("typing a key on the grid", "a" * 30,
          lambda s: s._text_entry("MASTER  PRIVATE  KEY", "xprv"), 20)

flags_for("the paper backup pages", "aaa",
          lambda s: s._show_backup(KEY, LABEL), 3)

# A full page typed, then committed, so the VERDICT is reached. Without
# this the script never leaves the entry screen, which is the bug above.
_to_verdict = text_keys("xprv", PAGES[0]) + "a"
flags_for("the check entry and its verdict", _to_verdict,
          lambda s: s._check_page(LABEL, 0, 3, PAGES[0]),
          len(_to_verdict) - 5)


# The camera viewfinder is a screen that can show a key too, because a key
# scan points a lens at one. It was NOT marked until audit A2.
#
# Only the VIEWFINDER frames are checked, not every frame the flow paints.
# The warning screen and the "importing into Core" screen carry no key and
# are correctly unmarked; demanding otherwise was this check's first
# mistake. screens.scanning is tagged so its frames can be told apart.

class OneFrameQr:
    last_image = "a photograph of a key QR"

    def strings(self):
        yield None
        yield "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy"


class ViewfinderWatcher:
    width, height = 320, 240

    def __init__(self):
        self.viewfinder_flags = []

    def show(self, image, sensitive=False):
        if getattr(image, "_is_viewfinder", False):
            self.viewfinder_flags.append(sensitive)


watcher = ViewfinderWatcher()
sess = corky_main.Session(watcher, hal.DevButtons("a" * 6), None,
                          animate=False, on_device=False)
sess.qr = OneFrameQr()
real_scanning = screens.scanning


def _tagged_scanning(w, h, *a, **k):
    img = real_scanning(w, h, None, "x", 0.0)
    img._is_viewfinder = True
    return img


screens.scanning = _tagged_scanning
try:
    sess._keymaterial("key")          # the REAL caller, not _scan_until
except Exception:                                  # noqa: BLE001
    pass
finally:
    screens.scanning = real_scanning

if not watcher.viewfinder_flags:
    bad("the key viewfinder: painted nothing, so this proves nothing")
elif not all(watcher.viewfinder_flags):
    bad(f"the key viewfinder: {watcher.viewfinder_flags.count(False)} of "
        f"{len(watcher.viewfinder_flags)} frames unmarked. Scanning a key "
        "writes a photograph of it to disk.")
else:
    ok(f"the key viewfinder: all {len(watcher.viewfinder_flags)} frames "
       "marked sensitive")

# ---- Core's verdict reaches the screen ---------------------------------
# The pages already matched character for character by the time this runs,
# so the UI cannot produce a disagreement and no end-to-end session can
# reach the refusal. The wiring is still worth pinning: a guard whose
# false branch is unreachable through the UI is exactly the kind that
# rots. Audit A6 (2026-09-06) deleted the whole comparison and every suite
# stayed green.
#
# signer.opens_wallet has its own real check against a real node in
# session K9. What is under test HERE is only that its answer changes what
# the panel says.
real_opens = signer.opens_wallet
for verdict, want_text, why in (
        (True, "your paper opens\nkey 73C5DA0A", "agrees"),
        (False, None, "refuses")):
    sess = session("a")
    signer.opens_wallet = lambda *a, _v=verdict, **k: _v
    try:
        got = sess._confirm_typed_key(KEY, "corky-73c5da0a", "73c5da0a")
    except hal.ScriptExhausted:
        got = "ran out of presses"
    finally:
        signer.opens_wallet = real_opens
    if got is not (verdict is True):
        bad(f"Core {why}, but _confirm_typed_key returned {got!r}")
    elif verdict and not drew(sess, screens.verified(320, 240, want_text)):
        bad("Core agreed and the panel never said the paper opens the key")
    elif not verdict and not drew(sess, screens.result(
            320, 240, ok=False, detail="that key does not open this wallet")):
        bad("Core refused and the panel did not say so")
    else:
        ok(f"Core {why} and the panel says so")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
