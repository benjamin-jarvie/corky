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

## Decided already (Ben, 2026-09-04)

**Never truncate. Group in fours, with a space between groups.** Colour the
first four and the last four differently from the middle, to make comparison
against a coordinator quicker.

This matches the codex32 spec's own display rule, `docs/wallets.md`: data
"should be displayed in uppercase with visually distinct four-character
windows". Corky already groups codex32 shares in fours through
`share_pages`; `screens.address_lines` does not group at all, it hard-wraps
every 22 characters.

One caution to carry into the design rather than ignore. **Highlighting the
head and tail is exactly the shortcut address-replacement malware relies
on**: a swapped address that matches on the first and last four passes a
glance. The colour should make a full comparison easier to track, not offer
a shortcut that replaces it. Worth deciding whether the middle stays plainly
legible and equally weighted, and whether the screen says anything about
checking all of it.

Open sub-questions this leaves:

- Which colours. OCHRE and CREAM are the existing palette; a third would be
  new.
- Whether the same grouping and colouring applies to the xpub and the
  descriptor on export, not only to addresses. The descriptor is long and
  carries a checksum, so it may want different treatment.
- Whether uppercase applies to addresses. The spec's rule is about codex32.
  Bech32 addresses are case-insensitive but conventionally lowercase, and
  uppercase changes the QR encoding mode.
