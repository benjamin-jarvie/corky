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
