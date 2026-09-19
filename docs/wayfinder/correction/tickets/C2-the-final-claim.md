# C2 What does the last screen claim?

Type: `wayfinder:grilling`, HITL. **Blocked by C1.**
Claimed 2026-09-19. **CLOSED 2026-09-19.**

## Question

Today the flow ends on "your paper opens key 73C5DA0A". Under C1 the
device corrects the typed string as it goes, so after three corrections
that sentence is no longer true: the paper opens the wallet only if the
person went back and fixed it, and the device cannot see whether they
did.

This repo has thrown out two screens for saying something untrue
(`result`'s SIGNED over a watch-only file, 2026-09-05; the verdict
screen that cited `getdescriptorinfo`, 2026-09-07). Decide what this one
is allowed to say.

## Answer

**Say the number, say what is true, and warn about what is not.**

Ben, 2026-09-19: "If any corrections were required, say there was x many
corrections, you may want to check one last time. This key with x
corrections opens x finger print. Warning: if you did not write down
those corrections and test them, you may not be able to recover that key
and funds."

So, with corrections:

    3 CORRECTIONS

    This key, with your 3 corrections, opens 73C5DA0A.

    You may want to check it one more time.

    If you did not write those 3 down and test them, you may not be able
    to recover this key or its funds.

Every claim on it is one the device actually verified. The thing it
cannot verify is named as a warning rather than asserted.

**Zero corrections keeps today's screen** and its wording, which is then
exactly true.

**Rejected in charting:** asking for the corrected characters a second
time to prove the paper was fixed. Honest end to end, and a second pass
on a d-pad. Ben chose the warning.
