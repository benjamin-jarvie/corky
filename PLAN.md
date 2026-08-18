# Corky: a stateless, air-gapped PSBT signer that runs Bitcoin Core's wallet
*Plan v1 → devil's advocate → v2 → devil's advocate → v3. 2026-08-17.*

## Review outcome (Ben, 2026-08-17)

- Approved: hardware on hand, Sparrow as v1 coordinator, v1 scope freeze.
- Shim disclosure: **explicit, not fine print.** The README leads with it (A-6 superseded).
- Name: **Corky.** Tagline: *Core's keys, nothing kept.*
- Shim built and passing all official vectors (`shim/test_shim.py`). Next gate: M0.

## Amendments after review (Ben, 2026-08-17, second pass)

- **A-10: dual transfer channels.** PSBT in/out via animated QR *and* via file
  on a USB stick (OTG port). The boot microSD cannot be hot-swapped, so
  file transfer is USB, Coldcard-style. QR remains the reference channel;
  USB removes the size ceiling. Both are opaque-PSBT-only.
- **A-11: language decision — Python, with a law.** Rust runs fine on the Pi
  (aarch64 is first-class; no compile theater), but it hardens the wrong
  layer: all crypto and all untrusted-input parsing live in Bitcoin Core
  regardless. Rust would also force the shim onto crates.io dependencies,
  destroying its stdlib-only claim, and the Pi camera/LCD ecosystem is
  Python-mature (SeedSigner's own drivers). Decision: Python for v1, under
  this frozen rule: **Corky's code never parses untrusted bytes. PSBTs pass
  through as opaque strings; Bitcoin Core is the only parser.** The zbar QR
  decoder (C, both languages) gets length caps and charset checks before its
  output is used. A Rust front-end rewrite is noted as a legitimate v2
  hardening step once v1 is a working reference.
- **A-12: hot-swap microSD channel is now a v1 requirement (Ben, second pass).**
  The mechanism is SeedSigner OS's trick: the operating system runs entirely
  from RAM after boot, so the boot microSD can be removed and reused as the
  PSBT sled (`/mnt/microsd` watcher). For Corky this means a minimal
  RAM-resident image (buildroot-style) carrying bitcoind + Python + the UI.
  *Devil's advocate, on the record:* this is now the riskiest item in the
  project. The rootfs, bitcoind, the ramdisk datadir and the UI must all
  share 512MB; a full Raspberry Pi OS cannot run from RAM at this size, so
  M3 becomes a real OS-image engineering task, not a hardening pass.
  Mitigations: M0 measures bitcoind's true footprint first; development
  through M2 stays on stock Raspberry Pi OS with the USB-stick channel
  (which remains in v1 as the fallback transfer path); the RAM-resident
  image is developed as M3 with a defined fallback (v1 ships with USB-only
  transfer if 512MB cannot hold the RAM image; microSD hot-swap then waits
  for a 1GB-class board). Side benefit if it lands: statelessness becomes
  structural — the OS itself is immutable and nothing can persist anywhere.
- **A-13: bigger display in v1 (Ben, second pass).** Target is the
  SeedSigner-Plus-class 2.4" ILI9341 at 320×240 (driver vendored from
  SeedSigner at `hw/vendor/ili9341.py`; the 3.5" ILI9486 is named in
  SeedSigner's settings but has no driver in their main repo yet). The UI
  renders resolution-independent PIL frames and asks the driver for its
  size, so the 1.3" ST7789 stays supported as the compact build.
  **SUPERSEDED by the A-13b finding below.**
- **A-13b: the display is Ben's own SeedSigner+ hat (resolved 2026-08-17).**
  Ben stocks the SeedSigner+ (Bitcoin Butlers shop product `seedsigner-plus`)
  and holds its PCBs: **2.8" IPS, 320x240, ST7789**, a standard 40-pin GPIO
  HAT with on-board d-pad/buttons, USB-C power input and microSD extender.
  It runs stock SeedSigner firmware with only the `st7789_320x240` display
  setting — which proves the buttons use the same GPIO map as the 1.3" hat
  and the controller is the ST7789 already vendored. Driver work = the
  320x240 init variant (width/height swap + 90-degree rotation, per
  SeedSigner's display factory). Nothing to buy for the display; the
  Pimoroni Display HAT Mini is off the list. Verify on arrival of the CM4:
  (1) power from ONE USB-C only (hat back-feeds 5V via GPIO; the carrier has
  its own input); (2) camera uses a STANDARD-width CSI ribbon on the carrier,
  not the Plus kit's Zero-width ribbon; (3) enclosure fit of the metal Plus
  case over the carrier stack.
- **A-14: Core-native seed entry (Ben, 2026-08-17, third pass).** Three input
  modes, in order of purity: (1) **private descriptor via static QR** — pure
  Core, self-describing (path + script type + checksum), no shim, no
  hardcoded derivation; (2) **xprv via static QR or text** — pure Core,
  Corky applies BIP84/86; (3) **BIP39 words / SeedQR** — the shim path,
  default, because the world's backups (including Ben's) are steel word
  plates. Both new formats fit a single static QR (~112 / ~150 chars) and
  base58check makes a bad scan fail loudly. Stated trade-offs: descriptor
  backups are print/engrave media, not stampable words; no BIP39-style
  passphrase layer on a raw xprv (the QR IS the wallet — say so on screen).
  Strategic note: mode 1 makes Corky the first signer with a shim-free,
  fully Core-native path; candidate default for onboarding fresh wallets.

- **A-15: primary board is now the CM4 (Ben, 2026-08-17, fourth pass).**
  **Raspberry Pi CM4 Lite, no-wireless, 2GB** (CM4002000; 4GB CM4004000 an
  acceptable substitute) on a **Waveshare CM4-IO-BASE-B** carrier. Rationale:
  no radio by manufacture (kills the air-gap critique with physics, no
  rework) and 2GB removes the A-12 RAM-resident-OS risk entirely. Display:
  **Pimoroni Display HAT Mini** (2.0" ST7789 320x240, 4 buttons, HAT form) on
  the carrier's standard 40-pin header — pin remap vs the vendored driver to
  be prepped before it arrives. The Zero 2 W becomes the dev mule and the
  pocket build in the existing SeedSigner case; M0's 512MB question now only
  gates the pocket build, not v1. Existing Zero-format spine PCBs are
  electrically compatible with the carrier's header but mechanically
  Zero-shaped; pending Ben identifying the exact PCB. UI must support
  4-button (no joystick) navigation as the primary scheme.

- **A-16: dev image vs release image (2026-08-18).** Two distinct images per
  release, both hashed in the pinned tuple. DEV: SSH enabled over the
  carrier's wired Ethernet (no radio involved; the cable is the visible,
  removable dev channel), HDMI console. RELEASE: no SSH server, network
  services masked, Ethernet driver blacklisted (stack removed entirely once
  M3's RAM-resident image lands). The air-gap claim attaches to the release
  image only. Desoldering the RJ45 remains a documented option for a
  paranoid build (through-hole part; far easier than radio rework).
- **A-17: UI design reference — Bitcoin Core App (2026-08-18).** The QML
  interface at bitcoincore.app (repo: bitcoin-core/gui-qml, qt6 branch) is a
  COMMUNITY project with the Bitcoin Design community — it sits in the
  bitcoin-core GitHub org but is NOT an official Bitcoin Core team product;
  record it accurately. Use: mine its transaction-review and send-flow
  patterns (Bitcoin Design Guide lineage, MIT) when refining Corky's review
  screens, so Corky's UI reads like the Core family. Watch item: if it grows
  PSBT-by-QR/file coordinator flows, the full stack becomes Core node +
  Core App coordinator + Corky signer.

## Post-v1 todo / hardening backlog (from the round-2 audit, 2026-08-18)

- **Secret hygiene: xprv-bearing RPC params travel as bitcoin-cli argv**,
  visible in process listings during the seconds of import. Single-user
  device, but move secret-bearing calls to `bitcoin-cli -stdin` at M2.
- Passphrase and typed xprv/descriptor entry have no on-device UI yet
  (dev-mode args only); build both text-entry screens at M2 alongside the
  camera. Testnet subdir map assumes testnet3; revisit if Core defaults to
  testnet4. README still names the 2.4" ILI9341 as primary — supersede with
  A-13b wording at next README pass.

## Post-v1 todo

- **Codex32 (BIP93) seed entry** as a fourth input mode: bech32 seed shares,
  k-of-n recovery, hand-verifiable checksums; authored by Wuille/O'Connor.
  FractalEncrypt has a full SeedSigner implementation in progress
  (FractalEncrypt/FractalEncrypt_seedsigner, Codex32_Implementation branch).
  **Deliberately deferred until Fractal publishes — do not front-run his
  work (Ben, 2026-08-17).** Revisit after his release; his QR share specs
  would be the compatibility target.
- Anti-exfil: not implementable via Core's RPC today (no nonce hook in
  walletprocesspsbt); documented as a stated trade-off in the README. Watch
  upstream Core for any sign-to-contract / anti-exfil RPC support.

## The idea in three sentences

Take SeedSigner's hardware (camera, small screen, no persistent secrets) and replace its
signing brain (embit, a Python reimplementation) with Bitcoin Core itself, running
wallet-only and offline. The device scans a PSBT as QR, shows the fee and outputs
computed by Core, signs with `walletprocesspsbt`, and returns the signed PSBT as QR.
Nothing is retained: the wallet lives on a ramdisk and dies at power-off.

**Why:** every DIY signer today trusts a rewrite of Bitcoin's wallet logic. This device
trusts the most reviewed Bitcoin code that exists, on hardware you assemble yourself.

## Fixed decisions (from Ben)

- Board: **Raspberry Pi Zero 2 W** (official aarch64 Core binaries run; no cross-compile).
- **Stateless.** No keys on the SD card, ever. SeedSigner's security model, Core's code.
- Existing kit reused: SeedSigner cases, WaveShare 1.3" LCD hat, Pi camera, metal seed plates.

---

## Plan v1

### Hardware
1. Pi Zero 2 W in the existing SeedSigner case with the existing LCD hat and camera.
2. Radios disabled in firmware: `dtoverlay=disable-wifi`, `dtoverlay=disable-bt` in
   `config.txt`, plus blacklisted kernel modules and disabled services.

### Software stack
1. Raspberry Pi OS Lite **64-bit** (needed for the official `aarch64-linux-gnu` Core binary).
2. Official Bitcoin Core release binary, signatures verified during image build.
3. `bitcoind` config: `-networkactive=0 -listen=0 -dbcache=4 -maxmempool=5
   -rpcthreads=1 -blocksonly=1`, datadir on a **tmpfs ramdisk**.
4. A thin Python front end (~300–500 lines): screen menus, camera QR scan (zbar),
   QR display (animated for large PSBTs), and RPC calls to localhost. It performs
   **no cryptography**.

### Session flow (stateless)
1. Power on. bitcoind starts against a fresh ramdisk datadir.
2. User enters the BIP39 seed (SeedSigner-style word entry or SeedQR scan).
3. Mnemonic → xprv conversion, then `createwallet(blank=true)` +
   `importdescriptors` with private descriptors (BIP84/86 paths).
4. Scan PSBT from coordinator (Sparrow, Specter, or Core itself).
5. `decodepsbt` / `analyzepsbt` → screen shows outputs, amounts, **fee** (Core's numbers).
6. User confirms → `walletprocesspsbt` → signed PSBT rendered as animated QR.
7. Power off. Ramdisk gone; device holds nothing.

### Milestones
- M0: bitcoind boots and signs a testnet PSBT over RPC on the Zero 2 W (no UI). Measure RAM.
- M1: full QR round trip with Sparrow watch-only, testnet.
- M2: stateless flow (seed entry each session), UI on the LCD hat.
- M3: hardening (radio kill verification, reproducible image build), mainnet trial with small sats.

---

## Devil's advocate, round 1

**DA-1. "Core's logic only" is already broken at step 3.** Bitcoin Core has no BIP39.
The mnemonic→xprv step must come from somewhere, and if that somewhere is embit, the
project's thesis collapses: the seed derivation, the root of everything, is the exact
reimplementation we set out to remove. This is the strongest objection to the whole design.

**DA-2. 512MB is asserted, not measured.** A 64-bit OS has a bigger memory footprint than
32-bit, bitcoind's minimal RSS on this config is undocumented, and the ramdisk *also*
comes out of the same 512MB. If bitcoind plus OS plus tmpfs plus the Python UI does not
fit, the plan dies at M0 and the milestones above pretend otherwise.

**DA-3. Seed entry each session is the attack surface.** Statelessness means typing or
scanning the seed on every use. A tampered image or a hidden persistence path (swap,
journald on SD, core dumps) could leak it. SeedSigner mitigates with a tiny auditable
codebase and no writable persistence during operation; this design boots a full Linux
with a writable root filesystem.

**DA-4. Why does this exist? Sparrow + SeedSigner already works.** Steelman the null
hypothesis: embit is small, heavily used, and easier to audit end-to-end than bitcoind.
"More reviewed code" is not automatically "smaller attack surface": bitcoind is two
orders of magnitude more code, and most of its review effort targets consensus, not
the wallet. The honest claim must be narrower.

**DA-5. Radio disable in firmware is a config line, not an air gap.** `config.txt` lives
on the SD card; anyone (or any compromise at image-build time) can re-enable WiFi by
editing a text file. The Zero 1.3's advantage was physics. Calling this device
"air-gapped" without a hardware step overstates it.

**DA-6. Blank-datadir chain assumptions.** With no chain, Core cannot check that the
PSBT's inputs exist or that locktimes/sequences make sense against the tip. Fine, all
signers share this limit, but `analyzepsbt`'s fee number depends entirely on the
coordinator-supplied `witness_utxo` amounts. A malicious coordinator can lie about the
fee to any air-gapped signer. Do not market fee display as stronger than it is.

## Amendments → Plan v2

**A-1 (answers DA-1).** No embit, no external crypto library. BIP39→seed is
PBKDF2-HMAC-SHA512 (Python stdlib `hashlib.pbkdf2_hmac`); seed→xprv is one
HMAC-SHA512 with key `"Bitcoin seed"` plus Base58Check encoding: about 60 lines of
stdlib-only code, no elliptic-curve math anywhere, verifiable line-by-line against the
BIP32/BIP39 test vectors, frozen once written. All EC operations (child key derivation,
signing) happen inside Core via the imported xprv descriptor. The trust statement
becomes exact: *stdlib hashing for seed decode, Core for every key operation.*
Also support scanning the existing SeedQR format so Ben's current backups work as-is.

**A-2 (answers DA-2).** M0 is promoted to a **go/no-go gate with numbers**: boot the
64-bit Lite image, run bitcoind on the stated flags, import a descriptor wallet, sign a
1000-input stress PSBT, and record peak RSS and free memory. Mitigations pre-planned:
zram instead of disk swap (never SD swap: seed material must not touch flash),
`rpcthreads=1`, and if 64-bit truly does not fit, the documented fallback is the same
design on a Pi 3A+/CM4-based board, not a return to cross-compiling.

**A-3 (answers DA-3, DA-5).** Hardening becomes part of the design, not a milestone tail:
read-only root filesystem (overlayfs), no swap-to-disk ever, journald to tmpfs,
core dumps off, and the radio kill done **twice**: firmware overlay *and* the physical
option documented (the Zero 2 W wireless front-end component is known and removable;
offer it as the "1.3-grade" assurance step for those with a hot-air station, with the
firmware-only path as standard). Image built reproducibly with published hashes.

**A-4 (answers DA-4).** Rewrite the claim. Not "smaller attack surface" but a **different
trust root**: SeedSigner asks you to trust embit's reimplementation of wallet logic;
this asks you to trust Bitcoin Core's implementation of wallet logic. Both are honest
choices; this project exists so the second one is *available* on DIY hardware, and as
a teaching artefact (the signer speaks the same RPCs as the node). Also the practical
win: descriptor semantics, PSBT handling and sighash logic are bit-for-bit the same
code Core uses, so coordinator/signer disagreements vanish by construction.

**A-5 (answers DA-6).** The fee screen states its own epistemics: fee is computed by
Core *from coordinator-supplied input amounts*. Show the fee **and** the total input
sum, and print the one-line warning SeedSigner users already know. No overclaiming.

---

## Devil's advocate, round 2

**DA-7. The 60-line stdlib shim still writes itself into the TCB.** Sixty lines with a
frozen hash and test vectors is defensible, but who reviews it? If the answer is "Ben
and Claude", the project's core marketing claim ("you trust Core, not a rewrite")
carries an asterisk that must be printed, not hidden.

**DA-8. Read-only root vs stock Raspberry Pi OS drift.** Overlayfs-on-Lite is a
well-trodden path, but every OS update reopens the hardening questions. A general-purpose
OS is the price of running Core; fine, but the image build must pin versions and the
project must state that its security posture is "hardened general-purpose Linux",
which is below SeedSigner's "no OS persistence to speak of" and above a laptop.

**DA-9. Boot time and UX honesty.** 64-bit Lite boot plus bitcoind init plus seed entry
plus descriptor import will plausibly cost 60–120 seconds before the first scan. For a
cold-storage tool used monthly this is fine, but if the real UX lands at three minutes,
users will stop powering off between steps, which erodes statelessness in practice.
Measure at M2 and set a hard budget.

**DA-10. Scope creep is the likeliest death.** Multisig registration, taproot script
paths, message signing, dice entropy, passphrase support: each is a reasonable ask and
each doubles the UI. SeedSigner took years to cover this surface. Version 1 must refuse
almost everything.

**DA-11. Core version upgrades.** Each Core release can change RPC fields
(`analyzepsbt`/`decodepsbt` output has changed before). Pin one Core version per image
release; the front end targets exactly that version. Never "latest".

## Amendments → Plan v3 (the reviewable plan)

**A-6 (answers DA-7).** The shim ships in the repo as a single file with its SHA256 in
the README, its test-vector run in CI, and an explicit invitation for external review.
The asterisk is printed. Long-term option noted: Sjors Provoost's Rust BIP39 tool
(bitcoin PR #32115) as an alternative shim from a Core contributor.

**A-7 (answers DA-8, DA-11).** One pinned tuple per release:
{RPi OS Lite 64-bit image hash, Core version + binary hash, front-end commit}.
The image is built by script from those pins. No apt upgrades on-device; updating means
reflashing. This is also what makes the build reproducible and teachable.

**A-8 (answers DA-9).** Hard UX budget: **power-on to ready-to-scan in under 90 seconds**
(bitcoind starts during seed entry, so the human is the critical path). If M2 misses
the budget, cut boot (systemd mask-list, no HDMI probe, quiet kernel) before touching
the security posture.

**A-9 (answers DA-10).** **V1 scope, frozen:** single-sig BIP84 and BIP86, BIP39 with
optional passphrase, SeedQR in, PSBT in/out via animated QR (UR2 for Sparrow
compatibility), fee/output review screen. Explicitly out of v1: multisig, message
signing, address explorer, dice entropy, on-device seed generation. (Seed generation
stays out precisely so the device never needs an entropy story; it signs for seeds
that already live on metal.)

### Final build sequence

| Gate | Deliverable | Pass condition |
|---|---|---|
| **M0** | bitcoind wallet-only on Zero 2 W, headless | Signs stress-test PSBT; peak RSS recorded; ≥100MB headroom |
| **M1** | QR round trip vs Sparrow watch-only, testnet | Fee/outputs on screen match Sparrow; signed PSBT broadcasts |
| **M2** | Stateless UI on LCD hat | Power-on→ready < 90s; power cycle provably wipes (RAM/ramdisk audit) |
| **M3** | Hardened reproducible image | Read-only root, radios dead (`rfkill` + no wlan0), image hash reproducible on second machine |
| **M4** | Mainnet trial | Small-sats spend from a metal-backed seed, end to end |

### Cost
Zero build cost beyond what is on hand if a spare Zero 2 W exists; otherwise one
Zero 2 W (~NZ$40). Everything else (case, hat, camera, SD) is SeedSigner kit already owned.

### What I need from Ben at review
1. Confirm a Zero 2 W is on hand (or I list one to order) and which coordinator is the
   v1 target (Sparrow assumed).
2. Approve the v1 scope freeze (A-9), especially *no on-device seed generation*.
3. Approve the shim asterisk (A-6): 60 lines of stdlib hashing sit outside Core.
4. Name the project.
