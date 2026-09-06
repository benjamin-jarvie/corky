# A2 Does the layer model actually hold, end to end

Type: `wayfinder:task`, AFK. **Closed 2026-09-06.**

**Blocked by:** Nothing. Takeable now.

## Question

The whole trust argument is three sentences: Layer 1 transforms secrets
and is zero lines; Layer 2 sees secrets and computes nothing on them;
Layer 3 never touches them. `tests/test_integrity.py` enforces the import
allowlist, and `tests/test_generate.py` enforces the no-RNG rule.

Nothing enforces the middle sentence. "Computes nothing on them" is a
claim about what Layer 2 DOES with a key, and it is checked by reading.

On 2026-09-05 a Layer 2 function put a private key on the command line for
several hours, and a two-axis review found it rather than a test. That is
one failure of the claim. This ticket asks whether there are others.

Trace every path a key takes, from the moment it enters to the moment it
is dropped, and at each step name what holds it, for how long, and what is
done to it. Then say which of those steps a test would catch a change to.

The README publishes the answer as "two moments". Prove the number or
correct it.


## Answer

**The model holds. The published account of it did not.** Three findings,
two of them leaks, and a devil's advocate then found that half my first
answer was wrong, which is recorded below because it is the useful half.

### The trace

A key exists in Python at four points and no others.

1. **Entering.** `_key_by_scan` or `_key_xprv_typed` produce a string;
   `open_session_xprv` hands it to `build_descriptors`, which builds eight
   descriptor strings around it, and `_import` sends those to Core through
   `-stdin`. Alive for the length of one import.
2. **Generated.** `generate_wallet` returns a wallet NAME. The key never
   enters Python at all. This is the only path with no exposure.
3. **On the way to paper.** `master_xprv` slices it out of Core's private
   descriptors. Alive from there until `_backup_paper` returns.
4. **Through a check.** `_verify_backup` holds it for the whole of a 594
   press comparison, plus a typed copy accumulating beside it.

Points 3 and 4 are the same reference: `xprv` in `_backup_paper` is live
across both the write-down and the check. The README called that a moment.
It is five to ten minutes.

### Leaks found and fixed

**Scanning a key photographed it onto a developer's disk.** The viewfinder
is a frame like any other, and `hal.DevDisplay` writes every frame it is
not told to blank. A key scan points a lens at a key, and that frame was
unmarked, so the dev harness saved a picture of one. Marked now. The
transaction viewfinder stays unmarked on purpose and the reason is in the
code.

**A mistyped WIF reached the panel and the journal in full.** `redact`
matched the six extended-private-key prefixes, and a WIF has no
word-shaped prefix at all. Core echoes what it refuses: `key
'cVjzvdHG…' is not valid`. Reproduced against Core, fixed, and pinned
against over-matching an address, a checksum or an xpub.

**Nothing tested the property that stops any of this.** Six call sites
pass `sensitive=True` and until now one was covered, incidentally. A
mutation sweep flipping each flag to False now catches **six of six**.

### What the devil's advocate demolished

- My first sensitive test was **vacuous for two of its four cases**: a
  script of twenty presses never leaves the entry screen, so the verdict
  was never painted and the same frames were counted twice. It also
  invented an argument the real caller does not pass.
- It then over-corrected: demanding every frame in the key-scan flow be
  marked failed on the warning and busy screens, which carry no key. Only
  the viewfinder frames are checked now.
- **The heap figure in the README was wrong.** It said 111 live objects
  holding 6,216 characters. Instrumenting the screen shows about ten alive
  at once; CPython frees each on rebind. The correction matters less than
  it sounds, because the freed bytes are not zeroed, and that is now what
  the README says.
- The five-to-ten minutes is arithmetic from a press count, not a
  stopwatch, and the README says so rather than claiming a measurement.

### Still open, handed on

Nothing verifies "Layer 1 is zero lines" or "Layer 2 computes nothing"
directly. The first is enforced by an import allowlist, which is a proxy;
the second is enforced by reading, which is what missed the key on the
command line. A6 owns whether that is testable at all.
