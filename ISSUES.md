# Known issues

Open defects and gaps, recorded so they are not lost between sessions.
Fixed items leave this file and live in the git history instead.

Last reviewed 2026-09-02, after the two-axis review of `e9ca1ab..4f23599`.
Testing rules that came out of that review: [TESTING.md](TESTING.md).

> Ben reversed the M1 deferral on 2026-09-02, after the evidence below was
> measured and shown. The reason recorded for the deferral ("neither can be
> proven without hardware") was wrong for both items, which is why
> [TESTING.md](TESTING.md) now carries rule 7.

## Fixed 2026-09-02

### I-1 `fit_to_panel` cropped an oversized QR instead of refusing it

**Fixed.** `corky/qrchannel.py`. The scale factor was `max(1, min(w //
img.width, h // img.height))`. The `max(1, ...)` floor pasted a QR larger
than the panel at full size and clipped it, so the panel showed something
QR-shaped that no scanner could read, with no warning.

Measured before the fix, on the 240px-high panel: a 336-character frame
renders a version-10 QR at 244px and lost 52% of its area. Frames were 255
characters at 212px, so the cliff was 79 characters away, held back only by
`MAX_FRAGMENT_LEN = 100`. Raising it to 150, a reasonable "fewer frames"
tune, crossed it.

Fix: `frames_to_images(panel=(w, h))` LOWERS `box_size` for the whole frame
set when the frames would not fit. `box_size` stays the ceiling, so a frame
that already fits renders exactly as before and the coordinator sees no
change at today's settings; only a frame that would overflow gets smaller
modules. `fit_to_panel` raises `QrChannelError` instead of cropping, and
`state_sign` catches it, because that raise happens after the PSBT is
signed and an unwind would throw the signature away. `tests/test_qr_out.py`
sweeps fragment lengths 100 to 400 on both panels, and pins that a fitting
frame is unchanged.

The ticket offered two fixes: "add a downscale path for the oversized case,
or cap the fragment size". This takes the second, applied to the module
size rather than the fragment length, which caps the pixels directly.
Downscaling was rejected: a non-integer downscale gives non-square modules,
which is the defect D11 named in the first place.

D11 also asked for the letterbox to sit "on the ink ground". It is white
instead, and `corky/qrchannel.py` records why: a QR needs a light quiet
zone, and an ink surround removes it. D11 is wrong on that word.

### I-2 POWER OFF did not power the device off

**Fixed.** `corky/main.py`. Both `_state_signed` and `state_settings`
returned control to Python, which exited 0. `image/corky.service` has
`Restart=on-failure`, so systemd stopped there; `image/corky-bitcoind.service`
is a separate unit and was untouched. bitcoind kept running, `/run/corky`
stayed mounted, and the ST7789 held the signed-result screen, with its
address and amount, on a device the operator believed was off.

Fix: `Session.power_off` covers the result screen, then runs `systemctl
poweroff`. systemd stops the node through `corky-bitcoind.service`'s own
`ExecStop`, which runs `bitcoin-cli stop` and waits up to
`TimeoutStopSec=30`, so the session does not stop the node a second time.
If `systemctl` is missing or fails, meaning no systemd, the session calls
the new `signer.stop_node` and then `halt -p`.

If the board is still running after both attempts, the panel says so and
waits for a key. A silent failure would repeat D16 on the failure path.

A crash still propagates without halting, so systemd can restart the unit.
`tests/test_poweroff.py` runs the real body, with `animate` and `on_device`
set as `main()` sets them, and fakes only the two halt commands. The halt
itself is confirmed on hardware at M0 (Trello BB-20).

The ticket's middle step, "unmount or wipe the ramdisk datadir", is
delegated, not done here, and `Session.power_off` says so: `close_session`
already deletes the wallet directory, which is the only secret-bearing path
under `/run/corky`, and the tmpfs dies with power. Cold-boot RAM remanence
stays an M3 question.

Two claims in the first version of this fix were wrong and are corrected
above. `Requires=` does NOT propagate a stop when a unit exits on its own;
`systemd.unit(5)` gives that behaviour to `BindsTo=`. And
`subprocess.run(check=False)` still raises `FileNotFoundError`, so the
no-systemd fallback could never have run. Both were found by the two-axis
review of this commit, not by the suite.

## Fixed 2026-09-03

Two-axis review of the M1 QR sprint (`/mp-code-review`), 15 findings, all
fixed. The full list is in
`docs/wayfinder/m1-qr-without-optics/tickets/08-imageqrsource.md`, under
Amendment. The three that were more than tidying:

### I-7 `frame_identity` ran container code before the guards

`scan_psbt` called `frame_identity()` before `FrameAssembler.feed()`, so
`URDecoder.parse`, `Bytewords.decode` and `Part.from_cbor` all saw a frame
before `MAX_FRAME_CHARS` refused anything. That breaks the condition PLAN A-11
puts on the opaque-bytes exception, which licenses container unwrapping only
when it is bounded and length-capped first. A 4000-character hostile frame
reached the CBOR decoder.

Fixed: one `checked_frame()` gates both, raises `QrChannelError` only.

### I-8 A camera-less board crashed instead of falling through

`CameraQrSource.scan_psbt_frames` was changed from `return iter(())` to
raising `RuntimeError`. `state_load` catches only `QrChannelError`, so on
hardware the PSBT screen would have taken the app down rather than falling
through to the USB stick. A regression introduced by the same sprint that
claimed the opposite in its own ticket.

Fixed and pinned by a test.

### I-9 One frame in 125 was unreadable by Sparrow, permanently

Corky rendered at exactly 4.0 pixels per module, and about 0.8% of frames
cannot be decoded by zxing, which is Sparrow's decoder. Deterministic, five
failures out of five, while `pyzbar` read the same images. `psbt_to_frames`
emitted one pure cycle which the display looped, so waiting showed the scanner
the same unreadable image forever. Roughly one transfer in seven could never
complete.

Fixed by emitting fountain parts past the pure cycle, as Sparrow's own encoder
does. Ticket 09 in the M1 map has the reasoning and the rejected options.
Rule 8 in `TESTING.md` is the lesson: every test used Corky's own decoder, so
nothing could have caught it.

## Open

Raised by the 2026-08-18 audit, never closed, and NOT closed here. Listed
because the previous version of this file claimed nothing was open.

### D17 Teardown failure is silent

`corky/main.py`, `Session.run`, and `signer._drop_wallet`. `run` catches and
discards every exception from `close_session`, and `_drop_wallet` deletes
the wallet directory with `ignore_errors=True`. No screen reports that the
unload or the delete failed. The power-off path now reports its own
failures, but the wallet teardown before it still does not.

### D18 Load, review and signing errors bypass UI recovery

`corky/main.py`. The menu catch blocks cover seed and tool setup only.
`state_load` does not catch `FileChannelError` or filesystem errors, and
`state_review` does not catch RPC failures. Those exceptions unwind the
process instead of painting a held error, and with `Restart=on-failure` a
bad USB file causes a restart loop until the file is removed.

`state_sign`'s QR path is the one case fixed here, because the raise that
this commit added would otherwise have discarded a good signature.

## Test gaps found by the same review

The review found that new input surfaces shipped without a test that feeds
them real data. All four are now closed; the rules they produced live in
[TESTING.md](TESTING.md). They stay listed here until the next review round
confirms them, because a gap that closes quietly tends to reopen quietly.

I-1 and I-2 were themselves recorded as hardware-blocked, which was wrong:
both were software defects with deterministic tests, and both are fixed
above. Nothing in this file waits on hardware except the standing
milestones below.

### I-3 `fit_to_panel` has no test

**Closed 2026-09-02.** `tests/test_qr_out.py` asserts integer scaling, square
modules, a white letterbox surround, and pins the I-1 cropping gap so the fix
is visible when it lands.

### I-4 `_show_qr_loop` has no test, and its shipping path never runs

**Closed 2026-09-02.** `tests/test_qr_out.py` sets `animate` and runs the real
loop on a thread, asserting it repeats, is paced by its delay, stops on a key,
paints panel-sized frames, and shows a single-frame PSBT once.

### I-5 Typed descriptor entry has no end-to-end test

**Closed 2026-09-02.** Session T2 reads a real private descriptor out of Core,
types it through the device character by character, and signs a PSBT funded to
that descriptor's own first address.

### I-6 `_state_signed` and `_ask_passphrase` have no direct tests

**Closed 2026-09-02.** `tests/test_ui_cost.py` now asserts every branch of
both: sign-another versus power-off versus C on the result screen, and
decline versus accept versus CANCEL on the passphrase prompt.

## Standing hardware-blocked work

Not defects. Recorded so the list above is not confused with them.

- M0: the gate run on the Pi Zero 2 W. Trello BB-20, due 2026-09-04.
- M1: camera QR capture. `CameraQrSource.scan_key` still raises.
- M2: display and GPIO bring-up on real hardware.
- M3: RAM-resident release image, radio kill verification, reproducible build.
