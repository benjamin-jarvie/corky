# Proving the optics

**Status: NOT DONE.** This is item 3 of the
[A11 verdict](wayfinder/beta-audit/tickets/A11-the-verdict.md) and the
oldest open issue, E-4. It is the last thing standing between a
supervised pilot and a tester holding a device.

A signer whose QR a coordinator cannot read is not a signer. Sparrow's
**library** is proven to exhaustion: 197 checks drive its own decoder out
of its verified release. A lens is not a library. Nobody has pointed a
camera at this panel.

Run this BEFORE `image/harden.sh`. Hardening takes SSH with it, and
every diagnosis below is easier with a shell.

## What is already covered, and what is not

| direction | who reads | covered by |
|---|---|---|
| inbound, the device reads a coordinator's QR | Core Signer's camera | `tests/hw_camera.py`, scripted |
| **outbound, a coordinator reads the panel** | **a phone or webcam** | **nothing** |

`tests/sparrow/` proves the outbound BYTES are correct and that zxing
decodes the rendered image. What it cannot prove is that a real lens, in
real light, at a real distance, resolves the panel.

## Setup

Board on the desk, running, SSH still alive. Sparrow on the laptop. One
phone wallet. Room light as a person would actually use, not a lamp
aimed at the screen.

## Part A. Inbound, scripted

    ssh corky-ip
    sudo python3 /opt/coresigner/tests/hw_camera.py --seconds 90

Paints the viewfinder on the LCD and names every QR it decodes. Show it
a PSBT QR from Sparrow. **Pass:** it decodes within a few seconds of
being aimed, without a tripod.

## Part B. Outbound, single-sig

On the device: **Export public key** -> pick a policy -> **QR code**.
The screen cycles all eight mask patterns at 0.3s. Hold each coordinator
in front of it as a person would.

Do all four policies. Native segwit and Taproot are what most people
use; Nested segwit is the awkward one at 61 modules against the others'
57.

## Part C. Outbound, multisig. NEW, and the bigger ask

Multisig is in the pilot, so this is not optional.

On the device: **Export public key** -> **Cosigner (P2WSH)** -> **QR
code**. That payload is a whole descriptor,
`wsh(sortedmulti(1,[xfp/48h/1h/0h/2h]tpub...))#checksum`, **167
characters against a single-sig 148**. A longer string is a denser code,
so this is the hardest thing the panel has to show.

Then **Advanced -> Type a path...** and enter a three-level blinded path
such as `607137099h/1711870460h/1965312408h`. Check the checksum echo,
then export its QR. That is the longest payload the device can produce.

In Sparrow: a 2-of-3 P2WSH wallet, keystore -> **Airgapped Hardware
Wallet** -> **Specter DIY** -> **Scan...**.

## Record the result here

| # | what | coordinator | read? | notes |
|---|---|---|---|---|
| A | inbound PSBT | Core Signer's camera | | |
| B1 | Native segwit | Sparrow | | |
| B2 | Taproot | Sparrow | | |
| B3 | Nested segwit | Sparrow | | |
| B4 | Native segwit | phone | | |
| C1 | Cosigner P2WSH, 167 chars | Sparrow | | |
| C2 | Blinded path, longest | Sparrow | | |
| C3 | Cosigner P2WSH | phone | | |

## What counts as a pass

**Read within one mask cycle, 2.4 seconds, held by hand at a comfortable
distance.** Not "reads if you brace it against a book for a minute".

A miss costs a cycle and the panel loops, so one slow read is survivable
and a consistent failure is not. If a row fails, say which mask was on
screen if you can see it, and keep the descriptor: `tests/sparrow/
test_export_interop.py` has a pinned corpus for exactly this and a real
failure belongs in it.

## If C fails and B passes

Then the cosigner QR is too dense for this panel and the answer is the
file channel, not the camera. `signer.write_cosigner` already writes the
one-liner to a stick or the card, and M8 measured that Sparrow's Specter
DIY importer reads it. Say so and the pilot ships the file route for
multisig.
