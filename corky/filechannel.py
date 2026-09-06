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
    """All candidate PSBT files on the drive, ignoring already-signed ones.

    **This is safe because of a decision made somewhere else.** `is_file()`
    follows symlinks, and every name here comes off a stick somebody else
    wrote, so on a filesystem with symlinks a file called `x.psbt` could
    point at anything this process can read. It cannot, because
    `image/corky-usb@.service` mounts removable media `-t vfat,exfat` and
    neither format has symlinks at all.

    That coupling had lived in two files that did not mention each other
    until the A1 audit, 2026-09-06. `tests/test_channels.py` now fails if
    the mount unit ever admits a filesystem that does, which is the point
    at which this function would need to stop trusting a name.
    """
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
    # Bound the READ, not an earlier stat. The stick is shared with the
    # coordinator, which is the whole reason wait_stable exists, so a file
    # can grow between being measured and being read. It did: a 1KB file
    # that grew during the gap was read at 6MB against this 4MB cap
    # (devil's advocate on audit A1, 2026-09-06). Reading one byte past
    # the cap and refusing on what actually arrived closes the window,
    # because there is no longer a window.
    with path.open("rb") as fh:
        raw = fh.read(MAX_PSBT_BYTES + 1)
    if not raw or len(raw) > MAX_PSBT_BYTES:
        # An empty file's size is known exactly and saying it is more use
        # to the reader than a word. An oversized one's is not: only
        # MAX_PSBT_BYTES + 1 bytes were read, on purpose, so "over" is the
        # honest word for it.
        got = "0 bytes" if not raw else f"over {MAX_PSBT_BYTES} bytes"
        raise FileChannelError(f"{path.name}: {got}, refusing")
    try:
        # Text export: strip ALL whitespace first — Sparrow/mail-style
        # exports wrap base64 at 64/76 columns and a stray newline must not
        # shunt a valid text PSBT into the binary branch (double-encoding).
        text = "".join(raw.decode("ascii").split())
        base64.b64decode(text, validate=True)
        return text
    except (UnicodeDecodeError, binascii.Error, ValueError):
        return base64.b64encode(raw).decode("ascii")


def wait_stable(path: Path, checks=3, interval=0.2) -> bool:
    """True once the file size stops changing (guards against reading a
    file mid-copy from the coordinator, because the stick is shared).

    A file that stays at zero bytes is stable, and read_psbt refuses it by
    size with a message that names it. Requiring size > 0 here instead made
    an empty file invisible: the device waited on "insert the stick…" for
    ever with the file already in front of it (found 2026-09-05).
    """
    import time
    last = -1
    stable = 0
    for _ in range(50):
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size == last:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
        last = size
        time.sleep(interval)
    return False


def write_signed(source: Path, signed_psbt_b64: str) -> Path:
    """Write the signed PSBT next to the source, binary format (Sparrow
    and Core both load it). Returns the path written.

    The bytes are forced to the medium before this returns. The user's next
    act after the result screen is to pull the stick, and a signature still
    sitting in the page cache is a signature that never left the device.
    """
    import os
    out = source.with_name(source.name[: -len(".psbt")] + SIGNED_SUFFIX)
    raw = base64.b64decode(signed_psbt_b64)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        # os.write is ONE write(2) and write(2) is allowed to be short. A
        # stick with 100 bytes left takes 100 bytes, returns 100, and
        # raises nothing; the next call is the one that reports ENOSPC.
        # The old code ignored the count, so a full or failing stick left
        # a truncated signature behind a screen that said the file was
        # written (audit A3, 2026-09-06). A half-written PSBT is not a
        # PSBT, and the user has already pulled the stick by the time
        # anyone finds out.
        done = 0
        while done < len(raw):
            n = os.write(fd, raw[done:])
            if n <= 0:
                break
            done += n
        if done != len(raw):
            raise FileChannelError(
                f"{out.name}: wrote {done} of {len(raw)} bytes, "
                "the medium is full or failing")
        os.fsync(fd)
    finally:
        os.close(fd)
    # And the directory entry itself, so the file is findable after a pull.
    dfd = os.open(out.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    except OSError:
        pass            # not every filesystem allows this; the data is down
    finally:
        os.close(dfd)
    return out
