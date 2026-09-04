# 07 Does Generate change ordering

Labels: wayfinder:grilling (HITL)
Blocked by: none

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
