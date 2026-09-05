# D3 One scrolling rule for the whole device

Type: `wayfinder:prototype`, HITL. Unblocked.

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
