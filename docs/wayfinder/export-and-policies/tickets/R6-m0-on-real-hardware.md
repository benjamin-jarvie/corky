# R6 The M0 memory gate, run on the board

Type: `wayfinder:research`. **Closed 2026-09-05 with a FAIL.**

## Question

Ben: "We are nearly ready to push a beta version?" M0 is the gate that
answers whether wallet-only bitcoind fits in 512MB. It had never been run
on hardware. It has now.

## Answer

**It fails, on the image the board is running.**

| measure | value |
|---|---|
| peak bitcoind RSS | 128 MB |
| peak gate process RSS | 57 MB |
| MemAvailable low-water | 81 MB |
| requirement | 100 MB |
| stress PSBT | 250 inputs, 980 KB |
| build, review and sign | 8.5 s |
| peak SoC temperature | 41.3 C |
| throttling | none, 0x0 |

Three runs, each fairer than the last:

- 35 MB with the signer running. Not a fair number: Corky's own bitcoind
  was resident beside the gate's.
- 44 MB with `corky` stopped. Still unfair: `corky-bitcoind` was up.
- **81 MB** with `corky-bitcoind`, `bluetooth` and `avahi-daemon` stopped.

## Why this is not yet a verdict on the design

The board runs **Raspberry Pi OS with its default services**, not the lean
image. With everything above stopped, these were still resident and every
one of them is removed by `image/harden.sh`:

| still resident | RSS |
|---|---|
| two sshd sessions plus sshd | about 23 MB |
| NetworkManager | 8 MB |
| wpa_supplicant | 4 MB |

That is roughly 30 MB, which would put the figure near the threshold. **It
is an estimate and it is not a pass.** TESTING.md rule 6: a cost claim
comes from a measurement. The measurement that settles this is the gate
run on a hardened flash, and `harden.sh` takes SSH with it, so that run
has to happen at the console or write its report to the card.

## What it means for a beta today

The stress case is 250 inputs. An ordinary transaction has a handful, and
signing one is nowhere near this. But 81 MB of headroom on a worst case
means a large consolidation could take the board out of memory, and the
device should not be handed to testers with that unknown.

Two honest options, and they are Ben's call:

1. Flash a hardened image and re-run the gate. Settles it properly.
2. Ship a private beta with a stated limit on input count, and the gate
   figure published, until 1 happens.

## A dev-machine lesson, recorded because it cost time

Stopping `avahi-daemon` to reclaim its memory killed mDNS, so
`corky-zero.local` stopped resolving and the board looked dead when it was
running perfectly. A `corky-ip` fallback is now in `~/.ssh/config`. On a
hardened board neither avahi nor SSH exists at all, so this is a dev
concern only.
