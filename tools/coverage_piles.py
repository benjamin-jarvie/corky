"""Sort every uncovered statement in corky/ into audit A5's three piles.

Run tools/coverage_run.sh first; this reads the .coverage it leaves.

A5 asked for the code that has never executed, sorted into: reachable in a
test and simply untested; reachable only on the device; and unreachable at
all. The ranges below are the answer, one line per region, and the script
asserts that every uncovered line falls in exactly one of them. That
assertion is the point: a classification with a gap in it is an opinion.

Rule 6 applies to this file. Each pile's size is counted here, never
estimated, and the ticket quotes what this prints.
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
subprocess.run(["python3", "-m", "coverage", "json", "-o", "/tmp/cov.json"],
               check=True, capture_output=True, cwd=ROOT)
with open("/tmp/cov.json") as fh:
    d = json.load(fh)

# (file, first, last, pile, what). Ranges are inclusive and must cover
# every missing line exactly once; the script asserts that below.
C = [
 ("corky/hal.py",56,60,2,"ST7789 panel init over SPI"),
 ("corky/hal.py",76,76,2,"pushing a frame to the panel"),
 ("corky/hal.py",170,170,1,"the stuck-key break in pressed()"),
 ("corky/main.py",113,113,3,"ImageQrSource.images(), the abstract marker"),
 ("corky/main.py",167,171,2,"picamera2 open and start"),
 ("corky/main.py",178,184,2,"the camera frame loop and its teardown"),
 ("corky/main.py",222,226,1,"DevQrSource paths no dev run takes yet"),
 ("corky/main.py",231,231,1,"DevQrSource.scan_psbt_frames with no PSBT file"),
 ("corky/main.py",266,266,1,"_next_kind called with a policy not in the ring"),
 ("corky/main.py",314,314,1,"_grid_move given a key it does not handle"),
 ("corky/main.py",360,365,1,"startup clear-out raises"),
 ("corky/main.py",374,380,1,"power-off teardown raises"),
 ("corky/main.py",482,482,1,"UP on the home grid"),
 ("corky/main.py",486,486,1,"LEFT on the home grid"),
 ("corky/main.py",504,506,1,"a flow raises a Core error, home reports it"),
 ("corky/main.py",547,547,1,"branch: the key list redraw"),
 ("corky/main.py",560,561,1,"Sign with no key loaded"),
 ("corky/main.py",572,573,1,"Check an address with no key loaded"),
 ("corky/main.py",578,583,1,"the address scan aborts, times out, or Core fails"),
 ("corky/main.py",593,594,1,"_check_address with no key loaded"),
 ("corky/main.py",597,597,1,"a BIP21 payment URI on the address scan"),
 ("corky/main.py",602,604,1,"getaddressinfo raises"),
 ("corky/main.py",665,665,1,"branch: leaving the key menu"),
 ("corky/main.py",679,679,1,"branch: leaving Tools"),
 ("corky/main.py",697,697,1,"UP in _pick"),
 ("corky/main.py",702,702,1,"branch: _pick redraw"),
 ("corky/main.py",773,773,1,"leaving the export menu"),
 ("corky/main.py",777,777,1,"branch: the export menu loop"),
 ("corky/main.py",792,796,1,"leaving the destination chooser; nothing to show"),
 ("corky/main.py",811,823,1,"_export_qr: the QR card and its keys"),
 ("corky/main.py",827,843,1,"_export_text: the paged descriptor and its keys"),
 ("corky/main.py",874,874,1,"the address screen opened on a policy the key lacks"),
 ("corky/main.py",882,883,1,"deriveaddresses raises mid-walk"),
 ("corky/main.py",898,899,1,"UP on the address screen"),
 ("corky/main.py",914,914,1,"leaving the watch-only destination chooser"),
 ("corky/main.py",943,943,1,"leaving the backup screen"),
 ("corky/main.py",959,964,1,"the discard confirmation: cancel and redraw"),
 ("corky/main.py",1015,1019,1,"a scanned DESCRIPTOR opens the session"),
 ("corky/main.py",1041,1047,1,"the text entry action bar"),
 ("corky/main.py",1062,1063,1,"C jumps to the action bar"),
 ("corky/main.py",1075,1078,1,"the key scan aborts or times out"),
 ("corky/main.py",1082,1083,1,"leaving the load screen"),
 ("corky/main.py",1138,1139,1,"the scan stream runs dry and restarts"),
 ("corky/main.py",1168,1169,1,"a key payload with non-ascii bytes"),
 ("corky/main.py",1178,1178,1,"an empty typed key"),
 ("corky/main.py",1202,1204,1,"the leak-check tool fails to launch"),
 ("corky/main.py",1211,1211,1,"a short line in the leak report"),
 ("corky/main.py",1219,1219,1,"an empty leak report"),
 ("corky/main.py",1226,1229,1,"scrolling the leak report"),
 ("corky/main.py",1275,1278,1,"paging back through the backup"),
 ("corky/main.py",1281,1281,1,"branch: the backup page loop"),
 ("corky/main.py",1309,1309,1,"abandoning the backup check"),
 ("corky/main.py",1326,1334,1,"the backup check: Core raises, or says not the same key"),
 ("corky/main.py",1354,1354,1,"abandoning the check on a page"),
 ("corky/main.py",1373,1376,1,"leaving a checked page"),
 ("corky/main.py",1408,1421,1,"the typed-entry caret, delete and focus keys"),
 ("corky/main.py",1431,1436,1,"backspace at the caret"),
 ("corky/main.py",1460,1463,1,"no channel can load a PSBT at all"),
 ("corky/main.py",1473,1476,1,"choosing between the two PSBT channels"),
 ("corky/main.py",1492,1499,1,"the stick file vanishes or cannot be stat'd"),
 ("corky/main.py",1495,1495,1,"branch: a file appears on the stick"),
 ("corky/main.py",1514,1517,1,"a file still being written; leaving the wait"),
 ("corky/main.py",1531,1533,1,"the large-frame advisory and the restart notice"),
 ("corky/main.py",1537,1537,1,"branch: the scan loop"),
 ("corky/main.py",1560,1565,1,"the PSBT scan stalls and starts again"),
 ("corky/main.py",1592,1592,1,"branch: the scan redraw"),
 ("corky/main.py",1609,1610,1,"a PSBT arrives with no key loaded"),
 ("corky/main.py",1626,1626,1,"declining to pick a key for the transaction"),
 ("corky/main.py",1638,1642,1,"REFUSED: the PSBT states no fee"),
 ("corky/main.py",1653,1653,1,"LEFT/RIGHT on the review screen"),
 ("corky/main.py",1668,1669,1,"BACK from review, key still loaded"),
 ("corky/main.py",1682,1686,1,"the wallet cannot complete the PSBT"),
 ("corky/main.py",1737,1737,1,"the spinner stops mid-cycle"),
 ("corky/main.py",1752,1752,1,"branch: the spinner loop"),
 ("corky/main.py",1775,1777,2,"the real panel, keypad and camera are built"),
 ("corky/qrchannel.py",103,107,1,"a single-part UR, and a malformed container"),
 ("corky/qrchannel.py",123,124,1,"a non-ascii QR is not a UR frame"),
 ("corky/qrchannel.py",175,175,1,"a null frame"),
 ("corky/qrchannel.py",182,188,1,"the wrong UR type, and a malformed container"),
 ("corky/qrchannel.py",230,231,1,"progress asked for after the PSBT is complete"),
 ("corky/qrchannel.py",245,245,1,"the no-progress timeout fires"),
 ("corky/qrchannel.py",266,266,1,"the large-frame advisory repeats"),
 ("corky/qrchannel.py",274,275,1,"the reason line for a stalled scan"),
 ("corky/qrchannel.py",305,305,1,"a QR too big for the panel"),
 ("corky/qrchannel.py",330,330,1,"branch: the frame encoder loop"),
 ("corky/screens.py",102,107,1,"text truncated with an ellipsis"),
 ("corky/screens.py",123,130,1,"text shrunk to the floor, then truncated"),
 ("corky/screens.py",401,431,1,"the viewfinder painting a real camera frame"),
 ("corky/screens.py",586,586,1,"branch: the script menu"),
 ("corky/screens.py",749,749,1,"branch: the address screen"),
 ("corky/screens.py",790,792,1,"branch: the review screen"),
 ("corky/screens.py",960,963,1,"branch: the leak report"),
 ("corky/screens.py",1029,1031,1,"branch: the backup page"),
 ("corky/screens.py",1044,1049,1,"the backup page footer for the last page"),
 ("corky/screens.py",1096,1096,1,"branch: the check screen"),
 ("corky/signer.py",238,239,1,"importdescriptors reports failures"),
 ("corky/signer.py",269,269,1,"a multisig descriptor is refused"),
 ("corky/signer.py",360,360,1,"a policy this key does not have"),
 ("corky/signer.py",402,402,1,"the watch-only import fails"),
 ("corky/signer.py",441,441,1,"branch: the prevout index is out of range"),
 ("corky/signer.py",471,471,1,"branch: the owners loop"),
 ("corky/signer.py",512,514,1,"a session whose master key cannot be read is dropped"),
 ("corky/signer.py",534,534,1,"descriptors that disagree about the master key"),
 ("corky/signer.py",588,592,1,"no wallet loaded, so no fingerprint"),
]

piles = collections.Counter()
by_file = collections.defaultdict(lambda: collections.Counter())
unclaimed = {}
for fn, info in sorted(d["files"].items()):
    miss = set(info["missing_lines"])
    for line in sorted(miss):
        hit = [c for c in C if c[0] == fn and c[1] <= line <= c[2]]
        if not hit:
            unclaimed.setdefault(fn, []).append(line)
        else:
            piles[hit[0][3]] += 1
            by_file[fn][hit[0][3]] += 1
if unclaimed:
    print("STALE: these uncovered lines fall in no range below.")
    for fn, lines in unclaimed.items():
        print(f"  {fn}: {lines}")
    print("\nThe ranges are a snapshot of the tree A5 measured. Re-read the"
          "\nnew code and place each line in a pile; do not widen a range to"
          "\nmake this quiet.")
    sys.exit(1)
print("every uncovered line falls in exactly one pile")
print()
names = {1: "reachable in a test, simply untested",
         2: "reachable only on the device",
         3: "unreachable at all"}
for p in (1, 2, 3):
    print(f"pile {p}: {piles[p]:4d} statements  {names[p]}")
print(f"total:  {sum(piles.values()):4d}")
print()
for fn in sorted(by_file):
    c = by_file[fn]
    print(f"  {fn:24s} pile1={c[1]:4d} pile2={c[2]:3d} pile3={c[3]:2d}")
