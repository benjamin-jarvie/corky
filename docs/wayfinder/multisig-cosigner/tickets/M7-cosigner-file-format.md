# M7 What file does a coordinator want a cosigner key in?

Type: `wayfinder:research`, AFK. **Blocked by M2 (closed).**
Claimed 2026-09-09, resolved by subagent.

## Question

M2 settled that the cosigner record leaves by QR and by file, and that
the file needs a new writer. `write_watch_only` makes a Core wallet
`.dat` through `backupwallet`, which is a wallet and not a cosigner
record; nothing imports it as one.

So: **what format do the coordinators actually read?** Not what looks
reasonable. What each one parses today, read from its source.

- **Bitcoin Core.** The reason this route exists at all, since Core reads
  no QR. Core takes a descriptor as an `importdescriptors` argument, so
  the question is whether a file helps it at all or whether the answer is
  a string a person pastes.
- **Sparrow.** Reads several cosigner formats. Which, and is one of them
  a plain descriptor in a text file?
- **Nunchuk.** `libnunchuk` is cloned-readable and takes arbitrary
  miniscript; find its import path for a single cosigner.
- **Coldcard's** JSON export shape is worth reading even though Corky is
  not a Coldcard, because coordinators already parse it and matching an
  existing shape beats inventing one.

Resolve by reading each project's own source, not its documentation, the
way `tests/sparrow/` was built. The answer records the format chosen and
which coordinator's parser was read to choose it.

TESTING.md rule 8 applies to whatever is built afterwards: an interop
claim tested with your own tools is not an interop claim.
