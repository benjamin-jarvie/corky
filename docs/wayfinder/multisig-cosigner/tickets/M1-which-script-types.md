# M1 Which BIP48 script types does Corky offer?

Type: `wayfinder:grilling`, HITL. **Blocks M2, M3.**

## Question

BIP48 defines the cosigner path as `m/48'/coin'/account'/script'`, where
the last hardened step names the script type:

| step | script | who uses it |
|---|---|---|
| `1'` | P2SH-P2WSH (nested) | older coordinators, Coldcard defaults |
| `2'` | P2WSH (native segwit) | Sparrow's default, what the charting session proved |
| `3'` | P2TR | taproot, and a different shape entirely |

Corky's four single-sig policies exist because Core makes all four and
hiding half a wallet was the D6 defect. The same argument does not
obviously carry: a cosigner branch is only useful if a coordinator asks
for that shape, and offering shapes nobody asks for is
`EXPORT_KINDS` growing for its own sake.

**Decide which script types Corky derives and exports**, and whether that
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
