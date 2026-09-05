# D6 A restored key has fewer policies than the key it restores

Type: `wayfinder:grilling`, HITL. Unblocked. Related: D1.

## Question

Found while building T0, and it is a hazard rather than a preference.

- A key **Core generates** carries four policies: `pkh`, `sh(wpkh)`,
  `wpkh`, `tr`. `createwallet` makes them all.
- A key that **arrives by scan or by typing** carries two.
  `signer.build_descriptors` builds BIP84 and BIP86 and nothing else,
  because `PURPOSES` is `(84, 86)`.

So generating a key on Corky, writing the paper backup, and later
restoring that same paper into Corky gives a wallet that presents **two of
the four policies the key actually controls**. Coins sent to a legacy or
nested segwit address of that key are still the key's, and another Bitcoin
Core would find and spend them, but Corky would not show them under
Receiving addresses and would not sign for them.

The device no longer crashes on this: `signer.available_kinds` reports what
a key has and the panel offers only that (T0). What is undecided is
whether the asymmetry should exist at all.

To decide:

- Does `build_descriptors` build all four, so an imported key matches a
  generated one?
- If yes, what does it cost? Each wallet was measured at about 3MB and the
  board has 512MB with five slots. Doubling the descriptor count needs a
  number, not a guess, and `m0/m0_gate.py` is where that number comes from.
- If no, what does the panel say, so a user restoring a paper backup is
  not silently shown half their wallet?
- Does the answer change for a key that arrives as a **descriptor** rather
  than an xprv? `open_session_descriptors` imports exactly what it is
  given, so a two-descriptor QR makes a two-policy wallet by definition.
