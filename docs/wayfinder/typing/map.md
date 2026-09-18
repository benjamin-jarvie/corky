# Map: typing 111 characters back in

Label: `wayfinder:map`. Tickets are in `tickets/`, one file each.
Charted 2026-09-18, after Ben tried to check a paper backup on the board
and could not finish.

## Destination

**A person can type 111 characters back in, and fix what they got wrong,
without being told how.**

Every screen where a person types is in scope: checking a paper backup,
typing a key in, typing a descriptor. They are one widget with one set
of traps, and fixing the screen Ben hit would leave the same confusion
waiting in the others.

## What Ben hit, 2026-09-18

Six defects in one sitting, on the first real attempt by anybody:

1. CHECK is not the default on the last backup page. DONE is.
2. The centre press FINISHES the page. With nothing typed, every
   character counts wrong at once.
3. Only A types a character. The centre press should too.
4. Finishing should mean reaching the buttons, not a centre shortcut.
5. The alphabet is 58 characters over two pages with no case toggle.
6. The cursor could not be moved. Correcting anything but the first
   character needed a mode nothing made visible.

A seventh nobody has hit: **typing a key IN** uses the same widget.

## Notes

- **Ben's words for the model, 2026-09-18.** "The chars written should be
  like the ones shown ... show a number and then the box with 4
  characters, so we can easily navigate it." The check screen must look
  like the backup screen, because the person is comparing one to the
  other and a different shape makes them do the mapping in their head.
- **"As efficiently as possible to reduce bloat."** Presses are the
  currency. `tests/test_ui_cost.py` already measures the route.
- This repo carries execution IN the map.
- Skills: `/mp-tdd` for anything built, `/mp-code-review` before it
  lands, `/mp-codebase-design` for anything restructured. `TESTING.md`
  rules 1 to 12a bind every test, and rule 11 twice over: a menu is two
  lists, and so is a document that names a row.
- Every screen here shows key material, so `hal.DevDisplay` blanks the
  frames a scripted session writes. `tests/test_backup_check.py` drives
  the loop in-process for that reason.

## What is already established

Measured, not recalled. No ticket needs to re-derive these.

- **The key is 111 characters.** Three pages of 48, 48 and 15, in
  4-character groups, 3 groups per row, 4 rows per page. 28 groups.
- **The display already uses those groups**, `screens._groups` and
  `GROUPS_PER_ROW = 3`. The check screen does not; it draws a flat echo
  line with a caret, which is the mismatch Ben named.
- **SeedSigner's source is on this machine**, at
  `~/bitcoin-self-custody/emulators/seedsigner`, so its keyboard can be
  read rather than guessed at.
- **The action bar is reachable by DOWN** since 2026-09-11, and the
  d-pad loops through it. That part is not broken.

## Decisions so far

<!-- one line per closed ticket -->

- [T1 How does SeedSigner enter characters?](tickets/T1-how-seedsigner-types.md):
  one alphabet per MODE and never a paged one. Its constructor RAISES if
  a charset will not fit, and the page-turn key it ships is used by no
  screen. A side button switches mode in one press and keeps the cursor
  where it is. Correction keys live on the keyboard itself, so there is
  no hidden mode. Its entry and display screens look nothing like each
  other, which is the one place we should not copy it.
- [T2 One alphabet with a toggle, or two pages?](tickets/T2-one-alphabet-or-two-pages.md):
  two modes on the C button, digits and lowercase on a 9x4 grid,
  uppercase on its own. Nine columns rather than a fifth row, because
  four rows already end at 0.83 and the buttons start at 0.887.

## Not yet specified

- **Box numbering, global or per page.** 1 to 28 across the whole key,
  or 1 to 12 on each page. A coordinator saying "box 8" means nothing
  until this is settled, and it may fall out of whatever the check
  screen ends up looking like.
- **The hint line.** Three hints name the next move, and the moves are
  about to change. What a hint should say when the model is obvious is
  not the same question as what it says today.
- **The descriptor charset.** 70 characters rather than 58, used when
  typing a descriptor in. Whatever the alphabet becomes has to hold it,
  and nobody has looked at whether a case toggle even applies.

## Out of scope

- **A different backup format.** The 111-character xprv stays. PLAN
  A-24, and the map is about typing it, not changing it.
