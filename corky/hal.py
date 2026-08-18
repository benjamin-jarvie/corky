"""Hardware abstraction: the same UI code runs on the device and on a dev
machine. Device backends drive the vendored ST7789/ILI9341 drivers and GPIO;
dev backends save frames as PNGs and read keys from stdin."""

from pathlib import Path


class DevDisplay:
    """Writes every frame to a PNG so a dev session is fully inspectable."""

    def __init__(self, outdir, width=320, height=240):
        self.width, self.height = width, height
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def show(self, image):
        self._n += 1
        image.save(self.outdir / f"frame-{self._n:03d}.png")


class ScriptExhausted(Exception):
    """The dev keypad script ran out — the session script was too short."""


class DevButtons:
    """Reads single-letter commands from a script string (or any iterable).
    Keys: u/d/l/r = d-pad, a = select/KEY1, b = back/KEY2, c = reject/KEY3."""

    def __init__(self, script):
        self._script = iter(script)

    def read(self):
        try:
            return next(self._script)
        except StopIteration:
            raise ScriptExhausted("dev keypad script exhausted") from None


class DeviceDisplay:
    """ST7789 320x240 (SeedSigner+ hat) via the vendored driver."""

    def __init__(self, width=320, height=240):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hw" / "vendor"))
        from st7789 import ST7789
        self._lcd = ST7789(width=width, height=height)
        self.width, self.height = width, height

    def show(self, image):
        self._lcd.show_image(image, 0, 0)


class DeviceButtons:
    """GPIO buttons per hw/HARDWARE.md pin map (BOARD numbering).
    The SeedSigner+ hat (A-13b) keeps the same GPIO map as the 1.3" hat —
    proven by stock SeedSigner firmware driving both; d-pad up/down plus
    A/B cover the whole four-button navigation scheme (A-15)."""

    PINS = {"u": 31, "d": 35, "l": 29, "r": 37, "press": 33,
            "a": 40, "b": 38, "c": 36}

    def __init__(self):
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setmode(GPIO.BOARD)
        for pin in self.PINS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def read(self):
        import time
        while True:
            for key, pin in self.PINS.items():
                if self._gpio.input(pin) == self._gpio.LOW:
                    while self._gpio.input(pin) == self._gpio.LOW:
                        time.sleep(0.01)      # wait for release (debounce)
                    return "a" if key == "press" else key
            time.sleep(0.02)
