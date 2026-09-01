# Audit: remaining software work, on-device UI, and branding

Scope: the three questions in `tasks/audit-ui-and-branding.md`. Every claim
below cites a file and line, or a measurement that this document explains how
to reproduce. The signing code, `shim/bip39_shim.py` and `SHIM_HASH` were read
only; none of them changed.

Measurements were produced by rendering every screen with `ImageDraw.text`
instrumented to report each string's bounding box, and by replaying the real
key-handling loops in `corky/main.py` against real BIP39 and codex32 strings.
Both are now permanent suites: `tests/test_screen_fit.py` and
`tests/test_ui_cost.py`.

The finding sections record audit baseline `ac5eeaf`, before the small changes
listed at the end. The post-change status is stated explicitly where the
baseline and current tree differ.

---

## 1. "No software work remains until the hardware arrives"

**Not true.** Four bring-up or validation groups genuinely need hardware.
Fifteen software items can be worked before or independently of that
validation.

`corky/qrchannel.py`, `corky/seedqr.py` and `corky/filechannel.py` were read
in full and contain no stubs or unfinished branches; their gaps are in how
`main.py` drives them (D11, D12).

### Hardware-blocked

| Item | Evidence | Gate |
|---|---|---|
| Camera focus, lighting, capture timing, and end-to-end QR validation | `corky/main.py:48-56`, `CameraQrSource.scan_key` raises, `scan_psbt_frames` returns an empty iterator | M1 |
| Display and GPIO physical bring-up | `corky/hal.py:52-84`, `DeviceDisplay`/`DeviceButtons` import `st7789` and `RPi.GPIO`; neither has ever run | M0/M2 |
| 320x240 ST7789 geometry and rotation validation | `hw/vendor/st7789.py:3` still says "fixed 240x240"; its `MADCTL` byte is `0x70` (MV set, so landscape is plausible) but nothing proves the geometry on the panel | M0 |
| Peak RSS, boot budget, and power-off RAM wipe | PLAN A-2, A-8, A-12 | M0/M2 |

The zbar decode step is *not* fully blocked: decoding a QR from an image file
needs no camera, so the parse-and-cap path (`_scan_key_guarded`,
`corky/main.py:242-251`) can be exercised against fixture images today.

### Not hardware-blocked, software work that remains

- **S1. At the audit baseline, the image could not load a PSBT at all.**
  `image/corky.service` ran `main.py --datadir=/run/corky` with no
  `--stick-dir`, so
  `Session.stick_dir` is `None` (`corky/main.py:85`) and `state_load`
  (`471-509`) skips the file channel entirely and polls the QR source, which
  on the device is the stub above. Both v1 transfer channels are therefore
  unreachable in the shipped unit. This is a unit-file line, not hardware.
- **S2. No passphrase entry UI.** Only `--passphrase` (`corky/main.py:577`).
  Named in PLAN's post-v1 todo for M2.
- **S3. No typed xprv or descriptor entry.** `screens.SEED_MENU_OPTIONS`
  offers "Scan descriptor QR" and "Scan xprv QR" only, and both route to
  `_keymaterial` -> the camera. With SeedQR and codex32-scan, **four of the six
  seed modes dead-end on the device today**, and they fail invisibly (D6).
- **S4. Secret-bearing RPC parameters travel as argv.** `signer.Rpc.call`
  (`corky/signer.py:52-59`) builds a `bitcoin-cli` command line; the xprv is an
  argument during `importdescriptors`. The `-stdin` migration is already
  written down in PLAN's hardening backlog.
- **S5. There is no testnet4 chain option.** `corky/signer.py:40-50` accepts
  `test` and maps it to `-testnet` plus `testnet3`; PLAN's hardening backlog
  explicitly says to revisit the mapping for testnet4. This is a compatibility
  gap, not a claim that the current `-testnet` path selects the wrong directory.
- **S6. Every long string on every screen is clipped or drawn off-canvas.**
  18 measured cases; see D1-D3.
- **S7. Fourteen named UI defects** that need no hardware to fix: D4-D9 and
  D11-D18. The QR defects alone make the animated-QR output path unusable as
  written.
- **S8. At the audit baseline there was no branding or splash.** See section 3.
- **S9. A finished session stops the service.** `main()` returns after one
  signature, and `image/corky.service` is `Type=simple` with
  `Restart=on-failure`, so a clean exit leaves the unit stopped. See D8.
- **S10. The hardened release image is not implemented.**
  `image/provision.sh:6-7` says the current scripts build only the dev image
  and defer network removal, read-only root, and reproducibility to M3; PLAN
  A-12 additionally requires the RAM-resident image. Building those artifacts
  is software work that can start without the panel. Hardware is needed to
  validate memory, boot time, persistence, and physical radio claims.
- **S11. There is no user-facing public-descriptor export.** README says Corky
  exports public descriptors for the paper/watch-only half of the backup, and
  `corky/signer.py:134-137` implements `public_descriptors`, but no production
  caller in `corky/main.py` displays or transfers them. Repository references
  outside the definition are tests only. Sparrow onboarding therefore lacks a
  device flow even though the underlying Core query exists.
- **S12. The third transfer channel and removable-media mounting are absent.**
  PLAN A-12 requires a `/mnt/microsd` watcher after the RAM-resident image
  lands. The current service passes only `/mnt/usb`, `provision.sh` merely
  creates that directory, and there is no mount/automount unit. The USB code
  works only after an operator mounts the drive; the boot-microSD channel has
  no production path yet.
- **S13. The adapter implementation itself need not wait for hardware.**
  `CameraQrSource` is an explicit stub, while PLAN A-13b identifies the known
  320x240 init variant (dimension swap and rotation). Hardware is required to
  validate focus, timing, GPIO, and panel geometry, but the camera adapter,
  driver variant, fixture-image decode tests, and service/mount configuration
  can be written first.
- **S14. README overstates the file channels as unlimited.** It says the file
  channels have no size limit, while `corky/filechannel.py:18` enforces a
  4 MiB cap. The cap is a reasonable hostile-input guard, but the public claim
  must state it.
- **S15. README names the wrong generated-backup format.** The v1 scope says
  the Core-RNG tool gives a codex32 string; PLAN A-19 and `_tool_generate`
  correctly use Core's master xprv. This is documentation drift, not a signing
  defect.

Explicitly deferred capabilities are not counted as current implementation
defects: multisig, message signing, address explorer, dice entropy, and the
possible Rust v2 front end are out of v1 scope. PLAN also records Fractal
codex32 QR interoperability as a future watch item and anti-exfiltration as
unavailable until Bitcoin Core exposes a suitable signing hook.

---

## 2. Is the on-device UI usable?

Judged against a 320x240 ST7789. At the baseline, the *review* screen was good
and the codex32 grid was well thought out, but seed entry, error recovery, and
the backup screens were not shippable. The changes below repair screen fit and
baseline error visibility; D4, D5, D7, D8, and D11-D18 remain.

### Readability

**D1. The backup screens run off the bottom of the display.**
`screens.codex32_share_display` (`corky/screens.py`) draws `len(share)//4`
four-character groups, three to a row, from `y = 0.26h` with a `0.13h` row
pitch. A 64-byte BIP39 seed encodes to a **127-character** codex32 secret =
32 groups = **11 rows**, ending near `y = 1.56h`. Measured on 320x240, the
master xprv from the A-19 generate flow (111 chars) draws four of its rows
between y=242 and y=350 on a 240-tall panel. Both `_tool_backup`
(`corky/main.py:376-381`) and `_tool_generate` (`411-412`) are therefore
unusable on hardware: the user is told to write down a string whose last third
is not on the screen.

**D2. The first-address confirmation is off both edges.** `_tool_generate`
passes `f"first address {address}"` into `codex32_verified`
(`corky/main.py:417-418`). A bech32 address at `0.06h` measures 390px wide,
centred: bounding box `[-36 .. 354]` on a 320px screen. The A-19 verification
step cannot be read at all.

**D3. No screen measures its own text.** `home()`'s first menu line is 51
characters at `0.055h` and its right edge lands at x=322 on a 320px screen
(x=316 on the 240px pocket build). `generate_warning` and
`keymaterial_warning` overflow six more lines on 240x240. Every string is
hand-fitted to one guessed width; nothing calls `textbbox`, so drift is
invisible until it is on a panel.

### Presses per task

Counted by replaying `_collect_words` (`corky/main.py:435-467`) and
`_codex32_entry_one` (`290-311`) against real strings:

| Task | Presses |
|---|---|
| Enter a random 24-word mnemonic | **546** (22.8/word; worst single word 36) |
| Enter one 127-char codex32 share | **480** |
| Recover from a 2-of-3 split (two shares) | **~960** |

Navigation overhead from the default selections is smaller but still
material: opening 24-word entry from home costs 5 presses before the first
letter (**551 total** for the measured sample); opening typed codex32 costs 5
before the grid; a one-string 24-word backup costs about **556** through its
final acknowledgement; Core generation costs 9 through address confirmation.
Once a wallet and PSBT are loaded, a transaction with `p` output pages costs
`p` review presses to visit every page and sign; rejection costs one `C`.

**D4. The letter cursor is a 26-position dial.** Word entry moves the cursor
one letter at a time with u/d and only reaches the candidate list through `R`.
The codex32 flow already solves this problem properly with a 4x8 grid
(`screens.codex32_entry`), so the device carries two different input models
for the same job and uses the worse one for the commonest task. A grid for
letters would cut D4's 546 to roughly a third.

**D5. There is no word-level undo.** `B` deletes one letter of the *current*
prefix. A word committed wrongly at position 3 of 24 cannot be corrected; `C`
abandons the whole entry (`corky/main.py:460`) and returns to the seed menu
with all 546 presses lost.

### Error recovery

**D6. Seed-entry errors flash and vanish.** `state_seed_menu`
(`corky/main.py:139-142`) shows the FAILED screen and returns immediately;
`state_home` repaints home on the next line (`110`) with no button wait.
`state_tools` does wait (`332`), so the two menus behave differently. On the
device this is what the user sees when they choose any of the four camera-fed
seed modes: a flicker, then the home screen. The message
"camera not yet wired (M1); use the USB stick" is never legible.

**D7. Back at the PSBT screen ends the session.** `state_load` returns on
`b`/`c` (`505-507`), `state_home` returns (`109`), and `run()`'s `finally`
calls `close_session`. The wallet is dropped and the seed must be re-entered
in full. There is no route from load or review back to home.

**D8. One PSBT per boot, then the program exits.** `state_sign` paints the
result and returns with no key wait (`564-565`); the call chain unwinds out of
`main()`. Combined with S9, the result screen is the final frame on a device
that must now be power-cycled to sign anything else.

**D9. The sign button refuses silently.** `state_review` requires every
output page to have been seen before `A` signs; when the requirement is not
met it advances the page and loops (`536-540`) with no message. On a 6-output
PSBT, pressing SIGN appears to scroll the screen for no reason.

**D15. The held error offers a false recovery path and no dismissal cue.**
`CameraQrSource.scan_key` raises "use the USB stick", but the USB path accepts
only `*.psbt`; it cannot load SeedQR, codex32, xprv, or descriptor key material.
The catch blocks now wait for a key, yet `screens.result(ok=False)` still says
"power off when done" and never says that a key returns home. The error is
readable now, but its recovery advice and controls are wrong.

**D16. `C · off` does not turn the device off.** `screens.home` labels the
control as power-off, but `state_home` only returns from the Python process.
It does not call system shutdown or stop bitcoind; combined with S9, the UI
service simply remains inactive after the clean exit. The label promises a
security-relevant state transition that the implementation does not perform.

**D17. Teardown failure is silent despite the “nothing kept” claim.**
`Session.run` catches and discards every exception from `close_session`, and
`signer._drop_wallet` deletes the wallet directory with `ignore_errors=True`.
No screen reports that unload or deletion failed. On real power removal the
ramdisk is still the final safety boundary, but D16 means the on-screen `off`
path does not reach that boundary; the current process can exit while bitcoind
and a failed-to-delete wallet remain alive.

**D18. Load, review, and signing errors bypass UI recovery.** The menu catch
blocks cover seed/tool setup only. `state_load` does not catch
`FileChannelError` or filesystem errors, and `state_review`/`state_sign` do not
catch RPC failures. These exceptions unwind the process instead of painting a
held error. With `Restart=on-failure`, a bad USB file can cause a restart and
repeat after the user re-enters the seed until the file is removed.

### The QR return channel

**D11. The signed-PSBT QR is stretched out of square.** `state_sign`
(`corky/main.py`) renders frames with `qrchannel.frames_to_images` (square, at
`box_size=4`) and then calls `img.resize((self.w, self.h))`, 320x240 on the
primary panel. A QR stretched to 4:3 has non-square modules and interpolated
edges; the coordinator's scanner has to recover a code that is no longer a
code. It should be scaled by an integer factor and letterboxed on the ink
ground, never stretched.

**D12. The animated QR plays once, with no frame timing.** The same loop
shows each frame exactly once, as fast as the display driver accepts them,
and then paints the result screen over the last frame. A BC-UR fountain
animation has to cycle continuously at a steady rate for a phone or Sparrow to
catch every part; a single unpaced pass is not readable for any multi-frame
PSBT. The loop needs a frame delay, repetition until the user says it is
captured, and a key to stop.

Neither is fixed here. Both change what the coordinator sees, and neither can
be proven without a scanner in front of the panel, so they are reported for the
M1 bring-up rather than guessed at now. They are software work, not
hardware-blocked design work: the fix is known for both.

**D13. A stalled Core can leave BUSY on screen forever.** `Rpc.call`
(`corky/signer.py:52-59`) invokes `subprocess.run` without a timeout. Seed
opening, generation, PSBT description, and signing all paint a BUSY screen
before making one or more RPC calls, and none polls a button while the child
process is blocked. A wedged `bitcoin-cli` therefore has no UI recovery path;
power removal is the only escape. This can be unit-tested with a stalled fake
CLI and does not require hardware.

**D14. Backup screens promise verification that never occurs.**
`codex32_share_display` says "checksum re-verifies before you leave" and ends
with "I wrote it, verify me", but `_show_backup` only waits for a button and
returns. `_tool_backup` accepts that acknowledgement without re-entry, while
`_tool_generate` shows an address from the still-open original Core wallet,
not from the user's transcription. A mistyped paper backup is therefore never
checked despite the on-screen claim. Fixing this needs an explicit re-entry or
independent verification ceremony, not hardware.

### Control surface

**D10. The brief says four buttons; the code needs seven.**
`hal.DeviceButtons.PINS` maps u/d/l/r/press/a/b/c, and codex32 grid entry needs
all four directions while `r` doubles as an action on home and word entry. PLAN
A-15b resolved the hardware question in favour of the SeedSigner+ d-pad, so the
code matches the plan and the *brief* is what is out of date, but this must be
settled before M2, because on a genuine four-button hat the codex32 modes and
the tools menu cannot be driven.

### Screens a user can get stuck in

D13 can block forever on BUSY. D7 and D8 are one-way doors that cost a full
seed re-entry; D14 ends a backup with verification implied but not performed;
and baseline D6 made the seed menu look inert on hardware. D15 leaves that
error's current recovery affordance misleading even though it is now held.
D16 does not perform its promised shutdown, D17 can silently leave the wallet
alive until real power loss, and D18 converts routine IO/RPC failures into a
service restart instead of a recoverable screen.

---

## 3. Does the start screen show a Bitcoin Butlers logo and title?

**At the audit baseline: no. After the justified changes below: yes.** The
current boot path paints `screens.splash` through `corky-splash.service` before
bitcoind. Physical-panel rendering remains a hardware bring-up check.

Evidence:

- The baseline's first frame was `screens.home` (`corky/main.py:103`), which
  painted the word `CORKY` in PIL's default bitmap font plus the tagline.
  There was no mark and no house name.
- The baseline had no image asset or generated logo path.
- The baseline had no boot splash. `image/corky.service` was ordered
  `After=corky-bitcoind.service`, so nothing paints the panel until bitcoind is
  up. The display is dark for the whole 60-90s boot budget (PLAN A-8).

### Proposed design: `screens.splash(w, h)`

Fits 320x240 and 240x240, renders correctly in one bit.

```
+------------------------------------------+
|                                          |
|              ___        ___              |   bow-tie mark
|              \  \  []  /  /              |   two outline triangles
|               \__\    /__/               |   meeting at a knot square
|                                          |   96x96 at 320x240
|                                          |
|       B I T C O I N  B U T L E R S       |   house name, letterspaced
|   -------------------------------------  |   1px rule
|                CORKY                     |   product, 0.10h
|        Core's keys, nothing kept         |   tagline, 0.045h
+------------------------------------------+
```

Rules that make it monochrome-safe and panel-safe:

1. **Two tones only.** Ink ground, cream everything. No hue carries meaning,
   so a 1-bit or inverted render loses nothing. The existing palette's red,
   green and ochre stay out of the splash.
2. **Outline geometry, not fills.** The bow-tie is drawn as 3px strokes, which
   survives both a 1-bit threshold and the panel's pixel grid. Minimum stroke
   3px, minimum glyph height 8px.
3. **Proportional layout**, like every other screen: the mark occupies
   `0.17h..0.43h`, the rule sits at `0.68h`, and the product block runs from
   `0.79h` to `0.91h`, so the same code drives the 240x240 pocket build.
4. **Every string measured** against the canvas before it ships
   (`tests/test_screen_fit.py`), so it cannot repeat D3.
5. **Shown before bitcoind, not after.** `corky.service` pulls in a
   `corky-splash.service` ordered `Before=corky-bitcoind.service`, so the brand
   is on the panel for the whole boot instead of a dark screen.

---

## Changes made from this report

Kept small and separate from each other. Everything else above remains
reported because it needs a design decision (D4, D5, D7, D8, D10, D13-D18),
broader image/onboarding work (S10-S13), or hardware validation.

1. **Screen fit**, `codex32_share_display` paginates instead of drawing off
   the canvas (D1); the first-address confirmation is shortened and wrapped
   (D2); `home`, `generate_warning` and `keymaterial_warning` are re-fitted
   (D3). Guarded by `tests/test_screen_fit.py`, which measures every string on
   every screen at both resolutions.
2. **Error visibility**, the seed menu waits for a key on failure like the
   tools menu does (D6), and the review screen says why it will not sign yet
   (D9). Guarded by `tests/test_ui_cost.py`.
3. **Branding**, `screens.splash` and `image/corky-splash.service` per the
   design above; the signing unit activates the splash, and the render uses
   one cream foreground tone on the ink ground.
4. **The USB channel**, `image/corky.service` passes `--stick-dir=/mnt/usb`
   and `provision.sh` creates that directory (S1). Mounting the stick there is
   still an operator step; until it is mounted the directory is empty and the
   flow behaves as it does today, so this closes the code half of S1 only.
5. **README accuracy**, file transfer now states its 4 MiB guard, and the
   Core-RNG tool correctly names its master-xprv backup (S14-S15).

Coder verification at handoff: `RUN_NODE=1 ./run_tests.sh`, all 17 suites
passed, including the bitcoind ones. `tests/e2e_session.py` sessions F, G and N
were updated for the new pagination and the refusal message, which are
deliberate behaviour changes. `shim/bip39_shim.py`, `SHIM_HASH` and the signing
path are untouched; `tests/test_integrity.py` still passes on the pinned hashes.

---

## Requirement traceability

| Operator requirement | Evidence |
|---|---|
| Reassess “no software work remains” from PLAN, README, and every `corky/*.py` | Section 1 separates four hardware-validation groups, fifteen software items, and explicit out-of-scope/watch items. |
| Judge 320x240, four-button usability by presses, recovery, readability, and traps | Section 2 records measured entry and navigation costs plus named defects D1-D18, including the A-15b control-surface mismatch, one-way flows, an indefinite BUSY state, unverified backups, misleading recovery/shutdown controls, silent teardown failure, and unhandled IO/RPC errors. |
| Find boot/splash branding and propose a monochrome-safe 320x240 design | Section 3 traces the baseline boot path, specifies the design, and states the current post-change path. |
| Report before changing code | Audit commit `1187e3a` precedes implementation commit `c81b528`. |
| Change only what the report justifies | The four bounded change groups above map directly to D1-D3, D6, D9, S1, and S8; all other findings remain report-only. |
| Do not change signing code, `shim/bip39_shim.py`, or `SHIM_HASH` | Task-wide diff contains none of those paths; the frozen integrity unit test passes. |
