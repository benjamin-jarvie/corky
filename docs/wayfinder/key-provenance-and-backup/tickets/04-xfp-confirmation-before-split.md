# 04 What the XFP confirmation shows before a split

Labels: wayfinder:grilling (HITL)
Blocked by: 03

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
