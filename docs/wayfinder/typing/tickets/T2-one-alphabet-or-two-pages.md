# T2 One alphabet with a toggle, or two pages?

Type: `wayfinder:grilling`, HITL. **Blocked by T1. Blocks T3.**

## Question

The alphabet is base58: `123456789abcdefghijkmnopqrstuvwxyz` and the
uppercase set, 58 characters, laid out 8 by 4 so it takes two pages.

Ben asked for a case button instead. That is one decision with several
consequences, and T1 brings the evidence:

- A toggle means one page of 32ish and a button that changes what the
  grid shows. Fewer presses to cross the alphabet, one more concept.
- Two pages means no modes, and a page turn in the middle of the
  alphabet that a person has to discover.
- **The descriptor charset is 70 characters**, not 58, and includes
  `()[]'/*#`. A case toggle does not obviously help it, and whatever is
  chosen has to hold it or the two screens diverge again.

Decide the alphabet and its layout. T3 builds whatever this settles.

## Answer, 2026-09-18. Ben's call: two modes, one button.

    digits + lowercase   34 characters, a 9x4 grid (36 cells)
    uppercase            24 characters
    C toggles between them, one press, cursor unmoved

**Nine columns, not a fifth row.** Four rows end at 0.83 of the panel
and the action bar starts at 0.887, so a fifth row does not fit without
shrinking every cell. Nine columns hold 36 where eight hold 32, which
takes 34 with no vertical change at all.

**C is free because of T3.** It is the focus-cycler today, and the flat
cursor removes the thing it cycles into. The button that made the screen
confusing becomes the one that makes it quick, which is SeedSigner's
KEY1 on the same hardware (T1).

**Only uppercase costs a switch.** Three modes would have been closer to
SeedSigner, and digits are scattered all through an xprv, so every digit
would cost a switch and a switch back.

`tests/test_ui_cost.py` searches the shortest route, so T3 reports what a
whole key actually costs rather than estimating it.

### Still open

The descriptor charset is 69 characters including `()[]'/*#`, and a case
toggle does not obviously divide it. It stays in the map's fog until
somebody types a descriptor in anger.
