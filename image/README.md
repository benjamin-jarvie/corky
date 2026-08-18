# Corky image kit

Dev-image build, two steps, both scripted:

1. Flash Raspberry Pi OS Lite **64-bit** (per `PINS`) with Raspberry Pi
   Imager — enable SSH and set a user in Imager's settings.
2. `./image/prepare-sd.sh` with the SD still mounted, then boot the Pi on
   an Ethernet cable and run `sudo bash /boot/firmware/corky-provision.sh`.

The result is the **dev image**: Corky at `/opt/corky`, verified Core
binary, ramdisk datadir at `/run/corky`, SPI enabled, `corky.service`
installed but not enabled, SSH on. The **release image** (no network
stack, read-only root, reproducible hashes) is the M3 deliverable and is
deliberately not produced by these scripts.

`PINS` is the whole release: OS image, Core version, and Corky commit,
each with hashes. The two `UNPINNED_UNTIL_FIRST_FLASH` values get recorded
on the first real flash and pinned thereafter.
