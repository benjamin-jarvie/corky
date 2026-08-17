"""Cross-implementation address check.

Derives mainnet addresses for the canonical test mnemonic through the full
Corky path (shim -> xprv -> Core deriveaddresses) and compares them to the
published BIP84/BIP86 test vectors that every other wallet (Sparrow, embit,
Electrum, Trezor) derives. If these match, Corky's wallets are byte-for-byte
interoperable with the ecosystem.

Vectors: BIP84 reference vectors (bitcoin/bips bip-0084) and BIP86
reference vectors (bip-0086), mnemonic "abandon ... about", no passphrase.

Runs a throwaway offline mainnet bitcoind (no chain, no network).
Run: python3 tests/test_addresses.py
"""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
from bip39_shim import mnemonic_to_xprv  # noqa: E402
import signer  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"

# Published reference vectors.
BIP84_FIRST_RECEIVE = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
BIP84_SECOND_RECEIVE = "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g"
BIP84_FIRST_CHANGE = "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el"
BIP86_FIRST_RECEIVE = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"
BIP86_SECOND_RECEIVE = "bc1p4qhjn9zdvkux4e44uhx8tc55attvtyu358kutcqkudyccelu0was9fqzwh"
BIP86_FIRST_CHANGE = "bc1p3qkhfews2uk44qtvauqyr2ttdsw7svhkl9nkm9s9c3x4ax5h60wqwruhk7"


def main():
    datadir = tempfile.mkdtemp(prefix="corky-derive-")
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-networkactive=0", "-listen=0",
         "-server=1", "-dbcache=4", "-maxmempool=5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="main")
    failures = []
    try:
        for _ in range(120):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)

        xprv = mnemonic_to_xprv(MNEMONIC)
        cases = [
            ("wpkh", 84, 0, [BIP84_FIRST_RECEIVE, BIP84_SECOND_RECEIVE]),
            ("wpkh", 84, 1, [BIP84_FIRST_CHANGE]),
            ("tr", 86, 0, [BIP86_FIRST_RECEIVE, BIP86_SECOND_RECEIVE]),
            ("tr", 86, 1, [BIP86_FIRST_CHANGE]),
        ]
        for func, purpose, change, expected in cases:
            raw = f"{func}({xprv}/{purpose}h/0h/0h/{change}/*)"
            checksum = rpc.call("getdescriptorinfo", raw)["checksum"]
            got = rpc.call("deriveaddresses", f"{raw}#{checksum}",
                           [0, len(expected) - 1])
            label = f"bip{purpose} {'change' if change else 'receive'}"
            if got == expected:
                print(f"ok   {label}: {got[0]}...")
            else:
                failures.append(f"{label}\n  got:  {got}\n  want: {expected}")
                print(f"FAIL {label}")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)

    if failures:
        print("\n" + "\n".join(failures))
        sys.exit(1)
    print("\nADDRESS PASS: shim + Core derive the published BIP84/BIP86 vectors")


if __name__ == "__main__":
    main()
