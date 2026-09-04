# 02 Keep Corky's codex32, or vendor python-codex32

Labels: wayfinder:research (AFK)
Blocked by: none

## Question

`corky/codex32.py` is 260 functional lines, ours, and verified BIP93-correct
on lengths and checksums (map fact 3). BenWestgate/python-codex32 is MIT, a
declared reference implementation of BIP-93, actively pushed, with three test
files including interpolation round-trips.

Worth answering before any codex32 work lands on top of ours:

1. What does python-codex32 have that ours does not? The README names
   CRC-based padding for `from_seed`, mutation of parsed strings, and
   `interpolate_at`. Does it do error correction, which the spec makes a
   SHOULD and which ours does not attempt?
2. Its `from_seed` identifier defaults to the bech32 BIP32 fingerprint. Ours
   uses `codex32.derive_identifier(seed)`. Which does the ecosystem expect,
   and does using the XFP leak anything a backup should not carry?
3. Do its test vectors pass against our implementation? A disagreement is a
   finding either way.
4. What would vendoring cost: dependency surface, and whether it fits the
   list in hw/HARDWARE.md, which today is Pillow, pyzbar, qrcode, urtypes,
   picamera2, RPi.GPIO and spidev.

Recommend keep, vendor, or borrow specific parts. Corky's rule is that Core
is the only parser of PSBT bytes; codex32 is ours to own, so this is a
maintenance and correctness question rather than a doctrinal one.
