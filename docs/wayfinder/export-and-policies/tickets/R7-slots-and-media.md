# R7 Card slots, USB, and where the private key is allowed to go

Type: `wayfinder:research`. **Closed 2026-09-05, with one correction that
changes the decision it was asked for.**

## Question

Ben: "the zero 2 w has only one microSD so you can and should only be able
to export by writing it down on paper, no encryption needed. That software
moves to the CM4 fork we have, also does CM4 have two microSD ports? If
not it has USB etc from base so you could just use some adapter securely
right?"

## 1. The CM4 has no configuration with two usable card slots

From Raspberry Pi's own Compute Module documentation, describing the IO
board: **"A microSD card slot (only for use with CM4Lite, which has no
eMMC; other variants ignore the slot)."**

| module | card slot | boots from |
|---|---|---|
| CM4 Lite, e.g. CM4002000 | one, and it is the boot device | microSD |
| CM4 with eMMC | present but **ignored** | soldered eMMC |

The Waveshare CM4-IO-BASE-B in the plan has one microSD slot, **two USB
2.0 ports** behind a built-in hub, and an M.2 slot.

So the answer to the question as asked is **no**. But the eMMC variant
solves the problem a better way than a second slot would: the boot device
is soldered down, so there is no card to remove, both USB ports are free
for data, and the operating system does not need to live in RAM for Ben's
workflow to work at all. On the Lite it does. That is a real argument for
buying eMMC rather than Lite, and it was not in A-15's reasoning.

## 2. The premise about the Zero is not quite right

**USB host already works on the Zero 2 W.** Checked on the board:
`config.txt` carries `otg_mode=1` and `dtoverlay=dwc2,dr_mode=host`, a USB
root hub is registered, and `provision.sh` blacklists every gadget module
so the port cannot be turned around into a device. A USB stick or a USB
card reader on an OTG adapter works today, and it does not touch the boot
card.

So "one slot, therefore paper only" does not follow. Paper-only is a
choice worth making on its merits, not a constraint the hardware imposes.

## 3. Is a USB adapter "secure"

Roughly as secure as the native slot, and both share the part that
matters. Either way the kernel mounts a filesystem somebody else wrote,
and filesystem parsers are where the exploitable bugs have historically
been. USB adds the host stack and the mass-storage driver on top of that,
so it is more surface, but not a different category, and Corky already
accepts exactly this risk for its USB stick channel.

The far bigger lever is what the medium is allowed to carry.

## Recommendation, and it is Ben's call

Draw the line at the key rather than at the medium:

- **The private key leaves on paper and photons only.** No file backup, no
  encryption, no passphrase. That deletes `backup_encrypted`,
  `restore_encrypted`, `_ask_passphrase`, the encrypt menu, the
  no-passphrase warning and Restore from file, and with them the entire
  A-23 hedge about a key on a card. A malicious card then cannot exfiltrate
  a key that was never written to one.
- **Public data keeps the file channel.** The watch-only wallet file that
  Bitcoin Core needs, and PSBTs. The worst a hostile card can do there is
  hand Core something Core rejects.

The cost, stated plainly: **the only backup becomes 111 handwritten
characters.** No second copy, no encryption at rest, and no way to restore
except by typing them back. That is a real reduction and it is why this is
Ben's decision and not mine. The paper check built on 2026-09-05 exists
precisely because that string has to be right the first time.

Not implemented pending his word, because deleting the encrypted backup is
destructive and the premise it was proposed on turned out to be
incomplete.
