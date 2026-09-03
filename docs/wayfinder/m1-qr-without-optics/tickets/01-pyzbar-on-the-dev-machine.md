# 01 The rig must use zbar, not zxing

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

`tests/sparrow/test_qr_airgap.py` proves Corky's rendered QR codes are
readable, but it reads them with **Sparrow's zxing**. The device will read
with **zbar**, through `pyzbar`. The two decoders do not have the same
tolerance for blur, tilt and low contrast, so a legibility number measured
with zxing does not transfer to the device.

Nothing in ticket 02 is trustworthy until the rig decodes with the same
library the device runs.

Get `pyzbar` and `libzbar0` working on the dev machine, confirm the version
matches what `image/provision.sh` installs, and add a decode helper the rig
can call. Record the version pin.

## Resolution (2026-09-03)

Done. The rig now decodes with **pyzbar 0.1.9 over zbar 0.23.93**, the same
binding `image/PINS` pins and the same library series Bookworm's `libzbar0`
provides (0.23.92).

It needed Rosetta. Homebrew on this machine lives at `/usr/local`, so its zbar
is x86_64, while the system `python3` is arm64 and cannot `dlopen` it. Neither
`DYLD_LIBRARY_PATH` nor a symlink fixes an architecture mismatch. The fix is an
x86_64 interpreter with x86_64 wheels in one target directory:

    tests/m1/setup.sh     installs pyzbar, qrcode, Pillow, numpy into
                          tests/m1/.build/py-x86  (nothing system-wide)
    tests/m1/run          runs a script under arch -x86_64 with that path

Rejected: decoding with `zbarimg` as a subprocess. It runs and it is the same C
library, but it is a different code path from the one on the device, and the
whole point of this ticket is that the numbers must transfer.

Also rejected: keeping Sparrow's zxing from `tests/sparrow`. Different decoder,
different tolerance, numbers that do not transfer.

Verified end to end: pyzbar decodes a real Corky-rendered UR frame,
`UR:CRYPTO-PSBT/1-10/...`, 238 bytes.

Closed.
