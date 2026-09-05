# 15 The stick mounts itself, and the card can be written

Labels: wayfinder:task (AFK, then a check on the board)
Blocked by: none
Status: resolved 2026-09-05 (board half is ticket 18)

## Question

Two file channels need to exist for a tester:

1. **Stick.** `provision.sh` says mounting is "the operator's step". A udev
   rule or a systemd automount must mount the first partition of a USB
   stick at `/mnt/usb`, and unmount cleanly when it is pulled. The Zero 2 W
   has one micro-USB data port; the image already sets host mode
   (`otg_mode=1`, `dtoverlay=dwc2,dr_mode=host`), and `lsusb` on the board
   shows the root hub with nothing on it. A micro-B to USB-A OTG adapter is
   needed. Check whether the SeedSigner case exposes the port.
2. **Card.** `/boot/firmware` is FAT32 and mounted read-write on the dev
   image. Corky writes exports and file backups there when the user chooses
   the card. Any computer reads it after power-off.

Tests: the stick path needs the board and an adapter. The card path is a
file write and is testable on the Mac with a temp dir standing in.

## Answer (built, 2026-09-05)

**The stick mounts itself.** `image/99-corky-usb.rules` starts
`corky-usb@<partition>.service` when a USB partition appears and stops it
when the partition goes, and that unit mounts and unmounts `/mnt/usb`.
`provision.sh` installs both and reloads udev.

Three choices in the mount options, all deliberate:

- **`-t vfat,exfat`, never auto-detect.** Letting mount pick would hand an
  untrusted stick its choice of the kernel's filesystem drivers, which is a
  large attack surface to open on a signer for no gain. Sticks are FAT.
- **`noexec,nosuid,nodev`.** Nothing on a stick may ever be executable here.
- **`flush` and `umask=0077`.** The user pulls the stick straight after the
  result screen, and a PSBT is nobody else's business.

**And the write is forced down before the screen says it is written.**
`write_signed` now fsyncs the file and its directory. A signature still in
the page cache when the stick is pulled is a signature that never left the
device, and the result screen would have said it had.

**The card** is `/boot/firmware`, FAT32 and mounted read-write on the dev
image. `corky.service` passes it as `--card-dir`, so the medium chooser
offers it beside the stick for the export and the encrypted backup, and any
computer reads it after power-off.

**Not proven here.** Everything above except the fsync needs the board and
an adapter: the Zero 2 W has one micro-USB data port, host mode is already
set in `config.txt` (`otg_mode=1`, `dtoverlay=dwc2,dr_mode=host`), and
`lsusb` on 2026-09-04 showed the root hub with nothing on it. A micro-B to
USB-A OTG adapter is needed, and whether the SeedSigner case exposes the
port is still unknown. Ticket 18 checks all of it.
