# D1 Which policies Corky offers, and in what order

Type: `wayfinder:grilling`. **Closed 2026-09-05.**

## Question

Ben, on the board: "If you write down one, it can sign for all, but if
exporting, you should have chosen this first."

The first half is settled and true: one written master private key opens
a Core wallet holding all four policies, so the paper backup covers all
four whatever the export shows. The second half is his decision, already
taken: the policy choice comes before the QR.

What is left to decide, once T1 to T3 say what the coordinators actually
accept:

- Which of the four does Corky offer? All four, or only those a real
  coordinator took?
- What order, and which is first?
- What does the panel say about a policy a coordinator will refuse? Corky
  can know that Bull Bitcoin has no taproot; whether it should say so is a
  separate question from whether it should hide the row.
- Do the addresses under Receiving addresses follow the same list?

One fact that has to sit in this decision: coins sent to a legacy or
nested address of this wallet are spendable by this key today, and
invisible on the panel today, because Corky browses two policies of four.

**Closed 2026-09-05.** Decided from R3's measured coordinator matrix.
Ben asked for the decisions to be finished; these are my calls with the
reasoning recorded, and every one of them is reversible.

## Decision

**Offer all four, in the order `wpkh, tr, sh, pkh`.** Native segwit first
because it is what almost every wallet defaults to; taproot second because
it is the modern one; nested segwit and legacy after, because their job is
opening older wallets rather than making new ones.

**Do not hide the ones a given coordinator refuses.** Corky no longer asks
which coordinator you are using, and it cannot tell. Bull Bitcoin has no
taproot, but a device that hid taproot on that account would be hiding it
from the four coordinators that do support it. The screen names each
policy in the words the wallets use, and the README carries the matrix.

**Receiving addresses follows the same list and the same order**, so the
addresses you compare are the addresses of the policy you exported.

## Why all four rather than the two we had

Three reasons, in order of weight:

1. A key controls all four whether or not Corky shows them. Coins on a
   legacy address were spendable and invisible until D6 was closed.
2. Recovery works for all four (R5): Sparrow rebuilds the wallet from the
   paper backup and signs spends the network accepts, for every policy.
3. Three coordinators of five take all four, and Core takes all four by
   file. Only Bull Bitcoin is short, and only of taproot.
