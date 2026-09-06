# A1 Read the four modules nothing has read

Type: `wayfinder:task`, AFK. **Closed 2026-09-06. Blocks A3, A5, A6.**

**Blocked by:** Nothing. Takeable now.

## Question

617 lines ship on the device that no review in this project has opened:

| module | lines | what it carries |
|---|---|---|
| `qrchannel.py` | 361 | every byte in and out by camera and panel |
| `filechannel.py` | 110 | every byte in and out by stick or card |
| `hal.py` | 119 | the display and the buttons |
| `splash.py` | 27 | the first frame |

The two-axis review reads a diff, and these were not in it. The design
pass named them and did not open them either.

Read them against the same standards the review applies: PLAN's
amendments as laws, TESTING.md's rules, CONTEXT.md's vocabulary, and the
layer model. Report per module: what its interface is, whether anything in
it touches key material, what it does when its input is hostile or absent,
and what has never been executed.

Not a rewrite. The output is findings with line numbers, each reproduced
before it is written down.


## Answer

Four modules read end to end. Three defects, two of them real bugs, one of
them mine. A devil's advocate pass afterwards demolished three of my first
four claims, which is recorded below because it is the more useful half.

### Defects found and fixed

**A jammed button hung the device for ever.** `DeviceButtons.pressed()`
waited for every contact to open with no bound, so a shorted or physically
jammed control held the loop while every other button still worked
underneath. In a sealed enclosure that reads as a crash. It now gives up
after `STUCK_AFTER`, ignores the pin until it reads high again, and pays
that cost once rather than per press.

**The size cap on a PSBT file could be beaten.** `read_psbt` called
`stat()`, then `read_bytes()`, and the stick is shared with the
coordinator, which is the whole reason `wait_stable` exists. A 1KB file
grown in that gap was read at **6MB against a 4MB cap**, reproduced. The
cap is now on the read itself: one byte past the limit is fetched and
refused, so there is no window.

**The file channel's safety rested on a decision in another file.**
`find_unsigned` trusts a filename off a stick and calls `is_file()`, which
follows symlinks. It is safe only because `image/corky-usb@.service`
mounts `-t vfat,exfat`, neither of which has symlinks. Neither file
mentioned the other. Both do now, and a test fails if the mount admits a
filesystem that does.

### What the devil's advocate demolished, and it was right

- **My first fix fired a phantom keypress.** A jammed contact returned its
  own key before being marked stuck, and an intermittent one, which is the
  common fault, fired a fresh phantom every time it closed. A key that
  never opens was never a press; it now returns nothing.
- **My flood test measured nothing.** 20,000 random frames, and NOT ONE
  reached the accumulator: random bytewords fail their CRC inside the
  vendored decoder. Rebuilt with valid frames from our own encoder, two
  transactions interleaved, 36,800 frames leaving 23 parts held.
- **My memory measure was a high-water mark.** `ru_maxrss` never falls, so
  "grew 0.0MB" was honest by luck with 0.2MB of headroom. Replaced by
  counting the decoder's own held parts, which is exact and portable.
- **My past-the-gate test passed with the guard deleted**, because the
  vendored decoder has a bare except. It now claims only what it proves:
  that ur2 contains those frames, which is ur2's property and not ours.

### Answered per module

**Key material.** None of the four transforms it. `hal.DeviceDisplay.show`
accepts `sensitive` and ignores it, and that asymmetry is a security
property nobody had written down: the dev display blanks because it writes
PNGs to a disk, the device display does not because a backup you cannot
see is not a backup. So the only place key material may be drawn is the
one place it cannot be kept.

**Hostile input.** The QR channel holds: frames past the guard are
contained by the vendored decoder, and accumulation is bounded. The file
channel had the cap bug above. `hal` and `splash` take no external input.

**Never executed.** `splash.py` had no test and was in no suite, and it is
the first thing the device runs. It has one now, including a check that it
still imports none of the signing stack, which is the claim its own
docstring makes. The rest of the never-executed question is A5's, with one
finding handed over: the QR checks in `test_adversarial.py` only run with
`RUN_NODE=1`, so a contributor running the fast suites never exercises
them.
