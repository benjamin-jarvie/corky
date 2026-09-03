#!/bin/sh
# The rig must decode with the same library the device runs: pyzbar 0.1.9 over
# the C zbar library (image/PINS, image/provision.sh:38-41). A number measured
# with any other decoder does not transfer to the Pi.
#
# On Apple Silicon this needs Rosetta. Homebrew here lives at /usr/local, so
# its zbar is x86_64, while the system python3 is arm64 and cannot dlopen it.
# The fix is an x86_64 interpreter plus x86_64 wheels in one target directory.
# Nothing is installed system-wide; everything lands in .build/py-x86.
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
command -v zbarimg >/dev/null 2>&1 || { echo "need zbar: brew install zbar"; exit 1; }
echo "ok   zbar $(zbarimg --version)"
mkdir -p "$DIR/.build/py-x86"
arch -x86_64 /usr/bin/python3 -m pip install --quiet --target "$DIR/.build/py-x86" \
    "pyzbar==0.1.9" "qrcode==7.4.2" pillow numpy
PYTHONPATH="$DIR/.build/py-x86" arch -x86_64 /usr/bin/python3 -c "
from pyzbar import zbar_library
print('ok   pyzbar 0.1.9 ->', zbar_library.load()[0]._name)"
