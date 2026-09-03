# M0 on the Pi: flash, boot, run, read numbers

Your part is about 20 minutes of hands-on time per board. The Pi does the
rest. Two boards are in scope and they need different network paths.

| Board | RAM | Network | Card slot |
|---|---|---|---|
| Pi Zero 2 W | 512MB | WiFi, 2.4GHz only, set in Imager | on the board |
| CM4 Lite on CM4-IO-BASE-B | 2GB | Ethernet cable, no radio on CM4002000 | on the carrier |

**Run the Zero 2 W first.** It carries the gate. M0 asks whether wallet-only
bitcoind fits in 512MB, and only the Zero can answer that. The CM4 has 2GB
and passes by arithmetic, so its run is a smoke test of the same toolchain
on the primary build, not a gate.

## 1. Flash (on the Mac)

1. Raspberry Pi Imager, device **Raspberry Pi Zero 2 W** (or **CM4**), OS
   **Raspberry Pi OS Lite (64-bit)**. 64-bit is required: the official Core
   binary is aarch64.
2. In Imager's settings (gear icon): hostname `corky`, enable SSH with a
   password, set locale. For the Zero 2 W add your **2.4GHz** WiFi. The
   Zero 2 W radio is single band and does not see a 5GHz network.
   Radios die at M3, not M0.
3. Flash to a spare card, one per board. Not your SeedSigner card.
4. Reinsert the card. macOS mounts the boot partition, then run:

   ```bash
   cd ~/clawd/projects/corky && ./image/prepare-sd.sh
   ```

   This copies Corky, the pinned build tuple and the provisioning script to
   the card. Eject.

## 2. First boot

**Zero 2 W:** power through the micro-USB port silkscreened `PWR IN`, the
one at the outer corner. The middle port marked `USB` is data and does not
power the board.

**CM4:** fit the CM4 to the carrier, put the card in the carrier's microSD
slot, and leave the **BOOT jumper open**. Closed means USB boot for writing
eMMC, which a Lite module does not have. Plug the Ethernet cable in. Power
through the carrier's USB-C with the 15.3W supply.

Then, from the Mac:

```bash
ssh <user>@corky.local
```

## 3. Provision

On the Pi:

```bash
sudo bash /boot/firmware/corky-provision.sh
```

This installs Bitcoin Core 31.1 against the hash pinned in `image/PINS`,
installs the display, GPIO, camera and QR packages, unpacks Corky to
`/opt/corky`, makes the ramdisk datadir, and turns on SPI for the hat. It is
idempotent. On a Zero 2 W over WiFi it takes about 15 minutes, most of it
`python3-picamera2`.

The Core hash was verified out of band on 2026-09-03: 11 good GPG signatures
on `SHA256SUMS`, keys taken from the guix.sigs repo rather than from
bitcoincore.org, and four builders attest the same hash independently. The
script refuses to install Core against an unpinned hash, on purpose. A
checksum fetched from the server that served the binary proves nothing.

## 4. Run the gate

```bash
sudo swapoff -a   # RPi OS enables swap by default; swap falsifies both
                  # gate numbers and the gate refuses to run with it on.
                  # Reverts at reboot.
cd /opt/corky && python3 m0/m0_gate.py --inputs 250
```

## 5. Read the verdict

The script prints `M0 PASS` or `M0 FAIL` with the numbers. Record:

- peak bitcoind RSS (MB)
- MemAvailable low-water (MB)  <- the pass line: **must stay >= 100**
- peak SoC temperature (C), and any `!!` throttle line
- the three timings (bitcoind start, session open, stress sign)

Temperature is in the report because ORDER.md drops the heatsink to save
7.5mm of case. Throttling costs sign time and nothing else, so it does not
fail the gate. An `under-voltage` line is different: it means the supply is
weak, and a weak supply spoils every other number above it.

Reference point: the same run on the Mac shows bitcoind RSS about 99MB, so
the expectation is a pass with room to spare. If it fails, the fallback
ladder in PLAN.md (zram first) applies before any hardware change.

Paste the report block back to Claude and M0 is closed either way.
