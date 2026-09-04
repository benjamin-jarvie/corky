# Map: key provenance, and backups that cannot lie

Labels: wayfinder:map
Opened 2026-09-04.

## Destination

Every backup and recovery flow works on the board: Corky knows where its key
came from, Tools can answer "what key is this?", codex32 splits the loaded key
behind an XFP confirmation, BIP-85 lives in Tools as its own thing, and no
flow can produce a backup of a wallet other than the one it says.

## Notes

- **Ben's instruction (2026-09-04): execution is carried in-map.** Chart, then
  build, as the M1 map did. Decisions and code both land here.
- The trigger: `_tool_backup` asks for 12 or 24 words even when a key is
  loaded, and will encode whatever is typed. A user with a Core-generated key
  can walk away holding a codex32 backup of **a different wallet**. The root
  cause is that the session records no provenance at all.
- Style: ASD-STE100. No em dashes in new prose.
- Test on the board, not only on the Mac. TESTING.md rule 9.

## Established facts. Do not re-derive.

1. **xprv to BIP39 words is impossible.** PBKDF2 and HMAC are one-way. Only a
   key that arrived AS words can ever show words.
2. **Core-generated keys have no BIP39 seed.** Core makes the master key
   directly. PLAN A-19, reaffirmed by Ben 2026-09-04.
3. **Corky's codex32 is BIP93-correct.** 48 chars at 128-bit, 74 at 256-bit,
   and it switches to the long 15-char checksum at 512-bit as the BIP
   requires. Verified 2026-09-04.
4. **But 127-char strings are optional-length.** `docs/wallets.md`: wallets
   SHOULD import 128- and 256-bit seeds, "other lengths are optional". Corky
   writes the 64-byte BIP39 seed, so a conforming wallet may refuse it.
5. **The codex32 spec has no generation guidance at all**: `## Generate
   Support` is `TODO`. Bails' entropy-from-Core design is Westgate's own.
6. **The spec sanctions encrypting recovery progress**: "Wallets MAY encrypt
   and store recovery progress... outside of the scope of this
   specification." That is partial shares mid-restore, NOT storing a seed.
7. **Core writes standard output descriptors**, so a Core-generated key's
   xpub is ordinary everywhere: Sparrow, Bull Bitcoin, Green and Core all
   read `wpkh([XFP/84h/1h/0h]tpub.../0/*)#checksum`. Nothing about Core
   generation makes the export unusual. Verified 2026-09-04.
8. **`deriveaddresses` is side-effect free**; `getnewaddress` advances the
   wallet index. Verified against Core 31.1: keypool 4000 before and after.
9. **XFP exists**: `signer.master_fingerprint`, read from public descriptors,
   shown on home since 2026-09-04.
10. **The codex32 identifier must NOT be the XFP.** BIP93 defines no
    convention. The XFP is public in every PSBT and descriptor, so putting it
    on a share links that share to an on-chain wallet and its balance,
    defeating the point that a single share is useless. Corky's
    `sha256(b"corky-id" + seed)[:4]` is domain-separated and one-way. Verified
    2026-09-04; corrects an earlier recommendation of mine.
11. **Head-and-tail colouring does nothing to an 8-character string.** The
    four-char grouping rule colours the first and last group differently; an
    XFP has exactly two groups, so both are coloured and nothing is
    distinguished. The rule is for addresses, xpubs and descriptors. Grouping
    still helps short identifiers; the colouring does not.
12. **BIP-85 is the only route from a Core key to words**, and the words open a
   DIFFERENT wallet. Entropy Lab does exactly this and says so plainly.

## Decisions so far

- [01 Should Generate make the seed first, the way Bails does](tickets/01-bails-ordering.md)
  — the ordering is sound and costs almost no new code; Bails' implementation
  must NOT be ported (scrypt needs 1 GiB, secrets in argv, Electrum, Tails).
  Core's entropy is Bails' scrypt SALT, not the seed. Its BIP-85 is zero code.
  Its recovery drill is real and worth taking. The decision itself is now
  [07 Does Generate change ordering](tickets/07-does-generate-change-ordering.md).

- **Backup story (Ben, 2026-09-04).** Default backup is Core's master xprv.
  BIP-85 is a separate Tools operation, never on the default path. The choice
  between them appears at backup time ONLY if the user deliberately derived a
  child. Rationale: the default path never has to explain a divergence that
  does not exist yet.
- **codex32 on a seedless key (Ben, 2026-09-04): say no, and say why.** Do
  NOT offer BIP-85 in that refusal. A child is a different wallet, so
  suggesting it where someone is trying to back up THIS key reads as "here is
  your backup" and is how people write down words that hold no coins.
- **codex32 backup belongs in Tools (Ben, 2026-09-04)**, beside BIP-85,
  rather than on the default generate path.

- [02 Keep Corky's codex32, or vendor python-codex32](tickets/02-vendor-python-codex32.md)
  — keep ours. The two implementations agree bit for bit on all five BIP93
  vectors and all six interpolation checks, which is the best evidence
  Corky's codex32 has had. Vendoring would pull elliptic-curve code into the
  module that forbids it, remove `split()` which only Corky has, and buy no
  error correction because neither does any. Corky copies BIP93's own inline
  Python verbatim. Borrow only CRC padding as a reader heuristic, and the
  spec's four-character-window entry rules.

- [03 What does the session record about where its key came from](tickets/03-what-provenance-records.md)
  — the XFP and an exact origin string, never the words or the seed. A flow
  needing the seed asks for a retype and refuses unless the derived XFP
  matches, which closes the wrong-wallet hazard at zero exposure cost, catches
  the 1-in-16 mnemonic BIP39's checksum lets through, and doubles as the
  recovery drill Corky lacks. Provenance lives as long as the wallet; a wallet
  Corky did not load this session is closed at startup.

- [04 What the XFP confirmation shows before a split](tickets/04-xfp-confirmation-before-split.md)
  — the fingerprint, the origin, and notice that a retype is coming. Which key
  and why this one can be split, nothing else; the rest lives on the export
  screen. The XFP goes on this transient screen and never on paper.

## Not yet specified

- What the recovery card must carry, and whether Corky prints or displays it.
  Candidates: XFP, script type and derivation, network, policy, passphrase
  presence. Blocked on knowing what provenance the session keeps.
- Encrypted recovery progress on the microSD, per fact 6. Scope is partial
  shares during a restore. Needs its own threat model: the card is the boot
  medium and M3 wants a RAM-resident OS.
- Calculating a final word from 11 or 23, so dice and seed-picker cards can
  be finished on the device. Corky's generate screen calls dice the default
  and cannot finish a dice seed. Roughly 350 lines, mostly in Layers 1 and 2.
- Whether the retype-and-verify decided in "What does the session record
  about where its key came from" is drill enough, or whether generation also
  needs Bails' fuller version: show the backup, discard it, rebuild the wallet
  only from what the user re-enters.
- Whether the review screen should show the XFP too, not only home.
- An address explorer in Tools, beyond the first few shown at export time.
- Whether the four-character grouping and head/tail colouring decided for
  addresses should also apply to the xpub, the descriptor, and the xprv
  backup, which today uses a different pagination path (`share_pages`).
- Whether Corky should verify a descriptor it is GIVEN (a coordinator handing
  back a watch-only descriptor to check against the loaded key), not only
  export its own.

## Out of scope

- Reversing an xprv into words. Impossible, see fact 1.
- Encoding a 64-byte BIP32 node as codex32 to make Core keys splittable.
  Verified possible, but every other wallet reads a codex32 string as a seed
  and would derive a different key. A backup that looks standard and is not.
