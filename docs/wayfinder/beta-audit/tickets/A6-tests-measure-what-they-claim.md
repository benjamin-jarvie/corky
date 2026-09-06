# A6 Do the tests measure what they claim

Type: `wayfinder:task`, AFK. **Blocked by A1.**

**Blocked by:** A5, whose coverage tells this one where to look first.

## Question

4,473 lines of tests, and in one evening three of them were found to be
measuring nothing: an assertion guarded by a condition that is never true,
a cost claim citing a number no test produces, and a stdin rule asserted
against fakes that could never have caught the defect it existed for.

That is three in one diff. This ticket asks how many more there are.

For every suite, ask the two questions that found those three:

- does each assertion actually execute, on every run, with the values it
  claims? An assertion behind a false guard is a comment.
- does it assert the round trip, or does it assert what the code already
  believes? TESTING.md rule 2 exists because a helper written from the
  code's own mental model agrees with it and is still wrong.

Then the cheap structural check: is there a suite whose failure mode is
"passes when the feature is deleted"?
