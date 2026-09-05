# N3 Keys persist until the device is turned off

Type: `wayfinder:task`. **Open. The behaviour is already correct; the
proof is missing.**

## Question

Ben: "I think the keys we're wiping after a certain amount of time or was
that you in development removing them? They need to persist unless turned
off essentially."

## The answer to the question as asked

**It was development.** There is no timer. Nothing in `corky/` expires a
key, and no code path drops one on a clock. What Ben saw was test scripts
and probes calling `signer.close_session` and `signer.close_key`
explicitly, which is what they should do.

A key is dropped in exactly three places, all deliberate:

- `signer.close_session`, in the `finally` around `state_home()`, which is
  reached when the user chooses POWER OFF;
- `signer.clear_on_start`, at startup, so a key left by a crashed session
  is never adopted by the next one;
- `signer.close_key`, when the user chooses Discard key.

So a key already survives everything else, including the card coming out,
because the wallets live on the `/run/corky` ramdisk and not on the card.

## What is missing

A test that says so. The whole no-persistence effort pushed one way, and
nothing pins the other direction: that a key stays loaded for as long as
the device is on. A regression that added an idle timeout would pass every
suite in the repo today.

The shape: a scripted session that loads a key, walks away from it through
several screens, comes back, and finds the same fingerprint still loaded
and still able to sign. Plus a static check that no timer or clock touches
the wallet calls.
