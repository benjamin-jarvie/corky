"""The file transfer channel: PSBTs on a removable drive (USB stick for now;
the boot microSD itself once the M3 RAM-resident image lands).

Flow, Coldcard-style:
  coordinator writes  <name>.psbt        -> stick -> Corky
  Corky writes        <name>-signed.psbt -> stick -> coordinator

Obeys the opaque-bytes law (PLAN.md A-11): this module never parses a PSBT.
It only detects the FILE ENCODING (binary vs base64 text, both of which
Sparrow and Core emit) and hands an opaque base64 string to Bitcoin Core,
which is the only parser. A size cap rejects absurd files before anything
touches them.
"""

import base64
import binascii
from pathlib import Path

MAX_PSBT_BYTES = 4 * 1024 * 1024  # generous; a 250-input PSBT is ~40KB
SIGNED_SUFFIX = "-signed.psbt"


class FileChannelError(Exception):
    pass


def find_unsigned(mount: Path):
    """All candidate PSBT files on the drive, ignoring already-signed ones."""
    return sorted(
        p for p in mount.glob("*.psbt")
        if not p.name.endswith(SIGNED_SUFFIX) and p.is_file()
    )


def read_psbt(path: Path) -> str:
    """Return the PSBT as an opaque base64 string. No parsing.

    Encoding detection only: a binary PSBT starts with bytes that are not
    clean printable ASCII; a text export is base64. Either way the payload
    is not inspected here.
    """
    size = path.stat().st_size
    if size == 0 or size > MAX_PSBT_BYTES:
        raise FileChannelError(f"{path.name}: {size} bytes, refusing")
    raw = path.read_bytes()
    try:
        text = raw.decode("ascii").strip()
        # Round-trip check: is it valid base64 text?
        base64.b64decode(text, validate=True)
        return text
    except (UnicodeDecodeError, binascii.Error, ValueError):
        return base64.b64encode(raw).decode("ascii")


def write_signed(source: Path, signed_psbt_b64: str) -> Path:
    """Write the signed PSBT next to the source, binary format (Sparrow
    and Core both load it). Returns the path written."""
    out = source.with_name(source.name[: -len(".psbt")] + SIGNED_SUFFIX)
    out.write_bytes(base64.b64decode(signed_psbt_b64))
    return out
