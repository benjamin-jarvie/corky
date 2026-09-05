# Raspberry Pi Zero form factor and the wireless radio

Research date: 2026-09-05. The question: can Corky's pocket build use a
Zero-form-factor board with no wireless radio fitted?

The SeedSigner enclosure takes a 65 mm x 30 mm board. The board needs the
standard 40-pin header position and a camera connector. A Compute Module on a
carrier board does not fit that enclosure.

**Source rule for this document.** Sections 1 to 5 use Raspberry Pi primary
sources only: raspberrypi.com product pages, raspberrypi.com documentation,
Raspberry Pi datasheets and product briefs on `datasheets.raspberrypi.com` and
`pip.raspberrypi.com`, and the Raspberry Pi news blog. Three sources sit in
Raspberry Pi code repositories and not on raspberrypi.com. This document marks
them **RPi repo**. Section 6 is **NON-PRIMARY** and this document marks every
claim in it.

## Verdict table

| # | Question | Verdict | Confidence | Source |
|---|----------|---------|------------|--------|
| 1 | Does Raspberry Pi make any Zero-form-factor board with no wireless chip fitted? | **Yes. The original Raspberry Pi Zero.** Raspberry Pi still sells it. The product page lists no wireless LAN and no Bluetooth. It stays in production until at least January 2030. Version 1.3 adds the CSI camera connector that SeedSigner needs. The official mechanical drawing gives 65 mm x 30 mm and four M2.5 holes at the same spacing as the Zero 2 W. Every other Zero-family board carries a radio. Raspberry Pi never sold a "Pi Zero 2" without the W. Raspberry Pi has released no Zero-class board after the Zero 2 W. | High | S7, S8, S9, S10, S1 |
| 2 | Zero 2 W: exact processor package, exact wireless chip, and is the radio inside the package? | Processor package: **Raspberry Pi RP3A0 system-in-package**. It holds the Broadcom BCM2710A1 die, a 4 Gbit Micron LPDDR2 die, and decoupling capacitors. **The radio is not inside the RP3A0.** The radio is a separate Synaptics part on the board. Raspberry Pi names it **SYN43436SXKUBG**, and changed it to **SYN43436PXKUBG** from 1 November 2025. So the radio can be reached without touching the processor. | High | S1, S4, S11, S3 |
| 3 | Zero 2 W RAM, and any larger variant? | **512 MB LPDDR2. No larger variant exists.** Raspberry Pi answered the question directly and said no. | High | S1, S2, S4 |
| 4 | Does Raspberry Pi document a hardware way to disable the radio? | **Not for the Zero 2 W.** The raspberrypi.com documentation does not mention `disable-wifi` or `disable-bt` at all. The overlay README documents them, and says only "Disable onboard WLAN". **It makes no claim that the radio powers down.** The overlay source disables the SDIO host controller, so the driver never binds. The chip keeps its power. Raspberry Pi does document a real hardware disable, but only for the Compute Modules: a pin that "prevents Wi-Fi from powering up". The Zero 2 W exposes `WL_ON` and `BT_ON` only as **status** test pads. | High | S22, S23, S24, S25, S3, S13, S15 |
| 5 | Official boards with no wireless silicon at all? | Nine families. Only one fits 65 x 30 mm: **the original Pi Zero**. The Compute Modules with no wireless (CM4, CM5, CM0, CM4S, CM3+, CM1) all need a carrier board. CM4 and CM5 are 55 x 40 mm. CM0 is 39 x 33 mm. CM4S and CM3+ use a 67.6 x 31 mm SODIMM, and CM1 is 67.6 x 30 mm. Pico and Pico 2 fit the space but are microcontrollers and cannot run Bitcoin Core. See the table in section 5. | High | S13 to S19, S21, S29 to S32, S35 to S37 |
| 6 | Community practice of physically removing the Zero 2 W radio? | **NON-PRIMARY.** Yes, and SeedSigner links to it. One guide is the only technical source. It removes an inductor and leaves the chip fitted and powered. No RF measurement proves the radio is silent. Treat it as risk reduction and not as proof. | Medium on existence. Low on effectiveness. | NP1 to NP5 |

## Q1: Zero-form-factor boards and their radios

| Board | Wireless chip fitted? | Which chip | Non-wireless variant of this exact model? |
|-------|----------------------|------------|-------------------------------------------|
| Raspberry Pi Zero (v1.2, v1.3) | **No** | none | The board itself is the no-wireless board |
| Raspberry Pi Zero W | Yes | Cypress CYW43438 | No |
| Raspberry Pi Zero WH | Yes | Cypress CYW43438 (same board plus a fitted header) | No |
| Raspberry Pi Zero 2 W | Yes | Synaptics SYN43436SXKUBG, then SYN43436PXKUBG | No |
| Raspberry Pi Zero 2 (no W) | **This board does not exist** | not applicable | not applicable |
| Any Zero-class board after 2021 | none released | not applicable | not applicable |

**The original Pi Zero.** The product page lists the full specification. It
names no wireless LAN and no Bluetooth. It says "Raspberry Pi Zero will remain
in production until at least January 2030" (S7). The products page still lists
it for sale (S10). The official model comparison in the documentation gives the
Pi Zero wireless value as "none" (S9). The official mechanical drawing, sheet
reference RPI-ZERO-V1_2, gives 65 mm across, 30 mm high, "4x M2.5 MOUNTING
HOLES", and hole spacing of 58 mm and 23 mm (S8). Those figures match the
Zero 2 W figures in S1 exactly. So a board that fits the enclosure fits both.

**The camera connector.** The Pi Zero product page lists "CSI camera connector
(v1.3 only)" (S7). Corky must buy v1.3. Version 1.2 has no camera connector.

**The processor.** The official processors page says the BCM2835 is used in
"the Raspberry Pi Zero, the Raspberry Pi Zero W" and is a "single-core
ARM1176JZF-S processor", instruction set ARMv6 (S20). The Zero 2 W uses the
RP3A0, a quad-core Cortex-A53, ARMv8, 64-bit (S20). This is a large step down
in capability. Corky must judge whether Bitcoin Core runs on ARMv6 with 512 MB.

**No Zero 2 without the W.** The official model comparison lists these
Zero-family entries and no others: "Raspberry Pi Zero", "Raspberry Pi Zero W",
"Raspberry Pi Zero WH", "Raspberry Pi Zero 2 W", "Raspberry Pi Zero 2 W with
headers" (S9). No entry named "Raspberry Pi Zero 2" appears.

**No Zero 3.** The raspberrypi.com products page lists Raspberry Pi Zero,
Zero W and Zero 2 W, and no later Zero-class board (S10).

**The new Zero-class part is a module, not a board.** Raspberry Pi now sells
Compute Module Zero. It uses the same RP3A0 as the Zero 2 W. It has genuine
no-wireless variants. It measures 39 mm x 33 mm x 2.8 mm and solders onto a
carrier board (S13). It does not fit the SeedSigner enclosure.

## Q2: the Zero 2 W package and its radio

**The processor package.** The product brief says: "At its heart is a Raspberry
Pi RP3A0 system-in-package (SiP), integrating a Broadcom BCM2710A1 die with
512MB of LPDDR2 SDRAM" (S1).

**What sits inside the package.** The Raspberry Pi news post lists the contents:
"the BCM2710A1 die used in BCM2837A1, a 4Gbit Micron LPDDR2 die, and the
decoupling capacitors required to smooth the core supply voltage" (S4). The
list names no radio. So the radio sits outside the RP3A0.

**The radio part number.** Raspberry Pi Product Change Notice 38 names it. The
title is "Change of wireless device from 43436S to 43436P". The change
description says: "The wireless device that provides Wi-Fi and Bluetooth is
changing from SYN43436SXKUBG to SYN43436PXKUBG" (S11). Products affected:
"Raspberry Pi Zero 2 W". Transition date: 1 November 2025. The SYN prefix is
Synaptics.

**This is the decisive point for Corky.** Raspberry Pi changed the radio part
without changing the processor. The PCN says "Mechanical (Form, Fit, Function)
Changes: None" and "Electrical: None" (S11). A part that Raspberry Pi swaps on
its own is a separate component. Removing it does not kill the processor.

**Corroboration.** The Zero 2 W test pad drawing lists two pads: "BT_ON
Bluetooth power status" and "WL_ON Wireless LAN power status" (S3). A radio
inside the SiP would not need board-level power-status pads. The Compute Module
Zero uses the same RP3A0 and carries its radio as a separate named chip, the
"Cypress CYW43439" (S13). The Raspberry Pi kernel device tree for the Zero 2 W
declares the Bluetooth part on `uart0` with `compatible = "brcm,bcm43438-bt"`
and a `shutdown-gpios` line, and puts Wi-Fi on a separate SDIO controller
(S26, S27, RPi repo).

**Warning: the Zero 2 W has shipped with more than one radio part.** The
Raspberry Pi firmware package holds four different Wi-Fi firmware files keyed to
`raspberrypi,model-zero-2-w`: `brcmfmac43430-sdio`, `brcmfmac43430b0-sdio`,
`brcmfmac43436-sdio` and `brcmfmac43436s-sdio` (S28, RPi repo). The Zero W has
only one, `brcmfmac43430-sdio`. PCN 38 also says: "There is no physical
difference between the two variants" (S11). So Corky cannot assume one radio
part, and cannot identify the part by looking at the board.

## Q3: RAM

The product brief specification says "Memory: 512MB LPDDR2" (S1). The product
page says "512MB SDRAM" (S2). Raspberry Pi answered the larger-RAM question in
the launch post. The question was "Will there be a version of Zero 2 W with 1GB
of SDRAM?". The answer was: "No. 1GB LPDDR2 monodie are not available, and
producing a SiP with two stacked SDRAM dice would be very challenging" (S4).

Raspberry Pi sells two Zero 2 W items: "Raspberry Pi Zero 2 W" and "Raspberry Pi
Zero 2 W with headers" (S2). Both carry 512 MB.

## Q4: what the overlays actually do

**The raspberrypi.com documentation does not document them.** This document
checked `configuration.html` and `config_txt.html`. Neither page mentions
`disable-wifi`, `disable-bt` or `rfkill` (S22).

**The overlay README documents them.** The README ships in the Raspberry Pi
firmware repository (S23, RPi repo). The entries read:

```
Name:   disable-wifi
Info:   Disable onboard WLAN on WiFi-capable Raspberry Pis.
Load:   dtoverlay=disable-wifi
Params: <None>
```

```
Name:   disable-bt
Info:   Disable onboard Bluetooth on Bluetooth-capable Raspberry Pis. On Pis
        prior to Pi 5 this restores UART0/ttyAMA0 over GPIOs 14 & 15.
Load:   dtoverlay=disable-bt
Params: <None>
```

**The documentation makes no power-down claim.** It says "Disable onboard WLAN".
It does not say the radio powers down. It does not say the radio stops
transmitting. The README opening explains the mechanism: "Device Tree makes it
possible to support many hardware configurations with a single kernel and
without the need to explicitly load or blacklist kernel modules" (S23).

**The overlay source confirms the mechanism.** `disable-wifi-overlay.dts` sets
the `mmc` node and the `mmcnr` node to `status = "disabled"` (S24, RPi repo).
That switches off the SDIO host controller. The Wi-Fi driver then never probes
the radio. `disable-bt-overlay.dts` sets the `uart1` node and the `bt` node to
`status = "disabled"` (S25, RPi repo). Neither overlay cuts power to the radio.
Neither overlay drives a hardware line. Software wrote the setting, and software
can undo it.

**Raspberry Pi does document a real hardware disable, but not for the Zero 2 W.**
The Compute Module Zero datasheet documents the `WiFi_ON` pin: "When driven or
tied low (logic 0), the pin prevents Wi-Fi from powering up, helping to reduce
power consumption or meet requirements to physically disable Wi-Fi" (S13). The
`BT_ON` pin carries the same wording for Bluetooth. The CM4 datasheet documents
the same idea: "When driven or tied low it prevents the wireless network module
from powering up" (S15). The CM4 also has a `WL_nDisable` pin: "Can be left
floating; if driven low the wireless interface will be disabled" (S15).

**The Zero 2 W has no such documented pin.** The Zero 2 W test pad drawing gives
`WL_ON` as "Wireless LAN power status" and `BT_ON` as "Bluetooth power status"
(S3). Raspberry Pi calls them status pads. Raspberry Pi does not document them
as control inputs for the Zero 2 W. Whether pulling the Zero 2 W `WL_ON` pad low
disables the radio is **unverified**.

## Q5: official boards and modules with no wireless silicon

| Product | Wireless variant with none fitted | Size | Needs a carrier? | Fits 65 x 30 mm? |
|---------|----------------------------------|------|------------------|------------------|
| Raspberry Pi Zero (v1.2, v1.3) | The whole product has no radio | 65 mm x 30 mm | No | **Yes, and it is the only one** |
| Raspberry Pi 1 Model B+ | No radio | 85 mm x 56 mm | No | No |
| Raspberry Pi 1 Model A+ | No radio | 65 mm long. Raspberry Pi never published the width. **Unverified** | No | No |
| Raspberry Pi 1 Model A, Model B | No radio | Raspberry Pi published no mechanical drawing. **Unverified** | No | No |
| Raspberry Pi 2 Model B | No radio | 85 mm x 56 mm, from "identical form-factor to ... Model B+" | No | No |
| Compute Module Zero (CM0) | Yes. `CM0000000`, `CM0000008`, `CM0000016` | 39 mm x 33 mm x 2.8 mm | Yes, it solders on | No. 33 mm is 3 mm too wide |
| Compute Module 4 (CM4) | Yes. `CM400xxxx` is no wireless; `CM410xxxx` is wireless | 55 mm x 40 mm x 4.7 mm | Yes, two 100-pin connectors | No |
| Compute Module 5 (CM5) | Yes. `CM500xxxx` is no wireless | 55 mm x 40 mm x 4.7 mm | Yes, two 100-pin connectors | No |
| Compute Module 4S (CM4S) | No radio at all | 67.6 mm x 31.0 mm, DDR2 SODIMM | Yes, a SODIMM socket | No |
| Compute Module 3, 3 Lite, 3+ | No radio at all | 67.6 mm x 31 mm | Yes, a SODIMM socket | No |
| Compute Module 1 (CM1) | No radio at all | 67.6 mm x 30 mm | Yes, a SODIMM socket | No |
| Raspberry Pi Pico, Pico 2 | No radio at all. These are microcontrollers | 51 mm x 21 mm x 1 mm | No | Yes, but they cannot run Bitcoin Core |
| Raspberry Pi Keyboard and Hub | No radio. It is a wired USB device | 284.80 mm x 121.61 mm x 20.34 mm | No | No |

Raspberry Pi confirms the wireless status of each family in the documentation
comparison tables. CM1, CM3, CM3+ and CM4S all read "none". CM4 and CM5 read
"optional". Pico and Pico 2 read "none". Pico W and Pico 2 W carry an Infineon
CYW43439 (S9, S21, S31).

**The Pico family cannot help Corky.** Pico and Pico 2 fit the space and carry
no radio. They are microcontrollers built on RP2040 and RP2350. They run no
Linux and no Bitcoin Core. They are listed here for completeness only.

**Only the original Pi Zero fits.** Every Compute Module needs a carrier board
that adds its own area. The smallest no-radio Linux module is CM0 at
39 mm x 33 mm. Its width alone exceeds the 30 mm slot.

**On the CM4, which the question asked about.** The datasheet says: "Small
Footprint 55 mm x 40 mm x 4.7 mm module" and "The CM4 is a compact 40mm x 55mm
module" (S15). The electrical interface is "two 100-pin high density connectors"
(S15). So the CM4 needs a carrier board and cannot fit the SeedSigner enclosure.
The product brief pricing table lists every part number. Rows starting `CM400`
show Wireless blank or "No". Rows starting `CM410` show Wireless "Yes" (S16).
The CM4 radio is a separate module: "The CM4 can be supplied with an on-board
wireless module based on the Cypress CYW43455" (S15). On modules without it,
"On CM4 modules without wireless, this pin is reserved" (S15).

**CM4S is not for general sale.** The datasheet says it "is intended for
specific industrial customers migrating from CM3 or Compute Module 3+ and is not
for general sale" (S18). Its product brief gives "Form factor 67.6mm × 31.0mm"
and marks the whole part-number range Wireless "No" (S30).

**The SODIMM modules differ by 1 mm.** The CM1 and CM3 datasheet says the
modules conform to JEDEC MO-224, "with the exception that the CM3, CM3L modules
are 31mm in height rather than 30mm of CM1" (S29). So CM1 is 67.6 x 30 mm and
CM3, CM3L and CM3+ are 67.6 x 31 mm. All three still need a SODIMM socket.

**CM5 uses the same radio as CM4.** The CM5 datasheet says "The wireless
interfaces on CM5 are provided by the Cypress CYW43455 silicon", and "CM5
connects to carrier boards through its two 100-pin connectors" (S17).

## Q6: NON-PRIMARY. Community practice of removing the radio

**Everything in this section is NON-PRIMARY. Raspberry Pi does not publish any
of it. Do not read it as official guidance.**

**SeedSigner recommends the Pi Zero 1.3 because it has no radio.** The
SeedSigner hardware page says: "For the highest assurance your signer is
operating in network isolation, the Raspberry Pi v1.3 has no WiFi or Bluetooth
capability" (NP1). Credibility: high for the project's own position, because the
project maintains the page.

**SeedSigner links to one removal guide.** The same page says: "Note: The
Raspberry Pi Zero W can be easily modified to permanently disable its wireless
communication capability" and links to the guide (NP1). The SeedSigner README
repeats the link and adds an operating note for users who have already done it
(NP2).

**The guide is the only technical source.** The repository is
`DesobedienteTecnologico/rpi_disable_wifi_and_bt_by_hardware` (NP3). It covers
the Zero 2 W by name: "RPi Zero w and RPi Zero 2 W wireless chip still in the
same position". Credibility: medium. It is a hobbyist tutorial with 53 GitHub
stars, last changed in May 2023. It is not a security audit. No security
researcher and no vendor has verified it. Every other source traces back to it.

**The guide does not remove the chip.** It removes one inductor. The guide says:
"VDD and GND still connected into the board but chip is not able to work without
the inductor" (NP3). The chip stays fitted and stays powered. The stated test is
`ip addr` showing no `wlan0`. That test proves the driver made no interface. It
does not prove the radio cannot transmit. **No RF measurement supports the
claim. This is unverified.**

**The Zero 2 W needs an extra step.** The guide says the radio sits under a metal
shield, and lists a heat gun, a hair dryer, a Dremel or sandpaper to get past it
(NP3). This step risks the board.

**An independent teardown names a different part.** Jeff Geerling X-rayed a
Zero 2 W and wrote that "the actual chip used here is the SYN43436, made by
Synaptics" (NP4). Credibility: medium-high for hardware writing, and it agrees
with Raspberry Pi's own PCN 38 (S11). The guide, however, worked from the
CYW43438 datasheet. **Nobody has published an X-ray of a Zero 2 W confirming the
inductor the guide names. Treat the guide's Zero 2 W pinout claim as
unverified.**

**Other signer projects avoid the problem instead.** SeedHammer specifies the
"Raspberry Pi Zero (version 1.3)" (NP5). Blockstream Jade ships firmware with no
Bluetooth driver. Foundation Passport states it has "no wireless functionality of
any kind". The pattern across the field is to pick a board with no radio, or to
ship firmware with no radio driver.

## Sources

Sections 1 to 5 use these. Each entry gives the URL and the line this document
relies on.

- **S1** Raspberry Pi Zero 2 W product brief, published April 2024.
  <https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-product-brief.pdf>
  (redirects to `https://pip-assets.raspberrypi.com/categories/584-raspberry-pi-zero-2-w/documents/RP-008359-DS-1-raspberry-pi-zero-2-w-product-brief.pdf`)
  > "At its heart is a Raspberry Pi RP3A0 system-in-package (SiP), integrating a Broadcom BCM2710A1 die with 512MB of LPDDR2 SDRAM."
  > "Form factor: 65mm × 30mm"
  > "Memory: 512MB LPDDR2"
  > "Connectivity: • 2.4GHz IEEE 802.11b/g/n wireless LAN, Bluetooth 4.2, BLE, onboard antenna"
  > "Sharing the same form factor as the original Raspberry Pi Zero, Raspberry Pi Zero 2 W fits inside most existing Raspberry Pi Zero cases."

- **S2** Raspberry Pi Zero 2 W product page.
  <https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/>
  > "512MB SDRAM"
  > "2.4GHz 802.11 b/g/n wireless LAN"
  > "Raspberry Pi Zero 2 W will remain in production until at least January 2030"

- **S3** Raspberry Pi Zero 2 W test pad locations.
  <https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-test-pads.pdf>
  > "BT_ON          Bluetooth power status"
  > "WL_ON          Wireless LAN power status"

- **S4** Raspberry Pi news blog, Zero 2 W launch post.
  <https://www.raspberrypi.com/news/new-raspberry-pi-zero-2-w-2/>
  > "the BCM2710A1 die used in BCM2837A1, a 4Gbit Micron LPDDR2 die, and the decoupling capacitors required to smooth the core supply voltage"
  > "No. 1GB LPDDR2 monodie are not available, and producing a SiP with two stacked SDRAM dice would be very challenging."

- **S5** Raspberry Pi news blog, Zero W launch post.
  <https://www.raspberrypi.com/news/raspberry-pi-zero-w-joins-family/>
  > "It uses the same Cypress CYW43438 wireless chip as Raspberry Pi 3 Model B to provide 802.11n wireless LAN and Bluetooth 4.0 connectivity."

- **S6** Raspberry Pi Zero W product page.
  <https://www.raspberrypi.com/products/raspberry-pi-zero-w/>
  > "802.11 b/g/n wireless LAN"
  > "Raspberry Pi Zero W will remain in production until at least January 2030"

- **S7** Raspberry Pi Zero product page.
  <https://www.raspberrypi.com/products/raspberry-pi-zero/>
  > "1GHz single-core CPU"
  > "512MB RAM"
  > "CSI camera connector (v1.3 only)"
  > "Raspberry Pi Zero will remain in production until at least January 2030"
  The specification list names no wireless LAN and no Bluetooth.

- **S8** Raspberry Pi Zero mechanical drawing, sheet reference RPI-ZERO-V1_2.
  <https://datasheets.raspberrypi.com/rpizero/raspberry-pi-zero-mechanical-drawing.pdf>
  The drawing gives "65" across and "30" high, with "4x M2.5 MOUNTING HOLES
  DRILLED TO 2.75 +/- 0.05mm", hole spacing "58" and "23", and "CORNER RADIUS =
  3.0mm". Read by rasterizing the PDF, because the drawing carries no text layer.

- **S9** Raspberry Pi computer hardware documentation, model comparison table.
  <https://www.raspberrypi.com/documentation/computers/raspberry-pi.html>
  Zero-family entries listed: "Raspberry Pi Zero", "Raspberry Pi Zero W",
  "Raspberry Pi Zero WH", "Raspberry Pi Zero 2 W", "Raspberry Pi Zero 2 W with
  headers". No entry named "Raspberry Pi Zero 2".
  > Raspberry Pi Zero wireless value: "none"
  > Raspberry Pi Zero 2 W: "2.4 GHz single-band 802.11n Wi-Fi (35 Mb/s) Bluetooth 4.2, Bluetooth Low Energy (BLE)"

- **S10** Raspberry Pi products page.
  <https://www.raspberrypi.com/products/>
  Lists "Raspberry Pi Zero 2 W", "Raspberry Pi Zero W" and "Raspberry Pi Zero".
  Lists no Zero 3. Lists Compute Module 5, 4, 4S, Zero, 3+ and 1.

- **S11** Product Change Notice 38, Raspberry Pi Zero 2 W.
  <https://pip-assets.raspberrypi.com/categories/1163-pcn/documents/RP-009258-PC-2-PCN38,%20Raspberry%20Pi%20Zero%202W%20Change%20to%20use%20the%2043436P%20wireless%20device.pdf>
  > "Title: Change of wireless device from 43436S to 43436P."
  > "Products Affected: Raspberry Pi Zero 2 W"
  > "The wireless device that provides Wi-Fi and Bluetooth is changing from SYN43436SXKUBG to SYN43436PXKUBG."
  > "Mechanical (Form, Fit, Function) Changes: None"
  > "Transition Date(s): 1 Nov 2025"
  > "There is no physical difference between the two variants."

- **S12** Product Information Portal, PCN category for Zero 2 W.
  <https://pip.raspberrypi.com/categories/1163-pcn>
  Lists two notices: "PCN21, Raspberry Pi Zero 2 W, Change of country of origin"
  and "PCN38, Raspberry Pi Zero 2W Change to use the 43436P wireless device".

- **S13** Compute Module Zero datasheet.
  <https://pip-assets.raspberrypi.com/categories/1286-raspberry-pi-compute-module-zero/documents/RP-009251-DS-3-cm0-datasheet.pdf>
  > "Compute Module Zero (CM0) is a System on Module (SoM) built around the RP3A0 chip, a custom-built system-in-package designed by Raspberry Pi."
  > "Compact module design. Small footprint of 39 mm × 33 mm × 2.8 mm."
  > "The CM0 module is designed to be soldered directly onto the carrier board."
  > "The wireless interfaces are provided by the Cypress CYW43439 chip"
  > "When driven or tied low (logic 0), the pin prevents Wi-Fi from powering up, helping to reduce power consumption or meet requirements to physically disable Wi-Fi."
  > "These pins are reserved on Compute Modules without wireless functionality."
  Variant table: "CM0000000 | - | 512 MB | Lite (0 GB)", "CM0000008", "CM0000016"
  all with wireless "-", and "CM0100000", "CM0100008", "CM0100016" with "Yes".
  Part number key: "CM0 | 0 = No, 1 = Yes | 00 = 512 MB | 000 = 0 GB (Lite)".

- **S14** Compute Module Zero product page.
  <https://www.raspberrypi.com/products/compute-module-zero/>
  Variants offered: "Compute Module Zero - No wireless, 0GB eMMC (Lite)",
  "Compute Module Zero - No wireless, 8GB eMMC", "Compute Module Zero - No
  wireless, 16GB eMMC", plus three wireless variants.

- **S15** Compute Module 4 datasheet.
  <https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf>
  > "Small Footprint 55 mm × 40 mm × 4.7 mm module"
  > "The CM4 is a compact 40mm × 55mm module."
  > "The electrical interface of the CM4 is via two 100-pin high density connectors"
  > "The CM4 can be supplied with an on-board wireless module based on the Cypress CYW43455"
  > "When driven or tied low it prevents the wireless network module from powering up."
  > "On CM4 modules without wireless, this pin is reserved."
  > "WL_nDisable   Can be left floating; if driven low the wireless interface will be disabled."

- **S16** Compute Module 4 product brief.
  <https://datasheets.raspberrypi.com/cm4/cm4-product-brief.pdf>
  > "Form factor   55 mm × 40 mm"
  > "Connectivity  Optional wireless LAN, 2.4GHz and 5.0GHz IEEE 802.11b/g/n/ac"
  Pricing table: part numbers `CM4001000` to `CM4008064` carry Wireless "No".
  Part numbers `CM4101000` to `CM4108064` carry Wireless "Yes".

- **S17** Compute Module 5 datasheet.
  <https://datasheets.raspberrypi.com/cm5/cm5-datasheet.pdf>
  > "Compact module design. Small footprint of 55 mm × 40 mm × 4.7 mm module with four M2.5 mounting holes."
  > "CM5 is a compact 40 mm × 55 mm module."
  Part number key: "CM5 | 0 = No, 1 = Yes". Variant rows `CM5002000`,
  `CM5004000` and similar carry wireless "-".

- **S18** Compute Module 4S datasheet.
  <https://datasheets.raspberrypi.com/cm4s/cm4s-datasheet.pdf>
  > "DDR2-SODIMM-mechanically-compatible form factor"
  > "The CM4S modules conform to JEDEC MO-224 mechanical specification for 200-pin DDR2 (1.8V) SODIMM modules"
  > "The Raspberry Pi Compute Module 4 SODIMM (CM4S) is intended for specific industrial customers migrating from CM3 or Compute Module 3+ and is not for general sale."
  The document never uses the word "wireless".

- **S19** Compute Module 3+ datasheet.
  <https://datasheets.raspberrypi.com/cm/cm3-plus-datasheet.pdf>
  > "The CM3+ modules conform to JEDEC MO-224 mechanical specification for 200 pin DDR2 (1.8 V) SODIMM modules"
  The mechanical drawing, Figure 2, gives "67.6" across and "31" high, with
  "2x M2 MOUNTING HOLES". Read by rasterizing the PDF. The block diagram,
  Figure 1, shows no wireless block.

- **S20** Raspberry Pi processors documentation.
  <https://www.raspberrypi.com/documentation/computers/processors.html>
  > BCM2835 is "used in the Raspberry Pi 1 Models A, A+, B, B+, the Raspberry Pi Zero, the Raspberry Pi Zero W, and the Raspberry Pi Compute Module 1"
  > "single-core ARM1176JZF-S processor"
  > RP3A0 is "used by the Raspberry Pi Zero 2 W", a "quad-core Arm Cortex A53 (Armv8) cluster"

- **S21** Raspberry Pi news blog, product series explained.
  <https://www.raspberrypi.com/news/raspberry-pi-product-series-explained/>
  The Zero series holds Zero, Zero W, Zero WH and Zero 2 W. The original Zero
  wireless value is "none". CM1, CM3, CM3+ and CM4S wireless value is "none".
  The CM4 offers optional wireless.

- **S22** Raspberry Pi configuration and config.txt documentation.
  <https://www.raspberrypi.com/documentation/computers/configuration.html>
  <https://www.raspberrypi.com/documentation/computers/config_txt.html>
  Neither page mentions `disable-wifi`, `disable-bt` or `rfkill`. `config_txt.html`
  describes the general option:
  > "The `dtoverlay` option requests the firmware to load a named Device Tree overlay – a configuration file that can enable kernel support for built-in and external hardware."

- **S23** **RPi repo.** Device tree overlay README, `raspberrypi/firmware`.
  <https://raw.githubusercontent.com/raspberrypi/firmware/master/boot/overlays/README>
  > "This directory contains Device Tree overlays. Device Tree makes it possible to support many hardware configurations with a single kernel and without the need to explicitly load or blacklist kernel modules."
  > "Name:   disable-wifi / Info:   Disable onboard WLAN on WiFi-capable Raspberry Pis. / Load:   dtoverlay=disable-wifi / Params: <None>"
  > "Name:   disable-bt / Info:   Disable onboard Bluetooth on Bluetooth-capable Raspberry Pis. On Pis prior to Pi 5 this restores UART0/ttyAMA0 over GPIOs 14 & 15."

- **S24** **RPi repo.** `disable-wifi-overlay.dts`, `raspberrypi/linux`.
  <https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.6.y/arch/arm/boot/dts/overlays/disable-wifi-overlay.dts>
  The whole overlay sets two nodes to disabled:
  > "target = <&mmc>; __overlay__ { status = "disabled"; };"
  > "target = <&mmcnr>; __overlay__ { status = "disabled"; };"

- **S25** **RPi repo.** `disable-bt-overlay.dts`, `raspberrypi/linux`.
  <https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.6.y/arch/arm/boot/dts/overlays/disable-bt-overlay.dts>
  > "/* Disable Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15. */"
  It sets `uart1` and the `bt` node to `status = "disabled"`.

- **S26** **RPi repo.** Zero 2 W device tree, `raspberrypi/linux`.
  <https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.6.y/arch/arm/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dts>
  > "compatible = "raspberrypi,model-zero-2-w", "brcm,bcm2837";"
  > "BT_ON", /* GPIO42 */"
  > "WIFI_CLK", /* GPIO43 */"
  Wi-Fi sits on `sdio_pins`, pins 34 to 39.

- **S27** **RPi repo.** `bcm2708-rpi-bt.dtsi`, `raspberrypi/linux`.
  <https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.6.y/arch/arm/boot/dts/broadcom/bcm2708-rpi-bt.dtsi>
  > "compatible = "brcm,bcm43438-bt";"
  > "shutdown-gpios = <&gpio 45 GPIO_ACTIVE_HIGH>;"

- **S28** **RPi repo.** Wi-Fi firmware files, `RPi-Distro/firmware-nonfree`,
  branch `trixie`, path `debian/added-firmware/brcm/`.
  Files keyed to the Zero 2 W:
  `brcmfmac43430-sdio.raspberrypi,model-zero-2-w.bin`,
  `brcmfmac43430b0-sdio.raspberrypi,model-zero-2-w.bin`,
  `brcmfmac43436-sdio.raspberrypi,model-zero-2-w.bin`,
  `brcmfmac43436s-sdio.raspberrypi,model-zero-2-w.bin`.
  Only one file is keyed to the Zero W:
  `brcmfmac43430-sdio.raspberrypi,model-zero-w.bin`.

- **S29** Compute Module 1 and Compute Module 3 datasheet.
  <https://pip-assets.raspberrypi.com/categories/617-raspberry-pi-compute-module-1/documents/RP-008161-DS-1-cm1-and-cm3-datasheet.pdf>
  > "The Compute Modules conform to JEDEC MO-224 mechanical specification for 200 pin DDR2 (1.8V) SODIMM modules (with the exception that the CM3, CM3L modules are 31mm in height rather than 30mm of CM1)"
  Figure 3 gives CM1 as 67.6 wide and 30 high. Figure 4 gives CM3 and CM3L as
  67.6 wide and 31 high. The only wireless mention refers to a different board:
  "on a Raspberry Pi 3 it is used to talk to the on-board BCM43438 WiFi device".

- **S30** Compute Module 4S product brief.
  <https://datasheets.raspberrypi.com/cm4s/cm4s-product-brief.pdf>
  > "Form factor    67.6mm × 31.0mm (compatible with JEDEC MO-224 mechanical specification for 200-pin DDR2)"
  The pricing table Wireless column reads "No" for every part number from
  `CM4S01000` to `CM4S08064`.

- **S31** Raspberry Pi Pico family datasheets.
  <https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf>
  <https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf>
  <https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf>
  <https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf>
  > Pico: "The Raspberry Pi Pico is a single sided 51×21 mm 1 mm thick PCB"
  > Pico 2: "The Raspberry Pi Pico 2 is a single sided 51×21 mm 1 mm thick PCB"
  > Pico W: "Pico W has an on-board 2.4 GHz wireless interface using an Infineon CYW43439."
  > Pico 2 W: "Pico 2 W has an on-board 2.4 GHz wireless interface using an Infineon CYW43439."
  The Pico and Pico 2 datasheets never use the words "wireless", "Bluetooth" or
  "Wi-Fi".

- **S32** Board mechanical drawings.
  <https://datasheets.raspberrypi.com/rpi/raspberry-pi-b-plus-mechanical-drawing.pdf>
  Model B+ is dimensioned 85 x 56.
  <https://datasheets.raspberrypi.com/rpi3/raspberry-pi-3-a-plus-mechanical-drawing.pdf>
  Pi 3 Model A+ is dimensioned 65 x 56.
  <https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf>
  and <https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf>
  Both are dimensioned 85 x 56.

- **S33** Raspberry Pi news blog, Model A+ launch.
  <https://www.raspberrypi.com/news/raspberry-pi-model-a-plus-on-sale/>
  > "65mm in length, versus 86mm for the Model A"

- **S34** Raspberry Pi news blog, Pi 2 launch.
  <https://www.raspberrypi.com/news/raspberry-pi-2-on-sale/>
  > "This has an identical form-factor to the existing Raspberry Pi 1 Model B+"

- **S35** Compute Module hardware documentation.
  <https://www.raspberrypi.com/documentation/computers/compute-module.html>
  > "A Raspberry Pi Compute Module IO Board (CMIO) provides the physical connectors, peripheral interfaces, and expansion options necessary for accessing and expanding a Compute Module's functionality."
  > "A Compute Module IO Board can be used as a standalone product, allowing for rapid prototyping and embedded systems development, or as a reference design for your own carrier (IO) board."

- **S36** Compute Module Zero product brief.
  <https://pip-assets.raspberrypi.com/categories/1286-raspberry-pi-compute-module-zero/documents/RP-009404-MM-1-Compute%20Module%20Zero%20product%20brief.pdf>
  > "Dimensions    39 mm × 33 mm × 2.8 mm"
  > "The Compute Module Zero board is designed to be soldered directly onto a carrier board."

- **S37** Raspberry Pi Keyboard and Hub product brief.
  <https://pip-assets.raspberrypi.com/categories/662-raspberry-pi-keyboard-and-hub/documents/RP-008211-DS-1-keyboard-mouse-product-brief.pdf>
  > "USB type A to micro USB type B cable included for connection to compatible computer"
  > "Dimensions: 284.80mm 121.61mm × 20.34mm"
  No wireless appears in the specification.

### NON-PRIMARY sources, section 6 only

- **NP1** SeedSigner hardware page. <https://seedsigner.com/hardware/>
  > "For the highest assurance your signer is operating in network isolation, the Raspberry Pi v1.3 has no WiFi or Bluetooth capability."
  Credibility: high, for the project's own position.

- **NP2** SeedSigner README, dev branch.
  <https://github.com/SeedSigner/seedsigner/blob/dev/README.md>
  > "Preferably version 1.3 which has no WiFi/Bluetooth capability"
  Credibility: high, for the project's own position.

- **NP3** DesobedienteTecnologico removal guide.
  <https://github.com/DesobedienteTecnologico/rpi_disable_wifi_and_bt_by_hardware>
  > "RPi Zero w and RPi Zero 2 W wireless chip still in the same position"
  > "VDD and GND still connected into the board but chip is not able to work without the inductor."
  Credibility: medium. Hobbyist tutorial, 53 stars, last changed May 2023, no
  independent verification.

- **NP4** Jeff Geerling, Zero 2 W X-ray teardown, October 2021.
  <https://www.jeffgeerling.com/blog/2021/look-inside-raspberry-pi-zero-2-w-and-rp3a0-au/>
  > "the actual chip used here is the SYN43436, made by Synaptics"
  Credibility: medium-high. It agrees with S11.

- **NP5** SeedHammer Controller. <https://seedhammer.com/article/the-seedhammer-controller>
  Specifies "Raspberry Pi Zero (version 1.3)".
  Credibility: high, for the project's own position.

## Not found

This document could not establish these from a Raspberry Pi primary source.

1. **The Pi Zero W and Zero WH radio part number beyond the news blog.** S5 names
   the Cypress CYW43438. No datasheet or product brief repeats it. The Zero WH
   has no product page of its own.
2. **The exact radio part on Zero 2 W units built before 1 November 2025 other
   than the 43436S.** S28 shows firmware for `43430`, `43430b0`, `43436` and
   `43436s`. Only PCN 38 names a part, and it names only 43436S and 43436P. So
   the earliest Zero 2 W boards may carry a different radio. **Unverified.**
3. **Whether pulling the Zero 2 W `WL_ON` or `BT_ON` test pad low disables the
   radio.** Raspberry Pi documents these as status pads for the Zero 2 W (S3).
   Raspberry Pi documents the control behaviour only for CM0, CM4 and CM5.
   **Unverified for the Zero 2 W.**
4. **The Zero 2 W FCC test reports.** The Product Information Portal holds
   `rpi_TEST_REPORT_PiZero2_WLAN_2.4GHz_FCC&IC` and three others, but they need
   a sign-in. This document could not read them.
5. **A raspberrypi.com sentence pointing readers to the overlay README.** Search
   results quoted one, but two direct reads of `config_txt.html` did not find it.
   **Unverified.**
6. **The width of the Raspberry Pi 1 Model A+.** The launch post gives only
   "65mm in length" (S33). Raspberry Pi published no mechanical drawing for it.
   **Unverified.** The 65 x 56 mm drawing that exists covers the Pi 3 Model A+,
   which is a different board.
7. **Dimensions for the Raspberry Pi 1 Model A and the original Model B.**
   Raspberry Pi published no mechanical drawing for either. Their wireless value
   is "none" (S9). **Dimensions unverified.**
8. **A Raspberry Pi 2 Model B mechanical drawing.** None exists on the portal.
   The 85 x 56 mm figure comes from the launch post wording plus the Model B+
   drawing (S32, S34). **Derived, not quoted.**
9. **A separate mechanical drawing for Pi Zero v1.3.** The only Zero drawing
   carries the reference RPI-ZERO-V1_2 (S8). The product page treats v1.2 and
   v1.3 as one product and separates them only by "CSI camera connector (v1.3
   only)" (S7). That the v1.3 outline matches is **unverified**.
10. **A Raspberry Pi sentence saying the CM4 requires a carrier board.** The CM4
    datasheet only names the two 100-pin connectors and the mating part numbers
    (S15). CM5 and CM0 have explicit carrier sentences (S17, S36). CM4 does not.
11. **A stated wireless-digit rule for CM4 part numbers.** CM5 and CM0 publish an
    explicit "0 = No, 1 = Yes" table (S17, S13). The CM4 documents do not. This
    document inferred the CM4 rule from its pricing table (S16).
12. **Whether Compute Module Zero sells outside China.** The product page shows a
    "Rest of the world" region selector and a buy control (S14). This document
    found no Raspberry Pi news post announcing it. **Unverified.**
13. **Any RF measurement proving a modified Zero 2 W cannot transmit.** None
    found, primary or otherwise.
