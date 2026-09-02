# Known issues

Open defects and gaps, recorded so they are not lost between sessions.
Fixed items leave this file and live in the git history instead.

Last reviewed 2026-09-02, after the two-axis review of `e9ca1ab..4f23599`.
Testing rules that came out of that review: [TESTING.md](TESTING.md).

## Deferred by decision (Ben, 2026-09-02): fix at M1

These two are real defects. They wait for M1, when a camera and a real
scanner sit in front of the panel, because neither can be proven without
that hardware.

### I-1 `fit_to_panel` crops an oversized QR instead of scaling it down

`corky/qrchannel.py`. The scale factor is `max(1, min(w // img.width, h //
img.height))`. The `max(1, ...)` floor means a QR larger than the panel is
pasted at full size and clipped, which destroys the quiet zone and makes the
code unreadable.

Today every frame is about 212 pixels against a 320x240 panel, so the factor
is always 1. Audit item D11 asked for "scaled by an integer factor". That
half of D11 is therefore inert: only the letterboxing runs.

Fix: add a downscale path for the oversized case, or cap the fragment size so
frames can never exceed the panel. Verify against a real scanner at M1.
Related: `MAX_FRAGMENT_LEN` in `corky/qrchannel.py`.

### I-2 POWER OFF does not power the device off

`corky/main.py`, `_state_signed` and `state_settings`. Both return control to
Python. Nothing calls a system shutdown and nothing stops `bitcoind`.

The audit raised this as D16 against the old single-shot result screen. The
new SIGN ANOTHER / POWER OFF bar and the settings menu repeat it, so the
device now offers the choice on two screens and honours it on neither.

Fix: POWER OFF should stop `bitcoind` (`bitcoin-cli stop`), unmount or wipe
the ramdisk datadir, then halt. The release image must also make halt safe
with a read-only root (M3).

## Test gaps found by the same review

The review found that new input surfaces shipped without a test that feeds
them real data. All four are now closed; the rules they produced live in
[TESTING.md](TESTING.md). They stay listed here until the next review round
confirms them, because a gap that closes quietly tends to reopen quietly.

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
