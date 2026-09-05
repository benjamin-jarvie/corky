# 04 The file backup is Core's own

Labels: wayfinder:grilling (HITL)
Blocked by: none
Status: CLOSED 2026-09-04

## Question

Ben wants "to try encrypting the file, opening on a different computer and
importing into Core". PLAN.md's fixed decisions say "No keys on the SD card,
ever". PLAN A-22 says zero lines of ours touch a key. Can both hold?

## Facts

Proven on the Mac, 2026-09-04, two regtest nodes, zero code of ours:

1. `encryptwallet <passphrase>` then `backupwallet <path>` on the signer
   node wrote a 32KB wallet file. The xprv does not appear in it in plain
   text.
2. `restorewallet` on the second node loaded it. The restored wallet knew
   the same first address.
3. A spend without the passphrase was refused with Core's error -13. After
   `walletpassphrase` the spend went through.

Corky's part is one passphrase screen and two RPC calls.

## Resolution (Ben, 2026-09-04)

**The file backup is Core's encrypted wallet file, made by Core's own
commands.** Ben's condition: "providing that's what Core does, so we're not
changing the value prop of Corky and creating unnecessary code." It is.

**The SD-card rule is amended.** Corky never writes a key on its own. A
backup that the user asks for, encrypted by Core with a passphrase the user
typed, written to a medium the user names, is allowed. The README says so
plainly. Recorded as PLAN A-23.

**Where it goes: ask every time.** Stick or card, one screen.

**Restore.** Under Key, Load a key, Restore from file. Corky lists the
wallet files on the stick or card, Core restores the chosen one, and the
passphrase is typed once, at restore, for the session. Core's
`walletpassphrase` with a long timeout; the wallet dies at power-off anyway.

Sparrow cannot read this file. It is Core to Core, for recovery, never for a
coordinator.
