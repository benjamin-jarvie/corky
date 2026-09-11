"""Where QR frames come from: a camera on the device, files in dev mode.

One seam, and the only one in Core Signer where the dev harness stands in for
hardware. `main.py` never learns which it has: it asks a source whether
it is `available`, then reads strings from it. That substitution is what
makes every screen reachable without a board, and it is why these three
classes are worth their own file rather than sitting among the fifty-two
methods of `Session` (extracted 2026-09-08, at Ben's call, after
measuring that the four other candidate seams in main.py were not seams
at all: they all reached into the same shared session state).

The interface is four things:

    available            is there a source at all
    images()             raw frames, for the viewfinder
    strings()            decoded QR payloads, one at a time
    scan_psbt_frames()   the same, restricted to UR frames

`ImageQrSource` holds the decode loop; the two concrete sources supply
frames and nothing else. Every stopping rule lives in `qrchannel`, not
here: a source yields strings and never decides when to stop (ticket 04).

LAYER 2, not layer 3. `strings()` yields whatever was decoded, and on the
Scan-a-key flow that is a private key; `DevQrSource` reads one out of
`--qr-key`. So this file SEES secrets and computes nothing on them, which
is layer 2's definition. `qrchannel.py` stays layer 3 because it only
ever handles crypto-psbt frames. tests/test_readme_claims.py counts it
in the layer 2 total, and tests/test_integrity.py holds it to the same
import allowlist as every other shipped module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qrchannel


class ImageQrSource:
    """Turns a stream of images into decoded QR strings.

    Ticket 04 fixed the contract: a source yields strings and nothing else.
    Every stopping rule lives in qrchannel.scan_psbt, so this class holds no
    policy at all. A tick with no code in view yields None, which is what lets
    the caller's no-progress timeout fire on a still scene.

    Subclasses supply images. That is the only part that needs hardware, which
    is why CameraQrSource below is four lines.
    """

    #: The most recent frame, for a viewfinder. None until one arrives.
    last_image = None

    #: A camera is always a channel worth offering for a PSBT.
    available = True

    def images(self):
        raise NotImplementedError

    def strings(self):
        """Decoded QR text, one per tick, None when nothing is in view.

        Ticket 04's contract: a source yields strings and nothing else, and
        every stopping rule lives in the caller. A PSBT and a key read the
        same way, so they share this one generator.
        """
        for image in self.images():
            # The image is parked here instead of riding the stream, so a
            # caller that wants a viewfinder can read it without the
            # stream carrying two types.
            self.last_image = image
            if image is None:
                yield None
                continue
            found = qrchannel.decode_image(image)
            if not found:
                yield None
            for payload in found:
                yield payload

    def scan_psbt_frames(self):
        return self.strings()


class CameraQrSource(ImageQrSource):
    """Device QR source: picamera2 into pyzbar.

    Measured on a Zero 2 W with an ov5647. On an idle board, 2026-09-04:
    512x384 at 30fps for both RGB888 and YUV420. On the board as it
    SHIPS, with bitcoind running beside it, 2026-09-05: 10.6fps over 30
    frames. That is still above hw/HARDWARE.md's 10fps target, and it is
    the number that matters, because the idle figure is not a condition
    the device is ever in while scanning.

    YUV420, because zbar works in greyscale. capture_array returns
    (height * 3 // 2, width) for that format, and the first `height` rows
    are the Y plane, which is the greyscale image already. Handing zbar an
    RGB frame only pays for a conversion it would do itself.
    """

    SIZE = (512, 384)          # hw/HARDWARE.md:75
    BUFFERS = 4

    def __init__(self):
        # Why there is no camera, when there is no camera. Read by the
        # caller; nothing here decides what to do about it.
        self.unavailable = None

    def images(self):
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            cam.configure(cam.create_video_configuration(
                main={"size": self.SIZE, "format": "YUV420"},
                buffer_count=self.BUFFERS))
            cam.start()
        except Exception as exc:
            # A board with no camera must fall through to the USB stick, not
            # take the whole app down (I-8). The caller gets an empty stream
            # and its no-progress timeout does the rest.
            self.unavailable = f"{type(exc).__name__}: {exc}"
            return
        width, height = self.SIZE
        try:
            while True:
                yield cam.capture_array("main")[:height, :width]
        finally:
            cam.stop()
            cam.close()


class DevQrSource:
    """Dev stand-in for the camera: returns file contents as scan payloads."""

    def __init__(self, key_path=None, psbt_path=None):
        self.key_path = key_path
        self.psbt_path = psbt_path
        self._shown = 0

    @property
    def available(self):
        """No PSBT file, no PSBT channel. state_load offers only channels
        that exist."""
        return bool(self.psbt_path)

    def strings(self):
        """The dev stand-in for a camera pointed at a static code: the key
        file if there is one, else the PSBT frames.

        One source at a time. A camera sees one thing, and yielding the key
        file AND the frames from here put the key into the PSBT assembler
        as a junk frame, where the tick that skipped it also ate a button
        press (found 2026-09-05).

        The key file may hold SEVERAL codes, one per line, for a session
        that scans more than one thing: an xprv, then an address to check
        against it. Each read moves on to the next line and the last line
        repeats, which is a person holding up one code and then another.
        A one-line file therefore behaves exactly as it always did.
        """
        if self.key_path:
            codes = Path(self.key_path).read_text().split("\n")
            codes = [c.strip() for c in codes if c.strip()]
            code = codes[min(self._shown, len(codes) - 1)]
            self._shown += 1        # BEFORE the yield: a caller that
            yield code              # accepts the first code never
            return                  # resumes this generator.
        if self.psbt_path:
            yield from Path(self.psbt_path).read_text().split()
            return
        raise RuntimeError("no --qr-key or --qr-psbt in this dev session")

    def scan_psbt_frames(self):
        """UR frames only, one per line in the dev file. Never the key."""
        if not self.psbt_path:
            return iter(())
        return iter(Path(self.psbt_path).read_text().split())
