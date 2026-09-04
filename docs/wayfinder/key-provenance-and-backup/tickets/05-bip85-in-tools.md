# 05 What BIP-85 in Tools produces, and how it refuses to be mistaken for a backup

Labels: wayfinder:grilling (HITL)
Blocked by: none (03 closed 2026-09-04)

## Question

Decided already (map, Decisions so far): BIP-85 is a separate Tools
operation, never on the default backup path, and the backup screen offers a
choice only if a child was deliberately derived.

Still open:

1. What it emits. Entropy Lab derives "English BIP-39 mnemonics (12 to 24
   words), HD-seed WIF, XPRV, HEX". Corky needs how much of that.
2. How the child is labelled so nobody mistakes it for a backup of the
   parent. This is the sharp edge: those words open a DIFFERENT wallet, and
   a user who writes them down and funds the Core wallet loses the coins.
3. Whether Corky can SIGN with a derived child, or only display it. Signing
   with it means a second wallet in Core and a second XFP on screen.
4. Which BIP-85 applications and indices are exposed, and whether the index
   is chosen by the user or fixed.
5. Whether Bails' pattern applies: root for savings, children for spending,
   panic and decoy wallets.
6. What the warning says. Ben asked what Greg Maxwell would say about BIP39:
   the substantive criticism is that the 4-bit checksum passes a wrong
   mnemonic about 1 time in 16 and cannot say WHICH word is wrong, that the
   words carry no derivation path or script type so they are not by
   themselves a backup, and that 2048 PBKDF2 rounds is a token against a
   weak passphrase.
