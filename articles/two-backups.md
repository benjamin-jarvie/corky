# Seed Generation, Seed In Use, Seed At Rest: An Honest Map of Bitcoin Self-Custody

*Draft v2, 2026-08-18. For Bitcoin Butlers. The framework of this article,
one secret weighed across three phases of its life, comes from jimbocoin.
Technical claims trace to Bitcoin Core's managing-wallets.md, BIP32/39/93,
the SeedPicker Solitaire repo, the SeedSigner dice-generation analysis, the
Yeti Cold protocol, and linked discussions with Ben Westgate.*

---

Most Bitcoin users believe one sentence that is only half true: "my twelve
words are my wallet."

The words are one piece of a system with three distinct phases, and each
phase has its own threats, its own tools, and its own ways to fool
yourself. A seed is **generated** once, **used** every time you sign, and
**at rest** in your backups for decades. Most custody advice argues about
one phase while silently assuming the other two are fine. This article
walks all three, using what we learned building Corky, our signing device
that runs Bitcoin Core itself, and it names the trade-offs the industry
prefers to round off.

## Phase 1: Seed generation, or the problem nobody can audit

Every wallet begins with one gulp of randomness. Every property you will
ever have flows from those 128 or 256 bits being genuinely unpredictable.
And here is the uncomfortable fact this phase turns on: **a compromised
random number generator is undetectable from its output.** A malicious or
broken generator can emit seeds that pass every statistical test ever
devised while being predictable to whoever planted the flaw. You cannot
audit randomness by looking at it. Firmware review helps the one percent
who read code; nobody reviews the silicon.

This stopped being theoretical. In 2026, a Coldcard entropy failure
demonstrated the exact scenario: seeds from the device's compromised RNG
path were at risk, while seeds derived from user-supplied dice rolls
remained secure. One sentence from the dice analysis deserves to be
engraved somewhere: **"You have to trust a seed a device creates for you.
You can verify a seed you rolled yourself."**

The asymmetry that saves us: generation is unverifiable, but everything
after generation is deterministic and therefore checkable. If the entropy
comes from your own hands, the device's remaining work (checksum,
derivation, addresses) can be cross-checked against independent software
and a liar gets caught. Physical entropy converts the one untrustable step
into the one step you performed yourself.

So: dice or cards?

**Dice, examined honestly.** The instinctive worry about dice, biased
faces, turns out to be the wrong worry. Measured real-world dice bias runs
around 1.4 percent, which costs a 24-word seed roughly 2.9 bits out of
256. Negligible. The real problems are human and structural. Human: the
procedure is boring, and a bored human skips steps; twenty honest rolls
followed by eighty impatient button-mashes is not entropy, and nothing in
the procedure catches it. Structural, and this is the one that changed our
recommendation: **the mapping from rolls to seed happens inside software.**
A survey of seventeen implementations found five incompatible
constructions: hash the digit string, remap sixes then hash, pack bits
directly, treat the rolls as one base-6 number, or use a worksheet.
Identical rolls produce different seeds on different devices. You cannot
compute SHA-256 by hand, so you are back to trusting the device for the
step the dice were meant to take away from it. The mitigation exists,
verify with disposable test rolls against a second implementation, but the
dependence never goes to zero.

**Cards, examined honestly.** SeedPicker Solitaire (jimbocoin's procedure)
was designed against six criteria: easy to learn, hard to screw up, errors
detectable, fast, enough entropy, resists bias. A standard 52-card deck,
riffle-shuffled seven times (the count research says suffices), then 23
pairs drawn without replacement. Each pair maps to a seed word through a
**printed lookup table**, and a shortcut removes even the table-reading
risk: pairs of different suits always land on a valid word. The 24th word
is the checksum, so a transcription error announces itself instead of
surfacing years later as a wallet that restores empty. The full-deck draw
preserves slightly more than 205 bits, comfortably past the 128 bits that
matter once a public key is exposed.

Why cards beat dice is now precise: **the deck maps to words on paper, in
the open, by lookup; dice map to seeds inside arithmetic you cannot
perform.** With cards, the offline device only computes the final checksum
word, and that single computation is cross-checkable. With dice, the device
performs the whole conversion, and five mutually incompatible conventions
mean even honest devices disagree. Shuffling is also a skill humans
practice for fun, which is not nothing: the procedure people enjoy is the
procedure people complete.

The bias objection to human entropy deserves its steel-man, because the
"do not roll your own randomness" advice came from somewhere real: humans
inventing "random" values from their heads are catastrophically
predictable, and humans get bored inside long procedures and start
improvising. The cards answer both, not by asking the human to be random,
but by making the physics short, pleasant, and checksummed. The human
shuffles; the deck is random.

**Ranked by how much unverifiable trust each method requires:** cards the
least (one cross-checkable computation), dice next (the whole mapping,
mitigated by test-roll verification), device RNG the most (the one step
that can never be audited). Device generation remains a defensible
convenience at small amounts; the Coldcard incident is the price sheet
for that convenience at large ones.
Corky's own scope excludes on-device generation entirely. We wrote "the
device deliberately has no entropy story" into the spec before we could
articulate why; this is why.

## Phase 2: Seed in use, or who signs and on what

Signing is where the seed touches a computer. Three questions decide
everything: whose wallet code runs, on what hardware, and what does the
device remember afterward.

**Whose code.** Hardware wallets run their vendor's implementation.
SeedSigner-class DIY devices run a small open reimplementation chosen for
auditability. Corky runs the reference implementation, Bitcoin Core,
wallet-only and offline, because Core's wallet logic is the most reviewed
in existence. Yeti Cold, JW Weatherman's protocol, makes the same bet at
system scale: nearly everything it does is Core, on the argument that you
depend on Core anyway, so depend on only that.

State the counter-argument fairly, because it is strong, and it rests on
one epistemic premise jimbocoin states better than anyone: "The only time
you know for sure your seed hasn't leaked is before it has been entered
into any device. At any other time you can't be sure." No audit disproves
a leak you cannot see, so his answer is structural: multi-vendor multisig
where no single vendor ever sees a quorum of your seed material, because
it is vanishingly unlikely that two independent vendors carry an
exfiltration bug at the same time, exploitable by the same parties.
Ideally you even reproduce the coordination (the coordinator: the online
watch-only wallet app, such as Sparrow, that builds transactions for your
signer to approve) on two independent stacks and confirm both derive
identical addresses before funding. Core is
simultaneously the most reviewed codebase in Bitcoin and its most valuable
infiltration target. Which risk is larger, one infiltration of the
best-reviewed honeypot or a coordinated simultaneous infiltration of
several smaller vendors, is genuinely unresolved; we hold the Core side of
that bet with our eyes open, and it is a bet.

**On what hardware, and the question you asked us straight: the wiped
laptop.** The standard air-gap recipe says factory-reset an old laptop and
never connect it. Honesty requires saying what that does not achieve. A
wipe replaces the software; it does not remove the WiFi and Bluetooth
hardware, and every off-switch you can reach from the keyboard is a
software claim about that hardware. The OS toggle, rfkill, even the BIOS
setting are all promises made by code you cannot see, on radios that are
still physically powered. For most threat models the promise is probably
kept. "Probably kept" is not an air gap.

The honest ladder, weakest to strongest:

1. Software disable (settings, rfkill, BIOS): a claim, not a fact.
2. Driver removal or an OS that never ships the drivers: a stronger claim,
   still software.
3. **Open the laptop and pull the radio card.** In most laptops WiFi and
   Bluetooth live on one small M.2 or mini-PCIe card with two antenna
   leads. Ten minutes with a screwdriver converts "promised off" into
   "physically absent." If you keep a laptop signer, this is the step that
   makes the word air-gap true.
4. Hardware manufactured without radios. This is why Corky moved from the
   Pi Zero 2 W (radio on the die, disabled by configuration) to a compute
   module sold without wireless silicon. "Cannot transmit" outranks every
   promise on the list.

Yeti, to its credit, is honest about its own gap: keys cross to the
networked machine on USB sticks because Core has no offline QR signing,
and the protocol accepts that as a measured compromise. USB is a wider
channel than photons through a camera, and a stick is writable both ways.
Reasonable people accept it; nobody should accept it unknowingly.

**What the device remembers.** A hardware wallet keeps your key inside it,
guarded by a PIN and a secure element, from setup until loss. A stateless
signer (SeedSigner, Corky) holds nothing: you bring the seed each session,
sign, power off, and the device forgets. Statelessness means a seized
device is just electronics. Its price must be stated with the same
honesty, and jimbocoin's premise above sets it: the seed is exposed in the
room at every use, and every entry into a device is another moment after
which "it has never leaked" can no longer be known for certain. The
stateless answer (the same audited device each time, nothing persisted,
a reproducible binary) is a real answer, not a complete one. Pick
deliberately: state guarded by silicon, or no state and disciplined
handling.

One asymmetry to complete the picture: a malicious signer can leak key
material through its signature nonces while producing normal-looking
transactions. Some hardware wallets counter with anti-exfil protocols
where the coordinator contributes randomness. Corky cannot, because Core
generates its own nonces and offers no hook; our answer is that the
signing binary is Core's reproducible, hash-verified build. Anti-exfil
defends against a compromised build, transparency defends against a
compromised vendor, and neither defends against both.

## Phase 3: Seed at rest, or the two backups

Now the phase where most coins are actually lost, and the distinction the
whole article hangs on.

**Your words back up a secret. A descriptor backs up a wallet.** BIP39
words encode entropy and nothing else: no derivation path, no script type,
no birth date. Recovery from words alone is a guessing game played against
shifting conventions, which is why Core developer Gregory Maxwell opposed
the standard from the start ("The lack of versioning is a serious design
flaw... On this basis alone I would recommend against use") and why
Bitcoin Core never implemented it. Core's native object, the descriptor,
is the complete recipe: key, path, script type, checksum, one line of
text. The ecosystem shipped BIP39 anyway because words stamp into steel
and elegance does not.

The gap closes for the cost of one sheet of paper. Words on steel hold
the secret; a printed public descriptor beside your documents holds the
map. The descriptor cannot spend; its only effect is turning recovery
from archaeology into a lookup, so the tradeoff runs one way: a page of
non-spending paper against a guessing game decades from now.
With multisig the rule sharpens, with one exception worth knowing
(FractalEncrypt's point): in a 2-of-2, the two seeds alone can both
reconstruct the wallet and spend, and with only four script policies in
existence, brute-checking them is trivial, so the descriptor backup is
optional there. Anything above 2-of-2 flips it to mandatory: a 2-of-3
can spend with two seeds but cannot rebuild the wallet without the third
cosigner's public key, and only the descriptor carries it.

**What Core's own backup doc is telling you.** managing-wallets.md
describes wallet-file backups (keys plus labels, history, and the
descriptor set, richer than words and heavier: a file, on media, in one
program's format) and is refreshingly blunt about encryption: it protects
the file at rest, a keylogger defeats it, and "if the passphrase is lost,
all the coins in the wallet will also be lost forever." Encryption narrows
an attack; it does not remove one.

**Backup privacy, from the person who built the standard.** Ben Westgate,
codex32's author: encryption and secret-splitting are the tools for backup
privacy, so a single compromised hiding place reveals nothing; multisig
addresses different threats; and these are not either-or decisions. Want
one stolen backup to disclose nothing? Split the seed codex32-style,
k-of-n, checksums verifiable by hand on paper. Want theft of a whole
signer to be insufficient to spend? Multisig. Want both properties? Use
both. And the companion warning from the same thread: pairing an encrypted
backup with a separately-stored password hand-builds a fragile 2-of-2; if
you want 2-of-2, the protocol sells the real thing.

**Media and transcription.** Paper burns and fades; steel survives the
house fire; optical discs shrug at EMP and magnets; the archival industry
keeps tape in salt mines. Redundancy across media types is nearly free.
Yeti's transcription discipline (keys written in NATO phonetic alphabet
with periodic checksums) addresses the quietest failure of all,
because the failure that actually takes coins is one backup, in one place,
in one format, that quietly stopped being readable, and handwriting
ambiguity is part of that failure.

## Putting it together: four systems, weighed

**Bitcoin Core on a desktop, single-sig with encryption.** Right engine,
wrong vessel. The keys live full-time on an online, general-purpose
machine, the doc's own keylogger caveat applies, and the passphrase adds a
loss mode faster than it removes a theft mode. To be plain about what is
and is not being dismissed: run Core, run your own node, verify your own
chain; just do not make that online machine the holder of your keys. Core
is the average person's node and watch layer, not their key layer.

**Hardware wallet plus card-generated seed.** The lowest total
unverifiable trust available at ordinary effort: card entropy closes the
RNG hole with only the checksum computed on the offline device, the HWW
gives screen-verified signing and key isolation, and steel words plus a
printed descriptor cover both halves of the backup. Its remaining trusts
are the vendor's firmware and supply chain, and its remaining loss modes
are the human ones. The BIP39 passphrase sits on a knife edge here: it
defends the steel if the steel is found, and it is the component most
often lost forever, so it trades a theft mode for a loss mode; written
and stored as seriously as the seed itself, with a small decoy balance on
the no-passphrase wallet, the trade tilts one way, and held only in a
skull it tilts the other.

**Yeti Cold.** Core-only 3-of-7 multisig across cheap laptops and
geography: survives four lost keys, requires three compromised locations
to steal, trusts Core and nothing else. Its honest costs: USB crossings
instead of QR, radios handled by procedure rather than by absence (pull
the cards), an on-chain fingerprint from the unusual quorum, and hours of
setup. And one charge this article's own first section requires us to
file: Yeti generates its seeds with Core's random number generator.
Jimbocoin's assessment is exactly right: arguably the best available
software generator, and epistemologically the same risk as letting a
Coldcard or any other manufacturer perform your seed genesis, because no
RNG's output can be verified. "If you're determined to trust a
counterparty, Core is the best counterparty to trust" is both Yeti's best
defense and its honest indictment, and card-generated seeds would close
the gap in Yeti just as they close it everywhere else. For deep cold
storage by someone who accepts the Core bet with that caveat attached, it
remains a serious, published, criticizable protocol, which is more than
most vendors offer.

**Multi-vendor multisig, no vendor a quorum.** The strongest answer to
"what if the implementation itself is the flaw": if no vendor ever sees
enough of your seed material to spend, no single vendor bug, however
invisible, can drain you. Judge it by the same six criteria the card
procedure was designed against: easy to learn, hard to screw up, errors
detectable, fast, enough entropy, resists bias. The cards pass because
they were engineered to pass. Multi-vendor multisig, today, fails the
first two for most people, and its own advocates concede the bind: making
it simpler means making the vendors more alike, and their unlikeness is
the security. For large holdings with a professional or a patient
operator, it is the ceiling. Sold to an average person as a starting
point, it mostly manufactures stuck funds.

## The through-line

One principle survives all three phases: **push trust toward things you
can physically verify or independently cross-check, and know the name of
every trust you keep.** Entropy from your own shuffle. Signing code you
chose on purpose, on hardware whose radios are absent rather than
promised off. Words on steel for the secret, a descriptor on paper for
the map, splitting when privacy of the backup itself matters. None of
this removes trust; it relocates trust to places where lying is hard.

The words were never your wallet. They were one third of one phase of it.
Now you have the map.

---

*Corky is our open build of the reference-implementation trust model:
Bitcoin Core as an air-gapped, stateless signer on radio-free hardware.
The build notes, including everything that went wrong, are public. Helping
people choose among the models above is literally our job.*
