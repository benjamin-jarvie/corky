"""If a screen has content past its edge, it says so.

Map ticket D3, in Ben's words: "We need the scroll bar if you can scroll
for any screen you can scroll." The rule was written, `screens.scrollbar`
was built, four screens were given one, and NOTHING checked. The two-axis
review found the gap: the ticket had said the shape of the fix was "a test
that walks every screen with more content than fits and fails if it draws
no indicator", and that test did not exist. `screens.review` had no bar at
all, which is the screen a transaction is signed from.

The suite has two halves and the second is the one that lasts:

1. Every screen listed below is rendered holding more than it shows, and
   must draw the indicator on its right edge.
2. The list must COVER every screen that can scroll. A screen can scroll
   when it takes `pages` or `index`, so the second half reads those
   signatures out of `screens` and fails if one is missing from the list.
   That is what stops the next scrollable screen shipping bare.

Run: python3 tests/test_scroll.py (no bitcoind needed)
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import screens                          # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


ADDR = "bc1q6rz28mcfaxtmd6v789l9rrlrusdprr9pz3cppk"
KEY = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ss"
       "vpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")
DESC = "wpkh([73c5da0a/84h/0h/0h]xpub6" + "A" * 90 + "/0/*)#aaaaaaaa"

#: Each entry renders the screen holding MORE than one screenful, plus
#: what kind of bar it should be: "bounded" when the end is known,
#: "endless" when pressing down goes on for ever.
SCROLLABLE = {
    "menu (via keys_menu)": (
        lambda w, h: screens.keys_menu(
            w, h, [(f"k{i}", f"{i:08x}") for i in range(8)], 5), "bounded"),
    "leak_report": (
        lambda w, h: screens.leak_report(
            w, h, [(f"thing {i}", "off", "normal") for i in range(20)], 9),
        "bounded"),
    "address_page, browsing": (
        lambda w, h: screens.address_page(w, h, 7, ADDR, "wpkh"), "endless"),
    "address_page, the three after an export": (
        lambda w, h: screens.address_page(w, h, 1, ADDR, "wpkh", total=3),
        "bounded"),
    "export_text": (
        lambda w, h: screens.export_text(
            w, h, screens.text_pages(DESC)[0], page=1,
            pages=len(screens.text_pages(DESC))), "bounded"),
    "backup_page": (
        lambda w, h: screens.backup_page(
            w, h, screens.text_pages(KEY)[1], "KEY 73C5DA0A",
            page=1, pages=3), "bounded"),
    "check_result": (
        lambda w, h: screens.check_result(
            w, h, screens.text_pages(KEY)[0], {3}, "KEY 73C5DA0A",
            page=1, pages=3), "bounded"),
    "review": (
        lambda w, h: screens.review(
            w, h, [(f"{ADDR}{i}", 1.0) for i in range(6)], 0.0001, page=1),
        "bounded"),
}


def _bar(img):
    """The scrollbar's thumb and track, read off the right-hand edge."""
    gold = tuple(int(screens.OCHRE[i:i + 2], 16) for i in (1, 3, 5))
    track = (0x3A, 0x35, 0x2E)
    px = img.load()
    thumb, rail = [], []
    for y in range(img.height):
        for x in range(img.width - 6, img.width):
            if px[x, y] == gold:
                thumb.append(y)
                break
            if px[x, y] == track:
                rail.append(y)
                break
    return thumb, rail


# --- 1. every screen that holds more than it shows draws the bar --------

for w, h in ((320, 240), (240, 240)):
    for name, (render, kind) in SCROLLABLE.items():
        thumb, rail = _bar(render(w, h))
        if not thumb:
            bad(f"{w}x{h} {name}: scrolls, and draws no bar")
            continue
        if not rail:
            bad(f"{w}x{h} {name}: a thumb with no track behind it")
            continue
        # The endless kind never reaches the bottom of its track; the
        # bounded kind is free to. A bar that claimed to know the length
        # of an endless list would be a lie told in pixels (D3).
        reaches_end = max(thumb) >= max(rail + thumb) - 1
        if kind == "endless" and reaches_end:
            bad(f"{w}x{h} {name}: the endless bar reaches the bottom, "
                "which tells the user the list ends")
        else:
            ok(f"{w}x{h} {name}: {kind} bar drawn")


# --- 2. the list above must cover every screen that can scroll ---------
# This is the half that survives the next screen. A screen scrolls when it
# takes `pages` or `index`, so read the signatures rather than trusting
# whoever adds one to remember this file.

covered = " ".join(SCROLLABLE)
missing = []
for name, fn in inspect.getmembers(screens, inspect.isfunction):
    if name.startswith("_"):
        continue
    params = inspect.signature(fn).parameters
    if not ({"pages", "index"} & set(params)):
        continue
    if name not in covered:
        missing.append(name)
if missing:
    bad(f"these screens take pages or index and are not checked here: "
        f"{sorted(missing)}. Give each one a scrollbar and add it above.")
else:
    ok("every screen that takes pages or index is checked for a bar")

print()
print("FAILED %d" % len(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
