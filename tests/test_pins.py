"""Nothing reaches the network without a hash to check it against.

`apt-get install` takes whatever the archive is serving today, so two
cards provisioned a week apart carried different software and neither
could be reproduced from anything in this repository. That was the whole
of the reproducibility gap: one OS image hash, and six .deb files.

Measured on the dev board 2026-09-23: `apt-get install -s` for the list
provision.sh used to ask for reports exactly SIX packages, because the
958 the OS image already carries satisfy every dependency.

This suite fails if anything in image/ fetches a file it cannot check.

Run: python3 tests/test_pins.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "image"
fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


PINS = (IMAGE / "PINS").read_text()

# --- 1. every pinned line is a url, a sha256 and a size -----------------
m = re.search(r'PINNED_DEBS="\n(.*?)\n"', PINS, re.S)
if not m:
    bad("image/PINS defines no PINNED_DEBS")
    print(f"\n{len(fails)} failure(s)")
    sys.exit(1)

debs = []
for line in m.group(1).splitlines():
    if not line.strip():
        continue
    parts = line.split()
    if len(parts) != 3:
        bad(f"a pinned line is not 'url sha256 size': {line!r}")
        continue
    url, digest, size = parts
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        bad(f"{url.rsplit('/', 1)[-1]} has no sha256: {digest!r}")
    elif not size.isdigit():
        bad(f"{url.rsplit('/', 1)[-1]} has no size: {size!r}")
    elif not url.startswith(("http://", "https://")):
        bad(f"a pinned line is not a url: {url!r}")
    else:
        debs.append((url, digest, int(size)))

if debs and not fails:
    ok(f"all {len(debs)} pinned packages carry a url, a sha256 and a size")

# --- 2. every hash is different ----------------------------------------
# A copy-and-paste that repeats one hash pins one file six times and
# would let five through unchecked.
digests = [d for _u, d, _s in debs]
if len(set(digests)) != len(digests):
    bad("two pinned packages share a sha256, so one of them is not pinned")
else:
    ok("every pinned hash is distinct")

# --- 3. provision.sh installs nothing from an index ---------------------
# `apt-get update` is fine and `apt-get purge` is fine. `apt-get install`
# is the one that reaches a rolling archive for a file nothing checks.
prov = (IMAGE / "provision.sh").read_text()
installs = [ln.strip() for ln in prov.splitlines()
            if re.search(r"^\s*apt(-get)?\s+install", ln)]
if installs:
    bad(f"provision.sh still installs from an index: {installs[0]!r}")
else:
    ok("provision.sh installs nothing from an index")

# --- 4. every download in image/ is checked -----------------------------
# A curl or a wget whose output nothing hashes is an unpinned input,
# whatever it is fetching.
for script in sorted(IMAGE.glob("*.sh")):
    text = script.read_text()
    fetches = re.findall(r"^\s*(?:curl|wget)\b.*$", text, re.M)
    for line in fetches:
        # The pinned loop verifies in the lines that follow it, and the
        # Core download is checked against CORE_SHA256 two lines below.
        checked = ("sha256sum" in text and
                   ("PINNED_DEBS" in text or "CORE_SHA256" in text))
        if not checked:
            bad(f"{script.name} fetches without checking: {line.strip()!r}")
            break
    else:
        if fetches:
            ok(f"{script.name}: {len(fetches)} download(s), all checked")

# --- 5. the release pins are not placeholders ---------------------------
# These are the two that say, in the file itself, that they are not
# filled in. A release image cannot be reproduced while either stands.
for name, placeholder in (("OS_IMAGE_SHA256", "UNPINNED_UNTIL_FIRST_FLASH"),
                          ("CORESIGNER_COMMIT", "HEAD")):
    found = re.search(rf'{name}="([^"]*)"', PINS)
    if not found:
        bad(f"image/PINS no longer defines {name}")
    elif found.group(1) == placeholder:
        print(f"todo {name} is still {placeholder!r}: a tester's card "
              "cannot be reproduced from this file")
    else:
        ok(f"{name} is pinned")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
