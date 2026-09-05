# 18 The full run on the board with Ben's Sparrow laptop

Labels: wayfinder:task (HITL)
Blocked by: 09, 10, 11, 12, 13, 15, 16, 17

## Before the card goes in (2026-09-05)

Everything below is done, so the flash is a clean run of the real path
rather than a repair of the board that is on the desk. Flash a fresh card;
do not reprovision the old one, because the old one has never seen the
current image kit.

Done, and why each mattered:

- The image carries the program and nothing else, 39 files and 0.27MB,
  where `git archive HEAD` used to put the whole repository on the card.
- `provision.sh` installs each required package on its own line. The old
  form asked for seven at once and fell back to a list that quietly
  dropped `python3-picamera2`, so an unavailable `python3-zbar` would have
  cost the camera and said nothing until a scan failed here.
- `nodebuglogfile=1`, so Core writes no log into the ramdisk. The old
  `debuglogfile=0` NAMED a log file called `0`.
- The USB channel mounts itself: a udev rule starts a mount unit, vfat and
  exfat only, `noexec,nosuid,nodev`. Never run on hardware.
- Every key Corky owns is dropped at startup and at close, scratch wallets
  included.

Still open when the card goes in, in the order they will bite:

1. **`OS_IMAGE_SHA256` is `UNPINNED_UNTIL_FIRST_FLASH`.** Record the
   sha256 of the image Raspberry Pi Imager downloads, into `image/PINS`,
   at the moment of the flash. It cannot be recovered later.
2. **`CORE_SHA256` is pinned and provisioning refuses to install without
   it.** That is deliberate. It is already pinned, and the eleven
   signatures were checked out of band on 2026-09-03.
3. **A micro-USB OTG adapter**, micro-B male to USB-A female, for the
   stick. The Zero 2 W has one data port. Whether the SeedSigner case
   exposes it is unknown.
4. **`m0/m0_gate.py` has not run since it was ported off the shim.** It
   reads `/proc/meminfo`, so it cannot run anywhere but the board.
5. **`tests/hw_buttons.py` and `tests/hw_camera.py` do not ship any more.**
   Run them from a clone, or copy them across by hand.
6. **Sparrow on the laptop**, with QR density set to Low.

## Question

Prove the destination on the Zero 2 W with Ben at the board and Sparrow on
his laptop, mainnet, small amounts. Ben's checklist:

1. Tools, New key. Write the xprv from the screen onto paper.
2. Key, Export public key, Sparrow, native segwit. Scan the QR into Sparrow
   as a new wallet. Compare the three addresses on Corky's screen with
   Sparrow's first three, every group.
3. Fund the first address from another wallet. Watch it arrive in Sparrow.
4. Sparrow: send a small amount, QR density Low. Corky: Scan, read the
   animated QR. Check fee and outputs match Sparrow's to the satoshi. Sign.
   Sparrow scans the signed QR with the laptop camera and broadcasts.
5. Key, Backup key, file. Type a passphrase. Write it to the card.
6. Power off. Power on. Key, Load a key, Type xprv from the paper. The
   fingerprint on the Key tile must match the one Sparrow shows.
7. Send again, as in step 4.
8. Take the card to another computer running Core. File, Restore Wallet, the
   file from step 5, the passphrase. The restored wallet's first address
   must be the address funded in step 3.

Record the two transaction ids, the block heights, the fingerprint, and
every screen that surprised Ben, in this ticket. TESTING.md rule 9: only
the board is evidence for the channels.
