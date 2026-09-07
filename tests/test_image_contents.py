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
        "articles/": "the articles",
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

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
