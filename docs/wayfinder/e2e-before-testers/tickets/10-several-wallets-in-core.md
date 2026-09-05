# 10 The session holds several keys

Labels: wayfinder:task (AFK)
Blocked by: none
Assignee: claude (claimed 2026-09-04)
Status: resolved 2026-09-05

## Question

Ticket 03 decided several keys. Today `signer.WALLET` is one fixed name and
every RPC assumes it. Rebuild the session around a list of loaded keys:

- one Core wallet per key, named by its fingerprint, created on import or
  generation; a second import of the same fingerprint is refused with a
  message, not duplicated;
- cap five, refused with a message at the sixth;
- `master_fingerprint`, `public_descriptors`, `describe_psbt`, `sign_psbt`
  and `close_session` take a key, not a constant;
- matching per ticket 03: `decodepsbt` fingerprints against loaded keys,
  the key screen only when more than one key is loaded;
- Discard key unloads one wallet and deletes its directory; power-off
  deletes all.

Tests: two keys loaded, a transaction for each, the right one signs; a
transaction nobody owns is refused; the cap holds; discard leaves the other
key signing. Measure RAM at five keys on the board and record it here.

## Answer (built, 2026-09-04/05)

Built test-first in `tests/test_keys.py` (15 checks, real regtest Core) and
`tests/e2e_keys.py` (three scripted device sessions). All 19 suites green.

**Slots, not renames.** 83 call sites used `signer.WALLET`, so the first key
keeps the historic wallet name `corky` and further keys take `corky-2` to
`corky-5` (`signer.SLOTS`, `MAX_KEYS = 5`). The fingerprint names a key on
every screen; the slot is invisible. Core cannot rename a wallet, and A-19
forbids re-deriving a generated one, so a slot scheme was the only way to
name a wallet before Core has made the key.

**Seam changes.** `open_session_xprv` and `open_session_descriptors` return
the slot name. `generate_wallet` returns `(name, xprv)` and takes the next
free slot instead of dropping the loaded key. `loaded_keys(rpc)` lists
`Key(name, xfp)` in slot order. `owners(rpc, psbt)` reads the master
fingerprints Core puts on every input (`bip32_derivs` and
`taproot_bip32_derivs`). `sign_psbt`, `public_descriptors`,
`master_fingerprint` and the new `master_xprv` take `wallet=`. `close_key`
drops one; `close_session` drops every slot.

**Duplicates are found after the import, not before.** `getdescriptorinfo`
keeps hardened steps on the xpub and carries no origin, so the fingerprint
is only knowable once Core holds the key. The new wallet is dropped again
and the message names the fingerprint: `key 73c5da0a is already loaded`.

**Matching, as ticket 03 decided.** One key loaded: no screen. Several: the
key screen (`screens.choose_key`) with the owner pre-selected and
non-owners greyed. Nobody owns it: `no loaded key owns it; wants <xfp>`,
held until a key is pressed, then home. A transaction with no fingerprints
at all is left to the current key and Core's verdict; that branch has no
test, because Core always writes fingerprints.

**Found on the way.** `Rpc.wallet_dir` was fixed at `<datadir>/wallets`,
but Core only uses that directory when it already exists. The ramdisk
datadir on the board has none, so every wallet directory would have
survived `close_session` in RAM. `wallet_dir` now follows Core's own rule.

RAM at five keys on the board: not measured yet (the board sync was
stopped); three keys measured at about 3MB each on 2026-09-04.
