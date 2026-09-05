"""Shared plumbing for the Sparrow interop suites.

Three scripts here all need the same things: a throwaway regtest node, a Corky
session, a miner wallet, a way to call the Java tools, and a pass/fail tally.
They each grew their own copy. This is the one copy.

Nothing in here is Corky's code under test. It is scaffolding.
"""
import random
import re
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "corky"))
import signer  # noqa: E402

BUILD = Path(__file__).resolve().parent / ".build"
JAVA_BIN = BUILD / "jdk-25.0.4.1+1/Contents/Home/bin/java"
# A-22 left this repo with no BIP39. This is exactly the key the old
# "abandon x11 about" mnemonic produced on regtest, so every address, fee
# and signature this suite asserts is unchanged by the cut.
XPRV = ("tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpA"
        "joLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd")
MINER = "miner"

SCRIPT_TYPES = (("P2WPKH", "wpkh("), ("P2TR", "tr("))


def require_build():
    if not JAVA_BIN.exists():
        sys.exit("run ./setup.sh first (builds tests/sparrow/.build)")


class Java:
    """Runs a compiled Java tool and returns its marked output lines.

    The tools print `TAG\\tvalue`. Untagged lines are library logging and are
    dropped, so a noisy dependency can never be mistaken for data.
    """

    def __init__(self):
        require_build()
        self.classpath = (BUILD / "cp.txt").read_text().strip() + ":" + str(BUILD / "out")
        self.chain_height = 200
        self.utxo_height = 101

    def __call__(self, cls, *args, raw=False, tags=("OUT",)):
        cmd = [str(JAVA_BIN), "--enable-native-access=ALL-UNNAMED",
               f"-Dchain.height={self.chain_height}",
               f"-Dutxo.height={self.utxo_height}"]
        if raw:
            cmd.append("-Dpsbt.mode=raw")
        cmd += ["-cp", self.classpath, cls, *[str(a) for a in args]]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError((out.stderr or out.stdout)[-1200:])
        marks = {}
        for line in out.stdout.splitlines():
            tag, sep, rest = line.partition("\t")
            if sep and tag in tags:
                marks.setdefault(tag, []).append(rest)
        if "OUT" not in marks:
            raise RuntimeError("no data:\n" + out.stdout[-1200:])
        return marks if len(tags) > 1 else marks["OUT"]


class Regtest:
    """A throwaway regtest node with a Corky session and a miner wallet."""

    def __init__(self, txindex=True, mine=250):
        self.datadir = tempfile.mkdtemp(prefix="corky-sparrow-")
        self.port = random.randint(20000, 60000)
        self.txindex = txindex
        self.mine_blocks = mine
        self.daemon = None

    def __enter__(self):
        (Path(self.datadir) / "bitcoin.conf").write_text(
            "regtest=1\n[regtest]\nrpcport=%d\n" % self.port)
        cmd = ["bitcoind", "-regtest", f"-datadir={self.datadir}", "-listen=0",
               "-fallbackfee=0.0001", "-server=1"]
        if self.txindex:
            cmd.append("-txindex=1")
        self.daemon = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        self.rpc = signer.Rpc(self.datadir, chain="regtest")
        for _ in range(80):
            try:
                self.rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)
        self.wallet = signer.open_session_xprv(self.rpc, XPRV)
        self.pubs = signer.public_descriptors(self.rpc, wallet=self.wallet)
        self.rpc.call("createwallet", MINER)
        self.miner_addr = self.rpc.call("getnewaddress", wallet=MINER)
        self.mine(self.mine_blocks)
        return self

    def __exit__(self, *exc):
        if self.daemon:
            self.daemon.terminate()
            self.daemon.wait(timeout=30)
        return False

    # -- convenience -----------------------------------------------------

    def mine(self, n=1):
        self.rpc.call("generatetoaddress", n, self.miner_addr, wallet=MINER)

    def height(self):
        return self.rpc.call("getblockcount")

    def new_address(self):
        return self.rpc.call("getnewaddress", wallet=MINER)

    def account(self, script_type, branch=0):
        """(fingerprint, path, xpub) for one of Corky's exported descriptors."""
        desc = self.descriptor(script_type, branch)
        m = re.search(r"\[([0-9a-f]{8})((?:/\d+h)+)\](\w+)", desc)
        return m.group(1), "m" + m.group(2), m.group(3)

    def descriptor(self, script_type, branch=0):
        prefix = dict(SCRIPT_TYPES)[script_type]
        return [d for d in self.pubs
                if d.startswith(prefix) and f"/{branch}/*" in d][0]

    def fund(self, address, btc="0.01"):
        """Send to an address and return (txid, vout, rawtx). Does not mine."""
        txid = self.rpc.call("sendtoaddress", address, Decimal(btc), wallet=MINER)
        raw = self.rpc.call("getrawtransaction", txid)
        dec = self.rpc.call("decoderawtransaction", raw)
        vout = [o["n"] for o in dec["vout"]
                if o["scriptPubKey"].get("address") == address][0]
        return txid, vout, raw


class Results:
    """A pass/fail tally with a printed summary and an exit code."""

    def __init__(self):
        self.rows = []

    def record(self, name, ok, note=""):
        self.rows.append((name, bool(ok), note))
        print(("ok   " if ok else "FAIL ") + name + (("  " + note) if note else ""))

    def summary(self, width=70):
        passed = sum(1 for _, ok, _ in self.rows if ok)
        print("\n" + "=" * width)
        print(f"PASS {passed}   FAIL {len(self.rows) - passed}")
        for name, ok, note in self.rows:
            if not ok:
                print("  FAIL " + name + "  " + note)
        return 0 if passed == len(self.rows) else 1
