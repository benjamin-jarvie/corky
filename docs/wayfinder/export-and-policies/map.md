# Map: export, script policies, and what the panel lets you scroll

Label: `wayfinder:map`. Tickets are in `tickets/`, one file each.

## Destination

An export flow that asks which script policy first, hands each coordinator
a string that coordinator is **proven** to read, and says on the panel what
it is handing over. Plus one device-wide rule for scrolling, so a screen
with more below it always says so.

Reaching the end means: every screen in the export path is decided, the
policy list is settled against measured coordinator behaviour rather than
documentation, and someone can go and build it without another decision.

## Notes

- Domain: Corky, the Core-only air-gapped signer. `CONTEXT.md` at the repo
  root defines the vocabulary. Use Core's words, not invented ones.
- Ben's standing rule: **do not reinvent the wheel.** The UI follows
  SeedSigner's structure and Bitcoin Core's vocabulary. Where a screen has
  no counterpart in either, ask before inventing one.
- Ben's standing rule on execution: this repo carries execution IN the map,
  as the M1 and e2e maps did. Decisions and the code that follows both land
  here.
- Skills every session should consult: `/grilling` and `/domain-modeling`
  for the decision tickets, `/mp-tdd` for anything built, `/mp-code-review`
  before the gate.
- `TESTING.md` rules 1 to 11 bind every test written here. Rule 8 matters
  most on this map: an interop claim tested with our own tools is not an
  interop claim. Where a coordinator is named, run the coordinator.
- The prior map, `docs/wayfinder/e2e-before-testers/`, holds tickets 19, 20
  and 21: desk research on BlueWallet, Green and Bull Bitcoin. It is
  research, not proof. This map's task tickets are the proof.

## Decisions so far

- [R1 What feeds the RNG on this board](tickets/R1-rng-inputs.md) — the SoC
  hardware RNG through the in-kernel `[hwrng]` thread, interrupt jitter, a
  firmware seed at boot, and Core's own cycle counter and process stats.
  NOT keystrokes, NOT the fan, NOT temperature, NOT RDRAND. One gap found:
  nothing in provisioning handles `/var/lib/systemd/random-seed`, which a
  read-only M3 image would freeze identical on every device.

- [T0 Let the device emit all four of Core's policies](tickets/T0-emit-all-four.md)
  — done. `signer.EXPORT_KINDS` carries all four, LEFT and RIGHT walk every
  policy a key HAS via `signer.available_kinds`, and the QR is captioned in
  the letterbox so four identical-looking codes can be told apart. Sparrow's
  own zxing reads all four captioned, on both panels, and Sparrow's library
  derives Core's addresses for all four including legacy and nested segwit
  (`tests/sparrow/test_export_interop.py`, 37 checks). T1, T2 and T3 are
  unblocked.

- [R2 How much entropy Corky actually has](tickets/R2-entropy-level.md) —
  a single number is not obtainable and anyone offering one is guessing.
  Measured instead: the hardware generator is clean (7.9998 bits/byte,
  chi-square 244 on df 255), boot entropy differs across reboots EVEN with
  the saved seed frozen to a constant, and three separate boots produced
  three different first keys. The evidence says "working and unverifiable
  in principle", not "low". Generation stays an option; cards and dice
  stay the default.
- [R3 Which script policies each coordinator accepts](tickets/R3-coordinator-policies.md)
  — read from each coordinator's own source. Sparrow, BlueWallet and Green
  take all four. Bull Bitcoin takes three and has no taproot anywhere in
  its source, which corrects the earlier desk research. Green refuses a
  UR-encoded descriptor and wants the plain string, which is what Corky
  sends.
- [D6 A restored key has fewer policies than the key it restores](tickets/D6-import-asymmetry.md)
  — closed by removing the asymmetry. `build_descriptors` builds all four;
  measured cost is 24kB per key and no change in resident memory.

- [R4 Is Core's RNG safe to have, and safe as the default](tickets/R4-rng-default.md)
  — "thin" was the wrong word: the kernel credits the SoC generator a full
  bit per bit, about 950,000 bits per second against a 256-bit
  requirement. The real caveat is concentration, fewer independent sources
  than a laptop, not scarcity. And the dice comparison rests on a path
  that does not exist: `sethdseed` is gone from Core v31.1 and A-22
  forbids the primitive, so dice cannot make a key here at all. The README
  claimed cards and dice were the default AND that dice entropy was out of
  scope. Corrected, and recorded as PLAN A-19b.

- [R5 Does the paper backup actually get the money back](tickets/R5-recovery.md)
  — yes, in Bitcoin Core and Sparrow, and nowhere else. Sparrow's own
  library rebuilds a spending wallet from the 111 characters for all four
  policies and signs spends the network accepts (21 checks). BlueWallet,
  Green and Bull Bitcoin all refuse a private key; they are coordinators
  here, not recovery targets.
- [R6 The M0 memory gate, run on the board](tickets/R6-m0-on-real-hardware.md)
  — **FAILS at 81MB against a 100MB requirement**, on an image still
  running SSH, NetworkManager and wpa_supplicant, which `harden.sh`
  removes. Roughly 30MB of that is dev-only, but an estimate is not a
  pass. The gate has to be re-run on a hardened flash, and that is the
  gate on a beta.

- [D1 Which policies Corky offers](tickets/D1-which-policies.md) — all
  four, in the order wpkh, tr, sh, pkh, and none hidden on a coordinator's
  account because Corky no longer knows which coordinator you use.
- [D2 What the export screens become](tickets/D2-export-sequence.md) —
  script type first, then the captioned QR, with EXPORT OPTIONS on it for
  the text form and Core's wallet file. Receiving addresses leaves the
  export path. Built.
- [D3 One scrolling rule](tickets/D3-scroll-rule.md) — one `scrollbar`
  helper on every screen with content past its edge; a fixed thumb that
  never arrives for the endless list. Built.
- [D4 What the descriptor screen calls itself](tickets/D4-what-to-call-it.md)
  — name the policy, and a footer saying it is your public key and where
  it sits, with no private key in it. Built.
- [D5 Does the boot microSD become a channel](tickets/D5-microsd-channel.md)
  — yes, and it is blocked on the OS running from RAM. **M3 moves from
  last to a prerequisite.**

## Not yet specified

- What the export screen sequence becomes once the policy list is settled.
  It cannot be drawn until the tasks below say which policies survive.
- Whether the descriptor should ever leave as anything but a plain string.
  Animated QR and UR were ruled out for the descriptor once; if a
  coordinator turns out to need a format we do not emit, that reopens.
- Whether the boot microSD becomes a named channel, and if so at which
  path. It touches PLAN A-23, so it is a decision, not a config change.
- What the M3 read-only image does about the saved random seed. R2 showed
  it is not load-bearing, so this is hygiene rather than a hazard: a
  constant file shipped on every device, contributing nothing. Remove it
  in provisioning when M3's shape is decided.
- Whether the change branch should ever be shown. Receiving addresses is
  receive-only on purpose, and that stands, but D1 may make the policy
  list long enough that the reason wants restating on the panel.

- What the M3 image does about the saved random seed (R2 says it is
  hygiene, not a hazard).
- Whether Corky should ever show change addresses.

## Open, and they are the way out of this map

- [N1 The card comes out and the signer keeps running](tickets/N1-card-removable.md)
  — this is M3, and Ben's whole microSD workflow depends on it.
- [N2 Say when the card can safely come out](tickets/N2-safe-to-remove.md)
  — blocked by N1.
- [N3 Keys persist until the device is turned off](tickets/N3-keys-persist.md)
  — the behaviour was already right and there was no timer; the proof
  landed as `tests/test_key_persistence.py`.
- [T1](tickets/T1-sparrow-policies.md), [T2](tickets/T2-phone-policies.md),
  [T3](tickets/T3-core-watch-only.md) — Ben's hardware checks, now much
  smaller than they were: R3 settled the policy question from source, so
  what is left is whether each app's camera reads our QR and whether the
  address matches.

## Out of scope

- Multisig export. v1 is single-sig; PLAN freezes that.
- Changing how Corky signs. This map is about what leaves the device
  before a transaction exists, not about signing one.
