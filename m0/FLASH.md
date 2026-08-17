# M0 on the Pi: flash, boot, run, read numbers

Your part is about 20 minutes of hands-on time. The Pi does the rest.

## 1. Flash (on the Mac)

1. Raspberry Pi Imager → device **Raspberry Pi Zero 2 W** → OS
   **Raspberry Pi OS Lite (64-bit)**. 64-bit is required: the official Core
   binary is aarch64.
2. In Imager's settings (gear icon): hostname `corky`, enable SSH with a
   password, set locale. Leave WiFi **configured for now** — M0 needs a way
   to get files on and results off. The radios die at M3, not M0.
3. Flash to a spare SD card (not your SeedSigner card).

## 2. First boot

SSH in (`ssh <user>@corky.local`), then:

```bash
sudo apt update && sudo apt install -y python3
# Bitcoin Core, official aarch64 binary (31.1 = the version all Corky tests ran against on the Mac):
cd /tmp
wget https://bitcoincore.org/bin/bitcoin-core-31.1/bitcoin-31.1-aarch64-linux-gnu.tar.gz
wget https://bitcoincore.org/bin/bitcoin-core-31.1/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS   # must say OK
tar xzf bitcoin-*-aarch64-linux-gnu.tar.gz
sudo install -m 755 bitcoin-*/bin/bitcoind bitcoin-*/bin/bitcoin-cli /usr/local/bin/
```

(For M0 the checksum check is enough; full GPG signature verification joins
the pinned image build at M3.)

## 3. Copy Corky across and run the gate

From the Mac:

```bash
scp -r ~/clawd/projects/corky <user>@corky.local:~/
```

On the Pi:

```bash
cd ~/corky && python3 m0/m0_gate.py --inputs 250
```

## 4. Read the verdict

The script prints `M0 PASS` or `M0 FAIL` with the numbers. Record:

- peak bitcoind RSS (MB)
- MemAvailable low-water (MB)  ← the pass line: **must stay ≥ 100**
- the three timings (bitcoind start, session open, stress sign)

Reference point: the same run on the Mac shows bitcoind RSS ≈ 99MB, so the
expectation is a pass with room to spare. If it fails, the fallback ladder in
PLAN.md (zram first) applies before any hardware change.

Paste the report block back to Claude and M0 is closed either way.
