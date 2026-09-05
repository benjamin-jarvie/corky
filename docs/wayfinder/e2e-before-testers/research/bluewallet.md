# BlueWallet: import of Corky descriptors and air-gapped PSBT signing

Research date: 2026-09-04. Newest BlueWallet release: 8.0.1 (2026-07-21).
Code quotes come from `master` on 2026-09-04. The descriptor parser, the watch-only `init()` logic and the UR module are byte-identical in the `8.0.1` tag (checked with `diff`).

## Verdict table

| # | Question | Verdict | Confidence | Source |
|---|----------|---------|------------|--------|
| 1 | Import a single-sig watch-only wallet from `wpkh([fp/84h/0h/0h]xpub.../0/*)#checksum`, typed, pasted or as a plain-text QR | Yes. `AbstractWallet.setSecret()` has a branch for `wpkh(`, `pkh(`, `sh(` and `tr(`. It reads the fingerprint and the path, converts `h` to `'`, converts the xpub to a zpub, and sets `segwitType = 'p2wpkh'`. `WatchOnlyWallet.init()` then builds an `HDSegwitBech32Wallet`. The text after the first `/` behind the xpub is dropped, so `/0/*)` and `#checksum` do no harm. An integration test imports a Coldcard descriptor with `/<0;1>/*` and a checksum. The screen is Add wallet, Import wallet (`screen/wallets/ImportWallet.tsx`). Text goes to `startImport()` in `class/wallet-import.ts`, step `watch only`. A scanned plain-text QR reaches the same text field. Other accepted forms: bare xpub, ypub, zpub; `[fp/84h/0h/0h]xpub`; `ur:crypto-account`, `ur:crypto-hdkey`, `ur:crypto-output`, `ur:crypto-multi-accounts`; Coldcard Electrum JSON; Coldcard `new-wasabi.json`; Keystone or Cobo JSON array; generic JSON with `bip86.desc` and similar. | High for the `wpkh(` form with `/<0;1>/*` and a checksum (test). The exact `/0/*` suffix has no test; the parser drops it the same way (unverified by a test). | S1, S2, S3, S4, S5, S6 |
| 2 | Taproot single-sig watch-only import (`tr(...)` or a BIP86 xpub) | Yes. `tr(` sets `segwitType = 'p2tr'` and keeps the plain xpub. `init()` builds an `HDTaprootWallet`. Unit tests import `tr([97311f91/86'/0'/0']xpub.../<0;1>/*)` and `[97311f91/86'/0'/0']xpub...`, assert `bc1p` addresses, and create a PSBT. A bare xpub with no path gives a legacy BIP44 wallet, so Corky must send the `tr(` wrapper or the `[fp/86h/0h/0h]` prefix. Wallet export shows taproot watch-only as a `tr(...)` descriptor. | High. No test uses `tr(...)#checksum`; the parser handles the checksum the same way as for `wpkh(` (unverified by a test). | S1, S2, S7, S8, S9, S18 |
| 3 | Show the unsigned PSBT as an animated QR and read the signed PSBT back with the camera | Yes. Precondition: the switch "Use with Hardware Wallet" on the Wallet details screen. Send then opens the screen `PsbtWithHardwareWallet` (`screen/send/psbtWithHardwareWallet.tsx`). It renders `<DynamicQRCode value={psbt.toHex()}>`. `encodeUR()` in `blue_modules/ur/index.js` encodes the PSBT as `ur:crypto-psbt` (BC-UR v2, `CryptoPSBT.toUREncoder`), 175 bytes per fragment, one frame per second. BBQr is used only if the wallet was imported from a BBQr scan, or via the hidden "Force use BBQR" control. Legacy UR v1 (`ur:bytes`) is used only if the legacy URv1 setting is on. The button "Scan Signed Transaction" opens `ScanQRCode`. `onBarCodeRead()` routes `UR:CRYPTO-PSBT` and BBQr `B$` to `BlueURDecoder`, legacy `UR:BYTES` to `decodeUR`, and also accepts Electrum base43 and plain base64. The result returns to `PsbtWithHardwareWallet.onBarScanned()`, which calls `wallet.combinePsbt()` (combine, finalize, extract) and shows a broadcast button. A file path exists too: "Open Signed Transaction". | High | S10, S11, S12, S13, S14, S15, S16, S17 |
| 4 | Version that introduced each capability | Bracket form `[fp/path]xpub`: v5.5.1 (2020-07-18). Descriptors with xpub for BIP84/BIP49: v6.3.2 (2022-11-23). Single-sig `wpkh(` descriptor from Sparrow: v6.4.9 (2023-10-17). Taproot BIP86 with `tr(` descriptors and taproot watch-only: v7.2.2 (2025-11-24). Animated QR PSBT: v5.4.4 (2020-07-01). PSBT for all HD watch-only wallets: v6.1.0 (2021-05-03). UR v2 QR codes: v6.1.9 (2021-07-10). BBQr: v7.2.6 (2026-02-23). BC-UR v2 scanning of `crypto-hdkey` and `crypto-multi-accounts`: 8.0.1 (2026-07-21). | Medium. Release notes are terse. No release note names `ur:crypto-psbt` directly. | S19 to S29 |

## Details per question

### Q1: single-sig descriptor import

The code path:

1. Screen `ImportWallet.tsx`. The user pastes text or taps the scan button. Both call `importMnemonic(text)`, which navigates to `ImportWalletDiscovery` with `importText`.
2. `ImportWalletDiscovery.tsx` line 119 calls `startImport(importText, ...)`.
3. `class/wallet-import.ts` lines 495-498: `yield { progress: 'watch only' }; const wo1 = new WatchOnlyWallet(); wo1.setSecret(text); if (wo1.valid()) {`.
4. `class/wallets/abstract-wallet.ts` lines 238-279: the descriptor branch. It computes `xpubIndex`, reads `fpAndPath` from the square brackets, and sets `xpub = this.secret.substring(xpubIndex).replace(/[()]/g, '').split('/')[0]`. For `wpkh(` it sets `this.segwitType = 'p2wpkh'` and `this.secret = this._xpubToZpub(xpub)`.
5. `class/wallets/watch-only-wallet.ts` line 82-86: `// Check script type first (most reliable - parsed from descriptor)` then `HDSegwitBech32Wallet` for `p2wpkh`.

Facts that matter for Corky:

- BlueWallet does not validate the descriptor checksum. It drops it.
- BlueWallet accepts `h` and `'` in the path. The Coldcard fixture uses `84h`.
- BlueWallet stores the zpub, not the xpub, for `wpkh(`.
- The import screen text says: "Please enter your seed words, public key, WIF, or anything you've got."
- A plain-text QR of the descriptor works because `ScanQRCode.onBarCodeRead()` passes unknown text to the caller unchanged (lines 197-226).

### Q2: taproot

- `abstract-wallet.ts` lines 264-266: `if (this.secret.startsWith('tr(')) { this.segwitType = 'p2tr'; this.secret = xpub; }`.
- `watch-only-wallet.ts` lines 83-84: `if (this.segwitType === 'p2tr') { hdWalletInstance = new HDTaprootWallet();`.
- `watch-only-wallet.ts` lines 92-95: the fallback `else if (this._derivationPath?.startsWith("m/86'"))` also gives `HDTaprootWallet`, so `[fp/86h/0h/0h]xpub` works without the `tr(` wrapper.
- `watch-only-wallet.ts` lines 101-103: a bare `xpub` gives `HDLegacyP2PKHWallet`. Corky must not export a bare xpub for taproot.
- `hd-taproot-wallet.ts` lines 95-128: `_addPsbtInput()` writes `tapBip32Derivation` with the master fingerprint and `tapInternalKey`.

### Q3: PSBT QR out, signed PSBT in

Preconditions in code:

- `watch-only-wallet.ts` line 45-47: `allowSend() { return this.useWithHardwareWalletEnabled() && this.isHd() && this._hdWalletInstance!.allowSend(); }`.
- `WalletDetails.tsx` line 642-646 shows the switch only for `wallet.type === WatchOnlyWallet.type && wallet.isHd()`. The label is `details_use_with_hardware_wallet` = "Use with Hardware Wallet".
- `hd-taproot-wallet.ts` line 134-136: `allowSend() { return true; }`.

Encoding:

- `DynamicQRCode.tsx` line 49-51: `capacity = 175`, `this.fragments = encodeUR(value, capacity, walletID ?? null);`. Line 116: `setInterval(this.moveToNextFragment, 1000)`.
- `ur/index.js` line 90-115: `forceProtocol = 'auto'` ends in `useURv1 ? encodeURv1(value, capacity) : encodeURv2(value, capacity)`. `useURv1` starts as `false`.
- `ur/index.js` line 184-188: `Psbt.fromHex(str); const data = Buffer.from(str, 'hex'); const cryptoPSBT = new CryptoPSBT(data); const encoder = cryptoPSBT.toUREncoder(len);`. This is `ur:crypto-psbt`.
- BBQr: `ur/index.js` line 95: `if (forceProtocol === 'BBQR' || (walletID && useBBQRWalletIDs.includes(walletID)))`. `StorageProvider.tsx` line 474-479 adds a wallet to that list when the import scan was BBQr. A wallet imported from a plain-text QR uses UR v2.

Decoding:

- `ScanQRCode.tsx` line 169-171: `if (ret.data.toUpperCase().startsWith('UR:CRYPTO-PSBT')) { return _onReadUniformResourceV2(ret.data); }`. Line 185-188: `B$` sets `useBBQRRef.current = true` and uses the same decoder. Line 190-198: multi-part `UR:BYTES` goes to the v2 decoder, other `UR` text goes to the v1 decoder.
- `ur/index.js` line 391-393: `if (decoded.type === 'crypto-psbt') { const cryptoPsbt = CryptoPSBT.fromCBOR(decoded.cbor); return cryptoPsbt.getPSBT().toString('base64'); }`.
- `psbtWithHardwareWallet.tsx` line 233-239 reads `route.params.onBarScanned`, then `onBarScanned()` line 87-88 calls `_combinePSBT(data)`, which calls `wallet.combinePsbt(psbt, receivedPSBT)`.
- `abstract-hd-electrum-wallet.ts` line 1219-1233: `combinePsbt()` calls `final1.combine(final2)` then `finalizeAllInputs().extractTransaction()`.

Edge in code, unverified in a device test: `psbtWithHardwareWallet.tsx` line 82-86 treats scanned data with no `+` and no `=` as a raw transaction hex. A base64 PSBT with no `+` and no `=` padding would be misread. This is rare.

### Q4: versions

See the Sources section, S19 to S29, for the quoted release lines.

## Sources

S1. `class/wallets/abstract-wallet.ts` (raw file fetched from https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallets/abstract-wallet.ts; identical block in tag 8.0.1)
> `// is it output descriptor?`
> `if (`
> `  this.secret.startsWith('wpkh(') ||`
> `  this.secret.startsWith('pkh(') ||`
> `  this.secret.startsWith('sh(') ||`
> `  this.secret.startsWith('tr(')`
> `) {`
> `  const xpubIndex = Math.max(this.secret.indexOf('xpub'), this.secret.indexOf('ypub'), this.secret.indexOf('zpub'));`
> `  const xpub = this.secret.substring(xpubIndex).replace(/[()]/g, '').split('/')[0];`
> `  const path = 'm' + fpAndPath.substring(pathIndex).replace(/h/g, "'");`
> `  if (this.secret.startsWith('tr(')) {`
> `    this.segwitType = 'p2tr';`
> `    this.secret = xpub;`
> `  } else if (this.secret.startsWith('wpkh(')) {`
> `    this.segwitType = 'p2wpkh';`
> `    this.secret = this._xpubToZpub(xpub);`

S2. `class/wallets/watch-only-wallet.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallets/watch-only-wallet.ts)
> `// Check script type first (most reliable - parsed from descriptor)`
> `if (this.segwitType === 'p2tr') {`
> `  hdWalletInstance = new HDTaprootWallet();`
> `} else if (this.segwitType === 'p2wpkh') {`
> `  hdWalletInstance = new HDSegwitBech32Wallet();`
> `// Fallback to path-based detection (for bare [fingerprint/path]xpub without descriptor wrapper)`
> `else if (this._derivationPath?.startsWith("m/86'")) {`
> `// Final fallback to xpub prefix (legacy behavior for bare xpub/ypub/zpub)`
> `else if (this.secret.startsWith('xpub')) {`
> `  hdWalletInstance = new HDLegacyP2PKHWallet();`
> `allowSend() {`
> `  return this.useWithHardwareWalletEnabled() && this.isHd() && this._hdWalletInstance!.allowSend();`
> `isHd() {`
> `  return this.secret.startsWith('xpub') || this.secret.startsWith('ypub') || this.secret.startsWith('zpub');`
> `* unsinged PSBT to be used with HW wallet (or other external signer)`
> `return this._hdWalletInstance.createTransaction(utxos, targets, feeRate, changeAddress, sequence, true, masterFingerprint);`

S3. `class/wallet-import.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallet-import.ts)
> `// maybe its a watch-only address?`
> `yield { progress: 'watch only' };`
> `const wo1 = new WatchOnlyWallet();`
> `wo1.setSecret(text);`
> `if (wo1.valid()) {`
> `// is it BC-UR payload with multiple accounts?`
> `if (account.ExtPubKey && account.MasterFingerprint && account.AccountKeyPath) {`
> `// is it a generic JSON with multiple accounts?`
> `if (json.chain === 'BTC' && json.xfp) {`
> `  for (const account of ['bip86', 'bip84', 'bip49', 'bip44']) {`
> `    if (json[account] && json[account].desc) {`

S4. `tests/integration/import.test.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/tests/integration/import.test.ts)
> `it('can import coldcard mk4 descriptor.txt', async () => {`
> `fs.readFileSync('tests/unit/fixtures/coldcardmk4/descriptor.txt').toString('utf8'),`
> `assert.strictEqual(store.state.wallets[0].getDerivationPath(), "m/84'/0'/0'");`

S5. `tests/unit/fixtures/coldcardmk4/descriptor.txt` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/tests/unit/fixtures/coldcardmk4/descriptor.txt)
> `wpkh([086ee178/84h/0h/0h]xpub6CqWTnie1ut9ZDD9xDeCn1VXk83VdAPSm8ZPfPNbb8w5z1e7jyy8zuX721uKj8u4GNxXqAevgEZjciUansnyz6ZhnSKyQWZwx2dpAxuCuDe/<0;1>/*)#mthwej8w`

S6. `screen/wallets/ImportWallet.tsx` and `screen/wallets/ImportWalletDiscovery.tsx` and `loc/en.json` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/wallets/ImportWallet.tsx, https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/wallets/ImportWalletDiscovery.tsx, https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/loc/en.json)
> `navigation.navigate('ImportWalletDiscovery', {` / `importText: text,`
> `<AddressInputScanButton type="link" onChangeText={onBarScanned} testID="ScanImport" />`
> `task.current = startImport(importText, askPassphrase, searchAccounts, isElectrumDisabled, onProgress, onWallet, onPassword);`
> `"import_explanation": "Please enter your seed words, public key, WIF, or anything you've got. BlueWallet will do its best to guess the correct format and import your wallet.",`
> `"import_scan_qr": "Scan or import a file",`
> `"import_success_watchonly": "Your wallet has been successfully imported. WARNING: This is a watch-only wallet, you can NOT spend from it.",`

S7. `tests/unit/watch-only-wallet.test.js` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/tests/unit/watch-only-wallet.test.js)
> `it('can import wallet descriptor for BIP84, but with xpub instead of zpub', async () => {`
> `'[dafedf1c/84h/0h/0h]xpub6DFMZMLizqqnyyHoWTG7qzmCR1irpiDEGT4JQX7ubeoFtV838ABKPfgAPQbM1TEekEyCuJF1BrmnA7JPrnzqi2VbycD3tVE3v5xsDQqYA3A',`
> `it('can import BIP86 (taproot) wallet descriptor', async () => {`
> `"tr([97311f91/86'/0'/0']xpub6C85eQDGy5NKEqCPnrnf4QcvxQCzRiTZFTa6YfuDU1hSQGWQHf6QBHogKXaS8hUhtvk6ND4btTdiWic26UKrk1pWrU4CQGrQoGxd6DP33Sw/<0;1>/*)",`
> `"[97311f91/86'/0'/0']xpub6C85eQDGy5NKEqCPnrnf4QcvxQCzRiTZFTa6YfuDU1hSQGWQHf6QBHogKXaS8hUhtvk6ND4btTdiWic26UKrk1pWrU4CQGrQoGxd6DP33Sw",`
> `assert.ok(w._getExternalAddressByIndex(0).startsWith('bc1p'), 'not taproot address, got: ' + w._getExternalAddressByIndex(0));`
> `it('can import taproot descriptor with non-BIP86 path', async () => {`
> `it('can import wpkh descriptor with custom path', async () => {`
> `it('can import BIP86 (taproot) wallet descriptor and create transaction', async () => {`
> `const { psbt } = w.createTransaction(utxos, [{ address: '13HaCAB4jf7FYSZexJxoczyDDnutzZigjS' }], 1, w._getInternalAddressByIndex(0));`
> `it('v2: can decodeUR() PSBT', () => {`
> `'UR:CRYPTO-PSBT/HKADGSJOJKIDJYZMADAEJYAOAEAEAEADWKMTGWJPPFGMCKJLKPNDNDBWAHBEAXCNFHPKRHUTPMGTBAFNWEBTLBECKENNBDJKADAEAEAEAEZMZMZMZMAONBLNADAEAEAEAEAECFKOPTBBCFBGNTGUVAEHNDPECFUYNBHKRNPMCMJNYTBKROYKLOPSVOHTADAEAEAEAEAECMAEBBWEWETAYKBETTTDISVDGYTTGMEHLSDMASFYPSPYDRAEAEAEAEAEADADCTLNZMAOAEAEAEAEAECMAEBBJYLSWNATMWIOEMHTPMFXCWMTGLZSTPVSCMWDLBKKADAYJEAOFLDYFYAOCXGYFNRKKPVYWFWEGLFZTYLDSFWNNEFGCTIMPEFHWMCWNNMTCHHTMYGRSOFRLODSAEAOCXKTKBHDNDCEFLMEBYOESETTIOAACHAXZMVWDNRDHEISHKETAMCHDSEOFXIYDECPHGADCLAOHSHHTYMTPAWKLNFYESCWNBKSWDVDNNYNMNCFLOFNTTWTNYFYNTHERORKDKQDWEGWAEAECPAOAXIHWEMNLPPDZTKSTEJLBNMOWFCSVYKNMNHKHFGDRNKELFRTSFCTSRZSSGJZAXRNHYCSADWMTNKIGHAEAELAAEAEAELAAEAEAELAADAEAEAELNAEAEAEAESSAOMKSP',`

S8. `class/wallets/hd-taproot-wallet.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallets/hd-taproot-wallet.ts)
> `export class HDTaprootWallet extends AbstractHDElectrumWallet {`
> `public readonly segwitType = 'p2tr';`
> `static readonly derivationPath = "m/86'/0'/0'";`
> `// returning regular xpub since industry standard is to use regular xpubs for Taproot wallets without any`
> `_addPsbtInput(psbt: Psbt, input: CoinSelectReturnInput, sequence: number, masterFingerprintBuffer: Buffer) {`
> `tapBip32Derivation: [` / `tapInternalKey: pubkey,`
> `allowSend() {` / `return true;`

S9. `class/wallet-descriptor.ts` and `screen/wallets/WalletExport.tsx` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallet-descriptor.ts, https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/wallets/WalletExport.tsx)
> `case path.startsWith("m/86'"):`
> `  return \`tr([${fpHex.toLowerCase()}/${path.replace('m/', '')}]${xpub})\`;`
> `// for taproot watch-only HD we dont just show xpub, we show wallet descriptor`
> `secret = WalletDescriptor.getDescriptor(fp, path, secret);`

S10. `screen/wallets/WalletDetails.tsx` and `loc/en.json` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/wallets/WalletDetails.tsx)
> `{wallet.type === WatchOnlyWallet.type && wallet.isHd && wallet.isHd() && (`
> `title={loc.wallets.details_use_with_hardware_wallet}`
> `wallet.setUseWithHardwareWalletEnabled(value);`
> `"details_use_with_hardware_wallet": "Use with Hardware Wallet",`

S11. `screen/send/SendDetails.tsx` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/send/SendDetails.tsx)
> `if (wallet?.type === WatchOnlyWallet.type) {`
> `  // watch-only wallets with enabled HW wallet support have different flow. we have to show PSBT to user as QR code`
> `  // so he can scan it and sign it. then we have to scan it back from user (via camera and QR code), and ask`
> `  // user whether he wants to broadcast it`
> `  navigation.navigate('PsbtWithHardwareWallet', {`

S12. `screen/send/psbtWithHardwareWallet.tsx` and `loc/en.json` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/send/psbtWithHardwareWallet.tsx)
> `{psbt && <DynamicQRCode value={psbt.toHex()} ref={dynamicQRCode} walletID={walletID} />}`
> `title={loc.send.psbt_tx_scan}`
> `navigation.navigate('ScanQRCode', {` / `showFileImportButton: true,`
> `return wallet.combinePsbt(psbt, receivedPSBT);`
> `if (data.indexOf('+') === -1 && data.indexOf('=') === -1 && data.indexOf('=') === -1) {` / `// this looks like NOT base64, so maybe its transaction's hex`
> `"psbt_this_is_psbt": "This is a Partially Signed Bitcoin Transaction (PSBT). Please finish signing it with your hardware wallet.",`
> `"psbt_tx_scan": "Scan Signed Transaction",`
> `"psbt_tx_open": "Open Signed Transaction",`

S13. `components/DynamicQRCode.tsx` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/components/DynamicQRCode.tsx)
> `const { value, capacity = 175, hideControls = true, walletID } = this.props;`
> `this.fragments = encodeUR(value, capacity, walletID ?? null);`
> `intervalHandler: setInterval(this.moveToNextFragment, 1000),`
> `this.fragments = encodeUR(value, capacity, walletID ?? null, 'BBQR');`
> `<Text style={animatedQRCodeStyle.text}>Force use BBQR</Text>`

S14. `blue_modules/ur/index.js` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/blue_modules/ur/index.js; identical in tag 8.0.1)
> `let useURv1 = false;`
> `* @param forceProtocol {'auto' | 'BBQR' | 'URv2' = 'auto'}`
> `if (forceProtocol === 'BBQR' || (walletID && useBBQRWalletIDs.includes(walletID))) {`
> `// auto (aka default):`
> `return useURv1 ? encodeURv1(value, capacity) : encodeURv2(value, capacity);`
> `Psbt.fromHex(str); // will throw if not PSBT hex`
> `const cryptoPSBT = new CryptoPSBT(data);`
> `const encoder = cryptoPSBT.toUREncoder(len);`
> `if (decoded.type === 'crypto-psbt') {` / `return cryptoPsbt.getPSBT().toString('base64');`
> `if (decodedBbqr.fileType === 'P') {` / `return uint8ArrayToBase64(decodedBbqr.raw);`

S15. `screen/send/ScanQRCode.tsx` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/screen/send/ScanQRCode.tsx)
> `if (ret.data.toUpperCase().startsWith('UR:CRYPTO-PSBT')) {` / `return _onReadUniformResourceV2(ret.data);`
> `if (ret.data.toUpperCase().startsWith('UR:CRYPTO-HDKEY')) {`
> `if (ret.data.toUpperCase().startsWith('B$')) {` / `useBBQRRef.current = true;`
> `if (ret.data.toUpperCase().startsWith('UR')) {` / `return _onReadUniformResource(ret.data);`
> `// is it base43? stupid electrum desktop`
> `navigation.dispatch(StackActions.popTo(launchedBy, { onBarScanned: data }, { merge: true }));`

S16. `class/wallets/abstract-hd-electrum-wallet.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/class/wallets/abstract-hd-electrum-wallet.ts)
> `combinePsbt(base64one: string | Psbt, base64two: string | Psbt) {`
> `final1.combine(final2);`
> `extractedTransaction = final1.finalizeAllInputs().extractTransaction();`

S17. `components/Context/SettingsProvider.tsx`, `components/Context/StorageProvider.tsx`, `helpers/scan-qr.ts` (https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/components/Context/SettingsProvider.tsx, https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/components/Context/StorageProvider.tsx, https://raw.githubusercontent.com/BlueWallet/BlueWallet/master/helpers/scan-qr.ts)
> `isLegacyURv1Enabled: boolean;` / `await setUseURv1();`
> `if (getScanWasBBQR()) {` / `await setWalletIdMustUseBBQR(w.getID());`
> `// this is not a flag of most recent BBQR format, its a flag if in a lifetime or app there was a BBQR scan`

S18. Pull request #8146 "Add taproot wallet bip86", merged 2025-11-10 (https://github.com/BlueWallet/BlueWallet/pull/8146)
> "Support output descriptors parsing (`tr(...)`) and add `WalletDescriptor` helper; generate descriptors for taproot watch-only exports."
> "Watch-only: Initialize HD watch-only as Taproot when xpub + BIP86 path; support descriptor imports; expose p2tr PSBT fields."

S19. Pull request #8166 "FIX: hw wallets with taproot integration", merged 2025-11-17 (https://github.com/BlueWallet/BlueWallet/pull/8166)
> Summary as fetched: "Updated `class/wallets/watch-only-wallet.ts` to select `HDTaprootWallet` when derivation path starts with `m/86'` (BIP86)". The fetch tool summarized this PR; the wording is not verbatim.

S20. Release v7.2.2, 2025-11-24 (https://github.com/BlueWallet/BlueWallet/releases/tag/v7.2.2)
> `* Add taproot wallet bip86 by @Overtorment in https://github.com/BlueWallet/BlueWallet/pull/8146`
> `* FIX: hw wallets with taproot integration by @Overtorment in https://github.com/BlueWallet/BlueWallet/pull/8166`

S21. Release v5.5.1, 2020-07-18 (https://github.com/BlueWallet/BlueWallet/releases/tag/v5.5.1)
> `* ADD: support importing watch-only in bitcoincore format fingerprint/derivationxpub (wallet descriptors)`

S22. Release v6.3.2, 2022-11-23 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.3.2)
> `* FIX: import wallet descriptors for BIP84 & BIP49, but with xpubs (closes #4993)`

S23. Release v6.4.9, 2023-10-17 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.4.9)
> `* FIX: import single-sig wallet descriptor (closes #5637)`

S24. Release v6.4.6, 2023-07-03 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.4.6)
> `* FIX: Scan of descriptor QR from Sparrow Wallet not working (closes #5539)`

S25. Release v5.4.4 "Air-gapped PSBT QR codes", 2020-07-01 (https://github.com/BlueWallet/BlueWallet/releases/tag/v5.4.4)
> `ADD: Cobo Vault hardware wallet (Animated QR)`

S26. Release v6.1.0, 2021-05-03 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.1.0)
> `- PSBT for all HD watch-only wallets`

S27. Release v6.1.9, 2021-07-10 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.1.9)
> `* Support for URv2 QR codes`

S28. Release v7.2.6, 2026-02-23 (https://github.com/BlueWallet/BlueWallet/releases/tag/v7.2.6)
> `- Support for BBQR with Coldcard`

S29. Release 8.0.1, 2026-07-21 (https://github.com/BlueWallet/BlueWallet/releases/tag/8.0.1)
> `Support BC-UR v2 air-gap scanning for hardware wallets (OneKey, Keystone)`
> `* fix: support BC-UR v2 air-gap scanning for hardware wallets (OneKey, Keystone) by @wabicai in https://github.com/BlueWallet/BlueWallet/pull/8427`

S30. Pull request #8427, merged 2026-07-20 (https://github.com/BlueWallet/BlueWallet/pull/8427)
> "Add missing UR types (`CRYPTO-HDKEY`, `CRYPTO-MULTI-ACCOUNTS`, `BTC-SIGNATURE`, `ETH-SIGNATURE`, `SOL-SIGNATURE`) to the v2 decoder whitelist"
> "Add `crypto-hdkey` handling in `BlueURDecoder.toString()`: parses a single HD key and returns `[{ExtPubKey, MasterFingerprint, AccountKeyPath}]` JSON"

S31. Release v6.0.6 "Offline signing", 2021-03-02 (https://github.com/BlueWallet/BlueWallet/releases/tag/v6.0.6)
> `Allows a BlueWallet app on any mobile phone to sign transactions offline. Using PSBTs and Airgapped Animated QR codes to transmit information on the dark.`

S32. Issue #4993 "Bluewallet imports SegWit watch-only wallet as legacy", 2022-08-30, closed (https://github.com/BlueWallet/BlueWallet/issues/4993)
> `[dafedf1c/84h/0h/0h]xpub6DFMZMLizqqnyyHoWTG7qzmCR1irpiDEGT4JQX7ubeoFtV838ABKPfgAPQbM1TEekEyCuJF1BrmnA7JPrnzqi2VbycD3tVE3v5xsDQqYA3A`

S33. Issue #5637 "BUG: Scan of singlesig descriptor QR from Sparrow Wallet not working", 2023-08-03, closed (https://github.com/BlueWallet/BlueWallet/issues/5637). The body is an image. No descriptor text was extracted.

S34. Issue #5539 "BUG: Scan of descriptor QR from Sparrow Wallet not working", 2023-05-23, closed, label multisig (https://github.com/BlueWallet/BlueWallet/issues/5539)
> "In BlueWallet: Add Wallet → Import Wallet" / "In BlueWallet: Scan or import a file"

S35. Issue #6311 "Add BBQr", 2024-03-22, closed (https://github.com/BlueWallet/BlueWallet/issues/6311). Fetched as a summary: BBQr is "a new Bitcoin QR spec for PSBTs and other Bitcoin related data types".

S36. bluewallet.io Watch-only page (https://bluewallet.io/watch-only/)
> "Import an xpub, ypub, zpub, or a single public address."
> "+ → Import wallet → paste or scan the public key or address."
> "build the transaction in BlueWallet, sign the PSBT on the device (QR or file), then bring the signed transaction back to broadcast."

S37. bluewallet.io Features page (https://bluewallet.io/features/)
> "Support for Taproot addresses (BIP86). Smaller transactions, improved privacy, and the latest Bitcoin address standard."
> "Support for PSBT - Partially Signed Bitcoin Transactions, BIP 174."
> "Ability to connect and work with Hardware Wallets that support PSBT."

S38. bluewallet.io "Sign a transaction offline" (https://bluewallet.io/docs/sign-offline/)
> "To sign an offline transaction you will need a watch-only (zpub) wallet on a device and a wallet with the seed on the other to sign it."
> "On the watch-only you build your transaction. This will generate a QR code that you will be able to scan or a file that you can export."

S39. bluewallet.io "Use BlueWallet offline as a cold wallet" (https://bluewallet.io/docs/offline-cold-wallet/)
> "Build a transaction on the watch-only wallet. It produces an unsigned transaction as a QR code or file."
> "Scan or import that transaction on the offline device to sign it."

S40. GitHub wiki "Supported wallet types" (https://github.com/BlueWallet/BlueWallet/wiki/Supported-wallet-types)
> "Watch-only - via account-level xpub/ypub/zpub (generally referred to as simply 'xpub')"
> The wiki does not mention descriptors or taproot.

## Not found

- Unverified: the BlueWallet X post on v7.2.2 ("Taproot watch-only", "Taproot hardware wallet support"). The oembed endpoint returned HTTP 402. The GitHub release v7.2.2 and PRs #8146 and #8166 cover the same claim.
- Unverified: hardware wallet PSBT and QR support in v4.6.0 (2019). The GitHub releases list starts at v4.9.0 (2019-12-14). The v4.6.0 claim exists only in an X post that I did not fetch.
- Not found: a release note that names `ur:crypto-psbt`. The closest line is v6.1.9 "Support for URv2 QR codes".
- Not found: a test that imports the exact Corky form `wpkh([fp/84h/0h/0h]xpub.../0/*)#checksum`. The closest test uses `/<0;1>/*)#mthwej8w`. The parser drops all text after the first `/` behind the xpub, so the result is the same. This is an inference from code, unverified by a test or a device.
- Not found: a test for `tr(...)#checksum`. The tests for `tr(` use `/<0;1>/*)` with no checksum, or no suffix.
- Not found: any descriptor checksum validation in BlueWallet. It ignores the checksum.
- Not found: any mention of descriptor import or taproot import in the bluewallet.io docs. The docs name xpub, ypub, zpub, and a single address only.
- Not loaded: the article bodies at https://bluewallet.io/docs/coldcard-watch/ and https://bluewallet.io/docs/cobo-vault/. The fetch tool returned only the navigation and the title.
- Not checked: when the descriptor branch in `abstract-wallet.ts` first appeared in this exact form. It is identical in tag 8.0.1 and `master`. Earlier tags were not compared.
- Unverified on a device: the edge in `psbtWithHardwareWallet.onBarScanned()` that treats data with no `+` and no `=` as a transaction hex.
