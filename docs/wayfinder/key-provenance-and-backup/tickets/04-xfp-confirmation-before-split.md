# 04 What the XFP confirmation shows before a split

Labels: wayfinder:prototype (HITL)
Blocked by: none (03 closed 2026-09-04)
Assignee: claude (claimed 2026-09-04)
Status: CLOSED 2026-09-04

## Question

Ben's ask (2026-09-04): "the person can see the XFP from home and ensure they
have the right key before splitting. Perhaps show that XFP as a confirmation
before splitting?"

Decide:

1. What the confirmation screen shows. XFP alone, or XFP plus script type,
   derivation and network.
2. Whether it also names the origin from ticket 03, so the user sees WHY
   this key can be split.
3. Whether the XFP goes ON the backup. **CORRECTED 2026-09-04: I recommended
   this and I was wrong.** Research on python-codex32 found that BIP93
   defines NO identifier convention ("We do not define how to choose the
   identifier"), so there is nothing to match. Worse, the XFP is public: it
   appears in every PSBT and descriptor. Putting it on a share lets whoever
   finds that share link it to a specific on-chain wallet and read its
   balance, which turns an individually useless share into a targeted signal
   worth hunting the others for. Corky's `derive_identifier` is
   `sha256(b"corky-id" + seed)[:4]`, domain-separated and one-way. **Keep
   it.** The open question is only whether the XFP appears on the
   CONFIRMATION SCREEN, which is transient, not on the paper, which is not.
4. Whether the same confirmation guards signing, not only splitting. A signer
   that cannot say which key is open invites signing with the wrong one.
5. What the abort path is, and whether it differs from KEY2 and KEY3
   elsewhere (hw/HARDWARE.md: back one page versus abort the flow).

## Resolution (Ben, 2026-09-04)

**Variant C: the fingerprint, where the key came from, and notice that a
retype is coming.** Prototype at `scratchpad/proto/confirm_variants.py`,
rendered at the real 320x240 with Corky's own type and palette.

    SPLIT THIS KEY?

         668B 2262
    loaded from typed words
    you will retype them to confirm

         BACK    SPLIT

It answers the two questions that matter at that moment: **which key**, and
**why this one can be split**. And it sets up the retype rather than
surprising the user with it, which matters because a Core-generated key
reaches a refusal instead and should see that coming.

Rejected: the full variant, with script types, both derivation paths and
network. Every fact a recovery needs, on the screen that authorises the
backup, is a real argument. But four of its five rows are identical for every
Corky key, so they carry no signal at the moment of choosing, and they are
recoverable from the descriptor export, which is a different screen with a
different job.

Rejected: the fingerprint alone. Cleanest, but silent about why this key is
splittable and about the retype.

### The identifier stays ours

Restated so it is not reopened: the XFP appears on this **transient** screen,
never on the **paper**. BIP93 defines no identifier convention, and the XFP is
public in every PSBT and descriptor, so putting it on a share links that share
to an on-chain wallet and its balance. Corky keeps
`sha256(b"corky-id" + seed)[:4]`.

### Finding: head-and-tail colouring does nothing to an XFP

Ben's rule for long strings is four-character groups with the first and last
group coloured differently. **An XFP is 8 characters, so it makes exactly two
groups, and the first and the last are both of them.** The whole string comes
out in the accent colour and the rule distinguishes nothing.

It is a rule for long strings: addresses, xpubs and descriptors, per "Getting
the watch-only descriptor out, and proving it landed". It should not be
applied mechanically to short identifiers. Four-character grouping still helps
an XFP; the colouring does not.

### Left open, deliberately

Whether the review screen shows the XFP so every signature also states which
key. Ben was offered that bundled with C and took C alone, so it stays in the
map's fog as its own question rather than being assumed either way.

Closed.
