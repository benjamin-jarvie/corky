# Map: the pure signer end to end, before testers arrive

Labels: wayfinder:map
Opened 2026-09-04. Charted with Ben in one grilling session; the closed
tickets below are that session's decisions, one per ticket.

## Destination

An outsider with a Sparrow laptop, a Bitcoin Core laptop, or a phone wallet
can generate a key on Corky, export the public key, receive, send, back up on
paper and as a Core-encrypted file, power-cycle, restore, and send again.
Every screen for that is decided, built, proven on the Zero 2 W, and written
down so a tester can repeat it. Phone wallets count: BlueWallet, Green and
Bull Bitcoin are researched, then proven with Ben's phone.

## State at handoff (2026-09-05, session switching model)

Done: every ticket except the three that need hardware or a person.
Decisions 01 to 07; built 08, 09, 10, 11, 12, 13, 14, 15, 16, 17; research
19, 20, 21. **Left: 18 (the board run with Ben and his Sparrow laptop), 22
(the phone proofs with Ben's phone), 23 (docs, PINS and the two-axis
review).** 18 is the gate the other two wait on. The board at
`corky-zero` still runs the ticket-10-era build: a sync was stopped
mid-copy, so run the rsync below before touching the board, then
`sudo systemctl restart corky`.

    rsync -a --delete --exclude .git --exclude .hypothesis --exclude __pycache__ \
      --exclude .build --exclude art/screens --exclude PINS.installed \
      --rsync-path="sudo rsync" ./ corky-zero:/opt/corky/

Tests: `./run_tests.sh` (fast), `RUN_NODE=1 ./run_tests.sh` (needs bitcoind),
always with `PYTHONDONTWRITEBYTECODE=1` (TESTING.md). Nothing is committed
yet: the whole map's work sits in the working tree for the two-axis review.

## Notes

- **Ben's instruction (2026-09-04): execution is carried in-map.** Chart,
  then build, as the M1 map did. Decisions and code both land here.
- **Do not reinvent the wheel.** The UI follows SeedSigner's structure and
  Core's vocabulary. When a screen has no counterpart in either, ask before
  inventing one.
- **Zero lines that touch a key.** PLAN A-22 stands. Every feature here is a
  screen over a Core RPC. If a feature needs code that transforms secret
  material, it belongs in the lab, not on this map.
- Words: `CONTEXT.md` at the repo root. Use them.
- Testing rules: `TESTING.md`. Rule 8 for every coordinator (run the
  counterpart), rule 9 for every channel (the board is the evidence).
- Style: ASD-STE100. No em dashes in new prose.
- Ben's laptop has a camera and Sparrow. The Sparrow flow is QR both ways.
  This Mac has no camera.

## Decisions so far

- [01 The destination](tickets/01-destination.md), Sparrow and Core laptops
  proven on the board; phones researched then proven with Ben's phone; mainnet.
- [02 Home is Scan, Key, Tools, Settings](tickets/02-home-tiles.md) , 
  SeedSigner's four tiles; key generation moves under Tools.
- [03 Several keys at once](tickets/03-several-keys.md), one Core wallet per
  key, named by fingerprint, cap five; the key screen appears only when more
  than one key is loaded.
- [04 The file backup is Core's own](tickets/04-file-backup-is-core.md) , 
  encryptwallet then backupwallet, proven; the SD-card rule is amended to
  "only when you ask"; unlock once at restore; destination asked every time.
- [05 Scan detects by content](tickets/05-scan-detects-by-content.md) , 
  transaction, key or address, decided by what the camera read.
- [06 Export public key](tickets/06-export-public-key.md), SeedSigner's
  wallet chooser, all five shown, phones marked untested; plain descriptor QR,
  no UR; Core gets a watch-only wallet file.
- [07 Menus in Core's vocabulary](tickets/07-menus.md), Tools holds New key
  only; Key holds Sign transaction, Export public key, Receiving addresses,
  Backup key, Discard key.

- [19 BlueWallet](tickets/19-research-bluewallet.md), takes the plain
  descriptor QR for wpkh and tr, returns `ur:crypto-psbt`; wire to the
  Sparrow format, untested until the phone proves it.
- [20 Green](tickets/20-research-green.md), takes the plain descriptor QR
  for wpkh and tr, returns `ur:crypto-psbt` behind Jade-labelled buttons;
  wire to the Sparrow format, watch the Jade prompt on the phone.
- [21 Bull Bitcoin](tickets/21-research-bull-bitcoin.md), takes the plain
  descriptor QR for wpkh only, no taproot; returns `ur:crypto-psbt` when the
  signing device is set to SeedSigner.

- [08 Prove no key material persists](tickets/08-no-persistence.md), 13
  checks that grep the whole datadir for the raw key bytes; found Core
  echoing keys into errors (now redacted before they reach the journal) and
  nothing clearing wallets after a crash-restart (now `clear_on_start`);
  Core's log file turned off properly.
- [10 Several keys in Core](tickets/10-several-wallets-in-core.md), slots
  `corky` to `corky-5`, fingerprints on screen, owner matched from Core's
  decodepsbt, duplicates refused by name; wallet_dir bug found and fixed.
- [11 Home and menus](tickets/11-home-and-menus.md), Scan, Key, Tools,
  Settings built; keys list, key menu, discard confirmation, paper backup by
  fingerprint; every scripted session re-sequenced.

- [12 Build the export](tickets/12-export-flow.md), wallet chooser, plain
  descriptor QR proven byte-identical through Sparrow's own zxing at both
  panel sizes, grouped text, three full addresses, and a Core watch-only
  wallet file a second Core restores.

- [13 File backup and restore](tickets/13-backup-and-restore.md), Core's
  own encryptwallet and backupwallet on a scratch copy so the loaded key
  keeps working; restore lists backups by fingerprint and unlocks once for
  the session; every refusal tested with real wrong data.

- [09 Key scan](tickets/09-key-scan-wiring.md), one `strings()` generator
  for both scans, 20-second no-progress timeout, B or C aborts, camera-less
  board says why at once, viewfinder throughout, A-11 guards in one place.
- [17 Errors held on screen](tickets/17-errors-held-on-screen.md), a named
  catch set around the sign loop (D18), teardown failures reported (D17),
  and an empty file on the stick now named on screen instead of leaving the
  device asking for a stick it already has.

- [15 Stick and card](tickets/15-stick-and-card-channels.md), udev starts
  a mount unit for a USB partition at `/mnt/usb`, vfat and exfat only with
  noexec, and signed writes are fsynced so a pulled stick still carries
  them; the board half waits for ticket 18 and an OTG adapter.

- [14 Receiving addresses](tickets/14-receiving-addresses.md), receive
  branch only, ten at a time, paging without end, script type asked first.
- [16 Repairs after the A-22 cut](tickets/16-repair-after-a22.md), the
  Sparrow harness, the M0 gate, both mainnet proof scripts and the screen
  renderer all run again.

- [24 Developer tooling and the signer allowlist](tickets/24-dev-tooling-and-signer-allowlist.md)
 : ruff, vulture and mypy on the dev machine only; no formatter; types on
  the signer seam; the README table of what the device carries, enforced as
  an import allowlist; four pieces of dead code and six duplicate menu loops
  removed.

## Review round (2026-09-05)

`/mp-code-review` against the fork point, two axes, run before ticket 18's
board gate as TESTING.md rule 5 requires. Every finding was reproduced
before it was acted on; none was taken on trust.

**The one that mattered.** `backup_encrypted` and `write_watch_only` build
a scratch wallet, and the backup scratch holds the PRIVATE descriptors
between `createwallet` and the `finally` that deletes it. Both clears
walked `SLOTS` only, so a crash in that window left a plaintext key on the
ramdisk that neither `close_session` nor the next session's
`clear_on_start` would ever drop. Reproduced, then fixed: both now drop
every wallet Corky owns, `corky` and anything `corky-`, and
`tests/test_no_persistence.py` builds an abandoned scratch and proves both
clears take it.

Also fixed, from the Spec axis: the Scan tile now detects by content as
ticket 05 decided, including an address checked against every loaded key
with `getaddressinfo`; Scan no longer polls the USB stick; the medium is
asked every time as ticket 04 decided, even when only one exists; the
address screen colours the head and tail groups in place rather than in a
footer; and a review with no key loaded no longer divides by zero.

From the Standards axis: the code now uses `CONTEXT.md`'s words, so
`seed_menu` is `load_key_menu` and `share_pages` is `text_pages`;
`signer.py` moved from layer 3 to layer 2 in the README, because it takes
an xprv and a passphrase and always did; one banned "not X, it is Y"
sentence is gone; `find_backups` no longer claims an order it does not
have; the six extended-private-key prefixes live in one list that the
redactor and the scan classifier share; and the key-scan surface now has a
real-data round trip in `tests/sparrow/test_export_interop.py`, where a
real descriptor and a real xprv go through the renderer, Sparrow's zxing,
the classifier and the A-11 guards.

## Review round two (2026-09-05)

`/mp-code-review` again, same fixed point, briefed to verify round one's
fixes as well as look for new defects. Seven of eight Spec fixes and three
of five Standards fixes verified as landed; the rest were partial, and one
review claim did not survive checking.

**What round two found in round one's work.**

- `_key_by_scan` still carried its own two-prefix copy of what a private
  key looks like, while `_classify_qr` used the shared list of six. The
  shotgun-surgery fix had missed a site.
- The Scan tile skipped a stray code silently, while its own docstring and
  ticket 05 both say "count it". It counts now, and the count is on screen,
  which is what tells the operator the camera is reading at all.
- A descriptor was anything with brackets, so a URL was handed to Core to
  refuse. It is now recognised by Core's own function names.
- A phone shows `bitcoin:bc1q...?amount=`, not a bare address, so the
  address row could never have fired for the wallets ticket 22 will test.
- A failed `clear_on_start` was swallowed, so ticket 08's promise could be
  false with nothing on screen.
- `_show_addresses` and `_browse_addresses` disagreed about what B does on
  the same screen. One function now, one key map.
- **A fabricated test literal.** `test_keyscan.py` called its descriptor
  "from Core, not a plausible-looking literal", and Core rejects it: the
  checksum belongs to a different descriptor. That is the exact rule-1
  failure the round-one fix claimed to close. Corrected from
  `getdescriptorinfo`, with the story kept in the file.
- **A self-referential test.** The backup-filename check built its probe
  from the screen's own constants, so it could never see them drift. It now
  uses a filename `backup_encrypted` actually wrote.
- Em dashes in every piece of prose written this session, `CONTEXT.md`
  included, against Ben's standing rule. All gone.
- `medium` was a synonym for `CONTEXT.md`'s **channel**. Renamed.

**One claim that did not survive checking.** The Standards axis read the
"no it's not X, it's Y" rule as banning the contrast in either order, and
flagged "It is a KEY, not a wallet". The rule bans the reversal, where a
negation comes first. Assert-then-qualify is ordinary English and stays.

**And one defect neither axis found**, turned up by auditing every
`createwallet` call while they read: `_next_slot` counted only LOADED
wallets, so a slot directory left on disk made the next key load die on
Core's raw "Database already exists", with no key loadable until reboot.
It now counts the same wallets the clears do.

**A new guard, because the safety net was too slow.** A rename left
`for _kind, path in media:` in a branch only the restore flow reaches, and
the only thing that caught it was a five-minute end-to-end run.
`tests/test_undefined_names.py` walks every function's scope and fails on a
name that is never bound. It was checked by reintroducing the real bug.
`run_tests.sh` now also runs the three Sparrow suites when their build
exists, because those hold the only coverage that reads a QR with a decoder
that is not ours.

Final state: 27 suites green, including the 81 interop checks.

## The board, answered (2026-09-05)

Ben asked whether a Zero 2 exists with no radio, because that board fits
the enclosure and the CM4 does not. Full findings, primary sources only:
[research/pi-zero-radio.md](research/pi-zero-radio.md).

**No Zero 2 without the W was ever sold, and no Zero-class board has been
released since 2021.** The only radio-free board in the 65 x 30 mm form
factor is the ORIGINAL Pi Zero, still in production to at least January
2030, and v1.3 has the camera connector.

**It cannot run our Bitcoin Core.** The original Zero is ARMv6. Core's
release builds are `aarch64-linux-gnu` and `arm-linux-gnueabihf`, and the
release build sets no `-march`, so the 32-bit binary carries the standard
armhf baseline, which is ARMv7. Running Core on ARMv6 means building it
ourselves, and then the binary is one that only we have verified, instead
of the official one with eleven signatures checked out of band. That trade
is the whole project in reverse. This is the same conclusion Ben reached
when he rejected the Zero 1.3 for its cross-compile burden.

**The useful finding: the Zero 2 W's radio is a separate component.** The
RP3A0 system-in-package holds only the processor die, the memory die and
capacitors. The radio is a Synaptics part beside it, so it can be reached
without touching the processor. That supports the decision already
recorded in the zero2w-m0-fixes map, that the pocket build instructs
physical removal.

**Two cautions for whoever does the removal.** Raspberry Pi changed the
part from SYN43436SXKUBG to SYN43436PXKUBG on 1 November 2025 and ships
four Wi-Fi firmware variants, so the board in hand must be inspected
rather than assumed. And `dtoverlay=disable-wifi` disables the SDIO host
controller only; nothing in the documentation says the radio loses power.
A real hardware disable pin is documented for the Compute Modules, not for
the Zero 2 W.

## Not yet specified

- Whether the backup passphrase needs a minimum length or a warning line.
  The grid takes 84 characters and Corky refuses only an empty one; Core
  accepts anything else.
- What the "untested" mark on a phone entry says on screen, and whether an
  untested entry shows the plain descriptor QR or refuses.
- Whether the Bitcoin Core chooser entry also shows the descriptor QR beside
  writing the wallet file.
- How the card channel meets the M3 RAM-resident image, where the card may
  be pulled while running. Writing to the boot partition on the dev image is
  settled; the release image is not.
- QR size of a descriptor on the 240x240 pocket panel. A 130-character
  descriptor is a version 7 code; whether it renders at 4 px per module there.

## Out of scope

- A network switch in Settings. Ben, 2026-09-04: mainnet only for this map.
  Testers use small mainnet amounts. Signet needs Core restarted with a chain
  flag and is its own effort.
- Multisig. Ben: down the road.
- UR encoding of the public key. Ben: no UR if the plain descriptor works,
  and it does for Sparrow and Core.
- Message signing, BIP-85, codex32, seed words, silent payments. Lab.
