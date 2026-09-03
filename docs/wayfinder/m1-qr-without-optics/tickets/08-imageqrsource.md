# 08 Build it

Labels: wayfinder:task (AFK)
Blocked by: 01, 03, 05, 06

## Question

With the contract fixed (04), the rules decided (05), the density policy
decided (03) and the harness built (06), write the source.

An `ImageQrSource` that takes image frames, decodes them with zbar, applies
the duplicate and hostile-frame guards, enforces the timeout and abort rules,
and satisfies the `QrSource` contract. `CameraQrSource` then becomes a thin
subclass whose only new job is producing images, which is the one part that
needs the board.

Adversarial coverage against the ticket 06 harness, in the style of
`tests/test_adversarial.py`.

## Resolution (2026-09-03)

Built, and the map's destination is reached.

**`corky/qrchannel.py`** gains four things and keeps its opaque-bytes law:

- `ADVISORY_FRAME_LEN = 400` and `NO_PROGRESS_TIMEOUT = 20.0`, the ticket 03
  and ticket 05 constants. `MAX_FRAME_CHARS = 3000` is untouched and still
  refuses; the new limit only advises, and the comment says so.
- `frame_identity(frame)` returns `(seq_len, message_len, checksum)`, which
  identifies the message a UR part belongs to. Same bounded container
  unwrapping the module docstring already licenses; nothing here parses a PSBT.
- `decode_image(image)` wraps pyzbar, lazily imported like `frames_to_images`,
  and treats its output as untrusted.
- `scan_psbt(source, clock, timeout, on_event, abort)` is the caller-side loop.
  Ticket 04 put the assembler here rather than in the source, so this one
  function holds every stopping rule and both the camera and the replay double
  inherit them. The clock is injectable, so a 20-second timeout costs nothing
  to test. A source may yield `None` for "a tick passed, nothing in view",
  which is what lets the timeout fire on a still scene.

**`corky/main.py`**: `CameraQrSource` is split. `ImageQrSource` turns images
into strings and holds no policy. `CameraQrSource` subclasses it and its only
remaining job is `images()`, which still raises. That is now **four lines** of
untested code in the whole channel, and all four need the board.

**`tests/m1/test_scan_loop.py`: 13 checks, all green.** Clean scan, duplicates
five deep, out of order, garbage skipped, foreign UR skipped, oversize skipped,
stalled scan times out, a slow-but-healthy scan at 15 seconds per frame is not
killed, a second PSBT restarts, the button aborts, the advisory fires once on
long frames and never on Corky's own, and real PNGs through pyzbar.

**README**: the setup instruction from ticket 03, with the measurement behind
it. `tests/test_readme_claims.py` caught the stale trust-layer line counts as
designed; they are updated (qrchannel 83 to 159, main 718 to 731, functional
total 1,910 to 1,999).

All twelve existing Corky suites still pass.

Closed.

## Amendment (2026-09-03, after `/mp-code-review`)

The resolution above was written alongside the code and two of its claims were
wrong. Both are corrected here rather than quietly edited, because a
retro-fitted resolution is worse than a wrong one.

**"Four lines of untested code in the whole channel" was false.** The Spec axis
counted about fifteen, of which only three needed the board. `decode_image` had
no test caller, and `ImageQrSource.scan_psbt_frames` was untested. Both are
covered now: `ImageReplaySource` routes through `qrchannel.decode_image`, and
`test_scan_loop.py` drives a real `ImageQrSource` subclass over PNGs, blank
views and idle ticks. The honest number is **one statement**, `images()`, and
it needs the board.

**"Both the camera and the replay double get them" was false.** Nothing outside
`tests/m1/` called `scan_psbt`. `state_load` still ran its own bare
`FrameAssembler` loop, so no ticket 05 rule reached a user, and ticket 05's own
rejected option ("feeding two interleaved sequences to one assembler, which is
today's behaviour") was still today's behaviour on the device.

Fixed by splitting the loop. `PsbtScan` is a state machine holding every rule,
drivable one frame at a time; `scan_psbt` is a thin loop over it for callers
with nothing else to do. `state_load` drives `PsbtScan` directly, because it
must also poll the USB stick and the buttons, which a blocking loop cannot do.
The advisory and the restart now render through `screens.busy`, which is the
screen string ticket 03 asked for and which was missing.

Three more defects the review found and this amendment fixes:

- **A regression.** `CameraQrSource.scan_psbt_frames` used to return `iter(())`
  and now raised, while `state_load` catches only `QrChannelError`. On a board
  with no camera the app would have crashed instead of falling through to the
  stick. `images()` returns `iter(())` again, and a test pins it.
- **Guard inversion, against PLAN A-11.** `frame_identity` ran `URDecoder.parse`,
  `Bytewords.decode` and `Part.from_cbor` before `MAX_FRAME_CHARS` refused
  anything. The guards are now one `checked_frame()` that both `frame_identity`
  and `FrameAssembler.feed` call first, and its errors are `QrChannelError` only.
- **`feed(None)` raised `AttributeError`.** The None sentinel was safe only
  inside `scan_psbt`. It now returns False everywhere.

Also: the advisory re-arms after a restart; `SequenceId` replaces a bare tuple;
`scan_key` says "use the USB stick" again rather than quoting this map.
