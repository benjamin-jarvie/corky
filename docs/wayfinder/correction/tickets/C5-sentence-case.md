# C5 Sentence case on every screen the device draws

Type: `wayfinder:task`, AFK. **Blocks C6.**
Unclaimed.

## Question

Ben, 2026-09-19: "ensure the sentences start with capital letters for
any disclaimers or text we show."

The device's copy is mostly lower case today, and deliberately so at the
time: "write this down. it opens the wallet", "your paper opens key
73C5DA0A", "that is not a valid key, check what you typed". Titles are
upper case and stay that way; this is about the sentences underneath
them.

The work:

1. Every string the device draws as a sentence starts with a capital.
   Titles, button labels and the character grid are not sentences and do
   not change.
2. The rule goes somewhere durable, so the next screen written follows
   it without being told. `CONTEXT.md` fixes the vocabulary and is the
   candidate.
3. A check enforces it, or it drifts. `tests/test_screen_fit.py` already
   captures every string every screen draws, which is the seam: a
   captured string that begins with a lower-case letter and contains a
   space is a sentence that broke the rule.

Point 3 is what makes this a task worth doing once rather than a tidy-up
that comes undone. Without it this ticket is re-opened in a month.

## Care

`docs/` is prose for people and already reads as prose. This is the
device's panel, not the documents.
