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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hw" / "vendor"))
from ur2.ur import UR                       # noqa: E402
from ur2.ur_encoder import UREncoder        # noqa: E402
from ur2.ur_decoder import URDecoder        # noqa: E402
from ur2.cbor_lite import CBOREncoder, CBORDecoder  # noqa: E402

# Fragment size tuned for 240-320px screens: SeedSigner's default density.
MAX_FRAGMENT_LEN = 100
MAX_FRAME_CHARS = 3000  # hostile-QR guard; real frames are a few hundred
_UR_CHARSET = set("abcdefghijklmnopqrstuvwxyz0123456789:-/")


class QrChannelError(Exception):
    pass


def psbt_to_frames(psbt_b64: str, max_fragment_len: int = MAX_FRAGMENT_LEN):
    """Encode an opaque base64 PSBT into one full cycle of UR frames.

    A single-frame result is a static QR; multi-frame results are shown as
    an animated loop. The fountain encoder can generate unlimited parts;
    one seq_len cycle is enough for a continuous loop display.
    """
    raw = base64.b64decode(psbt_b64)
    enc = CBOREncoder()
    enc.encodeBytes(raw)                     # crypto-psbt = CBOR byte string
    encoder = UREncoder(UR("crypto-psbt", enc.get_bytes()),
                        max_fragment_len=max_fragment_len)
    return [encoder.next_part() for _ in range(encoder.fountain_encoder.seq_len())]


class FrameAssembler:
    """Feed camera-decoded QR strings; .psbt_b64 appears when complete."""

    def __init__(self):
        self._decoder = URDecoder()
        self.psbt_b64 = None

    def feed(self, frame: str) -> bool:
        """Returns True once the PSBT is fully assembled."""
        if self.psbt_b64 is not None:
            return True
        frame = frame.strip()
        if len(frame) > MAX_FRAME_CHARS:
            raise QrChannelError("QR frame too large, refusing")
        if not frame.lower().startswith("ur:crypto-psbt/"):
            raise QrChannelError("not a crypto-psbt UR frame")
        if not set(frame.lower()) <= _UR_CHARSET:
            raise QrChannelError("frame contains invalid characters")
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


def frames_to_images(frames, box_size=4, border=2):
    """Render UR frames as PIL images for the display (lazy import so this
    module stays importable without Pillow/qrcode, e.g. in logic tests)."""
    import qrcode
    images = []
    for f in frames:
        qr = qrcode.QRCode(box_size=box_size, border=border,
                           error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(f.upper())   # alphanumeric mode: denser QR for UR strings
        qr.make(fit=True)
        images.append(qr.make_image(fill_color="black",
                                    back_color="white").convert("RGB"))
    return images


def fit_to_panel(img, w, h):
    """Scale a square QR to the panel by an INTEGER factor and letterbox it.

    Resizing a square QR to a 4:3 panel gives non-square modules and
    interpolated edges, so the coordinator's scanner has to recover a code
    that is no longer a code. An integer factor with NEAREST keeps every
    module square and hard-edged; the surround is white so the quiet zone
    survives.
    """
    from PIL import Image
    factor = max(1, min(w // img.width, h // img.height))
    scaled = img.resize((img.width * factor, img.height * factor),
                        Image.NEAREST)
    panel = Image.new("RGB", (w, h), "white")
    panel.paste(scaled, ((w - scaled.width) // 2, (h - scaled.height) // 2))
    return panel
