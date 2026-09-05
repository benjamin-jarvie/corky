"""The QR transfer channel: PSBTs as BC-UR animated QR codes.

This is the format Sparrow, SeedSigner and Foundation devices speak
(ur:crypto-psbt fountain codes). Encoding/decoding of the UR container uses
SeedSigner's vendored BC-UR module (hw/vendor/ur2, BSD-2-Clause-Patent).

Opaque-bytes law (PLAN A-11), with its ONE documented exception: the UR
container itself (bytewords + a single CBOR byte-string header) must be
removed here to get at the payload — that unwrapping is transport framing,
not PSBT parsing, and it is bounded (length cap + charset check first,
errors contained to QrChannelError). The PSBT inside stays opaque; Bitcoin
Core remains the only parser of PSBT bytes.
"""

import base64
import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hw" / "vendor"))
from ur2.ur import UR                       # noqa: E402
from ur2.ur_encoder import UREncoder        # noqa: E402
from ur2.ur_decoder import URDecoder        # noqa: E402
from ur2.cbor_lite import CBOREncoder, CBORDecoder  # noqa: E402
from ur2.bytewords import Bytewords, Bytewords_Style_minimal  # noqa: E402
from ur2.fountain_encoder import Part as FountainEncoderPart  # noqa: E402

# Fragment size tuned for 240-320px screens: SeedSigner's default density.
MAX_FRAGMENT_LEN = 100

# How many times the pure cycle the display carries. 2 means seq_len pure
# fragments followed by seq_len fountain parts, so any single unreadable frame
# has an alternative route. See ticket 09 and tests/m1/outbound_margin.py.
FOUNTAIN_REDUNDANCY = 2
MAX_FRAME_CHARS = 3000  # hostile-QR guard; real frames are a few hundred
_UR_CHARSET = set("abcdefghijklmnopqrstuvwxyz0123456789:-/")


# Ticket 03. Sparrow's Low density tops out near 215 characters and its Normal
# density near 775. A frame past this length is readable only when the code
# fills most of the camera view, so Corky says so rather than letting the user
# watch a percentage that will not move. This ADVISES; it never refuses.
# MAX_FRAME_CHARS above is the separate hostile-input guard, and it refuses.
ADVISORY_FRAME_LEN = 400

# Ticket 05. Give up when the completion percentage has not moved for this
# long. Measured from the last progress, not from the start of the scan: a
# 10-input PSBT at Low density is 23 frames or more, and is slow but healthy.
NO_PROGRESS_TIMEOUT = 20.0


class QrChannelError(Exception):
    pass


class ScanTimeout(QrChannelError):
    """Progress stopped for NO_PROGRESS_TIMEOUT seconds."""


class ScanAborted(QrChannelError):
    """The user pressed the button."""


# What identifies the message a UR part belongs to. Two frames with the same
# SequenceId carry the same PSBT; a different one means the user pointed the
# camera at another transaction (ticket 05).
SequenceId = collections.namedtuple("SequenceId", "seq_len message_len checksum")


def checked_frame(frame):
    """The one gate every frame passes before any container code sees it.

    Length cap, then prefix, then charset. Nothing downstream may run before
    this returns, which is the condition the module docstring puts on the
    opaque-bytes exception (PLAN A-11). Raises QrChannelError, never anything
    else, so one `except QrChannelError` at the call site is a complete guard.
    """
    frame = frame.strip()
    if len(frame) > MAX_FRAME_CHARS:
        raise QrChannelError("QR frame too large, refusing")
    if not frame.lower().startswith("ur:crypto-psbt/"):
        raise QrChannelError("not a crypto-psbt UR frame")
    if not set(frame.lower()) <= _UR_CHARSET:
        raise QrChannelError("frame contains invalid characters")
    return frame


def frame_identity(frame):
    """Which UR sequence a frame belongs to, or None for a single-part UR.

    A multi-part UR part carries seq_len, message_len and checksum. Those three
    identify the message being sent, so a frame from a different PSBT has a
    different triple and ticket 05 can act on it.

    This is the same bounded container unwrapping the module docstring already
    licenses. The PSBT inside stays opaque; nothing here parses it.
    """
    frame = checked_frame(frame)          # raises QrChannelError, never passes
    try:
        _type, components = URDecoder.parse(frame)
        if len(components) != 2:
            return None                   # a single-part UR has no sequence
        cbor = Bytewords.decode(Bytewords_Style_minimal, components[1])
        part = FountainEncoderPart.from_cbor(cbor)
    except Exception as exc:
        raise QrChannelError(f"malformed UR container: {exc}") from None
    return SequenceId(part.seq_len, part.message_len, part.checksum)


def decode_image(image):
    """Every QR payload in one camera image, as strings.

    Lazy import so this module stays importable without pyzbar, matching
    frames_to_images. pyzbar output is untrusted: the caller length-caps and
    charset-checks it before anything else looks at it.
    """
    from pyzbar import pyzbar as _pyzbar
    out = []
    for sym in _pyzbar.decode(image):
        try:
            out.append(sym.data.decode("ascii"))
        except UnicodeDecodeError:
            continue          # a non-ascii QR is not a UR frame
    return out


def psbt_to_frames(psbt_b64: str, max_fragment_len: int = MAX_FRAGMENT_LEN,
                   redundancy: int = FOUNTAIN_REDUNDANCY):
    """Encode an opaque base64 PSBT into UR frames for the display.

    A single-frame result is a static QR; multi-frame results are an animated
    loop.

    The list is `redundancy` times the pure cycle. Parts 1..seq_len are the
    pure fragments; every part after that is a fountain part, an XOR of a
    random subset, and any of them can stand in for a pure part the scanner
    never got.

    That matters because one cycle on its own is fragile (ticket 09). Corky
    renders at exactly 4.0 pixels per module, and about one frame in 125 is
    deterministically unreadable by zxing, the decoder Sparrow uses. Looping a
    pure cycle shows the scanner the identical unreadable image forever, so
    such a transfer never completes. Fountain parts give it another way to the
    same bytes, which is what Sparrow's own UREncoder does when it sends to us.
    """
    raw = base64.b64decode(psbt_b64)
    enc = CBOREncoder()
    enc.encodeBytes(raw)                     # crypto-psbt = CBOR byte string
    encoder = UREncoder(UR("crypto-psbt", enc.get_bytes()),
                        max_fragment_len=max_fragment_len)
    if encoder.is_single_part():
        return [encoder.next_part()]
    parts = encoder.fountain_encoder.seq_len() * max(1, redundancy)
    return [encoder.next_part() for _ in range(parts)]


class FrameAssembler:
    """Feed camera-decoded QR strings; .psbt_b64 appears when complete."""

    def __init__(self):
        self._decoder = URDecoder()
        self.psbt_b64 = None

    def feed(self, frame) -> bool:
        """Returns True once the PSBT is fully assembled.

        `None` means a tick passed with no code in view. It is not an error
        and it is not progress, so it returns False. Callers that poll a
        camera hand it straight through.
        """
        if self.psbt_b64 is not None:
            return True
        if frame is None:
            return False
        frame = checked_frame(frame)
        self._decoder.receive_part(frame)
        if self._decoder.is_complete():
            try:
                ur = self._decoder.result_message()
                if ur.type != "crypto-psbt":
                    raise QrChannelError(f"unexpected UR type {ur.type}")
                dec = CBORDecoder(ur.cbor)
                raw, _ = dec.decodeBytes()
            except QrChannelError:
                raise
            except Exception as exc:  # malformed container must not crash UI
                raise QrChannelError(f"malformed UR container: {exc}") from None
            self.psbt_b64 = base64.b64encode(raw).decode("ascii")
            return True
        return False

    @property
    def progress(self) -> float:
        return self._decoder.estimated_percent_complete()


class PsbtScan:
    """Every ticket 05 stopping rule, drivable one frame at a time.

    Ticket 04 put the assembler on the caller's side of the contract, not
    inside the QR source. This class is that caller-side piece. It is a state
    machine rather than a loop because `state_load` has to interleave QR
    frames with the USB stick check and the button poll, and a blocking loop
    cannot do that.

    Feed it one decoded string per call, or None for "a tick passed and no
    code was in view". A camera must send those Nones, or a still scene would
    never let the no-progress timeout fire.

    `on_event(kind, detail)` reports for the screen. Kinds: "advisory",
    "skipped", "restart", "progress".
    """

    def __init__(self, clock=None, timeout=NO_PROGRESS_TIMEOUT, on_event=None):
        self._clock = clock or time.monotonic
        self._timeout = timeout
        self._say = on_event or (lambda _kind, _detail: None)
        self._assembler = FrameAssembler()
        self._identity = None
        self._advised = False
        self.psbt_b64 = None
        self.progress = 0.0
        self.skipped = 0
        self._last_move = self._clock()

    def feed(self, frame):
        """Returns True once the PSBT is complete. Raises ScanTimeout."""
        if self.psbt_b64 is not None:
            return True
        if frame is not None:
            try:
                self._consider(checked_frame(frame))
            except QrChannelError as exc:
                self.skipped += 1
                self._say("skipped", str(exc))
            if self.psbt_b64 is not None:
                return True
            moved = self._assembler.progress
            if moved > self.progress:
                self.progress = moved
                self._last_move = self._clock()
                self._say("progress", moved)
        if self._clock() - self._last_move > self._timeout:
            raise ScanTimeout(self._why("no progress for "
                                        f"{self._timeout:.0f}s"))
        return False

    def _consider(self, frame):
        """One validated frame. Restart on a new sequence, else assemble."""
        if not self._advised and len(frame) > ADVISORY_FRAME_LEN:
            self._advised = True
            self._say("advisory", len(frame))

        seen = frame_identity(frame)
        if seen is not None and self._identity is not None and seen != self._identity:
            self._say("restart", seen)
            self._assembler = FrameAssembler()
            self._identity = None
            self.progress = 0.0
            self._last_move = self._clock()
            # A fresh transaction earns a fresh advisory: the new coordinator
            # session may be at a different density from the last one.
            self._advised = len(frame) > ADVISORY_FRAME_LEN
            if self._advised:
                self._say("advisory", len(frame))

        if self._assembler.feed(frame):
            self.psbt_b64 = self._assembler.psbt_b64
        elif self._identity is None and seen is not None:
            self._identity = seen

    def _why(self, reason):
        tail = f", {self.skipped} frames skipped" if self.skipped else ""
        return f"{reason} at {self.progress:.0%}{tail}"


def frames_to_images(frames, box_size=4, border=2, panel=None):
    """Render UR frames as PIL images for the display (lazy import so this
    module stays importable without Pillow/qrcode, e.g. in logic tests).

    panel=(w, h) LOWERS box_size when the frames would not fit that panel.
    Frame length drives the QR version, so one tuning change to
    MAX_FRAGMENT_LEN can push a frame past the panel, where fit_to_panel used
    to crop it into a code no scanner can read (I-1). box_size stays the
    ceiling, so frames that already fit render exactly as before; only frames
    that would overflow get smaller modules.

    One box_size applies to the WHOLE set, taken from the biggest frame in
    it. Frames differ in version, so a per-frame size would change the image
    size during the animation while a scanner is still reading it.
    """
    import qrcode
    codes = []
    for f in frames:
        qr = qrcode.QRCode(box_size=box_size, border=border,
                           error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(f.upper())   # alphanumeric mode: denser QR for UR strings
        qr.make(fit=True)
        codes.append(qr)
    if panel:
        span = max(qr.modules_count + 2 * border for qr in codes)
        box_size = min(box_size, min(panel) // span)
        if box_size < 1:
            raise QrChannelError(
                f"a {span}-module QR does not fit a {min(panel)}px panel at "
                "one pixel per module; lower MAX_FRAGMENT_LEN")
        for qr in codes:
            qr.box_size = box_size
    return [qr.make_image(fill_color="black",
                          back_color="white").convert("RGB") for qr in codes]


def text_to_image(text, panel=None, box_size=8, border=2):
    """One static QR of arbitrary text, for the public key export.

    NOT `frames_to_images`: that uppercases its input to reach QR
    alphanumeric mode, which is right for UR frames (they are lowercase by
    definition) and destroys a descriptor, where `xpub` and the checksum
    are case-sensitive. This encodes the bytes as given.

    `panel` lowers box_size so the code fits the screen, as the frame
    renderer does.
    """
    import qrcode
    qr = qrcode.QRCode(box_size=box_size, border=border,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    if panel:
        span = qr.modules_count + 2 * border
        box_size = max(1, min(box_size, min(panel) // span))
        qr = qrcode.QRCode(box_size=box_size, border=border,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(text)
        qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def fit_to_panel(img, w, h):
    """Scale a square QR to the panel by an INTEGER factor and letterbox it.

    Resizing a square QR to a 4:3 panel gives non-square modules and
    interpolated edges, so the coordinator's scanner has to recover a code
    that is no longer a code. An integer factor with NEAREST keeps every
    module square and hard-edged; the surround is white so the quiet zone
    survives.
    """
    from PIL import Image
    if img.width > w or img.height > h:
        # Cropping a QR silently destroys it: the panel still shows something
        # QR-shaped and no scanner will ever read it. Refuse instead, and let
        # frames_to_images(panel=...) size the modules so this cannot arise.
        raise QrChannelError(
            f"a {img.width}x{img.height} QR does not fit a {w}x{h} panel")
    factor = min(w // img.width, h // img.height)
    scaled = img.resize((img.width * factor, img.height * factor),
                        Image.Resampling.NEAREST)
    panel = Image.new("RGB", (w, h), "white")
    panel.paste(scaled, ((w - scaled.width) // 2, (h - scaled.height) // 2))
    return panel
