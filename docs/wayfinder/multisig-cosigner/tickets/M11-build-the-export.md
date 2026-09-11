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
