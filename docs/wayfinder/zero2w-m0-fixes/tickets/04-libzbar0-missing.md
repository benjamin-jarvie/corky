# 04 pyzbar needs libzbar0; no apt line installs it

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

PIP_PINS installs pyzbar==0.1.9, which dlopens the libzbar shared library
at import time. Neither apt line in provision.sh step 2 names libzbar0.
If the first apt line fails and the fallback runs, no zbar library exists
and the camera QR path dies at M1 with ImportError. What closes the gap?

Fix: add libzbar0 to both apt lines with a one-line comment saying why pip
cannot pull it in.

## Resolution (2026-08-31)

Done. `libzbar0` added to both apt lines in provision.sh step 2 with a
comment saying pyzbar dlopens it and pip cannot provide it. `bash -n`
passes. Whether `python3-zbar` exists in RPi OS Bookworm stays open on the
map; either way the fallback line now carries libzbar0.

Closed. Trello BB-24.
