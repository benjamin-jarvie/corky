# Bull Bitcoin: how it takes a public key and returns a transaction

Researched 2026-09-04 from primary sources only: Bull Bitcoin's own pages, the
app's source on GitHub, and its release notes. No claim below was tested on a
phone. Every verdict comes from code and notes.

## The app

One app lineage carries every name below. The store name today is **BULL**
(Google Play) and **BULL BITCOIN** (App Store). The seller is Satoshi Portal
Inc. The repository calls it "The Bull Bitcoin Mobile Wallet and Exchange App".

- Source: https://github.com/SatoshiPortal/bullbitcoin-mobile (Flutter, BDK,
  MIT). Code read at branch `develop`, commit `eb7c4fa` (2026-09-04),
  `pubspec.yaml` version `6.13.1+216`. Parsing lives in the `satoshifier`
  package of https://github.com/SatoshiPortal/bull_sdk, pinned at `88e05c9`.
- Android: https://play.google.com/store/apps/details?id=com.bullbitcoin.mobile
  (package `com.bullbitcoin.mobile`, matches `android/app/build.gradle`).
- iOS: https://apps.apple.com/us/app/bull-bitcoin/id6743380972 (bundle
  `com.bullbitcoin.app`, version 6.13.1 on 2026-09-04).
- Marketing site: https://wallet.bullbitcoin.com/en, page title "Bull Bitcoin
  Wallet - Self-Custodial Bitcoin Wallet".

The older "Bull Bitcoin Mobile" app is the same repository. Its first
prerelease is v0.1.0 (2023-06-16). The README at tag v0.3.0 names it "Bull
Bitcoin Mobile". The Play listing HTML carries version strings 0.1.92, 0.1.96,
0.3.2, 0.4.0 and 5.4.4 for the same package. The SatoshiPortal organisation
holds no second wallet repository. Unverified: whether an unrelated Bull
Bitcoin wallet app existed before June 2023.

## Verdicts

| # | Question | Verdict | Confidence | Source |
|---|----------|---------|------------|--------|
| 1 | Import a watch-only single-sig wallet from a Core descriptor such as `wpkh([fp/84h/0h/0h]xpub.../0/*)#checksum`, typed, pasted, or as a plain-text QR | **Yes, pasted or scanned. Not typed.** The input field has a paste button and no keyboard. Screen: Add a new wallet > Import watch-only (`ImportWatchOnlyScreen`, route `/import-watch-only`, hint "Paste xpub, ypub, zpub or descriptor"). The Scan QR button opens `ScanWatchOnlyScreen` (route `/import-watch-only-scanner`). Code path: `WatchOnlyWalletEntity.parse` > `Satoshifier.parse` > `WatchOnlyDescriptorParser` > `Descriptor.parse` > `fromExternalDescriptor` > `WalletRepository.importDescriptor`. The parser accepts `wpkh(`, `sh(wpkh(`, `pkh(` with a key origin of three hardened parts, `h` or `'`, `/0/*` or `/<0;1>/*`, and an optional `#checksum`. The checksum is verified when present. The app rebuilds the descriptor as `wpkh([fp/84h/0h/0h]xpub/0/*)` and drops the checksum. Other accepted forms: plain xpub, ypub, zpub, tpub, upub, vpub; `[fp/84h/0h/0h]xpub`; `ur:crypto-account`; `ur:crypto-hdkey`; `ur:bytes`; Passport and Keystone JSON; Coldcard file and NFC. Private keys are refused. | High, from code. Not proven on a phone. | S1, S2, S3, S4, S5, S6, S7, S8, S23 |
| 2 | Taproot single-sig watch-only import, `tr(...)` | **No.** `Derivation.fromPurpose` accepts 44h, 49h and 84h and throws "Unknown derivation purpose" for 86h. The app's `ScriptType` enum holds bip84, bip49 and bip44 only. No release note names taproot. PR #2726 "import and sign taproot descriptors" (2026-08-24) is closed and not merged. PR #2793 (open, base `develop`, 2026-09-03) lists "Taproot descriptor policies". Nothing has shipped. | High, from code. | S9, S10, S11, S12, S13 |
| 3 | Show the unsigned PSBT as an animated QR, in which encoding, and read the signed PSBT back with the camera | **Yes, when the wallet has a signer device set.** Send > "Show PSBT" (`ShowPsbtButton`, shown when `wallet.signsRemotely`) > "Sign transaction" screen (`ShowPsbtScreen`, route `/show-psbt`). The encoding follows `SignerDeviceEntity.supportedQrType`: Coldcard Q gives **BBQr** (`Bbqr.splitPsbt`, file type psbt, one frame per 2 s); Jade, Krux, Keystone, Passport, SeedSigner and Specter give **UR `ur:crypto-psbt`** (`UrQrGenerator.generatePsbtUr`, fragment length 100, slider 25 to 200, one frame per 1 s). Coldcard Mk4 signs over NFC only. Ledger and BitBox sign over USB or Bluetooth. A pasted descriptor has no device. The import details screen shows a "Signing Device" dropdown that lists every device. With no device set the sign screen shows no QR. **Read back:** "I'm done" > "Broadcast signed transaction" (`BroadcastSignedTxPage`) > Camera (`ScanQrPage`). `QrScannerWidget` decodes `ur:` multipart streams (types crypto-psbt and bytes) to base64. `BroadcastSignedTxCubit.onQrScanned` finalizes a base64 PSBT, or combines it with the unsigned PSBT when inputs are missing, or joins BBQr parts. Paste and NFC are also accepted. A single plain base64 PSBT QR is read too. For Corky: pick SeedSigner in the dropdown for UR, or Coldcard Q for BBQr. | High, from code. Not proven on a phone. | S2, S14, S15, S16, S17, S18, S19, S20, S21, S22 |
| 4 | Which version introduced each capability | Watch-only import: v0.2.2 (2024-06-13, prerelease) "Import Watch-only wallets"; descriptor import in the current code: PR #972 merged 2025-07-03, next release v5.4.0 (2025-08-06) "Import External Wallets" (mapping inferred, unverified). External descriptors: v6.2.1 (2025-10-21). Coldcard Q with BBQr: v5.1.0 (2025-06-17) "Coldcard Q support", PR #991 merged 2025-07-21. UR QR: PR #1258 merged 2025-10-06, v6.0.0 (2025-10-15) "URQR for Hardware Wallet Import". Specter, SeedSigner and Krux for all users: PR #1398 merged 2025-10-31, next release v6.3.0 (2025-11-05), not named in its notes (unverified). Jade and Passport: v6.4.0 (2025-12-02). Keystone: v6.5.0 (2026-01-06). Coldcard NFC: 6.12.0 (2026-07-05). Hardened QR, UR, BBQR and PSBT parsing: v6.13.0 (2026-08-18). Taproot: none. | Medium. Release notes are terse. PR to release mapping is inferred where marked. | S24 to S31 |

## Sources

Code quotes come from branch `develop` at `eb7c4fa` unless stated. Blob links
use `develop`.

- **S1** README, https://raw.githubusercontent.com/SatoshiPortal/bullbitcoin-mobile/main/README.md
  - "Users can import watch-only wallets via QR code, copy-pasting an Xpub/Ypub/Zpub, uploading a Coldcard file or via NFC (for Coldcard)."
  - "Users can create PSBTs from watch-only wallets for offline signing."
  - "Users can broadcast PSBTs signed in an offline wallet."
  - "Secure Bitcoin Wallet: this is a descriptor-based Bitcoin network wallet which uses bech32 segwit addresses."
- **S2** English strings, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/localization/app_en.arb
  - `"importWalletImportWatchOnly": "Import watch-only"`
  - `"importWatchOnlyPasteHint": "Paste xpub, ypub, zpub or descriptor"`
  - `"importWatchOnlyErrorInvalidFormat": "This doesn't look like a valid public key or descriptor. Double-check what you pasted."`
  - `"importWatchOnlySigningDevice": "Signing Device"` and `"importWatchOnlyUnknown": "Unknown"`
  - `"sendShowPsbt": "Show PSBT"`, `"psbtFlowSignTransaction": "Sign transaction"`, `"psbtFlowDone": "I'm done"`
  - `"broadcastSignedTxPageTitle": "Broadcast signed transaction"`, `"broadcastSignedTxPasteHint": "Paste a PSBT or transaction HEX"`, `"broadcastSignedTxScanQR": "Scan the QR code from your hardware wallet"`
  - `"importQrDeviceSeedsignerStep6": "Select \"Sparrow\" as the export option"`
- **S3** `lib/features/import_watch_only_wallet/watch_only_wallet_entity.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/import_watch_only_wallet/watch_only_wallet_entity.dart
  - `throw FormatException('Watch-only imports require public extended keys');`
  - `final satoshified = await satoshifier.Satoshifier.parse(normalized);`
  - `if (satoshified is satoshifier.WatchOnlyDescriptor) {` ... `} else if (satoshified is satoshifier.WatchOnlyXpub) {`
  - `const factory WatchOnlyWalletEntity.descriptor({ required satoshifier.WatchOnlyDescriptor watchOnlyDescriptor, @Default(SignerEntity.remote) SignerEntity signer, ... @Default(null) SignerDeviceEntity? signerDevice, })`
- **S4** satoshifier `descriptor.dart` at `88e05c9`, https://github.com/SatoshiPortal/bull_sdk/blob/88e05c9e9d2911f3dcd44b449ee97e27c73c1e51/packages/satoshifier/lib/descriptor.dart
  - `if (!DescriptorChecksum.isValid(descriptor)) {` ... `throw FormatException('Invalid descriptor checksum');`
  - External pattern: `r"(\w+(?:\(\w+)?)\(\[([a-fA-F0-9]+)/([0-9]+[\'h])/([0-9]+[\'h])/([0-9]+[\'h])\]([^/]+)/0/\*\)(?:#[a-zA-Z0-9]+)?$"`
  - Combined pattern: `r'(\w+)\(\[([a-fA-F0-9]+)/([0-9]+h)/([0-9]+h)/([0-9]+h)\]/?([^/<]+)'`
  - `String get external { return "${operand.value}($origin$pubkey/0/*)${_isShwpkh ? ')' : ''}"; }`
  - `final derivation = Derivation.fromPurpose(derivationPurpose);`
- **S5** satoshifier `utils/descriptor_checksum.dart` at `88e05c9`, https://github.com/SatoshiPortal/bull_sdk/blob/88e05c9e9d2911f3dcd44b449ee97e27c73c1e51/packages/satoshifier/lib/utils/descriptor_checksum.dart
  - "A descriptor without a suffix is accepted: the suffix is optional in BIP-380 and several wallets still export descriptors without it"
  - "When a suffix is present it must be correct"
- **S6** satoshifier `registry.dart` and `parsers/watch_only_descriptor_parser.dart` at `88e05c9`, https://github.com/SatoshiPortal/bull_sdk/blob/88e05c9e9d2911f3dcd44b449ee97e27c73c1e51/packages/satoshifier/lib/registry.dart
  - `(WatchOnlyXpubParser, WatchOnlyXpubParser.parse), (WatchOnlyDescriptorParser, WatchOnlyDescriptorParser.parse),`
  - `final descriptor = Descriptor.parse(data); return Satoshifier.watchOnlyDescriptor(descriptor: descriptor);`
- **S7** `lib/core/widgets/inputs/paste_input.dart` and `lib/features/import_watch_only_wallet/presentation/cubit/import_watch_only_cubit.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/core/widgets/inputs/paste_input.dart
  - The widget builds a `BBText` and an `IconButton` with `Icons.paste_sharp` that calls `Clipboard.getData(Clipboard.kTextPlain)`. It has no `TextField`.
  - Cubit: `if (trimmed.length >= 111) { switch (await _parseWatchOnlyInputUsecase.execute(trimmed)) {`
- **S8** `lib/core/urqr/urqr.dart` and `lib/core/widgets/qr_scanner_widget.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/core/urqr/urqr.dart
  - `if (data.toLowerCase().startsWith('ur:')) { _processUrData(data); } else { widget.onScanned(data); }`
  - `if (type == "crypto-hdkey") {` ... `} else if (type == "crypto-account") {` ... `} else if (type == "crypto-psbt") {` ... `} else if (type == "bytes") {` ... `throw UnsupportedUrType(type);`
  - `_parsePassportJsonDescriptors`: `for (final key in ['bip84', 'bip49', 'bip44']) {`
- **S9** satoshifier `enums/derivation.dart` at `88e05c9` (same text at bull_sdk HEAD `a4dd62d`, 2026-08-12), https://github.com/SatoshiPortal/bull_sdk/blob/88e05c9e9d2911f3dcd44b449ee97e27c73c1e51/packages/satoshifier/lib/enums/derivation.dart
  - `enum Derivation { bip44("Legacy", "P2PKH", "44h", "m/44h/0h/0h"), bip49("Nested SegWit", "P2SH-P2WPKH", "49h", "m/49h/0h/0h"), bip84("Native SegWit", "P2WPKH", "84h", "m/84h/0h/0h");`
  - `default: throw 'Unknown derivation purpose';`
- **S10** `packages/primitives/lib/src/script_type.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/packages/primitives/lib/src/script_type.dart
  - `enum ScriptType { bip84(purpose: 84), bip49(purpose: 49), bip44(purpose: 44);`
- **S11** `lib/core/wallet/wallet_metadata_service.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/core/wallet/wallet_metadata_service.dart
  - `case '84h': script = ScriptType.bip84; case '49h': script = ScriptType.bip49; case '44h': script = ScriptType.bip44; default: throw 'Unknown script: $matchingScript';`
- **S12** PR #2726 "feat(wallet): import and sign taproot descriptors", https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/2726
  - GitHub API: `state: closed`, `merged: False`, base `codex/hardware-wallet-policies`.
  - Body: "Import and analyze Taproot descriptor wallets." Example: `tr([FINGERPRINT/86'/0'/0']XPUB/<0;1>/*)`
- **S13** PR #2793 "feat(bullvault): add descriptor wallet and vault workflows", https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/2793
  - GitHub API: `state: open`, base `develop`.
  - Body: "analyze and sign Miniscript and Taproot descriptor policies, including timelocks, multisig, preimages, PSBT review, and safe finalization"
- **S14** `lib/features/send/ui/screens/send_screen.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/send/ui/screens/send_screen.dart
  - `if (wallet != null && wallet.signsRemotely && !hasFinalizedTx) (wallet.signerDevice != null && wallet.signerDevice!.isLedger) ? const SignLedgerButton() : (wallet.signerDevice != null && wallet.signerDevice!.isBitBox) ? const SignBitBoxButton() : const ShowPsbtButton() else const ConfirmSendButton(),`
  - `context.pushNamed( PsbtFlowRoutes.show.name, extra: (psbt: unsignedPsbt, signerDevice: signerDevice), );`
- **S15** `lib/core/wallet/domain/entities/wallet.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/core/wallet/domain/entities/wallet.dart
  - `bool get isWatchOnly => signer == SignerEntity.none;`
  - `bool get isWatchSigner => signer == SignerEntity.remote;`
  - `bool get signsRemotely => isWatchSigner;`
  - `bool get isHardwareWallet => signerDevice != null;`
- **S16** `lib/features/psbt_flow/show_psbt/show_psbt_screen.dart` and `psbt_router.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/psbt_flow/show_psbt/show_psbt_screen.dart
  - `show('/show-psbt');`
  - `if (signerDevice != null && signerDevice!.supportedQrType != QrType.none) ...[ ShowAnimatedQrWidget(`
  - `showSlider: signerDevice!.supportedQrType == QrType.urqr,`
  - `final canSignViaNfc = signerDevice == SignerDeviceEntity.coldcardQ || signerDevice == SignerDeviceEntity.coldcardMk4;`
- **S17** `lib/core/entities/signer_device_entity.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/core/entities/signer_device_entity.dart
  - `enum QrType { none, bbqr, urqr }`
  - `case SignerDeviceEntity.coldcardQ: return QrType.bbqr; case SignerDeviceEntity.jade: case SignerDeviceEntity.krux: case SignerDeviceEntity.keystone: case SignerDeviceEntity.passport: case SignerDeviceEntity.seedsigner: case SignerDeviceEntity.specter: return QrType.urqr; default: return QrType.none;`
- **S18** `lib/features/psbt_flow/data/psbt_qr_encoder_adapter.dart`, `lib/core/urqr/urqr.dart`, `lib/core/bbqr/bbqr.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/psbt_flow/data/psbt_qr_encoder_adapter.dart
  - `QrType.bbqr => await Bbqr.splitPsbt(psbt), QrType.urqr => UrQrGenerator.generatePsbtUr( psbt, fragmentLength: fragmentLength, ),`
  - `final encoder = UREncoder(ur, fragmentLength);` and `return UR('crypto-psbt', Uint8List.fromList(encoded));`
  - `final split = await bbqr.Split.tryFromData( bytes: psbtBytes, fileType: bbqr.FileType.psbt, options: bbqrOptions, );`
- **S19** `lib/features/psbt_flow/show_animated_qr/` state, cubit and widget, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/psbt_flow/show_animated_qr/show_animated_qr_cubit.dart
  - `@Default(100) int fragmentLength,`
  - `QrType.bbqr => const Duration(seconds: 2), QrType.urqr => const Duration(seconds: 1),`
  - `min: 25.0, max: 200.0,`
- **S20** `lib/features/import_watch_only_wallet/presentation/watch_only_details_widget.dart` and the cubit, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/import_watch_only_wallet/presentation/watch_only_details_widget.dart
  - `if (entity.signerDevice == null) Row( children: [ ... DropdownButtonFormField<SignerDeviceEntity?>( ... items: [null, ...SignerDeviceEntity.values]`
  - Cubit: `signer: device == null ? SignerEntity.none : SignerEntity.remote,`
- **S21** `lib/features/broadcast_signed_tx/presentation/broadcast_signed_tx_cubit.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/broadcast_signed_tx/presentation/broadcast_signed_tx_cubit.dart
  - `if (payload.startsWith('cHN')) {` "// Jade returns a non-finalized PSBT, but BDK doesn't finalize transactions it did not sign itself"
  - "// Seedsigner doesn't return the original input data, so here we try to add inputs data from the unsigned tx"
  - `final tx = psbt.combine(other: signedPsbt);`
  - `final (tx, bbqr) = await state.bbqr.scanTransaction(payload);`
- **S22** `lib/features/broadcast_signed_tx/presentation/pages/broadcast_signed_tx_page.dart` and `router.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/broadcast_signed_tx/presentation/pages/broadcast_signed_tx_page.dart
  - `broadcastHome('/broadcast-signed-tx'), broadcastScanQr('scan-qr'), broadcastScanNfc('scan-nfc');`
  - Buttons: `context.loc.broadcastSignedTxCameraButton`, `context.loc.broadcastSignedTxNfcButton`, `context.loc.broadcastSignedTxPushTxButton`
- **S23** `lib/features/import_watch_only_wallet/presentation/scan_watch_only_screen.dart` and `import_watch_only_router.dart`, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/lib/features/import_watch_only_wallet/presentation/scan_watch_only_screen.dart
  - `import('/import-watch-only'), scan('/import-watch-only-scanner');`
  - `final watchOnly = await WatchOnlyWalletEntity.parse( signerData, signerDevice: widget.signerDevice, );`
- **S24** GitHub Releases (read through the API, `repos/SatoshiPortal/bullbitcoin-mobile/releases`, 77 entries), https://github.com/SatoshiPortal/bullbitcoin-mobile/releases
  - v0.1.0, 2023-06-16, prerelease: "UPDATE: Import" "- manual descriptors fields"
  - v0.2.2, 2024-06-13, prerelease: "- Import Watch-only wallets"
  - v5.1.0, 2025-06-17: "- Coldcard Q support"
  - v5.4.0, 2025-08-06: "Import External Wallets", "Cold Card Support"
  - v6.0.0, 2025-10-15: "URQR for Hardware Wallet Import", "Fixes in Swap to Watch-only wallets"
  - v6.2.1, 2025-10-21: "Add support to external descriptors"
  - v6.4.0, 2025-12-02: "New Harware Support: Blockstream Jade, Foundation Passport", "Watch-only import disclaimer updated."
  - v6.5.0, 2026-01-06: "Keystone hardware support"
  - v6.11.1, 2026-06-08: "PSBT QR codes are now readable by Jade hardware wallets in dark mode."
  - v6.13.0, 2026-08-18: "Hardened QR, UR, BBQR, BIP21, PSBT, transaction-parent, and label parsing against malformed or mismatched input."
  - v6.13.1, 2026-08-31: "fix(import_qr_device): update Foundation Passport import instructions"
- **S25** CHANGELOG.md, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/CHANGELOG.md
  - "## [6.12.0] - 2026-07-05" ... "**Coldcard NFC**: Import a Coldcard Q or Mk4 wallet and sign transactions over NFC — a tap instead of finicky QR scanning."
  - "## 6.13.1 - 2026-08-27" ... "Fixed Passport UR fountain decoding."
  - "Strengthened wallet and label imports with private-key rejection, network and descriptor checks, duplicate detection, ownership validation, and orphan-seed cleanup."
- **S26** PR #972 "feat: import watch-only descriptor wallet by scanning or pasting", merged 2025-07-03, https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/972
  - "Support: - bip44 - bip49 - bip84"
  - Tested payload: `wpkh([86241f88/84h/0h/0h]xpub6D8aKHkNUjVrjpVcrmsyiSuUR3PTfV2eLaV4bBhAqDGqug2yuchjzEet2GMixYWT6opmFr7WXDi1ofZBF5YMCwZuftQ8hCHaUPXNiqfJvLs/<0;1>/*)#ht0s3dna`
- **S27** PR #898 "feat: scan `xpub`, `ypub` or `zpub` to import a watch-only wallet", merged 2025-06-03, https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/898
- **S28** PR #991 "feat: ColdCard Q integration PSBT / BBQR / PushTx (NFC)", merged 2025-07-21, https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/991
  - "Repaired the BBQR scanner since the replacement by `flutter_zxing`"
  - "**Schema v5**: Added `signerDevice` **nullable** column to `wallet_metadatas`"
- **S29** PR #1258 "Add URQR support", merged 2025-10-06, https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/1258
  - "Adds support for UR QR scanning, and adds the following devices which support it: - Jade - Keystone - Krux - Passport - SeedSigner"
- **S30** PR #1398 "Add support for Specter. Allow SeedSigner and Krux.", merged 2025-10-31, https://github.com/SatoshiPortal/bullbitcoin-mobile/pull/1398
  - "Added support for Specter (clone of SeedSigner). Show SeedSigner and Krux to all users"
- **S31** App Store listing, https://apps.apple.com/us/app/bull-bitcoin/id6743380972
  - Title "BULL BITCOIN", seller "Satoshi Portal Inc", "Version 6.13.1"
  - What's New: "Coldcard NFC — Import and sign with Coldcard Q and Mk4 over NFC"; "Enhanced parsing protections for QR, UR, BBQR, BIP21, and PSBT formats"; "Hardware wallets • Fixed Passport QR scanning and updated import instructions"
- **S32** Google Play listing, https://play.google.com/store/apps/details?id=com.bullbitcoin.mobile
  - Page HTML: `og:title` "BULL - Apps on Google Play"; developer "Satoshi Portal Inc."; version strings "0.1.92", "0.1.96", "0.3.2", "0.4.0", "5.4.4"
- **S33** Bull Bitcoin blog, "BULL - the Perfect Bitcoin Wallet", https://www.bullbitcoin.com/blog/bull-by-bull-bitcoin
  - "Can import watch-only wallets"
  - "You can import descriptors and xpubs too!"
  - "Segwit-native descriptor based wallet using the battle-tested BDK library"
  - "Already, we support Coldcard Q1 by CoinKite and we have built integrations for many other hardware wallets that will be released over the next weeks and months."
- **S34** Bull Bitcoin blog, "How to Move Bitcoin From Your Spending Wallet to Cold Storage Privately", https://www.bullbitcoin.com/blog/how-to-move-bitcoin-from-your-spending-wallet-to-cold-storage-privately
  - "You can import an existing cold wallet as watch-only by adding its extended public key (XPUB)"
  - "Both options work with devices such as Passport, Blockstream Jade, SeedSigner, and more"
- **S35** BULL Wallet guides, published by Bull Bitcoin ("Copyright © 2024-2025 Bull Bitcoin"), https://guides.bitcoinsupport.com/guide-overview.html
  - Import overview, https://guides.bitcoinsupport.com/configurations/import-wallet/overview.html: "Paste public key (xpub) or scan public key QR"; "receive and spend Bitcoin from it, via broadcasting PSBT"
  - Connect SeedSigner, https://guides.bitcoinsupport.com/configurations/import-wallet/connect-seedsigner.html: "Select "Export Xpub""; "Choose "Single Sig", then select your preferred script type (choose Native Segwit if unsure)"; "Select "Sparrow" as the export option"; "On your mobile device, tap Open Camera"
  - Connect Specter, https://guides.bitcoinsupport.com/configurations/import-wallet/connect-specter.html: "Select "Master public keys""; "Choose "Single key""; "Disable "Use SLIP-132""
  - Connect ColdCard Q, https://guides.bitcoinsupport.com/configurations/import-wallet/connect-coldcard-q.html: "Select 'Export Wallet'"; "Choose 'Bull Bitcoin' as the export option"
  - Broadcast overview, https://guides.bitcoinsupport.com/configurations/broadcast-transaction/overview.html: "Broadcast signed transaction, via: Paste a Partially Signed Bitcoin Transaction (PSBT) or transaction HEX, Scan with camera, Sign with NFC (PushTx)"
- **S36** README at tag v0.3.0, https://raw.githubusercontent.com/SatoshiPortal/bullbitcoin-mobile/v0.3.0/README.md
  - "Bull Bitcoin Mobile is a self-custodial Bitcoin and Liquid Network which offers non-custodial atomic swaps across Bitcoin, Lightning and Liquid."
  - "Users can import watch-only wallets via QR code, copy-pasting an Xpub/Ypub/Zpub, uploading a Coldcard file or via NFC"
- **S37** SatoshiPortal repositories with "wallet" in the name or description, https://github.com/orgs/SatoshiPortal/repositories?q=wallet&type=all
  - Listed: bullbitcoin-mobile, bull_sdk, lwk-dart, lqmassive, ark-wallet-dart, spark-wallet. No second mobile wallet app.
- **S38** App identifiers in the repository, https://github.com/SatoshiPortal/bullbitcoin-mobile/blob/develop/pubspec.yaml
  - `pubspec.yaml`: `name: bb_mobile`, `description: Bull Bitcoin Mobile Wallet`, `version: 6.13.1+216`
  - `android/app/build.gradle`: `applicationId = 'com.bullbitcoin.mobile'`
  - `ios/Runner.xcodeproj/project.pbxproj`: `PRODUCT_BUNDLE_IDENTIFIER = com.bullbitcoin.app;`
  - `pubspec.yaml`: `satoshifier: git: url: https://github.com/SatoshiPortal/bull_sdk ref: 88e05c9e9d2911f3dcd44b449ee97e27c73c1e51`

## Not found

- No phone test. Every verdict above comes from code and notes. The phone
  proof is ticket 22.
- help.bullbitcoin.com: the index lists no wallet article. Its `?ask=` query
  endpoint returned HTTP 403.
- Google Play description text: the fetch tool truncated the page. Only the
  title, the developer and the version strings were read from the HTML.
- wallet.bullbitcoin.com renders "Loading..." without JavaScript. Only its
  title was read.
- The Coldcard Q broadcast guide holds a video and one line of text. No text
  steps for the PSBT round trip exist in Bull's guides.
- No release note names the first release that shows SeedSigner, Specter and
  Krux, the first release that displays a PSBT as a UR QR, or the first
  release with the "Signing Device" dropdown. The PR merge dates stand in.
- Whether the Send flow builds a PSBT for a descriptor wallet whose signer is
  set to "Unknown" (signer `none`). The code shows `ConfirmSendButton` for
  that case. Not traced further.
- Whether an unrelated Bull Bitcoin wallet app existed before v0.1.0
  (2023-06-16). No repository, store listing or blog post for one was found.
- Which QR form SeedSigner's "Sparrow" export produces. Bull's guide names the
  option; it does not name the encoding.
