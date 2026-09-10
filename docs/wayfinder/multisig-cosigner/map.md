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

- **Sparrow keeps a partial signature it did not make.** Measured
  2026-09-10 against drongo 2.5.4. `wallet.sign(psbt)` signs the PSBT in
  place and adds to what is already there, so the CHAINED route works:
  coordinator sends, Corky signs, the signed PSBT returns by QR, and the
  coordinator signs on top. That is the air-gapped flow, and it needed
  proving rather than assuming. The COMBINED route, where both sign the
  original and `combinepsbt` merges, reaches **identical transaction
  hex**. The two are interchangeable and Corky does not care which the
  coordinator uses.

- **`analyzepsbt` answers "did WE add a signature", it just cannot
  answer "is this finished".** `next` reads `signer` before and after,
  which is what the note below says. `missing.signatures` is a separate
  field listing the key hashes Core has not seen, and it shrinks as
  signatures land. Measured 2026-09-10, and it is what `sign_psbt`'s
  `added` is built on. Core also returns the IDENTICAL base64 string
  when it signs nothing, which is a free second reading of the same
  fact.
- **Signing at a path the device was told needs the master xprv.** A
  descriptor is the only way Core imports a derivation and a descriptor
  carries the key, so there is no route that keeps the key inside Core.
  M9 makes the exposure as narrow as it goes: only when the loaded
  policies signed nothing, into a scratch wallet, dropped in a
  `finally`.

- **The path is not a fixed set.** M1 settled it: Corky derives where it
  is told. Every ticket after this one inherits that, and so does every
  test: "these four policies" is no longer a claim anything can check by
  enumeration.
- **Miniscript, decay and blinding are all M1 in disguise.** Core signs
  a Liana-shaped timelock policy and finalises it alone; it imports a
  three-tier decaying quorum and takes Corky's signature at every tier;
  it signs on a 93-bit random hardened path. Every one of those is
  reachable by the same trick as plain multisig, which is importing
  Corky's own key at the right path as an ordinary single-sig
  descriptor. See M6.
- **`analyzepsbt` cannot tell a finished PSBT from an unfinished one.**
  It reports `next: signer` both before and after Corky's signature, so
  nothing derives "one of two present" from it. Counting
  `partial_signatures` would, and `_REVIEW_DROPS` drops that too.
- **Bitcoin Core has no file import at all.** `importdescriptors` takes
  `desc` as `RPCArg::Type::STR` and `importwallet`/`dumpwallet` are gone.
  A cosigner file reaches a Core coordinator only as a string a person
  carries into a descriptor they assemble. M2 added the file route
  believing Core would read it; half of that was wrong and M7 says which
  half.
- **A cosigner branch derives a single-sig address, not the quorum's.**
  The quorum's address needs every cosigner and Corky holds one. So an
  address is not available as a confirmation anywhere in this map, and
  Core's 8-character descriptor checksum is what a person compares
  instead. Measured: changing the path or the fingerprint changes it, and
  a corrupt xpub is refused outright because base58 carries its own.
- **A descriptor may hold at most one private key.** Two xprvs in one
  descriptor are refused as "not sane: contains duplicate public keys"
  even when they differ. Irrelevant in practice and worth knowing before
  someone writes a test that trips on it.

## Decisions so far

<!-- one line per closed ticket -->

- [M1 Which BIP48 script types does Corky offer?](tickets/M1-which-script-types.md):
  arbitrary paths, told to the device, which opens miniscript, decay and
  blinding together. Signing reads its path out of the PSBT and shows it
  on the review screen, so none of those shapes needs setting up first.
  Export keeps named rows at the top and puts the typed path inside
  Advanced, which is Coldcard's structure with the capability they do not
  have.
- [M2 How does the cosigner key leave the device?](tickets/M2-cosigner-export.md):
  by QR and by file, not by typing. The typed path echoes Core's
  8-character descriptor checksum rather than a test address, because a
  cosigner branch derives a single-sig address and not the quorum's. The
  file route exists because Core reads no QR, and its format is M7.
- [M3 What changes in the signing path?](tickets/M3-signing-path.md):
  a partial signature is delivered on today's SIGNED screen rather than
  refused, and the review screen carries what that screen no longer
  says: the threshold, the path and every cosigner's fingerprint. Undrops
  `witness_script`, which M5 must re-measure for.
- [M4 Does Sparrow accept Corky's cosigner export?](tickets/M4-sparrow-accepts.md):
  yes, in M7's format unchanged, and it signs beside us. 20 checks green
  in `tests/sparrow/test_cosigner.py` on both an ordinary BIP48 path and
  a 93-bit blinded one: Sparrow derives the same addresses Core does,
  Corky signs one share, and the quorum finalises by either the chained
  or the combined route to identical hex. Proves the interop and the
  format, NOT the device flow, because the test stands in for M3's
  unbuilt "import the path out of the PSBT".
- [M9 Build M3: deliver the signature, and make review say what it is](tickets/M9-build-the-signing-path.md):
  built. Review states the quorum, the path and every cosigner, and the
  device signs its share at whatever path the PSBT names, so
  `tests/sparrow/test_cosigner.py` no longer needs a stand-in. `sign_psbt`
  gains `added`, because `complete` is False both for one signature of
  two and for none at all. **The undrop costs 0.29MB retained and
  nothing at the peak**, measured at 150 multisig inputs, so M5 is a
  confirmation rather than a risk.
- [M10 Prove the master xprv leaves nothing when it signs at a told path](tickets/M10-prove-the-xprv-window.md):
  measured, and it leaves nothing. The scratch wallet DOES hold the key
  while signing, which is the positive control; after the sign, and
  after a sign forced to FAIL, no new file holds it and the wallet is
  gone. No key reached argv in 13 calls, and defeating that needs BOTH
  `Rpc.call`'s `_SECRET_RE` guard and the explicit stdin flag disabled
  together.
- [M7 What file does a coordinator want a cosigner key in?](tickets/M7-cosigner-file-format.md):
  a bare key expression on one line, which Coldcard writes and both
  Sparrow and Nunchuk read. Coldcard omits the `/0/*` suffix Core gives
  us, so Corky strips it. Core reads no file either, which corrects half
  of M2's reasoning.

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
- **Which tier of a decaying quorum a spend uses.** None of the three
  tiers finalised on Corky's signature alone, including the one-key tier
  past its timelock, and the likely cause is that the coordinator's
  `nSequence` never enabled the timelocked branch. If that is right the
  choice belongs to the coordinator and Corky's job does not change. It
  is not proven, and M6 says so rather than assuming it.
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
