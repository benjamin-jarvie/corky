# 07 Menus in Core's vocabulary

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

What goes in Tools and in the Key menu? SeedSigner's Tools has New seed,
Calc final word, Address explorer, Verify address. Corky has no seed words.
Ben, on the explorer: "what does Core use?"

## Facts

Core has no address explorer. It has the Receive tab, which hands out the
next unused address, and a window named Receiving addresses that lists a
wallet's addresses. Both belong to a wallet. Address checking is
`getaddressinfo`.

SeedSigner's per-seed menu, from its source, in order: Scan transaction,
Export xpub, Address explorer, Backup seed, Discard seed.

## Resolution (Ben, 2026-09-04)

**Tools:** New key. Nothing else. It is Core's Create Wallet.

**Key**, with a key selected, in this order:

1. Sign transaction (the channel menu: Scan QR, USB stick)
2. Export public key (ticket 06)
3. Receiving addresses (Core's name; the export's address page with paging)
4. Backup key (paper: the xprv in groups; file: ticket 04)
5. Discard key (red, with a confirmation)

**Key, Load a key:** Scan, Type descriptor, Type xprv, Restore from file.

Verify address is not a menu entry. An address QR is detected on the Scan
tile (ticket 05).
