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

    def show(self, image, sensitive=False):
        self._n += 1
        if sensitive:
            # Never persist seed-bearing screens, even in dev (repo
            # standard 5: no silent persistence of key material).
            from PIL import Image
            image = Image.new("RGB", (self.width, self.height), "#1A1714")
        image.save(self.outdir / f"frame-{self._n:03d}.png")


class ScriptExhausted(Exception):
    """The dev keypad script ran out — the session script was too short."""


class DevButtons:
    """Reads single-letter commands from a script string (or any iterable).
    Keys: u/d/l/r = d-pad, p = centre press, a = select/KEY1,
    b = back or delete/KEY2, c = abort/KEY3."""

    def __init__(self, script):
        self._script = iter(script)

    def read(self):
        try:
            return next(self._script)
        except StopIteration:
            raise ScriptExhausted("dev keypad script exhausted") from None

    def pressed(self):
        """Non-blocking on the device; on the dev harness it consumes the
        script exactly as read() does, so a scripted session stays
        deterministic instead of spinning on a poll that never returns."""
        return self.read()


class DeviceDisplay:
    """ST7789 320x240 (SeedSigner+ hat) via the vendored driver."""

    def __init__(self, width=320, height=240):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hw" / "vendor"))
        from st7789 import ST7789
        self._lcd = ST7789(width=width, height=height)
        self.width, self.height = width, height

    def show(self, image, sensitive=False):  # noqa: ARG002 - the display contract; only the dev display blanks
        self._lcd.show_image(image, 0, 0)


class DeviceButtons:
    """GPIO buttons per hw/HARDWARE.md pin map (BOARD numbering).
    The SeedSigner+ hat (A-13b) keeps the same GPIO map as the 1.3" hat —
    proven by stock SeedSigner firmware driving both. Navigation scheme is
    d-pad + A/B/C keys (A-15 as amended: the four-button requirement died
    with the Display HAT Mini when the Plus hat took its place)."""

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
            key = self.pressed()
            if key is not None:
                return key
            time.sleep(0.02)

    #: When more than one contact is closed, this decides. A deliberate
    #: press beats a direction, because pushing the centre of a five-way
    #: stick can close a direction on the way down, and the old code
    #: returned whichever pin came first in the dictionary, which was "u".
    #: On the board that made a centre press on Tools read as up (Ben,
    #: 2026-09-05).
    PRIORITY = ("press", "a", "b", "c")

    def pressed(self):
        """Whatever is down right now, or None. Does not block.

        The polling loops (waiting on a stick, running the camera) must stay
        responsive to Back while doing their own work, so they cannot sit
        inside read().

        One press gives one event. The wait is for EVERY contact to open,
        not just the one that was chosen, so a direction still held from
        the same movement does not fire again the moment this returns.
        """
        import time
        low = [k for k, pin in self.PINS.items()
               if self._gpio.input(pin) == self._gpio.LOW]
        if not low:
            return None
        chosen = next((k for k in self.PRIORITY if k in low), low[0])
        while any(self._gpio.input(pin) == self._gpio.LOW
                  for pin in self.PINS.values()):
            time.sleep(0.01)                  # wait for release (debounce)
        return "p" if chosen == "press" else chosen
