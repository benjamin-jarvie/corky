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
import threading
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


def swap_active_mb():
    """Active swap in MB. Under swap, peak RSS reads low and MemAvailable
    reads high, so no verdict is possible (ticket 01,
    docs/wayfinder/zero2w-m0-fixes)."""
    swaps = Path("/proc/swaps")
    if not swaps.exists():
        return 0  # not Linux: dev run, no verdict either way
    total = 0
    for line in swaps.read_text().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            total += int(parts[2])  # size column is KB
    # Ceiling division: 1KB of active swap must still trip the guard.
    return (total + 1023) // 1024


def _watch_low_water(stop, box):
    """Sample MemAvailable every 200ms: the true low point falls between
    RPC calls, so two spot samples are not enough (ticket 02)."""
    while not stop.wait(0.2):
        m = mem_available_mb()
        if m is not None and (box[0] is None or m < box[0]):
            box[0] = m


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--inputs", type=int, default=250)
    n = args.parse_args().inputs

    swap = swap_active_mb()
    if swap:
        print(f"M0 INVALID: {swap}MB of swap is active. Swap makes RSS read"
              " low and MemAvailable read high; no verdict is possible.")
        print("Fix: sudo swapoff -a   (reverts at reboot), then re-run.")
        sys.exit(2)

    stop_sampler = threading.Event()
    low_box = [None]  # MemAvailable floor at 200ms resolution
    threading.Thread(target=_watch_low_water,
                     args=(stop_sampler, low_box), daemon=True).start()

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
        floors = (low_box[0], low_water, mem_now)
        report["MemAvailable low-water (MB)"] = (
            min(x for x in floors if x is not None)
            if any(x is not None for x in floors) else "n/a (not Linux)")

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
        stop_sampler.set()
        try:
            rpc.call("stop")
            daemon.wait(timeout=60)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)


if __name__ == "__main__":
    main()
