# N2 Say when the card can safely come out

Type: `wayfinder:prototype`. **Open. Blocked by N1.**

## Question

SeedSigner tells you when its OS is in RAM and the card is no longer
needed. Corky must do the same, because a user who pulls the card at the
wrong moment on a device that has not finished reading it gets a corrupt
card and no warning.

To decide, once N1 makes it possible:

- Where the message appears. At boot, once, as a screen you dismiss? Or as
  a state the home screen carries, so it is true whenever it is shown?
- What it says when the card is still needed, which is the more dangerous
  half. Silence is what a user reads as permission.
- Whether the device notices the card leaving and returning, and whether
  the screen changes when it does.
- What happens to a file operation that is running when the card goes.
