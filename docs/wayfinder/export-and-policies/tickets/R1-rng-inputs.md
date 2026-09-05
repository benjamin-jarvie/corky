# R1 What feeds the RNG on this board

Type: `wayfinder:research`. **Closed 2026-09-05.**

## Question

Ben: "answer the question about our RNG, what inputs go into it - fan? We
have none, temp - we can know, key strokes? There is none, so we need to
know what's going into the entropy at the moment and what's not with
Corky."

## Answer

Measured on `corky-zero`, a Pi Zero 2 W running the current image, on
2026-09-05. Not quoted from documentation.

### What goes in

**The kernel's CSPRNG, which is what Core actually asks.** Core calls
`getrandom()`; the `/dev/random` and `/dev/urandom` strings in the binary
are its fallbacks. Everything below feeds that one pool.

- **The SoC's own hardware random number generator.**
  `/sys/class/misc/hw_random/rng_current` reads `3f104000.rng`, the
  BCM2835 ring-oscillator generator on the die. It feeds the kernel pool
  continuously through the in-kernel `[hwrng]` thread, which is running
  (PID 67). `rngd` is **not** running and is not needed for this.
- **Interrupt timing jitter.** 4,258,191 interrupts since boot, each one
  contributing the low bits of its arrival time.
- **A seed the firmware hands the kernel at boot.** `dmesg` shows
  `random: crng init done` at `0.000000`, before any jitter could have
  accumulated. `/proc/device-tree/chosen/rng-seed` is absent because the
  kernel consumes that property and wipes it, so its absence is the
  evidence it was used.
- **Systemd's saved seed**, `/var/lib/systemd/random-seed`, 32 bytes,
  stirred in at boot. The kernel credits it zero entropy by default, so it
  stirs rather than seeds.
- **Bitcoin Core's own additions**, mixed into its internal SHA512 state
  on top of the OS bytes: the CPU cycle counter, `getrusage`, its own
  `/proc/self` statistics, ASLR addresses, the environment, the clock, and
  a periodic re-stir. Core never replaces the OS bytes with these; it adds
  to them.

### What does not go in

- **Keystrokes. None exist.** `/proc/bus/input/devices` lists exactly two
  devices, `vc4-hdmi` and `vc4-hdmi HDMI Jack`. Corky's d-pad is GPIO,
  polled by Python, and never reaches the kernel's input-randomness path.
  Ben's instinct was right.
- **Fan speed. There is no fan**, and a fan tachometer is not a kernel
  entropy source on any Linux.
- **Temperature.** Readable, and read by nothing. Neither the kernel nor
  Core mixes it in, and it would be a poor source: it moves slowly and
  predictably.
- **RDRAND and RDSEED.** x86 instructions. `bitcoind` here is
  `ELF 64-bit LSB pie executable, ARM aarch64`. The Cortex-A53 predates
  the ARMv8.5 RNDR instruction, so there is no ARM equivalent either.
- **Anything of Corky's.** PLAN A-19 and A-22: no `random`, no `secrets`,
  no `os.urandom`, no camera noise, no button timing.
  `tests/test_generate.py` fails if one appears.

### What this changes about the honest claim

The README says the silicon under Core cannot be verified. That stands.
What this measurement adds is **why it matters more here than on a
laptop**: a board with no keyboard, no fan, no rotating disk and no radios
has thin entropy by construction. Nearly all of it comes from one
ring oscillator on the die plus interrupt timing. That is a concrete reason
cards and dice remain the documented default, rather than a general one.

### One gap found, and it is real

Nothing in `image/provision.sh` or `image/harden.sh` touches
`/var/lib/systemd/random-seed`. On the current developer image the root
filesystem is writable, so systemd refreshes it each boot and the file
differs per device. On the planned **M3 RAM-resident, read-only image that
file would be baked in**, identical on every device and every boot. It is
credited zero entropy, so it should not be load-bearing. "Should not be
load-bearing" is exactly the assumption that deserves a test.

Recorded in the map's **Not yet specified**, because what to do depends on
whether M3 has a read-only root or an overlay, which is not decided.
