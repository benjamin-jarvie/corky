# T3 What Bitcoin Core gets, and whether it carries all four

Type: `wayfinder:task`, HITL. Blocked by: T0.

## Question

Bitcoin Core reads no QR, so its half of the air gap is a file:
`signer.write_watch_only` runs Core's own `backupwallet` on a wallet made
with `disable_private_keys`.

On the laptop, restore that file with File, Restore Wallet. Record:
does it restore; does it carry all four policies or only the two Corky
currently exports; do its first receive addresses match the board's.

This is the one coordinator where the policy question may answer itself,
because a wallet file carries whatever descriptors are in it rather than
one chosen string.

Second half, and it is a real one: the file has nowhere to go. The unit
configures `--stick-dir=/mnt/usb` and no `--card-dir`, so the boot microSD
is never offered. Record what Ben actually had to do to get the file onto
the laptop, because that is the evidence D5 needs.
