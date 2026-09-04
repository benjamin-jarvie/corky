# 03 What does the session record about where its key came from

Labels: wayfinder:grilling (HITL)
Blocked by: none
Assignee: claude (claimed 2026-09-04)
Status: CLOSED 2026-09-04

## Question

The session records nothing today. That is the root cause of the codex32
bug: `_tool_backup` cannot tell a key that came from words from one Core
generated, so it asks for words in both cases and would encode the wrong
wallet.

Decide, with Ben:

1. Which origins are distinct enough to matter. Candidates: typed words,
   scanned SeedQR, typed xprv, scanned xprv, typed descriptor, codex32
   recovery, Core generation, BIP-85 child.
2. What each origin licenses. Words license a codex32 backup; an xprv
   licenses nothing beyond signing; Core generation licenses BIP-85.
3. Whether the words themselves are held for the session, or only the fact
   that words were used. Holding them makes codex32 backup possible without
   retyping, which is Ben's ask, and it keeps secret material in Python
   memory for longer, which Layer 2 exists to minimise.
4. Whether provenance survives a return to home, and what clears it.
5. Whether Tools should display the origin, and in what words.

The answer shapes every other ticket on this map.

## Resolution (Ben, 2026-09-04)

**Corky holds a fingerprint and a label. Never key material. It proves a
retype opens the same key.**

### 1. What the session holds

The **XFP** and the **origin**. Not the words, not the seed.

When a flow needs the seed (a codex32 backup), Corky asks for the words
again, derives a key, and compares the fingerprint against the loaded one.
Match: proceed. Mismatch: refuse, and say that these words do not open this
key.

Rejected: holding the mnemonic for the session. It removes the retype, which
was the original ask, but it lengthens the exact window Layer 2 exists to
shorten. The README's claim is that 1,471 lines see secrets and compute
nothing with them; holding a mnemonic from load until power-off buys
convenience rather than safety.

Rejected: holding the 64-byte seed instead. The seed IS the wallet, so it is
not meaningfully less secret than the words.

**Three things this buys beyond the obvious one.** It closes the wrong-wallet
hazard completely, with no path left where a backup encodes a key other than
the one loaded. It costs zero extra exposure time. And it catches a wrong
word: BIP39's checksum is four bits, so a wrong mnemonic still validates
about one time in sixteen, and comparing the derived fingerprint catches that
absolutely.

**The retype is the recovery drill.** Bails forces one and Corky has none. If
you cannot retype your words, you did not really have them, and the moment to
find that out is before there are coins.

### 2. How precisely the origin is recorded

**Exactly.** One string naming which of these it was:

    typed words, scanned SeedQR, typed xprv, scanned xprv,
    typed descriptor, codex32 recovery, Core generation, BIP-85 child

Licensing is computed from it, not stored separately:

| origin | codex32 backup |
|---|---|
| typed words, scanned SeedQR, codex32 recovery | allowed, after a verified retype |
| typed xprv, scanned xprv, typed descriptor | refused: no seed exists |
| Core generation | refused: no seed exists (unless "Does Generate change ordering" changes this) |
| BIP-85 child | it has words, so allowed, but the screen must say the child is a different wallet |

Rejected: a has-seed/no-seed boolean. It is all the licensing needs, but it
leaves Tools unable to say a key came from Core rather than a pasted xprv,
and every refusal reads the same. Recording the origin costs one string.

Tools displays the origin. That is what makes Tools able to answer "what key
is this", which is the map's destination.

### 3. Lifecycle: an orphaned wallet is dropped

Provenance is set when a key loads and cleared when the wallet closes, so it
lives exactly as long as the key. Returning to home does not clear it: home
is reachable with a key still open, by design (D7).

**If Corky starts and finds a wallet it did not load this session, it closes
that wallet.** A wallet Corky cannot account for is not Corky's. This is the
strongest statelessness answer and it matches power-off being the real
teardown.

Cost, accepted: a crash mid-session loses the loaded key and you reload from
your backup. That is a thing you should be able to do, and being made to do
it occasionally is not a bad property for this device.

Rejected: asking the user to assert the origin of an orphaned wallet. It asks
them to state something Corky cannot verify, and a wrong answer re-opens the
exact hazard this ticket closes.

Closed. Unblocks the XFP confirmation, BIP-85 in Tools, and the export flow.
