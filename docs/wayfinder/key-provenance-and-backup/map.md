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
7. **XFP exists**: `signer.master_fingerprint`, read from public descriptors,
   shown on home since 2026-09-04.
8. **BIP-85 is the only route from a Core key to words**, and the words open a
   DIFFERENT wallet. Entropy Lab does exactly this and says so plainly.

## Decisions so far

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
- A recovery drill: create a backup, then restore from it before coins exist.
  Bails does this. Nothing in Corky does.
- Whether the review screen should show the XFP too, not only home.

## Out of scope

- Reversing an xprv into words. Impossible, see fact 1.
- Encoding a 64-byte BIP32 node as codex32 to make Core keys splittable.
  Verified possible, but every other wallet reads a codex32 string as a seed
  and would derive a different key. A backup that looks standard and is not.
