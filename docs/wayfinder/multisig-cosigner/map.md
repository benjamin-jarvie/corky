# Map: Corky signs its share of a multivendor quorum

Label: `wayfinder:map`. Tickets are in `tickets/`, one file each.
Charted 2026-09-09.

## Destination

**A key Bitcoin Core generated can be one cosigner in a multivendor
quorum, and Corky signs its share air-gapped.**

The map is done when a person can put a Corky key into a 2-of-3 beside
two other vendors, and sign for it on the device, without the private
key ever entering a hot wallet.

## Notes

- **Why this matters, Ben, 2026-09-09.** Multivendor multisig exists so
  no single vendor's mistake loses your coins. Bitcoin Core is missing
  from that story and it is the most reviewed implementation there is,
  because everybody else's key is a BIP39 seed phrase and Core cannot
  make or read one. A Corky key is a Core key, so it can go in the
  quorum. If a vendor's key generation turns out to be wrong, and
  vendors differ enormously in how carefully they review a change, the
  quorum holds.
- **Ben's scope cut, 2026-09-09:** "We just need to be able to sign. If
  they're doing multisig with Core, they'll back up outside of us, and
  same in Sparrow." Corky holds ONE key and signs. The quorum belongs to
  the coordinator.
- This repo carries execution IN the map, as every previous one has.
- Skills: `/mp-tdd` for anything built, `/mp-code-review` before it
  lands, `/mp-codebase-design` for anything restructured. `TESTING.md`
  rules 1 to 12 bind every test. `CONTEXT.md` fixes the vocabulary and
  gains words here (**quorum**, **cosigner**).
- **Rule 8 is the house rule of this map.** Every interop claim is run
  against the counterpart it names. Sparrow's own library is in
  `tests/sparrow/`, out of its verified release. A claim about Sparrow
  that Sparrow has not been asked is a rumour.
- PLAN A-11 still holds: Core is the only thing that parses a PSBT or a
  descriptor. Nothing in this map changes that.

## What is already established

Measured in the charting session, 2026-09-09, against Core 31.1 and
Sparrow 2.5.4's own library. These are facts, not decisions, and no
ticket needs to re-derive them.

- **Core signs a multisig share with ONLY the BIP48 branch imported, as
  an ordinary single-sig descriptor.** `wpkh(xprv/48h/1h/0h/2h/{0,1}/*)`
  produces one partial signature on a quorum PSBT. Corky's four standard
  policies produce none. **So Corky never needs the quorum descriptor.**
  This is the finding the whole map is shaped around.
- **The cosigner xpub Sparrow wants is reachable.** Core's
  `getdescriptorinfo` public form keeps hardened steps unexpanded and is
  useless watch-only. Importing into a scratch wallet and reading
  `listdescriptors` gives `[xfp/48h/1h/0h/2h]tpub…` at depth 4, which is
  the cosigner form. Same round trip `write_watch_only` already uses.
- **Sparrow accepts a Core master key as a cosigner.** 2-of-3 P2WSH
  built in its own library beside two BIP39 mnemonics: real addresses,
  real `wsh(sortedmulti(2,…))`.
- **`describe_psbt` and `signer.owners` already work on a multisig
  PSBT**: outputs, fee, input count, `next_role: signer`, and all three
  cosigner fingerprints.
- **Core has no BSMS (BIP129) and no quorum setup command.** A multisig
  wallet in Core IS an imported descriptor, and `listdescriptors true`
  is its backup: one string holding the key and the quorum together.
- **Core signs on a BLINDED path, and most hardware wallets do not.**
  Blinded xpubs are Michael Flaxman's protocol from 2021, implemented in
  `buidl-python`'s `multiwallet.py` and in Unchained's Caravan since
  2024. Instead of the standard `m/48'/0'/0'/2'`, the cosigner key is
  derived at a random hardened path, `secure_secret_path` in buidl, "31
  bits of good entropy" per level. The coordinator gets
  `[real-xfp/random-hardened-path]child-xpub`, so it can watch the wallet
  and cannot reconstruct it, and buidl warns "Do NOT share this record
  with the holder of the seed phrase, or they will be able to unblind
  their key". Spending needs BOTH the seed and the record.

  buidl's own warning is the interesting half for this map: "few HWWs can
  sign on these paths. Some can't even co-sign a multisig transaction
  with nonstandard BIP32 paths." **Core has no such limit.** Tested
  2026-09-09 with a 3-level, 93-bit random hardened path: the quorum
  imports, and Core signs its share. That is a thing Corky can do that
  most of the vendors in a multivendor quorum cannot.

## Decisions so far

<!-- one line per closed ticket -->

_None yet. Charted 2026-09-09._

## Not yet specified

- **Taproot multisig.** BIP48 script type 2' is P2WSH. Taproot changes
  the shape entirely (musig2, script paths), Core's support is its own
  question, and nothing here has been looked at. Revisit once the P2WSH
  route works end to end.
- **What the address screen does for a multisig key.** Today
  `_page_addresses` walks the four single-sig policies. A BIP48 branch
  derives cosigner keys, not addresses anyone can pay: an address needs
  the whole quorum, which Corky does not hold. The screen probably has
  to say something rather than show something, and what it says is not
  yet a sharp question.
- **Several quorums at once.** Corky holds up to five keys. Whether one
  key can be a cosigner in more than one quorum, and whether that is
  visible anywhere, has not been thought about.
- **Blinded xpubs as a supported flow rather than an accident.** Core
  signs on these paths, which most hardware wallets cannot, so Corky
  could support the protocol properly: derive a cosigner key at a random
  hardened path, and export the blinded record. Two things are unclear
  and neither is sharp enough to ticket. Where does the 93 bits come
  from, given PLAN A-19 says Corky ships no randomness and asks Core for
  every byte of it. And blinding breaks the property that the paper key
  alone recovers the wallet, in a way the standard paths do not, which
  is the descriptor argument at its strongest and needs its own thinking
  about what Corky then owes the user.

## Out of scope

- **Backing up the quorum, on paper or digitally.** Ruled out by Ben,
  2026-09-09: the coordinator holds it, in Sparrow or in Core, and backs
  it up there. Corky's backup stays the 111-character key it is today.
  Charting had gone some way into this (four printable QRs at 4px per
  module, or Core's own 435-character private descriptor) before the cut.
- **Corky holding or displaying the quorum descriptor.** Follows from
  the finding above: signing does not need it, so carrying it would be
  scope with no payer.
