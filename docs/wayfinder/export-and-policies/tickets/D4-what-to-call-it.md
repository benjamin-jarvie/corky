# D4 What the descriptor screen calls itself

Type: `wayfinder:grilling`. **Closed 2026-09-05.**

## Question

Ben: "the descriptor - which says public key 1/4 - is this just the public
key though?"

No. The screen holds Core's output descriptor: the script type, the origin
fingerprint, the derivation path, an extended public key, and a checksum.
The QR carries the same string. "PUBLIC KEY" is what people call an xpub
export, which is why it was chosen, and it is not what is on the screen.

Same question as the paper backup's naming, which Ben already settled by
rejecting both "xprv" and "master seed": say the true thing in words
people know. Decide what this screen is called, and what one line under it
says the coordinator is being given.

**Closed 2026-09-05.**

## What it actually holds

Core's output descriptor: `wpkh([73c5da0a/84h/0h/0h]xpub…/0/*)#checksum`.
That is a script type, a master fingerprint, a derivation path, an
extended public key, and a checksum. Calling it "PUBLIC KEY" is what
people say when they mean an xpub export, and Ben was right that it is not
what is on the screen.

## Decision

**The screens name the policy, and say plainly what the string is and what
it is not.**

- The QR: `NATIVE SEGWIT` in the letterbox, which is already shipped.
- The text pages: title `NATIVE SEGWIT · PART 1/4`, footer
  `your public key and where it sits. no private key here`.
- The row on the key menu stays **Export public key**, because that is
  what the user is trying to do and it is the phrase every coordinator
  uses for it.

The precise word, "output descriptor", belongs in the README where there
is room to explain it. On a 320x240 panel the footer earns its space by
answering the question a careful person asks at that screen, which is
whether they are about to hand someone their key.

Same principle as the paper backup naming Ben settled: say the true thing
in words people already know, and keep the exact token for the docs.
