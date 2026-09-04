"""Interactive GPIO check. RUN ON THE BOARD, with the hat fitted.

    sudo python3 tests/hw_buttons.py

hal.DeviceButtons carries a pin map lifted from SeedSigner (hw/HARDWARE.md,
BOARD numbering) that had never touched a real GPIO. This rig walks every
control in turn, prompts on the panel, and reports what actually fired
against what was asked for. A swapped pair shows up as a mismatch rather
than as a confusing UI six weeks later.

The prompts go on the LCD, not the terminal, because the operator is looking
at the device and pressing its buttons.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))

import hal        # noqa: E402
import screens    # noqa: E402

# Asked for in this order. The label is what the operator reads on screen.
CONTROLS = [
    ("u", "JOYSTICK UP"),
    ("d", "JOYSTICK DOWN"),
    ("l", "JOYSTICK LEFT"),
    ("r", "JOYSTICK RIGHT"),
    ("p", "JOYSTICK PRESS (push it in)"),
    ("a", "KEY1  (top)"),
    ("b", "KEY2  (middle)"),
    ("c", "KEY3  (bottom)"),
]


def main():
    display = hal.DeviceDisplay()
    buttons = hal.DeviceButtons()
    w, h = display.width, display.height
    print(f"panel {w}x{h}, pins {buttons.PINS}")
    print("Follow the prompts on the screen. Ctrl-C to stop.\n")

    results = []
    for want, label in CONTROLS:
        display.show(screens.busy(w, h, message=f"press {label}"))
        t0 = time.time()
        got = buttons.read()
        dt = time.time() - t0
        ok = got == want
        results.append((label, want, got, ok))
        print(f"{'ok  ' if ok else 'MISMATCH'} {label:<28} "
              f"asked {want!r}, got {got!r}   ({dt:.1f}s)")

    bad = [r for r in results if not r[3]]
    display.show(screens.busy(
        w, h, message="all 8 controls correct" if not bad
        else f"{len(bad)} control(s) wrong"))

    print("\n" + "=" * 60)
    if bad:
        print(f"{len(bad)} of {len(CONTROLS)} controls did not match the map:")
        for label, want, got, _ in bad:
            print(f"  {label}: expected {want!r}, the board sent {got!r}")
        print("\nhal.DeviceButtons.PINS needs correcting, "
              "and so does hw/HARDWARE.md.")
        return 1
    print(f"PASS  all {len(CONTROLS)} controls match hal.DeviceButtons.PINS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\naborted")
        sys.exit(2)
