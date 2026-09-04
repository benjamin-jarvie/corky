# 07 Does Generate change ordering

Labels: wayfinder:grilling (HITL)
Blocked by: none
Assignee: claude (claimed 2026-09-04)
Status: CLOSED 2026-09-04

## Question

The facts are in from "Should Generate make the seed first, the way Bails
does". The decision is now Ben's, and it is narrow:

**Does Corky's Generate stay Core-makes-the-key, or become
Core-makes-entropy then Corky-makes-the-seed?**

What seed-first buys:

- Every generated key HAS a seed, so codex32 works and nothing has to refuse.
- The backup becomes a **74-character** standard-length codex32 string
  instead of a 111-character xprv, and it splits into k-of-n shares.
- Other wallets can import it: 256-bit is a length the spec says wallets
  SHOULD support, unlike the 127-char strings Corky writes today.
- It costs almost no new code. `seed_to_xprv` is verified against BIP32
  vector 1 and a BIP93 vector, `codex32.py` is BIP93-correct, and
  `_codex32_open` already does seed to descriptors.

What it costs:

- **PLAN A-19 as written.** "Seed generation and usage EXACTLY as a Bitcoin
  Core wallet" becomes false: Corky performs the seed-to-key derivation on
  the generate path. It already performs that step for BIP39 words, so this
  is not new capability, but it is newly on the path Ben reaffirmed twice on
  2026-09-04 as "the whole point".
- A throwaway wallet that must be reliably destroyed. Core has no delete
  RPC. On Corky the datadir is a 128MB tmpfs that power-off wipes, which is
  a stronger guarantee than Bails' shell EXIT trap.

Sub-decisions if the answer is yes:

1. **Seed length: 128 or 256 bit?** Bails hardcodes 128 (48 chars, less to
   transcribe). 256 (74 chars) matches Core's own key strength. Both are
   spec-standard lengths.
2. **Where do the seed bytes come from?** Recommended: the throwaway xprv's
   own master key and chain code, used directly, no new construction. NOT a
   bespoke HMAC, which would invent a scheme nobody can reproduce, and NOT
   Bails' scrypt, whose 1 GiB working set is impossible on a 512MB board.
3. **Does user entropy mix in?** Bails uses dice as the scrypt password with
   Core's xprv as the salt. That is a real design, and it changes the story
   from "Core is the only source" to "Core plus you". It also needs a KDF
   Corky cannot afford on this hardware.
4. If yes, is it a **replacement** for the current Generate, or a **second
   option** beside it?

Whatever the answer, the recovery drill is worth taking: Bails forces a
re-type and rebuilds the wallet only from what was re-entered. Its mismatch
check is an unimplemented TODO, so Corky should do the comparison Bails does
not.

## Resolution (Ben, 2026-09-04)

**Generation does not change. The conversion lives in Tools, it replaces the
key, and it is refused once the wallet has ever received.**

I drifted here and Ben pulled it back: he had already decided codex32 belongs
in Tools, separate from generation, and I re-opened it as a generation
change. His version works.

    Core generates      K
    Tools converts      K's bytes -> seed S -> HMAC -> K'
    codex32 encodes     S
    restoring S gives   K'

**The conversion necessarily produces a different key.** That is forced, not a
flaw: BIP32 turns a seed into a key by HMAC, and Core starts at the key. So
the conversion cannot be a *backup* of the existing key. It must **replace**
it: Corky imports `K'` and the wallet becomes `K'`. The fingerprint on home
changes, which is the honest visible signal.

**Safe only before the wallet is funded.** Convert after receiving and the
coins sit at `K`'s addresses while the backup restores `K'`. Corky checks the
wallet has never received and refuses otherwise.

Rejected, and it is the dangerous reading: leaving the wallet as `K` while the
backup encodes `S`. It would look like a working backup and restore the wrong
wallet, which is the exact hazard this map exists to close.

So A-19 stays literally true. Core makes the key with its own RNG and Corky
signs with that wallet, unless the user deliberately asks Tools to convert it
into one that can be split.

**Seed length is unresolved.** 128-bit gives a 48-character string, a third
less to stamp and read back on every share, at the security level Bitcoin's
own address hashes sit at; Bails hardcodes it. 256-bit preserves all of
Core's entropy in 74 characters. Ben stopped before answering, so it goes to
the full version's fog.

Closed.
