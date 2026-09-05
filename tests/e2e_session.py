"""Full-device dress rehearsals on the dev HAL: three scripted sessions
covering the four pure-Core key modes, QR PSBT in/out, and refusal of a
fee-less PSBT. Run: python3 tests/e2e_session.py"""

import base64
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402
import qrchannel  # noqa: E402

# A-22: the pure signer has no BIP39. This is exactly the key the old
# "abandon x11 about" mnemonic produced on regtest, so every address,
# fee and signature these tests assert is unchanged.
XPRV = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"


BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def grid_keys(payload):
    """Button script that types payload on the 4x8 grid (cursor starts 0)."""
    cur, out = 0, []
    for ch in payload:
        tgt = BECH32.index(ch)
        d = (tgt - cur) % 32
        out.append("d" * (d // 8) + "r" * (d % 8) + "a")
        cur = tgt
    return "".join(out)


def _pub(rpc, desc):
    """The watch-only form of a private descriptor, checksummed by Core."""
    info = rpc.call("getdescriptorinfo", desc, stdin=True)
    return info["descriptor"]


def run_device(datadir, script, frames, stick=None, qr_key=None, qr_psbt=None):
    cmd = [sys.executable, str(ROOT / "corky" / "main.py"), "--dev",
           f"--datadir={datadir}", "--chain=regtest", f"--script={script}",
           f"--frames-dir={frames}"]
    if stick:
        cmd.append(f"--stick-dir={stick}")
    if qr_key:
        cmd.append(f"--qr-key={qr_key}")
    if qr_psbt:
        cmd.append(f"--qr-psbt={qr_psbt}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def main():
    datadir = tempfile.mkdtemp(prefix="corky-sess-")
    import random as _rnd
    _port = _rnd.randint(20000, 60000)
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % _port)
    work = Path(tempfile.mkdtemp(prefix="corky-sess-work-"))
    daemon = subprocess.Popen(
        ["bitcoind", "-regtest", f"-datadir={datadir}", "-listen=0",
         "-fallbackfee=0.0001", "-server=1", "-debuglogfile=0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(60):
            try:
                rpc.call("getblockcount")
                break
            except RuntimeError:
                time.sleep(0.5)

        # Coordinator: watch wallet from Corky's xpubs, funded
        signer.open_session_xprv(rpc, XPRV)
        pubs = signer.public_descriptors(rpc)
        signer.close_session(rpc)
        rpc.call("createwallet", "watch", True, True, "", False, True)
        rpc.call("importdescriptors",
                 [{"desc": d, "active": True, "timestamp": "now",
                   "range": [0, 200], "internal": "/1/*" in d}
                  for d in pubs], wallet="watch")
        addr = rpc.call("getnewaddress", wallet="watch")
        rpc.call("generatetoaddress", 101, addr)

        def fund_psbt(amount):
            dest = rpc.call("getnewaddress", wallet="watch")
            return rpc.call("walletcreatefundedpsbt", [], [{dest: amount}],
                            0, {"fee_rate": 10}, True, wallet="watch")["psbt"]

        import io
        import screens as scr

        def _render(fn, *a, **k):
            b = io.BytesIO()
            fn(320, 240, *a, **k).save(b, format="PNG")
            return b.getvalue()

        def _frames(d):
            return sorted(Path(d).glob("frame-*.png"))

        def _has(d, png):
            return any(p.read_bytes() == png for p in _frames(d))


        # ---- Session B: xprv via QR + PSBT in AND out via QR ----
        xprv_file = work / "key.txt"
        xprv_file.write_text(XPRV)
        frames_file = work / "psbt_frames.txt"
        frames_file.write_text("\n".join(qrchannel.psbt_to_frames(fund_psbt(1.0))))
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "a" + "ra", work / "framesB",
                       qr_key=xprv_file, qr_psbt=frames_file)
        assert r.returncode == 0, f"B failed rc={r.returncode}:\n{r.stderr[-1200:]}"
        shots = sorted((work / "framesB").glob("frame-*.png"))
        assert len(shots) > 6, "B: expected QR output frames on screen"
        lastb = shots[-1].read_bytes()
        assert any(lastb == _render(scr.result, ok=True,
                                    detail=f"shown as {n} QR frames",
                                    actions_sel=1)
                   for n in range(1, 80)), "B: final frame not a QR-out result"
        print(f"ok   B: xprv QR (warning screen shown) -> PSBT via QR -> signed QR out ({len(shots)} frames)")


        # ---- Session D: many-output PSBT forces paged review ----
        stickd = work / "stickD"; stickd.mkdir()
        dests = {rpc.call("getnewaddress", wallet="watch"): 0.2
                 for _ in range(4)}
        many = rpc.call("walletcreatefundedpsbt", [],
                        [{a: v} for a, v in dests.items()],
                        0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickd / "many.psbt").write_bytes(base64.b64decode(many))
        key_file2 = work / "key2.txt"
        key_file2.write_text(XPRV)
        # 5 outputs = 3 pages at two per page: forced 'a' walks pages 2
        # and 3, the fourth 'a' signs
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "aaa" + "ra", work / "framesD",
                       stick=stickd, qr_key=key_file2)
        assert r.returncode == 0, f"D failed:\n{r.stderr}"
        assert (stickd / "many-signed.psbt").exists(), "D: signed file missing"
        # Negative: a SINGLE 'a' at review (one page still unseen) must NOT
        # sign — proves the gate blocks, not just that enough 'a's sign.
        stickd2 = work / "stickD2"; stickd2.mkdir()
        many2 = rpc.call("walletcreatefundedpsbt", [],
                         [{rpc.call("getnewaddress", wallet="watch"): 0.2}
                          for _ in range(4)] and
                         [{a: v} for a, v in dests.items()],
                         0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickd2 / "many.psbt").write_bytes(base64.b64decode(many2))
        key_sq3 = work / "key3.txt"; key_sq3.write_text(XPRV)
        # load key, scan xprv, review: ONE 'a' (force-advance only) then 'c'
        # rejects; 'a' dismisses the rejection, then settings -> power off.
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "ac" + "a" + "draa",
                       work / "framesD2",
                       stick=stickd2, qr_key=key_sq3)
        assert not (stickd2 / "many-signed.psbt").exists(), \
            "D2: PSBT signed with a page unseen — paging gate is broken!"
        assert r.returncode == 0, f"D2 failed:\n{r.stderr}"
        # The rejection returns to home now (D7), so it is no longer the
        # last frame; it must still be rendered byte-identically.
        assert _has(work / "framesD2", _render(
            scr.result, ok=False, detail="rejected by user")), \
            "D2: the exact rejection screen was never shown"
        print("ok   D: paged review — signs only after all pages seen, "
              "blocks when one is unseen")

        # ---- Session D3: paging NAVIGATION (u/d, wraparound) ----
        # Mutation testing showed the u/d paths and modulo arithmetic were
        # never exercised: D only force-advanced via 'a'. Here all pages
        # are seen by real navigation, both directions.
        stickd3 = work / "stickD3"; stickd3.mkdir()
        many3 = rpc.call("walletcreatefundedpsbt", [],
                         [{a: v} for a, v in dests.items()],
                         0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickd3 / "many.psbt").write_bytes(base64.b64decode(many3))
        key_sq4 = work / "key4.txt"; key_sq4.write_text(XPRV)
        # review: d,u,d,d touch pages 1,0,1,2 -> all three seen via nav
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "dudda" + "ra", work / "framesD3",
                       stick=stickd3, qr_key=key_sq4)
        assert r.returncode == 0, f"D3 failed:\n{r.stderr}"
        assert (stickd3 / "many-signed.psbt").exists(), "D3: nav-sign missing"
        # wraparound: u from page0 lands on page2 ((0-1)%3), u again on 1
        stickd4 = work / "stickD4"; stickd4.mkdir()
        many4 = rpc.call("walletcreatefundedpsbt", [],
                         [{a: v} for a, v in dests.items()],
                         0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickd4 / "many.psbt").write_bytes(base64.b64decode(many4))
        key_sq5 = work / "key5.txt"; key_sq5.write_text(XPRV)
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "uua" + "ra", work / "framesD4",
                       stick=stickd4, qr_key=key_sq5)
        assert r.returncode == 0, f"D4 failed:\n{r.stderr}"
        assert (stickd4 / "many-signed.psbt").exists(), "D4: wraparound broken"
        print("ok   D3/D4: paging navigation u/d + wraparound exercised")


        # ---- Session R3: 2-output PSBT is exactly ONE page ----
        # pages = (len+1)//2 : 2 outputs -> 1 page, a single 'a' signs.
        stickr = work / "stickR3"; stickr.mkdir()
        p3 = rpc.call("walletcreatefundedpsbt", [],
                      [{rpc.call("getnewaddress", wallet="watch"): 0.1}],
                      0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickr / "p3.psbt").write_bytes(base64.b64decode(p3))
        key_sqr = work / "sq_r3.txt"; key_sqr.write_text(XPRV)
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "a" + "ra", work / "framesR3",
                       stick=stickr, qr_key=key_sqr)
        assert r.returncode == 0, f"R3 failed:\n{r.stderr}"
        assert (stickr / "p3-signed.psbt").exists(), "R3: 2-out page count wrong"
        print("ok   R3: 2-output PSBT reviewed as one page and signed")

        # ---- Session I: incomplete QR assembly, then abort at load ----
        allframes = qrchannel.psbt_to_frames(fund_psbt(1.0))
        assert len(allframes) > 1, "I: need a multi-frame PSBT"
        part = work / "partial_frames.txt"
        part.write_text(allframes[0])
        emptystick = work / "stickI"; emptystick.mkdir()
        key_sqi = work / "key_i.txt"; key_sqi.write_text(XPRV)
        # state_load now opens on a channel menu (Ben, 2026-09-04), and this
        # session supplies BOTH channels, so the menu appears and has to be
        # answered before the scan loop is reached at all. Without the extra
        # "a" the abort key lands on the menu and this stops testing what its
        # name says. B goes back one page to the menu, C aborts to home
        # (hw/HARDWARE.md), so the two need different tails.
        for abkey, tail in (("b", "c" + "draa"), ("c", "draa")):
            r = run_device(datadir,
                           "ra" + "da" + "a" + "a" + "a" + abkey + tail,
                           work / ("framesI" + abkey),
                           stick=emptystick, qr_key=key_sqi, qr_psbt=part)
            assert r.returncode == 0, f"I({abkey}) failed:\n{r.stderr}"
            # In dev there is no camera frame, so screens.scanning falls back
            # to the wait frame with the scan's own message.
            assert _has(work / ("framesI" + abkey),
                        _render(scr.busy, "hold the QR in view")), \
                f"I({abkey}): the scan screen was never shown"
            assert _has(work / ("framesI" + abkey),
                        _render(scr.channel_menu, 0)), \
                f"I({abkey}): the channel menu was never shown"
        print("ok   I: partial QR makes progress; b/c abort the load loop")

        # ---- Session J: PSBT this wallet cannot complete -> refusal ----
        # A-22: the watch wallet used to be a by-product of the codex32
        # session, which moved to the lab. J makes its own, so it stands
        # alone: a funded wallet whose keys Corky does not hold.
        stickj = work / "stickJ"; stickj.mkdir()
        rpc.call("createwallet", "foreignJ")
        fa = rpc.call("getnewaddress", wallet="foreignJ")
        rpc.call("generatetoaddress", 101, fa)
        foreign = rpc.call("walletcreatefundedpsbt", [],
                           [{rpc.call("getnewaddress", wallet="foreignJ"): 0.5}],
                           0, {"fee_rate": 10}, True, wallet="foreignJ")["psbt"]
        (stickj / "alien.psbt").write_bytes(base64.b64decode(foreign))
        key_sqj = work / "key_j.txt"; key_sqj.write_text(XPRV)
        foreign_xfp = signer.master_fingerprint(rpc, wallet="foreignJ")
        # Ticket 03: the transaction names its key, so the refusal comes
        # BEFORE review and names the fingerprint it wants. One key
        # dismisses it, then settings, power off.
        r = run_device(datadir, "ra" + "da" + "a" + "a" + "a" + "draa", work / "framesJ",
                       stick=stickj, qr_key=key_sqj)
        assert r.returncode == 0, f"J failed:\n{r.stderr}"
        assert not (stickj / "alien-signed.psbt").exists(), "J: signed foreign PSBT!"
        # Returns to home after the refusal (D7); the screen must still be
        # rendered byte-identically somewhere in the run.
        assert _has(work / "framesJ", _render(
            scr.result, ok=False,
            detail=f"no loaded key owns it; wants {foreign_xfp}")), \
            "J: the exact cannot-complete screen was never shown"
        print("ok   J: foreign PSBT -> cannot-complete refusal, golden-verified")





        # ---- Session N: 3-page review, page ORDER pinned frame-by-frame --
        def paged_run(tag, navkeys):
            st = work / ("stickN" + tag); st.mkdir()
            pn = rpc.call("walletcreatefundedpsbt", [],
                          [{rpc.call("getnewaddress", wallet="watch"): 0.05}
                           for _ in range(6)],
                          0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
            (st / "n.psbt").write_bytes(base64.b64decode(pn))
            signer.open_session_xprv(rpc, XPRV)
            info = signer.describe_psbt(rpc, pn)
            signer.close_session(rpc)
            outs = [(o["address"], o["amount_btc"]) for o in info["outputs"]]
            assert (len(outs) + 1) // 2 == 4, "N: expected exactly 4 pages"
            # Each page has two renders now: the plain one, and the one
            # that says why SIGN was refused (unseen pages remain).
            pages = [[_render(scr.review, outs, info["fee_btc"],
                              input_total_btc=info["input_total_btc"],
                              page=i, unseen_pages=refused)
                      for refused in (False, True)]
                     for i in range(4)]
            key_sq = work / ("key_n" + tag + ".txt")
            key_sq.write_text(XPRV)
            r = run_device(datadir, "ra" + "da" + "a" + "a" + navkeys + "ra",
                           work / ("framesN" + tag), stick=st, qr_key=key_sq)
            assert r.returncode == 0, f"N{tag} failed:\n{r.stderr}"
            assert (st / "n-signed.psbt").exists(), f"N{tag}: sign missing"
            seq = []
            for f in _frames(work / ("framesN" + tag)):
                raw = f.read_bytes()
                for i, variants in enumerate(pages):
                    if raw in variants:
                        # (page, refused): variants[1] carries the banner.
                        seq.append((i, variants.index(raw) == 1))
            return seq
        # navigate d,d,d then sign: four plain renders, never the banner
        assert paged_run("1", "ddda") == [(0, False), (1, False), (2, False),
                                          (3, False)], \
            "N1: page navigation order or refusal state drifted"
        # forced advance a,a,a,a: each unseen page must carry the banner
        assert paged_run("2", "aaaa") == [(0, False), (1, True), (2, True),
                                          (3, True)], \
            "N2: forced advance must show the refusal banner on unseen pages"
        print("ok   N: 4-page review order pinned (nav and forced advance)")


        # ---- Session T: typed xprv and typed descriptor (S3) ----
        # The audit's S3 asked for key material that can be TYPED, for a
        # build with no camera. Both modes were shipped once with a charset
        # that could not express them (no 'B', no brackets), so these type a
        # REAL xprv and a REAL descriptor character by character.
        import screens as _scr          # was imported by a session A-22 removed
        def text_keys(charset, want):
            """Keys that type `want` on the paged text grid, computed by
            walking the same rules main._text_entry uses."""
            pages = _scr.charset_pages(charset)
            page, cur, out = 0, 0, []
            for ch in want:
                tp = next(i for i, pg in enumerate(pages) if ch in pg)
                ti = pages[tp].index(ch)
                while page < tp:                  # r past the end pages on
                    n = len(pages[page])
                    while cur < n - 1:
                        out.append("r"); cur += 1
                    out.append("r"); page += 1; cur = 0
                while page > tp:                  # l past the start pages back
                    while cur > 0:
                        out.append("l"); cur -= 1
                    out.append("l"); page -= 1; cur = len(pages[page]) - 1
                n = len(pages[page])
                while cur + 8 <= ti:
                    out.append("d"); cur = min(n - 1, cur + 8)
                while cur - 8 >= ti:
                    out.append("u"); cur = max(0, cur - 8)
                while cur < ti:
                    out.append("r"); cur += 1
                while cur > ti:
                    out.append("l"); cur -= 1
                out.append("a")
            out.append("p")                            # centre press = done
            return "".join(out)

        stickt = None
        typed_xprv = XPRV
        assert not {c for c in typed_xprv
                    if c not in _scr.CHARSETS["xprv"]}, \
            "T: a real xprv contains characters the xprv grid cannot type"
        stickt = work / "stickT"; stickt.mkdir()
        pt = rpc.call("walletcreatefundedpsbt", [],
                      [{rpc.call("getnewaddress", wallet="watch"): 0.3}],
                      0, {"fee_rate": 10}, True, wallet="watch")["psbt"]
        (stickt / "typed.psbt").write_bytes(base64.b64decode(pt))
        # Key tile -> "Type xprv" is index 2 -> type it -> Sign transaction -> sign
        r = run_device(datadir,
                       "ra" + "ddda" + text_keys("xprv", typed_xprv)
                       + "a" + "a" + "ra",   # Sign transaction, sign, POWER OFF
                       work / "framesT", stick=stickt)
        assert r.returncode == 0, f"T failed:\n{r.stderr}"
        assert (stickt / "typed-signed.psbt").exists(), \
            "T: typed xprv did not open a key that could sign"
        print("ok   T: a real xprv typed on the grid opens the key and signs")

        # The descriptor grid must express a real Core PRIVATE descriptor,
        # so ask Core for one from a throwaway wallet that holds keys.
        rpc.call("createwallet", "desccheck")
        _d = rpc.call("listdescriptors", True,
                      wallet="desccheck")["descriptors"]
        _missing = {c for desc in _d for c in desc["desc"]
                    if c not in _scr.CHARSETS["descriptor"]}
        assert not _missing, \
            f"T: real Core descriptors need characters the grid lacks: {_missing}"

        # ...and typing one must actually open a key that signs. This is the
        # end-to-end shape whose absence let the original S3 charset bug
        # ship: a charset assertion alone would have passed it too.
        rpc.call("unloadwallet", "desccheck")
        # Corky's OWN private wpkh receive descriptor, in Core's own form
        # (origin in brackets, checksummed), read straight back out of a
        # session opened from the test mnemonic.
        signer.open_session_xprv(rpc, XPRV)
        _privs = rpc.call("listdescriptors", True,
                          wallet=signer.WALLET)["descriptors"]
        _priv = next(d["desc"] for d in _privs
                     if d["desc"].startswith("wpkh(")
                     and not d.get("internal"))
        signer.close_session(rpc)
        assert not {c for c in _priv
                    if c not in _scr.CHARSETS["descriptor"]}, \
            "T2: Corky's own private descriptor is not typeable on the grid"

        # Fund the first address of that exact descriptor, so the typed
        # descriptor alone is enough to sign.
        # The public form keeps the hardened origin, so only the private
        # descriptor can derive. stdin keeps it out of the process list.
        _a0 = rpc.call("deriveaddresses", _priv, [0, 0], stdin=True)[0]
        rpc.call("generatetoaddress", 101, _a0)
        _utxo = next(u for u in rpc.call("listunspent", 1, 9999, [_a0],
                                         wallet="watch")
                     if u["spendable"] or True)
        stickt2 = work / "stickT2"; stickt2.mkdir()
        _p2 = rpc.call("walletcreatefundedpsbt",
                       [{"txid": _utxo["txid"], "vout": _utxo["vout"]}],
                       [{rpc.call("getnewaddress", wallet="watch"): 1.0}],
                       0, {"fee_rate": 10, "add_inputs": False}, True,
                       wallet="watch")["psbt"]
        (stickt2 / "desc.psbt").write_bytes(base64.b64decode(_p2))
        # Key tile -> "Type descriptor" is index 1 -> type it -> Sign transaction -> sign
        r = run_device(datadir,
                       "ra" + "dda" + text_keys("descriptor", _priv)
                       + "a" + "a" + "ra",
                       work / "framesT2", stick=stickt2)
        assert r.returncode == 0, f"T2 failed:\n{r.stderr}"
        assert (stickt2 / "desc-signed.psbt").exists(), \
            "T2: a typed descriptor did not open a key that could sign"
        print("ok   T2: a real Core descriptor typed on the grid opens a "
              "key and signs")
        print("ok   T: the descriptor grid can express a real Core descriptor")

        # ---- Session G: exact-Core generation from the Keys screen (A-19) --
        # Keys, New key, accept the tradeoff, then the BACKUP CHOICE. New
        # key is the FIRST row on the Keys screen now, and the paper backup
        # is the second backup option, so this session takes it
        # deliberately: d then a, then one a per screenful
        # of the master xprv (111 characters paginate into three), then the
        # address screen, then back out.
        fg = work / "framesG"
        xprv_pages = 3
        r = run_device(datadir,
                       "ra" + "a" + "a"           # Keys, New key (first row), accept
                       + "da"                     # backup menu -> On paper
                       + "a" * xprv_pages + "a"   # the pages, then the address
                       + "b" + "b" + "draa",
                       fg)
        assert r.returncode == 0, f"G failed:\n{r.stderr}"
        assert _has(fg, _render(scr.generate_warning)), \
            "G: the tradeoff screen was never shown before generation"
        assert _has(fg, _render(scr.busy,
                                "Bitcoin Core is generating your key…")), \
            "G: Core was not asked to create the wallet"
        assert not (rpc.wallet_dir / signer.WALLET).exists(), \
            "G: the session wallet was not deleted at teardown"
        assert _has(fg, _render(scr.backup_menu, 0)), \
            "G: the backup choice was never offered after generation"
        print("ok   G: Core-RNG generation -> backup choice -> wallet open "
              "in Core -> both wallets gone at teardown")

        print("\nSESSION PASS: xprv-QR, typed xprv, typed descriptor, "
              "Core-RNG generation, QR in/out, stick in/out, "
              "refusal, paged review")
    finally:
        try:
            rpc.call("stop")
            daemon.wait(timeout=30)
        except Exception:
            daemon.kill()
        shutil.rmtree(datadir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
