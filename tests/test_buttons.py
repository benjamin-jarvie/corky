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
import threading
import time
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

    # 6. A contact that never opens is ignored, not waited on.
    #    The old wait had no bound, so a shorted or jammed button held the
    #    loop for ever and the device looked crashed while every other
    #    control still worked underneath (audit A1, 2026-09-06).
    jam = FakeGPIO()
    jam.state = {PINS["u"]: LOW}      # never released: release_after None
    sys.modules["RPi.GPIO"] = jam
    sys.modules["RPi"].GPIO = jam
    b = hal.DeviceButtons()
    b._gpio = jam
    b.STUCK_AFTER = 0.05             # do not make the suite wait 3 seconds

    t0 = time.monotonic()
    first = b.pressed()
    took = time.monotonic() - t0
    if took > 1.0:
        bad(f"a jammed contact held pressed() for {took:.1f}s")
    elif first is not None:
        bad(f"a jammed contact reported {first!r} as a press. It never "
            "opened, so it was never a press.")
    else:
        ok(f"a jammed contact reports nothing, in {took * 1000:.0f}ms, "
           "instead of hanging or firing a phantom press")

    # And it stays quiet rather than firing every time it is polled.
    if b.pressed() is not None:
        bad("a jammed contact kept firing after it was seen to be stuck")
    else:
        ok("a jammed contact is ignored once it is known to be stuck")

    # An INTERMITTENT contact is the common fault, and the first version of
    # this fix fired a phantom press on every close (devil's advocate,
    # 2026-09-06).
    flapper = hal.DeviceButtons()
    flapper._gpio = jam
    flapper.STUCK_AFTER = 0.05
    fired = []
    for _ in range(3):
        jam.state = {PINS["u"]: LOW}
        fired.append(flapper.pressed())
        jam.state = {}
        flapper.pressed()             # the read that notices it went high
    if any(f is not None for f in fired):
        bad(f"an intermittent contact fired phantom presses: {fired}")
    else:
        ok("an intermittent contact fires no phantom presses")

    # A healthy button, pressed and RELEASED normally, still works with a
    # contact jammed beside it. Released, because a press that is never
    # released is what "jammed" means.
    jam.state = {PINS["u"]: LOW}
    b.pressed()                       # re-learn the jam
    jam.state = {PINS["u"]: LOW, PINS["a"]: LOW}
    threading.Timer(0.02,
                    lambda: jam.state.__setitem__(PINS["a"], HIGH)).start()
    if b.pressed() != "a":
        bad("a jammed contact blocked a healthy one")
    else:
        ok("other controls keep working with one contact jammed")

    # A deliberate hold shorter than the deadline is still one press. This
    # is the property the deadline could have eaten.
    hold = hal.DeviceButtons()
    hold._gpio = jam
    hold.STUCK_AFTER = 0.30
    jam.state = {PINS["u"]: LOW}      # learn the jam with ONLY u down, or
    hold.pressed()                    # b gets marked stuck along with it
    jam.state = {PINS["u"]: LOW, PINS["b"]: LOW}
    threading.Timer(0.15,
                    lambda: jam.state.__setitem__(PINS["b"], HIGH)).start()
    if hold.pressed() != "b":
        bad("a 150ms hold against a 300ms deadline was not reported")
    else:
        ok("a deliberate hold shorter than the deadline is still one press")

    # A pin that recovers is admitted again.
    jam.state = {}
    b.pressed()                       # the read that notices it went high
    jam.state = {PINS["u"]: LOW}
    # The fake counts reads cumulatively, so its counter has to go back to
    # zero or release_after is already past and every read returns HIGH.
    jam.reads = 0
    jam.release_after = 12
    if b.pressed() != "u":
        bad("a recovered contact was not admitted again")
    else:
        ok("a contact that starts working again is admitted again")

    # 7. read() blocks until something is pressed. It had never executed
    #    (audit A5, 2026-09-06): every test drives pressed() directly, so
    #    the loop the DEVICE actually sits in was never entered.
    # Driven by READ COUNT, not by a timer. A first version raced: it
    # cleared the pin 20ms after pressing it while read() polls every 20ms,
    # so about one run in twelve missed the window and spun (devil's
    # advocate on A5, 2026-09-06). Counting reads is deterministic, and it
    # keeps the check in this process rather than a thread that can leak.
    class Waiter(FakeGPIO):
        """High until asked often enough, then C, then high again."""

        def __init__(self):
            super().__init__()
            self.polls = 0

        def input(self, pin):
            self.polls += 1
            if 30 <= self.polls < 40 and pin == PINS["c"]:
                return LOW
            return HIGH

    waiter = Waiter()
    sys.modules["RPi.GPIO"] = waiter
    sys.modules["RPi"].GPIO = waiter
    rb = hal.DeviceButtons()
    rb._gpio = waiter
    rb.STUCK_AFTER = 2.0
    before = waiter.polls
    got = rb.read()
    if got != "c":
        bad(f"read() returned {got!r}, expected 'c'")
    elif waiter.polls - before < 30:
        bad(f"read() returned after {waiter.polls - before} polls without "
            "waiting for anything to be pressed")
    else:
        ok(f"read() waits through {waiter.polls - before} polls, then "
           "returns the press")

    print()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
