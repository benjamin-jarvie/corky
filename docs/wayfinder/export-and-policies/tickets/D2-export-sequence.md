# D2 What the export screens become

Type: `wayfinder:prototype`. **Closed 2026-09-05.**

## Question

Ben walked the current flow and could not tell where he was: a QR, then
the descriptor over four pages, then straight into addresses where A steps
through them one at a time, then a Bitcoin Core menu on the way back, then
a channel chooser that offered USB only.

Draw the sequence the export becomes once D1 fixes the policy list.
Prototype it as rendered frames, not prose, and put them in front of Ben.

Constraints that are already decided and are not reopened here:
- the policy is chosen first (D1);
- Core's descriptor leaves as a plain string, not UR (prior map);
- Bitcoin Core gets a file because it reads no QR.

Open inside this ticket: whether the four-page descriptor text belongs in
the main path or behind a "type it by hand" door; whether the addresses
belong in the export path at all, given Receiving addresses is its own row
on the key menu; where the Bitcoin Core file offer sits.

**Closed 2026-09-05.**

## What was wrong

Ben walked it and could not tell where he was. Export public key gave a
QR with no label, then the descriptor over four pages titled "PUBLIC KEY
1/4", then DONE dropped into receiving addresses where A stepped through
them one at a time, then B surfaced a Bitcoin Core menu, which asked for a
USB stick that was not there, and reported "SIGNED".

## Decision: SeedSigner's shape, with the parts we proved unnecessary cut

SeedSigner's export is: seed, Export Xpub, signature type, script type,
coordinator, QR. Ben's standing rule is not to reinvent that. Two of those
steps are gone for good reasons, and one is coming back.

- **Signature type: cut.** v1 is single-sig. There is nothing to ask.
- **Coordinator: cut, and it stays cut.** R3 proved all five read the same
  plain descriptor. The chooser produced an identical QR four times out of
  five.
- **Script type: restored, and it comes first.** Ben: "if exporting, you
  should have chosen this first." D1 settled the list.

So the flow is:

    KEY 73C5DA0A
      Export public key
        -> SCRIPT TYPE     Native segwit / Taproot / Nested segwit / Legacy
          -> the QR, captioned with the policy it carries
             A opens EXPORT OPTIONS: Show as text
                                     Wallet file for Bitcoin Core
                                     Done
             B returns to SCRIPT TYPE

## Three specific removals

- **Receiving addresses leaves the export path.** It is already a row on
  the key menu. Arriving there by pressing DONE on a descriptor was the
  step that lost him, and one address with no instruction was never a
  check anyway.
- **The Bitcoin Core file offer stops ambushing the way out.** It moves
  into EXPORT OPTIONS, where it is chosen rather than met.
- **"SIGNED" over a written file is gone** already (commit da16b1c), and
  so is the phantom USB stick (`_file_channels` now needs a real mount).

## What each screen is called: see D4.
