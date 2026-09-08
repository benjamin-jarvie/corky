"""The row you press must be the thing that happens.

Corky's menus are a list of labels in `screens.py` and an `if selected ==
N` cascade in `main.py`. Nothing joined the two, so on 2026-09-05 the
BACKUP menu drew "On paper" as row 0 and ran the FILE backup for it.
Choosing paper asked for an encryption passphrase, which is the "back
button does nothing on backup to paper" Ben reported from the board. The
screens rendered correctly and every suite was green, because no test ever
asked which handler a labelled row runs.

This suite drives the real `_pick` loop with a scripted keypad, and asserts
the handler that ran is the one the label names. It needs no bitcoind and
no panel: every handler is replaced by a recorder.

Run: python3 tests/test_menu_wiring.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import hal                          # noqa: E402
import main as corky_main           # noqa: E402
import screens                      # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


class NullDisplay:
    width, height = 320, 240

    def show(self, image, sensitive=False):
        pass


class NullRpc:
    chain = "regtest"
    wallet_dir = Path("/nonexistent")

    def call(self, method, *params, **kw):
        # Enough shape for the menus to render. A key presenting all four
        # policies is what every key presents since map ticket D6.
        if method == "listdescriptors":
            return {"descriptors": [
                {"desc": f"{fn}([73c5da0a/{n}h/0h/0h]xpub6/0/*)#aaaaaaaa",
                 "active": True, "internal": False}
                for fn, n in (("wpkh", 84), ("tr", 86),
                              ("sh(wpkh", 49), ("pkh", 44))]}
        return ""


def session(script):
    return corky_main.Session(NullDisplay(), hal.DevButtons(script),
                              NullRpc(), animate=False, on_device=False)


def to_row(n):
    """The presses that choose row n from the top of a list screen."""
    return "d" * n + "a"


def pin(menu, rows, run, expected):
    """Choose every row of one menu in turn; record what each one ran.

    `run(session)` opens the menu and returns the name of the handler that
    fired. `expected` maps each row's label to that name. The trailing B
    leaves the menu, because a menu state repaints and asks again once its
    handler returns.
    """
    for i, (label, _note) in enumerate(rows):
        want = expected[label]
        try:
            got = run(session(to_row(i) + "b"))
        except hal.ScriptExhausted:
            got = "ran out of presses"
        if got == want:
            ok(f"{menu}: '{label}' runs {want}")
        else:
            bad(f"{menu}: '{label}' runs {got}, not {want}")


def recorder(sess, names, into):
    """Replace each named method with one that records being called."""
    for name in names:
        def note(*a, _n=name, **k):
            into.append(_n)
            return True
        setattr(sess, name, note)


# --- 1. the key menu: four rows, four handlers ---------------------------

def run_key_menu(sess):
    ran = []
    recorder(sess, ("_export", "_browse_addresses", "_backup_paper",
                    "_discard"), ran)
    sess.state_key_menu("corky")
    return ran[0] if ran else "nothing"


corky_main.signer.master_fingerprint = lambda *a, **k: "73c5da0a"
pin("KEY", screens.KEY_MENU_OPTIONS, run_key_menu, {
    "Export public key": "_export",
    "Receiving addresses": "_browse_addresses",
    "Backup key": "_backup_paper",
    "Discard key": "_discard",
})


# --- 3. the ways to get a key, in the order the KEYS screen lists them ---

for i, (label, _note) in enumerate(screens.KEYS_ACTIONS):
    s = session("")
    got = []
    recorder(s, ("_tool_generate", "_key_by_scan",
                 "_key_xprv_typed"), got)
    s._load_key(i)
    want = {"New key": "_tool_generate",
            "Scan a key": "_key_by_scan",
            "Type private key": "_key_xprv_typed"}[label]
    if got == [want]:
        ok(f"KEYS: '{label}' runs {want}")
    else:
        bad(f"KEYS: '{label}' runs {got}, not {want}")


# --- 4. how a key leaves: three routes, dispatched by index -------------
# `_export_one` picks with `[qr, text, file][choice]`, which is the exact
# shape TESTING.md rule 11 was written about: a list of labels in screens
# and a positional dispatch in main, with nothing joining them.

def run_export(sess):
    ran = []
    recorder(sess, ("_export_qr", "_export_text", "_export_file"), ran)
    # A finished export goes on to the addresses, which is D2's decision
    # and not this suite's business: what is under test is WHICH route ran.
    sess._page_addresses = lambda *a, **k: None
    sess._export_one("corky", "wpkh")
    return ran[0] if ran else "nothing"


corky_main.signer.export_descriptor = lambda *a, **k: "wpkh(tpubX)#aaaaaaaa"
pin("EXPORT AS", screens.EXPORT_OPTIONS, run_export, {
    "QR code": "_export_qr",
    "Text to type": "_export_text",
    "Wallet file": "_export_file",
})


# --- 5. tools ------------------------------------------------------------

def run_tools(sess):
    ran = []
    recorder(sess, ("_tool_leak_check", "_tool_check_address"), ran)
    sess.state_tools()
    return ran[0] if ran else "nothing"


pin("TOOLS", screens.TOOLS_OPTIONS, run_tools, {
    "Check for leaks": "_tool_leak_check",
    "Check an address": "_tool_check_address",
})


# An EMPTY menu must not crash. _pick divided by count on the first
# d-pad press, and ZeroDivisionError is not in Session.HANDLED, so it
# ended the process instead of painting an error. _export reaches it: a
# wallet imported as a bare descriptor need not hold any of the four
# script policies, and signer.available_kinds says so in its own
# docstring (found reading main.py, 2026-09-07).
sess = corky_main.Session(NullDisplay(), hal.DevButtons("dudua"),
                          rpc=NullRpc())
try:
    got = sess._pick(lambda sel: None, 0)
    ok("an empty menu returns at once instead of dividing by zero") \
        if got is None else bad(f"an empty menu chose row {got}")
except ZeroDivisionError:
    bad("an empty menu still divides by zero, which HANDLED cannot catch "
        "and which therefore ends the process")
except hal.ScriptExhausted:
    bad("_pick waited for input on a menu with no rows")

# And the export flow says so rather than opening that menu.
class NoPolicies:
    chain = "regtest"

    def call(self, method, *a, **k):
        if method == "listdescriptors":
            return {"descriptors": []}
        return ""


class Painted:
    width, height = 320, 240

    def __init__(self):
        self.shown = []

    def show(self, image, sensitive=False):
        self.shown.append(image)


disp2 = Painted()
sess2 = corky_main.Session(disp2, hal.DevButtons("a"), rpc=NoPolicies())
try:
    sess2._export("corky-x")
except ZeroDivisionError:
    bad("_export still reaches the empty menu")
except hal.ScriptExhausted:
    bad("_export opened a menu with no rows and waited for a press")
else:
    # Assert the WORDS, not merely that nothing exploded. With _pick made
    # safe, an unguarded _export returns quietly and the user is dropped
    # back with no idea why, which passed this check until the message
    # was asserted (2026-09-07).
    want = screens.result(320, 240, ok=False,
                          detail="this key has no policies to export",
                          label="FAILED").tobytes()
    if any(f.tobytes() == want for f in disp2.shown):
        ok("a key with no exportable policy is told so, not shown a "
           "blank menu")
    else:
        bad("_export returned silently on a key with no policies; the "
            "user is sent back with nothing said")

# Browsing addresses has the SAME root and a different symptom:
# _page_addresses did order[0] on the tuple available_kinds returned, and
# IndexError is no more catchable by HANDLED than ZeroDivisionError was.
# Fixed alongside the export menu; missed on the first pass through it
# (2026-09-07).
disp3 = Painted()
sess3 = corky_main.Session(disp3, hal.DevButtons("a"), rpc=NoPolicies())
try:
    sess3._browse_addresses("corky-x")
except IndexError:
    bad("_page_addresses still indexes an empty policy list, which ends "
        "the process")
except hal.ScriptExhausted:
    bad("_page_addresses opened a screen for a key with no policies")
else:
    want3 = screens.result(320, 240, ok=False,
                           detail="this key derives no addresses",
                           label="FAILED").tobytes()
    if any(f.tobytes() == want3 for f in disp3.shown):
        ok("a key that derives no addresses says so")
    else:
        bad("_browse_addresses returned silently with nothing on screen")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
