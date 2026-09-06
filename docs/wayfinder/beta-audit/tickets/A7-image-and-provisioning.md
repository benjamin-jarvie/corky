# A7 The image a tester flashes

Type: `wayfinder:task`, AFK. **Needs the board to confirm.**

**Blocked by:** Nothing, and it needs the board to confirm a flash.

## Question

A tester does not get this repository. They get a card. Nothing has
audited what is on it.

`image/` holds `provision.sh`, `harden.sh`, `prepare-sd.sh`,
`leak-check.sh`, three systemd units, a udev rule and a mount unit.
`tests/test_image_contents.py` checks the archive carries what
`provision.sh` reaches for, and that is the only automated check there is.

It is also demonstrably not enough: on 2026-09-05 the board had never had
the USB mount rule installed, because it was provisioned before those
lines existed, and every suite stayed green while the file channel could
not work at all. The repo was right and the board was wrong, and nothing
compared them.

Answer:

- what a fresh flash actually produces, run end to end, not read;
- whether `harden.sh` closes what it claims: 13 of 22 leak rows fail on
  the dev image and nobody has watched them go to zero;
- what `provision.sh` does when a step fails halfway, since it is a shell
  script with no transaction;
- whether the pinned Core hash is checked on the device or only on the
  builder;
- what a tester can verify for themselves without trusting either of us.

---

## Answer (2026-09-06)

**The board was running two things the repository had already fixed.**
Asked it directly rather than reading the scripts.

### What was actually on the card, against what the repo says

| installed file | verdict |
|---|---|
| `corky-bitcoind.service` | matches |
| `corky-splash.service` | matches |
| `corky-usb@.service` | matches |
| `99-corky-usb.rules` | matches |
| **`corky.service`** | **differs** |
| **`/etc/corky-bitcoin.conf`** | **differs** |

- **`corky.service` had no `--card-dir`.** The card channel did not exist
  on the device. That is ISSUES **E-5**, "Core's file has nowhere to go",
  fixed in the repository and never installed. With no stick mounted
  either, the board had nowhere at all to write a watch-only wallet.
- **`bitcoin.conf` still carried `debuglogfile=0`.** Core reads that as a
  FILENAME. A file called `0` was sitting in the ramdisk holding **5,736
  bytes of Core's log**, and Core's own first log line warns the log may
  contain privacy-sensitive information. Ticket 08 fixed this in the repo
  on 2026-09-04.

Both are now installed and the log file does not come back: stopped the
node, deleted `0`, started it, and the file stayed gone. Worth knowing
that the stale file **survives the config fix** until the process
restarts, because Core holds it open; on a real device the ramdisk dies
at power-off, so it cannot outlive a session.

### image/verify-install.sh

The answer to this ticket and to "what can a tester verify for
themselves". It runs **on the device**, reads only, changes nothing:

- every installed file against the repository at `/opt/corky`, by sha256,
  printing the diff when they disagree;
- both Core binaries against pinned hashes;
- each channel against what is actually mounted;
- the ramdisk against the log file that should not be in it.

It reads the **repository's** `image/PINS`, not `PINS.installed`.
Checking a device against a copy of whatever that device was built from
is asking the suspect for an alibi, and the first version did exactly
that: run on the board, it reported "no hash pinned" for both binaries.

The board passes it now. `tests/test_image_contents.py` fails if it stops
shipping.

### Bitcoin Core, verified rather than assumed

`provision.sh` checks the tarball against `CORE_SHA256` at install time
and never again, which is the one moment nobody is watching. So:

1. Downloaded the pinned tarball. `core.tgz: OK` against `CORE_SHA256`,
   the hash carrying 11 GPG signatures checked out of band on 2026-09-03.
2. Extracted `bitcoind` and `bitcoin-cli` from it.
3. Compared with the board's.

```
bitcoind     1b279e038691c10e30d9c99a071ff967439020c4352e8ea3b156fb6b03751f83
bitcoin-cli  815c0969dabe4b67d180f3e0c597c995ca03fd3a65ff2b2d1b1223109f6df589
```

**Identical, byte for byte.** The Core on Ben's board traces to those 11
signatures. Both hashes are now in `image/PINS` so any installed device
can be re-checked without an 82MB download, and the suite fails if they
go missing.

### What provision.sh does when a step fails halfway

`set -euo pipefail`, so it stops at the first failure and leaves a
partial install. It is idempotent and re-running completes it. That was
always the design; what was missing is any way to tell whether the
re-run finished the job, which is now `verify-install.sh`.

### harden.sh: mapped, not run

The dev image fails **13 of 26** leak rows. Each one maps to a step:

| failing rows | closed by |
|---|---|
| Wi-Fi and Bluetooth overlays | 1/5, `disable-wifi` and `disable-bt` |
| both drivers loaded, blacklist missing | 2/5, `corky-no-radio.conf` |
| radio firmware on the card | 3/5, moves `/lib/firmware/brcm` |
| Wi-Fi and Bluetooth services, network manager | 4/5, masks nine units |
| **remote login running** | 4/5, masks `ssh` and `sshd` |
| wlan0 present, BT device present, radio up at boot | consequences of 1 to 4, after a reboot |

Nothing fails that the script does not address. **Running it needs Ben.**
It is one way, it removes SSH, and reflashing the card is the only way
back, so watching 13 go to 0 is his call to authorise. Nothing else in
this audit is blocked on it.

### One gap found in the leak check itself

It verified four of the five units. `corky-splash.service` was missing,
and it is the one that paints the first thing anybody sees; a board
without it boots to a dark panel for the length of a bitcoind start and
looks broken. 26 rows now, not 25.

### Still open, and it belongs to the verdict

`OS_IMAGE_SHA256="UNPINNED_UNTIL_FIRST_FLASH"`,
`DEV_IMAGE_SHA256="RECORDED_AFTER_PROVISION"` and
`CORKY_COMMIT="HEAD"` are placeholders. A tester's card cannot be
reproduced from `image/PINS` as it stands, and `CORKY_COMMIT=HEAD` means
two testers flashing a week apart get different signers. A11 has to weigh
that.

The card is also mounted by the OS with `fmask=0022`, so a PSBT written
to `/boot/firmware` is world-readable, where the stick's own unit sets
`umask=0077` and its comment says "a PSBT is nobody else's business". The
two channels disagree, and the card's options come from the image's
`fstab`, not from this repository. Carried from A3.
