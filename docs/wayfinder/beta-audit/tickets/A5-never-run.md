# A5 What has never run, on anything

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A1, because coverage of an unread module is a number nobody can read.

## Question

TESTING.md rule 3: if a branch exists only for the device, a test must set
the flag and run it. Rule 7: "needs hardware" is a claim that needs
checking.

Find the code that has never executed. Not by reading: by measuring.
Instrument a full suite run and list every function and branch in `corky/`
that no test reaches, then sort them into three piles:

- reachable in a test and simply untested;
- reachable only on the device, and therefore rule 3's problem;
- unreachable at all, and therefore dead.

The third pile is the interesting one. `vulture` finds unused names; it
does not find a live function whose second branch nobody has entered.
