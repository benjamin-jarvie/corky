# A5 What has never run, on anything

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A1, because coverage of an unread module is a number nobody can read.

## Question

TESTING.md rule 3: if a branch exists only for the device, a test must set
the flag and run it. Rule 7: "needs hardware" is a claim that needs
checking.

Find the code that has never executed. Not by reading: by measuring.
Instrument a full suite run and list every function and branch in `coresigner/`
that no test reaches, then sort them into three piles:

- reachable in a test and simply untested;
- reachable only on the device, and therefore rule 3's problem;
- unreachable at all, and therefore dead.

The third pile is the interesting one. `vulture` finds unused names; it
does not find a live function whose second branch nobody has entered.

---

## Answer (2026-09-06)

Measured, not read. `tools/coverage_run.sh` runs every suite with
coverage's subprocess hook, because most of Core Signer runs in a child
process (`python3 coresigner/main.py --dev ...` under `subprocess.run`); a
plain `coverage run` sees none of it. `tools/coverage_piles.py` sorts
what is left into the three piles and **asserts that every uncovered
line falls in exactly one of them**, so the classification has no gap.
Both are in the repo, so the numbers below can be reproduced.

### The number

**86%** of statements in `coresigner/`, 224 never executed out of 1,956.

That is the union of two architectures. The arm64 suites alone report
**84%**, and the gap is not rounding: `libzbar` on this Mac is x86_64
only, so `pyzbar` cannot load under arm64, and the whole QR decode path
(`qrchannel.decode_image`, `ImageQrSource.strings`) is unreachable in
the main suite. It is covered, under Rosetta, by `tests/m1`. A
measurement that quietly omits the QR decoder is not a measurement of
Core Signer, so `coverage_run.sh` now runs that suite too and says so when the
Rosetta build is missing.

### The three piles

| pile | statements | what it is |
|---|---|---|
| 1 | 205 | reachable in a test, simply untested |
| 2 | 18 | reachable only on the device |
| 3 | **1** | unreachable at all |

By file: `main.py` 151/12/1, `screens.py` 30/0/0, `qrchannel.py`
12/0/0, `signer.py` 11/0/0, `hal.py` 1/6/0.

### Pile 3, which is the one the ticket wanted

One statement. `coresigner/main.py:113`:

```python
class ImageQrSource:
    def images(self):
        raise NotImplementedError
```

Nothing instantiates `ImageQrSource`, and its only subclass,
`CameraQrSource`, overrides `images()`. So the line cannot run in any
configuration Core Signer ships or tests. It stays, because it is the contract
that makes `strings()` safe to inherit, and a future source that forgets
to override would otherwise fail somewhere less obvious. It is a guard,
and it is correctly the only one.

`vulture` finds none of this, which is what the ticket predicted: it
looks for unused names, and `images` is used on every frame.

### Pile 2 is small, and it got smaller under checking

18 statements, all of them naming a device the Mac does not have:

- `hal.py:56-60,76` the ST7789 panel over SPI;
- `main.py:167-171,178-184` picamera2 opening and reading the camera;
- `main.py:1775-1777` the branch that builds those three for real.

Rule 7 says "needs hardware" is a claim that needs checking, and two
claims did not survive it:

- `filechannel.py:131-132`, the guard for a filesystem that refuses
  `fsync` on a **directory**, which is what a FAT32 stick does. The only
  thing needing the board was one syscall, so the syscall is now faked,
  as `EINVAL` rather than as a convenient generic error. `filechannel.py`
  is at 100%.
- `splash.py:27`. This one was never uncovered at all. `test_splash.py`
  runs the program end to end, but builds the child's environment from
  scratch, which drops `COVERAGE_PROCESS_START` along with everything
  else. The instrument was reporting the first thing the device runs as
  dead code while the suite was running it. Fixed by passing the two
  coverage variables through, and nothing else, so check 1's point (that
  splash needs almost nothing) still holds. `splash.py` is at 100%.

That is rule 4 in its own right: a metric that counts wrongly is worse
than no metric, and this one was counting a whole program wrongly.

### Pile 1, and the four gaps worth fixing before beta

205 statements. Most are error and cancel paths, which matter but fail
safe. Four did not, and are now covered:

1. **The LEFT/RIGHT policy walk on the address screen.** `_next_kind`
   was called by exactly one line in the codebase, and that line had
   never run. This is the walk that reaches a legacy or nested address
   after the chooser was taken off the front of the screen (Ben,
   2026-09-05), so all four policies existed but three were unreachable
   in any test. Session **K12** now walks the whole ring and back,
   asserting each policy's own first address against Core. Two mutations
   of `_next_kind` die.
2. **Check an address.** The entire Tools feature was uncovered, and the
   first attempt at session K11 could not work: one `--qr-key` file held
   one code, so the session scanned the address AS the key and never
   reached a verdict. `DevQrSource` now hands out one code per scan.
   K11 asserts both verdicts; making `ismine` always true, or always
   false, kills it.
3. **The refusal path.** `signer.py:444` sets `complete_inputs = False`
   when an input carries neither a `witness_utxo` nor the previous
   transaction, which is what makes the device print "PSBT lacks input
   data; fee unknown; refused". It had never executed. `createpsbt`
   builds that shape, and check **1d** now asserts no total and no fee.
4. **The legacy input amount**, check 1c, which existed but could not
   fail: it compared `describe_psbt`'s fee to `decodepsbt`'s fee, and
   `describe_psbt` returns `decodepsbt`'s fee. It now derives the
   expected total from the node's UTXO set with `gettxout`, so a wrong
   prevout index shows up. Mutating the index makes it read 47.99998530
   BTC where the chain says 2.00000000.

The classifier lists the rest region by region. The largest remaining
group is `main.py`'s cancel and back keys inside the entry screens
(`1041-1063`, `1408-1436`), which `tests/test_ui_cost.py` models but no
session presses.

---

## Re-measured 2026-09-08

The answer above is left as it was written. Its line numbers are of the
tree measured on 2026-09-06, and `main.py` has been restructured since,
so quoting them at today's file would be wrong in a way that reads as
right.

The classifier itself carried that defect. It pinned line numbers, and
two of its pins had slid: `main.py:266` onto a comment, `main.py:1138`
onto a blank line. It asserted that every uncovered line falls in a
range, which catches a line arriving. It never asked whether a range
still holds a line, which is what catches one leaving. So the pile
totals could only ever shrink, silently, and the table above is the
number they shrank from.

It keys on **function names** now. A name survives every edit inside the
function and breaks loudly on a rename, which is the alarm that was
missing. Both directions are asserted, and `run_tests.sh` checks the
cheap half (that every named function exists) on every run.

Today's figures, from the same two-architecture run:

**86%** of statements in `coresigner/`, **222 never executed out of 2,028**,
across **61 functions**.

| pile | statements | what it is |
|---|---|---|
| 1 | 202 | reachable in a test, simply untested |
| 2 | 19 | reachable only on the device |
| 3 | **1** | unreachable at all |

By file: `main.py` 146/12/1, `screens.py` 31/0/0, `signer.py` 13/0/0,
`qrchannel.py` 12/0/0, `hal.py` 0/7/0, `filechannel.py` and `splash.py`
at 100%.

Pile 3 is still the single `raise NotImplementedError` in
`ImageQrSource.images`, for the reason given above. Pile 2 gained one
statement, `hal.py`'s stuck-key `break`, which needs GPIO. The
conclusions of the 2026-09-06 answer stand; only the arithmetic moved.
