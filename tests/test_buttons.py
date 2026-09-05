"""One press gives one event, and the right one.

On the board, 2026-09-05, pressing the centre of the d-pad on the Tools
tile moved the highlight up instead of opening Tools. The pin map was
right and no pin was stuck: a probe on the hardware showed pin 33 going
low on its own. The fault was in the reader. It walked the pin dictionary
and returned the FIRST pin it found low, and "u" is first, so any moment
where a direction contact was also closed became an up.

Run: python3 tests/test_buttons.py (no hardware needed)
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))

LOW, HIGH = 0, 1


class FakeGPIO:
    BOARD = "board"
    IN = "in"
    PUD_UP = "pud_up"
    LOW = LOW

    def __init__(self):
        self.state = {}
        self.reads = 0
        #: pins to release after N reads, so a held press can be simulated
        self.release_after = None

    def setmode(self, *a): pass
    def setup(self, *a, **k): pass

    def input(self, pin):
        self.reads += 1
        if self.release_after is not None and self.reads > self.release_after:
            return HIGH
        return self.state.get(pin, HIGH)


fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)

def main():
    import importlib
    import hal
    sys.modules["RPi"] = types.ModuleType("RPi")
    stub = FakeGPIO()
    sys.modules["RPi.GPIO"] = stub
    sys.modules["RPi"].GPIO = stub
    importlib.reload(hal)
    PINS = hal.DeviceButtons.PINS

    def press(names, release_after=200):
        s = FakeGPIO()
        s.state = {PINS[n]: LOW for n in names}
        s.release_after = release_after
        sys.modules["RPi.GPIO"] = s
        sys.modules["RPi"].GPIO = s
        b = hal.DeviceButtons()
        b._gpio = s
        return b.pressed()

    # 1. Each control on its own reports itself.
    wanted = {"u": "u", "d": "d", "l": "l", "r": "r", "press": "p",
              "a": "a", "b": "b", "c": "c"}
    wrong = {n: press([n]) for n in wanted if press([n]) != wanted[n]}
    if not wrong:
        ok(f"all {len(wanted)} controls report themselves")
    else:
        bad(f"controls misread: {wrong}")

    # 2. THE BUG. A centre press that also closes a direction is a press.
    for direction in ("u", "d", "l", "r"):
        got = press(["press", direction])
        if got != "p":
            bad(f"centre press with {direction} also closed reported {got!r}")
            break
    else:
        ok("a centre press beats a direction closed by the same movement")

    # 3. The action keys beat a direction too, for the same reason.
    if press(["a", "u"]) == "a" and press(["c", "d"]) == "c":
        ok("A and C beat a direction as well")
    else:
        bad("an action key lost to a direction")

    # 4. Nothing pressed is None, so the polling loops stay responsive.
    if press([]) is None:
        ok("nothing pressed reports None")
    else:
        bad("an idle keypad reported a press")

    # 5. One press is one event: the reader waits for EVERY contact to
    #    open, so a direction still held does not fire again immediately.
    s = FakeGPIO()
    s.state = {PINS["press"]: LOW, PINS["u"]: LOW}
    s.release_after = 6          # both open after a few reads
    sys.modules["RPi.GPIO"] = s
    sys.modules["RPi"].GPIO = s
    b = hal.DeviceButtons()
    b._gpio = s
    first = b.pressed()
    second = b.pressed()
    if first == "p" and second is None:
        ok("one press gives one event, with nothing left over")
    else:
        bad(f"a held direction fired again: {first!r} then {second!r}")

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
