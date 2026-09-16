"""Every menu path a document tells a person to press must exist.

docs/CAMERA-TEST.md sent Ben to the board with "Export public key ->
Cosigner (P2WSH)" after that row had been replaced by a Multisig submenu,
and "Advanced -> Type a path..." after Advanced was removed and typed
paths were switched off. Nothing failed. He would have found out standing
at the device with a phone in his hand.

TESTING.md rule 11 says assert the label rather than the index. The same
argument applies one step out: a DOCUMENT that names a row is a second
list, and nothing joined it to the first.

The convention is a code span with arrows:

    `Key → Export public key → Multisig… → Native segwit → QR code`

Every segment must be a row this build actually draws, a home tile, or
one of the placeholders below. Write a menu path any other way and this
check cannot see it, which is the one hole and it is deliberate: a fuzzy
matcher over prose would flag every bold word in the repo.

Run: python3 tests/test_doc_menus.py   (no bitcoind, no hardware)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "coresigner"))
import screens  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    fails.append(m)
    print("FAIL", m)


#: Screens a person navigates to that are not rows in a list: the four
#: home tiles, and the titles of screens reached by choosing a row.
TILES = {"Scan", "Key", "Tools", "Settings"}

#: Stand-ins a document may use where any row of a set would do.
PLACEHOLDERS = {"<a policy>", "<a script type>"}


def known_labels():
    """Every row label this build can draw, from the screens themselves."""
    labels = set(TILES) | set(PLACEHOLDERS)
    for options in (screens.KEY_MENU_OPTIONS, screens.KEYS_ACTIONS,
                    screens.EXPORT_OPTIONS, screens.COSIGNER_OPTIONS,
                    screens.TOOLS_OPTIONS):
        for row in options:
            labels.add(row[0])
    labels.update(screens.SCRIPT_LABELS.values())
    labels.add(screens.MULTISIG_ROW)
    for row in screens.multisig_rows("m/48h", "m/48h", 0):
        labels.add(row[0])
    return labels


LABELS = known_labels()
#: One line, and short. The first version was `([^`]*→[^`]*)` which
#: matched between two backticks far apart in the prose and swallowed
#: four paragraphs because an arrow happened to fall between them.
PATH = re.compile(r"`([^`\n]{0,100}?→[^`\n]{0,100}?)`")

docs = sorted(ROOT.glob("docs/*.md")) + [ROOT / "README.md"]
checked = 0
for doc in docs:
    for span in PATH.findall(doc.read_text()):
        segments = [s.strip() for s in span.split("→")]
        checked += 1
        unknown = [s for s in segments if s and s not in LABELS]
        if unknown:
            bad(f"{doc.name}: {span.strip()[:54]!r} names "
                f"{unknown} which no menu draws")
        else:
            ok(f"{doc.name}: every row in {segments[0]} → … exists")

if not checked:
    bad("no menu paths found in any document; the convention is a code "
        "span with arrows, and this check is now watching nothing")

print(f"\n{checked} menu path(s) checked, {len(fails)} failure(s)")
sys.exit(1 if fails else 0)
