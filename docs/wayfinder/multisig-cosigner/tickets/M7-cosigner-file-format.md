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

---

## Answer, 2026-09-09. Read from each project's source.

### The format with the widest support

**A bare key expression, one line, nothing else:**

    [8d427bd4/48h/1h/0h/2h]tpubDErVqwfZ8V8DiTQUWnbLScTFk2Sfar7uB8V4LAWRpu7h5…

Coldcard writes exactly this as `key_expr.txt`
(`shared/export.py:512`, `make_key_expression_export`), Sparrow reads it
(its Specter DIY and Krux importers, and line 3 of a BSMS round-1 file),
and Nunchuk reads it (`Utils::ParseSignerString`,
`src/descriptor.cpp:405`).

**Note what Coldcard does NOT write: the `/0/*` suffix.** Their line is
`[xfp/path]xpub` and the fingerprint is lowercased. Core's
`listdescriptors` gives us the suffix, so Corky has to strip it. That is
the single most actionable detail in this ticket.

### The file does NOT reach Bitcoin Core, and M2 assumed it would

M2 added the file route because Core reads no QR. The research says Core
reads no FILE either: `src/wallet/rpc/backup.cpp` defines
`importdescriptors` with `desc` as `RPCArg::Type::STR`, and
`importwallet`/`dumpwallet` are gone. There is no file-based import at
all.

Worse, **a key expression is not a descriptor.** Core needs
`wsh(sortedmulti(2,…))#checksum`, and a cosigner record is one member of
that. So the file's value for a Core coordinator is that it carries the
string onto the laptop for a person to assemble a descriptor from. That
is real and useful, and it is not "Core imports the file". M2's
reasoning was half right and the map now says which half.

### What breaks a plain `.txt`, all from source

- **Sparrow has no generic "descriptor" cosigner importer.** The user
  must choose **Specter DIY** or **Krux** from the list. `io/Descriptor.java`
  is a whole-wallet importer, never a cosigner one.
- **The whole file is read verbatim.** A comment, a header, a second
  line or a `wsh(...)` wrapper all break it.
- **Nunchuk uses `regex_match`**, a full match allowing at most one
  trailing newline. CRLF, a BOM, or a leading space fails.
- **Key-origin brackets are mandatory**, exactly 8 hex, and no `m/`
  inside them. drongo's `KEY_ORIGIN_PATTERN` takes `h` or `'` equally.

### The other format worth having

Coldcard's generic JSON (`generate_generic_export`, `shared/export.py:370`)
is the only shape that four Sparrow importer classes AND Nunchuk's JSON
path both name. Top level `chain`, `xfp`, `account`, `xpub`, then objects
`bip44 bip49 bip84 bip48_1 bip48_2 bip45`, each with `name`, `xfp`,
`deriv`, `xpub`, `desc`.

**A gotcha if it is ever shipped**: Sparrow's `ColdcardMultisig` checks
the top-level `xpub`+`path` branch FIRST and enforces the SLIP-132
prefix against the script type, so a plain `tpub` there is rejected for a
P2WSH wallet. The nested `bip48_2` form, or `p2wsh_deriv`/`p2wsh` with a
`Vpub`, is what works.

Whether Corky writes the JSON as well as the one-liner is a decision and
not a fact, so it is **M8** rather than an answer here.
