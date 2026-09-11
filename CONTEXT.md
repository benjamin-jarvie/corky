# Core Signer: the words

The ubiquitous language. The code, the tests, the tickets and Ben use these
words for these things and no synonym. Implementation detail does not belong
here.

**Core Signer**: the device and its program: screens, buttons, camera, and the
calls it makes to Bitcoin Core. Core Signer computes nothing on a key.

**Core**: Bitcoin Core, running wallet-only and offline on the device. Every
operation on a key happens inside Core.

**key**: one master private key, held by Core as one wallet for one session.
A key is named by its **fingerprint**. Core Signer holds up to five keys at once.
_Avoid_: seed (Core Signer's main build has no seed words), wallet (a Core term,
not a screen word).

**fingerprint**: the eight hex characters Core derives from a key's master
public key. It names the key on every screen and inside every transaction.
_Also_: XFP, in code and in chat.

**session**: power-on to power-off. Keys live in the ramdisk for the session
and nowhere else.

**coordinator**: the software that watches the chain, builds transactions
and broadcasts them: Sparrow, a Bitcoin Core laptop, or a phone wallet.
Core Signer is never a coordinator.

**public key**: what a coordinator needs from a key: Core's watch-only
descriptors. It holds no secret. _Also_: xpub, in chat. _Avoid_: watch-only
wallet as a screen word; it is what the coordinator makes from the public
key.

**descriptor**: Core's own text form of a key or of a public key, with its
checksum. Core Signer passes descriptors through and never rewrites one.

**transaction**: a PSBT, on screen and in the tickets. Core Signer reviews it with
Core's numbers, signs it with Core, and hands it back.

**backup**: the **paper backup**, and there is no other kind. It is the
key's xprv, written by hand from the screen, and Bitcoin Core and Sparrow
both open it. PLAN A-24 deleted the encrypted file backup, so this device
never writes a private key to any medium. _Avoid_: file backup, which was
a real thing until 2026-09-05 and is now only a thing that was removed.

**channel**: how bytes cross the air gap. **QR**: the camera reads, the
screen shows. **stick**: a USB stick in the OTG port. **card**: the boot
microSD, read in another computer.

**file channel**: stick and card together, as against QR. The device
offers whichever of the two is really there. _In code_: `filechannel.py`,
`Session._file_channels`.

**policy**: which script type a key's addresses use. There are four:
Native segwit, Taproot, Nested segwit and Legacy, in the words Sparrow,
BlueWallet and Core's own GUI use for them. One key holds all four unless
it was imported as a bare descriptor. _In code_: `kind`, and the four are
`wpkh`, `tr`, `sh`, `pkh`. _Avoid_: script type and address type as
screen words; derivation path, which is a different thing that a policy
implies.

**quorum**: several keys that together control one wallet, and how many
of them a spend needs. On screen as `2 of 3`. The coordinator holds it,
never Core Signer. _In code_: `quorum`, a `(threshold, total)` pair. _Avoid_:
multisig wallet, which names the software rather than the arrangement.

**cosigner**: one key inside a quorum, and the record a coordinator needs
to put it there: `[fingerprint/path]xpub`. Core Signer is one cosigner and
never the quorum. _In code_: `cosigner_key`. _Avoid_: participant,
member, signer, which is Core's role name for something else.

**share**: one cosigner's signature on a transaction that needs more than
one. It is a finished piece of work and never a failure. The screen says
`SHARE` for it, and `SIGNED` only when the transaction can be sent.
_In code_: `complete` is False for a share. _Avoid_: partial signature as
a screen word, and "incomplete", which reads as a fault.

**tier**: one branch of a policy that changes what a spend needs as time
passes, such as 3 keys now and 1 key after 20 blocks. The coordinator
chooses the tier when it builds, with `nSequence`, and Core Signer can only
show it and refuse. On screen as `AFTER 20 BLOCKS`. _In code_:
`timelocks` for what the policy holds and `spend_lock` for the one this
spend enables. _Avoid_: decay path, recovery path, miniscript branch,
all of which name the same thing three ways.

**primary build**: the CM4 Lite with the SeedSigner+ display hat, 2.8"
ST7789 at 320x240 (PLAN A-13b/A-15). **pocket build**: the Pi Zero 2 W in
the SeedSigner case.

Panel size is NOT decided by which of the two it is. The board on Ben's
desk is a Zero 2 W and it answers 320x240, measured 2026-09-06 by asking
`hal.DeviceDisplay` on the board itself. Every screen is written for both
320x240 and 240x240 and `tests/test_screen_fit.py` renders both, so the
pairing is a fact about one board rather than a rule.

**Layer 1, 2, 3**: the README's trust layers. Layer 1 transforms secret
material and is zero lines on main. Layer 2 sees secrets and carries them
as strings. Layer 3 is opaque to secrets.

**lab**: the full build, kept in the butlers-playground repository: seed
words, codex32, SeedQR, and everything main refused.
