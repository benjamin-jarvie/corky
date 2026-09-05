"""M4-lite Taproot: prove a real BIP340 Schnorr keyspend signature is
accepted by mainnet consensus. Two chained txs from the same burner seed:
  A: receive[1] (P2WPKH, ECDSA) -> receive[0] BIP86 (P2TR)   [funds taproot]
  B: that P2TR utxo            -> receive[2] (P2WPKH)         [Schnorr spend]
Tx B is the new coverage: taproot key-path signing on real funds.
Broadcast is a separate manual step (prints both signed hexes)."""
import base64
import shutil
import struct
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, "corky")
import signer

# The burner key, as an xprv. A-22 left this branch with no BIP39, so the
# key arrives in the form Core itself understands. Pass the file holding it
# as argv[1], or set CORKY_BURNER_XPRV. It was a mnemonic in the original
# 2026-08-19 run; the recorded result (tx 19d1180b, block 963255) stands.
def burner_xprv():
    import os
    if len(sys.argv) > 1:
        return open(sys.argv[1]).read().strip()
    key = os.environ.get("CORKY_BURNER_XPRV", "").strip()
    if not key:
        sys.exit("give the burner xprv: a file as argv[1], or "
                 "CORKY_BURNER_XPRV in the environment")
    return key

# funding UTXO = receive[1] P2WPKH, 9800 sats
FUND_TXID = "19d1180b816e00c1d272a25bda3caf1dc466b70c24ba128aee25e1a32b61cf41"
FUND_VOUT = 0; FUND_AMT = 9800

def cvi(n): return bytes([n]) if n < 0xfd else b"\xfd" + struct.pack("<H", n)

def build_psbt(txid, vout, in_amt, in_spk, out_amt, out_spk):
    tx = struct.pack("<I", 2) + cvi(1)
    tx += bytes.fromhex(txid)[::-1] + struct.pack("<I", vout) + b"\x00" + b"\xfd\xff\xff\xff"
    tx += cvi(1) + struct.pack("<q", out_amt) + cvi(len(out_spk)) + out_spk
    tx += struct.pack("<I", 0)
    wutxo = struct.pack("<q", in_amt) + cvi(len(in_spk)) + in_spk
    psbt = b"\x70\x73\x62\x74\xff"
    psbt += b"\x01\x00" + cvi(len(tx)) + tx + b"\x00"
    psbt += b"\x01\x01" + cvi(len(wutxo)) + wutxo + b"\x00"
    psbt += b"\x00"
    return base64.b64encode(psbt).decode()

def txid_of(rawhex):
    # segwit txid = double-sha of the non-witness serialization; simplest:
    # ask no one — compute via bitcoind decoderawtransaction later. Here we
    # return None and rely on the daemon.
    return None

def main():
    xprv = burner_xprv()
    dd = tempfile.mkdtemp(prefix="m4tr-")
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={dd}", "-networkactive=0", "-listen=0",
         "-server=1", "-dbcache=4", "-maxmempool=5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(dd, chain="main")
    try:
        for _ in range(120):
            try: rpc.call("getblockcount"); break
            except RuntimeError: time.sleep(0.5)
        rpc.call("createwallet", signer.WALLET, False, True, "", False, True)
        def d84(c):
            raw = f"wpkh({xprv}/84h/0h/0h/{c}/*)"; cs = rpc.call("getdescriptorinfo", raw)["checksum"]; return f"{raw}#{cs}"
        def d86(c):
            raw = f"tr({xprv}/86h/0h/0h/{c}/*)"; cs = rpc.call("getdescriptorinfo", raw)["checksum"]; return f"{raw}#{cs}"
        rpc.call("importdescriptors",
                 [{"desc": d84(c), "active": True, "internal": bool(c), "timestamp": "now", "range": [0, 5]} for c in (0, 1)]
                 + [{"desc": d86(c), "active": False, "internal": bool(c), "timestamp": "now", "range": [0, 5]} for c in (0, 1)],
                 wallet=signer.WALLET)

        def addr(desc, i):
            return rpc.call("deriveaddresses", desc, [i, i])[0]
        def spk(a): return bytes.fromhex(rpc.call("validateaddress", a)["scriptPubKey"])
        r1 = addr(d84(0), 1)                       # funding source (P2WPKH)
        taproot = addr(d86(0), 0)                  # P2TR receive[0]
        r2 = addr(d84(0), 2)                       # final P2WPKH sink

        # ---- TX A: P2WPKH -> P2TR (fund taproot) ----
        feeA = 110; outA = FUND_AMT - feeA
        psbtA = build_psbt(FUND_TXID, FUND_VOUT, FUND_AMT, spk(r1), outA, spk(taproot))
        infoA = signer.describe_psbt(rpc, psbtA)
        assert str(infoA["outputs"][0]["address"]) == taproot
        sA = signer.sign_psbt(rpc, psbtA); assert sA["complete"], "A unsigned"
        finA = rpc.call("finalizepsbt", sA["psbt"]); assert finA["complete"]
        hexA = finA["hex"]
        txidA = rpc.call("decoderawtransaction", hexA)["txid"]
        print("TX_A (fund taproot) txid:", txidA, "-> P2TR", taproot, "amt", outA)

        # ---- TX B: P2TR -> P2WPKH (Schnorr keyspend) ----
        feeB = 110; outB = outA - feeB
        psbtB = build_psbt(txidA, 0, outA, spk(taproot), outB, spk(r2))
        infoB = signer.describe_psbt(rpc, psbtB)
        assert str(infoB["outputs"][0]["address"]) == r2
        sB = signer.sign_psbt(rpc, psbtB); assert sB["complete"], "B unsigned (taproot keyspend failed)"
        finB = rpc.call("finalizepsbt", sB["psbt"]); assert finB["complete"]
        hexB = finB["hex"]
        decB = rpc.call("decoderawtransaction", hexB)
        wit = decB["vin"][0]["txinwitness"]
        assert len(wit) == 1 and len(wit[0]) in (128, 130), f"not a single Schnorr sig: {wit}"
        print("TX_B (taproot Schnorr keyspend) txid:", decB["txid"], "witness:", len(wit), "item,", len(wit[0])//2, "byte sig")
        open("/private/tmp/claude-502/-Users-ai-sandbox/34ce17fa-ff17-409e-9d56-ec137a14fc59/scratchpad/taproot_A.hex", "w").write(hexA)
        open("/private/tmp/claude-502/-Users-ai-sandbox/34ce17fa-ff17-409e-9d56-ec137a14fc59/scratchpad/taproot_B.hex", "w").write(hexB)
        print("M4-LITE TAPROOT SIGN PASS (A funds P2TR, B is a real Schnorr keyspend)")
    finally:
        try: rpc.call("stop"); daemon.wait(timeout=30)
        except Exception: daemon.kill()
        shutil.rmtree(dd, ignore_errors=True)

if __name__ == "__main__":
    main()
