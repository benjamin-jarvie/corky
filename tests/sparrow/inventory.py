"""What Sparrow actually puts in an exported PSBT, and what survives Corky.

Core does the parsing, via decodepsbt. An earlier version of this file walked
the PSBT key-value maps by hand, which is exactly what PLAN A-11 forbids and
was unnecessary two lines from an RPC that already does it.

Run: python3 inventory.py
"""
import sys
from decimal import Decimal

import harness
from harness import Java, Regtest

# decodepsbt's field names, in the order worth reading them
INPUT_FIELDS = ["non_witness_utxo", "witness_utxo", "sighash",
                "bip32_derivs", "taproot_bip32_derivs", "taproot_internal_key",
                "partial_signatures", "taproot_key_path_sig",
                "final_scriptSig", "final_scriptwitness"]
OUTPUT_FIELDS = ["redeem_script", "witness_script", "bip32_derivs",
                 "taproot_internal_key", "taproot_bip32_derivs"]


def present(section, fields):
    """Which fields the PSBT carries, by presence and not by truthiness.

    decodepsbt reports taproot's SIGHASH_DEFAULT as an empty string, so a
    truthiness test silently hides a field that is set. Show the value for
    sighash, because SIGHASH_DEFAULT and ALL are the interesting difference.
    """
    out = []
    for f in fields:
        if f not in section:
            continue
        if f == "sighash":
            out.append(f"sighash={section[f] or 'DEFAULT'}")
        else:
            out.append(f)
    return ", ".join(out) or "(empty)"


def report(rpc, label, psbt):
    d = rpc.call("decodepsbt", psbt)
    print(f"  {label}")
    print("    global :", "UNSIGNED_TX"
          + (", GLOBAL_XPUB" if d.get("global_xpubs") else ""))
    print("    input  :", present(d["inputs"][0], INPUT_FIELDS))
    for n, out in enumerate(d["outputs"]):
        print(f"    output{n}:", present(out, OUTPUT_FIELDS))
    return d


def main():
    java = Java()
    with Regtest() as net:
        for script_type, _ in harness.SCRIPT_TYPES:
            fp, path, xpub = net.account(script_type)
            addr = java("SparrowGen", "addresses", "REGTEST", script_type,
                        xpub, fp, path, 1, "RECEIVE")[0].split("\t")[1]
            txid, vout, raw = net.fund(addr)
            net.mine()
            java.chain_height = net.height()
            dest = net.new_address()

            print(f"\n=== {script_type} ===")
            psbt = java("SparrowGen", "psbt", "REGTEST", script_type, xpub, fp,
                        path, 2.0, f"p={dest},500000,false",
                        f"u=RECEIVE,0,{txid},{vout},1000000,{java.chain_height},{raw}")[0]

            d = report(net.rpc, "Sparrow export (what crosses the air gap):", psbt)
            print("    tx nLockTime:", d["tx"]["locktime"],
                  " nSequence:", [hex(v["sequence"]) for v in d["tx"]["vin"]],
                  " tip:", java.chain_height)

            signed = harness.signer.sign_psbt(net.rpc, psbt)
            report(net.rpc, "after Corky signs:", signed["psbt"])
            final = net.rpc.call("finalizepsbt", signed["psbt"])
            ftx = net.rpc.call("decoderawtransaction", final["hex"])
            print("    final nLockTime:", ftx["locktime"],
                  " nSequence:", [hex(v["sequence"]) for v in ftx["vin"]])
            net.rpc.call("sendrawtransaction", final["hex"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
