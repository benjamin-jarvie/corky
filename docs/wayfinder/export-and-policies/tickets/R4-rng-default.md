# R4 Is Core's RNG safe to have, and safe as the default

Type: `wayfinder:research`. **Closed 2026-09-05.** Follows R2.

## Question

Ben, on R2: "'no keyboard, no fan, no spinning disk, no radios means the
entropy is thin by construction' seems contradicting to 'so generation
stays a legitimate option'. So generating a key via core on zero 2w or
cm4 is sufficient entropy? No ball park? Is it safe to even have or not?
If it is, is it safe to be a default over dice? Cards won't work because
it's BIP32 not BIP39."

He is right on both counts. "Thin" was the wrong word, and the dice
comparison rests on a path that does not exist.

## 1. "Thin" was wrong. Here is the ballpark.

`/sys/class/misc/hw_random/rng_quality` reads **1024**. That is the
kernel's own accounting: it credits the BCM2835 generator **1024 bits of
entropy per 1024 bits read**, one bit per bit, full entropy. Measured
throughput is 119 kB/s, so about **950,000 credited bits per second**.
The kernel needs **256 bits, once**, to seed the CRNG for the life of the
boot. It is saturated in well under a millisecond.

So the quantity is not thin. It is enormous relative to the requirement.

What IS narrower than a laptop is the **number of independent sources**.
Interrupt counts on the board, by source:

| source | interrupts |
|---|---|
| arch_timer | 376,839 |
| function-call IPIs | 87,569 |
| mmc1, the SD card | 76,578 |
| IRQ work | 15,485 |
| rescheduling | 7,003 |
| uart-pl011 | 5,825 |
| DMA | 4,563 |
| mailbox | 3,184 |

Eight sources with real counts, dominated by the timer and the card. A
laptop adds keyboard timing, mouse timing, disk seeks and network
interrupts on top of its own hardware generator.

**The correct claim is concentration risk, not scarcity.** There is far
more than enough entropy; there is less variety behind it. If the ring
oscillator were compromised in a way that still passed R2's statistical
tests, there is less else on this board to save you. That is a real
difference from a laptop and it is what I should have written.

One caveat that must be said plainly: `quality = 1024` is the driver's
**declaration**, auditable in the kernel source, not a measurement. Nobody
can measure it from outside. That is R2's conclusion restated.

## 2. Is it safe to have? Yes.

The kernel gets its 256 bits from a dedicated hardware entropy source
before userspace starts. The generator is statistically clean over a
megabyte. Boot entropy differs across reboots even with the saved seed
frozen. Twelve generated keys were distinct and three separate boots gave
three different first keys. Nothing measured points at insufficiency.

This is the same mechanism every Linux-based signing device uses.

## 3. Is it safe as the default over dice? There is no dice.

**Dice cannot produce a Corky key.** This is the finding that matters, and
it makes the question different from the one being asked.

To turn dice rolls into a key you need BIP32 master key derivation, which
is HMAC-SHA512 over the entropy. Two things have to be true for that to
happen on this device, and neither is:

- **Corky cannot do it.** PLAN A-22 puts zero lines in the layer that
  transforms secrets. No `hashlib`, no `hmac`, no `secrets`, no curve
  library, anywhere in `corky/`. `tests/test_integrity.py` fails if one
  appears.
- **Core cannot do it either.** `sethdseed` was the RPC that took raw
  entropy and it went with the legacy wallets. Confirmed against the
  binary on the board: `help sethdseed` returns "unknown command" on
  v31.1. Core's descriptor wallets offer exactly two doors: `createwallet`
  generates with Core's own RNG, and `importdescriptors` takes a key you
  already have.

Ben's own point closes the other half: cards are a BIP39 technique, mapping
draws to words. Corky has no BIP39 at all. That was the headline tradeoff
of the Core-only build.

So the real choice on this device is not "Core's RNG or dice". It is:

- **Core generates the key here**, on a board with radios physically
  disabled, no writable persistence, and the key alive only in RAM; or
- **you bring an xprv made somewhere else**, which means trusting another
  machine's RNG, and then typing 111 characters or scanning a QR of the
  key.

The second is not obviously safer, and for most people it is worse.

## 4. What the README says, and it is wrong

`README.md` currently claims "**Generation: cards and dice by default,
Bitcoin Core by choice**", and lists "cards, dice, words, a codex32 share
set, or Bitcoin Core's own RNG" as the ways a key is born. It also says,
sixty lines further down, "Out of scope for v1: multisig, message signing,
and **dice entropy**."

Both cannot be true. The second is the accurate one. The first is left
over from before the A-22 cut, when the BIP39 shim and codex32 were in the
tree and cards and dice really did have a path. They do not now.

Corrected in this commit. The README should say what is true: Core's RNG
is the only way to create a key on this device, the alternative is to bring
one in, and the tradeoff is stated honestly rather than by pointing at a
door that is bricked up.

## 5. What would it take to have a dice path

Recorded because it is the obvious next question, not because it is
proposed. Any of these, and each costs something the project has
deliberately refused:

- Reintroduce a cryptographic primitive to `corky/` to do the BIP32 master
  derivation. Breaks A-22, which is the whole trust argument.
- Ship the `lab` branch's BIP39 shim. Breaks the Core-only claim.
- Do the dice-to-xprv conversion on another computer and type the result
  in. Works today with no code change, and moves the trust to that other
  computer, which is what dice was supposed to avoid.
- Wait for a Core RPC that accepts entropy. None is proposed upstream.
