# 01 Swap invalidates the gate

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

Raspberry Pi OS Bookworm enables dphys-swapfile by default. With swap on,
pages swap out under pressure: peak RSS reads low and MemAvailable reads
high, so the gate can print PASS on a machine that would OOM without swap.
The M3 image has no swap. What must change so the gate cannot give a
verdict under swap?

Fix: m0/m0_gate.py refuses to run when /proc/swaps shows active swap, and
m0/FLASH.md tells Ben to `sudo swapoff -a` first (reverts at reboot).

## Resolution (2026-08-31)

Done. `swap_active_mb()` reads /proc/swaps; any active swap prints
`M0 INVALID` with the fix command and exits 2 before bitcoind starts.
On non-Linux it returns 0, so dev runs are unchanged. FLASH.md's first-boot
block now begins with `sudo swapoff -a` and says why. Verified: gate runs
clean on the Mac (250 inputs, signed).

Closed. Trello BB-21.
