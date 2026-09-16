# Core Signer: what a pilot tester is given, and told

Draft, 2026-09-16. Ben approves the wording before anybody gets a device.

This exists because a beta that hides its own limits is not a beta. Every
number here was measured on the board a tester will hold, and the file
that measured it is named so you can re-run it.

---

## In one paragraph

Core Signer is a Bitcoin signer that holds nothing. Your key lives in the
memory of a Raspberry Pi with no network, and it is gone the moment the
power goes. It signs transactions your own wallet software builds, and it
gives them back. It is not a wallet: it has no idea what you own.

## The one thing that will lose your coins

**The paper backup is the only backup.**

111 characters, written by hand, on paper. There is no file, no
encryption, no cloud, no second copy, and no way for us to help you. Pull
the power before you have written it down and the coins are gone.

Write it down. Use the VERIFY step, which types it back in and asks
Bitcoin Core whether it opens the same wallet. Then keep the paper the
way you would keep the coins, because it **is** the coins.

This is deliberate. PLAN A-24.

## Only two programs can open that backup

**Bitcoin Core** and **Sparrow.** BlueWallet, Green and Bull Bitcoin
cannot.

The reason is worth knowing. Your 111 characters are a key, not a wallet.
A wallet also needs the derivation paths and the script type, and Bitcoin
Core will not guess: hand it a bare key and it answers "not a valid
descriptor function". Core Signer and Sparrow both know the standard
convention and apply it for you. Software that expects a 12 or 24 word
seed phrase does not, because Core Signer does not use one.

## How much it will sign

| | ceiling | measured |
|---|---|---|
| ordinary payments | **150 inputs** | Zero 2 W, 139MB spare |
| multisig | **120 inputs** | Zero 2 W, 129MB spare |

Past those it refuses on screen and names the number. It does not try and
die half way, which would leave a signature nowhere.

Almost nothing hits these. You reach them consolidating a large number of
small payments, such as an exchange withdrawal paid out in pieces.

## The card you were given

**If `harden.sh` has not been run on it, SSH and both radios are live.**
That is a development card. It is fine on a bench and it is not a card to
put real money on.

On a hardened card the radios are disabled in firmware, the drivers are
blacklisted and their firmware is moved aside. The chip still has power,
so software can only ever tell you the radio is unused, never that it is
absent. On a Zero 2 W the radio is its own component beside the
processor, so the only certain answer is to remove it.

Check your own card, without trusting us:

    sudo bash /opt/coresigner/image/verify-install.sh

## Multisig

Core Signer can be one key of several. Export → **Multisig…** → the
script type, then QR or file. Your coordinator asks what device it is:
choose **Specter DIY**.

The quorum belongs to your coordinator, not to Core Signer. Back it up
there. Your paper backup recovers your key and not the arrangement.

**Typed derivation paths are switched off for this pilot.** They reach
paths the paper backup cannot recover on its own, and that question is
not finished.

## Known broken, and shipped anyway

- **The card channel writes world-readable files.** `/boot/firmware` is
  mounted `fmask=0022` by the operating system; the USB stick's own unit
  sets `umask=0077`. Public keys only, and still worth knowing.
- **On the pocket build the camera is the only round trip** unless you
  have a micro-USB OTG adapter. The card is the boot device, so reading
  it elsewhere means powering off, and powering off wipes the key.
- **The documents describe two builds and this board is a third.** A Zero
  2 W answering 320x240. Nothing is broken by it; every screen is written
  for both sizes.

## What we want back from you

- Anything the screen said that turned out not to be true. That is the
  most valuable bug there is.
- Anything you could not find. The ABORT button was unreachable for a
  day because nothing said which key reached it.
- What your coordinator did with the QR: which wallet, did it read first
  time, how far away, what light.
- Anything you did that we clearly never expected.

Do not send us your paper backup, a photograph of it, or any part of it.
Nobody who needs it is asking.
