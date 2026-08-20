"""Fast unit tests for the file channel: no bitcoind, no PSBT signing.

Covers wait_stable (mid-copy guard) and read_psbt size/encoding boundaries,
which the e2e test never exercises. Run: python3 tests/test_filechannel.py
"""

import base64
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
import filechannel  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r} want {want!r}")
        print(f"FAIL {name}")
    else:
        print(f"ok   {name}")


def check_raises(name, fn, *a):
    try:
        fn(*a)
    except filechannel.FileChannelError:
        print(f"ok   {name}")
    else:
        FAILURES.append(f"{name}: no error raised")
        print(f"FAIL {name}")


tmp = Path(tempfile.mkdtemp(prefix="corky-fc-unit-"))

# ---- wait_stable ------------------------------------------------------

# A file that already sits still returns True quickly.
still = tmp / "still.psbt"
still.write_bytes(b"\x70\x73\x62\x74\xff" + b"\x00" * 40)
t0 = time.monotonic()
check("stable file is stable", filechannel.wait_stable(still, checks=3, interval=0.02), True)
# It must actually wait for `checks` stable polls, not return on the first.
check("waited at least (checks-1)*interval", time.monotonic() - t0 >= 0.04, True)

# A missing file returns False (never raises).
check("missing file not stable", filechannel.wait_stable(tmp / "nope.psbt"), False)

# An empty file is never "stable" (size > 0 is required), so it times out.
empty = tmp / "empty.psbt"
empty.write_bytes(b"")
check("empty file not stable", filechannel.wait_stable(empty, checks=2, interval=0.01), False)

# A file still being written must NOT be reported stable until writing
# stops. Drive wait_stable with a scripted stat() so the timing is exact:
# each poll returns the next size in the sequence.
class _FakeStat:
    def __init__(self, size):
        self.st_size = size


class _ScriptedPath:
    def __init__(self, sizes):
        self._sizes = list(sizes)
        self._i = 0

    def stat(self):
        size = self._sizes[min(self._i, len(self._sizes) - 1)]
        self._i += 1
        return _FakeStat(size)


# Size never stops changing -> never three equal polls in a row -> False.
grow = _ScriptedPath([10 * i for i in range(1, 60)])
check("growing file not stable", filechannel.wait_stable(grow, checks=3, interval=0), False)

# Grows, then holds at 4000 for enough polls to satisfy checks=3 -> True.
settle = _ScriptedPath([10, 20, 30, 4000, 4000, 4000, 4000])
check("file stable once writing stops", filechannel.wait_stable(settle, checks=3, interval=0), True)

# A 1-byte file that holds still is stable: the guard is size > 0, not > 1.
tiny = _ScriptedPath([1, 1, 1, 1])
check("1-byte stable file is stable", filechannel.wait_stable(tiny, checks=3, interval=0), True)

# ---- read_psbt size + encoding boundaries -----------------------------

# Zero-length file is refused.
check_raises("empty file refused", filechannel.read_psbt, empty)

# The cap is exactly 4 MiB. Pin the boundary with a LITERAL size, not
# filechannel.MAX_PSBT_BYTES: sizing the test files from the constant would
# move them together with any mutation of it and hide the change.
CAP = 4 * 1024 * 1024
check("cap constant is 4 MiB", filechannel.MAX_PSBT_BYTES, CAP)
at_cap = tmp / "atcap.psbt"
at_cap.write_bytes(b"\x00" * CAP)
check("max-size (4 MiB) file accepted", base64.b64decode(filechannel.read_psbt(at_cap)),
      b"\x00" * CAP)

over = tmp / "over.psbt"
over.write_bytes(b"\x00" * (CAP + 1))
check_raises("over-cap (4 MiB + 1) file refused", filechannel.read_psbt, over)

# Binary PSBT: bytes that are not clean base64 get base64-encoded.
binfile = tmp / "bin.psbt"
binfile.write_bytes(b"psbt\xff\x01\x02\x03")
check("binary psbt re-encoded", base64.b64decode(filechannel.read_psbt(binfile)),
      b"psbt\xff\x01\x02\x03")

# Text PSBT (base64 with wrapped whitespace) is returned as-is, whitespace
# stripped, not double-encoded.
payload = b"psbt\xff" + bytes(range(60))
b64 = base64.b64encode(payload).decode()
wrapped = b64[:20] + "\n" + b64[20:40] + "\n" + b64[40:]
txtfile = tmp / "txt.psbt"
txtfile.write_text(wrapped)
got = filechannel.read_psbt(txtfile)
check("text psbt whitespace-stripped", got, b64)
check("text psbt not double-encoded", base64.b64decode(got), payload)

# find_unsigned skips already-signed files.
(tmp / "a.psbt").write_bytes(b"x")
(tmp / "a-signed.psbt").write_bytes(b"x")
names = {p.name for p in filechannel.find_unsigned(tmp)}
check("find_unsigned excludes signed", "a-signed.psbt" in names, False)
check("find_unsigned includes unsigned", "a.psbt" in names, True)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURES")
    for f in FAILURES:
        print(f)
    sys.exit(1)
print("FILE CHANNEL UNIT PASS")
