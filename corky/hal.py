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

    def show(self, image, sensitive=False):  # noqa: ARG002 - see below
        """Paint the frame. `sensitive` is accepted and ignored, and that
        is the point of it.

        The two displays answer the same call differently ON PURPOSE, and
        that difference is a security property rather than an oversight.
        DevDisplay writes every frame to a PNG, so a sensitive frame must
        be blanked or a paper backup ends up on a developer's disk. This
        display writes to a panel a person is looking at, and a backup
        they cannot see is not a backup.

        So: the only place key material may be drawn is the one place it
        cannot be kept. Nobody had written that down until audit A1.
        """
        self._lcd.show_image(image, 0, 0)


class DeviceButtons:
    """GPIO buttons per hw/HARDWARE.md pin map (BOARD numbering).
    The SeedSigner+ hat (A-13b) keeps the same GPIO map as the 1.3" hat —
    proven by stock SeedSigner firmware driving both. Navigation scheme is
    d-pad + A/B/C keys (A-15 as amended: the four-button requirement died
    with the Display HAT Mini when the Plus hat took its place)."""

    PINS = {"u": 31, "d": 35, "l": 29, "r": 37, "press": 33,
            "a": 40, "b": 38, "c": 36}

    #: How long a contact may stay closed before it is treated as stuck.
    #: Longer than any deliberate press, short enough that a jam does not
    #: look like a crash.
    STUCK_AFTER = 3.0

    def __init__(self):
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        self._stuck = set()
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
        """Whatever is down right now, or None.

        Returns at once in every normal case. The one exception is a
        contact that will not open: deciding it is jammed rather than held
        takes STUCK_AFTER, and that cost is paid ONCE, because the pin is
        then ignored until it reads high again.

        The polling loops (waiting on a stick, running the camera) must stay
        responsive to Back while doing their own work, so they cannot sit
        inside read().

        One press gives one event. The wait is for EVERY contact to open,
        not just the one that was chosen, so a direction still held from
        the same movement does not fire again the moment this returns.

        **A contact that never opens is ignored, not waited on, and never
        reported as a press.** The wait used to have no bound: a shorted or
        jammed button held the loop for ever and the device looked crashed
        while every other button still worked underneath. A jam is a
        plausible fault in a sealed enclosure, and the honest behaviour is
        to carry on without the broken control.

        The first version of that fix returned the jammed key anyway, so a
        stuck contact fired a phantom press, and an intermittent one fired
        a fresh phantom every time it closed. A devil's advocate review
        caught it the same day. A key that is still down at the deadline
        was never a press, so nothing is returned for it.

        A pin that later goes high is admitted again on the next read.
        """
        import time
        self._stuck = {k for k in self._stuck
                       if self._gpio.input(self.PINS[k]) == self._gpio.LOW}
        low = [k for k, pin in self.PINS.items()
               if self._gpio.input(pin) == self._gpio.LOW
               and k not in self._stuck]
        if not low:
            return None
        chosen = next((k for k in self.PRIORITY if k in low), low[0])
        deadline = time.monotonic() + self.STUCK_AFTER
        while True:
            held = [k for k, pin in self.PINS.items()
                    if self._gpio.input(pin) == self._gpio.LOW
                    and k not in self._stuck]
            if not held:
                break                         # released: a real press
            if time.monotonic() > deadline:
                self._stuck.update(held)
                if chosen in held:
                    # It never opened, so it was never a press.
                    return None
                break
            time.sleep(0.01)                  # wait for release (debounce)
        return "p" if chosen == "press" else chosen
