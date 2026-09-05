# Blockstream Green (Blockstream app) and Corky output descriptors

Research date: 2026-09-04. Sources: Blockstream help center, the gdk, green_android, green_ios and green_qt repositories, their CHANGELOG files, and the pinned parser libraries that gdk and the apps call (rust-miniscript, rust-bitcoin, libwally-core). Every claim below points to a quoted line in the Sources section. Claims without a quoted line are marked "unverified".

## Verdict table

| # | Question | Verdict | Confidence | Source |
|---|----------|---------|------------|--------|
| 1 | Watch-only singlesig from a Core descriptor | Yes. All three apps accept a pasted or scanned plain-text descriptor such as `wpkh([fp/84h/0h/0h]xpub.../0/*)#checksum` on the singlesig watch-only setup screen. The apps pass the string to gdk as `core_descriptors`. gdk parses it with rust-miniscript and rejects: no key origin, no wildcard, an origin path that is not exactly `purpose'/coin'/account'`, a purpose that does not match the script type, and `<0;1>` multipath keys. gdk verifies `#checksum` when present and accepts `h` and `'` hardened markers. The app screens also accept SLIP-132 xpub/ypub/zpub (sent as `slip132_extended_pubkeys`) and `ur:crypto-account` animated QR (decoded by gdk into descriptors). The "Import from file" button reads only Coldcard JSON and Electrum JSON, so Corky's plain-text file cannot be imported through that button. Screens: Android and iOS "Set Up Watch Only" (Android view model `WatchOnlySinglesigViewModel`, iOS `WOViewModel.validateImport`); desktop `SinglesigWatchOnlyAddPage`. gdk calls: `GA_login_user` (since 0.0.59) and `GA_register_user` (since 0.72.0) with a `core_descriptors` credential. | High | S1, S2, S5, S6, S7, S8, S9, S11, S12, S13, S14, S16, S24, S25, S26, S34, S35 |
| 2 | Taproot singlesig watch-only (`tr(...)` or BIP86) | Yes in gdk since 0.75.0 (2025-03-20): `parse_single_sig_descriptor` accepts `tr([fp/86'/coin'/n']xpub/0/*)` with no tap tree and maps it to `ScriptType::P2tr`; a subaccount type `"p2tr"` exists; the watch-only device JSON sets `supports_p2tr` true; PSBT creation from a descriptor watch-only session is allowed since 0.73.0. The Android detector lists `tr(` and its tests include BIP86 `tr(` descriptors. iOS pre-validates with libwally, which has a `tr` builtin. Desktop passes the typed text through. A BIP86 xpub has no SLIP-132 prefix, so the `tr(` descriptor form is the one to use. Not tested end to end in this research. | High for gdk and Android; Medium for iOS and desktop (source verified, not run) | S5, S7, S9, S10, S12, S16, S32, S35 |
| 3 | Unsigned PSBT as animated QR for a non-Jade signer; encoding; read the signed PSBT back | Yes, with a caveat. The code does not check the device type. Android creates a PSBT for any singlesig watch-only session; iOS for any singlesig watch-only wallet; desktop for any watch-only wallet whose login used `core_descriptors` on a Bitcoin Electrum network (an xpub-imported desktop wallet gets no QR flow). Encoding: BC-UR `ur:crypto-psbt` multi-part fragments from `GA_bcur_encode` (Android fragment length 50, desktop 40, upper-cased on desktop, 250 ms per frame on desktop). Read-back: desktop and iOS accept only a `ur:crypto-psbt` QR by camera, or a `.psbt` file (binary or base64); Android accepts a camera scan (BC-UR decoded to base64) or a `.psbt` file. gdk then finalises and broadcasts the signed PSBT via `GA_broadcast_transaction`. Caveat: every screen label says "Scan QR with Jade" and the help article names only Jade; Android and iOS show a Jade-unlock prompt before the export page on watch-only sessions (whether a user can skip it with a non-Jade signer is unverified). No source lists Ledger or Trezor as QR signers; their support in Green is over USB or Bluetooth and was not researched here. | High for encoding and read-back; Medium for a non-Jade signer (code has no Jade gate, UI assumes Jade, not tested) | S3, S4, S5, S17, S18, S19, S20, S21, S22, S27, S28, S29, S30, S36, S37, S38, S39, S40 |
| 4 | Version that introduced each capability | gdk: 0.0.57 (2022-11-23) exposes `core_descriptor` and `slip132_extended_pubkey`; 0.0.59 (2023-04-12) login with xpubs or descriptors; 0.68.0 (2023-09-27) BC-UR decode of `crypto-psbt`, `crypto-output`, `crypto-account` and PSBT signing; 0.70.0 (2024-02-01) `GA_psbt_from_json`; 0.72.0 (2024-07-26) `GA_register_user` with watch-only credentials; 0.73.0 (2024-09-18) PSBT creation from descriptor watch-only sessions and direct PSBT broadcast; 0.75.0 (2025-03-20) BIP-86 P2TR singlesig. green_android: 4.0.3 (2023-04-29) watch-only for singlesig Bitcoin; 4.0.19 (2023-11-20) BC-UR animated QR import; 4.0.38 (2024-11-13) "Jade QR Mode"; 5.1.0 (2025-10-09) export unsigned PSBT to file and import signed PSBT in watch-only wallets. green_ios: 4.0.3 (2023-04-28) import watch-only via xpubs and descriptors from QR codes or files; 4.0.36 (2024-10-23) "QR mode for singlesig watch-only"; 5.1.0 (2025-10-14) export and import PSBT files in watch-only wallets. green_qt: 2.0.5 (2024-05-08) add or import singlesig watch-only wallet; 3.5.0 (2026-08-10) airgapped signing with Jade on watch-only wallets. | High for the quoted entries; Medium for the Android animated-QR version (the 4.0.38 entry does not name watch-only) | S10, S23, S31, S33 |

## Details that matter for Corky's export

1. Key origin is mandatory. gdk returns `UnsupportedDescriptor` when the xpub has no `[fingerprint/path]` origin (S7, test `shp2wkh_no_key_origin`). Corky's `[d2b7e45c/84h/0h/0h]` satisfies this.
2. The origin path must be exactly three hardened levels: `purpose'/coin'/account'`. The purpose must be 84 for `wpkh`, 86 for `tr`, 49 for `sh(wpkh())`, 44 for `pkh` (S7, `match_key_origin`). A fourth level fails (S7, test `p2wpkh_incorrect_key_origin2`).
3. The xpub's own child number must be the hardened account index from the origin path, or unhardened 0 (a Ledger quirk) (S7, `check_xpub_consistency`). An xpub derived at `m/84h/0h/0h` satisfies this.
4. A wildcard is mandatory: `/0/*` passes, `/0` fails (S7, `has_wildcard`).
5. One descriptor is enough. The external `/0/*` descriptor and the internal `/1/*` descriptor yield the same account xpub, and gdk derives both chains from it (S7, test comment; S5, `GA_get_subaccount` returns two descriptors).
6. `<0;1>` multipath keys fail. rust-miniscript parses them as `MultiXPub`; gdk matches only `DescriptorPublicKey::XPub` (S7, S11c).
7. `#checksum` is optional and is verified when present (S11a). Hardened markers `h` and `'` are both accepted by rust-bitcoin (S11b) and by libwally (S32).
8. Network detection on Android uses the xpub prefix and the `'` path form (`/84'/0'/`). With `84h` the path check misses, but the `xpub` prefix inside a descriptor still selects mainnet (S12, `detectNetwork`). Testnet uses `tpub`.
9. "Import from file" is for Coldcard JSON and Electrum JSON, on Android (S13, `importFile`), iOS (S26, `parseGenericJson`, `parseElectrumJson`) and desktop (S35, `parseFile`). A raw descriptor text file is rejected. Paste or scan the descriptor instead.
10. The signed PSBT must come back as `ur:crypto-psbt` for the camera path on desktop and iOS (S30, S40). Android takes the decoded text of any scan and treats it as the PSBT (S18, S22); a plain base64 QR on Android is unverified.

## Sources

Fetch notes: the help center moved from `help.blockstream.com/hc/en-us/articles/...` to `help.blockstream.com/blockstream-app/...`. Several old `hc/en-us` URLs returned 404 on 2026-09-04. Quotes marked "as rendered" come from a fetch tool that summarises pages; the wording is the tool's rendering of the page.

### Help center

S1. https://help.blockstream.com/blockstream-app/perform-advanced-wallet-operations/set-up-watch-only-wallet
- As rendered: "Singlesig users: Copy the 'extended public keys' or 'output descriptors'".
- As rendered: "Return to your home screen and tap the wallet icon. Select Set Up a New Wallet > Get Started > Set Up Watch Only."
- As rendered: "Singlesig users can: Paste the copied xpub; Scan its QR code; Import from file (requires JadeLink)".
- Android path as rendered: "Select the three-dot menu and tap Watch-only", "Copy the 'output descriptor'".

S2. https://help.blockstream.com/blockstream-jade/set-up-transact-recover-your-wallet/set-up-watch-only-access-for-jade
- "Singlesig: Copy the extended public key (xpub)".
- "From the app's home screen, tap Set up a New Wallet, then choose Add Wallet → Watch-only."
- "Select your account type and paste in the extended public key or enter the credentials if using a Multisig Shield/2FA account."

S3. https://help.blockstream.com/blockstream-app/perform-advanced-wallet-operations/export-psbt
- "The Blockstream app enables you to export Partially Signed Bitcoin Transactions (PSBTs), which may be useful when signing transactions with an offline device (like a Jade Plus)."
- "Before beginning, ensure that you've set up a watch-only account in the Blockstream app for the Jade device that you will be signing transactions with."
- "Tap Sign Transaction via QR, unlock your Jade Plus, then tap Export Transaction."
- "Tap Next, tap Import from file, then select your signed PSBT file from the JadeLink folder on your mobile device."

S4. https://help.blockstream.com/hc/en-us/articles/900003101806-What-is-watch-only-mode (also at https://help.blockstream.com/blockstream-app/perform-advanced-wallet-operations/what-is-watch-only-mode)
- Cannot: "send transactions from your wallet without an offline signer".
- Can: "generate addresses and receive new transactions".

### gdk documentation

S5. https://github.com/Blockstream/gdk/blob/master/docs/source/gdk-json.rst (rendered at https://gdk.readthedocs.io/en/latest/gdk-json.html)
- Line 157: "To authenticate a descriptor watch-only wallet (singlesig only):"
- Line 162: `"core_descriptors": ["pkh([00000000/44'/1'/0']tpubDC2Q4xK4XH72J7Lkp6kAvY2Q5x4cxrKgrevkZKC2FwWZ9A9qA5eY6kvv6QDHb6iJtByzoC5J8KZZ29T45CxFz2Gh6m6PQoFF3DqukrRGtj5/0/*"],`
- Line 165 to 171: "Or alternatively:" `"slip132_extended_pubkeys": ["tpubDC2Q4xK4XH72J7Lkp6kAvY2Q5x4cxrKgrevkZKC2FwWZ9A9qA5eY6kvv6QDHb6iJtByzoC5J8KZZ29T45CxFz2Gh6m6PQoFF3DqukrRGtj5"],`
- Line 173 to 174: "The values to use for ``"core_descriptors"`` and ``"slip132_extended_pubkeys"`` can be obtained by calling `GA_get_subaccount` from a non-descriptor watch-only session."
- Line 390: "For singlesig subaccounts, one of ``"p2pkh"``, ``"p2wpkh"``, ``"p2sh-p2wpkh"`` or ``"p2tr"``."
- Line 393 to 397: ":core_descriptors: Singlesig only. The Bitcoin Core compatible output descriptors. One for the external chain and one for internal chain (change), for instance ``"sh(wpkh(tpubDC2Q4xK4XH72H18SiEV2A6HUwUPLhXiTEQXU35r4a41ZVrUv2cgKUMm2fsKTapi8DH4Y8ZVjy8TQtmyWMuH37kjw8fQGJahjWbuQoPm6qRF/0/*))"`` ``"sh(wpkh(tpubDC2Q4xK4XH72H18SiEV2A6HUwUPLhXiTEQXU35r4a41ZVrUv2cgKUMm2fsKTapi8DH4Y8ZVjy8TQtmyWMuH37kjw8fQGJahjWbuQoPm6qRF/1/*))"`` for a ``p2sh-p2wpkh`` subaccount."
- Line 398 to 401: ":slip132_extended_pubkey: Singlesig and Bitcoin only. The extended public key with modified version as specified in SLIP-0132 (xpub, ypub, zpub, tpub, upub, vpub). Use of this value is discouraged and this field might be removed in the future. Callers should use descriptors instead."
- Line 996 to 1003: "Where ``data`` is longer than ``max_fragment_len``, the result is a multi-part encoding using approximately 3 times the minimum number of fragments needed to decode the data, split into parts of size ``max_fragment_len`` or less." "In this case, the caller must provide all returned parts to any decoder, e.g. by generating an animated QR code from them." "Special case is for ``ur_type`` equal to ``crypto-psbt``: ``data`` field is expected to be in base64 format."
- Line 1016: `"parts": ["ur:crypto-seed/oeadgdstaslplabghydrpfmkbggufgludprfgmaotpiecffltnlpqdenos"]`
- BCUR Decoded data JSON: ":ur_type: "crypto-psbt". :psbt: The psbt in base-64 format." ":ur_type: "crypto-output". :descriptor: The bitcoin output descriptor." ":ur_type: "crypto-account". :descriptors: The list of all available descriptors for the account. :master_fingerprint: The BIP32 key fingerprint of the master key of the account."

### gdk source

S6. https://github.com/Blockstream/gdk/blob/master/subprojects/gdk_rust/gdk_common/src/model.rs
- `pub enum WatchOnlyCredentials { Slip132ExtendedPubkeys(Vec<String>), CoreDescriptors(Vec<String>), }`
- `fn from_descriptor(s: &str, expected_is_mainnet: bool, is_liquid: bool)` calls `parse_single_sig_descriptor(s, coin_type, is_liquid)?` and returns `master_xpub_fingerprint: Some(master_xpub_fingerprint)`.
- `fn from_slip132_extended_pubkey`: `let (is_mainnet, script_type, xpub) = decode_from_slip132_string(s)?;` and `master_xpub_fingerprint: None`.

S7. https://github.com/Blockstream/gdk/blob/master/subprojects/gdk_rust/gdk_common/src/descriptor.rs
- Line 15 to 30 (`match_key_origin`): matches `(Some(Hardened p), Some(Hardened c), Some(Hardened n), None) if (*p == purpose && *c == coin_type) => Ok(*n), _ => Err(Error::UnsupportedDescriptor)`.
- Line 41 to 49 (`check_xpub_consistency`): `ChildNumber::Hardened { index: n } if n == bip32_account => Ok(...)`, "// Ledger sets the child number to unhardened 0, allow for that", `_ => Err(Error::UnsupportedDescriptor)`.
- Line 74 to 78: `Descriptor::parse_descriptor(&crate::EC, &s).map_err(|_| Error::UnsupportedDescriptor)?; if !desc.has_wildcard() { return Err(Error::UnsupportedDescriptor); }`
- Line 95 to 99: `else if let Descriptor::Wpkh(wpkh) = desc { if let DescriptorPublicKey::XPub(descriptorxkey) = wpkh.as_inner() { if let Some((f, p)) = &descriptorxkey.origin { let n = match_key_origin(&p.clone().into(), 84, coin_type)?; return check_xpub_consistency(ScriptType::P2wpkh, ...`
- Line 109 to 121: `else if let Descriptor::Tr(tr) = desc { if let DescriptorPublicKey::XPub(descriptorxkey) = tr.internal_key() { if tr.tap_tree().is_none() { if let Some((f, p)) = &descriptorxkey.origin { let n = match_key_origin(&p.clone().into(), 86, coin_type)?; return check_xpub_consistency(ScriptType::P2tr, ...`
- Line 125: `Err(Error::UnsupportedDescriptor)`
- Line 139: `let p2wpkh = format!("wpkh([00000000/84'/1'/0']{}/0/*)", tpub);`
- Line 144 to 147 (invalid cases): `shp2wkh_no_wildcard = format!("sh(wpkh([00000000/49'/1'/0']{}/0))", tpub)`, `shp2wkh_no_key_origin = format!("sh(wpkh({}/0/*))", tpub)`, `p2wpkh_incorrect_key_origin1 = format!("sh(wpkh([00000000/44'/1'/0']{}/0/*))", tpub)`, `p2wpkh_incorrect_key_origin2 = format!("sh(wpkh([00000000/84'/1'/0'/0']{}/0/*))", tpub)`.
- Line 209 to 212: "// Note that external and internal descriptors yield to the same xpub" `assert_eq!(shp2wpkh_xpub_external.to_string(), tpub); assert_eq!(shp2wpkh_xpub_internal.to_string(), tpub);`

S8. https://github.com/Blockstream/gdk/blob/master/subprojects/gdk_rust/gdk_electrum/src/account.rs
- Line 116: `ScriptType::P2tr => ("tr", ""),` inside `fn descriptor(&self, is_internal: bool)`.
- Line 130 to 132: `let checksum = gdk_common::elements_miniscript::descriptor::checksum::desc_checksum(&desc)?; Ok(format!("{}#{}", &desc, checksum))`
- Line 785: `3 => (ScriptType::P2tr, 86),`

S9. https://github.com/Blockstream/gdk/blob/master/src/signer.cpp
- Line 59 to 68: `const auto slip132_pubkeys = j_array(credentials, "slip132_extended_pubkeys"); const auto descriptors = j_array(credentials, "core_descriptors"); if (descriptors && !slip132_pubkeys && !descriptors->empty()) { // Descriptor watch-only login return { { "core_descriptors", std::move(*descriptors) } }; } if (slip132_pubkeys && !descriptors && !slip132_pubkeys->empty()) { // Descriptor watch-only login return { { "slip132_extended_pubkeys", std::move(*slip132_pubkeys) } }; }`
- Line 79 to 83: `static const nlohmann::json WATCH_ONLY_DEVICE_JSON{ { "device_type", "watch-only" }, ... { "supports_p2tr", true }, { "supports_liquid_p2tr", true } };`
- Line 101 to 103: `} else if (credentials.contains("username") || credentials.contains("slip132_extended_pubkeys") || credentials.contains("core_descriptors")) { ret = WATCH_ONLY_DEVICE_JSON;`
- Line 269 to 272: `bool signer::is_descriptor_watch_only() const { return m_credentials.contains("core_descriptors") || m_credentials.contains("slip132_extended_pubkeys"); }`

S10. https://github.com/Blockstream/gdk/blob/master/CHANGELOG.md
- "## Release 0.75.0 - 25-03-20" "- Bitcoin(Singlesig): Add support for BIP-86 P2TR (Taproot) wallets." "- HWW: Add a new device JSON key ``"supports_p2tr"`` to indicate P2TR inputs can be signed by the device."
- "## Release 0.73.0 - 24-09-18" "- PSBT: Allow PSBT creation from singlesig descriptor watch-only sessions." "- GA_broadcast_transaction: Added support for broadcasting a PSBT/PSET directly. The PSBT is automatically finalized; callers no longer need to manually finalize and extract before sending a signed PSBT."
- "## Release 0.72.0 - 24-07-26" "- GA_register_user: Added support for creating watch only users by passing in watch only credentials." (as rendered by the fetch tool; the raw block for 0.72.0 lists GA_shutdown, metadata sync and GA_cache_control first).
- "## Release 0.70.0 - 24-02-01" "GA_psbt_from_json to create a PSBT/PSET from the result of GA_create_transaction/GA_blind_transaction." (as rendered).
- "## Release 0.68.0 - 23-09-27" "- GA_psbt_sign: Support signing BTC PSBTv0 and PSBTv2 in addition to Liquid PSETs." "- GA_psbt_sign: Support signing PSBT/PSET with hardware wallets." "GA_bcur_decode: Support parsing crypto-psbt, crypto-output and crypto-account." (last line as rendered).
- "## Release 0.0.59 - 2023-04-12" "- GA_login_user: add support for Electrum watch only. It is now possible to login with a list of xpubs or descriptors."
- "## Release 0.0.57 - 2022-11-23" "GA_get_subaccount: add user_path, core_descriptor, slip132_extended_pubkey." (as rendered).

S11. Parser libraries pinned by gdk (https://github.com/Blockstream/gdk/blob/master/subprojects/gdk_rust/Cargo.lock: `name = "miniscript" version = "12.2.0"`, `name = "bitcoin" version = "0.32.4"`; https://github.com/Blockstream/gdk/blob/master/subprojects/gdk_rust/gdk_common/Cargo.toml: `bitcoin = { version = "0.32", features = ["serde"] }`, `miniscript = "12.2"`)
- S11a. https://github.com/rust-bitcoin/rust-miniscript/blob/12.2.0/src/descriptor/checksum.rs line 35 to 56: "/// Checks and verifies the checksum if it is present and returns the descriptor string without the checksum." `let mut parts = s.splitn(2, '#'); let desc_str = parts.next().unwrap(); if let Some(checksum_str) = parts.next() { let expected_sum = desc_checksum(desc_str)?; if checksum_str != expected_sum { return Err(Error::BadDescriptor(format!("Invalid checksum '{}', expected '{}'", checksum_str, expected_sum))); } } Ok(desc_str)`. https://github.com/rust-bitcoin/rust-miniscript/blob/12.2.0/src/descriptor/mod.rs line 947: `let desc_str = verify_checksum(s)?;`
- S11b. https://github.com/rust-bitcoin/rust-bitcoin/blob/bitcoin-0.32.4/bitcoin/src/bip32.rs line 220 to 224: `impl FromStr for ChildNumber { ... let is_hardened = inp.chars().last().map_or(false, |l| l == '\'' || l == 'h');`
- S11c. https://github.com/rust-bitcoin/rust-miniscript/blob/12.2.0/src/descriptor/key.rs line 21 to 28: `pub enum DescriptorPublicKey { Single(SinglePub), XPub(DescriptorXKey<bip32::Xpub>), MultiXPub(DescriptorMultiXKey<bip32::Xpub>), }`

### green_android source

S12. https://github.com/Blockstream/green_android/blob/master/data/src/commonMain/kotlin/com/blockstream/data/utils/WatchOnlyDetector.kt
- Line 45: `val validPrefixes = listOf("xpub", "ypub", "zpub", "tpub", "upub", "vpub", "Ltub", "Mtub")`
- Line 65 to 68: `trimmed.contains("m/44'/0'/") || trimmed.contains("m/49'/0'/") || trimmed.contains("m/84'/0'/") || trimmed.contains("m/86'/0'/") || trimmed.contains("/44'/0'/") || trimmed.contains("/49'/0'/") || trimmed.contains("/84'/0'/") || trimmed.contains("/86'/0'/") -> Network.ElectrumMainnet`
- Line 80: `trimmed.contains("xpub") && isDescriptor(trimmed) -> Network.ElectrumMainnet`
- Line 92 to 107: `fun isDescriptor(input: String): Boolean { ... trimmed.contains("wpkh(") || trimmed.contains("wsh(") || trimmed.contains("pkh(") || trimmed.contains("sh(") || trimmed.contains("tr(") || ...`
- Line 128 to 130: `trimmed.startsWith("ur:crypto-", ignoreCase = true) -> InputType.BCUR` `isDescriptor(trimmed) -> InputType.DESCRIPTOR` `isValidXpub(trimmed) || looksLikeXpub(trimmed) -> InputType.XPUB`
- Line 157 to 158: `InputType.DESCRIPTOR -> { val credType = WatchOnlyCredentialType.CORE_DESCRIPTORS`

S13. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/models/onboarding/watchonly/WatchOnlySinglesigViewModel.kt
- Line 32: `override fun screenName(): String = "OnBoardWatchOnlySinglesig"`
- Line 73 to 75: `if (input.contains("(") || detectionResult.credentialType == WatchOnlyCredentialType.CORE_DESCRIPTORS) { isOutputDescriptors.value = true }`
- Line 123 to 146 (`importFile`): "// Coldcard" ... `name == AccountType.BIP86_TAPROOT.gdkType` ... `((inner["_pub"] as? JsonPrimitive) ?: (inner["xpub"] as? JsonPrimitive))` ... "// Electrum" `((json["keystore"] as? JsonObject)?.get("xpub") as? JsonPrimitive)`
- Line 152: `throw Exception("id_format_is_not_supported_or_no_data")`
- Line 162 to 176: `watchOnlyDescriptor.value.takeIf { it.isNotBlank() }?.split("|", "\n")` ... `val watchOnlyCredentials = if (isOutputDescriptors.value) { WatchOnlyCredentials(coreDescriptors = watchOnlyDescriptors) } else { WatchOnlyCredentials(slip132ExtendedPubkeys = watchOnlyDescriptors) }`
- Line 187 to 191: `createNewWatchOnlyWallet(network = network, persistLoginCredentials = false, watchOnlyCredentials = watchOnlyCredentials)`

S14. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/screens/onboarding/watchonly/WatchOnlySinglesigScreen.kt
- Line 66 to 71: `NavigateDestinations.Camera.getResult<ScanResult> { viewModel.postEvent(WatchOnlySinglesigViewModel.LocalEvents.AppendWatchOnlyDescriptor(value = it.result)) }`
- Line 112: `text = stringResource(Res.string.id_scan_or_paste_xpub_descriptor),`

S15. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/models/abstract/AbstractScannerViewModel.kt
- Line 61: `if ((isDecodeContinuous && scannedText.startsWith(prefix = "ur:", ignoreCase = true)) || bcurPartEmitter != null) {`
- Line 81: `barcodeScannerResult(ScanResult.from(bcurDecodedData))`
- Line 99: `barcodeScannerResult(ScanResult(scannedText))`
- https://github.com/Blockstream/green_android/blob/master/data/src/commonMain/kotlin/com/blockstream/data/data/ScanResult.kt line 7 to 10: `data class ScanResult(val result: String, val bcur: BcurDecodedData? = null)` ... `ScanResult(result = bcurDecodedData.simplePayload, bcur = bcurDecodedData)`
- https://github.com/Blockstream/green_android/blob/master/data/src/commonMain/kotlin/com/blockstream/data/gdk/data/BcurDecodedData.kt line 31 to 32: `val simplePayload: String get() = descriptors?.joinToString(",") ?: descriptor ?: psbt ?: data ?: ""`

S16. https://github.com/Blockstream/green_android/blob/master/data/src/commonTest/kotlin/com/blockstream/data/utils/WatchOnlyDetectorTest.kt
- Line 131: `assertEquals(Network.ElectrumMainnet, detector.detectNetwork("tr([73c5da0a/86'/0'/0']xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz/0/*)"))`
- Line 162: `assertTrue(detector.isDescriptor("tr(xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz/0/*)"))`
- Line 240 to 246: `val descriptor = "wpkh([73c5da0a/84'/0'/0']xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V/0/*)"` ... `assertEquals(WatchOnlyCredentialType.CORE_DESCRIPTORS, result.credentialType)`

S17. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/models/send/CreateTransactionViewModel.kt
- Line 404 to 406: `if (!transaction.isSweep() && (session.isWatchOnly.value || createPsbt)) { // Create PSBT ProcessedTransactionDetails(psbt = session.psbtFromJson(account.network, transaction).psbt)`
- Line 470 to 484: `if (it.psbt != null && it.txHash == null) { ... NavigateDestinations.JadeQR(greenWalletOrNull = greenWalletOrNull, operation = JadeQrOperation.Psbt(psbt = it.psbt!!, transactionConfirmation = transactionConfirmLook()), deviceModel = session.deviceModel)`
- Line 384 to 392: `if (psbt != null) { return@doAsync session.broadcastTransaction(network = network, broadcastTransaction = BroadcastTransactionParams(psbt = psbt, simulateOnly = !broadcast)) }`

S18. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/models/jade/JadeQRViewModel.kt
- Line 88 to 91: `data class Psbt constructor(val psbt: String, val transactionConfirmation: TransactionConfirmation? = null) : JadeQrOperation(askForJadeUnlock = true)`
- Line 265 to 276: `if (operation.askForJadeUnlock && session.isWatchOnlyValue) { ... NavigateDestinations.AskJadeUnlock(isOnboarding = false)`
- Line 280 to 286: `private fun preparePsbtRequest() { doAsync({ session.jadePsbtRequest((operation as JadeQrOperation.Psbt).psbt) }, onSuccess = { _urParts.value = it.parts })`
- Line 315 to 318: `private fun exportPsbt(saveToDevice: Boolean) { doAsync({ // Convert it to v0 for better compatibility val psbt = session.psbtToV0((operation as JadeQrOperation.Psbt).psbt)`
- Line 349 to 376 (`importPsbt`): `type = FileKitType.File(listOf("psbt"))` ... "// In binary format" `if (session.psbtIsBinary(psbt)) { Base64.Default.encode(psbt) } else { // In Base64 format (Jade)` ... `.takeIf { session.psbtIsBase64(it) } ?: throw Exception("Not a valid PSBT")`
- Line 437 to 442 (`setScanResult`): `is JadeQrOperation.Psbt -> { postSideEffect(SideEffects.Success(scanResult.result)) postSideEffect(SideEffects.NavigateBack()) }`
- Line 615 to 630: `val PsbtScenario = Scenario(listOf(StepInfo(title = Res.string.id_scan_qr_with_jade, message = Res.string.id_validate_the_transaction_details, step = 1, isScan = false), StepInfo(title = Res.string.id_scan_qr_on_jade, message = Res.string.id_validate_the_transaction_details, step = 2, isScan = true),), showStepCounter = true)`

S19. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/screens/jade/JadeQRScreen.kt
- Line 325 to 337: `if (step.isScan) { if (viewModel.operation is JadeQrOperation.Psbt) { GreenButton(text = stringResource(Res.string.id_import_from_file), ...) { viewModel.postEvent(JadeQRViewModel.LocalEvents.ImportPsbt) }`
- Line 355 to 357: `GreenButton(text = stringResource(Res.string.id_export_to_file),`

S20. https://github.com/Blockstream/green_android/blob/master/data/src/commonMain/kotlin/com/blockstream/data/gdk/GdkSession.kt
- Line 2573 to 2581: `suspend fun jadePsbtRequest(psbt: String): BcurEncodedData { val params = BcurEncodeParams(urType = "crypto-psbt", data = psbt) return bcurEncode(params) }`

S21. https://github.com/Blockstream/green_android/blob/master/data/src/commonMain/kotlin/com/blockstream/data/gdk/params/BcurEncodeParams.kt
- Line 12: `val data: String? = null, // cbor hex or base64 for crypto-psbt`
- Line 21 to 22: `@SerialName("max_fragment_len") val maxFragmentLen: Int = 50`

S22. https://github.com/Blockstream/green_android/blob/master/compose/src/commonMain/kotlin/com/blockstream/compose/screens/send/SendConfirmScreen.kt
- Line 110 to 114: `NavigateDestinations.JadeQR.getResult<JadeQRResult> { viewModel.postEvent(CreateTransactionViewModelAbstract.LocalEvents.BroadcastPsbtTransaction(psbt = it.result)`

S23. https://github.com/Blockstream/green_android/blob/master/CHANGELOG.md
- "## [5.1.0] - 2025-10-09" "- Watch-only wallets: Export or share unsigned psbt to a file and import signed psbt (pset support coming soon)" "- Refactored watch-only wallet setup with automatic network and format detection"
- "## [4.0.38] - 2024-11-13" "- Jade QR Mode"
- "## [4.0.25] - 2024-03-15" "- Enable Singlesig Liquid watch-only descriptors"
- "## [4.0.19] - 2023-11-20" "- Support Jade watch-only import by scanning BCUR animated QR codes"
- "## [4.0.3] - 2023-04-29" "- Enable watch-only for Singlesig Bitcoin"
- "## [3.8.0] - 2022-04-13" "Add Bitcoin Singlesig hardware wallet support" (as rendered)

### green_ios source

S24. https://github.com/Blockstream/green_ios/blob/master/gaios/WOFlow/ViewModels/WOViewModel.swift
- Line 71 to 75: `static func validateImport(text: String) throws -> WOImportInput { let isListOfPubKeys = ["xpub", "ypub", "zpub", "tpub", "upub", "vpub"].contains(text.prefix(4).lowercased()) let type: WOImportType = isListOfPubKeys ? .slip132 : .descriptor`
- Line 86 to 90: `for desc in keys { if allNetworks.filter({ Wally.isDescriptor(desc, for: $0) }).isEmpty { throw WOImportValidationError.invalidDescriptor(desc) } }`
- Line 92 to 95: `let credentials = Credentials(coreDescriptors: isListOfPubKeys ? nil : keys, slip132ExtendedPubkeys: isListOfPubKeys ? keys : nil)`

S25. https://github.com/Blockstream/green_ios/blob/master/core/Extensions/Wally.swift and https://github.com/Blockstream/green_ios/blob/master/greenaddress/Wally.swift
- core/Extensions/Wally.swift line 28 to 35: `public static func getNetwork(descriptor: String) -> NetworkId? { let networks: [NetworkId] = descriptor.starts(with: "ct") ? [.electrumLiquid, .electrumTestnetLiquid] : [.electrumMainnet, .electrumTestnet] for network in networks { if Wally.descriptorParse(descriptor, network: getWallyNetwork(network)) != nil { return network } } return nil }`
- greenaddress/Wally.swift line 351 to 353: `public static func descriptorParse(_ descriptor: String, network: UInt32) -> OpaquePointer? { ... if wally_descriptor_parse(descriptor, nil, network, WALLY_MS_IS_DESCRIPTOR, &wallyDescriptor) != WALLY_OK {`

S26. https://github.com/Blockstream/green_ios/blob/master/gaios/WOFlow/Controllers/WODetailsCompactViewController.swift
- Line 51: `lblHint2.text = "id_scan_or_paste_your_xpub_or".localized`
- Line 163 to 166: `@IBAction func btnScan(_ sender: Any) { let storyboard = UIStoryboard(name: "Scanner", bundle: nil) let vc = storyboard.instantiateViewController(identifier: "QrScannerViewController")`
- Line 198 to 207: `func didScan(value: ScanResult) { if let result = value.result { textView.text = result } else if let descriptor = value.bcur?.descriptor { textView.text = descriptor } else if let descriptors = value.bcur?.descriptors { textView.text = descriptors.joined(separator: "\n") }`
- Line 230 to 233: `if let keys = WOViewModel.parseGenericJson(content), !keys.isEmpty { textView.text = keys.joined(separator: ", ") } else if let keys = WOViewModel.parseElectrumJson(content), !keys.isEmpty {`

S27. https://github.com/Blockstream/green_ios/blob/master/gaios/Sendflow/ViewModels/SendTxConfirmViewModel.swift
- Line 131 to 133: `func enableExportPsbt() -> Bool { wm?.isWatchonly ?? false && network.singlesig && txType != .sweep && !importSignedPsbt }`
- Line 137 to 139: `func needExportPsbt() -> Bool { wm?.isWatchonly ?? false && network.singlesig && txType != .sweep && signedPsbt == nil }`
- Line 198 to 211: `func exportPsbt() async throws { ... unsignedPsbt = try await gdkNetworkBackend.getPsbt(tx: tx) let params = BcurEncodeParams(urType: "crypto-psbt", data: unsignedPsbt) guard let res = try await wm.bcurEncode(params: params) else { throw TransactionError.invalid(localizedDescription: "Invalid bcur") } bcurUnsignedPsbt = res }`
- Line 214 to 227: `func sendPsbt() async throws -> SendTransactionSuccess { ... guard let psbt = signedPsbt else { throw TransactionError.invalid(localizedDescription: "id_invalid_psbt".localized) } return try await backend.broadcastTransaction(broadcastTransaction: BroadcastTransactionParams(psbt: psbt, memo: transaction.memo, simulateOnly: false))`

S28. https://github.com/Blockstream/green_ios/blob/master/gaios/Sendflow/Controllers/SendTxConfirmViewController.swift
- Line 402 to 411: `func presentQRPsbtShowViewController() { let stb = UIStoryboard(name: "QRUnlockFlow", bundle: nil) if let vc = stb.instantiateViewController(withIdentifier: "QRPsbtShowViewController") as? QRPsbtShowViewController { vc.unsignedPsbt = viewModel.unsignedPsbt vc.qrBcur = viewModel.bcurUnsignedPsbt`
- Line 477 to 479: `@IBAction func btnSignViaQr(_ sender: Any) { exportPsbt() }`
- Line 498 to 506: `if position == 1 { if viewModel.needConnectHw() { presentConnectViewController() } else if viewModel.needExportPsbt() { exportPsbt() } else { send() }`
- Line 622 to 626: `extension SendTxConfirmViewController: QRPsbtAquireViewControllerDelegate { func didSign(psbt: String) { viewModel.signedPsbt = psbt send() }`

S29. https://github.com/Blockstream/green_ios/blob/master/gaios/HWFlow/Controllers/QRPsbtShowViewController.swift
- Line 41 to 47: `title = "id_scan_qr_with_jade".localized` ... `btnExport.setTitle("Export Transaction".localized, for: .normal)`
- Line 65 to 66: `if let bcur = qrBcur { qrCodeView.configure(frames: bcur.parts)`
- Line 115 to 124: "// Convert it to v0 for better compatibility" ... `if version == UInt32(WALLY_PSBT_VERSION_2) { try Wally.psbtSetVersion(wallyPsbt, version: UInt32(WALLY_PSBT_VERSION_0)) }`

S30. https://github.com/Blockstream/green_ios/blob/master/gaios/HWFlow/Controllers/QRPsbtAquireViewController.swift
- Line 37 to 41: `title = "id_scan_qr_with_jade".localized` ... `lblHint.text = "id_import_signed_transaction".localized` `btnImport.setTitle("id_import_from_file".localized, for: .normal)`
- Line 88 to 98 (`validatePsbt`): `if Wally.psbtIsBytes(psbt.bytes) { ... return try Wally.psbtToBase64(wallyPsbt) } else if let txt = String(data: psbt, encoding: .utf8) { ... if Wally.psbtIsBase64(txt) { return txt } } throw GaError.GenericError("id_invalid_psbt")`
- Line 122 to 126: `func didFindCode(_ code: ScanResult) { qrScanView.stopScanning() guard let psbt = code.bcur?.psbt, Wally.psbtIsBase64(psbt) else {` ... `message: "id_invalid_psbt".localized`

S31. https://github.com/Blockstream/green_ios/blob/master/CHANGELOG.md
- "## [5.1.0] - 2025-10-14" "- Export and import PSBT from files in watch-only wallets" "- Streamlined watch-only wallets import flow with automatic detection"
- "## [5.0.0] - 2025-05-27" "Allow access in watchonly mode for Jade users with singlesig accounts" (as rendered)
- "## [4.0.36] - 2024-10-23" "- QR mode for singlesig watch-only"
- "## [4.0.19] - 2023-11-22" "Scan BCUR animated qr code" and "Add watch-only import from Jade" (as rendered)
- "## [4.0.3] - 2023-04-28" "- Add import of watch-only wallets through xpubs and descriptors from QR codes or files" "- Allow import of Coldcard watch-only in generic json and electrum format"
- "## [3.7.6] - 2021-11-10" "Support for send to bech32m P2TR address types, available 144 blocks after Taproot" (as rendered)

S32. libwally-core, the C library behind `wally_descriptor_parse` used by green_ios (https://github.com/ElementsProject/libwally-core/blob/master/src/descriptor.c and https://github.com/ElementsProject/libwally-core/blob/master/src/bip32.c)
- descriptor.c line 2405 to 2406: `I_NAME("tr"), KIND_DESCRIPTOR_TR,`
- descriptor.c line 376: "* Checksum code adapted from bitcoin core: bitcoin/src/script/descriptor.cpp DescriptorChecksum()"; line 3175: `} else if (str[i] == '#') {` ... line 3183: "ret = WALLY_EINVAL; /* Garbage before checksum */"
- bip32.c line 80 to 82: `static bool is_hardened_indicator(char c, bool allow_upper, uint32_t *features) { if (c == '\'' || c == 'h' || (allow_upper && c == 'H')) {`
- The exact libwally commit that green_ios ships was not checked; master was read.

### green_qt source

S33. https://github.com/Blockstream/green_qt/blob/master/CHANGELOG.md (also https://github.com/Blockstream/green_qt/releases/tag/release_2.0.5)
- "## [3.5.0] - 2026-08-10" "- Jade QR Connect for connecting and unlocking Jade over QR codes" "- Airgapped signing with Jade on watch-only wallets" "- Updated GDK to 0.77.7"
- "## [2.0.10] - 2024-09-02" "### Fixed:" "- Login with singlesig watch-only"
- "## [2.0.5] - 2024-05-08" "- Add or import singlesig watch-only wallet" "- New watch-only section in wallet settings dialog" "- Expose extended public keys and output descriptors of singlesig accounts"

S34. https://github.com/Blockstream/green_qt/blob/master/qml/SinglesigWatchOnlyAddPage.qml
- Line 70: `text: selector.index === 0 ? qsTrId('id_scan_or_paste_your_extended') : qsTrId('id_scan_or_paste_your_public')`
- Line 78 to 81: `onTextChanged: { error_badge.clear() selector.index = keys_field.text.includes('(') ? 1 : 0 }`
- Line 94 to 98: `if (selector.index === 0) { controller.loginExtendedPublicKeys(keys_field.text) } else { controller.loginDescriptors(keys_field.text) }`
- Line 152 to 160: `Option { text: qsTrId('id_xpub') enabled: !self.network.liquid && !keys_field.text.includes('(')` ... `Option { text: qsTrId('id_descriptor')`
- Line 230 to 239: `ScannerPopup { id: scanner_popup onCodeScanned: (code) => { text_area.text = code } onBcurScanned: (result) => { if (result.ur_type === 'crypto-account') { text_area.text = result.descriptors.join('\n') } } }`

S35. https://github.com/Blockstream/green_qt/blob/master/src/watchonlylogincontroller.cpp
- Line 172 to 176: `m_extended_pubkeys = input.split('\n', Qt::SkipEmptyParts); setValid(true); login(new LoginTask(QJsonObject{{ "slip132_extended_pubkeys", QJsonArray::fromStringList(m_extended_pubkeys) }}, QJsonObject{}, session));`
- Line 186 to 191: `m_core_descriptors = input.split('\n', Qt::SkipEmptyParts); QJsonObject details{{ "core_descriptors", QJsonArray::fromStringList(m_core_descriptors) }}; setValid(true); login(new LoginTask(details, QJsonObject{}, session));`
- Line 205 to 210 (`parseFile`): `if (content.value("chain").toString() == "BTC") { ... if (name != "p2pkh" && name != "p2sh-p2wpkh" && name != "p2wpkh" && name != "p2tr") continue;` and line 219: `} else if (content.value("wallet_type").toString() == "standard") {`

S36. https://github.com/Blockstream/green_qt/blob/master/qml/util.js
- Line 512 to 519: `function canAirgapSend(context) { if (!context?.watchonly || !context.wallet) return false const login = context.wallet.login if (!login?.coreDescriptors?.length) return false const network = login.network if (!network?.electrum || network.liquid) return false return true }`
- Line 521 to 524: `function isSendEnabled(context) { if (!context?.watchonly) return true return canAirgapSend(context) }`

S37. https://github.com/Blockstream/green_qt/blob/master/qml/SendConfirmPage.qml
- Line 281 to 287: `text: UtilJS.canAirgapSend(self.context) ? qsTrId('id_sign_transaction_via_qr') : qsTrId('id_confirm_transaction') onClicked: { if (UtilJS.canAirgapSend(self.context)) { self.pushPage(airgap_unlock_page) } else { controller.sign() } }`

S38. https://github.com/Blockstream/green_qt/blob/master/src/airgappedsigncontroller.cpp
- Line 55: `auto psbt = new PsbtFromJsonTask(m_transaction, session);`
- Line 63 to 68: `const QJsonObject details{ { "ur_type", "crypto-psbt" }, { "data", m_unsigned_psbt }, { "max_fragment_len", 40 }, }; auto encode = new EncodeBCURTask(details, session);`
- Line 100: `QDateTime::currentDateTime().toString("yyyyMMddhhmmss") + ".psbt";`
- Line 131 to 142: `QJsonObject details{ { "psbt", psbt }, { "simulate_only", false }, };` ... `auto broadcast = new BroadcastTransactionTask(details, session);`
- Line 167 to 174 (`parsePsbtFile`): `static const QByteArray psbt_magic = QByteArray::fromHex("70736274ff"); if (data.startsWith(psbt_magic)) { return QString::fromLatin1(data.toBase64()); } auto text = QString::fromLatin1(data).trimmed(); text.remove('\n').remove('\r'); return text;`

S39. https://github.com/Blockstream/green_qt/blob/master/qml/AirgappedExportPage.qml
- Line 59: `text: qsTrId('id_scan_qr_with_jade')`
- Line 71: `text: 'On Jade, scan QR and validate transaction details'`
- Line 85 to 89: `Timer { interval: 250 running: self.controller.parts.length > 0 repeat: true onTriggered: qrcode.index = (qrcode.index + 1) % self.controller.parts.length }`
- Line 98: `text: self.controller.parts.length > 0 ? self.controller.parts[qrcode.index].toUpperCase() : ''`
- Line 161 to 163: `text: qsTr('Export to file') enabled: self.controller.unsignedPsbt.length > 0 onClicked: self.controller.savePsbtToFile()`

S40. https://github.com/Blockstream/green_qt/blob/master/qml/AirgappedImportPage.qml and https://github.com/Blockstream/green_qt/blob/master/qml/AirgappedUnlockPage.qml
- AirgappedImportPage.qml line 74 to 78: `onBcurScanned: (result) => { if (result.ur_type === 'crypto-psbt') { self.controller.importSignedPsbt(result.psbt) } }`
- AirgappedImportPage.qml line 97 and 104 to 111: `text: qsTrId('id_import_from_file')` ... `const psbt = self.controller.parsePsbtFile(file_dialog.selectedFile) if (psbt.length === 0) { self.pushPage(error_page, { error: qsTr('The selected file does not contain a valid PSBT.'), }) return } self.controller.importSignedPsbt(psbt)`
- AirgappedUnlockPage.qml line 14 and 55 to 60: `title: 'Unlock Jade'` ... `JadeUnlockSignView { ... onAlreadyUnlocked: self.pushExport() onUnlockRequested: self.pushQrUnlock() }`

## Not found

1. No help-center page or release note names a non-Jade QR signer. All screen labels in the export and import pages say "Scan QR with Jade" (S19 string ids, S29, S30, S39, S40). Whether the Android and iOS "AskJadeUnlock" step (S18 line 265 to 276) can be skipped by a user with a non-Jade signer is unverified. Desktop has an "already unlocked" path that goes straight to the export page (S40).
2. Ledger and Trezor: this research did not verify their support list from a primary source. green_android 3.8.0 says "Add Bitcoin Singlesig hardware wallet support" without naming devices (S23). No source shows a Ledger or Trezor QR flow.
3. The Green app version that first offered a Taproot (BIP86) account type in the UI. gdk added it in 0.75.0 (S10). The Android and iOS CHANGELOG files have no matching entry. The Android code has `AccountType.BIP86_TAPROOT("p2tr")` and `ChooseAccountTypeViewModel` lists it; the iOS code has `case bip86Taproot = "p2tr"`. Unverified which app release shipped it.
4. The Android version that first showed the unsigned PSBT as an animated QR for a singlesig watch-only wallet. The nearest entry is 4.0.38 "Jade QR Mode" (2024-11-13) (S23). The iOS entry 4.0.36 "QR mode for singlesig watch-only" (2024-10-23) is explicit (S31).
5. End-to-end tests. No app was run in this research. Every verdict comes from documentation and source reading.
6. Android camera read-back of a signed PSBT that is a plain base64 QR (not BC-UR). The scanner passes any text through as the PSBT (S15, S18, S22); whether gdk then accepts it is unverified.
7. Android handling of `ur:crypto-account` descriptors joined with "," (S15 `simplePayload`) against a splitter that uses only "|" and "\n" (S13 line 163). Unverified; not relevant to Corky's plain-text QR.
8. The libwally commit shipped inside green_ios; master was read (S32).
9. The old `hc/en-us/articles/19340800530713` and `20108354124185` URLs returned 404 through the fetch tool on 2026-09-04. The `blockstream-app` and `blockstream-jade` paths were used instead (S1, S2).
