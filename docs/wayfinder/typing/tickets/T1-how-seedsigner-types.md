# T1 How does SeedSigner enter characters?

Type: `wayfinder:research`, AFK. **Blocks T2.**

## Question

Ben, 2026-09-18: "Look at how seed signer enters chars, is there a upper
case button, rather than two alphabets to navigate."

Core Signer paints 58 base58 characters over two pages of 32 and the
only way between them is paging. SeedSigner has solved the same problem
on the same size panel with the same five buttons, and its source is on
this machine at `~/bitcoin-self-custody/emulators/seedsigner`. Read it
rather than guess.

Answer these, with file and line:

1. What does its keyboard look like: one alphabet with a case or mode
   toggle, or several pages?
2. How does a person move the cursor, and how many presses does one
   character cost?
3. How does it mark and correct a mistake already entered?
4. Does it lay characters out in groups, and does the entry screen
   resemble the display screen?
5. Anything it does that we have not thought of, and anything it
   deliberately does not do.

Facts only. The decision is T2's.

## Answer, 2026-09-18. Read from the source, commit 5a91af0.

`~/bitcoin-self-custody/emulators/seedsigner/.../src/seedsigner/`, origin
`github.com/SeedSigner/seedsigner.git`. Two claims were spot-checked by
hand afterwards because they decide T2.

**1. One alphabet per MODE, never a paged one.** Five `Keyboard` objects
for the passphrase screen (`gui/screens/seed_screens.py:664-673`):
lowercase and uppercase 4x9, digits 3x5, and two symbol sets 4x6. Seed
words use a single 5x6 lowercase grid with no modes at all
(`seed_screens.py:52-64`).

**It refuses to page.** The constructor raises if the charset does not
fit the grid (`gui/keyboard.py:207-208`):

    if rows * cols < len(charset) + additional_key_spaces:
        raise Exception(f"charset will not fit in a {rows}x{cols} layout")

A `KEY_PREVIOUS_PAGE` exists at `keyboard.py:84-89` and **no screen uses
it**. So the thing Core Signer does, SeedSigner built the parts for and
then chose not to do.

**2. Switching is a button, not navigation, and it costs one press.**
KEY1 toggles abc/ABC; KEY2 cycles digits and the two symbol sets
(`seed_screens.py:885-963`). The cursor does not move:
`set_selected_key_indices(x=cur_keyboard.selected_key["x"], y=...)`
copies the position into the incoming keyboard (`:912`, verified). The
button label repaints to name the NEXT mode (`:1036-1043`).

**3. Correction is keys ON the keyboard, not a mode.** `KEY_CURSOR_LEFT`,
`KEY_CURSOR_RIGHT` and `KEY_BACKSPACE` sit on the last row
(`keyboard.py:72-83`, `:262-277`), and backspace deletes AT the cursor
rather than only at the end (`seed_screens.py:996`). You reach them by
navigating to them, so there is no hidden mode and nothing to discover.

**4. Entry and display do NOT resemble each other.** Display groups
seed words in fours with numbers (`views/seed_views.py:1056`); entry is
one word at a time on a grid with a candidate list. Keyboard rows are a
plain slice, `charset[i*cols:(i+1)*cols]` (`keyboard.py:241`), never
grouped.

**This is where Core Signer should NOT copy them.** Ben's whole point is
that our entry screen must look like our display screen, because the
person is comparing paper to panel. SeedSigner does not have that
problem: nobody types a seed word back in against a printed grid.

**5. Cleverer than a plain grid:** after each letter it greys the
letters that cannot continue a valid BIP-39 word
(`seed_screens.py:134-149`), keeping dead keys visible but dim. **Not
applicable here**: every base58 character is valid at every position, so
there is nothing to dim. Vertical moves skip empty slots
(`keyboard.py:341-383`); left and right wrap, up and down do not
(`screens/screen.py:1190`).

**Not found in the source:** any base58 keyboard.
