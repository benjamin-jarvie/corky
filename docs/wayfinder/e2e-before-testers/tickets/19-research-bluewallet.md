# 19 BlueWallet: how it takes a public key and returns a transaction

Labels: wayfinder:research (AFK)
Blocked by: none
Status: resolved 2026-09-04

## Question

From primary sources only (BlueWallet's documentation, its source on
GitHub, its release notes), establish with URLs and quoted lines:

1. Can BlueWallet import a watch-only single-signature wallet from a Core
   output descriptor such as `wpkh([fp/84h/0h/0h]xpub.../0/*)#checksum`,
   typed or as a plain-text QR? If not, which forms does it take: xpub,
   zpub, `ur:crypto-account`, other?
2. Does it support taproot single-signature watch-only, `tr(...)`?
3. When sending from a watch-only wallet, can it show the unsigned PSBT as
   an animated QR for an external signer, in which encoding (UR, BBQr,
   other), and read the signed PSBT back with the phone camera?
4. Which version introduced each capability.

Write the findings to `../research/bluewallet.md`: a verdict table, then
the sources. No claim without a URL. Mark anything not found as not found.

## Answer (research, 2026-09-04)

Full findings with 40 quoted sources: [research/bluewallet.md](../research/bluewallet.md).

1. **Descriptor import: yes.** BlueWallet's `AbstractWallet.setSecret()` has a
   branch for `wpkh(`, `pkh(`, `sh(` and `tr(`. It reads the fingerprint and
   path, converts `h` to `'`, converts the xpub to a zpub, and drops the
   `/0/*` suffix and the checksum. Screen: Add wallet, Import wallet, paste
   or scan. A plain-text QR of Corky's descriptor lands in the same field.
2. **Taproot: yes.** `tr(` builds an `HDTaprootWallet`; unit tests import
   `tr([fp/86'/0'/0']xpub/<0;1>/*)` and make a PSBT. A bare xpub with no
   prefix becomes a legacy wallet, so Corky must always send the wrapper.
3. **PSBT round trip: yes**, with the "Use with Hardware Wallet" switch on.
   The send screen shows `ur:crypto-psbt` as an animated QR at one frame a
   second; "Scan Signed Transaction" reads `ur:crypto-psbt`, BBQr, legacy
   `ur:bytes`, base43 and base64, then finalizes and offers broadcast.
4. Versions: `wpkh(` from Sparrow v6.4.9 (2023-10); `tr(` v7.2.2 (2025-11);
   UR v2 QR v6.1.9 (2021-07); BBQr v7.2.6 (2026-02).

**Consequence for ticket 06 and 22:** BlueWallet takes the same plain
descriptor QR as Sparrow, and returns transactions in the UR Corky already
reads. Its export entry is wired to the Sparrow format. It stays marked
untested until Ben's phone proves it (ticket 22).
