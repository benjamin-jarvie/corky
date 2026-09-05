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
    recorder(s, ("_tool_generate", "_key_by_scan", "_key_xprv_typed",
                 "_key_from_file"), got)
    s._load_key(i)
    want = {"New key": "_tool_generate",
            "Scan a key": "_key_by_scan",
            "Type private key": "_key_xprv_typed"}[label]
    if got == [want]:
        ok(f"KEYS: '{label}' runs {want}")
    else:
        bad(f"KEYS: '{label}' runs {got}, not {want}")


# --- 4. tools ------------------------------------------------------------

def run_tools(sess):
    ran = []
    recorder(sess, ("_tool_leak_check", "_tool_check_address"), ran)
    sess.state_tools()
    return ran[0] if ran else "nothing"


pin("TOOLS", screens.TOOLS_OPTIONS, run_tools, {
    "Check for leaks": "_tool_leak_check",
    "Check an address": "_tool_check_address",
})


print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
