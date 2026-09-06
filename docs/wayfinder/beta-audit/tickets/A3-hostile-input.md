# A3 What a hostile QR, file or card can make the device do

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A1, which says what the channels do before this asks what breaks them.

## Question

Everything reaching this device comes from somewhere else: a QR held up
to the camera, a file on a stick, a card in the slot. The stated defence
is PLAN A-11, that Corky treats key material as opaque bytes and only
Bitcoin Core parses.

That is a claim about the payload. It says nothing about the envelope,
and the envelope is parsed by us: UR frames, fountain parts, filenames,
file sizes, the mount itself.

For each channel, answer with a test rather than a paragraph:

- what a malformed frame, a huge frame, a truncated file, an empty file,
  a filename with a path in it, and a filesystem that lies about its size
  each make the device do;
- whether any of them can make it write outside its channel, hang with no
  way out, or show something misleading;
- `tests/test_adversarial.py` has 28 checks already. Which of the above
  does it not cover?

The mount is new since the last adversarial pass and has never been fed
anything hostile.
