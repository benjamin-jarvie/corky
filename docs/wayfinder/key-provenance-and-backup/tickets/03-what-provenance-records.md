# 03 What does the session record about where its key came from

Labels: wayfinder:grilling (HITL)
Blocked by: none

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
