# R2 How much entropy Corky actually has

Type: `wayfinder:research`. **Closed 2026-09-05.**

## Question

Ben: "what's Corky's level on entropy, can we ball park it? If we can't
and suspect it's low, we should not even offer it as an option, let alone
a default."

## Answer

**A single number is not obtainable, and anyone who gives you one is
guessing.** Here is why, and here is what was measured instead.

A modern Linux kernel does not meter entropy the way the old one did. It
gathers until it has 256 bits of estimated entropy, declares the generator
seeded, and from then on it is a stream cipher: output is unpredictable if
and only if that seed was. So the question is never "how many bits per
second"; it is "was the seed unpredictable", and that is not answerable by
looking at the output. A counter encrypted under AES passes every
statistical test there is.

What the tests CAN do is detect gross failure, and what experiment can do
is show the thing is not repeating. Both were run on `corky-zero`.

### 1. The hardware generator is alive and unbiased

One megabyte read from `/dev/hwrng`, the BCM2835 ring oscillator, at
119 kB/s:

| measure | result | ideal |
|---|---|---|
| Shannon entropy | 7.9998 bits/byte | 8.0 |
| bit balance | 0.49984 | 0.5 |
| chi-square (df 255) | 244.2 | 205 to 310 |
| serial correlation | +0.00117 | 0 |
| longest repeated-byte run | 3 | 3 to 4 |

No stuck bits, no bias, no short period. This rules out a broken
generator. It does not rule out a backdoored one, and nothing can.

### 2. Boot entropy is fresh, and the saved seed is not carrying it

An early-boot probe unit captured 32 bytes of `/dev/urandom` before
`sysinit.target`, across three reboots. Three different values.

Then the interesting one, because it is the M3 read-only image in
miniature: `/var/lib/systemd/random-seed` was overwritten with a constant
and made immutable, so both boots started from the same saved seed. The
early reads were still completely different, `41cd4ccf…` and `f7c312f9…`.

**So the saved seed file is not load-bearing.** The boot entropy comes
from the firmware seed and the hardware generator. A read-only M3 image
that freezes that file would be untidy, not dangerous. Worth removing from
the image for hygiene; not a reason to hold M3.

### 3. The shipping path does not repeat

Twelve keys generated through `signer.generate_wallet` on the board:
twelve distinct fingerprints, bit balance 0.5052 over 384 bits.

Then the test that catches a frozen boot state, which the above would not:
the FIRST key generated after each of three separate reboots.
`2a2a3afd`, `176bef8e`, `10fe87d2`. Three boots, three different keys.

### The recommendation, since it is a decision

The evidence does not support "low". It supports **"working, and
unverifiable in principle"**, which is a different claim and the one the
README already makes. Every hardware wallet on the market is in exactly
this position; none of them can prove their silicon either.

So generation stays a legitimate option. What the measurements do not
change is which option is the DEFAULT, and the README's answer stands:
cards and dice move the unpredictable step out of the machine and into
something you watch happen. This board makes that argument stronger rather
than weaker, because a device with no keyboard, no fan, no spinning disk
and no radios has thin entropy by construction. Nearly all of it is one
ring oscillator plus interrupt timing.

### How to re-run this

The probe unit and the frozen-seed test were removed from the board after
the run. The reboot loop and the statistics are in this session's
transcript; the two that are worth making permanent are the twelve-key
distinctness run and the first-key-after-boot comparison, because they
test the shipping path and would catch a frozen image.
