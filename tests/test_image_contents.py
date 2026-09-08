"""The image carries the program and nothing else.

`prepare-sd.sh` used to run `git archive HEAD`, which put the whole
repository on the signer: every test, every ticket, the articles and the
art, and 38 Python files that never execute there. A signer should carry
what it runs. Every extra file is one more thing a reader has to audit
before they can believe the device.

This suite is the pin. It builds the archive the way prepare-sd.sh does,
then asserts two things that must both stay true: everything provision.sh
reaches for is inside it, and nothing that only belongs to development is.

Run: python3 tests/test_image_contents.py (no bitcoind needed)
"""
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def archive_paths():
    """Exactly what prepare-sd.sh puts in corky.tar.gz, read out of the
    script itself so the two cannot drift apart."""
    script = (ROOT / "image" / "prepare-sd.sh").read_text()
    m = re.search(r'archive --format=tar\.gz -o "\$BOOT/corky\.tar\.gz" HEAD \\?\s*\n?\s*([^\n]*)',
                  script)
    if not m or not m.group(1).strip():
        bad("prepare-sd.sh no longer names the paths it ships")
        return None, []
    spec = m.group(1).split("#")[0].split()
    out = subprocess.run(["git", "archive", "--format=tar", "HEAD", *spec],
                         cwd=ROOT, capture_output=True)
    if out.returncode:
        bad(f"git archive refused {spec}: {out.stderr[-200:]!r}")
        return spec, []
    import io
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tar:
        return spec, [m.name for m in tar.getmembers() if m.isfile()]


def main():
    spec, names = archive_paths()
    if not names:
        print("FAILED 1")
        sys.exit(1)
    ok(f"prepare-sd.sh ships {len(spec)} paths, {len(names)} files")

    # 1. Everything provision.sh installs from /opt/corky must be present,
    #    or the first real flash dies partway through provisioning.
    provision = (ROOT / "image" / "provision.sh").read_text()
    needed = set()
    for line in provision.splitlines():
        for hit in re.findall(r"/opt/corky/([A-Za-z0-9_@./-]+)", line):
            # A path at the end of a cp or install line is where the file
            # GOES, not a file the image must already carry. PINS.installed
            # is written by provisioning itself.
            if line.rstrip().endswith("/opt/corky/" + hit):
                continue
            needed.add(hit)
    needed = sorted(needed)
    missing = [n for n in needed if n not in names]
    if not missing:
        ok(f"every path provision.sh installs is in the image ({len(needed)})")
    else:
        bad(f"provision.sh would not find: {missing}")

    # 2. The program itself, the vendored code it imports, and the three
    #    scripts a tester runs ON the device. verify-install.sh is the one
    #    that matters most and shipped in nothing until audit A7: it is how
    #    anybody, including a tester who trusts neither of us, checks that
    #    the card in their hand matches the repository they can read.
    required = ("corky/main.py", "corky/signer.py", "corky/screens.py",
                "corky/qrchannel.py", "corky/filechannel.py",
                "corky/hal.py", "corky/splash.py",
                "image/leak-check.sh", "image/harden.sh", "image/unharden.sh",
                "image/verify-install.sh", "image/PINS",
                "hw/vendor/st7789.py", "hw/vendor/ur2/__init__.py",
                "hw/vendor/fonts/fa-solid-subset.ttf", "LICENSE")
    absent = [r for r in required if r not in names]
    if not absent:
        ok("the program, the vendored drivers, the font and the licence ship")
    else:
        bad(f"the image is missing {absent}")

    # 3. And nothing that belongs only to development.
    unwanted = {
        "tests/": "the suites",
        "docs/": "the wayfinder maps and tickets",
        "art/": "the artwork",
        "tools/": "the dev scripts",
        "PLAN.md": "the planning record",
        "TESTING.md": "the testing rules",
        "ISSUES.md": "the defect list",
        "ORDER.md": "the parts list",
        "CONTEXT.md": "the glossary",
        "run_tests.sh": "the test runner",
        "ruff.toml": "the linter config",
        "requirements-dev.txt": "the dev tools",
    }
    leaked = sorted({why for prefix, why in unwanted.items()
                     for n in names if n.startswith(prefix)})
    if not leaked:
        ok(f"none of the {len(unwanted)} development-only paths ship")
    else:
        bad(f"the signer would carry: {leaked}")

    # 4. No Python on the device except the program and what it imports.
    stray = [n for n in names if n.endswith(".py")
             and not n.startswith(("corky/", "hw/vendor/"))]
    if not stray:
        ok("no Python ships that the device does not run")
    else:
        bad(f"Python that never runs on the device: {stray}")

    # 5. The pins a device can be checked against. The tarball hash can
    #    only be used at install time, which audit A7 pointed out is the
    #    one moment nobody watches; the binary hashes make an installed
    #    device re-checkable for ever.
    pins = (ROOT / "image" / "PINS").read_text()
    for key in ("CORE_BIN_SHA256", "CLI_BIN_SHA256"):
        m = re.search(rf'{key}="([0-9a-f]*)"', pins)
        if m and len(m.group(1)) == 64:
            ok(f"{key} is pinned, so an installed device can be re-checked")
        else:
            bad(f"{key} is missing or not a sha256 in image/PINS, so "
                "verify-install.sh cannot check the binary on the board")

    # 6. The signer's own payload must be verified before it is unpacked
    #    as root. Bitcoin Core is checked against a sha256 and eleven GPG
    #    signatures; corky.tar.gz was taken on trust, unpacked as root and
    #    then run as root at every boot (audit of image/, 2026-09-08).
    prov = (ROOT / "image" / "provision.sh").read_text()
    prep = (ROOT / "image" / "prepare-sd.sh").read_text()
    if "CORKY_TARBALL_SHA256" not in prep:
        bad("prepare-sd.sh records no hash for corky.tar.gz, so the "
            "device has nothing to check the payload against")
    elif "CORKY_TARBALL_SHA256" not in prov:
        bad("provision.sh does not check corky.tar.gz against a hash "
            "before unpacking it as root")
    elif "sha256sum -c" not in prov:
        bad("provision.sh names the hash but never verifies it")
    else:
        ok("the payload is hashed when the card is written and verified "
           "before it is unpacked")
    if "--no-same-owner" not in prov:
        bad("tar unpacks with the tarball's own ownership; everything in "
            "/opt/corky should belong to root whatever the archive says")
    else:
        ok("the payload unpacks as root, whatever the archive claims")

    # 7. A card must say which Corky is on it. CORKY_COMMIT="HEAD" told a
    #    tester nothing and made two cards a week apart indistinguishable
    #    (audit A7).
    if 'CORKY_COMMIT=' not in prep or "rev-parse HEAD" not in prep:
        bad("prepare-sd.sh does not pin the commit it packed into the "
            "card's PINS, so a tester cannot say which Corky they have")
    else:
        ok("the card records the exact commit it was written from")

    # 8. git archive packs HEAD, so uncommitted work silently does not
    #    reach the card.
    if "diff-index --quiet HEAD" not in prep:
        bad("prepare-sd.sh writes a card from HEAD without checking for "
            "uncommitted changes, so edited code can silently not ship")
    else:
        ok("a dirty working tree stops the card being written")

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
