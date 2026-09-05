# T2 Which policies the three phone wallets accept

Type: `wayfinder:task`, HITL. Blocked by: T0.

## Question

Ben has the phone. Same procedure as T1, for BlueWallet, Green and
Bull Bitcoin: scan Corky's descriptor QR for each of the four policies,
record what each wallet accepts and what it calls it, and compare the
first receive address against the board's.

Desk research says (tickets 19, 20, 21 of the previous map): BlueWallet
and Green take the plain descriptor for `wpkh` and `tr`; Bull Bitcoin
takes `wpkh` only and wants the signing device set to "SeedSigner"; Green
labels everything Jade. **None of that is proven.** Where the phone
disagrees with the research, the phone is right and the research ticket
gets corrected.

Also record what each returns when it makes a transaction, because that
is the other half of the loop: the research says all three return
`ur:crypto-psbt`.
