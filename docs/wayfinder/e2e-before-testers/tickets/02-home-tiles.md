# 02 Home is Scan, Key, Tools, Settings

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

Home has four tiles today: load key, key generation, tools, settings. The
tools tile is empty since PLAN A-22. Where do export, backup and the new
screens go, and does generation keep a tile?

## Resolution (Ben, 2026-09-04)

**Four tiles, SeedSigner's four.** Ben: "look at SeedSigner's UI and UX,
don't reinvent the wheel."

| SeedSigner | Corky | Holds |
|---|---|---|
| Scan | **Scan** | the camera; see ticket 05 |
| Seeds | **Key** | loaded keys by fingerprint, or Load a key; see ticket 07 |
| Tools | **Tools** | New key, which is Core's Create Wallet |
| Settings | **Settings** | Power off, About |

Key generation leaves the home screen and goes under Tools, where SeedSigner
keeps "New seed". This reverses Ben's tile order of 2026-09-01.

Icons: the vendored Font Awesome subset has six glyphs. New glyphs come from
the Font Awesome 5 file inside the verified Sparrow release
(`tests/sparrow/.build/ext/com.sparrowwallet.sparrow/font/fa-solid-900.ttf`),
subset with fonttools, and `hw/vendor/fonts/NOTICE.md` lists each one.
