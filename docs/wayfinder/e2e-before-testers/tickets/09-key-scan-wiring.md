# 09 Wire the key scan, with stop rules

Labels: wayfinder:task (AFK)
Blocked by: none
Status: resolved 2026-09-05

## Question

Two of the four load-key entries fail on the board. Verified 2026-09-04 by
running `CameraQrSource().scan_key()` on the Zero 2 W:

```
RuntimeError: SeedQR scanning not wired yet (M2); type the seed
```

Both "Scan descriptor QR" and "Scan xprv QR" reach that line, and the
message names a SeedQR that main no longer has. The camera itself works
(M1); what is missing is a scan of a single static QR with stop rules.

Build it, on the M1 map's ticket 05 rules: 20 seconds with no decode times
out, B or C aborts, the viewfinder shows throughout, a bad frame is counted
and skipped. Length cap and charset check stay in `_scan_key_guarded`.
The same reader serves ticket 05's content detection.

Tests: a replay source that yields a real descriptor PNG, a real xprv PNG,
an address PNG, and garbage, asserting the outcome of each and the timeout.

## Answer (built, 2026-09-05)

`tests/test_keyscan.py`, 9 checks, no bitcoind needed.

Both "Scan" entries used to raise `SeedQR scanning not wired yet (M2)`, a
message naming a feature this branch no longer has. The camera itself was
already proven (M1); what was missing was a scan that can end.

**The contract did not change.** `ImageQrSource.strings()` is now the one
generator that yields decoded text, or None for a tick with nothing in
view, and both the PSBT scan and the key scan read from it. Ticket 04's
rule holds: the source yields strings, the caller owns every stopping rule.

**The rules, from the M1 map's ticket 05.** A tick that does not decode is
not a fault. A scan that reads nothing for 20 seconds gives up and says so.
B or C aborts at any point, and an abort is a choice, not an error to
report. A board with no camera says why at once rather than waiting out the
timeout, because that answer will never change (I-8).

**The viewfinder is painted throughout.** On the board, aiming blind gave
one read in 120 seconds and the same target with a viewfinder gave 53 in 90
(hw/HARDWARE.md), so this is not decoration.

The A-11 guards moved into `_guard_key_payload`, applied to whatever a
source yields: the 4096-byte cap, ASCII only, and the key charset. Tested
with an oversized payload and one carrying control bytes.

`Session.clock` is injectable, so the timeout is tested in milliseconds
instead of waiting 20 seconds.

Still not proven on the board: a real camera reading a real descriptor QR.
That is ticket 18's job.
