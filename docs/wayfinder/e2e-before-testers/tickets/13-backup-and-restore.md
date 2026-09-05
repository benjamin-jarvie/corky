# 13 Build the file backup and its restore

Labels: wayfinder:task (AFK)
Blocked by: 10
Status: resolved 2026-09-05

## Question

Build ticket 04: the passphrase entry on the grid, `encryptwallet` and
`backupwallet` to the medium the user chose on the ask-every-time screen,
the restore entry under Load a key that lists wallet files on the stick or
card and runs `restorewallet` then `walletpassphrase` for the session.
Name the file by fingerprint.

The passphrase charset was removed as dead code in the A-22 review; bring it
back with the text-entry screen's paging.

Tests: the two-node probe of 2026-09-04 made permanent; a restore with a
wrong passphrase is refused and the screen says so; a file that is not a
wallet is refused without a crash (rule 1: real data through the surface).

## Answer (built, 2026-09-05)

`tests/test_backup.py` (11 checks across two real Cores) and session K6 in
`tests/e2e_keys.py`, which backs a key up on the device, discards it, and
loads it again from the file.

**Backup key now asks which backup**, because there are two and they are
not alternatives. **On paper** is the master xprv, the key itself, titled
by fingerprint. **To a file** is Core's `encryptwallet` then
`backupwallet`, which is exactly the pair a Core user runs, so another Core
restores it with `restorewallet` and unlocks it with `walletpassphrase`.
Nothing of ours encrypts anything.

**The encryption happens on a scratch copy, not on the loaded key.** This is
the one design decision here. `encryptwallet` locks the wallet it is called
on, so encrypting the session's own key would silently add a passphrase
prompt to every later signature. Corky builds a scratch wallet from the same
private descriptors, encrypts that, backs it up, and deletes it. Proven: the
loaded key is still unencrypted afterwards, and no scratch wallet is left.

**Restore is the fourth entry under Load a key.** It lists the backup files
on the stick and the card by the fingerprint in their name, so the user
picks a key rather than a filename, then asks for the passphrase once and
unlocks for the session (ticket 04).

**Every refusal was tested with real wrong data** (rule 1), and each leaves
the session exactly as it was: a wrong passphrase, a file that is not a
wallet at all, and the watch-only export, which holds no private key and
would otherwise load as a key that cannot sign.

**Naming.** `corky-<xfp>-backup.dat` is the encrypted key backup;
`corky-<xfp>-watch.dat` is the watch-only export for a Core laptop. The
restore chooser lists only the first.

**A note for ticket 08.** A backup file on the boot card survives power-off
by design. That is the one key-bearing thing Corky writes to a medium, it
happens only when the user asks, and Core encrypts it with the user's own
passphrase.

**Found while building this.** A `str.replace` edit that did not match left
the restore entry out of the menu's dispatch list, so selecting it raised
"list index out of range" behind the menu's own catch-all. The e2e session
found it; the golden-frame assertions named the screen that never appeared.
