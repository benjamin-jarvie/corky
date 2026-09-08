"""Nothing in hw/vendor changes without somebody saying so.

2,251 lines here run on the device and none of them are ours. The README
calls that "audit upstream", which is a fair thing to say about code with
other eyes on it, and a hollow one unless the copy in this tree can be
compared with something.

It could not be. `hw/vendor/ur2/VENDORED.md` and both display drivers
cite "dev branch" and a date. A branch moves, so there is no point to
diff against, and a silent edit to a vendored file, whether ours or a
bad merge's, would look exactly like the original (found 2026-09-07).

This does not prove the files match upstream; only a fetch of the exact
upstream commit could, and that needs a network this repository's whole
point is not having. What it proves is that they have not changed SINCE
they were vendored, which is the half that can be checked offline and
the half a supply-chain attack has to beat.

Regenerate deliberately, never casually:
    python3 tests/test_vendor_pinned.py --update

Run: python3 tests/test_vendor_pinned.py   (no bitcoind, no hardware)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "hw" / "vendor"
PINS = Path(__file__).with_name("vendor-pins.json")

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    print("FAIL", m)
    fails.append(m)


def shipped():
    """Every vendored file that reaches the device, in a stable order."""
    out = {}
    for p in sorted(VENDOR.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main():
    now = shipped()
    if "--update" in sys.argv:
        PINS.write_text(json.dumps(now, indent=2, sort_keys=True) + "\n")
        print(f"wrote {len(now)} pins to {PINS.name}")
        return 0
    if not PINS.exists():
        bad(f"{PINS.name} is missing; run with --update to create it")
        print("\nFAILED 1")
        return 1
    pinned = json.loads(PINS.read_text())

    added = sorted(set(now) - set(pinned))
    gone = sorted(set(pinned) - set(now))
    changed = sorted(f for f in set(now) & set(pinned) if now[f] != pinned[f])

    if added:
        bad(f"vendored files nobody pinned: {added}. If they are meant to "
            "be here, say where they came from and run --update.")
    if gone:
        bad(f"pinned files that have vanished: {gone}")
    if changed:
        bad(f"vendored code CHANGED without the pin moving: {changed}. "
            "That is either an edit to somebody else's code or a bad "
            "merge, and either way it needs a reason before --update.")
    if not (added or gone or changed):
        ok(f"all {len(now)} vendored files match their pins")

    # And the provenance has to be readable, per file, or "audit upstream"
    # means nothing to whoever tries.
    origins = {"hw/vendor/ur2/VENDORED.md", "hw/vendor/fonts/NOTICE.md"}
    for rel in sorted(now):
        if rel.endswith(".py") and not rel.startswith("hw/vendor/ur2/"):
            head = (ROOT / rel).read_text()[:400]
            if "Vendored from" not in head:
                bad(f"{rel} does not say where it came from")
    missing = sorted(o for o in origins if not (ROOT / o).exists())
    if missing:
        bad(f"missing provenance notes: {missing}")
    elif not fails:
        ok("every vendored module says where it came from")

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
