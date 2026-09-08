"""Nothing in hw/vendor changes without somebody saying so.

2,251 lines here run on the device and none of them are ours. The README
calls that "audit upstream", which is a fair thing to say about code with
other eyes on it, and a hollow one unless the copy in this tree can be
compared with something.

It could not be. `hw/vendor/ur2/VENDORED.md` and both display drivers
cite "dev branch" and a date. A branch moves, so there is no point to
diff against, and a silent edit to a vendored file, whether ours or a
bad merge's, would look exactly like the original (found 2026-09-07).

That half is offline and cheap: it proves the files have not changed
SINCE they were vendored, which is what a supply-chain attack has to
beat.

The other half was done on 2026-09-08 and written down. It used to say a
comparison with upstream "needs a network this repository's whole point
is not having", which is true of the DEVICE and not of the dev machine,
where the vendoring happens. Fetched, compared byte for byte, and
recorded in `vendor-upstream.json` against the exact commit rather than
against a branch that moves:

    SeedSigner dev @ 85cd9a0211ee (2026-09-04)
    15 of 17 files byte-identical
    st7789.py and ili9341.py differ, and say so at the top

Anybody who does not want to take that on trust can repeat it:
    python3 tests/test_vendor_pinned.py --verify-upstream

which fetches that same commit and re-derives every hash. It needs git
and a network, so it is a dev-machine check and not part of the suite.

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
UPSTREAM = Path(__file__).with_name("vendor-upstream.json")

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


def check_upstream(now):
    """The half that needed a network, done once and written down.

    This file's docstring used to say a comparison with upstream "needs a
    network this repository's whole point is not having". True of the
    DEVICE and not of the dev machine, which is where the vendoring
    happens. Done on 2026-09-08 against SeedSigner dev, and the point in
    history it moved from is recorded, so an auditor can repeat it
    against the same commit rather than against a branch that has since
    moved on.

    What runs here, offline, is the cheap half: the recorded upstream
    hashes against the files in this tree. It proves the same thing the
    fetch proved, for anybody who trusts that the fetch happened, and
    `--verify-upstream` is how they stop trusting it and check.
    """
    if not UPSTREAM.exists():
        bad(f"{UPSTREAM.name} is missing, so 'audit upstream' is a phrase "
            "with nothing behind it")
        return
    rec = json.loads(UPSTREAM.read_text())
    src = rec["_source"]
    drift = []
    for rel, info in sorted(rec["files"].items()):
        if rel not in now:
            bad(f"{rel} is recorded against upstream but is no longer in "
                "this tree")
        elif info["identical"] and now[rel] != info["upstream_sha256"]:
            drift.append(rel)
    if drift:
        bad(f"{drift} were recorded as byte-identical to upstream "
            f"{src['commit'][:12]} and no longer are")
        return
    same = [r for r, i in rec["files"].items() if i["identical"]]
    diff = [r for r, i in rec["files"].items() if not i["identical"]]
    ok(f"{len(same)} of {len(rec['files'])} vendored files are byte-identical "
       f"to SeedSigner {src['commit'][:12]}, verified {src['verified']}")
    for rel in sorted(diff):
        head = (ROOT / rel).read_text()[:600]
        if "Modified:" not in head:
            bad(f"{rel} differs from upstream and its header does not say "
                "so, which is the one case a reader cannot detect")
    if diff:
        ok(f"and the {len(diff)} that differ each say so at the top: "
           f"{sorted(Path(r).name for r in diff)}")


def verify_upstream_now():
    """Fetch the recorded commit and re-derive every hash. Dev machine
    only: it needs git and a network."""
    import subprocess
    import tempfile
    rec = json.loads(UPSTREAM.read_text())
    src = rec["_source"]
    with tempfile.TemporaryDirectory() as tmp:
        print(f"fetching {src['repo']} at {src['commit'][:12]}…")
        subprocess.run(["git", "init", "--quiet", tmp], check=True)
        subprocess.run(["git", "-C", tmp, "remote", "add", "origin",
                        src["repo"]], check=True)
        r = subprocess.run(["git", "-C", tmp, "fetch", "--quiet", "--depth",
                            "1", "origin", src["commit"]])
        if r.returncode != 0:
            bad(f"could not fetch {src['commit']}; upstream may have "
                "garbage-collected it, which is itself worth knowing")
            return 1
        subprocess.run(["git", "-C", tmp, "checkout", "--quiet", "FETCH_HEAD"],
                       check=True)
        for rel, info in sorted(rec["files"].items()):
            theirs = Path(tmp) / info["upstream_path"]
            if not theirs.exists():
                bad(f"{info['upstream_path']} is not in {src['commit'][:12]}")
                continue
            got = hashlib.sha256(theirs.read_bytes()).hexdigest()
            ours = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            if got != info["upstream_sha256"]:
                bad(f"{rel}: upstream hash recorded as "
                    f"{info['upstream_sha256'][:12]}, fetched "
                    f"{got[:12]}. The record is wrong.")
            elif (got == ours) != info["identical"]:
                bad(f"{rel}: recorded identical={info['identical']}, "
                    f"actually {got == ours}")
            else:
                state = "identical to" if info["identical"] else "differs from"
                ok(f"{Path(rel).name} {state} upstream, as recorded")
    print()
    print("FAILED %d" % len(fails) if fails else
          f"UPSTREAM VERIFIED at {src['commit'][:12]}")
    return 1 if fails else 0


def main():
    now = shipped()
    if "--verify-upstream" in sys.argv:
        return verify_upstream_now()
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

    check_upstream(now)

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
