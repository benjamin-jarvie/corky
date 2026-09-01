# Core Compartmentalization, and the Pi Zero 1.3 Question

*Research note, 2026-08-31. Two questions, checked against primary sources
only: the Bitcoin Core source tree, the published release notes, the
tracking issues, and the vendor documentation. Every claim carries the URL
that owns it. Bitcoin Core 31.1 is the current release. Core 31.0 shipped
on 2026-04-19
([release page](https://bitcoincore.org/en/releases/31.0/)).*

---

## Question 1: Is Bitcoin Core being split into separate parts?

Someone on X said that the developers "are breaking out various parts, it's
just a long process." That claim is true. The detail matters, because the
parts that exist are not the parts people assume.

### The multiprocess work

Core has a multiprocess build. It produces two extra executables,
`bitcoin-node` and `bitcoin-gui`. The usage document states the option
directly: "The `-DENABLE_IPC=ON` build option, supported and enabled by
default on Unix systems, can be passed to build the supplemental
`bitcoin-node` and `bitcoin-gui` multiprocess executables"
([doc/multiprocess.md](https://github.com/bitcoin/bitcoin/blob/master/doc/multiprocess.md)).

The flag changed name and default three times. The history is visible in
the build files.

- Through Core 28.x the autotools flag was `--enable-multiprocess`. The
  help text ended with "Experimental (default is no)"
  ([configure.ac at v28.0](https://github.com/bitcoin/bitcoin/blob/v28.0/configure.ac)).
- Core 29.0 moved to CMake. The option became `WITH_MULTIPROCESS`, default
  `OFF`, and the string still said "Experimental"
  ([CMakeLists.txt at v29.0](https://github.com/bitcoin/bitcoin/blob/v29.0/CMakeLists.txt)).
- Core 30.0 renamed the option to `ENABLE_IPC` and turned it on by default
  on every non-Windows platform. The word "Experimental" left the option
  string. The line reads
  `cmake_dependent_option(ENABLE_IPC "Build multiprocess bitcoin-node and bitcoin-gui executables in addition to monolithic bitcoind and bitcoin-qt executables." ON "NOT WIN32" OFF)`
  ([CMakeLists.txt at v31.1, line 156](https://github.com/bitcoin/bitcoin/blob/v31.1/CMakeLists.txt#L156)).

So the build is default-on. The runtime behaviour is not.

Read the same document further: "The multiprocess binaries currently
function the same as the monolithic binaries, except they support an
`-ipcbind` option." The split into separate address spaces is future work.
The document says so: "In the future, after
[#10102](https://github.com/bitcoin/bitcoin/pull/10102) they will have
other differences. Specifically `bitcoin-gui` will spawn a `bitcoin-node`
process to run P2P and RPC code, communicating with it across a socket
pair, and `bitcoin-node` will spawn `bitcoin-wallet` to run wallet code"
([doc/multiprocess.md](https://github.com/bitcoin/bitcoin/blob/master/doc/multiprocess.md)).
Two open pull requests carry that work:
[#19460](https://github.com/bitcoin/bitcoin/pull/19460) adds
`bitcoin-wallet -ipcconnect`, and
[#19461](https://github.com/bitcoin/bitcoin/pull/19461) adds
`bitcoin-gui -ipcconnect`.

The state today is one process that can talk over an IPC socket. It is not
three processes.

### What the release notes say

Core 28.0 and 29.0 say nothing about multiprocess or IPC
([28.0](https://bitcoincore.org/en/releases/28.0/),
[29.0](https://bitcoincore.org/en/releases/29.0/)).

Core 30.0 is the first release that ships the feature in the binaries. Its
notes describe an "IPC Mining Interface" and add, under install changes,
that "The libexec/ directory also contains new bitcoin-node and bitcoin-gui
binaries which support IPC features and are called through the bitcoin tool.
(#31679)" ([30.0 release notes](https://bitcoincore.org/en/releases/30.0/)).
The binaries live in `libexec/`, not in `bin/`, and they are not on the
PATH. The user runs `bitcoin -m node`.

Core 31.0 changed the IPC mining schema in a breaking way. "The IPC mining
interface now requires mining clients to use the latest `mining.capnp`
schema. Clients built against older schemas will fail when calling
`Init.makeMining`"
([31.0 release notes](https://bitcoincore.org/en/releases/31.0/), PR #34568).

The one interface that Core actually exposes over IPC today is the mining
interface. Core 30.0 calls it experimental.

### libmultiprocess and the Cap'n Proto schemas

The IPC transport is
[libmultiprocess](https://github.com/bitcoin-core/libmultiprocess). It was
a `depends` package. PR
[#31741](https://github.com/bitcoin/bitcoin/pull/31741) merged it into the
Core tree as a git subtree on 2025-04-11. It now lives at
[src/ipc/libmultiprocess/](https://github.com/bitcoin/bitcoin/tree/master/src/ipc/libmultiprocess).

The schema files at
[src/ipc/capnp/](https://github.com/bitcoin/bitcoin/tree/master/src/ipc/capnp)
are `common.capnp`, `echo.capnp`, `init.capnp`, `mining.capnp` and
`rpc.capnp`. There is no `wallet.capnp` and no `chain.capnp`. The absence is
the evidence: the wallet boundary has no wire format yet.

The tracking issue is
[bitcoin/bitcoin#28722](https://github.com/bitcoin/bitcoin/issues/28722),
"Multiprocess tracking issue", opened 2023-10-24 by ryanofsky. It is still
open. A live design question sits at
[#34981](https://github.com/bitcoin/bitcoin/issues/34981), "multiprocess:
expose existing interfaces or design new ones?", opened 2026-04-01.

### libbitcoinkernel

The kernel library is the second decomposition effort. It extracts
consensus validation, and nothing else.
[doc/design/libraries.md](https://github.com/bitcoin/bitcoin/blob/master/doc/design/libraries.md)
describes `libbitcoin_kernel` as the "Consensus engine and support library
used for validation by *libbitcoin_node*", and states that it "should only
depend on *libbitcoin_util*, *libbitcoin_consensus*, and
*libbitcoin_crypto*".

The same file excludes the wallet by rule: "GUI and wallet libraries
*libbitcoinqt* and *libbitcoin_wallet* in particular should not depend on
*libbitcoin_kernel* and the unneeded functionality it would pull in, like
block validation."

The C API landed in PR
[#30595](https://github.com/bitcoin/bitcoin/pull/30595), "kernel: Introduce
C header API", merged 2025-11-04. Earlier steps were
[#24304](https://github.com/bitcoin/bitcoin/pull/24304) (`bitcoin-chainstate`,
2022-03-03), [#24322](https://github.com/bitcoin/bitcoin/pull/24322) (initial
library, 2022-04-28), [#31869](https://github.com/bitcoin/bitcoin/pull/31869)
(CMake target, 2025-02-17) and
[#33077](https://github.com/bitcoin/bitcoin/pull/33077) (monolithic static
library, 2025-08-06).

The header states its own stability: "The header is unversioned and not
stable yet. Users should expect breaking changes. It is also not yet
included in releases of Bitcoin Core"
([src/kernel/bitcoinkernel.h](https://github.com/bitcoin/bitcoin/blob/master/src/kernel/bitcoinkernel.h)).
No release notes for 29.0, 30.0 or 31.0 mention it.

The live tracking issue is
[#27587](https://github.com/bitcoin/bitcoin/issues/27587), "Bitcoin Kernel
Library Project Tracking", open since 2023-05-06. The older issue
[#24303](https://github.com/bitcoin/bitcoin/issues/24303) was closed on
2023-05-10 in favour of it.

The kernel does not help Corky. Corky needs Core's wallet. The kernel is
the part with no wallet in it.

### Is there a standalone signer binary?

No. Core ships no binary whose job is to sign. Two things get mistaken for
one.

**`bitcoin-wallet` is an offline wallet file tool.** It registers exactly
four commands: `info`, `create`, `dump` and `createfromdump`
([src/bitcoin-wallet.cpp](https://github.com/bitcoin/bitcoin/blob/master/src/bitcoin-wallet.cpp)).
It creates a descriptor wallet file, it reports on one, and it converts
between a wallet file and a dump file. It does not parse a PSBT. It does not
sign. It does not derive addresses for you. It runs against a wallet file on
disk, with no node.

**The external signer interface points outward, not inward.** `-signer=<cmd>`
tells a running `bitcoind` to call an external program. The document opens
with it: "Bitcoin Core can be launched with `-signer=<cmd>` where `<cmd>` is
an external tool which can sign transactions and perform other functions.
For example, it can be used to communicate with a hardware wallet"
([doc/external-signer.md](https://github.com/bitcoin/bitcoin/blob/master/doc/external-signer.md)).
The reference tool is [HWI](https://github.com/bitcoin-core/HWI). The same
document warns about it: "it should be used with caution. It is considered
experimental and has far less review than Bitcoin Core itself."

So `-signer` makes Core a client of a hardware signer. It does not make Core
into a signer that something else drives. Corky uses the opposite
arrangement: Core holds the keys and signs, and the Corky Python code drives
Core over RPC.

The supported air-gap pattern is written down, and it is two full Core
instances. See
[doc/offline-signing-tutorial.md](https://github.com/bitcoin/bitcoin/blob/master/doc/offline-signing-tutorial.md):
an `offline` host that "does not have, or need, a copy of the blockchain",
and an `online` host with a synced chain. Corky is the offline host of that
tutorial, put in a box.

### Is "coordinator" a Bitcoin Core concept?

No. The word appears three times in the whole repository. Once in a MuSig2
example inside libsecp256k1
([examples/musig.c](https://github.com/bitcoin/bitcoin/blob/master/src/secp256k1/examples/musig.c)),
where it names the party that aggregates nonces and partial signatures. Twice
in functional test scripts about multisig PSBT flow. There is no coordinator
component, no coordinator binary and no coordinator interface.

The nearest real thing is the role vocabulary of
[BIP 174](https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki),
which names a Creator, an Updater, a Signer, a Combiner, an Input Finalizer
and a Transaction Extractor. What wallet software calls a "coordinator" is
the Creator plus Updater plus Combiner plus Extractor, running on the online
machine. Corky's README already uses the word this way, and names Sparrow as
the target.

### Summary of Question 1

The claim on X is correct in direction and optimistic in pace.

| Effort | Status on 2026-08-31 |
|---|---|
| `ENABLE_IPC` build option | Default on, non-Windows, since 30.0 |
| `bitcoin-node`, `bitcoin-gui` binaries | Shipped in `libexec/` since 30.0 |
| Separate wallet process | Not shipped. PRs #19460, #10102 open |
| IPC mining interface | Shipped, called experimental, schema broke in 31.0 |
| libbitcoinkernel | Merged in tree, unstable API, not in any release |
| Standalone signer binary | Does not exist |
| Coordinator component | Does not exist |

---

## Question 2: Can a Pi Zero 1.3 run Corky's node or coordinator?

### Corky's three words

Corky's README and PLAN use three words for three different machines.

- The **signer** is the Corky device. It runs `bitcoind` wallet-only and
  offline, on a ramdisk, with `networkactive=0`. It holds the seed for one
  session and signs a PSBT. It never syncs a chain
  ([m0/bitcoin.conf](../m0/bitcoin.conf)).
- The **coordinator** is the online wallet software that builds the PSBT and
  broadcasts the signed result. Corky's target is Sparrow. The coordinator
  is not Corky's code and does not run on Corky hardware.
- The **node** is the online full node that the coordinator talks to. Corky
  does not ship one and does not require you to run one.

The question "can the node or coordinator run on a Pi Zero 1.3" therefore
asks about two machines that Corky does not build. The answer is still
useful, because people ask it.

The board is the one SeedSigner uses: a BCM2835, one ARM1176 core at 1GHz,
ARMv6, no NEON, 512MB LPDDR2, no radio, microSD only.

### ARMv6 is the hard stop

Bitcoin Core does not build for ARMv6, and Core said so itself. The 0.13.1
release notes carry an ARM section that is still the clearest statement in
the repository:

> "no model of Raspberry Pi 1 device can run either binary because they are
> all ARMv6 architecture devices that are not compatible with ARMv7-A or
> ARMv8-A."

([doc/release-notes/release-notes-0.13.1.md](https://github.com/bitcoin/bitcoin/blob/master/doc/release-notes/release-notes-0.13.1.md))

The Pi Zero 1.3 uses the same BCM2835 as the Pi 1. That sentence covers it.

Nothing has changed since. The Guix release build targets seven hosts, and
the list contains `arm-linux-gnueabihf` and `aarch64-linux-gnu` only
([contrib/guix/guix-build](https://github.com/bitcoin/bitcoin/blob/master/contrib/guix/guix-build)).
The depends README labels them "for Linux ARM 32-bit" and "for Linux ARM
64-bit"
([depends/README.md](https://github.com/bitcoin/bitcoin/blob/master/depends/README.md)).
The published 31.1 binaries match: `bitcoin-31.1-arm-linux-gnueabihf.tar.gz`
and `bitcoin-31.1-aarch64-linux-gnu.tar.gz`, with no armv6l file
([bitcoincore.org/bin/bitcoin-core-31.1/](https://bitcoincore.org/bin/bitcoin-core-31.1/)).

The `gnueabihf` triplet sets the floor. The Debian armhf port "requires at
least an Armv7 CPU with Thumb-2 and VFPv3D16"
([wiki.debian.org/ArmHardFloatPort](https://wiki.debian.org/ArmHardFloatPort)).
ARM1176 has neither Thumb-2 nor VFPv3. The binary will not start.

The operating system closes the other door. Raspberry Pi documents that the
64-bit OS "is designed for newer Raspberry Pi models that have 64-bit
processors, like Raspberry Pi 3, 4, and 5", and that the 32-bit version "is
designed for older Raspberry Pi models ... like the original Raspberry Pi, 2,
and Raspberry Pi Zero"
([raspberrypi.com OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)).
A Pi Zero 1.3 runs 32-bit armv6l Raspberry Pi OS and nothing else.

You would have to compile Bitcoin Core from source, on the device or with a
custom armv6 cross toolchain, and then maintain that toolchain yourself for
every release. Core's own build guide asks for "at least 1.5 GB of memory
available when compiling"
([doc/build-unix.md](https://github.com/bitcoin/bitcoin/blob/master/doc/build-unix.md)),
which the board does not have, so on-device compilation is out and cross
compilation is the only path. Nobody in the Core project tests that target.

That result applies to all three roles, because all three would need a Core
binary if you put them on this board.

### 512MB of RAM

Corky already measured the signer case. The M0 gate runs `bitcoind` with the
production flags `-dbcache=4 -maxmempool=5 -rpcthreads=1` and records peak
RSS ([m0/m0_gate.py](../m0/m0_gate.py)). Those flags are the documented
minimums: "The minimum value for `-dbcache` is 4" and "The minimum value for
`-maxmempool` is 5"
([doc/reduce-memory.md](https://github.com/bitcoin/bitcoin/blob/master/doc/reduce-memory.md)).

The reference run on a development Mac shows `bitcoind` RSS near 99MB
([m0/FLASH.md](../m0/FLASH.md)). The M0 pass line is 100MB of MemAvailable
headroom on the target board. That number is for a wallet-only `bitcoind`
with no chain. It is not a measurement of a synced node.

A validating node is a different budget. `-dbcache` defaults to 1024MiB, or
450MiB when Core detects less than 4096MiB of system RAM
([doc/reduce-memory.md](https://github.com/bitcoin/bitcoin/blob/master/doc/reduce-memory.md)).
On a 512MB board Core would fall to the 450MiB default and immediately
exhaust the machine, so you would have to force `-dbcache` far lower. The
same document states the cost: "A lower `-dbcache` makes initial sync time
much longer."

Corky's own PLAN already treats 512MB as tight for the signer alone. PLAN
item A-12 records that "The rootfs, bitcoind, the ramdisk datadir and the UI
must all share 512MB; a full Raspberry Pi OS cannot run from RAM at this
size" ([PLAN.md](../PLAN.md)). That is the signer, with no blockchain
anywhere in the picture.

### Storage and initial block download

The pruned floor is 550MiB of block files. Core sets the constant with a
comment that explains it: "we need the high water mark which triggers the
prune to be one 128MB block file + added 15% undo data = 147MB greater for a
total of 545MB. Setting the target to >= 550 MiB will make it likely we can
respect the target"
([src/validation.h](https://github.com/bitcoin/bitcoin/blob/master/src/validation.h)).

That 550MiB is only the blocks. The chainstate directory holds the UTXO set
and is separate. Core's assumeutxo document warns that the snapshot and
background chainstate directories are "each multiple gigabytes in size
(likely growing larger than the...)"
([doc/assumeutxo.md](https://github.com/bitcoin/bitcoin/blob/master/doc/assumeutxo.md)).
I did not find a current authoritative UTXO set size in a Core primary
source, so treat the exact figure as unsure. Measure it with
`gettxoutsetinfo` on a synced node. The practical floor for a pruned node in
2026 is several gigabytes, not 550MiB.

Initial block download on this board is the part I cannot cite. I found no
primary-source benchmark of Bitcoin Core IBD on an ARM1176 at 1GHz, and I
will not invent one. State the reasoning instead. IBD validates every
signature in the chain. The work scales with the block count and with
per-core integer throughput. An ARM1176 has one core, no NEON, and roughly
one order of magnitude less integer throughput per clock than a Cortex-A53,
which is the Pi Zero 2 W core. A microSD card gives random-write performance
in the low single-digit MB/s, and the chainstate is a random-write workload.
With `-dbcache` forced to a few tens of megabytes, the UTXO cache would
flush to that card continuously. A sync that takes days on a Pi 4 would
plausibly take months here, and might never finish before the chain outruns
it. I am unsure of the exact number. I am confident about the sign.

### Verdict by role

**Signer: plausible, but blocked by ARMv6.** The memory profile fits. Corky
measured 99MB RSS for wallet-only `bitcoind`, and the board has 512MB. There
is no chain, no IBD and no chainstate. The single blocker is the
architecture. There is no official armv6 Core binary, and building one is
unsupported work that no Core contributor tests. This is exactly why Corky's
pocket build uses the Pi Zero 2 W, which is a Cortex-A53 and runs the
official `aarch64-linux-gnu` build.

**Node: no.** ARMv6 blocks it, 512MB blocks it, and the microSD blocks IBD.
Three independent failures. Fix any one and the other two remain.

**Coordinator: no, and it is the wrong question.** In Corky's vocabulary the
coordinator is Sparrow or equivalent on your online machine. Sparrow is a
JVM desktop application with a graphical interface. It does not target ARMv6
and does not fit 512MB. The coordinator is meant to be a machine you already
own.

### The smallest board that works

The **Raspberry Pi Zero 2 W** is the smallest board that runs an official
Bitcoin Core binary. It carries a Cortex-A53, which is ARMv8-A, so
`bitcoin-31.1-aarch64-linux-gnu.tar.gz` runs on it unmodified. It also has
512MB, so it is a signer board, not a node board. Corky already uses it as
the pocket build, and PLAN item A-12 already records the 512MB risk and the
mitigations.

For a **node**, do not use a Zero-class board at all. Use at least 2GB of
RAM and an SSD over USB 3 rather than a microSD. Corky's primary build, the
CM4 Lite, is chosen for the signer role for the same RAM reason: PLAN records
that "2GB removes the A-12 RAM-resident-OS risk entirely"
([PLAN.md](../PLAN.md)).

### The honest answer in one paragraph

SeedSigner runs on a Pi Zero 1.3 because SeedSigner wrote its own small
wallet in Python and MicroPython, and Python runs on ARMv6. Corky runs
Bitcoin Core, and Bitcoin Core does not run on ARMv6. That is the whole
difference, and it is the direct cost of Corky's central design choice. The
README states the choice plainly: Corky maximizes review instead of
minimizing code. The Pi Zero 1.3 is one of the things that choice buys you
out of.
