# Corky image kit

Dev-image build, two steps, both scripted:

1. Flash Raspberry Pi OS Lite **64-bit** (per `PINS`) with Raspberry Pi
   Imager — enable SSH and set a user in Imager's settings.
2. `./image/prepare-sd.sh` with the SD still mounted, then boot the Pi
   on the network and run `sudo bash /boot/firmware/corky-provision.sh`.
   Network per board: the CM4 carrier has an Ethernet jack, use the
   cable. The Zero 2 W has no Ethernet port: set WiFi in Imager's
   settings before flashing, as m0/FLASH.md says.

What the device ends up carrying, and why each package is there, is one
table in the top-level README under "What runs on the signer". Developer
tools come from `requirements-dev.txt` and never go on the board.

The USB PSBT channel mounts itself: `99-corky-usb.rules` starts
`corky-usb@.service` when a stick is plugged in, which mounts its first
partition at `/mnt/usb`, and stops it when the stick is pulled. Only vfat
and exfat, and `noexec,nosuid,nodev`, because auto-detecting the filesystem
would hand an untrusted stick its pick of the kernel's filesystem drivers.
The boot card is the other file medium: `/boot/firmware` is FAT32 and any
computer reads it after power-off.

The result is the **dev image**: Corky at `/opt/corky`, verified Core
binary, ramdisk datadir at `/run/corky`, SPI enabled, `corky.service`
installed but not enabled, SSH on. The **release image** (no network
stack, read-only root, reproducible hashes) is the M3 deliverable and is
deliberately not produced by these scripts.

`PINS` is the whole release: OS image, Core version, and Corky commit,
each with hashes. The two `UNPINNED_UNTIL_FIRST_FLASH` values get recorded
on the first real flash and pinned thereafter.

## Security posture of the DEV image (plainly)

- `provision.sh` sources `corky-PINS` from the FAT32 boot partition as
  root: **anyone with physical access to the SD card before provisioning
  can run code as root.** That is acceptable for the dev image (which also
  has SSH on and holds no keys), and unacceptable for release — the M3
  release image has no provisioning step at all.
- Core binary installs are refused until `CORE_SHA256` is pinned; verify
  the hash out-of-band (SHA256SUMS + Guix attestation keys on a trusted
  machine), then pin. A checksum fetched from the same server as the
  binary proves nothing and is not used as a gate.
