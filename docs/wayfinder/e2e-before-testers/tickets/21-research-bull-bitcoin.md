# 21 Bull Bitcoin Mobile: how it takes a public key and returns a transaction

Labels: wayfinder:research (AFK)
Blocked by: none
Status: resolved 2026-09-04

## Question

The same four questions as ticket 19, for the Bull Bitcoin mobile wallet,
from Bull Bitcoin's documentation, its source on GitHub, and release notes.
Establish first which app is meant: Bull Bitcoin has shipped more than one
wallet. Pin down watch-only import forms, taproot, and PSBT export by QR.

Write the findings to `../research/bull-bitcoin.md`, same shape as ticket 19.

## Answer (research, 2026-09-04)

Full findings with 38 quoted sources: [research/bull-bitcoin.md](../research/bull-bitcoin.md).

**The app:** one lineage, `SatoshiPortal/bullbitcoin-mobile` (Flutter on
BDK), sold as BULL on Google Play and BULL BITCOIN on the App Store, version
6.13.1 on 2026-09-04. No second wallet app exists.

1. **Descriptor import: yes** for `wpkh([fp/84h/0h/0h]xpub/0/*)#checksum`,
   pasted or as a plain-text QR, on Add a new wallet, Import watch-only. The
   field has a paste button and no keyboard. The checksum is verified when
   present. Also takes xpub, ypub, zpub, `ur:crypto-account`,
   `ur:crypto-hdkey`, a Coldcard file, and NFC.
2. **Taproot: no.** The parser throws on `86h`; `ScriptType` holds 84, 49
   and 44 only. A taproot PR is open and unmerged.
3. **PSBT round trip: yes, only when a "Signing Device" is set** on the
   import screen. SeedSigner, Specter, Krux, Jade, Keystone and Passport give
   `ur:crypto-psbt` (one frame a second); Coldcard Q gives BBQr. The camera
   on "Broadcast signed transaction" reads UR, BBQr, or one base64 QR.
4. Versions: watch-only import v0.2.2 (2024-06); descriptor paste and scan
   v5.4.0 (2025-07); UR QR v6.0.0 (2025-10).

**Consequence for tickets 06 and 22:** Bull Bitcoin takes the plain
descriptor QR for native segwit only. Corky's Bull Bitcoin entry offers
BIP84 only and the screen says to pick "SeedSigner" as the signing device.
Untested until Ben's phone proves it.
