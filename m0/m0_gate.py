"""M0 go/no-go gate: does wallet-only bitcoind fit and sign on 512MB?

Run ON THE PI (works on a dev machine too, with reduced measurements):
    python3 m0/m0_gate.py [--inputs 250]

What it does, with the exact production memory flags from m0/bitcoin.conf:
  1. Starts bitcoind on regtest in a temp datadir.
  2. Opens a Corky session (shim -> importdescriptors), timed.
  3. A miner wallet funds Corky with N separate UTXOs.
  4. Corky builds and signs a PSBT spending ALL N inputs (the stress case:
     PSBT size and signing cost scale with input count).
  5. Records peak bitcoind RSS (VmHWM), system MemAvailable, and timings.

PASS condition (from PLAN.md): stress PSBT signs, and on the Pi
MemAvailable never drops below 100MB.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"
FLAGS = ["-regtest", "-dbcache=4", "-maxmempool=5", "-rpcthreads=1",
         "-networkactive=0", "-listen=0", "-server=1",
         "-fallbackfee=0.0001", "-debuglogfile=0"]


def vm_hwm_mb(pid):
    status = Path(f"/proc/{pid}/status")
    if not status.exists():  # dev machine (macOS): current RSS via ps instead
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
        return int(out) // 1024 if out else None
    for line in status.read_text().splitlines():
        if line.startswith("VmHWM"):
            return int(line.split()[1]) // 1024
    return None


def mem_available_mb():
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) // 1024
    return None


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--inputs", type=int, default=250)
    n = args.parse_args().inputs

    datadir = tempfile.mkdtemp(prefix="corky-m0-")
    t0 = time.time()
    daemon = subprocess.Popen(["bitcoind", f"-datadir={datadir}", *FLAGS],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    report = {}
    low_water = None
    try:
        for _ in range(240):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)
        report["bitcoind start (s)"] = round(time.time() - t0, 1)

        t = time.time()
        signer.open_session(rpc, MNEMONIC)
        report["session open: shim + importdescriptors (s)"] = round(time.time() - t, 1)

        # Miner funds Corky with n UTXOs, batched to keep this quick.
        rpc.call("createwallet", "miner")
        mine_addr = rpc.call("getnewaddress", wallet="miner")
        rpc.call("generatetoaddress", 120, mine_addr)
        corky_addrs = [rpc.call("getnewaddress", wallet=signer.WALLET)
                       for _ in range(min(n, 200))]
        sent = 0
        while sent < n:
            batch = {corky_addrs[(sent + i) % len(corky_addrs)]: 0.01
                     for i in range(min(100, n - sent))}
            rpc.call("send", batch, wallet="miner")
            sent += len(batch)
            rpc.call("generatetoaddress", 1, mine_addr)
        utxos = len(rpc.call("listunspent", wallet=signer.WALLET))
        report["corky utxos funded"] = utxos
        low_water = mem_available_mb()

        # The stress PSBT: spend everything (all inputs, one output).
        t = time.time()
        dest = rpc.call("getnewaddress", wallet="miner")
        inputs = [{"txid": u["txid"], "vout": u["vout"]}
                  for u in rpc.call("listunspent", wallet=signer.WALLET)]
        total = sum(float(u["amount"]) for u in
                    rpc.call("listunspent", wallet=signer.WALLET))
        funded = rpc.call("walletcreatefundedpsbt", inputs,
                          [{dest: round(total - 0.05, 8)}], 0,
                          {"fee_rate": 5}, True, wallet=signer.WALLET)
        report["stress psbt inputs"] = len(inputs)
        review = signer.describe_psbt(rpc, funded["psbt"])
        signed = signer.sign_psbt(rpc, funded["psbt"])
        assert signed["complete"], "stress PSBT did not fully sign"
        report["build+review+sign stress PSBT (s)"] = round(time.time() - t, 1)
        report["fee shown (rBTC)"] = review["fee_btc"]
        report["peak bitcoind RSS (MB)"] = vm_hwm_mb(daemon.pid)
        mem_now = mem_available_mb()
        report["MemAvailable low-water (MB)"] = (
            min(x for x in (low_water, mem_now) if x is not None)
            if (low_water or mem_now) else "n/a (not Linux)")

        print("\nM0 GATE REPORT")
        for k, v in report.items():
            print(f"  {k}: {v}")
        rss = report["peak bitcoind RSS (MB)"]
        mem = report["MemAvailable low-water (MB)"]
        if isinstance(mem, int):
            verdict = "PASS" if mem >= 100 else "FAIL"
            print(f"\nM0 {verdict}: headroom {mem}MB (need >=100MB)")
        else:
            print(f"\nM0 (dev run): signing works; RSS now ~{rss}MB. "
                  "Run on the Pi for the real verdict.")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=60)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)


if __name__ == "__main__":
    main()
