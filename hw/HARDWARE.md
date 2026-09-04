# Corky hardware reference
*Extracted from the SeedSigner repo (MIT) 2026-08-17, so the UI layer targets
Ben's exact kit with zero guesswork.*

## The kit

**v1 primary build (PLAN A-15):** Raspberry Pi CM4 Lite, no-wireless, 2GB
(CM4002000) on a Waveshare CM4-IO-BASE-B carrier, with Ben's SeedSigner+
hat (2.8" ST7789 320x240, d-pad + keys) on the carrier's 40-pin header,
and a camera on the carrier's CSI port. Parts list: ../ORDER.md.

**Pocket build (also supported):** the SeedSigner-shaped original —

- Raspberry Pi Zero 2 W
- WaveShare 1.3" LCD hat: 240×240 IPS, ST7789 controller, RGB565, plus a
  5-way joystick and three push buttons
- Pi camera (OV5647 class) on the CSI ribbon
- Existing SeedSigner enclosure

## Display (from SeedSigner's own driver, now vendored at `hw/vendor/st7789.py`)

- SPI0 CE0 (`spidev(0, 0)`) at 40MHz.
- Control pins, **BOARD numbering** (physical pin numbers): DC=22, RST=13,
  BL=18 (backlight, driven HIGH on init).
- Rendering: PIL `Image` (exactly 240×240) → RGB565 → full-frame SPI write.
  No partial updates; SeedSigner redraws whole frames and it is fast enough
  for menus and animated QRs at a few FPS.
- SeedSigner's display factory also supports st7789 320×240, ili9341 and
  ili9486. **Corky v1's primary display is Ben's SeedSigner+ hat: 2.8" ST7789
  at 320×240 (A-13b/A-15)**; the 1.3" 240×240 remains the pocket build. The
  ili9341 driver stays vendored for Plus-class 2.4" boards.

## Buttons (from `hardware/buttons.py`, BOARD numbering, 40-pin header)

| Control | Pin (BOARD) |
|---|---|
| Joystick up | 31 |
| Joystick down | 35 |
| Joystick left | 29 |
| Joystick right | 37 |
| Joystick press | 33 |
| KEY1 (top) | 40 |
| KEY2 (middle) | 38 |
| KEY3 (bottom) | 36 |

All inputs with internal pull-ups (`PUD_UP`, so pressed = LOW). SeedSigner
adds software debounce and key-repeat timing on top; worth lifting that logic
too when the UI is built.

### What each control does (PLAN A-15c)

Eight controls, all of them used. The "4-button primary scheme" in PLAN A-15
belonged to the Pimoroni Display HAT Mini and died with A-13b/A-15b; it is
not a requirement.

| Control | Corky's meaning |
|---|---|
| Joystick up / down | Move the selection; page through review outputs |
| Joystick left / right | Move within a grid row; toggle the bottom action bar |
| Joystick press | Pick the top candidate word; move the edit caret in codex32 entry; finish text entry |
| KEY1 (A) | Select / activate the highlighted option |
| KEY2 (B) | Delete a character; step back one word; back one page; back to home from review |
| KEY3 (C) | Abort the current flow. Two documented exceptions: in codex32 grid entry C finishes the share, and in text entry C moves focus to the CANCEL / DONE bar |

The same map applies to the CM4 build and the Zero 2 W pocket build: the
CM4 carrier presents the standard Raspberry Pi 40-pin GPIO header, so BOARD
pin numbers are identical on CM4, Zero 1.3 and Zero 2 W.

## Verified on real hardware, 2026-09-04 (Zero 2 W, SeedSigner+ hat)

Everything below was read from source until this date. What the board says:

| Claim | Result |
|---|---|
| ST7789 320x240 over SPI0 CE0 | works, after two driver fixes (ISSUES I-11) |
| Control pins DC=22, RST=13, BL=18 (BOARD) | correct |
| Button map, all eight controls | correct, `tests/hw_buttons.py` |
| Camera is OV5647 class | yes: `ov5647`, up to 2592x1944 |
| picamera2 at ~512x384, ~10fps | 30fps capture; 8.2fps through the whole
  loop including decode and painting the panel |

**The camera is mounted at 90 degrees to the panel.** The frame arrives
sideways. This does not affect scanning, because zbar reads a QR at any
orientation, so Corky must NOT rotate before decoding: it would cost a copy
per frame and buy nothing. Rotate for the viewfinder only, where a human has
to aim.

**The viewfinder rotates 90 and fills the panel (Ben, 2026-09-04).** An
upright picture from a 90-degree mount is portrait, and the panel is
landscape 4:3, so it must give up either screen width or field of view.
Filling crops the left and right edges of the view. Ben chose the screen
over the edges, and rejected turning the module in its mount. Time to first
decode of the same target, measured:

| viewfinder | first lock |
|---|---|
| none, aiming blind | 35.3s |
| rotated, letterboxed | 29.6s |
| rotated, filling the panel | **8.3s** |

A viewfinder is not a nicety. Blind aiming got 1 read in 120s; the same
target with a viewfinder gave 53 in 90s.

**The display driver uses Pillow only, not numpy.** The RGB565 pack is four
`point()` lookups and an `Image.merge("LA", ...)`, 14ms per 320x240 frame on
a Zero 2 W. numpy would have been faster to write and is already on the
board via picamera2, but it is not on the dependency list above, and that
list is the point.

## Camera: the one place Corky must NOT copy SeedSigner

SeedSigner pins `picamera==1.13`, the **legacy** camera stack, frozen to old
Raspberry Pi OS releases. Corky runs current 64-bit Bookworm (bitcoind needs
it), where the legacy stack is gone. Corky uses **picamera2/libcamera**
(preinstalled on Raspberry Pi OS) for the QR video stream instead:
~512×384 at ~10fps into pyzbar, mirroring SeedSigner's stream settings.

## QR libraries (SeedSigner's choices, all applicable)

- `pyzbar` (SeedSigner maintains its own fork pinned by commit) for decode —
  wraps the C zbar library. Corky rule: length-cap and charset-check zbar
  output before use; the string then goes to Core opaque.
- `qrcode` for encode; UR (`crypto-psbt`) framing via SeedSigner's `ur2`
  module, vendored at `hw/vendor/ur2` — UR is what Sparrow speaks for
  animated PSBTs. (SeedSigner also uses `urtypes` for richer UR types;
  Corky needs only crypto-psbt and does it with ur2's CBOR alone.)
- Plus `Pillow` for all rendering. Total third-party surface for the UI:
  Pillow, pyzbar, qrcode, urtypes, picamera2, RPi.GPIO, spidev — none of
  which ever see key material (keys exist only inside bitcoind and, for
  seconds at seed entry, in the shim).

## A finding worth stealing later: how SeedSigner does hot-swap microSD

SeedSigner OS (their buildroot image) runs **entirely from RAM** after boot;
`hardware/microsd.py` watches `/mnt/microsd`, so the boot card can be removed
and reused for data. Corky v1 keeps the USB-stick channel (full Raspberry Pi
OS cannot leave its boot card), but a RAM-resident Corky OS at M3+ would make
the boot card itself the PSBT sled AND make statelessness structural: the
whole OS becomes immutable-by-location. Parked, not planned: 512MB must fit
OS + bitcoind + UI first, and M0 will tell us the headroom.
