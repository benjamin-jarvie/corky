# R8 Does Bitcoin Core 32.0 matter to Corky

Type: `wayfinder:research`. **Closed 2026-09-05.**

## Question

Ben sent the 32.0 feature summary and asked whether it matters, and how
far away it is.

## How far away

Milestone 32.0 is **open**, 105 issues closed and 9 remaining, last touched
2026-09-05. **No release candidate is tagged yet**; the newest releases are
v31.1 (2026-07-08), v30.3 and v29.4. Ben's summary puts rc1 near
10 September and the release near 10 October, which is consistent.

So: days to rc1, about five weeks to release. Nothing moves under us
without a decision, because `image/PINS` pins 31.1 by hash and provisioning
refuses to install anything else.

## Three items matter. The rest do not.

### 1. `exportwatchonlywallet`, and it deletes a scratch wallet

Merged, PR 32489 on 2026-07-03, with release notes in 35650.

Corky builds the watch-only file by hand today: create a scratch wallet
with `disable_private_keys`, import the public descriptors, `backupwallet`,
drop the scratch wallet. That scratch wallet, `corky-watch`, was half of
the worst finding in the 2026-09-05 two-axis review, because a crash
between creating it and dropping it left a wallet on the ramdisk that
nothing cleared.

Core 32 does the whole thing in one RPC. `signer.write_watch_only`
collapses to a single call and the scratch wallet stops existing.

Worth noting: **PR 35655, "Use in-memory SQLite for temporary wallet in
exportwatchonlywallet".** Core hit the same problem with its own temporary
wallet and fixed it by never putting it on disk. That is the fix we would
have wanted, made upstream.

### 2. PSBTv2 becomes the default, and the risk is narrow

BIP 370 was implemented in PR 21283, merged 2026-05-05. Read out of
master's `src/wallet/rpc/spend.cpp`:

    {"psbt_version", RPCArg::Type::NUM, RPCArg::Default(2), ...}
    uint32_t psbt_version = 2;

So yes, **v2 is the default for PSBT-CREATING RPCs**, with 0 still
selectable.

Corky never creates a PSBT. The shipped signer calls exactly three PSBT
RPCs: `decodepsbt`, `analyzepsbt` and `walletprocesspsbt`.
`walletcreatefundedpsbt` appears only in test harnesses, which fund
transactions a coordinator would otherwise have built.

`walletprocesspsbt` takes no version argument. It decodes what it is
given, fills and signs, and re-serialises the same object, so it should
hand back the version it received. **That is a reading of the source, not
a test**, and the test is cheap: `tests/sparrow` already takes a PSBT from
Sparrow's own library, signs it with Core, and gives it back to Sparrow.
Run those three suites against rc1 the day it ships.

**One thing gets better.** Core 31.1 cannot parse Sparrow's silent-payment
PSBTs because they are v2, which is a documented interop boundary in this
repo. Core 32 can. That boundary disappears.

### 3. libevent removed: small, and in our direction

One fewer third-party dependency inside the binary the whole trust
argument rests on, and possibly a smaller binary, which is not nothing
when N5 is counting megabytes for a RAM image.

### What does not matter

Faster initial sync (Corky never syncs: `networkactive=0`, wallet only),
the peer connection limit, global relay rate limiting, Tor's proof-of-work
defence (no network at all), and mempool fee estimation, because the
coordinator estimates fees and Corky only displays what Core computes from
the PSBT it was handed.

Silent Payments in libsecp256k1 is roadmap, not v1. v1 is single-sig
BIP84/86 and PLAN freezes that.

## What to do

1. When rc1 ships, run `tests/sparrow` against it. Three suites, and they
   are the only things that would notice a PSBT version regression.
2. If they pass, plan the move to 32.0 for the watch-only RPC alone. It
   removes a scratch wallet from a device whose whole claim is that
   nothing persists.
3. Do not move before then. 31.1 is pinned by hash for a reason.
