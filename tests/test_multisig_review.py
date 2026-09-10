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
    finally:
        daemon.terminate(); daemon.wait()
    print("\n" + ("=" * 60))
    print(f"MULTISIG REVIEW: {'FAIL ' + str(len(fails)) if fails else 'PASS'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
