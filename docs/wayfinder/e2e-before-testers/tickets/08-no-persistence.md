# 08 Prove no key material persists

Labels: wayfinder:task (AFK)
Blocked by: none
Status: resolved 2026-09-05

## Question

Ben, 2026-09-05: "It's really important that keys don't persist. Like it has
to not fucking persist and we need to explicitly ensure it doesn't." And:
"Key unable to persist after shut down / discard. Just to be clear, no
persistence!"

Corky's whole claim is that the device holds nothing. Ticket 10 found that
`Rpc.wallet_dir` pointed at a directory Core does not always use, so on the
board every wallet directory would have survived a discard. That was found
by accident. Prove the property on purpose, for every path a key could take
to a medium that outlives the session.

## Answer (2026-09-05)

`tests/test_no_persistence.py`, 16 checks against a real Core, plus session
K4 in `tests/e2e_keys.py` for the wiring. It treats the whole datadir as one
blob of bytes and refuses to find a key in it.

**The first check is the one that makes the rest mean anything.** While a
key IS loaded, the search must FIND it. The first version of this suite
searched for the xprv as text and reported six clean passes. It was blind:
Core stores the PUBLIC descriptor (a tpub) in `wallet.dat` and keeps the
private key as raw bytes in its own record, so "tprv..." appears nowhere on
disk. The needles are now the 32-byte private key, the 32-byte chain code
and the text form, and the loaded-key check proves the search can hit.

**What is proven, against Core 31.1:**

| Path | Result |
|---|---|
| while loaded | the key IS on disk, in `wallet.dat` and `wallet.dat-journal` |
| after `close_key` | zero bytes, in any form, anywhere under the datadir |
| after `close_session` with three keys | zero bytes for all three, no directories |
| a Core-generated key, discarded | zero bytes (covers the A-19 path, where no one typed the key) |
| Core's log files | no key material |
| bitcoind's own shutdown | writes nothing back |
| a key left by a crashed session | dropped before the first screen |
| an abandoned scratch wallet | dropped by both clears (added 2026-09-05) |

**Two real defects found and fixed.**

1. **Core echoes the key back in its error messages.** Verified: a bad xprv
   makes `getdescriptorinfo` answer ``wpkh(): key 'tprv8Zgx...' is not
   valid``. Corky puts Core's message on the panel, and the same string
   reaches stderr, which systemd captures into the **journal on the SD
   card**. A key on the card is the one thing this device must never do.
   `signer.redact()` now strips anything matching an extended private key,
   in every network prefix, at the point the error is raised. It leaves
   public keys alone, which the screens need. This is string handling, not
   key handling: nothing computes on the key, it only refuses to repeat it,
   so PLAN A-22 stands.

2. **Nothing cleared wallets at startup.** `corky.service` has
   `Restart=on-failure`, and `corky-bitcoind.service` is a separate unit, so
   a crashed session comes back in two seconds with its wallet still loaded
   in a node that never stopped, on a ramdisk that never died. The next user
   would see a key they never entered, named on the home screen, ready to
   sign. `signer.clear_on_start()` drops every Corky slot before the first
   screen, and the session holds a message saying how many it cleared.

**Also fixed:** the shipped `m0/bitcoin.conf` set `debuglogfile=0`, which
Core reads as a FILENAME, so the board had a log file called `0` in its
datadir carrying Core's full log. Now `nodebuglogfile=1`, verified: the
production conf starts a node and leaves no log file at all. A test pins the
conf so it cannot come back.

## Amendment (2026-09-05, round two of the review)

The Spec axis found the hole this ticket's own claim did not cover.
`backup_encrypted` and `write_watch_only` build a scratch wallet, and the
backup scratch holds the PRIVATE descriptors between `createwallet` and the
`finally` that deletes it. Both clears walked `SLOTS` only, so a crash in
that window left a plaintext key on the ramdisk that neither the session
close nor the next startup would ever drop. Reproduced before it was
believed, then fixed: `signer._corky_wallets` returns every wallet named
`corky` or beginning `corky-`, and both clears use it. A test builds an
abandoned scratch and proves both clears take it.

Two smaller things came out of the same round. A `clear_on_start` that
FAILS used to be swallowed, so this ticket's promise could be false with
nothing on screen; it now says so, as the teardown path does (D17). And
`_next_slot` counted only LOADED wallets, so a slot directory left on disk
made the next key load die on Core's raw "Database already exists"; it now
counts the same wallets the clears do.

## What this does NOT prove

- **RAM.** Cold-boot remanence stays an M3 question. The datadir is a tmpfs
  and dies with power, but a key sits in bitcoind's memory while loaded.
- **The board.** Every check here ran on the Mac. TESTING.md rule 9 says the
  target is the only evidence for the target, and the Pi was off. Ticket 18
  must run this suite on the board and read the journal after a crash.
- **Media the user chose.** The file backup (ticket 13) writes an encrypted
  wallet to a stick or a card on purpose. That is a key on a medium, by
  request, encrypted by Core with the user's passphrase.
- **The M3 release image**, which must have no journal persistence at all.
