# 01 Should Generate make the seed first, the way Bails does

Labels: wayfinder:research (AFK)
Blocked by: none
Assignee: claude (claimed 2026-09-04)
Status: CLOSED 2026-09-04

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

## Resolution (2026-09-04)

**The ordering is sound. Bails' implementation must not be ported.**

### The ordering works, and Corky already owns every piece

`shim/bip39_shim.py:seed_to_xprv` is sufficient for the seed-to-key step,
verified two ways: it reproduces BIP32 test vector 1, and it reproduces the
published xprv for BIP93 vector
`ms10testsxxxxxxxxxxxxxxxxxxxxxxxxxx4nzvca9cmczlw`. `corky/codex32.py`
already has `encode_secret`, `split`, `recover` and `to_xprv`, and
`_codex32_open` (`corky/main.py:584`) already does seed -> `to_xprv` ->
`build_descriptors`. The only missing piece is the entropy grab, about eight
RPC lines.

### What Bails actually does

`Bails/bails/.local/bin/bails-wallet:492-509`, the bash repo (the Python one
does not implement this). It creates an **encrypted** throwaway descriptor
wallet with a 64-byte random passphrase, unlocks it, regexes the master xprv
out of the `tr(...)` descriptor, locks and unloads it, and lets a shell EXIT
trap delete the directory. Core has no delete-wallet RPC; the discarded
passphrase is what crypto-shreds it.

**Core's entropy is the salt, not the seed.** `ms32.py:224-232`:

    hashlib.scrypt(password=user_entropy + str(seed_length),
                   salt=bitcoin_core_entropy,
                   n=2**20, r=8, p=1, maxmem=1025**3, dklen=seed_length)

So the user's dice or keyboard entropy is the password and Core's xprv is the
salt. That is a **mixing** design, not "Core generates and Corky reshapes",
and it changes the A-19 argument: Bails is not claiming Core is the sole
source. `bails-wallet:511` hardcodes 16 bytes, so a **128-bit** seed.

### Why the code cannot be ported

- **scrypt N=2^20, r=8 is a 1 GiB working set** (`128 * r * N`), with
  `maxmem=1025**3`. The Zero 2 W has 512MB total and M0 measured 117MB of
  headroom at the worst case. Hard blocker, and it appears in three
  functions.
- **Electrum dependency** for `BIP32Node`. Corky's shim replaces it.
- **Zenity, GTK, D-Bus and Tails assumptions** throughout, including LUKS
  vaults and a screen locker.
- **Secrets in argv.** `bails-wallet:510-518` interpolates the xprv, the user
  entropy and the passphrase into `python3 -c`, and line 449 puts a private
  descriptor into `importdescriptors` argv. `corky/signer.py` already forbids
  this: every secret goes through `bitcoin-cli -stdin` (S4), and I-10 made
  PSBTs do the same.
- GNU-only `grep -oP` and `awk 'NR==3'` checksum extraction.

### Two defects found in Bails, worth reporting upstream

- `bails-wallet:503` `unset $key` unsets the variable *named by the value*,
  not `key`.
- `bails-wallet:444` hardcodes coin type `0h` regardless of network, so
  testnet wallets get mainnet paths.

### Findings that close other questions

- **BIP-85 in Bails is aspirational. Zero code.** It appears only in
  `README.md:22-23` and `docs/DESIGN_SCOPE.md:44-45`. No `83696968`, no
  derivation, no decoy or panic wallets. So there is no reference
  implementation to follow for ticket 05; Corky would be first.
- **The recovery drill is implemented** (`bails-wallet:519-524`): it forces a
  re-type, discards the generated material, and rebuilds the wallet **only**
  from what the user re-entered. But the promised mismatch warning is a live
  TODO at 521-523. Corky should do the comparison Bails did not.
- Core accepts a key from a 256-bit seed without complaint; it never sees the
  seed, only an xprv, and HMAC-SHA512 yields 64 bytes for any seed length.
- The imported wallet is essentially indistinguishable from a Core-native
  one: same four-purpose descriptor set from one master key.

### One recommendation from the research that I reject

The researcher proposed `hmac(b"corky-seed-v1", xprv_bytes, sha512)[:32]` for
the xprv-to-seed step. **No.** That invents a new derivation scheme nobody
else can reproduce, in a project whose entire argument is that it does not
invent crypto. The xprv already contains 64 bytes of Core RNG output as the
master key and chain code. Use those bytes directly as the codex32 seed. No
new construction, no entropy lost, and the discarded throwaway key is never
the one that holds coins.

Closed. The decision this unblocks is now its own ticket, "Does Generate
change ordering", with the facts settled.
