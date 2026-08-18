# Corky hardware reference
*Extracted from the SeedSigner repo (MIT) 2026-08-17, so the UI layer targets
Ben's exact kit with zero guesswork.*

## The kit (identical to a SeedSigner build, board swapped)

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
- `qrcode` for encode, `urtypes` for UR (`crypto-psbt`) animated QR framing —
  UR is what Sparrow speaks for animated PSBTs.
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
