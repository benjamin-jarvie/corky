"""M4-lite: the real mainnet signing path against a funded burner UTXO.

Coordinator role (this file, online-derived data): builds the funded PSBT
with witness_utxo. Signer role (offline bitcoind): imports the
burner descriptors and signs. Sweeps burner receive[0] -> receive[1] so the
sats stay under the harness for further test rounds. Broadcast is a separate
manual step (prints the signed hex).
"""
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

TXID = "de2b23a1ced68cc80c8b1bf04c609e7fe096987db3b62d15ea3fc0d12fa650d8"
VOUT = 0; AMT = 10000; FEE = 200; SEND = AMT - FEE

def cvarint(n):
    return bytes([n]) if n < 0xfd else b"\xfd" + struct.pack("<H", n)

def main():
    xprv = burner_xprv()
    dd = tempfile.mkdtemp(prefix="m4-")
    daemon = subprocess.Popen(
        ["bitcoind", f"-datadir={dd}", "-networkactive=0", "-listen=0",
         "-server=1", "-dbcache=4", "-maxmempool=5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(dd, chain="main")
    try:
        for _ in range(120):
            try: rpc.call("getblockcount"); break
            except RuntimeError: time.sleep(0.5)

        # signer wallet: import burner BIP84 receive+change
        rpc.call("createwallet", signer.WALLET, False, True, "", False, True)
        def desc(c):
            raw = f"wpkh({xprv}/84h/0h/0h/{c}/*)"
            cs = rpc.call("getdescriptorinfo", raw)["checksum"]
            return f"{raw}#{cs}"
        rpc.call("importdescriptors",
                 [{"desc": desc(c), "active": True, "internal": bool(c),
                   "timestamp": "now", "range": [0, 5]} for c in (0, 1)],
                 wallet=signer.WALLET)

        raw84 = f"wpkh({xprv}/84h/0h/0h/0/*)"
        cs = rpc.call("getdescriptorinfo", raw84)["checksum"]
        src = rpc.call("deriveaddresses", f"{raw84}#{cs}", [0, 0])[0]
        dest = rpc.call("deriveaddresses", f"{raw84}#{cs}", [1, 1])[0]
        src_spk = bytes.fromhex(rpc.call("validateaddress", src)["scriptPubKey"])
        dst_spk = bytes.fromhex(rpc.call("validateaddress", dest)["scriptPubKey"])

        # coordinator: unsigned tx
        tx = struct.pack("<I", 2)
        tx += cvarint(1)
        tx += bytes.fromhex(TXID)[::-1] + struct.pack("<I", VOUT) + b"\x00" + b"\xfd\xff\xff\xff"
        tx += cvarint(1)
        tx += struct.pack("<q", SEND) + cvarint(len(dst_spk)) + dst_spk
        tx += struct.pack("<I", 0)

        # PSBT with witness_utxo on input 0
        wutxo = struct.pack("<q", AMT) + cvarint(len(src_spk)) + src_spk
        psbt = b"\x70\x73\x62\x74\xff"
        psbt += b"\x01\x00" + cvarint(len(tx)) + tx + b"\x00"  # global: key 0x00 = unsigned tx
        psbt += b"\x01\x01" + cvarint(len(wutxo)) + wutxo + b"\x00"  # input0: witness_utxo
        psbt += b"\x00"                                         # output0: empty
        psbt_b64 = base64.b64encode(psbt).decode()

        # signer reviews then signs (Corky's exact path)
        info = signer.describe_psbt(rpc, psbt_b64)
        print(f"REVIEW: out {info['outputs'][0]['address']} "
              f"{info['outputs'][0]['amount_btc']} BTC, fee {info['fee_btc']} BTC, "
              f"in-total {info['input_total_btc']}")
        assert str(info["outputs"][0]["address"]) == dest
        signed = signer.sign_psbt(rpc, psbt_b64)
        assert signed["complete"], "PSBT did not fully sign"
        final = rpc.call("finalizepsbt", signed["psbt"])
        assert final["complete"]
        print("SIGNED_TX_HEX:", final["hex"])
        print("SRC:", src, "-> DEST(receive[1]):", dest, "SEND:", SEND)
        open("/private/tmp/claude-502/-Users-ai-sandbox/34ce17fa-ff17-409e-9d56-ec137a14fc59/scratchpad/signed_sweep.hex", "w").write(final["hex"])
        print("M4-LITE SIGN PASS")
    finally:
        try: rpc.call("stop"); daemon.wait(timeout=30)
        except Exception: daemon.kill()
        shutil.rmtree(dd, ignore_errors=True)

if __name__ == "__main__":
    main()
