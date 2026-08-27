# Corky order list — US Amazon
*2026-08-18. Five items, ~US$130. Display/controls/case NOT needed: Ben's
SeedSigner+ hat (MadBo/Rothery v1.0.1 pill PCB) is the front end.*

## Buy

1. **Raspberry Pi CM4 Lite, 2GB, NO wireless — code CM4002000**
   https://www.amazon.com/Raspberry-Compute-Module-Bluetooth-CM4002000/dp/B0BF98TRZH
   - Title must say CM4002000 exactly. Reject CM4102xxx (wireless) and
     CM4002008 (eMMC). 4GB CM4004000 is an acceptable substitute.
   - Bundle alternative (heatsink incl.; discard antenna kit):
     https://www.amazon.com/Waveshare-Raspberry-Compute-Compact-Without/dp/B08PVL2378
   - If scalped, list price: https://www.pishop.us/product/raspberry-pi-compute-module-4-2gb-lite-cm4002000/
   ~US$50

2. **Waveshare CM4-IO-BASE-B carrier (6-item bundle with FFC cables)**
   https://www.amazon.com/Waveshare-CM4-IO-BASE-B-Raspberry-Compute-Adapter/dp/B0991YLS6M
   ~US$35

3. **Official Raspberry Pi 15.3W USB-C PSU, 5.1V/3A, US plug**
   https://www.amazon.com/Raspberry-Official-Power-Supply-15-3W/dp/B07YD2LZDC
   ~US$14

4. **2× SanDisk High Endurance 32GB microSD**
   https://www.amazon.com/s?k=sandisk+high+endurance+32gb+microsd
   - Only a listing "Ships from and sold by Amazon.com" (counterfeit risk).
   ~US$20

5. **2× SanDisk Ultra Fit 32GB USB (PSBT sleds)**
   https://www.amazon.com/sandisk-ultra-fit-32gb/s?k=sandisk+ultra+fit+32gb
   - Same sold-by-Amazon rule.
   ~US$18

## Do NOT buy

- Display, buttons, jumper wires, camera ribbon (carrier takes the standard
  15-pin ribbon that ships with camera modules), HDMI adapters (carrier has
  full-size HDMI), OTG adapter (carrier has USB-A onboard).
- Ethernet cable: any existing one works for the dev image (SSH over wire;
  release image ships without a network stack).

## Mechanical note (measured 2026-08-18)

SeedSigner+ hat: pill-shaped, **146 × 50.8mm** (5.75" × 2"). Carrier:
**85 × 56mm**. The hat overhangs the carrier's length by ~60mm (it was
designed as the full faceplate of the metal case) and is **5mm narrower**
than the carrier, so ~2.5mm of carrier shows on each side. The carrier sits
behind the pill like the Zero did; the pill remains the face of the device.
The hat's USB-C is power-only with data pins disabled (silkscreened) — good;
power via the CARRIER's USB-C only, never both.

Open question for when parts arrive: underside clearance — whether the hat's
female header seats over the CM4+heatsink or needs a ~$3 stacking header.
Mounting holes will NOT line up with the carrier; standoffs or the case
design carry the mechanical load.

## Underside clearance — RESOLVED on paper (2026-08-27)

**Verdict: buy a stacking header. The standard 11mm HAT spacing does not clear
the CM4 plus any heatsink.**

Vertical stack, measured from the carrier's top copper:

| Item | Height | Source |
|---|---|---|
| CM4 mated on the 1.5mm DF40C socket | **5.08mm** | RPi CM4 datasheet (6.58mm if a 3.0mm DF40HC is fitted) |
| Waveshare CM4-HEATSINK | +5mm | 55 x 40 x 5mm |
| Waveshare CM4-HEATSINK-B | +10mm | 55 x 40 x 10mm |
| Thermal pad | +~0.5mm | typical |

- With the 5mm heatsink: **~10.6mm**. Available: 11.0mm. Gap **~0.4mm**.
- With the 10mm heatsink: **~15.6mm**. Available: 11.0mm. **Interference 4.6mm.**

The 11.0mm figure is the standard Pi HAT spacing: 2.5mm male header insulator
on the carrier plus an 8.5mm female socket body on the hat. It is why 11mm
standoffs are the HAT standard.

A 0.4mm gap is not a pass. That is a bare aluminium heatsink 0.4mm below the
hat's underside solder joints, with no mechanical constraint holding it there
(the mounting holes do not line up, see the note above).

**Buy: a 2x20 stacking header with a 16mm body.** That gives 18.5mm clearance:
7.9mm clear over the 5mm heatsink, 2.9mm over the 10mm one. ~US$3.
13.5mm bodies also exist and clear the 5mm heatsink only.

### Still unmeasured — check when the parts arrive

1. **Which heatsink is in the bundle.** 5mm or 10mm changes nothing about the
   decision, but confirm before trusting the 2.9mm margin.
2. **Is the CM4 inside the hat's footprint?** Near certain (146mm hat over an
   85mm carrier), but not confirmed from a layout drawing.
3. **USB-A under the hat.** A full-size USB-A port is 14.5mm tall. If one sits
   under the pill, even the 16mm stacking header (18.5mm) leaves only 4mm, and
   the ports become unusable. Waveshare publishes a 3D drawing (CM4-IO-BASE.7z)
   that settles this.
4. **The hat's own socket body height.** Assumed the standard 8.5mm. Measure it
   with calipers; an extra-tall socket already fitted would change the answer.

SPI0 runs at 40MHz. An extra 8mm of header pin is harmless at that speed. Do
not solve this with a ribbon GPIO extender.
