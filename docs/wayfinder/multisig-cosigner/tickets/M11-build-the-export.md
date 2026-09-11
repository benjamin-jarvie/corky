# M11 Build the cosigner export

Type: `wayfinder:task`, AFK. **Blocked by M2, M7, M8 (all closed).**

## Question

`signer.cosigner_key` exists and is proven against Sparrow. Nothing in
`main.py` calls it, so a person cannot get the record off the device.
M2 designed the flow, M7 picked the file format and M8 settled the
question and the wording. Nothing is left to decide.

Build it:

1. A row on the key menu that exports this key as a cosigner.
2. Named rows for the common paths at the top, and the typed path inside
   Advanced, which is M1 decision 3.
3. ONE question: QR or file (M8).
4. **QR** shows `wsh([xfp/path]tpub)`. **File** writes the bare
   one-liner. The two payloads differ and the person never sees that.
5. Both screens say to choose **Specter DIY** in the coordinator, which
   is Ben's requirement: the coordinator asks what device type, so Corky
   has to say which to pick.
6. The typed path echoes Core's 8-character descriptor checksum rather
   than a test address, which is M2: a cosigner branch derives a
   single-sig address and not the quorum's.

## Done when

The flow runs on the dev rig, `tests/sparrow/test_cosigner_formats.py`
still passes against what the device actually writes rather than against
a string a test built, and the screens are in `test_screen_fit.py`.

## The wording, already settled

M8 read Sparrow's own layout rather than deferring it. The airgapped
import is an `Accordion` with one pane per device, so the person picks
the device first, and each pane carries a **"Scan..."** and an **"Import
File..."** button. So both screens read the same shape:

    choose Specter DIY, then Scan...
    choose Specter DIY, then Import File...

Nothing in this ticket waits on hardware.

## Answer, 2026-09-10. Built, and two things were wrong before it ran.

`tests/sparrow/test_cosigner_formats.py`, 36 checks, now reading the
file **the device writes** rather than a string the test builds. Four
mutations, all detected.

### What shipped

- `signer.cosigner_path(rpc, script, account)` builds `48h/{coin}h/…`
  from the chain, so a regtest key never offers a mainnet path.
- `signer.write_cosigner` writes `corky-<xfp>-cosigner.txt`, one line,
  **no trailing newline**.
- `signer.cosigner_qr` returns
  `wsh(sortedmulti(1,<record>/0/*))#<checksum>`.
- `screens.script_menu` gains the **Cosigner (P2WSH)** row with the path
  beside it, and an **Advanced…** row. `screens.cosigner_options` asks
  QR or file, two rows and not the single-sig export's three, because
  M2 ruled out typing it.
- `main.Session._export_cosigner` runs the flow and both endings name
  the entry to pick: "choose Specter DIY, then Scan" and "…then Import
  File".

### The defect the device-written file exposed

**Sparrow refuses the file if it ends with a newline.** `\n`, `\r\n` and
two newlines all fail; a LEADING space is tolerated. This ticket first
wrote the record with a trailing newline, because M7 had read Nunchuk
allowing at most one and that seemed the safe side. Sparrow is the
stricter of the two, and the file must satisfy both.

Nothing would have caught this. The M8 suite passed for a day against a
string the test itself built without a newline. Pointing it at
`write_cosigner` turned three checks red immediately, and there are now
three checks that fail if anyone helpfully adds the newline back, which
is exactly the change a person makes to a text file that lacks one.

### The QR payload M8 recorded was one Core refuses

`wsh([xfp/path]tpub)` is not a descriptor: `getdescriptorinfo` answers
"A function is needed within P2WSH". Sparrow parses it anyway, which is
the trap. M8 is corrected above; the payload is the `sortedmulti(1,…)`
form that Core checksums and Sparrow reads.

### Not built, and deliberately

**Advanced** is a row that says so. It holds the nested-segwit path, the
account number and the typed path with its checksum echo, which is M1
decision 3 and M2's echo. That is its own slice and the named row is
what a person needs first.
