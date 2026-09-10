# M6 Miniscript, decaying quorums, and blinded paths: one question or four?

Type: `wayfinder:grilling`, HITL. **Blocked by M1.**

## Question

Ben, 2026-09-09: look at miniscript, Liana, Nunchuk, decaying keys and
blinded xpubs. Charting did, against Core 31.1, with both wallets cloned
and read. The finding is that **they are all the same question wearing
different clothes**, and the question is M1's: what paths may Corky hold
a key at?

What was established, so this ticket starts from facts:

- **Core signs a Liana-shaped policy.** `wsh(or_d(pk(primary),and_v(
  v:pkh(recovery),older(20))))` imports, and Corky's key alone signs AND
  FINALISES the primary path: `final_scriptwitness` present, two witness
  items, `testmempoolaccept` allowed.
- **Core imports a three-tier decaying quorum.** 3-of-3 now, 2-of-3 after
  10 blocks, one key after 20. Corky contributes one signature at every
  tier, holding only its own branch, exactly as it does for plain
  multisig.
- **A descriptor may hold at most ONE private key.** Two xprvs in one
  descriptor are refused as "not sane: contains duplicate public keys",
  even when they are demonstrably different keys. Irrelevant in practice,
  because a signer holds one key and the rest are xpubs, but it wasted an
  hour of charting and is worth writing down.
- **Decay tiers use the same seeds at DIFFERENT paths.** Liana's own
  model says so: "one or more recovery paths with any number of key
  checks, behind increasing relative timelocks. No two recovery paths may
  have the same timelock", with `DuplicateKey` and
  `DuplicateOriginSamePath` as separate errors. So one Corky key can
  appear in several tiers, at several accounts, and **Corky may need
  several branches imported for one wallet.** That is the sharpest thing
  this ticket has to decide.
- **Nunchuk takes arbitrary miniscript**, `set_miniscript_template(
  std::string)`, with a `Timelock` model of height or time, relative or
  absolute. Its `WalletTemplate` enum is only DEFAULT and
  DISABLE_KEY_PATH, so the decay is composed by the user rather than
  chosen from a list.

**What is NOT established, and this ticket should not assume it.** None
of the three tiers finalised on Corky's signature alone, including the
one-key tier past its timelock. The likely cause is `nSequence`: the
coordinator's `walletcreatefundedpsbt` builds for the first satisfiable
path, so the input's sequence never enables the timelocked branch. If
that is right, **which tier a spend uses is the coordinator's choice at
build time and not the signer's**, and Corky's job is unchanged. It has
not been proven, and proving it is the first thing to do here.

So the decision:

- Does M1's answer cover an arbitrary path, or a list? An arbitrary path
  makes miniscript, decay and blinding all reachable with no further
  work. A list closes all three.
- If a key can be in several tiers, does Corky import several branches
  for one wallet, and what does the key screen then show? One key with
  four branches is a different object from the four script policies.
- Does the review screen have to say which tier is being spent? It can
  read the paths out of the PSBT; whether a person can act on that is a
  judgement.

## Measured, 2026-09-10, Core 31.1 on regtest

A real three-tier decaying quorum, built and spent three ways. The
policy, with our key at a different account in each tier:

    wsh(or_d(multi(2,A@0,S0@0,S1@0),
             or_i(and_v(v:multi(2,A@1,S0@1),older(10)),
                  and_v(v:pk(A@2),older(20)))))

| spend | our paths | our sigs | finalises | mempool |
|---|---|---|---|---|
| tier 1, `nSequence` 0xfffffffd | 3 | 3 | no | - |
| tier 2, `nSequence` 10 | 3 | 3 | no | - |
| tier 3, `nSequence` 20 | 3 | 0, already final | **yes** | **accepted** |

### 1. The nSequence hypothesis is CONFIRMED, and it was the cause

Charting saw no tier finalise and suspected `nSequence`. That was right.
With the sequence set and the coin 25 blocks old, the one-key tier
finalises and the network accepts it. Tiers 1 and 2 stay unfinished
because a STRANGER's signature is missing, which is correct.

**So the tier is the coordinator's choice at build time, and Corky's job
does not change.** That was the ticket's first question and it is now a
fact rather than a guess.

### 2. A reused key needs a different path in every tier

Core refuses the policy outright otherwise: "not sane: contains
duplicate public keys". That is Liana's `DuplicateOriginSamePath` seen
from the other side, and it is a rule the coordinator must follow, not
Corky.

### 3. Corky already imports several branches, and M9 did it

Our key sits at three accounts. One signing pass imported all three
branches and produced **three signatures in one action**. `_branches`
collects every derivation the PSBT names for this fingerprint, so the
ticket's sharpest question needs no new work: the device does it, and
nothing has to be set up first.

### 4. A one-key tier comes back FINISHED, not partial

`walletprocesspsbt` finalises by default, so when Corky's own key
satisfies the branch the device hands back a broadcastable transaction.
That is the correct outcome and it is a different outcome from a share.

### 5. And the review screen says almost none of this

`describe_psbt` reports `quorum=None`, because Core types a miniscript
witness script as `nonstandard` rather than `multisig`. The screen shows
the path and six cosigners, with no threshold, no timelock and no tier.

**This is the finding that matters.** M3 decision 1 accepted SIGNED over
a partial signature, and the thing that made it acceptable was decision
2: the review screen states the threshold, so the flow says the
transaction needs others BEFORE you sign. For a miniscript wallet the
screen cannot state a threshold, so that justification lapses. M3 said
"If the review screen ever loses that, this decision has to be reopened
with it." For this class of wallet it never had it.

Core does give the timelocks readably. The decoded `asm` for the policy
above yields `['10', '20']` before `OP_CHECKSEQUENCEVERIFY`, and two
`OP_CHECKMULTISIG`, so a tier line is reachable the same way the
threshold is, without Corky parsing a script itself.

## Answer, 2026-09-10. Two of the three questions were already answered.

The ticket asked three things. Measurement closed the first two before
any decision was needed, and turned the third into a sharper question
that Ben answered.

### 1. Arbitrary path or a list? Already M1, and M9 built it

Arbitrary. Nothing here reopens it, and the measurement above shows why:
Corky signed a Liana policy and all three tiers of a decaying quorum
holding only its own branches, which is the same trick as plain
multisig.

### 2. Several branches for one wallet? Yes, and it needs no work

Our key sat at three accounts. One signing pass imported all three
branches and produced three signatures in one action, because M9's
`_branches` reads every derivation the PSBT names for this fingerprint.
Nothing has to be set up first and the key screen does not change: it is
still ONE key, and the branches are a property of the transaction rather
than of the key.

### 3. Does review say which tier? Yes, and the SIGNED screen too

**Ben's call, 2026-09-10, from four options: both.**

- **Before signing**, the review screen shows the tier this spend
  enables: `AFTER 20 BLOCKS · m/48h/1h/2h/2h`, and `TIMELOCKED` when
  the policy holds locks that this spend does not use. `describe_psbt`
  gains `timelocks`, read from the same `asm` the threshold comes from,
  and `spend_lock`, the highest lock the input's `nSequence` enables.
  Corky parses no script.
- **After signing**, the result screen separates the two outcomes. A
  finished transaction says `SIGNED · ready to send`. One share of a
  quorum says `SHARE · needs another signature`. Until now both said
  SIGNED, so a transaction that can move the money on its own looked
  exactly like one waiting on two more people.

**This closes M3's open condition.** M3 wrote: "What makes it acceptable
here is decision 2: the REVIEW screen states the threshold. If the
review screen ever loses that, this decision has to be reopened with
it." For a miniscript wallet the screen never had a threshold to state,
because Core types the witness script as `nonstandard`. The outcome line
is true for every wallet shape, so the trade no longer rests on a screen
that cannot always deliver.

### Deliberately not read

`spend_lock` is `None` whenever the answer is not plainly readable: no
locks, inputs whose sequences disagree, BIP68's disable bit set, or
512-second units instead of blocks. Comparing a block count to a
duration is a consensus rule rather than a reading, and a screen that
says nothing is right more often than a screen that guesses.

CONTEXT.md gains **quorum**, **cosigner**, **share** and **tier**.
