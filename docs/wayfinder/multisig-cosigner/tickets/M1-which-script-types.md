# M1 Which BIP48 script types does Core Signer offer?

Type: `wayfinder:grilling`, HITL. **Blocks M2, M3, M6.**
Claimed 2026-09-09.

## Question

BIP48 defines the cosigner path as `m/48'/coin'/account'/script'`, where
the last hardened step names the script type:

| step | script | who uses it |
|---|---|---|
| `1'` | P2SH-P2WSH (nested) | older coordinators, Coldcard defaults |
| `2'` | P2WSH (native segwit) | Sparrow's default, what the charting session proved |
| `3'` | P2TR | taproot, and a different shape entirely |

Core Signer's four single-sig policies exist because Core makes all four and
hiding half a wallet was the D6 defect. The same argument does not
obviously carry: a cosigner branch is only useful if a coordinator asks
for that shape, and offering shapes nobody asks for is
`EXPORT_KINDS` growing for its own sake.

**Decide which script types Core Signer derives and exports**, and whether that
is one, two or all three. `2'` is proven to work end to end; `1'` is
untested here; `3'` is in the fog and probably its own map.

The answer sets `PURPOSE_FUNCS` or whatever replaces it, the export menu,
and how much of M2 and M3 there is to build.

**A blinded path is the same question wearing different clothes.**
Flaxman's blinded-xpub protocol derives the cosigner key at a random
hardened path instead of a standard one, and Core signs on those paths
where most hardware wallets refuse (see the map's established facts).
Whatever answers this ticket has to say whether the set is fixed at
build time or can be an arbitrary path the device is told about, because
that decides whether blinding is reachable at all.

---

## Answer, 2026-09-09. Ben's call, three decisions.

### 1. Arbitrary paths, told to the device

Core Signer derives at whatever path it is given. Not a table, not an
enumeration. Core imposes no limit and signs on every shape tested: BIP48
multisig, a Liana timelock, a three-tier decay, and a 93-bit random
hardened path.

This is the decision M6 said would open or close miniscript, decaying
quorums and blinded xpubs together. It opens them. It is also less code
than the alternative, because there is no table to keep.

What it costs: "Core Signer supports these four policies" stops being a
sentence anyone can check by enumeration, and becomes "Core Signer derives
where it is told". The tests have to change shape with it.

### 2. Signing takes its path from the PSBT, and shows it

A PSBT names Core Signer's own derivation path in `bip32_derivs`, alongside
every cosigner's. Verified against a BLINDED path nobody had told the
device:

    4513369e  m/607137099h/1711870460h/1965312408h/0/0
    f0d67a70  m/48h/1h/0h/2h/0/0
    bc05b401  m/48h/1h/0h/2h/0/0

So Core Signer matches its own fingerprint, reads the path, derives that branch
and signs. **No setup before signing, for any of these shapes.** A
blinded or decaying wallet works with nothing configured.

The path goes on the review screen beside the outputs. With arbitrary
paths allowed, the path is the one thing distinguishing a wallet you set
up from one you did not, so hiding it would remove the only signal. The
protection stays where it already is: you approve the outputs and the
fee, and now you can also see whose wallet you are approving for.

### 3. Export: named rows first, typed path inside Advanced

Coldcard's structure was read for this rather than recalled
(`shared/flow.py`, `shared/export.py`, master). Theirs nests expert
things once under `Advanced/Tools` and destructive things twice under
`Danger Zone`, and their xpub export offers **no custom path at all**:
paths come from templates with only the account number substituted,
`m/48h/{coin}h/{acc}h/2h` and so on. No function of theirs accepts an
arbitrary path from a user. On the decision above, Coldcard is the wallet
that cannot, which is what buidl's "few HWWs can sign on these paths"
warning is about.

So Core Signer takes their safety for the common case and keeps the
capability:

    EXPORT AS
      Native segwit / Taproot / Nested segwit / Legacy
      Cosigner (P2WSH)          m/48'/0'/0'/2'
      Advanced…
         Cosigner (nested)      m/48'/0'/0'/1'
         Account number         0
         Type a path…

Nobody types `m/48'/0'/0'/2'`, so nobody mistypes it. The free-text row
is one level down, where it is not reached by accident, and it is the
only route to a blinded xpub.

**A typed path needs an echo, and this is the reason.** Blinding is
exactly where a typo is unrecoverable: get it wrong and the coordinator
watches a wallet your key does not open, and nothing says so until money
is in it. The typed row must show the path back and derive a test address
to compare against the coordinator, rather than accepting a string and
moving on. That is M2's to design.
