# 06 Export public key

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

Corky has no export flow. The interop tests built the public key in the
harness, so the gap never showed. What does export look like, for which
coordinators, in which forms?

## Facts

- Sparrow's own library (drongo, from the verified 2.5.4 release) parses
  Core's public descriptor verbatim, hardened `h` markers and `#checksum`
  included, and derives the same first three addresses as Core for both
  wpkh and tr. Proven 2026-09-04; the probe becomes a permanent test.
- A Core-generated wallet lists eight active descriptors: pkh, sh(wpkh),
  wpkh and tr, receive and change. Only wpkh and tr may leave the device.
- Bitcoin Core has no QR reader. Its public key must arrive as a file.
- The generate flow's "first address" screen truncates the address and calls
  `getnewaddress`, which advances the wallet's index on every redraw.
  `deriveaddresses` is side-effect free.

## Resolution (Ben, 2026-09-04)

**SeedSigner's shape: choose the wallet software first.** The list shows all
five now: Sparrow, Bitcoin Core, BlueWallet, Green, Bull Bitcoin. Sparrow
and Bitcoin Core are wired first. A phone entry is marked untested until its
research ticket closes, and is wired to the format that research names.

Then the script type: native segwit (BIP84) or taproot (BIP86).

**Sparrow, and any wallet that reads plain text:** a static QR of the public
receive descriptor, Core's string with its checksum, no UR. Then the text in
four-character groups. Then the first three receive addresses in full,
grouped in fours, first and last group in ochre and the middle in cream,
with the line "compare every group" (Ben's earlier rule: never truncate,
group in fours, colour head and tail).

**Bitcoin Core:** a watch-only wallet file. Corky makes a wallet with no
private keys, imports the four public descriptors into it, and Core's own
`backupwallet` writes the file. Core's GUI restores it with File, Restore
Wallet. Zero formatting code of ours. File only, to the stick or the card.

The generate flow's address screen is replaced by the export's address page.

## Amendment (2026-09-05, after the two-axis review)

The decision above says a phone entry is "marked untested until its
research ticket closes". Tickets 19, 20 and 21 are now closed, and the
entries still read "untested". The Spec axis was right to flag that as a
closed decision quietly rewritten, so it is rewritten here instead.

**The mark now means "not proven on a handset", not "not researched".**
The research closed a different question: it established that all three
apps read the plain descriptor Corky writes, and that all three hand a
PSBT back as `ur:crypto-psbt`, which Corky already decodes. None of that
was tested on a phone, and the two things a phone can still break are the
camera reading the panel and the app's own flow, neither of which a source
reading can settle. Ticket 22 removes the mark per app, with a version
number and a transaction id.

Bull Bitcoin keeps a second qualifier for a reason the research found: its
parser throws on `86h`, so its entry offers native segwit only.
