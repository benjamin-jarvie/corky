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
sys.path.insert(0, str(ROOT / "coresigner"))
sys.path.insert(0, str(ROOT / "tests"))
import hal                              # noqa: E402
import main as coresigner_main               # noqa: E402
import screens                          # noqa: E402
import signer                           # noqa: E402
from e2e_keys import (check_keys, commit_presses,  # noqa: E402
                      text_keys)

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


class NoRpc:
    """A node that is never called, but knows which network it is on.

    The typing screens ask, because the 16 characters every master key
    starts with are different on mainnet and everywhere else.
    """

    chain = "regtest"


def session(script):
    return coresigner_main.Session(Frames(), hal.DevButtons(script), NoRpc(),
                              animate=False, on_device=False)


def run_page(script, want):
    sess = session(script)
    try:
        return sess, sess._check_typed(LABEL, want)
    except hal.ScriptExhausted:
        return sess, "ran out of presses"


def drew(sess, image):
    want = image.tobytes()
    return any(f.tobytes() == want for f in sess.display.shown)


PAGES = screens.text_pages(KEY)


# --- 1. a page typed correctly is accepted ------------------------------
# No trailing "a": text_keys walks to the bar and takes CHECK itself, and
# a correct key returns from _check_typed with no verdict in between.

sess, got = run_page(check_keys(PAGES[0]), PAGES[0])
if got != PAGES[0]:
    bad(f"a correctly typed page was not accepted: {got!r}")
else:
    ok("a page typed correctly is accepted, with no screen in the way")

# --- 2. a wrong character is marked, in place, with no verdict screen ----
# Ben, 2026-09-18: CHECK redraws the page with the mistake outlined and
# the cursor on it. The old flow put up a screen that counted the
# mistakes and then made a person find them.

# PAST THE PREFIX. The first 16 characters are prefilled, so they can
# no longer be got wrong, and a check that puts the mistake there is
# checking nothing.
AT = len(signer.TESTNET_PREFIX) + 4
BAD_PAGE = PAGES[0][:AT] + ("2" if PAGES[0][AT] != "2" else "3") + PAGES[0][AT + 1:]

sess, got = run_page(check_keys(PAGES[0], BAD_PAGE), PAGES[0])
if got != "ran out of presses":
    bad(f"a wrong page returned {got!r} instead of asking for a fix")
elif not drew(sess, screens.text_entry(
        320, 240, f"{LABEL}  ·  ALL  {len(PAGES[0])}  TYPED",
        BAD_PAGE, 0, "xprv", 0,
        # actions_sel None: the grid has the focus when the page comes
        # back marked, so neither button is lit (Ben, 2026-09-18).
        actions_sel=None, caret=AT, actions=("ABORT", "CHECK"), wrong={AT},
        want_len=len(PAGES[0]),
        hint=coresigner_main.Session._type_hint(screens.modes("xprv"), 0,
                                                "xprv"))):
    bad("the page was not redrawn with position 5 marked and the "
        "cursor on it")
else:
    ok("a wrong character is outlined in place, cursor already on it")

# A marked page and a clean one must not render the same, or the red
# outline is decoration.
# Both renders carry the SAME caret, so the only difference is the
# outline. Without it the window follows the caret to the end of the
# page and position 5 is not on screen to be marked at all.
if (screens.text_entry(320, 240, "T", PAGES[0], 0, "xprv", 0, caret=AT,
                       wrong={AT}, want_len=48).tobytes()
        == screens.text_entry(320, 240, "T", PAGES[0], 0, "xprv", 0,
                              caret=AT, wrong=set(), want_len=48).tobytes()):
    bad("a page with a mistake renders identically to a clean one")
else:
    ok("the red outline actually changes what is drawn")

# --- 3. fixing one mistake walks to the next ----------------------------
# The whole point of the jump: three mistakes cost three corrections and
# no hunting.

THREE = (PAGES[0][:3] + "2" + PAGES[0][4:9] + "2" + PAGES[0][10:20]
         + "2" + PAGES[0][21:])
wrong_three = sorted(coresigner_main._wrong_at(THREE, PAGES[0]))
if wrong_three != [3, 9, 20]:
    bad(f"the fixture does not have three mistakes: {wrong_three}")
else:
    caret = wrong_three[0]
    fixed = THREE
    walked = [caret]
    for _ in range(3):
        fixed = fixed[:caret] + PAGES[0][caret] + fixed[caret + 1:]
        caret = coresigner_main._next_gap(fixed, PAGES[0], caret)
        walked.append(caret)
    if fixed != PAGES[0]:
        bad(f"walking the mistakes did not repair the page: {fixed!r}")
    elif walked[:3] != [3, 9, 20]:
        bad(f"the cursor did not walk mistake to mistake: {walked}")
    else:
        ok("fixing walks 3 -> 9 -> 20, one correction each")

# --- 4. a short page is not accepted, and is not accused either --------
# Red marks what you typed wrong. Every position ahead of the caret was
# in that set until 2026-09-18, so a page eight characters in drew forty
# red boxes: the screen said "forty mistakes" to a person who had made
# none. Whether the page is FINISHED is a question about its length.

short = PAGES[0][:20]
if coresigner_main._wrong_at(short, PAGES[0]):
    bad("a page still being typed is marked wrong where it is not typed")
else:
    ok("a page still being typed carries no red marks ahead of the caret")

# Typed short, then CHECK. Running out of presses is the proof it did
# NOT return: an accepted page returns the string and stops reading.
_sess, got = run_page(text_keys("xprv", short) + "a", PAGES[0])
if got != "ran out of presses":
    bad(f"a page that stops 28 characters early was accepted: {got!r}")
else:
    ok("a page that stops early is still not accepted")

# --- 5. the caret keys ON the grid move the caret --------------------
# SeedSigner puts cursor-left, cursor-right and backspace on the keyboard
# itself (map typing, T1), so there is no mode to find. Ours needs two,
# because B already deletes. Ben could not move the caret at all before:
# it lived behind a C nothing mentioned.

_CELLS = screens.mode_cells(screens.modes("xprv")[0][1])
_LEFT = _CELLS.index(screens.CARET_LEFT)


def _walk(cur, target):
    """Presses that move the grid cursor from one cell to another."""
    seen, queue = {cur: ""}, [cur]
    while queue:
        at = queue.pop(0)
        if at == target:
            return seen[at]
        for k in ("u", "d", "l", "r"):
            nxt = coresigner_main._cell_move(k, _CELLS, at)
            if nxt not in seen:                 # a move that does not move
                seen[nxt] = seen[at] + k        # is never put in the route
                queue.append(nxt)
    raise AssertionError(f"no route to cell {target}")


def _to_bar(cur):
    """Presses that take the cursor off the bottom of the grid, to the bar."""
    at, downs = cur, 1
    while coresigner_main._cell_move("d", _CELLS, at) != at:
        at = coresigner_main._cell_move("d", _CELLS, at)
        downs += 1
    return "d" * downs


sess = session(_walk(0, _LEFT) + "aa" + "b" + _to_bar(_LEFT) + "a")
typed, caret = sess._check_entry(LABEL, PAGES[0], "abcde", 5)
if typed != "abde":
    bad(f"the caret keys did not move the caret: typed is {typed!r}, "
        "expected 'abde' after two lefts and a delete")
else:
    ok("the caret keys walk the typed text, and B deletes at the caret")

# --- 6. ABORT is reachable by going DOWN, and the d-pad loops ----------
# Ben, on the board (2026-09-11): "If you can't get to abort, remove the
# button or make sure you can go down and left and actually get to the
# button." DOWN off the bottom row now lands on the bar, and DOWN again
# returns to the top of the grid.

sess = session(_to_bar(0) + "la")
typed, _ = sess._check_entry(LABEL, PAGES[0], "", 0)
if typed is None:
    ok(f"DOWN x{len(_to_bar(0))} reaches the bar, then L and A abort")
else:
    bad(f"DOWN then L then A returned {typed!r}; the buttons under the "
        "grid are not reachable by going down")

sess = session(_to_bar(0) + "d" + _to_bar(0) + "la")
typed, _ = sess._check_entry(LABEL, PAGES[0], "", 0)
if typed is None:
    ok("DOWN from the bar loops to the top of the grid, and round again")
else:
    bad(f"the d-pad did not loop through the bar; got {typed!r}")

sess = session("b")
typed, _ = sess._check_entry(LABEL, PAGES[0], "", 0)
if typed is not None:
    bad("B with nothing typed did not leave the check entry")
else:
    ok("B with nothing typed leaves, the way B leaves everywhere else")

# --- 6b. the case toggle keeps the letter you were on ------------------
# Ben, on the board, 2026-09-18: "Should the numbers be after the
# characters so when going to and fro the capitals and normal letters,
# we are closer to where we were on the alphabet?" They moved, and the
# cursor lands on the same letter rather than near it.

_UP = screens.mode_cells(screens.modes("xprv")[1][1])
for _ch in "apz":
    _at = _CELLS.index(_ch)
    _to = _UP[coresigner_main._same_cell(_CELLS, _at, _UP)]
    if _to != _ch.upper():
        bad(f"C from {_ch!r} landed on {_to!r}, not {_ch.upper()!r}")
        break
else:
    ok("C carries the cursor to the same letter in the other case")

for _ch in (screens.CARET_LEFT, screens.CARET_RIGHT):
    _at = _CELLS.index(_ch)
    if _UP[coresigner_main._same_cell(_CELLS, _at, _UP)] != _ch:
        bad(f"C moved the cursor off the {_ch!r} key")
        break
else:
    ok("and leaves the caret keys where they are, which are in both")

_five = _CELLS.index("5")
if coresigner_main._same_cell(_CELLS, _five, _UP) == 0:
    ok("a digit has no other case, so C starts at the first capital")
else:
    bad("C from a digit lands somewhere with no relation to the digit")

# --- 6c. Core's refusal, in words a person can act on ------------------
# What Ben read on the board (2026-09-18), cut at sixty characters with
# the verdict still to come:
#   "getdescriptorinfo: error code: -5 error message: pkh(): key"

CORE_SAID = ("getdescriptorinfo: error code: -5\n\nerror message:\n"
             "pkh(): key 'tprv8ZgxMBicQKsPe5YM' is not valid")
said = coresigner_main.Session._core_says(RuntimeError(CORE_SAID))
if "not a valid key" in said and "pkh" not in said and len(said) < 60:
    ok(f"a refused key reads as {said!r}")
else:
    bad(f"a refused key still reads as Core's own jargon: {said!r}")

other = coresigner_main.Session._core_says(
    RuntimeError("loadwallet: error code: -4\n\nerror message:\n"
                 "Wallet file verification failed."))
if other == "Wallet file verification failed.":
    ok("and any other refusal keeps Core's own last line")
else:
    bad(f"an unrelated Core error was mangled: {other!r}")

# --- 6d. a refused key reopens the grid holding what was typed ---------
# Core refused Ben's key on the board (2026-09-18) and the screen threw
# all 111 characters away, so one wrong character cost the whole key
# again. The proof is that the SECOND attempt carries the same string
# with no typing presses between the two.

TRIES = []


def _refuse_once(_rpc, text):
    TRIES.append(text)
    if len(TRIES) == 1:
        raise RuntimeError("getdescriptorinfo: error code: -5\n\n"
                           "error message:\npkh(): key 'x' is not valid")
    return signer.WALLET


# The grid opens holding the prefix, so the person types what follows.
TAIL = "e5YMU9gH"
TYPED = signer.TESTNET_PREFIX + TAIL
_real_open = signer.open_session_xprv
signer.open_session_xprv = _refuse_once
try:
    sess = session(text_keys("xprv", TAIL)       # type it, then DONE
                   + "a"                         # dismiss FAILED
                   + commit_presses("xprv", 0, 0))   # DONE again, as-is
    sess._key_xprv_typed()
finally:
    signer.open_session_xprv = _real_open

if TRIES == [TYPED, TYPED]:
    ok("a refused key comes back typed, and DONE alone sends it again")
else:
    bad(f"the second attempt sent {TRIES[1:]!r}, not the key already "
        "typed. A refusal costs all 111 characters again")

# --- 6e. every box of the key is reachable by typing -------------------
# THE CHECK THAT SHOULD HAVE BEEN WRITTEN FIRST. Ben reported this three
# times: "I can not even re-enter all of the words" (2026-09-18), then
# twice on 2026-09-19. Two real defects were found and fixed on the way
# and neither was this one, because each was found by reading the loop
# and reasoning, and this is only visible by typing a key the way a
# person types one: with a mistake in it.
#
# The check took one 48-character page at a time and would not leave a
# page until every character matched, so one capital typed in lower case
# pinned a person on boxes 1 to 12 for ever. This suite typed every page
# PERFECTLY, so it never saw the wall.

KEY_BOXES = screens._groups(KEY)
boxes_seen = set()
_real_entry = screens.text_entry


def _spy(w, h, title, text, cursor=0, charset="xprv", mode=0, secret=False,
         actions_sel=None, caret=None, hint=None, actions=("CANCEL", "DONE"),
         wrong=(), want_len=None, first_box=1):
    count = -(-max(want_len or 0, len(text)) // 4)
    boxes_seen.update(range(first_box, first_box + count))
    return _real_entry(w, h, title, text, cursor, charset, mode, secret,
                       actions_sel, caret, hint, actions, wrong, want_len,
                       first_box)


# One capital typed in lower case, early, exactly what Ben did. Then the
# whole rest of the key. Every box has to be reachable anyway.
WRONG_AT = next(n for n, c in enumerate(KEY)
                if c.isupper() and n >= len(signer.TESTNET_PREFIX))
MISTYPED = KEY[:WRONG_AT] + KEY[WRONG_AT].lower() + KEY[WRONG_AT + 1:]

screens.text_entry = _spy
try:
    sess = session(check_keys(KEY, MISTYPED) + "b")
    try:
        sess._check_typed(LABEL, KEY)
    except hal.ScriptExhausted:
        pass
finally:
    screens.text_entry = _real_entry

want_boxes = set(range(1, len(KEY_BOXES) + 1))
if boxes_seen == want_boxes:
    ok(f"a key typed with one capital in lower case still reaches all "
       f"{len(KEY_BOXES)} boxes")
elif boxes_seen:
    bad(f"typing reached boxes {min(boxes_seen)} to {max(boxes_seen)} of "
        f"{len(KEY_BOXES)}. One wrong character early stops the rest of "
        "the key being entered at all.")
else:
    bad("no boxes were drawn at all")

# And box N holds the Nth four characters of the key, which is what a
# person is matching against their paper.
for n in (1, 13, len(KEY_BOXES)):
    if KEY_BOXES[n - 1] != KEY[(n - 1) * 4:n * 4]:
        bad(f"box {n} does not hold characters {(n-1)*4+1} to {n*4}")
        break
else:
    ok("and box N holds the Nth four characters of the key")

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
    sess = coresigner_main.Session(w, hal.DevButtons(script), None,
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

# A full page typed, then committed, so every frame of a real page is
# counted. Without the commit the script never leaves the entry screen.
_a_page = check_keys(PAGES[0])
flags_for("the check entry", _a_page,
          lambda s: s._check_typed(LABEL, PAGES[0]),
          len(_a_page) - 5)


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
sess = coresigner_main.Session(watcher, hal.DevButtons("a" * 6), None,
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
        got = sess._confirm_typed_key(KEY, "coresigner-73c5da0a", "73c5da0a")
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
