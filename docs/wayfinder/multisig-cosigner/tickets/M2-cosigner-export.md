# M2 How does the cosigner key leave the device?

Type: `wayfinder:grilling`, HITL. **Blocked by M1.**

## Question

A coordinator needs `[xfp/48h/coin'/0h/script']tpub…` to put Corky in a
quorum. Charting proved Core will produce exactly that, via the scratch
wallet round trip `write_watch_only` already uses.

What is undecided is the shape of it on the device:

- **Is the cosigner branch a fifth row in the existing export menu**,
  beside Native segwit / Taproot / Nested segwit / Legacy? It is not a
  script policy in the same sense: it produces no addresses on its own.
  Putting it in the same list may be the honest simplification or a
  category error on a screen.
- **Which of the three export routes carry it?** QR, text to type,
  wallet file. The string is about 120 characters, so all three are
  possible where the quorum descriptor was not.
- **Does the screen say what it is for?** "This is one key of a quorum.
  It is useless on its own" is a different message from the single-sig
  export, which is a wallet a coordinator can watch immediately.

Depends on M1 because the number of script types decides whether this is
one row or several.
