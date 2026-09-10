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
