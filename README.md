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

The device holds nothing. The wallet lives on a ramdisk, the key is entered
each session, and power-off wipes everything. A key arrives as an **xprv**,
which is your private key written the standard way, or as a **descriptor**,
which is that key plus the rules for deriving addresses from it.

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
  or dice with cross-checked mapping) where the one unverifiable step is
  performed by your own hands, and everything downstream is deterministic,
  so a lying device gets caught. One opt-in tool sits beside that: Corky
  can ask **Bitcoin Core** to generate a key, in a throwaway wallet it then
  uses for signing, and hand you the master private key itself as the backup,
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

**Nothing in Corky computes on your key. Some of it carries and draws
your key, and here is exactly which parts.**

An earlier version of this section said "nothing in Corky touches your
key". That was too strong, and the layer table below contradicted it three
paragraphs later. A signer has to get the key from your hand into Bitcoin
Core, and it has to put a backup on the screen for you to write down, and
both of those mean the key is a string in Corky's memory for a moment.
Saying otherwise invites exactly the criticism it is trying to duck.

So, plainly. **Bitcoin Core does all key management**: it generates the
key, derives every child, holds it, and signs with it. Corky derives
nothing, hashes nothing, and signs nothing. `tests/test_integrity.py`
fails if any shipped module so much as imports a cryptographic library.

**Corky sees your key at three moments, and no others:**

1. **On the way in.** What you type on the grid, or what the camera reads,
   is a string in Python until it reaches Core through `bitcoin-cli
   -stdin`. Never the command line, so it is never in a process listing.
2. **On the way to paper, and only if you ask.** The paper backup asks
   Core for the master key and renders it as pixels. This is the one time
   a key is pulled **out** of Core for a reason that is not cryptographic,
   which is why the encrypted file backup is the first option and this one
   is the second.
3. **The backup passphrase**, typed on the grid, on its way to Core's own
   `encryptwallet`.

Everything else, including the whole file channel and the whole QR channel,
carries transactions and public keys only.

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
Your backup is the master private key itself, 111 characters, and it
cannot be split into
shares. If that is unacceptable, the `lab` branch keeps the translator,
codex32 and SeedQR, and is meant for people who read code.

Corky's claim is not "trustless". It is: **you trust Bitcoin Core's wallet
implementation instead of a rewrite of it, and nothing else of ours computes
on your key, because there is no such code to compute with.**

## Every way off this board, and the two claims that are not the same claim

A radio is not the only way off a board, and on this one it was not even
the worst. Ten areas are checked and closed: the two firmware overlays, the
drivers, the firmware blobs, the interfaces, the services, what the kernel
saw at boot, **swap**, **the journal**, **the serial console and USB device
mode**, and Bitcoin Core's own networking.

Swap was the worst of them. Raspberry Pi OS enables it by default, so the
memory holding a key could be written to the card, and nothing in this
repository turned it off until 2026-09-05. The serial console was the next
worst: Raspberry Pi OS puts a login on two GPIO pins, so three wires and
physical access was a root shell. And the Zero's USB port can act as a
device, which would let the board present itself to any computer as a
network card, a serial port or a disk.

**Tools, Check for leaks** runs it on the device and puts the verdict on
the panel: green when nothing can carry data off, otherwise the failures,
five to a screen. That matters most on a hardened board, where the panel is
the only place a report can be read, because there is no SSH left.

From a terminal it is `sudo bash /opt/corky/image/leak-check.sh`, and
`--porcelain` is what the Tools screen reads. One implementation, two
readers.

**Two images, and they are not the same device.** `provision.sh` builds the
**dev image**: it keeps SSH, the radios and a login, because you cannot work
on a board without them. It still closes the paths that have no development
value, so swap, the journal, the serial console and USB device mode are shut
there. `image/harden.sh` is the **one-way step** you run when the board is
about to hold a real key: it takes the radios and SSH away, and reflashing
the card is the only way back. A dev image is expected to fail the radio
rows of the leak check, and the report says so rather than crying wolf.

**A clean run proves the OS is not driving the radio. It does not prove
the radio is off.** Raspberry Pi documents a hardware disable pin for the
Compute Modules and not for the Zero 2 W, and the `disable-wifi` overlay
disables the SDIO host controller while the chip keeps its power. Nothing
in Raspberry Pi's documentation claims a power-down.

So there are two claims:

| Claim | What proves it |
|---|---|
| The OS is silent | `radio-check.sh` on the device |
| The radio cannot transmit | the part is not on the board |

The Zero 2 W's radio is a **separate Synaptics component beside the
processor**, not inside the processor package, so removal does not touch
the processor. That is what the pocket build asks for, and it is the only
version of this that is physics rather than configuration. The primary
sources are in
[`docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md`](docs/wayfinder/e2e-before-testers/research/pi-zero-radio.md),
including the part number change of 1 November 2025, which means the board
in your hand has to be looked at rather than assumed from a guide.

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

## Where the randomness comes from, and where ours cannot reach

Corky's one generation path asks Bitcoin Core for the key, so it inherits
Core's entropy and nothing else. This is what Core actually does, read out
of `src/random.cpp` and `src/randomenv.cpp` at the v31.1 tag, and then what
that means on a board with no network, no disk activity and no user typing.

**What Core mixes in, every time it seeds:**

| Source | What it is |
|---|---|
| The operating system | `getrandom(2)` on Linux, the kernel's own pool |
| CPU instructions | `RDRAND` and `RDSEED`, when the processor has them |
| A high-resolution counter | the cycle counter, read repeatedly |
| The stack pointer | where this call happens to be in memory |
| An events pool | timings Core itself has accumulated |
| Dynamic environment | every clock, resource usage, and on Linux the contents of `/proc/diskstats`, `/proc/vmstat`, `/proc/schedstat`, `/proc/zoneinfo`, `/proc/meminfo`, `/proc/softirqs`, `/proc/stat` and its own `/proc/self/status` |
| Static environment | the host name, the kernel version, the environment block, the address of its own functions, the network interfaces and their addresses, and the device details of `/` |
| Strengthening | at startup it runs the mixer in a loop for 100 milliseconds, so the result depends on how fast this exact machine is |

Everything is folded into SHA-512 and mixed into a pool. No single source
has to be good on its own.

**Where this board is thinner than a desktop, and it is worth knowing:**

- **No network interfaces to speak of.** A hardened Corky has no radio, so
  the interface list Core hashes is almost empty, and the addresses on it
  are not unique to you.
- **No disk activity.** The datadir is a tmpfs and nothing else writes, so
  `/proc/diskstats` is close to still.
- **A quiet machine.** Nothing else is running, which is the point of the
  device, and it is also what a general-purpose desktop has that this does
  not: a hundred processes making unpredictable timing.
- **`RDRAND` and `RDSEED` do not exist on ARM.** Those are x86
  instructions. On this board that row of the table is simply absent.
- **A fresh boot every time.** The device is stateless, so Core's own
  events pool starts empty on every session rather than accumulating.

**What is the same, and it is the part that matters most:** the kernel's
`getrandom` is the same call, seeded by the same kinds of interrupt timing,
and on a Raspberry Pi it is also fed by the SoC's own hardware random
number generator through the kernel. The cycle counter, the strengthening
loop and the SHA-512 mixing are identical, because it is the same Core
binary doing them.

**What Corky adds: nothing.** It calls `createwallet` and Core does the
rest. There is no Python `random`, no `os.urandom`, no dice entry, no
camera noise, no timing of your button presses. A test fails if any of
those appear. That is a deliberate refusal to improve on Core, not an
oversight, because a homemade entropy source is exactly the kind of thing
that looks clever and loses money.

**The honest bottom line, stated more carefully than it used to be.** An
earlier version of this said software entropy "cannot be audited". That
was too broad, and Ben was right to push on it. There are two different
questions and only one of them is beyond reach.

**You CAN verify that the code is the code.** Bitcoin Core's releases are
built reproducibly, so the binary corresponds to source anyone can read.
Eleven signatures on the 31.1 hashes were checked out of band on
2026-09-03 from a different host to the one serving the binary, and that
hash is pinned in `image/PINS`, and provisioning refuses to install
without it. The M3 release image gets the same treatment: a hash of the
whole card, reproducible from this repository. So "is the generator the
one in the repository?" is a question with a real answer, and the answer
is checkable by you.

**You CANNOT verify the inputs it was given, or the output it produced.**

- The kernel's `getrandom` is not part of Core's reproducible build. Nor
  is the processor, nor the chip's own hardware generator, which the
  kernel also feeds from. Verified Core code asking a compromised kernel
  or a compromised chip produces exactly the bytes it is given.
- And randomness cannot be checked after the fact. A good generator and a
  backdoored one produce output that looks identical, which is the point
  of a backdoored one. No amount of reading the output tells you which you
  had.

So the accurate claim is narrower and stronger: **the software is
auditable and verified; the silicon and the kernel under it are not, and
the result is unfalsifiable either way.** Cards and dice do not fix the
software, which was never the weak part. They move the unpredictable step
out of the machine entirely, into something you watch happen. That is why
they remain the documented default, and it is the whole of the difference.

## Against the honest alternative: Core on an air-gapped laptop

The people most likely to pick this apart already have a better answer than
a hardware wallet: a laptop with its radios out, running the same Bitcoin
Core, signing PSBTs from a USB stick. Corky should be measured against that
and not against a vendor's sealed box. Here is where it wins, and where it
does not.

### Loading a key in

**Laptop.** You type or paste the key into a terminal or Core's console.
On a command line it is in the process list while it runs, and in
`~/.bash_history` afterwards, which is a file on a disk. In the GUI console
it is in the scrollback. If you pasted it, it is in the clipboard, and
clipboard managers are common.

**Corky.** Typed on a grid or read from a QR, held in memory, handed to
Core on standard input. Never on a command line, so never in a process
list. There is no shell, no history file, and no clipboard.

**Corky wins.** The shell history file is the persistence path people
forget, and it is on the laptop's real disk.

### Generation

**Laptop.** Core generates the key onto the laptop's own disk. Backing it
up means copying `wallet.dat` off, or reading the key out in the console
and into the scrollback. Deleting either afterwards is not deletion: flash
storage with wear levelling does not reliably overwrite in place.

**Corky.** Core generates onto a tmpfs, which is RAM. The default backup
is Core's own encrypted file, and the key is never read out of Core to
make it. Power off and the wallet is gone.

**Corky wins**, on where the key rests rather than on how it is made. The
generation itself is identical, because it is the same Core.

### Exporting the public key

**Laptop.** `listdescriptors`, then carry the text across on a stick, or
retype it.

**Corky.** A QR on the panel, read by a camera. Nothing crosses but light.

**Corky wins**, and it is the difference between a medium and a photon.

### Signing

**Laptop.** The unsigned PSBT arrives on a USB stick that has been in an
online computer. Your air-gapped machine then mounts a filesystem written
by that computer, which means its kernel parses attacker-influenced
structures before Core sees anything. Then the signed PSBT goes back the
same way. The stick crosses the gap twice, in both directions.

**Corky.** The camera reads pixels and the panel emits pixels. A QR code
carries no filesystem. The only thing that ever parses PSBT bytes is Core.
The USB stick still exists as an option for people who want it, and it
carries the same risk there as anywhere.

**Corky wins**, and this is the largest single difference between the two.

### Reviewing what you are about to sign

**Laptop.** Core's own interface shows you the transaction. Whatever else
you trust, you are not trusting a third party's rendering of Core's
numbers.

**Corky.** Core computes the fee and the outputs, and then **our 2,226
lines draw them**. If `screens.py` renders the wrong address, you sign the
wrong thing, and no amount of Core underneath saves you.

**The laptop wins.** This is the sharpest cost of the whole design, and it
is the reason the review screen has more tests than anything else here:
Corky's numbers are checked against Sparrow's own library, to the satoshi,
across both script types and eight transaction shapes. That is evidence,
not a rebuttal.

### Everything else about the laptop

It has a real keyboard, and typing 111 characters on a five-way pad is
miserable and error-prone. It has more memory, so it can hold transactions
that this board cannot. It can be reinstalled from scratch. Its Core is
reviewed by everyone who reviews Core, which is the same Core Corky runs.

Against that: a laptop is a general-purpose computer with a package
manager, a desktop, and years of installed history, and you are asked to
believe all of it. Corky is one program, a panel, a camera and a battery,
and the numbers for how much of it is ours are printed above.

### What neither can do

Neither can verify the input amounts a coordinator claims. An air-gapped
signer has no chain to check them against, so the fee on the screen is
computed from numbers the coordinator supplied. Corky says so on the review
screen. A laptop running Core says so nowhere, because it assumes you
know.

## What a Python signer cannot promise, measured

The three moments above are honest about WHERE the key is. This is honest
about what happens to it there, because it is the first thing a reader who
knows Python will ask.

**Python strings cannot be overwritten.** They are immutable, so the
runtime is free to copy them and there is no way to zero one when you are
done. `_text_entry` builds a typed key one character at a time, and each
character makes a new string. Typing the 111-character master key leaves
**111 separate objects holding 6,216 characters of key prefixes** in the
heap, the longest of them 110 of the 111 characters, and not one of them
can be wiped. Nothing in CPython can fix that, and any signer written in
Python has the same property whether or not its authors mention it.

What actually bounds the damage is the shape of the device, not the code:

- The datadir is a **tmpfs**. It is RAM. Power off and it is gone.
- The process ends at power off, and the heap goes with it.
- Nothing is written to the card. `tests/test_no_persistence.py` searches
  every byte under the datadir for the raw private key and the chain code,
  after a discard, after a close, after a crash restart, and after Core's
  own shutdown.
- Core's errors are redacted before they can reach the screen or the
  journal, because Core quotes the key back in them.

**What is left, stated so nobody has to find it:** while the device is
powered, copies of your key exist in RAM that Corky cannot erase. Cold
boot memory remanence is a real attack against that, and the answer to it
is to power the device off, which is also the answer to everything else on
this device. It is an M3 question and it is not solved here.

**The one exposure that was a choice is now the second option.** Getting a
key IN requires it to pass through memory. Showing a paper backup does
not: it asks Core for the master key purely to draw it on a screen. So the
encrypted file backup is offered first, and `generate_wallet` no longer
returns the key at all. A key Core generates and you back up to a file is
**never read out of Core**. Choose the paper backup and it is, once, on
purpose, and the menu says which one costs you that.

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

Single-sig BIP84 (native segwit) and BIP86 (taproot). **Up to five keys at
once**, one Core wallet each, named on screen by fingerprint; a transaction
is matched to its key by the fingerprints Core reads off its inputs. Key
entry in four forms: **Core generates one**, a **key or descriptor QR**
read by the camera, a raw **xprv typed on the grid**, which is the way
back from a paper backup, and **restore from a Core wallet backup** on a
stick or the boot card. None of
them is transformed by anything of ours at all: pure Core from the first
byte. (Descriptor mode is the answer to
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

**Export and backup.** Export public key writes what a coordinator needs:
a plain-text QR of Core's own output descriptor, the same string in
four-character groups for typing, and the first three receive addresses in
full for comparison. Sparrow, BlueWallet, Green and Bull Bitcoin all read
that descriptor as written; Bitcoin Core has no QR reader, so it gets a
watch-only wallet file its own GUI restores. Receiving addresses browses
further, ten at a time, receive branch only. Backup key offers two: the
master private key on paper, and a file that Core's own `encryptwallet` and
`backupwallet` produce, which another computer running Core restores with
your passphrase.

**Nothing persists.** A discard, a close, a crash-restart and a power-off
each leave no byte of a key anywhere on the device; `tests/test_no_persistence.py`
searches the whole datadir for the raw key bytes to prove it. The one
exception is the file backup, which is a key on a medium **because you
asked for it**, encrypted by Core with a passphrase you typed (PLAN A-23).

Out of scope for v1: multisig, message signing, and dice entropy. Corky
signs for keys that already live on metal, and writes no randomness of its
own; the one generation path it offers asks Bitcoin Core for the entropy
and gives you the master private key itself to write down. See PLAN A-19 for the
tradeoff, stated plainly.


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

**Layer 2 — sees secrets, computes nothing with them. 1962 lines.**
The device's body, and the wire to Core: menus, screens, buttons, and the
calls that hand Core what you supplied. It routes and displays key material
during entry and backup, and performs no arithmetic on any of it.
[`corky/main.py`](corky/main.py) (995) ·
[`corky/screens.py`](corky/screens.py) (579) ·
[`corky/signer.py`](corky/signer.py) (314) ·
[`corky/splash.py`](corky/splash.py) (13) ·
[`corky/hal.py`](corky/hal.py) (61).

`signer.py` sat in layer 3 until 2026-09-05, when a review pointed out that
it takes an xprv and a passphrase as parameters and always had. It carries
them to Core and computes nothing with them, which is layer 2 by this
README's own definition.

**Layer 3 — never touches secrets at all. 248 lines.**
[`corky/filechannel.py`](corky/filechannel.py) (59) and
[`corky/qrchannel.py`](corky/qrchannel.py) (189) move PSBTs as opaque
bytes. Core is the only parser, by law ([PLAN.md A-11](PLAN.md)).

**Total functional code: 2,210 lines** (3,833 with blanks/comments).
A bug in either layer can show you the wrong thing. Neither can compute
you the wrong key, because neither computes keys at all.

**Test code: 3,963 lines — none of it ships on the device.**
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

## What runs on the signer

Everything the device carries, and why. A package goes on the signer only
if a shipped module imports it or the board needs it to drive the panel or
the camera. `tests/test_integrity.py` holds the same list as an allowlist,
so a new import fails the suite until this section, `image/PINS` and
`image/provision.sh` are all changed on purpose. Nothing under "Dev
machine only" is ever installed on the device.

| On the signer | Source | Why it is there |
|---|---|---|
| Raspberry Pi OS Lite, 64-bit | image pinned in `image/PINS` | the OS; its hash is recorded on first flash |
| Bitcoin Core 31.1 | official binary, sha256 in `image/PINS`, 11 GPG signatures checked out of band | the wallet, all of it |
| Python 3 | the OS's own | runs Corky |
| Pillow | apt `python3-pil` | every screen is a PIL image |
| qrcode 7.4.2 | pip, pinned in `PIP_PINS` | renders the outbound QR frames |
| pyzbar 0.1.9 + libzbar0 | pip, pinned; apt `libzbar0` | decodes what the camera sees |
| picamera2 | apt `python3-picamera2` | the camera |
| spidev | apt `python3-spidev` | the SPI bus the panel hangs off |
| RPi.GPIO | apt `python3-rpi.gpio` | the buttons |
| ST7789 driver | vendored, `hw/vendor/st7789.py` (MIT, SeedSigner) | the panel |
| UR codec | vendored, `hw/vendor/ur2` (BSD-2, Foundation) | animated-QR fountain frames |
| one icon font subset | vendored, `hw/vendor/fonts` (CC BY 4.0) | seven home and settings glyphs |
| Corky | `/opt/corky`, three systemd units, one udev rule | this repository |

**Two things on the dev image that should not survive to the release
image.** `python3-pip` is there only to install the two pinned packages;
Debian ships both as `python3-qrcode` and `python3-pyzbar`, and if their
versions match the pins, apt can supply them and pip leaves the device.
`python3-zbar` is named on `provision.sh`'s first apt line and probably
does not exist as a package; the fallback line omits it. Both are checked
on the board at the next provision (ticket 23).

The image carries the program and nothing else: `corky/`, the vendored
drivers and font, the systemd units and the udev rule, one `bitcoin.conf`
and the licence. 39 files, 0.27MB. It used to be the whole repository, 1.09MB,
including every test and ticket; `tests/test_image_contents.py` now fails if
development files reach the card or if the program's own files leave it.

**Dev machine only, never on the signer:** `ruff`, `vulture` and `mypy`
from `requirements-dev.txt`; Sparrow 2.5.4 and a JDK under
`tests/sparrow/.build`; the Rosetta virtualenv under `tests/m1/.build`;
and a `bitcoind` for the regtest suites.

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

**M0 passed on the Pi Zero 2 W** (PLAN A-21): 226MB of headroom signing 250
ordinary inputs, once a GPU split the device never uses was cut to 32MB.
**M1 passed except the optics**, then the camera itself was wired and reads
a real Sparrow frame on the board.

Everything else provable without hardware is proven on a dev machine
against Core v31.1: the full signing pipeline on regtest, address
derivation against the published BIP84/BIP86 vectors, the screen set at
both display resolutions, and the whole interop claim run against
**Sparrow's own library** out of its signed release, because a QR tested
with your own decoder is not an interop test (TESTING.md rule 8).

Next: the end-to-end run on the board with a Sparrow laptop, then the
phone wallets. `docs/wayfinder/e2e-before-testers/` charts it.

## Build gates

| Gate | Deliverable | Pass condition |
|---|---|---|
| M0 | bitcoind wallet-only on the Zero 2 W (pocket build; sizes the M3 RAM image) | **PASSED 2026-09-03**: 226MB headroom at 250 ordinary inputs (PLAN A-21) |
| M1 | QR round trip vs Sparrow watch-only, testnet | fee/outputs match Sparrow; signed PSBT broadcasts |
| M2 | stateless UI on the LCD hat | power-on→ready < 90s; power cycle provably wipes |
| M3 | hardened reproducible image | read-only root; radios dead; image hash reproducible |
| M4 | mainnet trial | software path proven on real funds (ECDSA + Taproot, both confirmed); on-device trial pending hardware |
