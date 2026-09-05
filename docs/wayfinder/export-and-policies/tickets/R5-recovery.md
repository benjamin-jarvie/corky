# R5 Does the paper backup actually get the money back

Type: `wayfinder:research`. **Closed 2026-09-05.**

## Question

Ben: "did you test recovery with any of those seeds / keys?"

No, and it was the largest untested thing in the project. Every other
suite proves the EXPORT lands: a coordinator gets the public descriptor
and watches the right addresses. This is the unhappy path, and it is the
one the paper backup exists for. Corky is lost, broken, or in a river.
All that survives is 111 characters written by hand. Does the money come
back out through software that is not Corky?

## Answer

**Yes, in Bitcoin Core and in Sparrow. Not in the three phone wallets.**

### Proven, and it is a real spend

`tests/sparrow/test_recovery.py`, 21 checks. Sparrow Wallet's own library,
out of the sha256-verified 2.5.4 release, rebuilds a spending wallet from
the bare master private key through
`Keystore.fromMasterPrivateExtendedKey`, which is the call Sparrow's own
"master private key" import drives. For each of the four policies:

1. the rebuilt wallet derives the addresses Bitcoin Core derives;
2. it carries the same master fingerprint;
3. Core funds one of its addresses and builds a PSBT;
4. Sparrow signs it, holding nothing but the paper backup;
5. **Core finalises that signature and `testmempoolaccept` says the
   network would take it.**

Step 5 is the one that matters. A signature Corky's own node will not
finalise is not a recovery, whatever the recovering wallet reports.

The file backup's recovery was already proven: Core's own `encryptwallet`
and `backupwallet`, restored on a second Core node, same fingerprint,
owning the same addresses (`tests/test_backup.py`).

### Not possible, and testers must be told

| wallet | recovers from the paper backup |
|---|---|
| Bitcoin Core | yes, build the descriptor and `importdescriptors` |
| Sparrow | yes, all four policies, proven above |
| BlueWallet | **no** |
| Green | **no** |
| Bull Bitcoin | **no** |

- **BlueWallet** handles an xprv only in `class/wallets/multisig-hd-wallet.ts`,
  for multisig cosigners. Its single-sig import (`class/wallet-import.ts`)
  takes mnemonics and watch-only public keys. There is no single-sig
  private-key path.
- **Green** never handles an xprv at all. No Kotlin source outside tests
  mentions one.
- **Bull Bitcoin** refuses it explicitly:
  `lib/features/import_watch_only_wallet/watch_only_wallet_entity.dart`
  matches the private-key prefixes and throws
  `"Watch-only imports require public extended keys"`.

This is not as bad as it reads. Those three are **coordinators** in
Corky's model: they watch and build, Corky signs. Recovery means Corky is
gone, and putting a private key into a phone is a different security
posture anyway. But it is a real limit and it belongs in the README, not
in a surprise.

## A test defect found on the way, worth recording

The first run reported taproot recovery broken: Sparrow signed and Core
refused to finalise. Taproot was fine. The suite funded one address per
policy in a loop, and `walletcreatefundedpsbt` left to itself spent
whichever coin it liked, so the taproot round was handed a native segwit
coin from the round before, which a taproot-only wallet cannot sign.
Naming the input, with `add_inputs: False`, fixed it. TESTING.md rule 5's
point in a new shape: reproduce the finding before believing it, including
when the finding is your own suite's.
