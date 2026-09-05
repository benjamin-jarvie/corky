# Corky: the words

The ubiquitous language. The code, the tests, the tickets and Ben use these
words for these things and no synonym. Implementation detail does not belong
here.

**Corky**: the device and its program: screens, buttons, camera, and the
calls it makes to Bitcoin Core. Corky computes nothing on a key.

**Core**: Bitcoin Core, running wallet-only and offline on the device. Every
operation on a key happens inside Core.

**key**: one master private key, held by Core as one wallet for one session.
A key is named by its **fingerprint**. Corky holds up to five keys at once.
_Avoid_: seed (Corky's main build has no seed words), wallet (a Core term,
not a screen word).

**fingerprint**: the eight hex characters Core derives from a key's master
public key. It names the key on every screen and inside every transaction.
_Also_: XFP, in code and in chat.

**session**: power-on to power-off. Keys live in the ramdisk for the session
and nowhere else.

**coordinator**: the software that watches the chain, builds transactions
and broadcasts them: Sparrow, a Bitcoin Core laptop, or a phone wallet.
Corky is never a coordinator.

**public key**: what a coordinator needs from a key: Core's watch-only
descriptors. It holds no secret. _Also_: xpub, in chat. _Avoid_: watch-only
wallet as a screen word; it is what the coordinator makes from the public
key.

**descriptor**: Core's own text form of a key or of a public key, with its
checksum. Corky passes descriptors through and never rewrites one.

**transaction**: a PSBT, on screen and in the tickets. Corky reviews it with
Core's numbers, signs it with Core, and hands it back.

**backup**: two forms. The **paper backup** is the key's xprv, written by
hand from the screen. The **file backup** is a wallet file encrypted by
Core with a passphrase, written to a stick or a card. Only the file backup
can be restored on another computer running Core.

**channel**: how bytes cross the air gap. **QR**: the camera reads, the
screen shows. **stick**: a USB stick in the OTG port. **card**: the boot
microSD, read in another computer.

**primary build**: the CM4 on the Waveshare carrier with the Display HAT
Mini. **pocket build**. the Pi Zero 2 W in the SeedSigner case.

**Layer 1, 2, 3**: the README's trust layers. Layer 1 transforms secret
material and is zero lines on main. Layer 2 sees secrets and carries them
as strings. Layer 3 is opaque to secrets.

**lab**: the full build, kept in the butlers-playground repository: seed
words, codex32, SeedQR, and everything main refused.
