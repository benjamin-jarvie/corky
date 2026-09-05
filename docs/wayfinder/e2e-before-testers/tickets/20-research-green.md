# 20 Blockstream Green: how it takes a public key and returns a transaction

Labels: wayfinder:research (AFK)
Blocked by: none
Status: resolved 2026-09-04

## Question

The same four questions as ticket 19, for Blockstream Green (mobile and
desktop), from Blockstream's documentation, the Green source on GitHub, and
release notes. Green's watch-only mode for singlesig and its handling of
output descriptors are the points to pin down, and whether Green can hand a
PSBT to any signer other than Jade.

Write the findings to `../research/green.md`, same shape as ticket 19.

## Answer (research, 2026-09-04)

Full findings with 40 quoted sources and ten descriptor constraints:
[research/green.md](../research/green.md).

1. **Descriptor import: yes.** Android, iOS and desktop accept a pasted or
   plain-text-QR `wpkh([fp/84h/0h/0h]xpub/0/*)#checksum` and hand it to gdk
   as `core_descriptors`. gdk requires the origin to be exactly
   `purpose'/coin'/account'`, requires the wildcard, and rejects `<0;1>`
   multipath. Core's form meets all three. Checksum and `h` markers are fine.
2. **Taproot: yes.** gdk 0.75.0 parses `tr([fp/86'/0'/n']xpub/0/*)` as
   p2tr; Android's detector includes `tr(`. iOS and desktop pass the text
   through, verified in source, not run.
3. **PSBT round trip: yes in code, with Jade's name on every label.** Mobile
   shows `ur:crypto-psbt` as an animated QR for any singlesig watch-only
   wallet, desktop only for descriptor-imported ones. The signed PSBT comes
   back by camera as `ur:crypto-psbt` or as a file. Every button says "Scan
   QR with Jade" and mobile shows a Jade-unlock prompt whose skip path is
   unverified.
4. Versions: gdk 0.0.59 (2023-04) descriptor login, 0.73.0 (2024-09) PSBT
   from descriptor watch-only, 0.75.0 (2025-03) P2TR; green_android and
   green_ios 5.1.0; green_qt 3.5.0 (2026-08).

**Consequence for tickets 06 and 22:** Green takes the same plain descriptor
QR as Sparrow for both script types. Its entry is wired to the Sparrow
format. The Jade-labelled prompt is the thing ticket 22 must watch for on
Ben's phone.
