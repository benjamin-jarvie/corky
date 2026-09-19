# Map: A wrong character cannot pass, and the paper gets fixed

Label: `wayfinder:map`. Tickets are in `tickets/`, one file each.
Charted 2026-09-19.

## Destination

**A person typing their paper backup back in cannot get more than one
character wrong, is told exactly what their paper should say, and is
told honestly at the end what was corrected.**

The map is done when the check screen behaves that way on the board and
the screens say it in words Ben approves.

## Notes

- **Why this matters, Ben, 2026-09-19.** The paper backup is the only
  backup (PLAN A-24). A single wrong character on it is a dead backup,
  and nothing else in the system will ever find that error. The check is
  the only place it can be caught.
- **What changed the shape of this map.** The device cannot know whether
  a mismatch is a wrong paper or a slipped thumb. The charting session
  spent its first question on how to make the device decide, and Ben
  threw the question out: "Who cares if they accidentally did it versus
  the paper being wrong." Show both characters and the PERSON decides in
  a glance, because they are holding the paper. That answer deleted a
  two-button prompt and every branch behind it.
- **Execution is carried IN this map**, as every previous one in this
  repo has done.
- Skills: `/mp-tdd` for anything built, `/mp-code-review` before it
  lands. `TESTING.md` rules 1 to 12a bind every test.
- **Rule 12a's other half is the house rule of this map.** The box
  numbering defect was reported three times and missed twice, because
  each time it was diagnosed by reading the loop instead of typing a key
  the way a person types one, with a mistake in it. Every claim here is
  driven through the real flow, with a mistake, before it is believed.
- PLAN A-11 holds. Nothing here parses a key: the device compares two
  strings it is already holding.

## What is already established

Facts from the charting session, 2026-09-19. No ticket re-derives them.

- **The typed string is scaffolding.** The paper is the artifact. The
  device correcting what was typed costs nothing, because nobody keeps
  it; only the paper has to end up right.
- **Blocking catches a SKIPPED character.** A skip shifts every
  character after it, so without blocking a person types 90 wrong
  characters before anything says so. This is a stronger reason for
  blocking than the one the idea arrived with.
- **Revealing the correct character leaks nothing.** The device drew the
  whole key on the panel two screens earlier.
- **The first 16 characters cannot be wrong.** They are prefilled, being
  the same on every Core master key on a network (`signer.MASTER_PREFIXES`,
  measured 2026-09-19).

## Decisions so far

<!-- one line per closed ticket -->

- [C1 What may the device assume when the paper and the typing disagree?](tickets/C1-what-the-device-assumes.md):
  nothing. It shows both characters and names the place, and the person
  decides which was wrong by looking at their paper. It interrupts only
  when they try to move FORWARD with one still wrong; a character fixed
  in place costs nothing.
- [C2 What does the last screen claim?](tickets/C2-the-final-claim.md):
  the number of corrections, that this key with those corrections opens
  that fingerprint, and a warning that an uncorrected paper may not
  recover the funds. Zero corrections keeps today's "your paper opens
  key X", which is then true.
- [C3 Does CHECK survive?](tickets/C3-checks-fate.md): no. If a wrong
  character cannot pass, the key is verified by the time it is finished,
  so CHECK can never fail and becomes DONE. The `marked` state, the
  fix-walking and the red-after-CHECK behaviour go with it.

## Not yet specified

- **Counting.** Whether a correction is counted per character or per
  box, and whether correcting the same character twice counts twice.
  Cheap either way; it only matters to the sentence on the last screen.

## Out of scope

- **The same flow on the "type a private key" screen.** That screen is
  restoring a key the device does not have, so there is nothing to
  compare against and none of this can apply. Core still refuses what is
  not a key, which is the only check available there.
- **Re-verifying the paper after a correction.** Put as an option in
  charting and rejected: it is a second pass over the corrected
  characters, and Ben chose the warning on the last screen instead.
