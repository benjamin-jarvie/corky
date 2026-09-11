# M8 Does Corky write the Coldcard JSON as well as the one-liner?

Type: `wayfinder:grilling`, HITL. **Blocked by M7 (closed).**

## Question

M7 established that a bare key expression on one line is the format with
the widest support: Coldcard writes it, Sparrow reads it as Specter DIY
or Krux, Nunchuk reads it. It is 138 characters minus the `/0/*` suffix
Coldcard omits.

It also established that Coldcard's generic JSON is the only shape four
Sparrow importer classes and Nunchuk's JSON path both name by that name.
A user importing from Corky would pick "Coldcard Multisig" in Sparrow's
list rather than "Specter DIY", which is a smaller lie about what the
device is than it sounds, and a lie nonetheless.

So: **one file or two?**

- **One line only.** Smallest writer, no JSON to keep in step with
  anybody's parser, and the user picks Specter DIY or Krux in Sparrow.
  The name in that list is wrong, and the import works.
- **Both.** The JSON is what a person expects to see, and it names all
  the paths at once rather than the one exported. Costs a second writer
  and the SLIP-132 trap M7 documented: Sparrow checks the top-level
  `xpub`+`path` branch first and rejects a plain `tpub` for a P2WSH
  wallet, so the nested `bip48_2` form is required.
- **JSON only.** Matches what coordinators expect and drops the
  one-liner. Loses Nunchuk's simplest path and the BSMS line-3 case.

Worth deciding alongside: whether the file names itself after the
fingerprint the way `write_watch_only` does (`corky-<xfp>-watch.dat`),
so two of them on one stick can be told apart.

## Measured, 2026-09-10, against Sparrow 2.5.4's own importers

`tests/sparrow/test_cosigner_formats.py`, 13 checks, calling the
importer a person picks from Sparrow's list through
`getKeystoreMultisig`. Rule 8, applied to a question M7 answered by
reading source.

| format | importers that take it |
|---|---|
| **one-liner** `[xfp/48h/1h/0h/2h]tpub…` | Krux, SeedSigner |
| **flat JSON** `{chain, xfp, account, p2wsh_deriv, p2wsh}` | ColdcardMultisig, PassportMultisig, KeystoneMultisig, JadeMultisig |
| nested `bip48_2` JSON | **none** |

Every accepted import lands at `m/48'/1'/0'/2'`, the path asked for.

### Three corrections to M7

1. **`SpecterDIYMultisig` has no keystore importer at all.** M7 said a
   person picks "Specter DIY" for the one-liner. They cannot. The names
   that work are **Krux** and **SeedSigner**.
2. **The nested `bip48_2` form does not work**, with a plain `tpub` or
   with a SLIP-132 `Vpub`. Every JSON importer refuses it with "Correct
   derivation not found for script type". M7 named this as the form that
   works. The one that works is the FLAT `p2wsh_deriv` + `p2wsh` pair.
3. **No SLIP-132 prefix is needed.** M7's gotcha said Sparrow enforces
   the prefix against the script type, so a plain `tpub` would be
   rejected and a `Vpub` required. A plain `tpub` in the flat form is
   accepted by all four. This matters more than it looks: producing a
   `Vpub` means swapping version bytes and recomputing a base58check
   double-SHA256, which is a crypto primitive PLAN A-22 forbids inside
   `corky/` and which Core will not do for us. **That objection is
   gone**, so the JSON is a plain formatting job.

### What the decision now costs

The JSON is five fields and one nesting level, built from the record
`cosigner_key` already returns. No new dependency, no key handling, no
re-encoding.

Whichever way this goes, **the person picks another vendor's name from
the list**. Corky is not a Krux, a SeedSigner or a Coldcard. There is no
generic "descriptor" cosigner importer: `Descriptor` is a whole-wallet
importer and exposes no keystore method.

## The QR half, measured 2026-09-10

Ben, 2026-09-10: "one is a QR and the other a microSD or USB export,
yes? So we should ask how they want to export and then tell them what to
import as and give them that file."

The channels DO want different things. Not the split above.

**The scan path does not use those importers at all.** Only `Bip93`
implements `KeystoreCodexImport`; everything else arrives through
`QRScanDialog`, whose `Result` carries an `ExtendedKey` or an
`OutputDescriptor`. `tests/sparrow/SparrowScan.java` drives those two
drongo parsers.

| QR payload | what Sparrow gets |
|---|---|
| `[xfp/48h/1h/0h/2h]tpub…` (what Corky writes) | **REFUSED** |
| the same with `/0/*` | **REFUSED** |
| a bare `tpub` | a key with **no origin**: no fingerprint, no path |
| `wsh([xfp/48h/1h/0h/2h]tpub)` | fingerprint, path and key, all correct |
| the flat JSON | REFUSED |

**So the QR must carry a descriptor, and today's record is not one.** A
bare key expression is not a complete descriptor, and the bare `tpub`
that does parse throws away the origin, which is the whole point of a
cosigner record. Any script function works, `wsh()` included, with or
without a range.

This is a correction to M2, which decided the cosigner key leaves "by QR
and by file" without asking what the QR must hold.

## The file half, corrected again

An importer that PARSES a format is not the same as a menu entry a
person can hand a file to. Three entries are scan-only:

| Corky writes | menu entries that accept it AS A FILE |
|---|---|
| the one-liner | Specter DIY, Krux |
| the flat JSON | Coldcard Multisig, Passport Multisig, Keystone Multisig, Cobo Vault, BlueWallet Vault |

Scan-only, so no file at all: **SeedSigner**, **Jade Multisig**,
**Keycard Shell Multisig**.

**And M7 was right about Specter DIY after all.** The earlier correction
in this ticket was wrong: it tested `SpecterDIYMultisig`, which has no
keystore importer, where the menu entry is plain `SpecterDIY`, which
does take the one-liner. `Krux` and `SeedSigner` both extend it, so the
one-liner IS the Specter DIY format. `JadeMultisig` extends
`ColdcardMultisig`, so the JSON is the Coldcard format. Two families,
not six.

## Still not known

Whether Sparrow asks for a device type BEFORE offering the scan button.
The decoding is generic, and `isKeystoreImportScannable()` is per
importer, so the list is probably still shown. That is a UI question
this cannot drive without a camera, and it belongs with the board work.

## Answer, 2026-09-10. Ben's call. One format, one name, both channels.

**Export asks ONE question: QR or file.** Each answer has exactly one
payload and one name to tell the person. No second question, no second
file, and no mention of Coldcard.

| channel | what Corky shows or writes | what the screen says to choose |
|---|---|---|
| QR | `wsh([xfp/48h/1h/0h/2h]tpub)` | Specter DIY |
| file | `[xfp/48h/1h/0h/2h]tpub` on one line | Specter DIY |

**Why Specter DIY and not Krux or SeedSigner.** Ben, 2026-09-10: "if
there's only two, why would we choose something that extends it". Krux
and SeedSigner are both subclasses of `SpecterDIY` in Sparrow, so the
one-liner IS the Specter DIY format and the other two are that format
under other names. Corky names the one they all extend. A person using
Krux picks Krux and it still works, because it is the same parser.

**Why the JSON is not written.** It would reach Passport, Keystone, Cobo
Vault and BlueWallet as well, and its natural name on screen is
Coldcard, which Ben ruled out. It also costs a second writer and a
second file for a person to choose between, which is the question this
answer removes.

**The QR and the file carry DIFFERENT text, and that is not a mistake.**
A bare key expression is not a complete descriptor, so the scan path
refuses it. The file importer wants exactly that bare expression and
refuses the wrapper. One question to the person, two payloads behind it,
and the person never sees the difference.

### What this leaves for the build

- `signer.cosigner_key` already returns the file form. The QR form is
  that string inside `wsh(...)`.
- The export flow itself is still unbuilt: M2 designed it, nothing in
  `main.py` calls `cosigner_key` yet.
- The screen must name Specter DIY on both paths, which is Ben's
  requirement: "the coordinator is going to ask what device type so we
  need to let them know which to choose too".

### The wording, settled the same day and without a camera

This ticket first deferred "does Sparrow show its device list before
offering the scan button" to the board. That was wrong. Scanning needs a
camera; the LAYOUT does not, and it is in the release already unpacked
in `tests/sparrow/.build`.

- `keystoreimport/hw_airgapped.fxml` is an **`Accordion`**.
- `HwAirgappedController` puts one `FileKeystoreImportPane` in it per
  `KeystoreFileImport`, so **the device list comes first** and the
  person expands the one they want.
- `FileImportPane` holds `scanButton` and `importButton`, labelled
  **"Scan..."** and **"Import File..."**, shown according to
  `isKeystoreImportScannable()` and `isFileFormatAvailable()`. Specter
  DIY has both true, which is why the test pins those two flags.

So the person picks the device FIRST and then chooses how to feed it,
and Corky's wording is the same shape on both paths:

    choose Specter DIY, then Scan...
    choose Specter DIY, then Import File...

Nothing here is left for the board.
