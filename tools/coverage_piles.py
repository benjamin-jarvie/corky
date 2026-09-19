"""Sort every uncovered statement in coresigner/ into audit A5's three piles.

Run tools/coverage_run.sh first; this reads the .coverage it leaves.

A5 asked for the code that has never executed, sorted into: reachable in
a test and simply untested; reachable only on the device; and unreachable
at all. The table below is the answer, one row per FUNCTION.

Per function, not per line, since 2026-09-08. The first version pinned
line numbers, and by the time a reviewer read it two of them had drifted:
main.py:266 was a comment and main.py:1138 was blank. Neither drift made
a sound. The script asserted that every uncovered line falls in a range,
which catches a line arriving; it never asked whether a range still holds
a line, which is what catches one leaving. A range that has slid onto a
blank line claims nothing, silently, and the pile totals shrink with no
alarm. Both directions are asserted now, and a function name survives
every edit inside the function, which is where the churn is.

Rule 6 applies to this file. Each pile's size is counted here, never
estimated, and the ticket quotes what this prints.
"""
import ast
import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, function, pile, what). Every function holding an uncovered line
# must appear exactly once, and every row here must still name a function
# that exists and still holds one.
C = [
 ("coresigner/hal.py", "DeviceDisplay.__init__", 2,
  "ST7789 panel init over SPI"),
 ("coresigner/hal.py", "DeviceDisplay.show", 2,
  "pushing a frame to the panel"),
 ("coresigner/hal.py", "DeviceButtons.pressed", 2,
  "the stuck-key break, needs GPIO"),
 ("coresigner/qrsource.py", "ImageQrSource.images", 3,
  "the abstract marker, raise NotImplementedError"),
 ("coresigner/qrsource.py", "CameraQrSource.images", 2,
  "picamera2 open, frame loop, teardown"),
 ("coresigner/qrsource.py", "DevQrSource.strings", 1,
  "dev paths with neither --qr-key nor --qr-psbt"),
 ("coresigner/qrsource.py", "DevQrSource.scan_psbt_frames", 1,
  "no PSBT file in a dev session"),
 ("coresigner/main.py", "_next_kind", 1,
  "called with a policy not in the ring"),
 ("coresigner/main.py", "_cell_move", 1,
  "given a key it does not handle"),
 ("coresigner/main.py", "Session.run", 1,
  "startup clear-out and power-off teardown raise"),
 ("coresigner/main.py", "Session.state_home", 1,
  "UP and LEFT on the grid; a flow raises a Core error"),
 ("coresigner/main.py", "Session.state_sign", 1,
  "Sign with no key loaded"),
 ("coresigner/main.py", "Session._tool_check_address", 1,
  "no key loaded; scan aborts, times out, or Core fails"),
 ("coresigner/main.py", "Session._check_address", 1,
  "no key loaded; a BIP21 URI; getaddressinfo raises"),
 ("coresigner/main.py", "Session._pick", 1,
  "UP in the shared list loop"),
 ("coresigner/main.py", "Session._export", 1,
  "leaving the export menu"),
 ("coresigner/main.py", "Session._export_one", 1,
  "the two refusals"),
 ("coresigner/main.py", "Session._export_qr", 1,
  "the QR card and its keys"),
 ("coresigner/main.py", "Session._export_text", 1,
  "the paged descriptor and its keys"),
 ("coresigner/main.py", "Session._page_addresses", 1,
  "the empty-order guard, a Core error, paging up"),
 ("coresigner/main.py", "Session._export_file", 1,
  "the write refusal"),
 ("coresigner/main.py", "Session._backup_paper", 1,
  "leaving the paper backup"),
 ("coresigner/main.py", "Session._discard", 1,
  "both ways out of the discard confirm"),
 ("coresigner/main.py", "Session._key_by_scan", 1,
  "the abort, and opening scanned descriptors"),
 ("coresigner/main.py", "Session._text_entry", 1,
  "the action bar: confirm, cancel, and C to jump"),
 ("coresigner/main.py", "Session._keymaterial", 1,
  "a rejected payload, and backing out"),
 ("coresigner/main.py", "Session._scan_until", 1,
  "the scan stream runs dry and restarts"),
 ("coresigner/main.py", "Session._guard_key_payload", 1,
  "a payload that is not text"),
 ("coresigner/main.py", "Session._key_xprv_typed", 1,
  "typing cancelled"),
 ("coresigner/main.py", "Session._tool_leak_check", 1,
  "the script fails to run; scrolling the report"),
 ("coresigner/main.py", "Session._show_backup", 1,
  "paging back off the first page"),
 ("coresigner/main.py", "Session._verify_backup", 1,
  "the refusal"),
 ("coresigner/main.py", "Session._check_typed", 1,
  "leaving the check screen with and without errors"),
 ("coresigner/main.py", "Session._check_entry", 1,
  "the caret keys and the grid/entry focus swap"),
 ("coresigner/main.py", "Session.state_load", 1,
  "the no-channel result screen; leaving the chooser"),
 ("coresigner/main.py", "Session._load_by_stick", 1,
  "an unreadable file, and one still being written"),
 ("coresigner/main.py", "Session._load_by_qr.on_event", 1,
  "the large-frame and restart notices"),
 ("coresigner/main.py", "Session._load_by_qr", 1,
  "a stalled scan, and the restart after it"),
 ("coresigner/main.py", "Session._key_for", 1,
  "no key loaded, and no descriptor for the policy"),
 ("coresigner/main.py", "Session.state_review", 1,
  "the no-outputs result; moving and leaving review"),
 ("coresigner/main.py", "Session._sign_and_deliver", 1,
  "the result screen after a failed delivery"),
 ("coresigner/main.py", "main", 2,
  "the device branch that builds the real HAL"),
 ("coresigner/qrchannel.py", "frame_identity", 1,
  "a single-part UR has no sequence"),
 ("coresigner/qrchannel.py", "decode_image", 1,
  "a non-ascii QR is not a UR frame"),
 ("coresigner/qrchannel.py", "FrameAssembler.feed", 1,
  "an unexpected UR type, and a malformed container"),
 ("coresigner/qrchannel.py", "PsbtScan.feed", 1,
  "a frame accepted after the payload is complete"),
 ("coresigner/qrchannel.py", "PsbtScan._consider", 1,
  "the large-frame advisory repeats"),
 ("coresigner/qrchannel.py", "frames_to_images", 1,
  "a payload too large to render"),
 ("coresigner/screens.py", "_tracked", 1,
  "right-anchored tracked text"),
 ("coresigner/screens.py", "_fit", 1,
  "the character-by-character truncation"),
 ("coresigner/screens.py", "_fit_block", 1,
  "the smallest size still does not fit"),
 ("coresigner/screens.py", "scanning", 1,
  "the viewfinder: rotate, fill, crop and the progress bar"),
 ("coresigner/screens.py", "backup_page", 1,
  "the footer on the last page"),
 ("coresigner/signer.py", "_import", 1,
  "importdescriptors reports failures"),
 ("coresigner/signer.py", "open_session_descriptors", 1,
  "a multisig descriptor is refused"),
 ("coresigner/signer.py", "export_descriptor", 1,
  "a policy this key does not have"),
 ("coresigner/signer.py", "write_watch_only", 1,
  "the watch-only import fails"),
 ("coresigner/signer.py", "generate_wallet", 1,
  "generation fails and the wallet is dropped"),
 ("coresigner/signer.py", "master_xprv", 1,
  "the master key cannot be read"),
 ("coresigner/signer.py", "opens_wallet", 1,
  "no shape for the policy; a descriptor with no origin"),
 ("coresigner/signer.py", "master_fingerprint", 1,
  "no wallet loaded, so no fingerprint"),
]

PILES = {1: "reachable in a test, simply untested",
         2: "reachable only on the device",
         3: "unreachable at all"}


def owners(path):
    """line number -> the qualified name of the function holding it.

    Lines outside any function map to nothing, and land in "<module>".
    """
    out = {}

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{ch.name}"
                for ln in range(ch.lineno, ch.end_lineno + 1):
                    out[ln] = name
                walk(ch, name + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, f"{prefix}{ch.name}.")

    walk(ast.parse(path.read_text()), "")
    return out


def defined(path):
    """Every qualified function name in one file."""
    return set(owners(path).values())


def classify(cov):
    """Put every uncovered line in a pile. Returns (piles, by_file, claimed,
    unclaimed)."""
    piles = collections.Counter()
    by_file = collections.defaultdict(collections.Counter)
    claimed = collections.Counter()
    unclaimed = collections.defaultdict(list)
    index = {(fn, f): pile for fn, f, pile, _ in C}

    for fn, info in sorted(cov["files"].items()):
        who = owners(ROOT / fn)
        for line in sorted(info["missing_lines"]):
            f = who.get(line, "<module>")
            pile = index.get((fn, f))
            if pile is None:
                unclaimed[fn].append((f, line))
            else:
                claimed[(fn, f)] += 1
                piles[pile] += 1
                by_file[fn][pile] += 1

    return piles, by_file, claimed, unclaimed


def stale(claimed, unclaimed):
    """Both directions: a line in no row, and a row holding no line."""
    problems = []
    for fn, hits in sorted(unclaimed.items()):
        for f, line in hits:
            problems.append(f"{fn}::{f} line {line} is in no row below")
    # The reverse direction, which the line-number version never asked.
    for fn, f, _, _ in C:
        if f not in defined(ROOT / fn):
            problems.append(f"{fn}::{f} is named below but no longer exists")
        elif not claimed[(fn, f)]:
            problems.append(f"{fn}::{f} holds no uncovered line any more; "
                            f"a test now reaches it, so drop the row")
    return problems


def names_only():
    """Assertion 2 alone: every row still names a function that exists.

    No coverage data, so run_tests.sh can afford it on every run. It
    catches the drift that a rename or a deletion causes, which is the
    kind that arrives without anybody thinking about this file. The other
    two assertions need a measurement and stay in the full run.
    """
    gone = [f"{fn}::{f}" for fn, f, _, _ in C if f not in defined(ROOT / fn)]
    for g in gone:
        print(f"  {g} is named in coverage_piles.py but no longer exists")
    return 1 if gone else 0


def main():
    if "--names-only" in sys.argv:
        return names_only()
    subprocess.run(["python3", "-m", "coverage", "json", "-o", "/tmp/cov.json"],
                   check=True, capture_output=True, cwd=ROOT)
    with open("/tmp/cov.json") as fh:
        cov = json.load(fh)
    piles, by_file, claimed, unclaimed = classify(cov)
    problems = stale(claimed, unclaimed)
    if problems:
        print("STALE, in %d place(s):" % len(problems))
        for p in problems:
            print(f"  {p}")
        print("\nThe table is a classification, not a filter. Read the new"
              "\ncode and put each function in a pile; do not widen a row to"
              "\nmake this quiet.")
        return 1

    print(f"every uncovered line falls in exactly one of {len(C)} functions")
    print()
    for p in (1, 2, 3):
        print(f"pile {p}: {piles[p]:4d} statements  {PILES[p]}")
    print(f"total:  {sum(piles.values()):4d}")
    print()
    for fn in sorted(by_file):
        c = by_file[fn]
        print(f"  {fn:24s} pile1={c[1]:4d} pile2={c[2]:3d} pile3={c[3]:2d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
