# A11 The verdict

Type: `wayfinder:grilling`, HITL. **Blocked by every other ticket.**

**Blocked by:** A1 through A10, all of them.

## Question

Go or no-go on a private beta, with reasons.

This is the destination and it is deliberately last. It is a decision, not
a summary: every finding from A1 to A10 arrives here already marked
blocking or not blocking, and this ticket is where Ben weighs them and
says which way.

What it has to produce, on one page:

- the answer, and the two or three findings that decided it;
- what a tester is asked to do, and what they are asked not to do;
- what is known to be broken and shipped anyway, said plainly, because a
  beta that hides its own limits is not a beta;
- what would change the answer.

If the answer is no, it says what specifically must be true for it to
become yes, in a form somebody can finish.

---

## Prepared for Ben, 2026-09-06. The decision is his.

A1 to A10 are closed. Every finding arrives here already marked. This is
the page.

### Recommendation: NO-GO for a stranger, GO for a supervised pilot

Not because the signer is unsound. The signing path is the best-evidenced
part of it: 132 checks against Sparrow's own library out of its verified
release, a wallet rebuilt from the paper backup that signs a spend the
network accepts, two real mainnet spends on the record, and 86% of
`corky/` measured as executed with exactly one statement unreachable.

The no-go is about the **package**, not the program. Three things.

### The three findings that decide it

**1. A 250-input consolidation can take the board out of memory.**
Re-measured today, three runs. Ordinary payments: 187MB of headroom,
pass. Exchange-batch withdrawals: **74MB against a 100MB requirement**,
fail. A-21 measured 97MB for that shape and R6 measured 81MB; it is
getting worse, not better. A tester consolidating an exchange withdrawal
is not an exotic act, and the failure mode is the device dying mid-sign.

**2. Nobody has proven a coordinator's camera can read this panel.**
Sparrow's *library* is proven, thoroughly. A lens is not a library.
T1, T2, T3, ticket 18 and ticket 22 all ask the same physical question
and none of them has been answered. A signer whose QR cannot be read is
not a signer.

**3. Two testers flashing a week apart get different devices.**
`CORKY_COMMIT="HEAD"`, `OS_IMAGE_SHA256="UNPINNED_UNTIL_FIRST_FLASH"`,
`DEV_IMAGE_SHA256="RECORDED_AFTER_PROVISION"`. And `harden.sh` has never
been run, so the card a tester gets today still has SSH and both radios
on it. A beta where nobody can say what the testers are running produces
bug reports nobody can reproduce.

### What would change the answer

Four things, each finishable, none depending on another:

1. **Run `harden.sh` on the board and watch the leak check go 13 to 0.**
   Every failing row maps to a step; nothing is unaccounted for. It is
   one way and takes SSH with it, which is why it needs your say-so.
2. **Pin the image.** Tag a commit, put the tag in `CORKY_COMMIT`, record
   `OS_IMAGE_SHA256` and `DEV_IMAGE_SHA256` from the flash you actually
   give people. `image/verify-install.sh` then lets any tester check
   their own card against the repository without trusting either of us.
3. **Point a phone and Sparrow's laptop at the panel.** T1, T2, T3, 18,
   22. Half a day with the board on the desk.
4. **Decide what to do about the batch shape.** Either fix it, or state
   an input limit in the tester instructions and have the device refuse
   past it. A-21 already names the fix that would help most:
   `describe_psbt` parses the whole `decodepsbt` document, including
   25,000 output objects it never reads.

Items 1, 2 and 3 are hours. Item 4 is a decision first.

### What a supervised pilot could do today

You, and one person in the room with you, on **mainnet with an amount you
would shrug at**, doing ordinary payments and not consolidations. That
exercises everything the audit could not: the camera, the panel in real
light, and a coordinator that is not a test harness.

### What a tester must be told, if one is handed a device

- **The paper backup is the only backup.** 111 characters, by hand. There
  is no file, no encryption, no second copy. Lose the paper and the coins
  are gone. PLAN A-24, and it is deliberate.
- **Do not consolidate.** Ordinary payments only, until finding 1 is
  settled.
- **This card is a dev image** unless `harden.sh` has been run on it: SSH
  and both radios are live.
- **Only Bitcoin Core and Sparrow can open the paper backup.** BlueWallet,
  Green and Bull Bitcoin cannot.
- **Verify your own card**: `sudo bash /opt/corky/image/verify-install.sh`.

### Known broken and shipped anyway, said plainly

- The batch-withdrawal memory ceiling, above.
- The card channel writes world-readable files: `/boot/firmware` is
  mounted `fmask=0022` by the OS, where the stick's own unit sets
  `umask=0077`.
- The documents describe two builds and the board is a third combination:
  a Zero 2 W answering 320x240. Harmless, and only you can name it.
- `tests/m1` needs Rosetta on an Apple Silicon dev machine, so the QR
  decode path is unmeasured on the main suite and has to be run
  separately.

### What the audit fixed, for weighing against the above

Ten tickets, and the ones that would have reached a tester:

| | |
|---|---|
| A1 | a jammed button hung the device for ever; a PSBT beat the 4MB cap at 6MB |
| A2 | scanning a key wrote a photograph of it to disk; a mistyped WIF reached the panel unredacted |
| A3 | a full stick left a truncated signature and the device said it wrote it |
| A4 | a node that was slow rather than dead froze the panel with no way out |
| A5 | three of four script policies were unreachable on the address screen |
| A6 | **the paper backup check could not fail**: it compared a string with itself |
| A7 | the board was running two things the repo had already fixed, one of them writing Core's log into the ramdisk |
| A8 | the security argument cited a file that has never existed; the RNG ban enforced one of the three things it named |
| A9 | seven of eight "open" issues were already closed |
| A10 | the README's Status showed only the passing half of M0 |

A6 is the one to sit with. The device told people their paper backup was
verified by Bitcoin Core, on the strength of comparing Corky's own copy
of a string to itself. Every suite was green through all of it.
