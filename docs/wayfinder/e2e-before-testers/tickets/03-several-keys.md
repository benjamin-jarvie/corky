# 03 Several keys at once

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

Corky holds one key today: one wallet with a fixed name, dropped before the
next is made. SeedSigner holds several seeds. Should Corky, and how does a
transaction find its key?

## Facts

Core holds many wallets at once. Measured on the Zero 2 W, 2026-09-04, with
the UI running:

| keys loaded | bitcoind RSS |
|---|---|
| 0 | 49.5MB |
| 1 | 54.5MB |
| 2 | 57.5MB |
| 3 | 60.4MB |

About 3MB per key. `decodepsbt` reports the master fingerprint on every
input, so Core already says which key a transaction belongs to.

## Resolution (Ben, 2026-09-04)

**Several, like SeedSigner.** One Core wallet per key, named by its
fingerprint. The Key tile lists them. Cap five; the table says five cost
about 15MB.

**Matching.** One key loaded: no extra screen. More than one loaded: one
screen lists the keys by fingerprint, the one Core says owns the inputs is
pre-selected, a key that owns none is greyed. No key owns the inputs: a held
screen says so and names the fingerprint the transaction wants.

Discard key unloads that one wallet and deletes its directory. Power-off
still deletes everything.
