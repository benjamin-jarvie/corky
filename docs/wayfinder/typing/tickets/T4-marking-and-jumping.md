# T4 Mark what is wrong, and walk between the mistakes

Type: `wayfinder:task`, AFK. **Blocked by T3.**

## Question

Ben, 2026-09-18, decided the flow: **no verdict screen when something is
wrong.** CHECK redraws the page with the mistakes marked and the cursor
already on the first one.

1. **A wrong character is drawn with red around it** (Ben's words:
   "show wrong characters with red around their character box").
2. **The cursor starts on the first wrong character.**
3. **Fixing one moves to the next wrong one**, automatically, and says
   so when none are left. A person can still move anywhere by hand.
4. A page that is right shows the verdict screen it shows today: Core
   read what was typed and agrees.

Today's `check_result` screen and its FIX/ABORT bar exist for the case
this removes. Decide whether it survives for the clean case or is
replaced.

## Done when

A page with three mistakes can be walked and fixed without the cursor
being moved by hand, and `tests/test_backup_check.py` proves it by
driving the real loop.
