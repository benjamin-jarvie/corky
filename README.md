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
each session (an xprv or a descriptor), and power-off wipes everything.

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
  restores with zero guessing.

The Core bet is stated as a bet: Core is at once the most reviewed wallet
code in existence and Bitcoin's most valuable infiltration target. Whether
one infiltration of the best-reviewed honeypot is likelier than a
coordinated compromise of several smaller vendors is genuinely unresolved;
multi-vendor multisig where no vendor is a quorum is the strongest
alternative answer, and it costs the complexity that its own advocates
concede. Corky holds the Core side with its eyes open.

## What you are trusting — stated plainly, not in fine print

**Nothing in Corky touches your key.**

That used to be almost true. Corky carried one translator, because Bitcoin
Core does not read BIP39 seed words and its developers have said it never
will, so something had to turn words into the xprv Core imports. PLAN A-22
removed it. This build cannot read a seed phrase at all.

What is left is a body of code that draws screens, reads buttons, and carries
bytes between you and Bitcoin Core:

- **No cryptographic primitive is imported anywhere in `corky/`.** Not
  `hashlib`, not `hmac`, not `secrets`, not any curve library. Enforced by
  [`tests/test_integrity.py`](tests/test_integrity.py), which fails if one
  reappears.
- **Keys reach Core three ways and Corky transforms none of them.** Core
  generates one with its own RNG; or you supply an **xprv** or a
  **descriptor**, typed or scanned, which Corky hands to `importdescriptors`
  as the string you gave it.
- Every operation on a key — deriving children, checking the transaction,
  signing — happens inside Bitcoin Core.

**The cost, said plainly.** You cannot bring a 12 or 24 word seed phrase.
Nobody can move here from an existing hardware wallet by typing their words.
Your backup is Core's 111-character master xprv, and it cannot be split into
shares. If that is unacceptable, the `lab` branch keeps the translator,
codex32 and SeedQR, and is meant for people who read code.

Corky's claim is not "trustless". It is: **you trust Bitcoin Core's wallet
implementation instead of a rewrite of it, and nothing else of ours computes
on your key, because there is no such code to compute with.**

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
passphrase. Key entry in two forms: a raw **xprv** or a **Core-native
private descriptor**, each arriving as a static QR or typed on the grid,
and neither transformed by anything of ours at
all: pure Core from the first byte. (Descriptor mode is the answer to
Maxwell's BIP39 critique: the backup carries its own derivation path, script
type and checksum. Its trade-off: it is a printed/engraved QR, not stampable
steel words, and has no passphrase layer — the QR is the wallet.) PSBT in/out via **three channels**: animated QR, which carries fountain parts past the pure cycle so a frame the scanner cannot read never strands a transfer;
a PSBT file on a USB stick in the OTG port; and — once the M3 RAM-resident
image lands — the boot microSD itself, SeedSigner-OS style (the whole OS runs
from RAM, so the card can be pulled and used as the PSBT sled). QR is the
tightest channel (photons only); the file channels cap a PSBT at 4MB
(`filechannel.MAX_PSBT_BYTES`). All
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

**Set Sparrow's QR density to Low.** Sparrow's default, Normal, packs up to
775 characters into one frame, which is an 81x81 QR. Measured against the
device's own decoder at its 512x384 camera stream, that reads reliably only
when the code fills about 90 percent of the view; ordinary hand blur takes
whole frames out below that. Low tops out near 215 characters, a 45x45 code,
and reads from anywhere in the frame. Corky does not refuse large frames, so
holding the camera closer works too, but it says so on screen when it sees
them. Numbers and method: `tests/m1/legibility_rig.py`.

Out of scope for v1: multisig, message signing, address explorer, and dice
entropy. Corky signs for seeds that already live on metal, and writes no
randomness of its own; the one generation path it offers (v1.1, opt-in)
asks Bitcoin Core for the entropy and gives you a codex32 string to write
down. See PLAN A-19 for the tradeoff, stated plainly.


## The code, in layers: Core, and a body that never touches your key

Corky is Bitcoin Core plus a small body of our Python. The body is
layered so the number that matters for trust stays tiny. Counted
2026-08-20 as lines of functional code (blanks and comments excluded);
file links are the audit map.

**Layer 1 — transforms secret material. 0 lines.**
There is none. PLAN A-22 removed the BIP39 shim, codex32 and SeedQR from
this build: nothing here computes on a seed or a key. Keys reach Core
three ways and Corky transforms none of them — Core generates one with
its own RNG, or you supply an **xprv** or a **descriptor**, typed or
scanned, which Corky hands to `importdescriptors` as an opaque string.

That is not a claim about care taken. It is enforced:
[`tests/test_integrity.py`](tests/test_integrity.py) fails if any shipped
module imports `hashlib`, `hmac`, `secrets` or any curve library, or if
the words `pbkdf2`, `seed_to_xprv` or `Bitcoin seed` reappear anywhere in
[`corky/`](corky/).

The cost is real and deliberate: **this build cannot accept a 12 or 24
word seed phrase**, so nobody can bring words from an existing hardware
wallet, and a backup is Core's 111-character master xprv rather than
words. The `lab` branch carries the removed modules for people who want
codex32, BIP-85 and more, and merges `main` forward so every fix here
reaches it.

**Layer 2 — sees secrets, computes nothing with them. 1065 lines.**
The device's body: menus, screens, buttons. It routes and displays key
material during entry and backup but performs no arithmetic on it.
[`corky/main.py`](corky/main.py) (572) ·
[`corky/screens.py`](corky/screens.py) (423) ·
[`corky/splash.py`](corky/splash.py) (13) ·
[`corky/hal.py`](corky/hal.py) (57).

**Layer 3 — never touches secrets at all. 394 lines.**
[`corky/signer.py`](corky/signer.py) (165) drives Core over RPC;
[`corky/filechannel.py`](corky/filechannel.py) (45) and
[`corky/qrchannel.py`](corky/qrchannel.py) (184) move PSBTs as opaque
bytes — Core is the only parser, by law
([PLAN.md A-11](PLAN.md)).

**Total functional code: 1,459 lines** (2,462 with blanks/comments).
A bug in either layer can show you the wrong thing. Neither can compute
you the wrong key, because neither computes keys at all.

**Test code: 2,572 lines — none of it ships on the device.**
[`tests/`](tests/). More test
than device is deliberate: a 36-cell signing matrix, 15 adversarial
checks, 9 scripted device sessions, property and fuzz suites, per-module mutation kill-rates — 74–100% on secret-touching modules,
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

**Plus 86 checks against Sparrow itself**, which the count above excludes and
`run_tests.sh` does not run. [`tests/sparrow/`](tests/sparrow/) drives Sparrow
2.5.4's own library out of its sha256-verified release, so the PSBTs Corky
signs are the PSBTs Sparrow really builds: 38 interop checks across both script
types and eight transaction shapes, with Corky's review fee and outputs
compared to Sparrow's own to the satoshi, and 20 more that put a real PSBT
through the QR channel in both directions. [`tests/m1/`](tests/m1/) adds 28
covering the scan rules, and two rigs that measure whether each side can
actually read the other's screen. Both need a one-time `setup.sh`, and
`tests/m1` needs Rosetta on Apple Silicon.

**Vendored, not ours: 2,251 lines** in [`hw/vendor/`](hw/vendor/) —
SeedSigner's display drivers and BC-UR codec, unmodified, MIT/BSD with
attribution. Theirs to audit upstream; only the integration points are
ours. The home icons are a six-glyph subset of Font Awesome Free Solid
([`hw/vendor/fonts/`](hw/vendor/fonts/), CC BY 4.0 / SIL OFL, attributed
in that directory's NOTICE); no other glyphs ship.

## How this is tested

`RUN_NODE=1 ./run_tests.sh` is the gate. [TESTING.md](TESTING.md) records the
rules that came out of the 2026-09-02 two-axis review, after a feature shipped
in a state where it could not work past a fully green suite: every input
surface needs a real-data round-trip test, the shipping branch must be the one
under test, a cost or count claim must come from a measurement, and
"needs hardware" is a claim that needs checking before anything is deferred
on it. [ISSUES.md](ISSUES.md) records what those rules have caught so far, and
lists what is still open: audit items D17 and D18, on error reporting.

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
