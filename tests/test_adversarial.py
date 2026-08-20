"""Adversarial signing suite for Corky. Regtest only, no real funds.

Each block states an ATTACK, the expected SAFE behavior, and asserts it.
House style: ok-lines on success, sys.exit(1) on any failure.

The threat model: a malicious or buggy coordinator (Sparrow, or an
impostor) controls every byte that crosses the air gap. Corky must never
sign what it does not own, never hide a change of outputs behind a review
screen, and never hang or crash on hostile input. Bitcoin Core is the only
PSBT parser and the only signer; these tests prove Corky's plumbing around
Core stays safe when the input is an attack.

Run: python3 tests/test_adversarial.py
"""

import inspect
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
sys.path.insert(0, str(ROOT / "shim"))

import codex32  # noqa: E402
import filechannel  # noqa: E402
import qrchannel  # noqa: E402
import signer  # noqa: E402
import bip39_shim  # noqa: E402

MNEMONIC = "abandon " * 11 + "about"
WATCH = "watcher"
FAILURES = []


def ok(msg):
    print(f"ok   {msg}")


def fail(msg):
    FAILURES.append(msg)
    print(f"FAIL {msg}")


def expect_raises(name, excs, fn, *args, **kwargs):
    """Assert fn raises one of excs (a controlled error), never hangs/returns."""
    try:
        fn(*args, **kwargs)
    except excs as exc:
        ok(f"{name}: raised {type(exc).__name__}")
        return
    except Exception as exc:  # noqa: BLE001
        fail(f"{name}: raised UNCONTROLLED {type(exc).__name__}: {exc}")
        return
    fail(f"{name}: returned/accepted, expected {excs}")


# ======================================================================
#  Regtest harness (single bitcoind for the whole suite)
# ======================================================================

def setup_regtest(rpc):
    """Corky session + coordinator watch wallet funded with real coins."""
    signer.open_session(rpc, MNEMONIC)
    pubs = signer.public_descriptors(rpc)
    rpc.call("createwallet", WATCH, True, True, "", False, True)
    imports = [{"desc": d, "active": True, "timestamp": "now",
                "range": [0, 200], "internal": "/1/*" in d} for d in pubs]
    rpc.call("importdescriptors", imports, wallet=WATCH)
    addr = rpc.call("getnewaddress", wallet=WATCH)
    rpc.call("generatetoaddress", 101, addr)
    return addr


def funded_psbt(rpc, amount=1.5):
    dest = rpc.call("getnewaddress", wallet=WATCH)
    funded = rpc.call("walletcreatefundedpsbt", [], [{dest: amount}], 0,
                      {"fee_rate": 10}, True, wallet=WATCH)
    return funded["psbt"], dest


# ======================================================================
#  ATTACK 1 — FALSE FEE via a lying witness_utxo amount
# ======================================================================
#
#  Attack: the coordinator inflates the witness_utxo amount inside the
#  PSBT. An air-gapped signer cannot check that amount against the chain.
#  Expected safe behavior: describe_psbt reports EXACTLY the fee Core
#  derives from the supplied (lying) amount. Corky invents no number of
#  its own; it faithfully surfaces Core's computation and the review
#  screen carries fee_note saying the amount is coordinator-supplied.
#  This is the DOCUMENTED coordinator-trust limit of any air-gapped
#  signer (describe_psbt docstring, README). The compensating control is
#  ATTACK 2: the signature commits to the real outputs, so a lie about
#  value cannot redirect coins.

def attack_false_fee(rpc):
    psbt, _ = funded_psbt(rpc)
    decoded = signer.describe_psbt(rpc, psbt)
    true_fee = decoded["fee_btc"]

    raw = _b64decode(psbt)
    decoded_tx = rpc.call("decodepsbt", psbt)
    wu = decoded_tx["inputs"][0]["witness_utxo"]

    # Core computes the fee from non_witness_utxo when present, ignoring any
    # witness_utxo lie. Strip the prevtx record (input key 0x00) so only the
    # witness_utxo remains, which is exactly what an air-gapped coordinator
    # would hand a segwit-only signer.
    raw = _drop_non_witness_utxo(raw)
    true_sat = int((Decimal(str(wu["amount"])) * 100_000_000).to_integral_value())
    lie_sat = true_sat * 2  # inflate the input by 100%
    # A witness_utxo serializes as amount(8 LE) + compactsize(scriptlen) +
    # scriptPubKey. Pin the match with the script bytes so we patch exactly
    # the input value and nothing that merely shares the 8-byte pattern.
    spk = bytes.fromhex(wu["scriptPubKey"]["hex"])
    txout = struct.pack("<Q", true_sat) + bytes([len(spk)]) + spk
    lie_txout = struct.pack("<Q", lie_sat) + bytes([len(spk)]) + spk
    # Target ONLY the witness_utxo record (PSBT input key 0x01), not the
    # non_witness_utxo copy of the prevout (key 0x00): patching the prevtx
    # would change its hash and Core would reject the outpoint. The record is
    # <keylen=01><keytype=01><valuelen><txout>.
    marker = b"\x01\x01" + bytes([len(txout)])
    needle = marker + txout
    if raw.count(needle) != 1:
        fail(f"attack1: witness_utxo record not uniquely located "
             f"({raw.count(needle)} matches)")
        return
    patched = _b64encode(raw.replace(needle, marker + lie_txout))

    shown = signer.describe_psbt(rpc, patched)["fee_btc"]
    core_fee = rpc.call("decodepsbt", patched)["fee"]
    # The device SHOWS Core's number for the lying input, nothing invented.
    if Decimal(str(shown)) != Decimal(str(core_fee)):
        fail(f"attack1: shown fee {shown} != Core fee {core_fee}")
        return
    # And that number moved because the coordinator lied: proof the fee is
    # coordinator-trusted, exactly as documented.
    if Decimal(str(shown)) <= Decimal(str(true_fee)):
        fail("attack1: lie did not change the shown fee; patch ineffective")
        return
    note = signer.describe_psbt(rpc, patched)["fee_note"]
    assert "coordinator-supplied" in note, "review screen omits the trust caveat"
    ok(f"attack1 false-fee: device shows Core's fee {shown} for the lying "
       f"input (true {true_fee}); documented coordinator-trust limit, "
       "output commitment (attack2) is the real defense")


def _read_compactsize(buf, i):
    b = buf[i]
    if b < 0xFD:
        return b, i + 1
    if b == 0xFD:
        return struct.unpack_from("<H", buf, i + 1)[0], i + 3
    if b == 0xFE:
        return struct.unpack_from("<I", buf, i + 1)[0], i + 5
    return struct.unpack_from("<Q", buf, i + 1)[0], i + 9


def _drop_non_witness_utxo(raw):
    """Remove the non_witness_utxo (keytype 0x00) record from the first PSBT
    input map, walking the container structurally. Leaves witness_utxo in
    place so Core must derive the fee from the (patchable) witness amount."""
    assert raw[:5] == b"psbt\xff", "not a PSBT"
    i = 5
    # Skip the global map: records until a 0x00 separator.
    while raw[i] != 0x00:
        klen, i = _read_compactsize(raw, i)
        i += klen
        vlen, i = _read_compactsize(raw, i)
        i += vlen
    i += 1  # global separator
    # First input map: copy records, dropping keytype 0x00.
    out = bytearray(raw[:i])
    while raw[i] != 0x00:
        start = i
        klen, j = _read_compactsize(raw, i)
        keytype = raw[j]
        j += klen
        vlen, j = _read_compactsize(raw, j)
        j += vlen
        if keytype != 0x00:  # keep everything except non_witness_utxo
            out += raw[start:j]
        i = j
    out += raw[i:]  # separator + remaining input/output maps unchanged
    return bytes(out)


def _b64decode(s):
    import base64
    return base64.b64decode(s)


def _b64encode(b):
    import base64
    return base64.b64encode(b).decode("ascii")


# ======================================================================
#  ATTACK 2 — OUTPUT SUBSTITUTION AFTER REVIEW
# ======================================================================
#
#  Attack: Corky reviews and signs a PSBT paying address D. The
#  coordinator then swaps output D for attacker address D' in the final
#  transaction. Expected safe behavior: the signature covers the outputs
#  (SIGHASH_ALL), so the tampered transaction fails validation. Core's
#  testmempoolaccept rejects it. Post-review tampering is fatal.

def attack_output_substitution(rpc):
    psbt, _ = funded_psbt(rpc)
    signed = signer.sign_psbt(rpc, psbt)
    assert signed["complete"], "attack2 setup: Corky did not fully sign"
    final_hex = rpc.call("finalizepsbt", signed["psbt"])["hex"]

    # Baseline: the untampered signed tx is accepted.
    res_ok = rpc.call("testmempoolaccept", [final_hex])
    assert res_ok[0]["allowed"], "attack2 baseline: honest tx rejected"

    # Tamper: rewrite a destination scriptPubKey to the attacker's address.
    # The witness (signature) bytes are left untouched, so the sighash no
    # longer matches the outputs. That is what testmempoolaccept must catch.
    evil_addr = rpc.call("getnewaddress", wallet=WATCH)
    evil_spk = rpc.call("getaddressinfo", evil_addr, wallet=WATCH)["scriptPubKey"]
    tampered = _swap_first_output(final_hex, evil_spk)
    res_bad = rpc.call("testmempoolaccept", [tampered])
    if res_bad[0]["allowed"]:
        fail("attack2: Core ACCEPTED a tx with a substituted output "
             "(signature did not cover outputs!)")
        return
    reason = res_bad[0].get("reject-reason", "")
    ok(f"attack2 output-substitution: tampered tx rejected "
       f"(reject-reason: {reason}); SIGHASH_ALL covers outputs")


def _swap_first_output(raw_hex, new_spk_hex):
    """Substitute the first P2WPKH output's scriptPubKey in a serialized tx.

    A signed segwit tx carries each scriptPubKey verbatim in the output
    section (0014 + 20-byte hash for P2WPKH). We replace one hash with the
    attacker's. The witness bytes are untouched, so the signature is now
    stale for the changed outputs.
    """
    assert new_spk_hex.startswith("0014"), "expected a P2WPKH destination"
    idx = raw_hex.find("0014")
    assert idx != -1, "no P2WPKH output found to substitute"
    return raw_hex[:idx] + new_spk_hex + raw_hex[idx + len(new_spk_hex):]


# ======================================================================
#  ATTACK 3 — MALFORMED PSBTs to describe/sign and to the channels
# ======================================================================
#
#  Attack: feed garbage where a PSBT is expected. Expected safe behavior:
#  every path raises a CONTROLLED error (RuntimeError from Core-backed
#  signer calls, FileChannelError, QrChannelError). Nothing hangs, nothing
#  gets signed.

def attack_malformed(rpc):
    import base64
    good, _ = funded_psbt(rpc)

    # -- describe_psbt / sign_psbt: Core is the parser, errors are RuntimeError
    truncated = good[: len(good) // 2]
    wrong_magic = _b64encode(b"xxxx" + _b64decode(good)[4:])
    b64_garbage = base64.b64encode(os.urandom(64)).decode()
    for name, bad in [("empty", ""), ("truncated-b64", truncated),
                      ("wrong-magic", wrong_magic),
                      ("valid-b64-garbage", b64_garbage)]:
        expect_raises(f"attack3 describe {name}", RuntimeError,
                      signer.describe_psbt, rpc, bad)
        expect_raises(f"attack3 sign {name}", RuntimeError,
                      signer.sign_psbt, rpc, bad)

    # -- filechannel: size guard rejects empty and oversized before parsing
    tmp = Path(tempfile.mkdtemp(prefix="corky-adv-"))
    try:
        empty = tmp / "empty.psbt"
        empty.write_bytes(b"")
        expect_raises("attack3 filechannel empty", filechannel.FileChannelError,
                      filechannel.read_psbt, empty)
        big = tmp / "big.psbt"
        big.write_bytes(b"\x00" * (filechannel.MAX_PSBT_BYTES + 1))
        expect_raises("attack3 filechannel oversized",
                      filechannel.FileChannelError, filechannel.read_psbt, big)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # -- qrchannel: hostile UR frames
    a = qrchannel.FrameAssembler()
    expect_raises("attack3 qr bad-charset", qrchannel.QrChannelError,
                  a.feed, "ur:crypto-psbt/1-1/lpaa$$$###notbech32")
    expect_raises("attack3 qr not-a-frame", qrchannel.QrChannelError,
                  qrchannel.FrameAssembler().feed, "hello world not a ur frame")
    expect_raises("attack3 qr oversized-frame", qrchannel.QrChannelError,
                  qrchannel.FrameAssembler().feed,
                  "ur:crypto-psbt/" + "a" * (qrchannel.MAX_FRAME_CHARS + 1))


# ======================================================================
#  ATTACK 4 — UNOWNED INPUT
# ======================================================================
#
#  Attack: ask Corky to sign a PSBT spending a UTXO for which the Corky
#  wallet holds no descriptor. Expected safe behavior: walletprocesspsbt
#  returns complete=False. Corky signs only what it owns and surfaces the
#  incomplete result rather than pretending it is broadcastable.

def attack_unowned_input(rpc):
    # A normal wallet WITH its own private keys, unrelated to Corky.
    rpc.call("createwallet", "stranger", False, False, "", False, True)
    saddr = rpc.call("getnewaddress", wallet="stranger")
    rpc.call("generatetoaddress", 101, saddr)
    dest = rpc.call("getnewaddress", wallet=WATCH)
    funded = rpc.call("walletcreatefundedpsbt", [], [{dest: 1.0}], 0,
                      {"fee_rate": 10}, True, wallet="stranger")
    result = signer.sign_psbt(rpc, funded["psbt"])
    if result["complete"]:
        fail("attack4: Corky signed a PSBT it does not own (complete=True)")
        return
    ok("attack4 unowned-input: walletprocesspsbt complete=False; Corky "
       "does not sign what it cannot, incomplete result surfaced")


# ======================================================================
#  ATTACK 5 — SIGHASH flag must be SIGHASH_ALL (0x01)
# ======================================================================
#
#  Attack / concern: a nonstandard sighash (NONE/SINGLE/ANYONECANPAY)
#  would let a coordinator strip Corky's commitment to the outputs.
#  Expected safe behavior: Corky never passes a sighash override to
#  walletprocesspsbt (verified by reading signer.sign_psbt), so Core uses
#  the default SIGHASH_ALL and every signature ends in the 0x01 byte.

def attack_sighash(rpc):
    src = inspect.getsource(signer.sign_psbt)
    assert "walletprocesspsbt" in src, "attack5: signer changed shape"
    lowered = src.lower()
    if "sighash" in lowered:
        fail("attack5: signer.sign_psbt mentions sighash; verify no override")
        return
    ok("attack5 source: sign_psbt passes no sighash override to Core")

    psbt, _ = funded_psbt(rpc)
    signed = signer.sign_psbt(rpc, psbt)
    final_hex = rpc.call("finalizepsbt", signed["psbt"])["hex"]
    tx = rpc.call("decoderawtransaction", final_hex)
    wit = tx["vin"][0]["txinwitness"]
    sig = wit[0]  # <signature> <pubkey> for P2WPKH
    if not sig.endswith("01"):
        fail(f"attack5: signature sighash byte is 0x{sig[-2:]}, not 0x01")
        return
    ok(f"attack5 sighash byte: signature ends 0x01 (SIGHASH_ALL)")


# ======================================================================
#  ATTACK 6 — DUPLICATE / REPLAY
# ======================================================================
#
#  Attack: describe and sign the same PSBT twice. Expected safe behavior:
#  idempotent. Core signs with RFC6979 deterministic nonces, so the two
#  signatures are identical and no session state is corrupted.

def attack_replay(rpc):
    psbt, _ = funded_psbt(rpc)
    d1 = signer.describe_psbt(rpc, psbt)
    d2 = signer.describe_psbt(rpc, psbt)
    if d1 != d2:
        fail("attack6: describe_psbt not idempotent")
        return
    s1 = signer.sign_psbt(rpc, psbt)
    s2 = signer.sign_psbt(rpc, psbt)
    if s1 != s2:
        fail("attack6: repeated sign produced a different result")
        return
    assert s1["complete"], "attack6: sign incomplete"
    ok("attack6 replay: describe and sign are deterministic and repeatable, "
       "no state corruption")


# ======================================================================
#  ATTACK 7 — codex32 adversarial share sets
# ======================================================================
#
#  Attack: hand recover()/validate() defective shares. Expected safe
#  behavior: each defect RAISES Codex32Error. The module detects errors;
#  it never returns a wrong seed.

def attack_codex32():
    seed = bytes(range(16))
    ent = os.urandom(64)
    set_test_k2 = codex32.split(seed, 2, 3, "test", ent)
    set_cash_k2 = codex32.split(seed, 2, 3, "cash", ent)
    set_test_k3 = codex32.split(seed, 3, 4, "test", ent)

    # sanity: an honest k-of-n recovers the real secret
    honest = codex32.recover(set_test_k3[:3])
    assert codex32.decode_secret(honest)[1] == seed, "codex32: honest recover broke"
    ok("attack7 baseline: honest 3-of-4 recovers the true seed")

    # mismatched identifiers (same threshold, different id)
    expect_raises("attack7 mismatched-identifiers", codex32.Codex32Error,
                  codex32.recover, [set_test_k2[0], set_cash_k2[1]])
    # mismatched thresholds
    expect_raises("attack7 mismatched-thresholds", codex32.Codex32Error,
                  codex32.recover, [set_test_k2[0], set_test_k3[1]])
    # one share short of k
    expect_raises("attack7 one-share-short", codex32.Codex32Error,
                  codex32.recover, set_test_k3[:2])
    # flipped checksum char (mutate the last symbol to a different one)
    good = set_test_k2[0]
    swap = "q" if good[-1] != "q" else "p"
    flipped = good[:-1] + swap
    expect_raises("attack7 flipped-checksum", codex32.Codex32Error,
                  codex32.validate, flipped)


# ======================================================================
#  ATTACK 8 — SeedQR / BIP39 shim adversarial mnemonics
# ======================================================================
#
#  Attack: enter a defective mnemonic. Expected safe behavior:
#  validate_mnemonic raises ValueError. No bad seed reaches Core.

def attack_shim():
    # bad checksum: valid words, wrong final word
    bad_checksum = "abandon " * 11 + "abandon"
    expect_raises("attack8 bad-checksum-word", ValueError,
                  bip39_shim.validate_mnemonic, bad_checksum)
    # wrong length: 13 words
    thirteen = "abandon " * 12 + "about"
    expect_raises("attack8 thirteen-words", ValueError,
                  bip39_shim.validate_mnemonic, thirteen)
    # non-wordlist word
    nonword = "abandon " * 11 + "zzzz"
    expect_raises("attack8 non-wordlist-word", ValueError,
                  bip39_shim.validate_mnemonic, nonword)
    # and the canonical mnemonic still validates (no false positives)
    assert bip39_shim.validate_mnemonic(MNEMONIC) == MNEMONIC.strip()
    ok("attack8 baseline: canonical mnemonic still validates")


# ======================================================================
#  Runner
# ======================================================================

def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    datadir = tempfile.mkdtemp(prefix="corky-adv-regtest-")
    # A private RPC port, written into the datadir conf so bitcoin-cli finds
    # it. This isolates the suite from any other regtest daemon that a
    # concurrent session may be running on the default port.
    rpcport = _free_port()
    Path(datadir, "bitcoin.conf").write_text(f"[regtest]\nrpcport={rpcport}\n")
    daemon = subprocess.Popen(
        ["bitcoind", "-regtest", f"-datadir={datadir}", "-listen=0",
         f"-rpcport={rpcport}", "-fallbackfee=0.0001", "-server=1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(60):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)

        # No-bitcoind tests first (fast, independent of the daemon).
        attack_codex32()
        attack_shim()

        setup_regtest(rpc)
        attack_false_fee(rpc)
        attack_output_substitution(rpc)
        attack_malformed(rpc)
        attack_unowned_input(rpc)
        attack_sighash(rpc)
        attack_replay(rpc)
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:  # noqa: BLE001
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)

    if FAILURES:
        print(f"\nADVERSARIAL SUITE FAIL: {len(FAILURES)} attack(s) not "
              "safely handled")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("\nADVERSARIAL SUITE PASS: false-fee, output-substitution, "
          "malformed input, unowned input, sighash, replay, codex32 and "
          "shim attacks all handled safely")


if __name__ == "__main__":
    main()
