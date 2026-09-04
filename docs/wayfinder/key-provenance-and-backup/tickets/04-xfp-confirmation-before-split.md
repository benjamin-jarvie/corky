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
3. Whether the XFP goes ON the backup. Bails defaults the codex32 identifier
   to the BIP32 fingerprint, so the paper names its own key. Ours derives an
   identifier from the seed instead. Changing it makes our strings match the
   convention and makes a share self-describing.
4. Whether the same confirmation guards signing, not only splitting. A signer
   that cannot say which key is open invites signing with the wrong one.
5. What the abort path is, and whether it differs from KEY2 and KEY3
   elsewhere (hw/HARDWARE.md: back one page versus abort the flow).
