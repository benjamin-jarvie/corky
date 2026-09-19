# C7 Can a skipped character be made impossible?

Type: `wayfinder:grilling`, HITL. **Surfaced by C4. Blocks C6.**
Claimed 2026-09-19. **CLOSED 2026-09-19.**

## Question

Surfaced while prototyping C4, and it is the most likely handwriting
error there is.

If somebody MISSES a character while writing the paper down, their
paper holds 110 characters. Every character after the gap then lands
one position early, so every one of them mismatches. Under C1 that is
about 90 interruptions, and every one of them gives WRONG advice: it
names a character on the paper that is perfectly correct, when the
fault is a gap several boxes earlier.

Three answers were put to Ben: detect the shift by comparing what was
typed against the NEXT character of the key, warn after a run of
corrections, or say nothing and let the final count be the alarm.

He took none of them: "You simply can't have an empty space. Make it
impossible to skip one."

## Answer

**The device cannot forbid a pen error, so it changes what the pen is
copying from. The backup screen numbers its groups, 1 to 28, exactly as
the typing screen does.**

Two things close at once:

1. **A skipped character leaves a box with three characters in it**,
   and the person writing sees that at the moment they do it, not days
   later.
2. **"Box 7, character 3" becomes a glance instead of a count.** The
   interruption names a box; until now the paper had no box numbers on
   it, so acting on that meant counting seven groups along your own
   handwriting.

The second is the one that was quietly broken all along. The typing
screen has numbered boxes and the paper did not, so every message the
device sent about a box was addressed to a numbering the person could
not see.

**This reverses an answer given earlier the same day.** Ben was asked
then how to stop `tprv` reading like a heading and said "leave it as it
is", which was right for that question. This is a different question,
and numbering answers it.

The cost is type size on the page being copied by hand. Measured in C6.

**Rejected:** also telling people to write the numbers down. It is 28
more things to copy, and a short box is visible without them.
