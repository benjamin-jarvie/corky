# N1 The card comes out and the signer keeps running

Type: `wayfinder:task`. **Open. Blocks N2, N3, D5's shipping half.**

## Question

Ben, 2026-09-05: "We also need to ensure the software will continue to run
if the microSD is taken out after boot, and give a popup saying you can
safely remove microSD now, like SeedSigner does, then test adding a blank
microSD to export a key to, add a different microSD with the a PSBT on it
to corky which has a key loaded."

## The state of it, measured

The operating system is on the card. `lsblk` on the board:
`mmcblk0p2` is mounted at `/`, `mmcblk0p1` at `/boot/firmware`, and there
is one usable slot. Pull the card today and the system dies at the next
disk touch. Nothing about this is a software setting.

So this ticket IS M3, the RAM-resident image, which the plan had last.
Ben's workflow makes it a prerequisite instead. The whole of his sequence
depends on it:

1. boot, load a key;
2. be told the card can come out;
3. take it out, and the signer keeps running with the key still loaded;
4. put in a blank card and export a public key to it;
5. put in a different card carrying a PSBT, sign, take it back to the
   coordinator.

## What it needs

Not designed here. The shape is SeedSigner's: a root filesystem that is
copied into RAM at boot and then unmounted, small enough to fit alongside
bitcoind in 512MB. `m0/FLASH.md` and the M0 gate figures (R6) bound the
budget: bitcoind peaked at 128MB and the gate's own process at 57MB, and
the UI replaces the latter.

The 512MB question is the whole risk. If the image plus bitcoind plus the
UI does not fit, PLAN A-12's fallback stands: QR and USB only, and the
card channel waits for a bigger board.
