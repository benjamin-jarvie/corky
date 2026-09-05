# T0 Let the device emit all four of Core's policies

Type: `wayfinder:task`, AFK. Blocks: T1, T2, T3.

## Question

Nothing to decide. The coordinator tests cannot run until the panel can
show a descriptor QR for each of Core's four policies, because the thing
under test is what a coordinator does with Corky's QR.

`signer.EXPORT_KINDS` is `{"wpkh", "tr"}` and the export screen toggles
between those two with LEFT and RIGHT. Core's wallet also holds `pkh`
(BIP44) and `sh(wpkh)` (BIP49), receive and change, verified against
v31.1 on regtest 2026-09-05.

Add the two missing policies so all four can be put in front of a
coordinator. This is a test instrument, not the answer to D1: which
policies Corky OFFERS in the shipped flow is D1's decision, taken once
the tests say what each coordinator accepts.
