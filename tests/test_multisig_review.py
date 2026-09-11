"""MULTISIG REVIEW. What the screen says before you sign one share.

Map multisig-cosigner, ticket M9, which builds M3's three decisions.
`tests/sparrow/test_cosigner.py` proves Sparrow takes our cosigner key
and signs beside it. This proves the DEVICE can do it: the review screen
states the threshold, the path and the cosigners, and a partial
signature is delivered rather than refused.

Run: python3 tests/test_multisig_review.py (needs bitcoind)
"""
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402

fails = []
def ok(m): print("ok  ", m)
def bad(m): fails.append(m); print("FAIL", m)


def start_node(prefix):
    datadir = tempfile.mkdtemp(prefix=prefix)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % random.randint(20000, 60000))
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-regtest", "-networkactive=0",
         "-listen=0", "-server=1", "-fallbackfee=0.0001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    for _ in range(120):
        try:
            rpc.call("getblockcount"); break
        except RuntimeError:
            time.sleep(0.5)
    return daemon, rpc, datadir


PATH = "48h/1h/0h/2h"


def cosigner(rpc, name):
    """One member of the quorum: a Core wallet, and its cosigner key."""
    rpc.call("createwallet", name)
    return signer.cosigner_key(rpc, name, PATH)


XPRV = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ss"
        "vpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")

_built = [0]


def build_quorum(rpc, threshold=2, total=3, extra_key=None):
    """A real 2-of-3, funded, with a spend to review. Returns (psbt, keys).

    `extra_key` puts an xprv WE hold into the quorum, so the spend is one
    this device can actually sign a share of.
    """
    tag = f"q{_built[0]}"
    _built[0] += 1
    keys = [cosigner(rpc, f"m9c{tag}{i}")
            for i in range(total - (1 if extra_key else 0))]
    if extra_key:
        rpc.call("createwallet", f"m9x{tag}", False, True, "", False, True)
        raw = f"wpkh({extra_key}/{PATH}/0/*)"
        c = rpc.call("getdescriptorinfo", raw, stdin=True)["checksum"]
        rpc.call("importdescriptors",
                 [{"desc": f"{raw}#{c}", "active": True, "timestamp": "now",
                   "range": [0, 20]}], wallet=f"m9x{tag}", stdin=True)
        keys.append(signer.cosigner_key(rpc, f"m9x{tag}", PATH))
    qw = f"m9quorum{tag}"
    rpc.call("createwallet", qw, True, True, "", False, True)
    for change in (0, 1):
        inner = (f"sortedmulti({threshold},"
                 + ",".join(f"{k}/{change}/*" for k in keys) + ")")
        info = rpc.call("getdescriptorinfo", f"wsh({inner})", stdin=True)
        rpc.call("importdescriptors",
                 [{"desc": f"wsh({inner})#{info['checksum']}",
                   "active": True, "internal": bool(change),
                   "timestamp": "now", "range": [0, 10]}],
                 wallet=qw, stdin=True)
    mw = f"m9miner{tag}"
    rpc.call("createwallet", mw)
    mine = rpc.call("getnewaddress", wallet=mw)
    rpc.call("generatetoaddress", 101, mine, wallet=mw)
    # TWO utxos at DIFFERENT addresses, and a spend that needs both. One
    # input cannot tell a cosigner list that dedupes from one that
    # appends, and the quorum must read "2 of 3" either way.
    for _ in range(2):
        addr = rpc.call("getnewaddress", wallet=qw)
        rpc.call("sendtoaddress", addr, 1.0, wallet=mw)
    rpc.call("generatetoaddress", 1, mine, wallet=mw)
    psbt = rpc.call("walletcreatefundedpsbt", [], [{mine: 1.5}], 0,
                    {"fee_rate": 5}, True, wallet=qw)["psbt"]
    return psbt, keys, mw


def build_decay(rpc):
    """A three-tier decaying quorum, funded, with a spend per tier.

    Our key sits at a DIFFERENT account in each tier, which is not a
    style choice: Core refuses the policy as "contains duplicate public
    keys" when a key repeats at one path, which is Liana's
    DuplicateOriginSamePath seen from the other side.

    Returns (spends, xfp) where spends is [(label, sequence, psbt), ...].
    """
    rpc.call("createwallet", "dours", False, True, "", False, True)
    ours = []
    for acct in (0, 1, 2):
        path = f"48h/1h/{acct}h/2h"
        raw = f"wpkh({XPRV}/{path}/0/*)"
        c = rpc.call("getdescriptorinfo", raw, stdin=True)["checksum"]
        rpc.call("importdescriptors",
                 [{"desc": f"{raw}#{c}", "active": acct == 0,
                   "timestamp": "now", "range": [0, 3]}],
                 wallet="dours", stdin=True)
        ours.append(signer.cosigner_key(rpc, "dours", path) + "/0/0")
    strangers = {}
    for i in (0, 1):
        rpc.call("createwallet", f"ds{i}")
        for acct in (0, 1):
            strangers[(i, acct)] = signer.cosigner_key(
                rpc, f"ds{i}", f"48h/1h/{acct}h/2h") + "/0/0"
    a, b, c = ours
    desc = (f"wsh(or_d(multi(2,{a},{strangers[(0, 0)]},{strangers[(1, 0)]}),"
            f"or_i(and_v(v:multi(2,{b},{strangers[(0, 1)]}),older(10)),"
            f"and_v(v:pk({c}),older(20)))))")
    desc += "#" + rpc.call("getdescriptorinfo", desc, stdin=True)["checksum"]
    rpc.call("createwallet", "dq", True, True, "", False, True)
    rpc.call("importdescriptors", [{"desc": desc, "timestamp": "now"}],
             wallet="dq", stdin=True)
    addr = rpc.call("deriveaddresses", desc, stdin=True)[0]
    rpc.call("createwallet", "dmn")
    mine = rpc.call("getnewaddress", wallet="dmn")
    rpc.call("generatetoaddress", 101, mine, wallet="dmn")
    rpc.call("sendtoaddress", addr, 1.0, wallet="dmn")
    rpc.call("generatetoaddress", 25, mine, wallet="dmn")
    u = rpc.call("listunspent", 1, 9999, [addr], wallet="dq")[0]
    spends = []
    for label, seq in (("normal", 0xfffffffd), ("tier 2", 10),
                       ("tier 3", 20)):
        spends.append((label, seq, rpc.call(
            "walletcreatefundedpsbt",
            [{"txid": u["txid"], "vout": u["vout"], "sequence": seq}],
            [{mine: float(u["amount"])}], 0,
            {"fee_rate": 2, "subtractFeeFromOutputs": [0]}, True,
            wallet="dq", stdin=True)["psbt"]))
    return spends, signer.master_fingerprint(rpc, "dours")


def main():
    daemon, rpc, datadir = start_node("m9-")
    try:
        psbt, keys, mw = build_quorum(rpc)

        # 1. THE THRESHOLD. M3 decision 2: review says "2 of 3". Core
        #    already reports the script type and the threshold, so Corky
        #    reads them and parses no script itself (PLAN A-11).
        info = signer.describe_psbt(rpc, psbt)
        if info.get("quorum") == (2, 3):
            ok(f"review knows the quorum: {info.get('quorum')}")
        else:
            bad(f"1: quorum should be (2, 3), got {info.get('quorum')!r}")

        # 2. A SINGLE-SIG PSBT MUST NOT CLAIM ONE. The screen showing
        #    "1 of 1" on an ordinary spend would be a new lie, which is
        #    the thing A6 was about.
        rpc.call("createwallet", "m9solo")
        solo_addr = rpc.call("getnewaddress", wallet="m9solo")
        rpc.call("sendtoaddress", solo_addr, 1.0, wallet=mw)
        mine = rpc.call("getnewaddress", wallet=mw)
        rpc.call("generatetoaddress", 1, mine, wallet=mw)
        solo = rpc.call("walletcreatefundedpsbt", [], [{mine: 0.5}], 0,
                        {"fee_rate": 5}, True, wallet="m9solo")["psbt"]
        solo_info = signer.describe_psbt(rpc, solo)
        if solo_info.get("quorum") is None:
            ok("a single-sig spend reports no quorum")
        else:
            bad(f"2: single-sig reported quorum {solo_info['quorum']!r}")

        # 3. MIXED INPUTS MUST NOT BECOME ONE CONFIDENT CLAIM. Reading
        #    the first input and printing "2 of 3" over a transaction
        #    that also spends a single-sig UTXO is exactly the kind of
        #    true-looking screen audit A6 removed.
        joined = rpc.call("joinpsbts", [psbt, solo], stdin=True)
        mixed = signer.describe_psbt(rpc, joined)
        if mixed.get("quorum") == "mixed":
            ok("a transaction spending both reports a mixed quorum")
        else:
            bad(f"3: mixed inputs reported {mixed.get('quorum')!r}, and the "
                "screen would state one quorum for all of them")

        # 4. THE COSIGNERS. M3 decision 3: the review screen names every
        #    fingerprint on the transaction. signer.owners() already
        #    reads them; describe_psbt now carries them WITH the path,
        #    because M1 decision 2 puts the path on the same screen.
        if info["input_count"] != 2:
            bad(f"fixture: wanted a 2-input spend, got "
                f"{info['input_count']}; checks 4 and 5 are weaker")
        cos = info.get("cosigners") or []
        want = signer.owners(rpc, psbt)
        if len(cos) == 3 and {x for x, _ in cos} == want:
            ok(f"review names all three cosigners: "
               f"{', '.join(sorted(x for x, _ in cos))}")
        else:
            bad(f"4: cosigners {cos!r} should be 3 entries matching {want!r}")

        # 5. THE ACCOUNT PATH, NOT THE LEAF. Core reports
        #    m/48h/1h/0h/2h/0/0, whose last two steps are the change
        #    branch and the address index. Those change every address
        #    and say nothing about which wallet this is, which is the
        #    thing M1 decision 2 wants the path to say.
        paths = {pth for _, pth in cos}
        if paths == {"m/48h/1h/0h/2h"}:
            ok("the path shown is the account, with no change/index tail")
        else:
            bad(f"5: paths {paths!r} should all be m/48h/1h/0h/2h")

        # 6. A SINGLE-SIG SPEND STILL SHOWS ITS PATH. M1: with arbitrary
        #    paths allowed, the path is the only thing telling a wallet
        #    you set up from one you did not, so it is not multisig-only.
        solo_cos = solo_info.get("cosigners") or []
        if len(solo_cos) == 1 and solo_cos[0][1].startswith("m/"):
            ok(f"a single-sig spend shows its path: {solo_cos[0][1]}")
        else:
            bad(f"6: single-sig cosigners {solo_cos!r} should be one entry "
                "carrying its account path")

        # 7. EVERY INPUT, NOT THE FIRST. A cosigner reader that stops at
        #    input 0 passes checks 4 to 6 and still hides a key from the
        #    screen: this transaction spends the quorum AND a single-sig
        #    utxo, so its second input carries a wallet the first does
        #    not mention.
        mixed_cos = mixed.get("cosigners") or []
        want_mixed = set(want) | {x for x, _ in solo_cos}
        if {x for x, _ in mixed_cos} == want_mixed and len(mixed_cos) == 4:
            ok(f"a mixed transaction names every input's key "
               f"({len(mixed_cos)} of them)")
        else:
            bad(f"7: mixed cosigners {mixed_cos!r} should be 4 entries "
                f"covering {want_mixed!r}")

        # 8. SIGNING NOTHING IS NOT SIGNING. M3 decision 1 delivers a
        #    partial signature instead of refusing it, and `complete`
        #    alone cannot carry that: it is False for one signature of
        #    two AND for none at all. A device that showed SIGNED over an
        #    untouched PSBT would be lying on its most important screen,
        #    which is the exact shape of the bug M4 nearly shipped.
        #
        #    This is a real case and not a contrived one: a loaded Corky
        #    key holds the four standard policies, so it has no key at a
        #    BIP48 path and Core signs nothing at all.
        solo_w = signer.open_session_xprv(rpc, XPRV)
        blind = signer.sign_psbt(rpc, psbt, wallet=solo_w)
        if blind.get("added") is False and blind["complete"] is False:
            ok("a wallet with no key at that path reports nothing added")
        else:
            bad(f"8: added={blind.get('added')!r} for a wallet that signed "
                "nothing, so SIGNED would show over an untouched PSBT")

        # 9. AND A REAL SHARE IS REPORTED AS ONE.
        rpc.call("createwallet", "m9ours", False, True, "", False, True)
        for change in (0, 1):
            raw = f"wpkh({XPRV}/{PATH}/{change}/*)"
            c = rpc.call("getdescriptorinfo", raw, stdin=True)["checksum"]
            rpc.call("importdescriptors",
                     [{"desc": f"{raw}#{c}", "active": True,
                       "internal": bool(change), "timestamp": "now",
                       "range": [0, 20]}], wallet="m9ours", stdin=True)
        quorum_psbt, _, _ = build_quorum(rpc, extra_key=XPRV)
        share = signer.sign_psbt(rpc, quorum_psbt, wallet="m9ours")
        if share.get("added") is True and share["complete"] is False:
            ok("one share of a quorum reports a signature added, not done")
        else:
            bad(f"9: added={share.get('added')!r} complete="
                f"{share['complete']!r} for one share of a 2-of-3")

        # 10. THE DEVICE SIGNS WHERE THE PSBT SAYS. M1 decision 2:
        #     signing takes its path from the PSBT. A loaded key holds
        #     the four standard policies and nothing at a BIP48 path, so
        #     without this the device cannot sign a share at all, which
        #     is the gap between what M4 proved possible and what Corky
        #     does. Same PSBT and same wallet as check 8, which signed
        #     nothing.
        told = signer.sign_psbt(rpc, quorum_psbt, wallet=solo_w,
                                xfp=signer.master_fingerprint(rpc, solo_w))
        if told.get("added") is True and told["complete"] is False:
            ok("a loaded key signs its share at the path the PSBT names")
        else:
            bad(f"10: added={told.get('added')!r} complete="
                f"{told['complete']!r}; the device cannot sign a share")

        # 11. AND IT LEAVES NOTHING BEHIND. The fallback imports the
        #     branch to sign it. PLAN A-24 and the whole persistence
        #     argument say what it imports must not outlive the signing.
        after = {w for w in rpc.call("listwallets") if "sign" in w}
        if not after:
            ok("the branch it imported to sign with is gone again")
        else:
            bad(f"11: {after!r} left loaded after signing")

        # 12. A DECAYING QUORUM. Core types a miniscript witness script
        #     as "nonstandard", so `quorum` is None and the review screen
        #     says no threshold. M3 decision 1 traded SIGNED-over-partial
        #     against decision 2 stating the threshold, and for this
        #     class of wallet the screen never had one. So the screen
        #     says the TIER instead, out of the same asm Core hands over.
        spends, dxfp = build_decay(rpc)
        by_label = {}
        for label, _seq, dpsbt in spends:
            by_label[label] = signer.describe_psbt(rpc, dpsbt)
        if by_label["tier 3"].get("timelocks") == (10, 20):
            ok("review reads both timelocks out of the policy: (10, 20)")
        else:
            bad(f"12: timelocks {by_label['tier 3'].get('timelocks')!r} "
                "should be (10, 20)")

        # 13. AND WHICH TIER THIS SPEND USES. The coordinator chooses it
        #     with nSequence at build time, which M6 measured. The device
        #     cannot change it and the person can refuse it, so the
        #     screen has to show it.
        got = {k: v.get("spend_lock") for k, v in by_label.items()}
        if got == {"normal": None, "tier 2": 10, "tier 3": 20}:
            ok(f"review names the tier each spend enables: {got}")
        else:
            bad(f"13: spend_lock {got!r} should be "
                "{'normal': None, 'tier 2': 10, 'tier 3': 20}")

        # 13b. BIP68 PUTS THE VALUE IN THE LOW 16 BITS. A sequence of
        #      0x00010005 means five blocks; read as a whole word it is
        #      65541, which clears both tiers and would name one the
        #      spend does not reach. Nothing else in this file separates
        #      the two readings, because 10 and 20 survive the mask.
        u = rpc.call("listunspent", 1, 9999, wallet="dq")[0]
        odd = rpc.call(
            "walletcreatefundedpsbt",
            [{"txid": u["txid"], "vout": u["vout"], "sequence": 0x00010005}],
            [{rpc.call("getnewaddress", wallet="dmn"): float(u["amount"])}],
            0, {"fee_rate": 2, "subtractFeeFromOutputs": [0]}, True,
            wallet="dq", stdin=True)["psbt"]
        odd_lock = signer.describe_psbt(rpc, odd).get("spend_lock")
        if odd_lock is None:
            ok("a sequence of 0x00010005 reaches no tier, as BIP68 reads it")
        else:
            bad(f"13b: spend_lock {odd_lock!r} for a sequence whose low 16 "
                "bits are 5; the screen would name a tier not reached")

        # 14. A PLAIN QUORUM CLAIMS NO TIMELOCK. A screen that said
        #     "AFTER 20 BLOCKS" over an ordinary 2-of-3 would be the
        #     same lie in the other direction.
        if not info.get("timelocks") and info.get("spend_lock") is None:
            ok("a plain 2-of-3 reports no timelock and no tier")
        else:
            bad(f"14: a plain quorum reported timelocks "
                f"{info.get('timelocks')!r} lock={info.get('spend_lock')!r}")

        # 15. AND CORKY SIGNS EVERY TIER IT IS IN, IN ONE PASS. Our key
        #     sits at three accounts here. M9's _branches reads all of
        #     them out of the PSBT, so nothing has to be set up first.
        t3 = signer.sign_psbt(rpc, spends[2][2], wallet="dours", xfp=dxfp)
        if t3["added"] and t3["complete"]:
            ok("past its timelock, Corky alone finishes the spend")
        else:
            bad(f"15: tier 3 added={t3['added']} complete={t3['complete']}; "
                "the one-key tier must finish on this device alone")
    finally:
        daemon.terminate(); daemon.wait()
    print("\n" + ("=" * 60))
    print(f"MULTISIG REVIEW: {'FAIL ' + str(len(fails)) if fails else 'PASS'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
