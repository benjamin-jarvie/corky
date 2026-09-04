# 02 Keep Corky's codex32, or vendor python-codex32

Labels: wayfinder:research (AFK)
Blocked by: none
Assignee: claude (claimed 2026-09-04)
Status: CLOSED 2026-09-04

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

## Resolution (2026-09-04)

**Keep Corky's implementation. Vendor nothing. Borrow two things, one of
which is spec text rather than his code.**

### The cross-test: the cryptographic core agrees exactly

All five canonical BIP93 vectors decode to identical seed bytes and
identifiers under both implementations. All six interpolation and recovery
checks match bit for bit, including the derived shares `d`/`e`/`f` of vector
3 and the uppercase vector 2. Each implementation accepts the other's strings
and recovers the same seed. Two independent implementations agreeing on the
maths is the strongest evidence Corky's codex32 has had.

Script kept at `scratchpad/crosstest.py`. Ben Westgate's suite passes 23
tests, Corky's 67 assertions.

### Three disagreements, and Corky is right on the one that matters

1. **Seed length, 36 mismatches.** python-codex32 rejects every length in
   16..64 that is not a multiple of 4 (`bip93.py:176-177`). BIP93 says
   16-to-64 bytes with a bit size that is a multiple of 8, and its own
   invalid vectors contain only 15- and 65-byte cases. **He is stricter than
   the spec. Corky matches it.**
2. **HRP.** His bare `Codex32String()` constructor is HRP-agnostic to support
   Core Lightning's `cl`, so it accepts three strings BIP93 lists as invalid.
   A vendoring hazard: a scanned CLN HSM secret would be taken for a master
   seed.
3. **Padding.** Corky zero-pads; his `from_seed` defaults to CRC. Both are
   spec-valid. Neither reproduces every canonical vector. Cosmetic, and cross
   decoding always agrees.

### Vendoring would cost the two rules the module is built on

`pyproject.toml` declares `bip32>=5.0.0`, imported at module top, so it is
unavoidable. That pulls `bip32`, `coincurve`, `cffi`, `pycparser`,
`asn1crypto` and a 1.5MB compiled `_libsecp256k1.so`.

Measured: 28ms and 23.1MB RSS to import, against Corky's 2ms and 15.2MB.

`corky/codex32.py:8-11` states "Python standard library only. No third-party
imports, ever" and "No elliptic-curve math." Vendoring breaks both, adds five
packages plus a C extension to the seven-item list in `hw/HARDWARE.md`, and
all of it exists to compute one default identifier Corky does not want. On a
board with 117MB of measured headroom that is not free.

### And it would remove the feature Corky needs

**python-codex32 has no `split()` and no RNG anywhere in `src/`.** It cannot
generate a fresh share set. `corky/codex32.py:318` `split()` with
caller-supplied entropy is exactly what `_tool_backup` uses.

### Neither does error correction

`grep -rniE "correct|erasure|syndrome|berlekamp"` over python-codex32 returns
nothing. Detect-only, like Corky. Vendoring buys zero progress on the ECW
SHOULD in `docs/wallets.md:28-33`.

### Corky is closer to the BIP than he is

BIP93's Reference Implementation section names only
`BlockstreamResearch/codex32` and says its own inline Python may be used as a
reference. **Corky copies that inline code verbatim** (diffed: differences
are `black` formatting and hex case only). His rewrite into a generalised
`Checksum` class is further from the BIP's own Python.

Maintenance: 97 commits over ten months, bursty, a seven-month gap ending in
a bare version bump. 4 stars, 1 fork, 0 open issues. Coverage 94% against
Corky's 97%. PyPI is at 0.6.1 while HEAD is 0.6.2, never published. No BIP-93
author endorsement.

### Borrow

1. **CRC padding as a READER heuristic only**, never as the write default.
2. **The four-character window and `?`-as-erasure entry rules** from
   `docs/wallets.md:44-64`. That is the real gap, and it is spec text.

Closed.
