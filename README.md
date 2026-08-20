# Corky

**Core's keys, nothing kept.**

Corky is a stateless, air-gapped Bitcoin signing device built from SeedSigner
hardware (a radio-free Raspberry Pi CM4, camera, and the SeedSigner+ display
hat; a Pi Zero 2 W pocket build exists too) with one difference that is
the whole point: the wallet brain is **Bitcoin Core itself**, running wallet-only
and offline. Key derivation, PSBT parsing, fee computation and transaction
signing are done by the same reviewed C++ code that runs the Bitcoin network's
reference node. No reimplementation of wallet logic.

The device holds nothing. The wallet lives on a ramdisk, the seed is entered
each session (words or SeedQR), and power-off wipes everything.

## What Corky aims to achieve

A seed lives in three phases: it is **generated** once, **used** every time
you sign, and **at rest** in backups for decades (framing from jimbocoin;
the long version is [articles/two-backups.md](articles/two-backups.md)).
Corky is a position taken in each phase, and the guiding principle across
all three: **relocate trust to places where lying is hard.**

- **Generation: not our job, by design.** A compromised random number
  generator is undetectable from its output, so Corky has no entropy story
  at all — no on-device seed generation, ever. Seeds are born in the
  physical world (SeedPicker-style cards, or dice with cross-checked
  mapping) where the one unauditable step is performed by your own hands.
  Everything downstream is deterministic, so a lying device gets caught.
- **Use: the reference implementation, on radio-free silicon.** Signing
  runs Bitcoin Core's own wallet code, and v1 hardware is a compute module
  manufactured without wireless: "cannot transmit" outranks every
  software-disabled radio, including the wiped-laptop air gap that is only
  ever a promise. Statelessness replaces the secure element: a seized
  Corky is just electronics.
- **At rest: words are half a backup.** BIP39 words back up a *secret*; a
  descriptor backs up a *wallet* (path, script type, checksum). Corky
  exports public descriptors precisely so the paper half of your backup
  can exist, and its descriptor entry mode means a Core-native backup
  restores with zero guessing and zero shim.

The Core bet is stated as a bet: Core is at once the most reviewed wallet
code in existence and Bitcoin's most valuable infiltration target. Whether
one infiltration of the best-reviewed honeypot is likelier than a
coordinated compromise of several smaller vendors is genuinely unresolved;
multi-vendor multisig where no vendor is a quorum is the strongest
alternative answer, and it costs the complexity that its own advocates
concede. Corky holds the Core side with its eyes open.

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


## The trade-offs, before critics find them

**Corky's trusted computing base is large, on purpose.** SeedSigner and Krux
minimize total code: a tiny OS and a small reimplemented wallet library.
Corky maximizes review instead: a full Linux and a 500,000-line node binary,
because the wallet logic inside that binary is the most scrutinized wallet
code in existence. These are opposite philosophies and neither wins outright.
If "least code" is your definition of a signer, use SeedSigner; it is a good
one. Corky exists for people whose definition is "Core's code".

**The radios are still on the board.** The Pi Zero 2 W physically contains
WiFi and Bluetooth. Corky disables them in firmware and blacklists the
drivers, and the build docs describe removing the wireless front-end
component for hardware-level assurance. Until you do that step, call this
device radio-disabled, not air-gapped-by-physics. The Zero 1.3 has no radio
at all but cannot run Core's published binaries.

**No secure element, no PIN.** Same position as SeedSigner: statelessness is
the substitute. The device holds nothing worth extracting; the seed lives on
metal and in the room, not in the hardware.

**Fee display trusts the coordinator.** Core computes the fee from input
amounts the PSBT supplies. A malicious coordinator can misstate them. Every
air-gapped signer shares this limit; Corky prints it on the review screen.

**No anti-exfiltration protocol.** A malicious signing device can leak key
material through its signature nonces while producing valid-looking
transactions. Anti-exfil ceremonies (coordinator contributes randomness to
the nonce) defeat this, and Corky cannot implement one: Bitcoin Core
generates its own deterministic nonces (RFC6979) and exposes no hook for
coordinator randomness. Corky's answer to the same attack is transparency
instead of protocol: the signing code is Bitcoin Core's published,
reproducibly built binary, hash-verified at image build, not a black box
whose nonces you must distrust. These are different mitigations with
different failure modes; anti-exfil protects against a compromised *build*,
transparency protects against a compromised *vendor*. If anti-exfil is your
requirement, Corky cannot meet it today.

**One maintainer, pinned versions.** Each release is a pinned tuple
(OS image, Core version, front-end commit) that updates only by reflash.
That is the mitigation, not a cure, for a small project's maintenance risk.

## v1 scope (frozen)

Single-sig BIP84 (native segwit) and BIP86 (taproot). BIP39 with optional
passphrase. Seed entry in three modes: BIP39 words / SeedQR (default; uses
the shim), a raw **xprv**, or a **Core-native private descriptor** — the last
two arrive as a single static QR or typed text and never touch the shim at
all: pure Core from the first byte. (Descriptor mode is the answer to
Maxwell's BIP39 critique: the backup carries its own derivation path, script
type and checksum. Its trade-off: it is a printed/engraved QR, not stampable
steel words, and has no passphrase layer — the QR is the wallet.) PSBT in/out via **three channels**: animated QR;
a PSBT file on a USB stick in the OTG port; and — once the M3 RAM-resident
image lands — the boot microSD itself, SeedSigner-OS style (the whole OS runs
from RAM, so the card can be pulled and used as the PSBT sled). QR is the
tightest channel (photons only); the file channels have no size limit. All
three carry only PSBTs, and only Bitcoin Core ever parses them. If 512MB
cannot hold the RAM-resident image, v1 ships QR + USB and the microSD channel
waits for a bigger board (the fallback is written down in PLAN.md A-12).

Display: the SeedSigner+ hat — 2.8" ST7789 at 320×240 with d-pad and keys —
is the primary build (PLAN A-13b); the 1.3" ST7789 (240×240) remains the
pocket build. ST7789 and ILI9341 drivers are vendored from SeedSigner (MIT)
in `hw/vendor/`. A review screen showing
outputs, amounts and the fee as computed by Core from the coordinator-supplied
input amounts (an air-gapped signer cannot independently verify input amounts;
none can). Coordinator target: Sparrow.

Out of scope for v1: multisig, message signing, address explorer, dice entropy,
and on-device seed generation. Corky signs for seeds that already live on metal;
it deliberately has no entropy story of its own.


## Bitcoin Core + 1,902 lines: audit the whole device in an afternoon

Corky's pitch in numbers: everything that runs on the device is **Bitcoin
Core plus 1,902 lines of our Python** (1,379 excluding blanks and
comments). No line of ours performs elliptic-curve cryptography or parses
an untrusted PSBT — Core does both. Counted 2026-08-20; the table is the
audit map:

| Group | File | Lines | What it does / what it must never do |
|---|---|---|---|
| **Secret-touching, frozen** | [`shim/bip39_shim.py`](shim/bip39_shim.py) | 92 | BIP39 words → xprv. Stdlib hashing only. Hash pinned in [`SHIM_HASH`](SHIM_HASH) |
| | [`corky/codex32.py`](corky/codex32.py) | 350 | BIP93 encode/split/recover/verify, BIP's own reference arithmetic. Hash pinned in [`SHIM_HASH`](SHIM_HASH) |
| Signing plumbing | [`corky/signer.py`](corky/signer.py) | 195 | Drives Core over RPC. No cryptography |
| Transfer channels | [`corky/filechannel.py`](corky/filechannel.py) | 84 | PSBT files on a stick. Opaque bytes only |
| | [`corky/qrchannel.py`](corky/qrchannel.py) | 101 | BC-UR animated QR. One documented framing exception |
| | [`corky/seedqr.py`](corky/seedqr.py) | 65 | SeedQR digits → words. No keys touched |
| UI / device | [`corky/main.py`](corky/main.py) | 577 | The state machine. Traffic cop, no crypto |
| | [`corky/screens.py`](corky/screens.py) | 354 | PIL renders. Pixels only |
| | [`corky/hal.py`](corky/hal.py) | 84 | Buttons and display glue |
| **Total ours** | | **1,902** | |

Not counted as ours, and not asking for your trust in the same way:

- [`hw/vendor/`](hw/vendor/) — 2,219 lines vendored unmodified from
  SeedSigner (display drivers, BC-UR codec; MIT/BSD, attribution in each
  file). Integration points are ours; the code is theirs and upstream.
- [`tests/`](tests/) + [`shim/test_shim.py`](shim/test_shim.py) — 2,614
  lines of tests: more test than device. The campaign behind them: a
  90-cell signing matrix, 28 adversarial checks, property/fuzz suites
  cross-checked against independent implementations, per-module mutation
  kill-rates (74–100% on secret-touching modules, survivors individually
  triaged), and two real mainnet spends — one ECDSA
  ([`19d1180b…`](https://mempool.space/tx/19d1180b816e00c1d272a25bda3caf1dc466b70c24ba128aee25e1a32b61cf41)),
  one Taproot Schnorr keyspend
  ([`0ee96d29…`](https://mempool.space/tx/0ee96d2995f73768f071954c5b116fcb894847289a94dbe313e6b8615cd9981d)).
- Run everything: [`./run_tests.sh`](run_tests.sh) (fast suites), with
  `RUN_NODE=1` for the full bitcoind set.

The frozen files cannot drift silently:
[`tests/test_integrity.py`](tests/test_integrity.py) fails the suite if a
pinned hash stops matching, and the wordlist's tamper-refusal is itself
tested.

## Audit record

The codebase has passed four independent review lenses with converging
results (2026-08-18):

1. **Standards review** (Fowler smell baseline + the repo's own documented
   laws), three rounds — each round's findings strictly shallower and
   confined to strictly newer code; core verified clean in round 3.
2. **Spec review** against PLAN.md and the frozen v1 scope, three rounds —
   zero scope creep in all three.
3. **loupe** (benthecarman's security-scanning harness: LLM discovery
   agents that must self-validate findings with a PoC before submitting) —
   full clean sweep, 10/10 files, zero findings, including the shim.
4. **Cross-model verification** (codex) via loupe's verifier — nothing to
   verify, nothing dismissed.

Fixes driven by the first two lenses are in the git history (satoshi-level
Decimal handling on the review screen, paged output review gated on every
page being seen, dev-mode seed-frame redaction, fee-unknown refusal, and
more — see commits e23982a, c3b9fdf, 30b3164). Running loupe also
surfaced two bugs in loupe itself; proven patches are staged at
../loupe-contrib pending a decision to send upstream. An empty findings
table from a scanner we watched work is evidence; an empty table from a
scanner that never ran is not — we hit both and learned to tell them
apart.

## Status

Planning complete (see [PLAN.md](PLAN.md), two devil's-advocate rounds).
Everything provable without hardware is proven on a dev machine against
Core v31.1: the shim (all official vectors), the full signing pipeline on
regtest (QR-channel equivalent and both file formats of the file channel),
address derivation against the published BIP84/BIP86 vectors, and the screen
set rendered at both display resolutions. Next gate: **M0** — measured proof
that wallet-only bitcoind fits and signs on the Zero 2 W's 512MB
(`m0/FLASH.md`).

## Build gates

| Gate | Deliverable | Pass condition |
|---|---|---|
| M0 | bitcoind wallet-only on the Zero 2 W (pocket build; sizes the M3 RAM image) | signs stress PSBT; peak RSS recorded; ≥100MB headroom |
| M1 | QR round trip vs Sparrow watch-only, testnet | fee/outputs match Sparrow; signed PSBT broadcasts |
| M2 | stateless UI on the LCD hat | power-on→ready < 90s; power cycle provably wipes |
| M3 | hardened reproducible image | read-only root; radios dead; image hash reproducible |
| M4 | mainnet trial | small-sats spend from a metal-backed seed |
