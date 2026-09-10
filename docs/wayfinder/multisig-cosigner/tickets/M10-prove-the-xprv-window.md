# M10 Prove the master xprv leaves nothing when it signs at a told path

Type: `wayfinder:task`, AFK. **Blocked by M9 (closed).**
Claimed and resolved 2026-09-10. Ben's call, from four options.

## Question

M9 built `sign_at_told_paths`. A descriptor is the only way Core imports
a derivation and a descriptor carries the key, so signing a share at a
path the PSBT names pulls the master xprv into Corky for the length of
one signature.

That door is already open three times: the paper backup reads the key to
show it, `cosigner_key` reads it to export, and `generate_wallet` reads
it once as a birth sanity check. M9 makes it four.

M9 recorded the reasoning for why this leaks nothing: the scratch wallet
is never the session's, it is dropped in a `finally`, nothing is
written, and the datadir is tmpfs. **Reasoning is not measurement**, and
every other claim in this repo was settled by measurement.

Prove it, in `tests/test_no_persistence.py`, which already treats the
datadir as one blob and already carries the positive control that makes
a miss mean something:

1. After a multisig sign at a told path, the key is in no file under the
   datadir, and no wallet directory survives.
2. The same after the sign FAILS part way, which is the case a leak is
   most likely to escape through.
3. The key reaches no argv during the whole sign. `Rpc.call` forces
   stdin for anything `redact` would strip, and M9 passes three
   descriptors carrying the xprv. Nothing has asked whether that holds.
4. No Core log file carries it.

Swap is already covered on the board: `image/leak-check.sh` refuses
`swapon`, `dphys-swapfile` and `dev-zram0.swap`. This ticket does not
repeat it.

## Done when

Those run green, each one mutation-verified, and the answer records what
the argv check actually saw.


## Answer, 2026-09-10. Measured. It leaves nothing.

Five checks in `tests/test_no_persistence.py`, which already treats the
whole datadir as one blob and searches for the private key bytes, the
chain code and the xprv text. Four mutations, all caught.

### The positive control first

**The scratch wallet DOES hold the master xprv while it signs**, in
`wallet.dat` and `wallet.dat-journal`. That is the descriptor being
stored, and it is exactly what the ticket suspected. Without this line
the three checks below would pass by being blind, which is the trap the
top of that file exists to name.

### What the checks say

1. **A told-path sign puts the key in no new file.** The test compares
   against a BASELINE taken before the sign, rather than demanding an
   empty datadir. A loaded session wallet holds the key on purpose and
   so does the fixture wallet that puts our key in the quorum, so
   "nothing anywhere" would be the wrong question and could be satisfied
   by closing the session first.
2. **The scratch wallet is gone from the disk** after the sign.
3. **A sign that FAILS part way leaves no new key and no wallet.** The
   failure is forced at `walletprocesspsbt`, which is after the
   descriptors are imported, so the wallet holds the key at the moment
   it raises. The `finally` runs.
4. **No key material reached argv in 13 `bitcoin-cli` calls.**
5. Core's log check already in this suite still passes.

### The argv result is better than asked for

Setting `stdin=False` on the descriptor calls changes nothing, because
`Rpc.call` matches `_SECRET_RE` against every argument and pushes to
stdin whether the caller asked or not. **Both have to be defeated before
the key reaches a process listing**, and the mutation that proves the
check bites had to disable the guard AND the explicit flag together.
That is the invariant the 2026-09-05 argv leak put there, working on a
call path written four days later that never had to know about it.

### Not covered here, and covered elsewhere

Swap. `image/leak-check.sh` refuses `swapon`, `dphys-swapfile` and
`dev-zram0.swap` on the board, so the RAM this key sits in cannot reach
a disk. That check runs with the rest of the image work.

A core dump is the one thing neither this nor the image check reads. The
datadir is tmpfs and swap is off, so a dump would have to be written to
the card by something that is not running. It is worth a line in the
image hardening rather than a ticket here.
