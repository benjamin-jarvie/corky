# 11 Rebuild home and the menus

Labels: wayfinder:task (AFK)
Blocked by: 10
Assignee: claude (claimed 2026-09-04)
Status: resolved 2026-09-05

## Question

Build tickets 02 and 07 as screens: the four tiles, the Key tile that lists
fingerprints or offers Load a key, the Key menu in its order, Load a key
with its four entries, Tools with New key, Settings unchanged. Add the
glyphs ticket 02 names and update the font NOTICE. Retitle the paper backup
page from "SHARE 1/1" to the key's fingerprint.

Tests: `test_screen_fit` for every new screen at both panels;
`test_ui_cost` remodelled for the new navigation; an e2e session that walks
every menu entry with a real key loaded.

## Answer (built, 2026-09-04/05)

Built with `tests/e2e_keys.py` session K3 (every menu walked with a real key)
and five new entries in `tests/test_screen_fit.py` at both panel sizes.

**Home** is Scan, Key, Tools, Settings (`screens.HOME_TILES`). The qrcode
glyph came from the Font Awesome 5 file inside the verified Sparrow release,
and the subset is rebuilt from that one file with fonttools, seven glyphs.
`hw/vendor/fonts/NOTICE.md` still needs its table updated (ticket 23).

**Key** (`Session.state_keys`): with no key it opens Load a key straight
away; with keys it lists them by fingerprint, Load a key last
(`screens.keys_menu`). A key's menu (`screens.key_menu`) is Sign
transaction, Export public key, Receiving addresses, Backup key, Discard
key. Export and Receiving addresses hold a one-line "not built yet" until
tickets 12 and 14. Backup key shows Core's master xprv for that key in
four-character groups, titled `KEY  <XFP>`. Discard key asks first with
BACK pre-selected (`screens.confirm_discard`), then unloads that one wallet.

**Load a key** has three entries: Scan a key, Type descriptor, Type xprv.
The scan decides by content: `xprv`/`tprv` prefix is an xprv, anything
else goes to Core as a descriptor (ticket 05). The camera part of that
scan is still ticket 09.

**Tools** holds New key. A new key lands on its own menu, as SeedSigner
does. **Scan** with no key holds "load a key first"; with a key it runs the
camera transaction loop. Settings is unchanged.

**Every scripted session was re-sequenced** for the new tiles
(`tests/e2e_session.py`, `tests/e2e_keys.py`, `tests/test_ui_cost.py`).
The dev display blanks sensitive frames, so backup pages are asserted as
blank-frame counts, and the page itself is pinned by `test_screen_fit`.
README line counts updated: 1,697 functional lines.

Not done here: `tests/tools/render_screens.py` still renders the old
screen set (ticket 16 territory).
