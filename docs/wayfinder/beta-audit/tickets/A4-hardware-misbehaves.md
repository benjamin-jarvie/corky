# A4 What the device does when hardware misbehaves rather than fails

Type: `wayfinder:task`, HITL. **Needs the board.**

**Blocked by:** Nothing, and it needs the board, which is on.

## Question

The suites cover hardware that works and hardware that is absent. The
middle case is untested and it is the one a tester will hit: a camera that
returns frames but out of focus, a stick pulled mid-write, a card that
mounts read-only, a panel that is connected but blank, a button that
bounces, a node that is slow rather than dead.

Ben has the board on. For each, either make it happen or say precisely why
it cannot be made to happen, and record what the device did.

The one that matters most: **a stick pulled while a signed transaction is
being written.** The mount unit uses `flush`, which is a claim that a
stick pulled straight after the file appears still carries it. That claim
has never been tested.
