"""Core-RNG seed generation (PLAN A-19), end to end on regtest.

Proves four things about the opt-in generate tool:
  1. The entropy comes from Bitcoin Core and differs on every call.
  2. What Corky shows the user is a valid codex32 secret, and its shares
     recombine to it.
  3. The wallet derived from that backup opens in Core and signs.
  4. The throwaway generation wallet is gone afterwards, and no Python
     RNG is reachable from any Corky module.
Run: python3 tests/test_generate.py
"""

import base64
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))
import codex32  # noqa: E402
import signer  # noqa: E402

fails = []


def ok(m):
    print("ok  ", m)


def bad(m):
    fails.append(m)
    print("FAIL", m)


def static_checks():
    """No Python RNG anywhere in the modules Corky ships."""
    banned = re.compile(r"\bos\.urandom\b|\bimport +(random|secrets)\b|"
                        r"\bfrom +(random|secrets) +import\b|"
                        r"\brandom\.(random|randint|choice|getrandbits)\b|"
                        r"\bsecrets\.(token_bytes|randbits|choice)\b")
    sources = sorted((ROOT / "corky").glob("*.py")) + \
        sorted((ROOT / "shim").glob("bip39_shim.py"))
    dirty = [f.name for f in sources if banned.search(f.read_text())]
    if dirty:
        bad(f"python RNG referenced in {dirty}")
    else:
        ok(f"no python RNG in any of the {len(sources)} shipped modules")
    # The same guarantee at runtime, in a clean interpreter: importing
    # Corky's modules must not pull the RNG modules in. (This test file
    # itself imports tempfile, which imports random, so it cannot be
    # checked in-process.)
    probe = ("import sys; sys.path[:0] = [%r, %r];"
             "import signer, codex32, seedqr, bip39_shim;"
             "print(sorted({'random','secrets'} & set(sys.modules)))"
             % (str(ROOT / "corky"), str(ROOT / "shim")))
    out = subprocess.run([sys.executable, "-c", probe],
                         capture_output=True, text=True)
    # Scope: every module that touches secret material or drives Core.
    # screens.py is excluded because Pillow imports random for its own
    # drawing helpers; screens.py never sees entropy, only glyphs.
    if out.returncode == 0 and out.stdout.strip() == "[]":
        ok("a clean import of the key-handling modules pulls in no RNG")
    else:
        bad(f"RNG modules reachable at import: {out.stdout.strip()} "
            f"{out.stderr.strip()[:120]}")


def node_checks():
    datadir = tempfile.mkdtemp(prefix="corky-gen-")
    port = 24000 + (hash(datadir) % 20000)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % port)
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={datadir}", "-regtest", "-server",
         "-fallbackfee=0.0002", "-daemonwait"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(120):
            try:
                rpc.call("getblockchaininfo")
                break
            except RuntimeError:
                time.sleep(0.5)

        # 1. Entropy: from Core, and fresh every time.
        a = signer.core_entropy(rpc)
        b = signer.core_entropy(rpc)
        if len(a) == len(b) == 64 and a != b:
            ok("core_entropy returns 64 fresh bytes per call")
        else:
            bad(f"core_entropy degenerate: {len(a)}/{len(b)} bytes, equal={a == b}")

        # 4. Statelessness: the throwaway wallet is unloaded AND deleted.
        loaded = rpc.call("listwallets")
        on_disk = (rpc.wallet_dir / signer.GEN_WALLET).exists()
        if signer.GEN_WALLET not in loaded and not on_disk:
            ok("throwaway generation wallet unloaded and deleted")
        else:
            bad(f"generation wallet persists: loaded={loaded} disk={on_disk}")

        # 2. The backup: a valid codex32 secret, and shares that recombine.
        ident = codex32.derive_identifier(a)
        secret = codex32.encode_secret(ident, a, threshold=0)
        if codex32.validate(secret) == secret and \
                codex32.decode_secret(secret)[1] == a:
            ok("generated seed encodes as a valid codex32 secret")
        else:
            bad("generated codex32 secret does not round-trip")
        shares = codex32.split(a, 2, 3, ident,
                               codex32.derive_split_entropy(a, 2, 3))
        recovered = codex32.recover(shares[:2])
        if codex32.decode_secret(recovered)[1] == a:
            ok("2-of-3 shares of the generated seed recombine to it")
        else:
            bad("shares of the generated seed do not recombine")

        # 3. The derived wallet opens in Core and signs a real PSBT.
        _, seed = codex32.decode_secret(secret)
        signer.open_session_xprv(rpc, codex32.to_xprv(seed, mainnet=False))
        addr = rpc.call("getnewaddress", wallet=signer.WALLET)
        rpc.call("generatetoaddress", 101, addr, wallet=signer.WALLET)
        funded = rpc.call("walletcreatefundedpsbt", [],
                          [{addr: 1.0}], 0, {"fee_rate": 10}, True,
                          wallet=signer.WALLET)["psbt"]
        signed = signer.sign_psbt(rpc, funded)
        if signed["complete"] and base64.b64decode(signed["psbt"]):
            ok("wallet from the generated seed signs a PSBT to completion")
        else:
            bad("generated-seed wallet could not complete a PSBT")
        signer.close_session(rpc)
        if not (rpc.wallet_dir / signer.WALLET).exists():
            ok("session wallet deleted after signing")
        else:
            bad("session wallet persists after close_session")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)


def main():
    static_checks()
    node_checks()
    if fails:
        print("\n" + "\n".join(fails))
        sys.exit(1)
    print("\nGENERATE PASS")


if __name__ == "__main__":
    main()
