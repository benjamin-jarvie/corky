# The Two Backups: What Your Seed Words Actually Save, and What They Don't

*Draft v1, 2026-08-18. For Bitcoin Butlers. ~2,400 words. Written from the
Corky build notes; technical claims trace to Bitcoin Core's
managing-wallets.md, BIP32/BIP39/BIP93, and the linked discussions.*

---

Most Bitcoin users believe one sentence that is only half true: "my twelve
words are my wallet."

The words are one of two backup traditions that grew up side by side and got
mixed together in most people's heads. Untangling them explains a Bitcoin
Core doc that confuses newcomers, a ten-year-old argument among developers,
and several decisions you should make on purpose instead of by default. We
hit every one of these building Corky, our signing device that runs Bitcoin
Core itself, so this article walks the same road we walked.

## One key, two ways to write it down

Since 2013, almost every wallet derives all of its addresses from a single
master key, through a standard called **BIP32** ("hierarchical deterministic
wallets"). One secret at the root, a tree of keys below it. Back up the root
once and every future address is recoverable. Before BIP32, wallets held a
bag of unrelated keys, and a backup went stale the moment a new key was
generated. Core's own documentation still carries the scars of that era.

The root secret can be written down two ways.

**The BIP32 way: the raw key.** The master key serializes as a string
starting with `xprv...`, 111 characters of base58. Modern practice wraps it
in a **descriptor**: the key plus the derivation path, the script type, and
a checksum, in one line of text. A descriptor is a complete recipe. Hand it
to any modern wallet and it rebuilds exactly the right addresses, no
guessing. This is the format Bitcoin Core speaks natively.

**The BIP39 way: the words.** Your 12 or 24 words are not the key. They are
a compressed encoding of random entropy, which is hashed (2,048 rounds of
PBKDF2, for the curious) into a seed, which becomes the BIP32 master key.
The words exist for one reason: humans cannot stamp `xprv9s21ZrQH...` into
steel without errors, but they can stamp ABANDON. The wordlist has 2,048
words, each identifiable by its first four letters, chosen so that a typo
is caught rather than silently accepted.

So BIP39 is a human-friendly front door to BIP32. Every hardware wallet
uses it. Nearly every steel backup plate sold assumes it. And Bitcoin Core
refuses to implement it. That refusal is not stubbornness, and understanding
it is the most useful mental upgrade in this article.

## Maxwell's objection: the words don't say enough

When BIP39 was proposed, Bitcoin Core developer Gregory Maxwell wrote: "The
lack of versioning is a serious design flaw in this proposal. On this basis
alone I would recommend against use of this proposal."

Here is the flaw in practical terms. Your words encode the root secret and
nothing else. They do not say which derivation path to walk, which script
type your addresses use, or when the wallet was born. Recovery therefore
depends on convention: the recovering wallet guesses the standard paths,
scans, and hopes. The conventions have shifted three times already (legacy,
then segwit, then taproot each brought a new path). Everyone has heard a
story of a recovery that showed a zero balance until the right derivation
was found. The words survived; the instructions did not, because the words
cannot carry instructions.

A descriptor carries the instructions. That is the whole difference. The
words are a backup of your *secret*. A descriptor is a backup of your
*wallet*.

Electrum rejected BIP39 for exactly this reason and built versioning into
its own seed format. Core went further and made the complete recipe, the
descriptor, its native object. The ecosystem shipped BIP39 anyway, because
stampable words won the market, and honestly, steel in your hand beats
elegance in a spec. Our own backups are BIP39 plates. Yours probably are
too. The point is not to feel bad about the words. The point is to know
what they leave out, and to write the missing part down.

**The practical rule: back up your words AND your public descriptor.** The
descriptor with public keys (it starts `wpkh(xpub...)` or similar) reveals
addresses but cannot spend. Print it, save it with your estate documents,
staple it to the inside of your safe. Words restore the secret; the
descriptor restores the map. Together they are a complete recovery with no
guessing, on any wallet software, decades from now.

## What Bitcoin Core's backup doc is really telling you

Core's managing-wallets.md describes backing up `wallet.dat`, encrypting the
wallet, and warns: "if the passphrase is lost, all the coins in the wallet
will also be lost forever." Threads about this doc go in circles because
readers assume it describes the same kind of backup as seed words. It does
not. A wallet-file backup saves the keys AND the metadata: labels,
transaction history, the exact descriptor set. Richer than words, and also
heavier: it is a file, it must live on media, and the file format belongs
to one program.

The doc is also honest about what wallet encryption is for: it protects the
file at rest, against someone who copies wallet.dat or sits down at your
unlocked computer. It does not protect against a keylogger, and it does not
make the file safe to store carelessly. Encryption narrows the attack, it
does not remove it.

Ben Westgate, who created the codex32 backup standard, put the resulting
landscape well in a recent thread: encryption and secret-splitting are the
tools for *backup privacy*, so that one compromised hiding place does not
reveal the key. Multisig addresses *different threats*, and these are not
either-or decisions. His example: if you want one stolen backup to reveal
nothing, split the seed so any two shares recover it but one alone is
useless. If you want theft of a whole signing device to be insufficient to
spend, use multisig. If you want both properties, use both. A jab from the
same thread is worth keeping: reinventing 2-of-2 by pairing an encrypted
backup with its password stored elsewhere gives you the fragility of
multisig with none of its guarantees. Decide which property you are buying
before you pay complexity for it.

And on media: paper burns, ink fades, hard drives die quietly. Steel
survives the house fire. Optical discs, unfashionable as they are, resist
solar storms, EMPs and magnets, and industry archives use magnetic tape in
salt mines. Redundancy across media types is cheap. The failure that
actually takes people's coins is almost never an exotic attack. It is one
backup, in one place, in one format, that stopped being readable.

## The trust question nobody asks about their signer

Here is the part of the story we only understood by building.

Whatever writes your backup and signs your transactions is software, and
you are trusting its authors. The question worth asking is: *whose
implementation of Bitcoin's wallet logic does your device run?*

Hardware wallets each run their vendor's own implementation. DIY signers
like SeedSigner run a small open-source reimplementation (embit) chosen for
auditability: few thousand lines, readable in an afternoon. These are
legitimate choices with a real trade-off: small and reviewable, but a
rewrite, maintained by a handful of people.

There is a third option almost nobody exercises: run the reference
implementation itself. Bitcoin Core's wallet code is the most reviewed
wallet code in existence. It is also enormous, and was never packaged as a
signing device. Corky is our attempt at exactly that: SeedSigner's hardware
(a radio-free Raspberry Pi, a camera, a small screen), but the wallet brain
is bitcoind, wallet-only, offline, with the wallet living in RAM and dying
at power-off. Every derivation, every fee calculation, every signature is
Core's code. The one exception is printed on the box: Core will never read
BIP39 words, so a 92-line translator, standard-library hashing only,
verified against the official test vectors, turns your words into the xprv
format Core imports. If you enter a descriptor instead, even that
disappears, and the device is Core from the first byte. Maxwell's position,
made physical.

Neither philosophy wins outright. Minimal code you can audit yourself,
versus maximal review by the most eyes in the industry. What matters is
that you know which one you picked.

## Air-gapped computers versus hardware wallets

The same honesty applies to the device question, and the industry sells
more certainty here than it owns.

**A hardware wallet** (Coldcard, Jade, Trezor and kin) is a purpose-built
computer with a secure element, a PIN, and keys stored inside the device.
Its strengths: nothing to assemble, keys survive between sessions,
tamper-resistant storage, a vendor doing security work for you. Its trusts:
the vendor's supply chain, the vendor's firmware, and the fact that the
device *contains your key* from setup day until the day you lose it, so a
seized or stolen device is a live problem the PIN must hold against.

**An air-gapped computer** (SeedSigner-style, and Corky) inverts the model.
The device stores nothing. You bring the seed to each session, on paper or
steel or a SeedQR; sign; power off; the device forgets. Its strengths:
statelessness means a confiscated device holds nothing, generic parts mean
no wallet-shaped purchase trail, and the whole stack is inspectable. Its
trusts: whoever assembled it (you), the general-purpose OS underneath, and
the seed's exposure in the room during entry. The radios deserve plain
words too: a Pi Zero 2 W has WiFi on the board, disabled by configuration,
and configuration is a claim, not physics. We moved Corky to a compute
module manufactured without radios because "cannot transmit" beats
"promised not to."

One more asymmetry worth naming: signature exfiltration. A malicious signer
can leak your key through its choice of signature nonces while producing
transactions that look perfectly normal. Some hardware wallets counter this
with anti-exfil protocols, where the coordinator contributes randomness.
Corky cannot run those protocols, because Core generates its own nonces and
exposes no hook. Our answer is different: the signing binary is Core's
reproducible build, hash-verified, so you are trusting published code
rather than a protocol. Anti-exfil defends against a compromised build;
transparency defends against a compromised vendor. Know which defence you
hold, because neither covers both.

## What we'd actually tell you to do

For most people holding meaningful savings:

1. **Words on steel, two locations.** BIP39 remains the right secret backup
   for humans. Buy plates or stamp washers; paper is a fire away from gone.
2. **Public descriptor on paper, with your documents.** This is the missing
   half. Export it from Sparrow or Core (or your device). It cannot spend;
   it can only make recovery exact instead of a guessing game.
3. **Decide what one stolen backup should reveal.** If the answer is
   "nothing," look at codex32 (BIP93): seed shares with hand-checkable
   checksums, k-of-n recovery, made for steel and paper. Splitting beats
   clever hiding.
4. **Multisig when a single device or person must not be enough.** It is a
   spending policy, complementary to all of the above, and it raises the
   metadata stakes: multisig recovery needs every cosigner's public key, so
   the descriptor backup stops being optional and becomes mandatory.
5. **Pick your signer's trust model on purpose.** Vendor implementation in
   tamper-resistant hardware, small reimplementation you can read, or the
   reference implementation on hardware you assembled. All three are
   defensible. Choosing by default is not.

The words are a fine backup of a secret. They were never a backup of a
wallet. Write down both halves, know what your signer runs, and most of the
disaster stories in this space stop being possible.

---

*Corky is our open build of the third trust model: Bitcoin Core as an
air-gapped, stateless signer. The build notes, including everything that
went wrong, are public. If you want help setting up any of the models
above, that is literally our job.*
