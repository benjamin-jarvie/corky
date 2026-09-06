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

---

## Answer (2026-09-06), partial: the software half

The ticket is HITL and the physical half needs Ben. What follows is
everything that could be made to happen without his hands, done, plus a
precise statement of what could not and why.

### The finding: a node that is slow rather than dead froze the device for ever

Absent bitcoind fails fast, so every suite covered that. The middle case
had no test and no guard. `signer.Rpc.call` ended in:

```python
out = subprocess.run(cmd, capture_output=True, text=True, input=feed)
```

**No timeout at all.** Measured, not reasoned: `SIGSTOP` on a live
regtest node, which leaves it listening and answering nothing, and the
call had still not returned after **45 seconds** with nothing that would
ever make it. On the device that is a frozen busy screen, no way out, no
shell to fix it from, and the only recovery is pulling the power.

`RPC_TIMEOUT = 120.0` now bounds every call and `TimeoutExpired` becomes
a `RuntimeError`, which is what `Session.HANDLED` catches, so the panel
gets a message it can dismiss. Re-measured with the same `SIGSTOP`: the
call gives up and the error names the node.

**The cap comes from a measurement, not a guess** (rule 6). Run on the
board on 2026-09-06:

```
session open: importdescriptors (s): 4.4
build+review+sign stress PSBT (s): 1.5   (60 inputs)
```

120s is 27x the slowest of those, so it cannot fire on a healthy node
doing real work. The test asserts that too: it fails if anyone tightens
`RPC_TIMEOUT` below 60s, because a guard that refuses real work is worse
than no guard.

`tests/test_property.py` pins it with a fake `bitcoin-cli` that sleeps.
Removing the timeout fails the suite.

### The rest of the list

| case | what happened |
|---|---|
| a node slow rather than dead | **was a permanent freeze; now a dismissible error** |
| a card that mounts read-only | `PermissionError`, contained. Covered by A3's attack 7 |
| a stick pulled mid-write | the write now refuses a short write rather than reporting success (A3). The `flush` claim still needs a real pull |
| a button that bounces | covered by A1's stuck-key work and `tests/test_buttons.py` |
| a camera returning out-of-focus frames | the scan counts and skips codes it cannot read and says so on screen; the no-progress timeout ends it |
| a panel connected but blank | **not testable without eyes on the board** |

### What still needs Ben, precisely

1. **A stick pulled while a signed transaction is being written.** The
   mount unit passes `flush`, which is the claim that a stick pulled
   straight after the file appears still carries it. Nothing in software
   can test that: it needs a hand on a stick at the right moment.
   Everything up to the pull is now covered, including the case where the
   medium fills mid-write.
2. **A panel connected but blank.** Only eyes can tell a blank panel from
   a panel showing a black screen.
3. **A camera out of focus at a real coordinator.** `tests/m1` has the
   two legibility rigs for this and they need a lens and a screen.

None of the three blocks the other tickets. All three belong with A10,
which already needs Ben, a phone and the Sparrow laptop.
