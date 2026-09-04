# 01 Should Generate make the seed first, the way Bails does

Labels: wayfinder:research (AFK)
Blocked by: none

## Question

Corky generates the key IN Core, so no seed ever exists and codex32 has
nothing to write. Bails (BenWestgate/bails-wallet) reverses it: "grab an xprv
from a temporary bitcoin core encrypted wallet for entropy", make a codex32
seed from that, derive the key, import it. Core stays the only entropy
source, and every key then HAS a seed.

Ben's lean (2026-09-04): research before deciding, and codex32 backup should
live in Tools beside BIP-85 rather than on the default generate path.

Find out, from the code rather than the README:

1. Exactly how Bails takes entropy from the throwaway wallet. Which RPC, how
   many bytes, and does it destroy the temporary wallet afterwards.
2. What it imports into Core, and whether Core's `importdescriptors` accepts
   a key derived from a 256-bit codex32 seed without complaint.
3. Whether the derived wallet is indistinguishable from a Core-native one
   afterwards, or carries some marker.
4. What Bails does about BIP-85 children ("spending, panic mode and decoy
   wallets will be BIP85 children xprvs to protect the savings").
5. Whether `shim/bip39_shim.py:seed_to_xprv` is sufficient for the seed to
   key step, or whether more is needed.

The decision this unblocks: does Corky's Generate change ordering, gain a
second option, or stay as it is. Note the cost either way: seed-first means
Corky performs the seed to key derivation on the generate path, which bends
PLAN A-19's "exactly as a Bitcoin Core wallet" as written.
