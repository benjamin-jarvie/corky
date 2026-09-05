# D3 One scrolling rule for the whole device

Type: `wayfinder:prototype`. **Closed 2026-09-05.**

## Question

Ben: "If there is more than one thing to display that's not within the
window, we need the scroll bar. For example, when seeing addresses from
Core with that key, it shows receive 0 and native segwit but it's not
intuitive that I can press down and see addresses. We need the scroll bar
if you can scroll for any screen you can scroll."

`screens._menu` already draws a scroll bar, so every list menu has one.
`_page_addresses`, `export_text`, `backup_page` and `check_result` do not,
and the addresses screen gives no sign that DOWN shows more.

Decide the rule, once, for the device:
- what the indicator looks like on a screen that is not a list;
- whether a screen with a known end (three addresses) and a screen with no
  end (browsing addresses forever) show the same thing;
- what it does at the ends.

Then make it structural, so a new scrollable screen cannot ship without
one. A test that walks every screen with more content than fits and fails
if it draws no indicator is the shape.

**Closed 2026-09-05.**

## Decision

**If a screen has content past its edge, it shows a scrollbar, in the same
place and the same shape on every screen.** `screens._menu` already draws
one down the right-hand edge; that geometry becomes a shared helper and
every scrollable screen calls it.

Ben: "it shows receive 0 and native segwit but it's not intuitive that I
can press down and see addresses. We need the scroll bar if you can scroll
for any screen you can scroll."

## The two cases, and they look different on purpose

- **Known end.** A menu of four rows, three addresses at the end of an
  export, three pages of a paper backup. The bar's thumb is sized to the
  fraction visible and positioned by index, exactly as `_menu` does now.
- **No end.** Browsing receiving addresses goes on for as long as you
  press down. There is no total to size a thumb against, so the indicator
  is a fixed-height thumb that moves and never reaches the bottom, plus
  the index already in the title. A bar that pretends to know the length
  of an endless list is a lie told in pixels.

## Making it structural

A rule that lives in four call sites drifts. `tests/test_scroll.py` walks
every screen that can hold more than it shows, renders it at both panel
sizes, and fails if the right-hand edge has no indicator. A new scrollable
screen cannot ship without one, which is the same trick
`tests/test_menu_wiring.py` plays on menu rows.
