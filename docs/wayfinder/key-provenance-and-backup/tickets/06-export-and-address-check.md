# 06 Getting the watch-only descriptor out, and proving it landed

Labels: wayfinder:grilling (HITL)
Blocked by: 03

## Question

Ben, 2026-09-04: "when exporting (xpub) we should also look at its first few
receive addresses and confirm they are the same?"

**Corky has no export flow at all.** Grepping the UI for descriptor or xpub
export returns nothing. The interop tests build the watch-only descriptor in
the harness (`tests/e2e_session.py:_pub`), so the gap never surfaced. The
sequence Ben describes has no first step, and the M1 gate assumes a Sparrow
watch-only wallet that nothing on the device can currently create.

Established 2026-09-04 against Core 31.1 on regtest:

- Core writes standard output descriptors, so a Core-generated key is
  ordinary everywhere:
  `wpkh([668b2262/84h/1h/0h]tpubDD3RG.../0/*)#l4l986e9`
  The origin already carries the XFP, so the descriptor names its own key.
- `deriveaddresses <desc> [0,N]` is **side-effect free**: the keypool was
  4000 before and after. It is the right call for a display.
- `_tool_generate` currently uses `getnewaddress`, which **advances the
  wallet's address index every time the screen is drawn**. Wrong call for a
  display, and a real if minor bug.
- It also shows the address truncated (`address[:14] + "…" + address[-6:]`),
  which defeats the entire purpose of a comparison.

Decide, with Ben:

1. What Corky exports: BIP84 only, BIP86 only, both, or a choice. Public
   descriptor with checksum, or a bare xpub, or both.
2. How it leaves the device: animated QR (Sparrow reads UR), the USB stick as
   a file, or both. Note Corky can already render QR out.
3. How many receive addresses to show for verification, and whether change
   addresses too. Full strings, never truncated.
4. Whether the check is a step in the export flow that the user must pass, or
   a separate Tools entry they can return to.
5. Whether the XFP is shown beside the addresses, so the comparison covers
   which key as well as which addresses.
6. Whether an address explorer belongs in Tools at all, or only the first few
   at export time. SeedSigner has a full explorer; that is more surface.

Related: `screens.address_lines` already exists for wrapping an address onto
the panel.
