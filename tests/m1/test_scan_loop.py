"""Ticket 08: the scan loop against the ticket 06 replay harness.

Every rule ticket 05 decided, exercised with no camera. The clock is injected,
so a 20-second timeout costs nothing to test.

Run: tests/m1/run tests/m1/test_scan_loop.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qrchannel  # noqa: E402
from replay_source import (ReplaySource, ImageReplaySource, scan_psbt,  # noqa: E402
                           OVERSIZE, out_of_order, with_foreign, with_garbage)

R = []


def check(name, ok, note=""):
    R.append((name, ok, note))
    print(("ok   " if ok else "FAIL ") + f"{name:44} {note}")


class Clock:
    """A hand-cranked monotonic clock."""
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Ticking(ReplaySource):
    """Yields None between frames, as a camera does when nothing is in view,
    and advances the clock on every tick."""
    def __init__(self, frames, clock, tick=1.0, idle_after=0):
        super().__init__(frames)
        self.clock, self.tick, self.idle_after = clock, tick, idle_after

    def scan_psbt_frames(self):
        for f in self.frames:
            self.clock.advance(self.tick)
            yield f
        for _ in range(self.idle_after):
            self.clock.advance(self.tick)
            yield None


def events():
    log = []
    return log, lambda kind, detail: log.append((kind, detail))


def main():
    PSBT_A = "cHNidP8BAHEC" + "A" * 1400
    PSBT_B = "cHNidP8BAHEC" + "B" * 1600
    fa = qrchannel.psbt_to_frames(PSBT_A)
    fb = qrchannel.psbt_to_frames(PSBT_B)
    print(f"PSBT A -> {len(fa)} frames, PSBT B -> {len(fb)} frames\n")

    # --- the happy path ---
    got = scan_psbt(ReplaySource(fa))
    check("clean scan completes", got == PSBT_A, f"{len(fa)} frames")

    got = scan_psbt(ReplaySource(fa, repeat_each=5))
    check("duplicate frames are harmless", got == PSBT_A, "5x each, as zbar emits")

    got = scan_psbt(ReplaySource(out_of_order(fa)))
    check("out of order completes", got == PSBT_A)

    # --- ticket 05: bad frames are skipped, never fatal ---
    log, on_event = events()
    got = scan_psbt(ReplaySource(with_garbage(fa)), on_event=on_event)
    skips = [d for k, d in log if k == "skipped"]
    check("garbage QR is skipped, not fatal", got == PSBT_A and len(skips) == 1,
          f"1 skip: {skips[0][:34] if skips else 'none'}")

    log, on_event = events()
    got = scan_psbt(ReplaySource(with_foreign(fa)), on_event=on_event)
    check("foreign UR type is skipped, not fatal",
          got == PSBT_A and sum(1 for k, _ in log if k == "skipped") == 1)

    log, on_event = events()
    got = scan_psbt(ReplaySource([OVERSIZE] + fa), on_event=on_event)
    check("oversize frame is skipped, not fatal",
          got == PSBT_A and sum(1 for k, _ in log if k == "skipped") == 1,
          "MAX_FRAME_CHARS refuses, scan survives")

    # --- ticket 05: no-progress timeout ---
    clock = Clock()
    try:
        scan_psbt(Ticking(fa[:2], clock, tick=1.0, idle_after=40),
                            clock=clock, timeout=20.0)
        check("stalled scan times out", False, "no exception raised")
    except qrchannel.ScanTimeout as e:
        check("stalled scan times out", True, str(e)[:44])

    clock = Clock()
    got = scan_psbt(Ticking(fa, clock, tick=15.0), clock=clock, timeout=20.0)
    check("slow but healthy scan is not killed", got == PSBT_A,
          f"15s between frames, {len(fa)} frames, well past 20s total")

    # --- ticket 05: a second PSBT restarts the scan ---
    log, on_event = events()
    got = scan_psbt(ReplaySource(fa[:3] + fb), on_event=on_event)
    restarts = [d for k, d in log if k == "restart"]
    check("second PSBT restarts the scan", got == PSBT_B and len(restarts) == 1,
          "switched after 3 frames of A, got B")

    # --- ticket 05: abort ---
    box = {"n": 0}
    def pressed():
        box["n"] += 1
        return box["n"] > 3
    try:
        scan_psbt(ReplaySource(fa), abort=pressed)
        check("button aborts the scan", False, "no exception raised")
    except qrchannel.ScanAborted:
        check("button aborts the scan", True, "raised after 3 frames")

    # --- ticket 03: the density advisory ---
    log, on_event = events()
    long_frames = ["ur:crypto-psbt/1-2/" + "a" * 500] + fa
    scan_psbt(ReplaySource(long_frames), on_event=on_event)
    advis = [d for k, d in log if k == "advisory"]
    check("long frames raise the density advisory", len(advis) == 1,
          f"once, at {advis[0]} chars" if advis else "never fired")

    log, on_event = events()
    scan_psbt(ReplaySource(fa), on_event=on_event)
    check("short frames raise no advisory",
          not any(k == "advisory" for k, _ in log),
          f"Corky's own frames are {max(len(f) for f in fa)} chars")

    # --- the real decode path, images through pyzbar ---
    tmp = Path(tempfile.mkdtemp(prefix="scanloop-"))
    paths = []
    for i, img in enumerate(qrchannel.frames_to_images(fa, panel=(320, 240))):
        q = tmp / f"{i:03d}.png"
        qrchannel.fit_to_panel(img, 320, 240).save(q)
        paths.append(q)
    src = ImageReplaySource(paths)
    got = scan_psbt(src)
    check("real PNGs through pyzbar complete", got == PSBT_A,
          f"{len(paths)} images, {src.undecodable} undecodable")

    # --- the production source class, not just the replay double -----------
    # ImageQrSource is what CameraQrSource inherits; only images() needs the
    # board. Drive the real class over the same PNGs, including the None it
    # must emit for a tick with nothing in view.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corky"))
    from main import ImageQrSource, CameraQrSource
    from PIL import Image

    class FileImages(ImageQrSource):
        def __init__(self, paths, blanks=2):
            self.paths, self.blanks = paths, blanks

        def images(self):
            yield Image.new("L", (64, 64), 255)      # a blank view, no code
            for p in self.paths:
                yield Image.open(str(p))
            for _ in range(self.blanks):
                yield None                            # ticks with nothing seen

    got = scan_psbt(FileImages(paths))
    check("ImageQrSource drives a real scan", got == PSBT_A,
          f"{len(paths)} PNGs plus blank views and idle ticks")

    yielded = list(FileImages(paths[:2], blanks=1).scan_psbt_frames())
    check("blank views and idle ticks yield None",
          yielded.count(None) == 2 and len([y for y in yielded if y]) == 2,
          f"{yielded.count(None)} Nones, {len([y for y in yielded if y])} frames")

    check("CameraQrSource degrades, does not raise",
          list(CameraQrSource().scan_psbt_frames()) == [],
          "yields nothing until capture lands, as before M1")

    # Ticket 09 replaced scan_key with the strings() contract: a source
    # yields decoded text and the caller owns every stopping rule. On a
    # machine with no camera the stream is empty and the reason is parked
    # on the source, which is what lets the caller say why at once (I-8).
    src = CameraQrSource()
    check("CameraQrSource.strings() yields nothing without a camera",
          list(src.strings()) == [], "empty stream")
    check("and says why, for the caller to show",
          bool(src.unavailable), str(src.unavailable)[:60])

    # --- ticket 09: an unreadable frame must not strand a transfer ---------
    fountain = qrchannel.psbt_to_frames(PSBT_A)
    seq_len = int(fountain[0].split("/")[1].split("-")[1])
    check("output carries fountain parts past the pure cycle",
          len(fountain) == seq_len * qrchannel.FOUNTAIN_REDUNDANCY,
          f"{len(fountain)} frames for a {seq_len}-part message")

    recovered = 0
    for drop in range(1, seq_len + 1):
        survivors = [f for f in fountain
                     if not f.split("/")[1].startswith(f"{drop}-")]
        if scan_psbt(ReplaySource(survivors)) == PSBT_A:
            recovered += 1
    check("any single unreadable frame is recoverable",
          recovered == seq_len,
          f"{recovered}/{seq_len} pure parts individually droppable")

    ok = sum(1 for _, o, _ in R if o)
    print(f"\nPASS {ok}   FAIL {len(R) - ok}")
    return 0 if ok == len(R) else 1


if __name__ == "__main__":
    sys.exit(main())
