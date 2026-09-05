"""A camera stand-in that satisfies the ticket 04 contract.

Ticket 04: a QR source yields decoded strings and nothing else. The caller owns
`FrameAssembler`. So a test double only has to yield strings, and a scripted
list of them is enough to drive every rule ticket 05 will decide.

Two sources here. `ReplaySource` yields strings straight from a script, for
logic tests. `ImageReplaySource` yields strings decoded from PNG files with the
same pyzbar the device runs, so the decode path itself is exercised without a
camera. Both satisfy the same contract as `DevQrSource` and the future
`CameraQrSource`.

Run the self-test:  tests/m1/run tests/m1/replay_source.py
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corky"))
import qrchannel  # noqa: E402


class ReplaySource:
    """Yields a scripted list of decoded QR payloads.

    repeat_each   duplicates every frame, as zbar does when the camera holds
                  still over one code for several tenths of a second
    loop          re-yields the whole script forever, as an animated coordinator
                  screen does; use with a caller that knows how to stop
    """

    def __init__(self, frames, repeat_each=1, loop=False):
        self.frames = list(frames)
        self.repeat_each = repeat_each
        self.loop = loop
        self.yielded = 0

    def scan_key(self):
        raise RuntimeError("ReplaySource carries PSBT frames only")

    def scan_psbt_frames(self):
        cycles = itertools.repeat(self.frames) if self.loop else [self.frames]
        for cycle in cycles:
            for f in cycle:
                for _ in range(self.repeat_each):
                    self.yielded += 1
                    yield f


class ImageReplaySource(ReplaySource):
    """Same contract, but the strings come out of real PNG files via pyzbar.

    Undecodable images are skipped, which is what a camera does with a blurred
    or half-captured frame. A caller cannot tell this apart from a camera that
    saw nothing, and that is the point.
    """

    def __init__(self, paths, repeat_each=1, loop=False):
        from PIL import Image
        import qrchannel
        frames = []
        self.undecodable = 0
        for path in paths:
            # the device's own decode path, so this exercises it rather than
            # calling pyzbar a second, slightly different way
            found = qrchannel.decode_image(Image.open(str(path)))
            if found:
                frames.extend(found)
            else:
                self.undecodable += 1
        super().__init__(frames, repeat_each=repeat_each, loop=loop)


# ---- scripted awkward cases, for ticket 05 and the ticket 08 tests ----------

GARBAGE = "not a qr code at all"
FOREIGN_UR = "ur:crypto-account/1-1/lpadaxcsencyhkrpnddshmgtwtiaaeaeae"
OVERSIZE = "ur:crypto-psbt/1-1/" + "a" * 4000        # over MAX_FRAME_CHARS


def out_of_order(frames):
    """Fountain parts arrive in whatever order the camera catches them."""
    return frames[::2] + frames[1::2]


def with_foreign(frames, at=1):
    """A different UR type appears mid-scan."""
    return frames[:at] + [FOREIGN_UR] + frames[at:]


def with_garbage(frames, at=1):
    """A shop receipt or a wifi QR wanders into view."""
    return frames[:at] + [GARBAGE] + frames[at:]



def _selftest():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corky"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hw" / "vendor"))
    import qrchannel

    psbt = "cHNidP8BAHEC" + "A" * 1400
    frames = qrchannel.psbt_to_frames(psbt)
    print(f"script: {len(frames)} UR frames from a {len(psbt)}-char PSBT")

    def assemble(src):
        asm = qrchannel.FrameAssembler()
        errors = 0
        for f in src.scan_psbt_frames():
            try:
                if asm.feed(f):
                    return asm.psbt_b64, errors, src.yielded
            except qrchannel.QrChannelError:
                errors += 1
        return asm.psbt_b64, errors, src.yielded

    checks = []
    got, err, n = assemble(ReplaySource(frames))
    checks.append(("in order", got == psbt and err == 0, f"{n} frames"))

    got, err, n = assemble(ReplaySource(frames, repeat_each=4))
    checks.append(("duplicates, as zbar emits them", got == psbt and err == 0,
                   f"{n} frames for {len(frames)} parts"))

    got, err, n = assemble(ReplaySource(out_of_order(frames)))
    checks.append(("out of order", got == psbt and err == 0, f"{n} frames"))

    got, err, n = assemble(ReplaySource(with_garbage(frames)))
    checks.append(("garbage QR mid-scan", got == psbt and err == 1,
                   f"{err} error raised, scan still completed"))

    got, err, n = assemble(ReplaySource(with_foreign(frames)))
    checks.append(("foreign UR type mid-scan", got == psbt and err == 1,
                   f"{err} error raised, scan still completed"))

    got, err, n = assemble(ReplaySource([OVERSIZE] + frames))
    checks.append(("oversize frame refused", got == psbt and err == 1,
                   "MAX_FRAME_CHARS held, scan still completed"))

    # Dropping a whole pure part used to strand the transfer. Since ticket 09
    # the frame list carries fountain parts past the pure cycle, so the mixed
    # parts reconstruct what was lost. This is the property that keeps a
    # transfer alive when zxing cannot read one of Corky's frames.
    got, err, n = assemble(ReplaySource(frames[1:]))
    checks.append(("missing pure part recovers from fountain parts",
                   got == psbt, "ticket 09"))

    # With no fountain parts at all there is nothing to recover from, which is
    # what the old one-cycle output amounted to.
    pure_only = [f for f in frames
                 if int(f.split("/")[1].split("-")[0]) <= len(frames) // 2]
    got, err, n = assemble(ReplaySource(pure_only[1:]))
    checks.append(("pure cycle alone cannot recover a lost part", got is None,
                   "why ticket 09 changed psbt_to_frames"))

    # the image path, through real pyzbar
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="replay-"))
    images = qrchannel.frames_to_images(frames, panel=(320, 240))
    paths = []
    for i, img in enumerate(images):
        q = tmp / f"{i:03d}.png"
        qrchannel.fit_to_panel(img, 320, 240).save(q)
        paths.append(q)
    src = ImageReplaySource(paths)
    got, err, n = assemble(src)
    checks.append(("real PNGs through pyzbar", got == psbt and err == 0,
                   f"{len(paths)} images, {src.undecodable} undecodable"))

    ok = sum(1 for _, o, _ in checks if o)
    for name, o, note in checks:
        print(("ok   " if o else "FAIL ") + f"{name:34} {note}")
    print(f"\nPASS {ok}   FAIL {len(checks) - ok}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(_selftest())


def scan_psbt(source, clock=None, timeout=qrchannel.NO_PROGRESS_TIMEOUT,
              on_event=None, abort=None):
    """Drive a QR source to completion and return the base64 PSBT.

    A test-side loop over PsbtScan. It lived in corky/qrchannel.py until
    2026-09-05, when a dead-code pass found the device never calls it:
    state_load drives PsbtScan itself, because it must also watch the
    buttons and paint the viewfinder. Shipped code that exists only for a
    test is weight the signer carries for nothing, so it moved here.
    """
    scan = qrchannel.PsbtScan(clock=clock, timeout=timeout, on_event=on_event)
    for frame in source.scan_psbt_frames():
        if abort is not None and abort():
            raise qrchannel.ScanAborted("scan cancelled")
        if scan.feed(frame):
            return scan.psbt_b64
    raise qrchannel.ScanTimeout(scan._why("frames ran out"))
