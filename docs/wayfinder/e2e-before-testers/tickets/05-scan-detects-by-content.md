# 05 Scan detects by content

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

What does the Scan tile accept from the camera? SeedSigner's Scan reads any
QR and decides what it is. Corky today has a load-key menu and a separate
channel menu for transactions.

## Resolution (Ben, 2026-09-04)

**Detect by content, as SeedSigner does.** Press Scan, point the camera at
any QR.

| What the camera read | What Corky does |
|---|---|
| UR frames | a transaction: review, then sign |
| text beginning `xprv` or `tprv` | a key: import as xprv |
| text that parses as a descriptor | a key: import as descriptor |
| a bitcoin address | check it with Core's `getaddressinfo` against every loaded key, and say which key owns it or that none does |
| anything else | count it, skip it, keep scanning |

The USB stick is not a Scan thing. It stays under Key, Sign transaction, as
today's channel menu.

The stop rules for a single static QR are the M1 map's ticket 05 rules:
20 seconds with no decode times out, a button aborts, the viewfinder shows
throughout. Building this is ticket 09.

## Amendment (2026-09-05, round two of the review)

Two deviations from the table above, both deliberate, both recorded here
rather than left for a reader to find in the code.

**The scan treats all six extended-private-key prefixes as a key**, not
just `xprv` and `tprv`. Core reads neither `yprv` nor `zprv` nor the rest,
so showing one gets Core's refusal on screen instead of the silent skip the
table promises. That is the better answer: somebody holding a key up to the
lens deserves to be told their key is in a form Core cannot read, and
silence would look like a camera fault. One list, `signer.XPRV_PREFIXES`,
is shared with the redactor so the two cannot disagree about what a private
key looks like.

**A descriptor is recognised by its function name**, from Core's own list,
rather than by having brackets in it. A URL with brackets was being handed
to Core to refuse; now it is skipped, as the table's last row asks.

**And a payment request is accepted where an address is.** A phone wallet
shows `bitcoin:bc1q...?amount=...`, not a bare address, so the BIP21 form
is unwrapped before the address check and again before `getaddressinfo`.
Without that the address row could never fire for the wallets ticket 22
will test.
