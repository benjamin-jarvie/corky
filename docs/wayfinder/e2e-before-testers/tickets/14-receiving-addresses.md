# 14 Receiving addresses

Labels: wayfinder:task (AFK)
Blocked by: 12
Status: resolved 2026-09-05

## Question

Build the Key menu's Receiving addresses: the export's address page with
paging, receive branch, Core-derived with `deriveaddresses`, for the
selected key. Whether change addresses show, and how far it pages, is in
the map's fog; decide it here and record it.

Tests: screen fit at both panels; the addresses match Core for pages 1 to 3.

## Answer (built, 2026-09-05)

Built, and the fog this ticket carried is answered.

**Receive branch only.** Core's own window of this name lists a wallet's
receiving addresses, and that is what a person compares against a
coordinator. Change addresses are deliberately absent: nobody hands one
out, and listing them beside the others invites giving one away. A test
pins that no change address appears in the browsed set.

**It pages without end.** `deriveaddresses` fetches ten at a time and the
next block is fetched when the index leaves the current one, so browsing
never stops at an arbitrary wall. Down or right goes on, up or left goes
back, B or C leaves. Proven that twenty derived addresses are twenty
different addresses and that the first three match what the export shows.

**It asks the script type first**, with the same two-entry menu the export
uses, because a key hands out both BIP84 and BIP86 addresses and neither is
the obvious default.

The screen is the export's address page: never truncated, grouped in fours,
first and last group in ochre, "compare every group" underneath.
