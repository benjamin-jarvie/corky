# 12 Build the export

Labels: wayfinder:task (AFK)
Blocked by: 11
Status: resolved 2026-09-05

## Question

Build ticket 06: the wallet chooser, the script-type choice, the plain
descriptor QR, the grouped text, the three-address page with head and tail
colouring, the Core watch-only wallet file, and the file writer for the
stick or card. Filter to wpkh and tr. Replace the generate flow's address
screen with the address page and its `getnewaddress` with
`deriveaddresses`.

Tests: an e2e session whose rendered QR decodes with pyzbar to Core's exact
string; the Sparrow probe made permanent in `tests/sparrow` (rule 8); a
second regtest node that `restorewallet`s the Core file and owns the same
addresses; legacy descriptors never appear; the keypool does not move when
the address page is drawn.

## Answer (built, 2026-09-05)

`tests/test_export.py` (11 checks against two real Cores),
`tests/sparrow/test_export_interop.py` (16 checks against Sparrow's own
library), and session K5 in `tests/e2e_keys.py` for the device walk.

**The flow.** Key menu, Export public key, then SeedSigner's question
first: which wallet is going to read this. All five are listed, the three
phones marked untested until ticket 22. Then the script type, native segwit
or taproot, skipped when the target reads only one (Bull Bitcoin's parser
throws on `86h`, ticket 21). Then three screens: the descriptor as one
static QR filling the panel, the same descriptor as text in four-character
groups, and the first three receive addresses one per screen, in full.

**Bitcoin Core takes a file instead**, because it has no QR reader.
`signer.write_watch_only` makes a wallet with `disable_private_keys`, imports
the public descriptors into it, and lets Core's own `backupwallet` write the
file. No code of ours shapes the format, and the scratch wallet is deleted
again, so the session is left exactly as it was found. Proven: a second Core
restores it, reports `private_keys_enabled: false`, owns Corky's first
address, and the file contains none of the key's bytes.

**Proven against the counterpart, not against ourselves** (rule 8). The QR
is rendered exactly as the panel shows it, at both panel sizes, then decoded
by the zxing reader Sparrow uses: byte-identical, four times out of four.
The decoded string goes into Sparrow's `OutputDescriptor.toWallet()`, which
reports Single Signature HD, the same fingerprint, and the same first five
addresses as Core, for wpkh and tr.

**Three details that matter.**

- `frames_to_images` uppercases its input to reach QR alphanumeric mode,
  which is right for UR frames and would destroy a descriptor, where the
  xpub and the checksum are case-sensitive. `qrchannel.text_to_image` is a
  separate renderer that encodes the bytes as given.
- Only wpkh and tr ever leave the device. A Core-generated wallet also
  carries legacy pkh and sh(wpkh) descriptors, and a test refuses them.
- The address screens use `deriveaddresses`, which is side-effect free. The
  old generate screen used `getnewaddress`, which advanced the wallet's
  index every time it was drawn, and truncated the address it showed. Both
  are gone: generation now ends on the same full-address screen.

**Ben's display rule, and its caution.** Never truncate, group in fours,
colour the first and last group. The middle groups keep the same size and
weight, and the footer reads "compare every group", because matching only
the ends is the shortcut address-replacement malware relies on.

**Also landed here:** `tests/sparrow/harness.py` was still calling the
deleted shim, so the 58 Sparrow interop checks could not run at all. It is
ported to the xprv, which unblocks the rest of ticket 16's list.
`Session` now takes a `card_dir`, and `corky.service` passes
`/boot/firmware`, so a file can go to the stick or the boot card.
