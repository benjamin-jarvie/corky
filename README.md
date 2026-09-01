# Corky

**Core's keys, nothing kept.**

Corky is a stateless, air-gapped Bitcoin signing device built from DIY
general-purpose hardware, in the same tradition as SeedSigner (which uses a
radio-free Raspberry Pi Zero 1.3, or a Zero 2 W). Corky's primary build is a
radio-free Raspberry Pi CM4 Lite, a camera, and the SeedSigner+ display
hat; a Pi Zero 2 W pocket build exists too. Corky has one difference that is
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

- **Generation: cards and dice by default, Bitcoin Core by choice.** A
  compromised random number generator is undetectable from its output, so
  Corky writes no RNG of its own and ships none: no `os.urandom`, no
  `random`, no `secrets`, enforced by a test. The recommended path is
  unchanged. Seeds are born in the physical world (SeedPicker-style cards,
  or dice with cross-checked mapping) where the one unauditable step is
  performed by your own hands, and everything downstream is deterministic,
  so a lying device gets caught. One opt-in tool sits beside that: Corky
  can ask **Bitcoin Core** to generate a key, in a throwaway wallet it then
  uses for signing, and hand you Core's own master xprv as the backup,
  read verbatim from Core's descriptors (PLAN A-19) — key generation and
  usage exactly as a Core wallet. That is
  a choice about who you trust with software entropy, not a verification
  win — Core's RNG is no more auditable at runtime than anyone else's, it
  is simply the most reviewed counterparty on offer. Core cannot make BIP39
  words and Corky will not invent them.
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


## The freedom property

The 2026 Coldcard incident taught the market a lesson bigger than one
device: the rarest property in hardware custody is not a feature, it is
independence. As one long-time Coldcard user put it after the incident,
what was lost was a device that never required the vendor's app to
generate keys, sign, or update firmware, and never leaked an xpub to a
vendor server at setup: "you did not depend on Coinkite in any way to
actually use your device after you bought it from them."

Corky has that property structurally, because there is no vendor in the
loop at all:

- **Key generation** needs no app and no server: cards, dice, words, a
  codex32 share set, or Bitcoin Core's own RNG on the device.
- **Signing** speaks PSBT files and BC-UR QR codes: any coordinator,
  any decade.
- **"Firmware" updates** are a pinned image you build and flash
  yourself, from this repo, from a fork, or never. No update server
  exists. Nothing phones home because there is nothing to phone.
- **Nobody learns your xpubs**: setup touches no network by
  construction.

If this project disappeared tomorrow, every Corky keeps working
forever, and this repo builds new ones. The honest asterisk: the same
commentator excluded DIY devices from consideration, and Corky is one.
That is the price of the property today: Corky is DIY while we perfect
it. An assembled device would change the labor, not the architecture,
and may come later.

## The trade-offs, before critics find them

**Corky's trusted computing base is large, on purpose.** SeedSigner and Krux
minimize total code: a tiny OS and a small reimplemented wallet library.
Corky maximizes review instead: a full Linux and a 500,000-line node binary,
because the wallet logic inside that binary is the most scrutinized wallet
code in existence. These are opposite philosophies and neither wins outright.
If "least code" is your definition of a signer, use SeedSigner; it is a good
one. Corky exists for people whose definition is "Core's code".

**Radios: the CM4 has none, the Zero 2 W build removes them by hand.** The
CM4 Lite (v1 hardware, PLAN A-15) was chosen because it is manufactured
without wireless silicon: nothing to disable, nothing to remove. The Pi
Zero 2 W pocket build carries WiFi and Bluetooth hardware on the board,
and the build instruction is to remove that hardware: desolder the
wireless front-end component before the device signs anything real. That
is soldering work (iron or hot-air station). If you will not solder,
build the CM4 version. The image also disables the radios in firmware
and blacklists the drivers, and the release image ships with no network
stack; these are backup layers and they do not replace removal. The
claim has two tiers. Front-end removal makes the device radio-removed.
Removing the whole wireless chip as well earns the claim "air-gapped by
physics", the same property the CM4 build has by manufacture.

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

**No attestation, no tamper resistance.** A secure-element vendor can
argue you cannot know that what runs on any device is what you loaded,
and Corky has no cryptographic attestation to answer with. Our answer is
relocation, not denial: the hardware is commodity silicon with nothing
wallet-shaped to intercept in a supply chain, and the software is a
pinned, hash-published image you flash yourself, so "what runs" narrows
to "what you flashed onto a generic board." The SoC itself remains a
black box, as it does for every device on the market. If hardware
attestation is your requirement, a secure-element device serves it and
Corky does not.

**"Isn't this just Bitcoin Core on a computer?"** No, and the
distinction is the whole design: running Core on a networked
general-purpose machine as a wallet is exactly what security
practitioners rightly call reckless. Corky is Core as a single-purpose,
stateless, offline cold signer: no network stack in the release image,
no radios in the silicon, no persistence, one job. The principles the
industry defends — risk isolation, attack-surface minimization,
dedicated devices for keys — are this device's shape. The remaining
honest gap against purpose-built hardware is physical: a general-purpose
OS and no secure element, mitigated by statelessness (a seized Corky
holds nothing) rather than by tamper-resistant silicon.

**Open source is not, by itself, a security claim.** Source
availability is an inspection property, and "many eyes" is a hope, not a
threat model: nobody reviews code for free, and we do not pretend
otherwise. Corky's trust story, in honest order: first, the cryptography
is Bitcoin Core's and the reviewed reference implementations', already
the most-reviewed lines in Bitcoin. Second, our 354 secret-touching
lines are small enough for one person to read in an afternoon;
smallness, not testing, is what makes real review possible. Third, the
test suite's fault-detection is mutation-measured per module so you can
judge the tests instead of taking them on faith, and the signing path is
proven on mainnet; these numbers measure verification depth against the
failures we modeled, and an attacker is not limited to our imagination.
Fourth, no independent security audit exists yet. Until one does, that
is a named open trust, and this section exists so nobody carries it
unknowingly.

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

Out of scope for v1: multisig, message signing, address explorer, and dice
entropy. Corky signs for seeds that already live on metal, and writes no
randomness of its own; the one generation path it offers (v1.1, opt-in)
asks Bitcoin Core for the entropy and gives you a codex32 string to write
down. See PLAN A-19 for the tradeoff, stated plainly.


## The code, in layers: Core + 354 lines that matter + a body

Corky is Bitcoin Core plus a small body of our Python. The body is
layered so the number that matters for trust stays tiny. Counted
2026-08-20 as lines of functional code (blanks and comments excluded);
file links are the audit map.

**Layer 1 — transforms secret material. 354 lines. Frozen, hash-pinned.**
The only code of ours that ever computes on a seed or key. Stdlib only,
no elliptic-curve math anywhere, hashes pinned in
[`SHIM_HASH`](SHIM_HASH) and enforced by
[`tests/test_integrity.py`](tests/test_integrity.py):

| File | Code lines | Does |
|---|---|---|
| [`shim/bip39_shim.py`](shim/bip39_shim.py) | 54 | BIP39 words → xprv |
| [`corky/codex32.py`](corky/codex32.py) | 260 | BIP93: the BIP's own reference arithmetic |
| [`corky/seedqr.py`](corky/seedqr.py) | 40 | SeedQR digits → words |

Enter by descriptor or xprv and even this layer is bypassed: pure Core.
Words-only users trust Core + 54 lines — the original pitch, still true.

**Layer 2 — sees secrets, computes nothing with them. 985 lines.**
The device's body: menus, screens, buttons. It routes and displays
secret material during entry but performs no cryptography on it.
[`corky/main.py`](corky/main.py) (556) ·
[`corky/screens.py`](corky/screens.py) (367) ·
[`corky/splash.py`](corky/splash.py) (13) ·
[`corky/hal.py`](corky/hal.py) (49).

**Layer 3 — never touches secrets at all. 246 lines.**
[`corky/signer.py`](corky/signer.py) (138) drives Core over RPC;
[`corky/filechannel.py`](corky/filechannel.py) (45) and
[`corky/qrchannel.py`](corky/qrchannel.py) (63) move PSBTs as opaque
bytes — Core is the only parser, by law
([PLAN.md A-11](PLAN.md)).

**Total functional code: 1,585 lines** (2,285 with blanks/comments).
A bug in layers 2–3 can annoy you; it cannot leak what it never
algebraically touches.

**Test code: 2,651 lines — none of it ships on the device.**
[`tests/`](tests/) + [`shim/test_shim.py`](shim/test_shim.py). More test
than device is deliberate: a 90-cell signing matrix, 28 adversarial
checks, 9 scripted device sessions, property/fuzz suites cross-checked against independent
implementations, per-module mutation kill-rates — 74–100% on secret-touching modules,
and 25%→81% on the state machine after mutation-driven test writing
there exposed and fixed a real bug (typed codex32 entry could never
type the ms1 separator; the flow was unusable until session G existed) —
survivors individually triaged, and two real
mainnet spends — ECDSA
([`19d1180b…`](https://mempool.space/tx/19d1180b816e00c1d272a25bda3caf1dc466b70c24ba128aee25e1a32b61cf41))
and a Taproot Schnorr keyspend
([`0ee96d29…`](https://mempool.space/tx/0ee96d2995f73768f071954c5b116fcb894847289a94dbe313e6b8615cd9981d)).
The README's own numbers are tested too:
[`tests/test_readme_claims.py`](tests/test_readme_claims.py) fails the suite
if any count above drifts from the tree or a link goes dead. Run it all:
[`./run_tests.sh`](run_tests.sh) (`RUN_NODE=1` adds the
bitcoind suites).

**Vendored, not ours: 2,219 lines** in [`hw/vendor/`](hw/vendor/) —
SeedSigner's display drivers and BC-UR codec, unmodified, MIT/BSD with
attribution. Theirs to audit upstream; only the integration points are
ours.

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
| M4 | mainnet trial | software path proven on real funds (ECDSA + Taproot, both confirmed); on-device trial pending hardware |
