# D4 What the descriptor screen calls itself

Type: `wayfinder:grilling`, HITL. Unblocked.

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
