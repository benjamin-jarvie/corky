# 17 Load, review and signing errors are held on screen

Labels: wayfinder:task (AFK)
Blocked by: none
Status: resolved 2026-09-05

## Question

ISSUES.md D18, open since the 2026-08-18 audit: `state_load` does not catch
`FileChannelError` or filesystem errors, and `state_review` does not catch
RPC failures. They unwind the process, and with `Restart=on-failure` a bad
file on the stick restart-loops the service until the file is removed. A
tester will hit this in the first hour.

Catch them, paint a held error with Core's message, return to the Key menu.
Also D17: teardown failures are silent; report them on the power-off path.

Tests: a garbage `.psbt` on a temp stick, an RPC that raises during review,
both end on the error screen with the process alive.

## Answer (built, 2026-09-05)

Sessions K7 and K8 in `tests/e2e_keys.py`, both driving the real device
process with a real bad file on a real stick directory.

**D18.** `_sign_loop` now catches a named set: `RuntimeError`, `OSError`,
`FileChannelError` and `QrChannelError`. Named rather than blanket, so a
genuine defect still crashes loudly in the tests instead of being painted
as a message. The same set replaces the bare `RuntimeError` catch around
the home tiles.

Why it matters more than one bad screen: `corky.service` carries
`Restart=on-failure`, so an exception here is a restart loop that lasts as
long as the file is on the stick.

**A worse defect found while testing it.** An empty `.psbt` file was
invisible. `wait_stable` required `size > 0`, so a zero-byte file was never
stable, never read, and never refused: the device sat on "insert the
stick…" for ever with the file already in front of it, and said nothing.
`wait_stable` now answers the question it is named for, whether the file is
still being written, and `read_psbt` refuses an empty file by size with a
message that names it. `_load_by_stick` paints that reason and keeps
waiting, remembering the file by name and size so it reports once, stays
responsive to the buttons, and tries again if the file is replaced.

**D17.** A teardown that fails is a key still in the node on a device whose
next screen says it is off. `Session.run` no longer discards that
exception; it holds "key not cleared" with the reason.

`tests/test_filechannel.py` changed with the contract it tests: an empty
file is stable, and refused by `read_psbt` with its name and size.
