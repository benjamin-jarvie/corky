# Corky

**Core's keys, nothing kept.**

Corky is a stateless, air-gapped Bitcoin signing device built from SeedSigner
hardware (Raspberry Pi Zero 2 W, camera, small LCD) with one difference that is
the whole point: the wallet brain is **Bitcoin Core itself**, running wallet-only
and offline. Key derivation, PSBT parsing, fee computation and transaction
signing are done by the same reviewed C++ code that runs the Bitcoin network's
reference node. No reimplementation of wallet logic.

The device holds nothing. The wallet lives on a ramdisk, the seed is entered
each session (words or SeedQR), and power-off wipes everything.

## What you are trusting — stated plainly, not in fine print

**One thing in Corky is not Bitcoin Core, and it sees your seed words.**

Bitcoin Core does not read BIP39 seed words and its developers have said it
never will. So Corky carries a translator: [`shim/bip39_shim.py`](shim/bip39_shim.py),
about 100 lines including comments, which turns your words into the xprv format
Core imports. Know exactly what it is:

- It uses **only Python's standard library hashing** (PBKDF2, HMAC-SHA512).
  No third-party crypto libraries. No elliptic-curve math anywhere in it.
- Its output is checked automatically against the **official BIP39 and BIP32
  test vectors** (`shim/test_shim.py`). A single wrong bit produces a wallet
  whose addresses do not match yours, which you would see immediately.
- It runs on a device with **no radio and no persistent storage**, so even a
  hostile version of it would have nowhere to send anything and nowhere to
  hide anything.
- It is **frozen**. Any change must re-pass the vectors and update the hash
  recorded below.

Every operation after the translator — deriving child keys, checking the
transaction, signing — happens inside Bitcoin Core.

If you cannot accept those ~100 lines, Corky is not for you, and that is a
legitimate position: use a signer whose whole stack you prefer. Corky's claim
is not "trustless". It is: **you trust Bitcoin Core's wallet implementation
instead of a rewrite of it, plus one small, frozen, vector-tested hashing file
that we show you.**

Shim integrity:

```
shasum -a 256 shim/bip39_shim.py shim/english.txt
```

The wordlist must hash to the canonical BIP39 value
`2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`
(the shim refuses to run otherwise). The shim's own current hash is recorded
in `SHIM_HASH` at the repo root and updated only with a passing vector run.

## v1 scope (frozen)

Single-sig BIP84 (native segwit) and BIP86 (taproot). BIP39 with optional
passphrase. SeedQR input. PSBT in/out via **three channels**: animated QR;
a PSBT file on a USB stick in the OTG port; and — once the M3 RAM-resident
image lands — the boot microSD itself, SeedSigner-OS style (the whole OS runs
from RAM, so the card can be pulled and used as the PSBT sled). QR is the
tightest channel (photons only); the file channels have no size limit. All
three carry only PSBTs, and only Bitcoin Core ever parses them. If 512MB
cannot hold the RAM-resident image, v1 ships QR + USB and the microSD channel
waits for a bigger board (the fallback is written down in PLAN.md A-12).

Display: 2.4" ILI9341 (320×240, SeedSigner-Plus class) as the primary build;
the 1.3" ST7789 (240×240) remains supported. Both drivers are vendored from
SeedSigner (MIT) in `hw/vendor/`. A review screen showing
outputs, amounts and the fee as computed by Core from the coordinator-supplied
input amounts (an air-gapped signer cannot independently verify input amounts;
none can). Coordinator target: Sparrow.

Out of scope for v1: multisig, message signing, address explorer, dice entropy,
and on-device seed generation. Corky signs for seeds that already live on metal;
it deliberately has no entropy story of its own.

## Status

Planning complete (see [PLAN.md](PLAN.md), including two devil's-advocate
rounds). Shim written and passing all vectors. Next gate: **M0** — measured
proof that wallet-only bitcoind fits and signs on the Zero 2 W's 512MB.

## Build gates

| Gate | Deliverable | Pass condition |
|---|---|---|
| M0 | bitcoind wallet-only on Zero 2 W, headless | signs stress PSBT; peak RSS recorded; ≥100MB headroom |
| M1 | QR round trip vs Sparrow watch-only, testnet | fee/outputs match Sparrow; signed PSBT broadcasts |
| M2 | stateless UI on the LCD hat | power-on→ready < 90s; power cycle provably wipes |
| M3 | hardened reproducible image | read-only root; radios dead; image hash reproducible |
| M4 | mainnet trial | small-sats spend from a metal-backed seed |
