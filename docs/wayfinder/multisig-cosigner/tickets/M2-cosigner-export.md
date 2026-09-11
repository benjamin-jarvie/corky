# M2 How does the cosigner key leave the device?

Type: `wayfinder:grilling`, HITL. **Blocked by M1 (closed).**
Claimed 2026-09-09.

## Question

A coordinator needs `[xfp/48h/coin'/0h/script']tpub…` to put Core Signer in a
quorum. Charting proved Core will produce exactly that, via the scratch
wallet round trip `write_watch_only` already uses.

What is undecided is the shape of it on the device:

- **Is the cosigner branch a fifth row in the existing export menu**,
  beside Native segwit / Taproot / Nested segwit / Legacy? It is not a
  script policy in the same sense: it produces no addresses on its own.
  Putting it in the same list may be the honest simplification or a
  category error on a screen.
- **Which of the three export routes carry it?** QR, text to type,
  wallet file. The string is about 120 characters, so all three are
  possible where the quorum descriptor was not.
- **Does the screen say what it is for?** "This is one key of a quorum.
  It is useless on its own" is a different message from the single-sig
  export, which is a wallet a coordinator can watch immediately.

M1 answered the shape: named rows at the top (the four single-sig plus
Cosigner (P2WSH)), and an Advanced submenu holding the nested variant,
the account number, and a typed path. What is left for this ticket is
what that typed row DOES.

**It must echo, and M1's answer says why.** A typed path is the only
route to a blinded xpub, and blinding is where a typo is unrecoverable:
get it wrong and the coordinator watches a wallet your key does not open,
with nothing saying so until money is in it. Deriving a test address on
the device, for a person to compare against what the coordinator shows,
is the cheapest check that catches it. Whether that is a screen, how many
addresses, and whether it blocks the export until compared, is this
ticket's to decide.

---

## Answer, 2026-09-09. Ben's call.

### What the record is

138 characters, the form Core produces through the scratch-wallet round
trip `write_watch_only` already uses:

    [8d427bd4/48h/1h/0h/2h]tpubDErVqwfZ8V8DiTQUWnbLScTFk…/0/*

Version 8 as a QR, 3 pixels per module, which is the same density as
today's single-sig export. So the eight-mask cycling already built covers
it and no new rendering work exists.

### The typed row echoes a CHECKSUM, not a test address

This ticket was written assuming a derived test address would catch a
mistyped path. It will not, and the reason is worth keeping: **a cosigner
branch derives a single-sig address, not the quorum's.** The quorum's
address needs every cosigner and Core Signer holds one. An address shown there
would be a thing nobody should ever pay, offered as a safety check.

Core's descriptor checksum does the job instead. Eight characters over
the whole record, and measured:

| change | checksum |
|---|---|
| the path, `2h` to `1h` | `#p3p94ngs` -> `#t8xs25pv` |
| the fingerprint | -> `#p69404l6` |
| one character of the xpub | Core refuses it outright, base58 carries its own |

So the confirm screen shows the fingerprint and the checksum:

    TYPED PATH  ·  CONFIRM
      m/607137099'/1711870460'/1965312408'
      8d427bd4  ·  #p3p94ngs
      Read this to your coordinator.

Eight characters is readable down a phone line, which is how a cosigner
setup actually gets confirmed, and Sparrow shows the same string.

### Routes: QR and file. Not text.

**QR** is the route the air-gap argument rests on and every phone
coordinator takes. Nothing new: same density as the export that ships.

**File** was added after the QR-only answer, because of a consequence
worth stating: **Core reads no QR** (ISSUES.md E-4), so a QR-only export
cannot reach a Bitcoin Core coordinator, and this map's whole destination
is getting a Core key into a quorum. A file closes that.

It needs a new writer. `write_watch_only` produces a Core wallet `.dat`
through `backupwallet`, which is a Core WALLET and not a cosigner record,
and no coordinator imports it as one. What is wanted is the descriptor
in a plain file. **The format has to be agreed with the coordinators
rather than invented here**, and that is the one part of this ticket that
is not already solved. It is M7.

**Text to type is not offered.** Ben's call. It would be three screens of
the same 138 characters, and the file route covers the no-camera case
that would have justified it.
