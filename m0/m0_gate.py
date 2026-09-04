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
    """Peak RSS in MB. pid may be "self" for this process."""
    status = Path(f"/proc/{pid}/status")
    if not status.exists():  # dev machine (macOS): current RSS via ps instead
        import os
        real = os.getpid() if pid == "self" else pid
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(real)],
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


def soc_temp_c():
    """SoC temperature in C, or None off a Pi. ORDER.md's cooling decision
    drops the heatsink, so the gate has to show what the SoC reaches."""
    zone = Path("/sys/class/thermal/thermal_zone0/temp")
    if not zone.exists():
        return None
    try:
        return int(zone.read_text().strip()) / 1000.0
    except ValueError:
        return None


THROTTLE_BITS = {0: "under-voltage NOW", 1: "arm frequency capped NOW",
                 2: "throttled NOW", 3: "soft temp limit NOW",
                 16: "under-voltage since boot", 17: "arm freq capped since boot",
                 18: "throttled since boot", 19: "soft temp limit since boot"}


def throttled():
    """(raw, [reasons]) from vcgencmd, or (None, []) where it is absent.
    A weak micro-USB supply shows up here and nowhere else in the report."""
    vc = shutil.which("vcgencmd")
    if vc is None:
        return None, []
    out = subprocess.run([vc, "get_throttled"], capture_output=True,
                         text=True).stdout.strip()
    if "=" not in out:
        return None, []
    raw = out.split("=", 1)[1]
    try:
        bits = int(raw, 16)
    except ValueError:
        return raw, []
    return raw, [name for bit, name in THROTTLE_BITS.items() if bits & (1 << bit)]


def _sample(stop, track):
    """Sample MemAvailable and SoC temperature every 200ms: the true low
    point falls between RPC calls, so two spot samples are not enough
    (ticket 02). Temperature peaks between calls the same way."""
    while not stop.wait(0.2):
        m = mem_available_mb()
        if m is not None and (track["mem"] is None or m < track["mem"]):
            track["mem"] = m
        t = soc_temp_c()
        if t is not None and (track["temp"] is None or t > track["temp"]):
            track["temp"] = t


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--inputs", type=int, default=250)
    n = args.parse_args().inputs

    swap = swap_active_mb()
    if swap:
        print(f"M0 INVALID: {swap}MB of swap is active. Swap makes RSS read"
              " low and MemAvailable read high; no verdict is possible.")
        # swapoff -a alone is not enough on Trixie. systemd-zram-generator
        # owns dev-zram0.swap, swap.target wants it, so systemd re-activates
        # the unit seconds after the device goes away. Stop the unit, and do
        # it in the same shell as the run so nothing can race it.
        print("Fix, in one session (both revert at reboot):")
        print("  sudo systemctl stop dev-zram0.swap   # Trixie: zram, or it")
        print("                                       # comes straight back")
        print("  sudo swapoff -a                      # any disk swap left")
        sys.exit(2)

    stop_sampler = threading.Event()
    track = {"mem": None, "temp": None}  # floor and peak at 200ms resolution
    threading.Thread(target=_sample,
                     args=(stop_sampler, track), daemon=True).start()

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
        # subtractFeeFromOutputs keeps this a single output with no change,
        # which is the shape the stress case wants. A hard-coded fee reserve
        # was wrong at both ends: 60x the real fee at 250 inputs, and larger
        # than the whole funded amount below about 10 inputs, where it failed
        # with "Transaction amount too small".
        funded = rpc.call("walletcreatefundedpsbt", inputs,
                          [{dest: round(total, 8)}], 0,
                          {"fee_rate": 5, "subtractFeeFromOutputs": [0]},
                          True, wallet=signer.WALLET)
        report["stress psbt inputs"] = len(inputs)
        review = signer.describe_psbt(rpc, funded["psbt"])
        signed = signer.sign_psbt(rpc, funded["psbt"])
        assert signed["complete"], "stress PSBT did not fully sign"
        report["build+review+sign stress PSBT (s)"] = round(time.time() - t, 1)
        report["fee shown (rBTC)"] = review["fee_btc"]
        report["stress psbt size (KB)"] = len(funded["psbt"]) // 1024
        report["peak bitcoind RSS (MB)"] = vm_hwm_mb(daemon.pid)
        # The gate's own process is part of the device's budget too: on the
        # real device this is corky/main.py, holding the same PSBT string and
        # the same decodepsbt JSON. Reporting only the daemon hid 45MB of the
        # loss between 180 and 210 inputs.
        report["peak gate process RSS (MB)"] = vm_hwm_mb("self")
        mem_now = mem_available_mb()
        floors = (track["mem"], low_water, mem_now)
        report["MemAvailable low-water (MB)"] = (
            min(x for x in floors if x is not None)
            if any(x is not None for x in floors) else "n/a (not Linux)")
        if track["temp"] is not None:
            report["peak SoC temperature (C)"] = round(track["temp"], 1)
        raw, reasons = throttled()
        if raw is not None:
            report["vcgencmd get_throttled"] = raw

        print("\nM0 GATE REPORT")
        for k, v in report.items():
            print(f"  {k}: {v}")
        rss = report["peak bitcoind RSS (MB)"]
        mem = report["MemAvailable low-water (MB)"]
        for reason in reasons:
            # Not a fail: the pass line is memory (PLAN.md), and ORDER.md
            # rules that throttling costs sign time and nothing else.
            # Under-voltage is still worth shouting about, because a weak
            # supply can spoil every other number above.
            print(f"  !! {reason}")
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
