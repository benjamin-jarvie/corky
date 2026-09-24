"""Break each claim on purpose. A check that was meant to catch it must fail.

TESTING.md rule 12a: clear __pycache__ around every run, and judge by the
EXIT CODE, not by counting FAIL lines. A mutation that crashes a suite
prints no FAIL line, and a runner that greps for one calls that survived.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITES = ["tests/test_backup_check.py", "tests/test_screen_fit.py",
          "tests/test_ui_cost.py", "tests/test_typing_uniform.py",
          "tests/test_pins.py"]

#: (name, file, find, replace) — each must match exactly once.
MUTATIONS = [
 ("red marks untyped positions again (Ben, 2026-09-19)",
  "coresigner/main.py",
  "    return {n for n, ch in enumerate(typed)\n"
  "            if ch != \" \" and (n >= len(want) or ch != want[n])}",
  "    return ({n for n, ch in enumerate(typed)\n"
  "             if ch != \" \" and (n >= len(want) or ch != want[n])}\n"
  "            | set(range(len(typed), len(want))))"),

 ("a wrong character no longer stops you moving on (C1)",
  "coresigner/main.py",
  "                elif wrong:\n", "                elif False:\n"),

 ("the device stops putting the right character in (C1)",
  "coresigner/main.py",
  "        return typed[:at] + want[at] + typed[at + 1:], min(at + 1,",
  "        return typed, min(at + 1,"),

 ("corrections are no longer recorded (C2)",
  "coresigner/main.py",
  "        made.append((box, char, want[at]))\n", "        pass\n"),

 ("the list stops saying what the character should be (Ben, 2026-09-23)",
  "coresigner/main.py",
  "        made.append((box, char, want[at]))",
  "        made.append((box, char, \"?\"))"),

 ("RECHECK asks for the whole key instead of the corrected boxes",
  "coresigner/main.py",
  '        want = "".join(key_text[(b - 1) * 4:(b - 1) * 4 + 4] for b in boxes)',
  "        want = key_text"),

 ("the typing boxes stop at 12 again (the bug, 3 reports)",
  "coresigner/screens.py",
  "    groups = _groups(padded) or [\"\"]",
  "    groups = (_groups(padded) or [\"\"])[:12]"),

 ("DONE finishes a key that is not finished (C6)",
  "coresigner/main.py",
  "                    if \" \" in typed or len(typed) < len(want):\n",
  "                    if False:\n"),

 ("CHECK IT stops being the default after a backup (Ben, 2026-09-19)",
  "coresigner/main.py",
  "        i, sel = 0, 1\n", "        i, sel = 0, 0\n"),

 ("the bar is marked while the grid has the focus (Ben, 2026-09-19)",
  "coresigner/screens.py",
  "        active = selected is not None and i == selected",
  "        active = i == (selected if selected is not None else 1)"),

 ("the paper stops numbering its boxes (C7)",
  "coresigner/screens.py",
  "            _fit(d, (x + num_w, y), str(first + row_start + i), size,\n"
  "                 GREY, \"rm\", num_w)\n", "            pass\n"),

 ("a screen sentence goes back to lower case (C5)",
  "coresigner/screens.py",
  '"Write this down. It opens the wallet"',
  '"write this down. it opens the wallet"'),

 ("the recheck lets you type over a character already right",
  "coresigner/main.py",
  "    if not ask:\n        return max(0, min(length, caret + direction))",
  "    if True:\n        return max(0, min(length, caret + direction))"),

 ("the recheck asks for whole boxes again, not the wrong characters",
  "coresigner/main.py",
  '        typed = "".join(" " if n in ask else ch\n'
  '                        for n, ch in enumerate(want))',
  '        typed = ""'),

 ("a pinned package loses its hash (test_pins)",
  "image/PINS",
  "libzbar0t64_0.23.93-8_arm64.deb 86bf2db996e828f87d2ab94509cd0b4fbc097e57e8976cb6142ee541b2638787 121644",
  "libzbar0t64_0.23.93-8_arm64.deb NOTAHASH 121644"),

 # NAVIGATION. tests/e2e_keys.py computes its routes by calling
 # _cell_move, so the round trip cannot disagree with it: a wrong rule
 # walks the script and the device identically and every session still
 # passes. TESTING.md rule 2 says a helper must not share the code's
 # assumptions, and the answer here is not to re-derive the rules a
 # third time, which is what went wrong three times; it is that
 # test_ui_cost pins _cell_move's PROPERTIES independently. These two
 # mutations are what make that claim checkable rather than asserted
 # (two-axis review, 2026-09-23).
 ("LEFT stops walking the whole grid (Ben, 2026-09-18)",
  "coresigner/main.py",
  '    if key == "l":\n        return (cur - 1) % len(cells)',
  '    if key == "l":\n        return cur if cur == 0 else cur - 1'),

 ("UP stops coming round to the bottom (Ben, 2026-09-18)",
  "coresigner/main.py",
  "        nxt = (row + (1 if key == \"d\" else -1)) % rows",
  "        nxt = max(0, row + (1 if key == \"d\" else -1))"),

 ("provision.sh installs from the index again (test_pins)",
  "image/provision.sh",
  "dpkg -i \"$DEB_CACHE\"/*.deb || {",
  "apt-get install -y -qq python3-pil || {"),
]


def clear_cache():
    subprocess.run(["find", ".", "-name", "__pycache__", "-type", "d",
                    "-not", "-path", "*/.build/*", "-exec", "rm", "-rf",
                    "{}", "+"], cwd=ROOT, capture_output=True)


def run_suites():
    """True when SOMETHING failed. Exit code first, FAIL line second."""
    for suite in SUITES:
        r = subprocess.run(["arch", "-arm64", "python3", suite], cwd=ROOT,
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or "\nFAIL" in r.stdout:
            return True, f"{suite} exit {r.returncode}"
    return False, "every suite passed"


caught, survived, skipped = [], [], []
for name, rel, find, repl in MUTATIONS:
    path = ROOT / rel
    original = path.read_text()
    n = original.count(find)
    if n != 1:
        skipped.append(name)
        print(f"SKIP  {name}\n      anchor matched {n} times, not 1. "
              "The code moved under this mutation and it now tests "
              "nothing.")
        continue
    path.write_text(original.replace(find, repl, 1))
    clear_cache()
    try:
        failed, why = run_suites()
    finally:
        path.write_text(original)
        clear_cache()
    if failed:
        caught.append(name)
        print(f"caught   {name}\n         by {why}")
    else:
        survived.append(name)
        print(f"SURVIVED {name}\n         {why}")

print(f"\n{len(caught)} caught, {len(survived)} survived, "
      f"{len(skipped)} did not apply")
for s in survived:
    print(f"  survivor: {s}")
for s in skipped:
    print(f"  did not apply: {s}")
# A skip is a failure. It is the same hole TESTING.md rule 12a names in
# its other half: a run that reports success for a mutation nothing ran.
sys.exit(1 if survived or skipped else 0)
