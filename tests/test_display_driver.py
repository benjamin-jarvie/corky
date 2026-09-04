"""The ST7789 window arithmetic, tested without a panel.

The driver is vendored from SeedSigner, where it only ever drove a 240x240
hat, so both high octets of the column and row address were hardcoded to
0x00. Corky's primary panel is the SeedSigner+ 2.8" at 320x240
(hw/HARDWARE.md), and 320 does not fit in one octet. This suite exists
because that defect is silent: the SPI writes all succeed and the panel
simply shows nonsense.

TESTING.md rule 9 in miniature. The bus is hardware, the arithmetic is not.
Stub spidev and RPi.GPIO, then read back the bytes the driver would send.

Run: python3 tests/test_display_driver.py
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"ok   {name}  {detail}")
    else:
        FAIL += 1
        print(f"FAIL {name}  {detail}")


class FakeSpi:
    def __init__(self, *_a, **_k):
        self.max_speed_hz = 0
        self.written = []

    def writebytes(self, b):
        self.written.append(("cmd_or_data", list(b)))

    def writebytes2(self, b):
        self.written.append(("bulk", len(b)))


def install_stubs():
    """Stand in for the two modules that only exist on a Pi."""
    spidev = types.ModuleType("spidev")
    spidev.SpiDev = FakeSpi
    sys.modules["spidev"] = spidev

    gpio = types.ModuleType("RPi.GPIO")
    gpio.BOARD = "BOARD"
    gpio.OUT = "OUT"
    gpio.HIGH = 1
    gpio.LOW = 0
    gpio.setmode = lambda *_a: None
    gpio.setwarnings = lambda *_a: None
    gpio.setup = lambda *_a, **_k: None
    gpio.output = lambda *_a: None
    rpi = types.ModuleType("RPi")
    rpi.GPIO = gpio
    sys.modules["RPi"] = rpi
    sys.modules["RPi.GPIO"] = gpio


def window_bytes(lcd, spi):
    """The 0x2A/0x2B address-window bytes from one SetWindows call."""
    spi.written.clear()
    lcd.SetWindows(0, 0, lcd.width, lcd.height)
    flat = [(kind, vals) for kind, vals in spi.written]
    out, current = {}, None
    for _kind, vals in flat:
        if vals in ([0x2A], [0x2B], [0x2C]):
            current = vals[0]
            out[current] = []
        elif current is not None:
            out[current].extend(vals)
    return out


def main():
    install_stubs()
    sys.path.insert(0, str(ROOT / "hw" / "vendor"))
    from st7789 import ST7789

    # ---- the panel Corky actually ships: 320x240 ----
    lcd = ST7789(width=320, height=240)
    spi = lcd._spi
    w = window_bytes(lcd, spi)

    check("320x240 column address is 4 bytes", len(w.get(0x2A, [])) == 4,
          f"got {w.get(0x2A)}")
    # Xend - 1 = 319 = 0x013F. The high octet is the whole point.
    check("320x240 column end is 319, not 63",
          w.get(0x2A) == [0x00, 0x00, 0x01, 0x3F],
          f"got {[hex(b) for b in w.get(0x2A, [])]}")
    check("320x240 row end is 239",
          w.get(0x2B) == [0x00, 0x00, 0x00, 0xEF],
          f"got {[hex(b) for b in w.get(0x2B, [])]}")

    # The window must span exactly as many pixels as show_image writes.
    xs, xe = (w[0x2A][0] << 8) | w[0x2A][1], (w[0x2A][2] << 8) | w[0x2A][3]
    ys, ye = (w[0x2B][0] << 8) | w[0x2B][1], (w[0x2B][2] << 8) | w[0x2B][3]
    check("320x240 window covers the whole panel",
          (xe - xs + 1) * (ye - ys + 1) == 320 * 240,
          f"window {xe - xs + 1}x{ye - ys + 1}")

    # ---- the pocket build's panel: unchanged from upstream ----
    lcd2 = ST7789(width=240, height=240)
    w2 = window_bytes(lcd2, lcd2._spi)
    check("240x240 column end is 239",
          w2.get(0x2A) == [0x00, 0x00, 0x00, 0xEF],
          f"got {[hex(b) for b in w2.get(0x2A, [])]}")
    check("240x240 window covers the whole panel",
          ((w2[0x2A][2] << 8 | w2[0x2A][3]) + 1)
          * ((w2[0x2B][2] << 8 | w2[0x2B][3]) + 1) == 240 * 240)

    # ---- show_image must refuse a mismatched image, not corrupt the panel ----
    from PIL import Image
    try:
        lcd.show_image(Image.new("RGB", (240, 240)), 0, 0)
        check("show_image rejects a wrong-sized image", False, "it accepted one")
    except ValueError:
        check("show_image rejects a wrong-sized image", True)

    # ---- and must write exactly width*height*2 bytes for RGB565 ----
    spi.written.clear()
    lcd.show_image(Image.new("RGB", (320, 240), "#123456"), 0, 0)
    bulk = [n for kind, n in spi.written if kind == "bulk"]
    check("show_image writes 2 bytes per pixel", bulk == [320 * 240 * 2],
          f"wrote {bulk}")

    print("\n" + "=" * 60)
    print(f"PASS {PASS}   FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
