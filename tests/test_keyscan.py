"""Scanning a key from the camera, with stopping rules (ticket 09).

Both "Scan a key" entries raised on the board until now:
    RuntimeError: SeedQR scanning not wired yet (M2); type the seed
The camera itself works (M1). What was missing is a scan that can end: a
frame that does not decode is skipped, a scan that makes no progress gives
up and says why, and a button aborts.

Run: python3 tests/test_keyscan.py (no bitcoind needed)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import main as corky_main  # noqa: E402
import qrchannel  # noqa: E402
import screens  # noqa: E402

XPRV = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"
# Core's own descriptor for the key above, with the checksum Core computes
# for it. The first version of this line spliced a real xpub onto a
# checksum from a different descriptor, and Core rejected the result:
# "Provided checksum 'lgch27l9' does not match computed checksum
# 'rvhyypq0'". A literal that a reviewer had to run Core to falsify is
# exactly what TESTING.md rule 1 warns about, so this one was taken from
# `getdescriptorinfo` on 2026-09-05 and the live round trip lives in
# tests/sparrow/test_export_interop.py.
DESC = "wpkh([73c5da0a/84h/1h/0h]tpubDDRDHYNXyuoRVQwotDQHrV7jFvyUzfihzUFKg6QMT47h8g8ai4CCs1w4mVAWWwkREw2bHUVhEWXWMHyzw79jpDuP8xp5GD4xtLktLUCqb1y/0/*)#rvhyypq0"

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


class Display:
    width, height = 320, 240
    def __init__(self): self.painted = []
    def show(self, image, sensitive=False): self.painted.append(image)


class Buttons:
    """`pressed` returns queued keys then None, as the real poll does."""
    def __init__(self, queue=()): self.queue = list(queue)
    def pressed(self): return self.queue.pop(0) if self.queue else None
    def read(self): return self.queue.pop(0) if self.queue else "a"


class Source:
    """A stand-in camera: a list of decoded payloads, None for a tick with
    nothing in view. Mirrors ImageQrSource's contract exactly.

    This drives the stopping RULES. The bytes are driven elsewhere, by
    tests/sparrow/test_export_interop.py, where a real descriptor and a
    real master xprv out of Core go through the renderer, Sparrow's zxing,
    this classifier and these guards (TESTING.md rules 1 and 8)."""
    last_image = None
    available = True
    def __init__(self, payloads, unavailable=None):
        self.payloads = list(payloads)
        self.unavailable = unavailable
        self.passes = 0
    def strings(self):
        self.passes += 1
        for p in self.payloads:
            yield p


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


def session(source, buttons, clock):
    s = corky_main.Session(Display(), buttons, rpc=None, qr_source=source)
    s.clock = clock
    return s


def main():
    # 1. A key arrives after two blind ticks, and blind ticks are not fatal.
    src = Source([None, None, XPRV])
    got = session(src, Buttons(), Clock())._scan_key_guarded()
    if got == XPRV:
        ok("a key found after two blind ticks is returned intact")
    else:
        bad(f"scan returned {got!r}")

    # 2. A descriptor comes back byte for byte, checksum included. A real
    #    one, from Core, not a plausible-looking literal (rule 1).
    got = session(Source([DESC]), Buttons(), Clock())._scan_key_guarded()
    if got == DESC:
        ok("a Core descriptor survives the scan unchanged, checksum included")
    else:
        bad(f"descriptor came back as {got!r}")

    # 3. Nothing in view: give up after the timeout, and say why.
    clock = Clock()
    src = Source([None] * 4)
    sess = session(src, Buttons(), clock)
    def tick():
        clock.t += 9.0
        return None
    sess.buttons.pressed = tick
    try:
        sess._scan_key_guarded()
        bad("a scan that never decodes did not stop")
    except qrchannel.ScanTimeout as exc:
        ok(f"a scan with nothing in view stops: {exc}")
    except Exception as exc:
        bad(f"the stalled scan raised {type(exc).__name__}: {exc}")

    # 4. A button aborts at any point, and abort is not an error to report.
    for key in ("b", "c"):
        try:
            session(Source([None, None, XPRV]), Buttons([key]),
                    Clock())._scan_key_guarded()
            bad(f"{key!r} did not abort the scan")
        except qrchannel.ScanAborted:
            ok(f"{key!r} aborts the scan")
        except Exception as exc:
            bad(f"{key!r} raised {type(exc).__name__}")

    # 5. A board with no camera says so at once instead of waiting out the
    #    timeout, because the answer will never change (I-8).
    try:
        session(Source([], unavailable="ImportError: no picamera2"),
                Buttons(), Clock())._scan_key_guarded()
        bad("a camera-less board did not say so")
    except RuntimeError as exc:
        if "picamera2" in str(exc):
            ok(f"a camera-less board says why: {str(exc)[:48]}")
        else:
            bad(f"unclear camera-less message: {exc}")

    # 6. The guards still bite: an oversized payload and one with
    #    characters no key can contain (PLAN A-11).
    for name, payload in (("oversized", "x" * (corky_main.MAX_KEY_PAYLOAD + 1)),
                          ("bad characters", "wpkh(\x00\x01\x02)")):
        try:
            session(Source([payload]), Buttons(), Clock())._scan_key_guarded()
            bad(f"a {name} payload was accepted")
        except RuntimeError as exc:
            ok(f"a {name} payload is refused: {str(exc)[:40]}")

    # 7. The viewfinder is painted while the scan waits. Aiming blind took
    #    35s to first read on the board; with the viewfinder it took 8.
    src = Source([None, None, XPRV])
    disp = Display()
    sess = corky_main.Session(disp, Buttons(), rpc=None, qr_source=src)
    sess.clock = Clock()
    sess._scan_key_guarded()
    blank = screens.scanning(320, 240, None, "hold the key QR in view", 0.0)
    if any(f.tobytes() == blank.tobytes() for f in disp.painted):
        ok(f"the viewfinder is painted while waiting ({len(disp.painted)} frames)")
    else:
        bad("the scan never painted a viewfinder")

    # 8. The classifier decides what a scanned code is (ticket 05). Real
    #    shapes, including the BIP21 URI a phone wallet actually shows and
    #    the kinds of stray code a desk produces.
    cases = [
        ("ur:crypto-psbt/1-3/lpadaxcfadbncy", "transaction"),
        (XPRV, "xprv"),
        # The classifier reads the prefix and nothing else, so this checks
        # the prefix list. It is the real key above wearing another
        # network's prefix, not an invented key.
        ("zprv" + XPRV[4:], "xprv"),
        (DESC, "descriptor"),
        ("bc1q635yhaml2afumm27jxsjmqayczf5nf0xmm9zh0", "address"),
        ("bitcoin:bc1q635yhaml2afumm27jxsjmqayczf5nf0xmm9zh0?amount=0.01", "address"),
        ("https://example.com/thing(with)brackets", None),
        ("hello world", None),
        ("", None),
    ]
    wrong = [(t[:34], corky_main._classify_qr(t), want)
             for t, want in cases if corky_main._classify_qr(t) != want]
    if not wrong:
        ok(f"the scan classifies all {len(cases)} shapes correctly")
    else:
        bad(f"classifier disagreed: {wrong}")

    # 9. On the Scan tile a code the scan does not want is counted and
    #    skipped, and the count reaches the screen, so the operator can
    #    tell the camera IS reading (ticket 05: "count it, skip it, keep
    #    scanning"). The explicit "Scan a key" path is deliberately the
    #    other way round: it accepts what it reads and says what is wrong
    #    with it, because there the user is holding a key up on purpose.
    disp = Display()
    src = Source(["hello world", "https://example.com/a(b)c", XPRV])
    sess = corky_main.Session(disp, Buttons(), rpc=None, qr_source=src)
    sess.clock = Clock()
    kind, got = sess._scan_until("hold any QR in view", corky_main._classify_qr)
    counted = [screens.scanning(320, 240, None,
                                f"hold any QR in view ({n} skipped)", 0.0)
               for n in (1, 2)]
    painted = [f.tobytes() for f in disp.painted]
    if (kind, got) == ("xprv", XPRV) and all(c.tobytes() in painted
                                             for c in counted):
        ok("stray codes are counted and skipped, and the count is on screen")
    else:
        bad(f"the scan does not report what it skipped: {kind}, "
            f"{len(painted)} frames")

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
