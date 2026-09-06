# A3 What a hostile QR, file or card can make the device do

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A1, which says what the channels do before this asks what breaks them.

## Question

Everything reaching this device comes from somewhere else: a QR held up
to the camera, a file on a stick, a card in the slot. The stated defence
is PLAN A-11, that Corky treats key material as opaque bytes and only
Bitcoin Core parses.

That is a claim about the payload. It says nothing about the envelope,
and the envelope is parsed by us: UR frames, fountain parts, filenames,
file sizes, the mount itself.

For each channel, answer with a test rather than a paragraph:

- what a malformed frame, a huge frame, a truncated file, an empty file,
  a filename with a path in it, and a filesystem that lies about its size
  each make the device do;
- whether any of them can make it write outside its channel, hang with no
  way out, or show something misleading;
- `tests/test_adversarial.py` has 28 checks already. Which of the above
  does it not cover?

The mount is new since the last adversarial pass and has never been fed
anything hostile.

---

## Answer (2026-09-06)

The payload was already well defended. **The envelope had one hole, and
it was on the write.**

`tests/test_adversarial.py` gains a seventh attack,
`attack_hostile_envelope`, which needs no bitcoind and answers the
ticket's list with eleven checks rather than a paragraph. The ticket said
that file held 28 checks; it holds 21, now 32.

### The finding: a full stick left a truncated signature and said it wrote it

`os.write` is one `write(2)`, and `write(2)` is **allowed to be short**. A
stick with 100 bytes left takes 100 bytes, returns 100, and raises
nothing; the call that reports `ENOSPC` is the *next* one. `write_signed`
ignored the return value:

```python
os.write(fd, raw)      # 4,005 bytes asked, 100 written, no error
os.fsync(fd)
```

Measured, not reasoned: faking a short write put **100 of 4,005 bytes** on
the medium and `write_signed` returned the path as a success. The result
screen then names the file. A half-written PSBT is not a PSBT, and the
user's next act is to pull the stick, so nobody finds out until a
coordinator refuses it.

It now loops until every byte is down and raises `FileChannelError` naming
the byte counts if progress stops. A medium that is merely **slow**, taking
the bytes 100 at a time, still completes; a guard that refused those would
break the working case, so both are checked. Deleting the guard fails the
suite.

### Everything else in the ticket's list was already contained

| hostile shape | what happens |
|---|---|
| a directory named `x.psbt` | not offered; `is_file()` |
| **a FIFO named `x.psbt`** | not offered; opening one would block for ever |
| a symlink to nothing | not offered |
| a symlink to a file outside the channel | offered in dev, impossible on device: vfat/exfat have no symlinks, and `tests/test_channels.py` fails if the mount unit ever admits one that does |
| a file that vanished mid-flow | `FileNotFoundError`, which `Session.HANDLED` catches |
| an empty or oversized file | `FileChannelError`, already covered |
| a file that grows between the stat and the read | refused on what arrived, not on the stat (A1) |
| a read-only medium | `PermissionError`, contained |
| malformed, huge, and structurally junk UR frames | attack 3, including 32,000 valid-CRC frames from two interleaved transactions |

The FIFO is the one worth naming. `is_file()` is all that stands between
the device and a read that never returns, on a machine with no shell to
kill it from, and nothing said so. Changing `is_file()` to `exists()` now
fails the suite.

**Nothing wrote outside the channel it was given.** The test asserts that
directly, with a second temporary directory that must stay empty.

### The mount, which had never been fed anything hostile

Asked on the board, 2026-09-06:

```
/boot/firmware exists mountpoint      vfat rw,relatime,fmask=0022,dmask=0022,…
/mnt/usb       exists NOT a mountpoint
```

Both answers are right. The card channel is a real vfat mount, so the
no-symlinks reasoning covers it as well as the stick. `/mnt/usb` with no
stick in it is a plain directory on the boot card and is **not** offered,
which is the A1 fix working on the real board rather than in a fake.

`image/corky-usb@.service` mounts `-t vfat,exfat` with `noexec,nosuid,nodev`
and `umask=0077`, and `tests/test_channels.py` fails if any of that
changes, checking every `ExecStart` and requiring the flags to be options
rather than substrings.

### Carried to A7, not fixed here

`/boot/firmware` is mounted by the OS with `fmask=0022,dmask=0022`, so a
PSBT written to the card is world-readable, where the stick's own unit
sets `umask=0077` and the comment there says "a PSBT is nobody else's
business". The two channels disagree about that, and the card's options
come from the image's `fstab` rather than from anything in this
repository. It is the image's problem, which is A7's.
