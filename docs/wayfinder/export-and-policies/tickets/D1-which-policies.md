# D1 Which policies Corky offers, and in what order

Type: `wayfinder:grilling`, HITL. Blocked by: T1, T2, T3.

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
