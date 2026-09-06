# Map: the audit that decides whether Corky ships a beta

Label: `wayfinder:map`. Tickets are in `tickets/`, one file each.

## Destination

**An evidenced go or no-go on a private beta.** Not a list of findings: a
decision, with every finding weighed as blocking or not blocking, and the
evidence for each written down where a tester can check it.

The map is done when someone can read one page and know whether to hand
this device to a person who is not Ben, and why.

## Notes

- Ben's call on scope, 2026-09-06: **everything, and the board is on.**
  Hardware items are in, not deferred to another map.
- Ben's call on cleanup: **delete what is superseded, git keeps it.** Two
  false claims reached him in one evening from stale documents, the `lab`
  branch and "cards and dice by default". A document nobody has checked
  is worse than no document.
- This repo carries execution IN the map, as every previous one has.
  Decisions and the code that follows both land here.
- Skills: `/mp-code-review` before the gate, `/mp-tdd` for anything built,
  `/mp-codebase-design` for anything restructured. `TESTING.md` rules 1 to
  11 bind every test. `CONTEXT.md` fixes the vocabulary.
- **Rule 5 is the house rule of this map.** Verify every finding against
  the source before acting on it. Five reviewer claims have failed
  verification in this project so far. A finding that has not been
  reproduced is a rumour.
- The board is `corky-zero`, and `corky-ip` in `~/.ssh/config` when mDNS
  is not resolving. Sync with the rsync in the previous map before
  touching it.

## Decisions so far

<!-- one line per closed ticket -->

- [A1 Read the four modules nothing has read](tickets/A1-unread-modules.md):
  three defects, two real bugs. A jammed button hung the device for ever; a
  PSBT file grown between the stat and the read beat the 4MB cap at 6MB;
  and the file channel's safety turned out to rest on a mount option in
  another file that neither mentioned. A devil's advocate then demolished
  three of my four first attempts, including a fix that fired phantom
  keypresses and a test that measured a high-water mark. Splash had no
  test and is the first thing the device runs.

- [A2 Does the layer model actually hold, end to end](tickets/A2-layer-model-holds.md):
  the model holds, the published account of it did not. Scanning a key
  photographed it onto a developer's disk; a mistyped WIF reached the panel
  and the journal unredacted; and the property that prevents both was
  guarded by one incidental test. A mutation sweep now catches six of six.
  The README's "two moments" was five to ten minutes, and its heap figure
  counted allocations as though they were live.

- [A5 What has never run, on anything](tickets/A5-never-run.md): 86% of
  `corky/` executes, across both architectures; the arm64 suites alone
  report 84%. Exactly ONE statement is unreachable in any configuration,
  and it is a deliberate guard. The instrument was wrong three ways
  before it was right, once calling the first program the device runs
  dead code while the suite ran it. Four gaps were not merely untested:
  three of four script policies were unreachable on the address screen,
  Check an address had no test that could work, the refusal for a PSBT
  with no stated fee had never executed, and the legacy fee assertion
  compared Core to Core so it could not fail.

## The frontier, and what waits behind it

Open tickets are not listed as decisions; this is the shape of them, so a
reader knows what is takeable without opening eleven files.

**Takeable now, nothing blocking:**

- [A8 Every claim the documents make](tickets/A8-claims-versus-reality.md): the cheapest, and the one that stops wrong things being believed.
- [A4 What the device does when hardware misbehaves](tickets/A4-hardware-misbehaves.md): needs the board, which is on.
- [A7 The image a tester flashes](tickets/A7-image-and-provisioning.md): the card is what a tester gets, and nothing has audited it.
- [A10 What the earlier maps left open](tickets/A10-carry-forward.md): needs the board and Ben's phone.
- [A3 What a hostile QR, file or card can make the device do](tickets/A3-hostile-input.md): unblocked by A1.
- [A6 Do the tests measure what they claim](tickets/A6-tests-measure-what-they-claim.md): unblocked by A5.

**Waiting:**

- [A9 Delete what is superseded](tickets/A9-delete-what-is-superseded.md), behind A8.
- [A11 The verdict](tickets/A11-the-verdict.md), behind all of them. It is
  the destination.

## Not yet specified

- What the beta actually is: how many testers, what they are asked to do,
  what they are told not to do, and how they report. It cannot be written
  until the go/no-go questions below have answers.
- Whether anything in the release image needs a second pair of eyes that
  is not Ben's and not mine.
- What happens to the four earlier maps once this one closes.

## Out of scope

- Multisig, message signing and dice entropy. PLAN freezes them out of v1.
- The `butlers-playground` fork's own state, beyond the sync that map N4
  already tracks.
