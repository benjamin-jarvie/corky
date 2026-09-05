# R3 Which script policies each coordinator accepts

Type: `wayfinder:research`. **Closed 2026-09-05.** Supersedes the "which
policies" half of T1 and T2.

## Question

Ben: "Blue and Green wallet are FOSS, we already have bull locally and
sparrow too, so perhaps clone down blue and green and you should be able
to do all the stats required rather than depend on me."

## Answer

Read from each coordinator's own source. No hand testing was needed to
answer the policy question.

| coordinator | legacy 44 | nested 49 | native 84 | taproot 86 |
|---|---|---|---|---|
| Sparrow | yes | yes | yes | yes |
| BlueWallet | yes | yes | yes | yes |
| Green | yes | yes | yes | yes |
| Bull Bitcoin | yes | yes | yes | **no** |
| Bitcoin Core | all four, and by file rather than QR |

**Sparrow** is not source reading. Its own library, out of the
sha256-verified release, parses all four of Core's descriptors and derives
Core's addresses for each, legacy and nested included. Asserted
permanently in `tests/sparrow/test_export_interop.py`, 37 checks.

**BlueWallet** (`class/wallets/abstract-wallet.ts`, around line 238)
accepts a string starting `wpkh(`, `pkh(`, `sh(` or `tr(`, pulls the
origin out of the square brackets, and maps to one of four wallet classes
in `class/wallets/watch-only-wallet.ts` line 84: `p2tr`, `p2wpkh`,
`p2sh(p2wpkh)`, `p2pkh`. All four of ours parse. One limit worth knowing:
it locates the key with `indexOf('xpub'|'ypub'|'zpub')`, so it is
**mainnet only**. A testnet `tpub` descriptor will not parse, which is why
this cannot be exercised on regtest.

**Green** names Core descriptors as a first-class credential type,
`WatchOnlyCredentialType.CORE_DESCRIPTORS`. Its detector
(`data/src/commonMain/kotlin/com/blockstream/data/utils/WatchOnlyDetector.kt`)
accepts `wpkh(`, `pkh(`, `sh(`, `tr(`. Better than that, Green's OWN test
file asserts all four forms explicitly, mainnet and testnet, in the shape
Corky emits.

Two Green notes. Its path-based network detection looks for `/84'/0'/`
with an apostrophe, and Core writes `84h`, so that rule misses; detection
still succeeds through the `xpub`-prefix rule beneath it. And
`InputType.BCUR` returns `isValid = false` for watch-only import, so Green
will NOT take a UR-encoded descriptor. It wants the plain string, which is
what Corky sends.

**Bull Bitcoin** (`~/bullbitcoin-mobile`, `lib/core/wallet/domain/entities/wallet.dart`
line 69) defines `ScriptType` as exactly `bip84`, `bip49`, `bip44`. There
is no taproot anywhere in its Dart source. `wallet_metadata_service.dart`
builds `wpkh([*])`, `sh(wpkh([*]))` and `pkh([*])` and its origin regex
expects the `h` notation Core writes.

This CORRECTS the earlier desk research (previous map, ticket 21), which
recorded Bull Bitcoin as native segwit only. It takes three of the four.
It is taproot it cannot take.

## What still needs Ben's hardware

Not the policy question. What source cannot tell you is whether the
application does what its parser says: whether the camera reads Corky's
QR at the density it renders, what each app calls the wallet on screen,
and whether the first receive address it shows matches the board's. That
is the remainder of T1, T2 and T3, and it is a much smaller job than it
was this morning.

## Reproducing

    git clone --depth 1 https://github.com/BlueWallet/BlueWallet.git
    git clone --depth 1 https://github.com/Blockstream/green_android.git

Bull Bitcoin is already at `~/bullbitcoin-mobile`. The clones were removed
after this run; nothing in the repo depends on them.
