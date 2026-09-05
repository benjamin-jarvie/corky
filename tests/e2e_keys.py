"""Several keys, on the device: scripted dev-HAL sessions for map
e2e-before-testers tickets 03 and 10. Run: python3 tests/e2e_keys.py
(needs bitcoind)."""
import io
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import signer  # noqa: E402
import screens as scr  # noqa: E402
import qrchannel  # noqa: E402

XPRV_A = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"


def text_keys(charset, want):
    """Keys that type `want` on the paged text grid, by walking the same
    rules main._text_entry uses (TESTING.md rule 2: assert the round trip,
    never the key count)."""
    pages = scr.charset_pages(charset)
    page, cur, out = 0, 0, []
    for ch in want:
        tp = next(i for i, pg in enumerate(pages) if ch in pg)
        ti = pages[tp].index(ch)
        while page < tp:
            n = len(pages[page])
            while cur < n - 1:
                out.append("r"); cur += 1
            out.append("r"); page += 1; cur = 0
        while page > tp:
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
    out.append("p")
    return "".join(out)


def run_device(datadir, script, frames, qr_key=None, qr_psbt=None,
               stick=None, card=None):
    cmd = [sys.executable, str(ROOT / "corky" / "main.py"), "--dev",
           f"--datadir={datadir}", "--chain=regtest", f"--script={script}",
           f"--frames-dir={frames}"]
    if stick:
        cmd.append(f"--stick-dir={stick}")
    if card:
        cmd.append(f"--card-dir={card}")
    if qr_key:
        cmd.append(f"--qr-key={qr_key}")
    if qr_psbt:
        cmd.append(f"--qr-psbt={qr_psbt}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def _render(fn, *a, **k):
    b = io.BytesIO()
    fn(320, 240, *a, **k).save(b, format="PNG")
    return b.getvalue()


def _shots(d):
    """Frames in paint order. Typing an xprv paints more than 999 frames,
    and the dev display numbers them with three digits, so a text sort
    puts frame-1000 before frame-999."""
    return sorted(Path(d).glob("frame-*.png"),
                  key=lambda p: int(p.stem.split("-")[1]))


def _has(d, png):
    return any(p.read_bytes() == png for p in _shots(d))


def fresh_xprv(rpc):
    rpc.call("createwallet", "donor")
    text = rpc.call("listdescriptors", True, wallet="donor")["descriptors"][0]["desc"]
    key = text[text.rindex("(") + 1:]
    for stop in "/)":
        if stop in key:
            key = key[: key.index(stop)]
    rpc.call("unloadwallet", "donor")
    shutil.rmtree(rpc.wallet_dir / "donor", ignore_errors=True)
    return key


def main():
    datadir = tempfile.mkdtemp(prefix="corky-keys-")
    (Path(datadir) / "bitcoin.conf").write_text(
        "regtest=1\n[regtest]\nrpcport=%d\n" % random.randint(20000, 60000))
    work = Path(tempfile.mkdtemp(prefix="corky-keys-work-"))
    daemon = subprocess.Popen(
        ["bitcoind", "-regtest", f"-datadir={datadir}", "-listen=0",
         "-fallbackfee=0.0001", "-server=1", "-nodebuglogfile"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(datadir, chain="regtest")
    try:
        for _ in range(60):
            try:
                rpc.call("getblockcount"); break
            except RuntimeError:
                time.sleep(0.5)
        # Two keys. A is the suite's key; B is born in Core. Their
        # fingerprints come from Core, never from a literal.
        xprv_b = fresh_xprv(rpc)
        name = signer.open_session_xprv(rpc, XPRV_A)
        xfp_a = signer.master_fingerprint(rpc, wallet=name)
        signer.close_session(rpc)
        name = signer.open_session_xprv(rpc, xprv_b)
        xfp_b = signer.master_fingerprint(rpc, wallet=name)
        pubs_b = signer.public_descriptors(rpc)
        signer.close_session(rpc)
        # A coordinator for B, funded, with one transaction ready.
        rpc.call("createwallet", "watchB", True, True, "", False, True)
        rpc.call("importdescriptors",
                 [{"desc": d, "active": True, "timestamp": "now",
                   "range": [0, 200], "internal": "/1/*" in d} for d in pubs_b],
                 wallet="watchB")
        addr_b = rpc.call("getnewaddress", wallet="watchB")
        rpc.call("generatetoaddress", 101, addr_b)
        psbt_b = rpc.call("walletcreatefundedpsbt", [],
                          [{rpc.call("getnewaddress", wallet="watchB"): 1.0}],
                          0, {"fee_rate": 10}, True, wallet="watchB")["psbt"]
        key_a = work / "key_a.txt"; key_a.write_text(XPRV_A)
        frames_b = work / "frames_b.txt"
        frames_b.write_text("\n".join(qrchannel.psbt_to_frames(psbt_b)))

        # ---- Session K1: the same key twice is refused, once loaded ----
        # The KEYS screen no longer skips itself when nothing is loaded, so
        # Load a key is a row you choose rather than a screen you land on.
        script1 = ("ra"          # Keys tile
                   + "a"         # Load a key
                   + "a"         # Scan a key
                   + "a"         # accept the warning: the key loads
                   + "b"         # back to KEYS, which now lists it
                   + "da"        # down to Load a key, select
                   + "a"         # Scan a key
                   + "a"         # accept the warning: refused, same key
                   + "a"         # dismiss the refusal
                   + "b"         # KEYS -> home
                   + "draa")     # settings -> power off
        r = run_device(datadir, script1, work / "framesK1", qr_key=key_a)
        assert r.returncode == 0, f"K1 failed:\n{r.stderr[-1500:]}"
        assert _has(work / "framesK1", _render(
            scr.result, ok=False, detail=f"key {xfp_a} is already loaded")), \
            "K1: the duplicate refusal was never shown"
        assert _has(work / "framesK1", _render(scr.home, 0, xfp=xfp_a)), \
            "K1: home never showed the loaded key's fingerprint"
        print("ok   K1: loading the same key twice is refused by fingerprint")

        # ---- Session K2: two keys, and the transaction picks its key ----
        # load A by QR; the QR transaction belongs to B, nobody owns it,
        # dismiss; load B by typing its xprv; the same transaction now finds
        # B among two keys: the key screen appears with B pre-selected,
        # confirm, review, sign, QR out, power off.
        script = ("ra" + "a" + "a" + "a"            # Keys -> Load a key -> Scan a key -> warning
                  + "a" + "a"                     # Sign transaction, dismiss the refusal
                  + "ra" + "da" + "dda" + text_keys("xprv", xprv_b)   # keys list, Load a key, Type xprv
                  + "a" + "a" + "a" + "ra")          # Sign transaction, confirm B, sign, power off
        r = run_device(datadir, script, work / "framesK2",
                       qr_key=key_a, qr_psbt=frames_b)
        assert r.returncode == 0, f"K2 failed:\n{r.stderr[-1500:]}"
        assert _has(work / "framesK2", _render(
            scr.result, ok=False, detail=f"no loaded key owns it; wants {xfp_b}")), \
            "K2: a transaction nobody owns was not refused by name"
        assert _has(work / "framesK2", _render(
            scr.choose_key, [("corky", xfp_a), ("corky-2", xfp_b)], {xfp_b}, 1)), \
            "K2: the key screen with B pre-selected was never shown"
        last = _shots(work / "framesK2")[-1].read_bytes()
        assert any(last == _render(scr.result, ok=True,
                                   detail=f"shown as {n} QR frames", actions_sel=1)
                   for n in range(1, 80)), "K2: final frame is not a signed result"
        print("ok   K2: two keys loaded; the transaction's owner is found and signs")

        # ---- Session K3: the menus, SeedSigner's shape (tickets 02, 07) ----
        # Home is Scan, Key, Tools, Settings. Scan with no key holds a
        # message. Key with no key opens Load a key; Scan a key loads A and
        # lands on A's menu. Backup key pages the xprv. Discard key asks,
        # then forgets A. Tools, New key generates a key and lands on its
        # menu; B twice goes back to home. Settings, power off.
        # Ticket 05: the Scan tile reads whatever is in front of it. Here
        # that is an xprv, so it loads the key and lands on its menu with
        # no Load-a-key detour at all.
        script = ("a"                             # Scan tile: xprv -> key menu
                  + "dda" + "a" + "dda" + "b"     # Receiving addresses -> segwit -> page on, back
                  + "da" + "da" + "aaa"           # Backup key -> On paper (2nd) -> 3 pages
                  + "da" + "ra"                   # Discard key -> confirm: DISCARD
                  + "da" + "a" + "c"              # Tools -> Check for leaks -> C leaves
                  + "b"                           # Tools -> home
                  + "ra" + "da" + "a"             # Keys -> New key (2nd action) -> proceed
                  + "da" + "aaa" + "a"            # backup choice -> On paper -> 3 pages -> address
                  + "b" + "b"                     # key menu -> keys -> home
                  + "draa")
        r = run_device(datadir, script, work / "framesK3", qr_key=key_a)
        assert r.returncode == 0, f"K3 failed:\n{r.stderr[-1500:]}"
        fr = work / "framesK3"
        assert _has(fr, _render(scr.home, 0)), "K3: home without a key"
        assert _has(fr, _render(scr.key_menu, xfp_a, 0)), \
            "K3: scanning an xprv did not land on that key's menu"
        assert _has(fr, _render(scr.key_menu, xfp_a, 0)), "K3: A's key menu"
        assert _has(fr, _render(scr.key_menu, xfp_a, 3)), "K3: Backup key highlighted"
        assert _has(fr, _render(scr.backup_menu, 0)), \
            "K3: the backup chooser, with the file backup first"
        assert _has(fr, _render(scr.backup_menu, 1)), \
            "K3: On paper is the second row now, and was selected"
        # The dev display blanks every sensitive frame (hal.DevDisplay), so
        # the three xprv pages are three blank frames in a row, and the
        # backup page itself is pinned by test_screen_fit.
        from PIL import Image
        blank = io.BytesIO()
        Image.new("RGB", (320, 240), "#1A1714").save(blank, format="PNG")
        blanks = sum(1 for f in _shots(fr) if f.read_bytes() == blank.getvalue())
        assert blanks >= 3, f"K3: expected 3 blanked backup pages, saw {blanks}"
        # Both frames matter and they are different: BACK is pre-selected,
        # and DISCARD only happens once the user moves to it.
        assert _has(fr, _render(scr.confirm_discard, xfp_a, 0)), \
            "K3: discard did not ask first, with BACK pre-selected"
        assert _has(fr, _render(scr.confirm_discard, xfp_a, 1)), \
            "K3: DISCARD was never the selected action"
        assert _has(fr, _render(scr.tools_menu, 0)), \
            "K3: the Tools menu, which now holds only the leak check"
        assert _has(fr, _render(scr.keys_menu, [], 1)), \
            "K3: the KEYS screen offers New key with nothing loaded"
        assert _has(fr, _render(scr.busy, "checking every way off this board…")), \
            "K3: the leak check never ran"
        assert _has(fr, _render(scr.key_menu, xfp_a, 2)), \
            "K3: Receiving addresses highlighted"
        assert _has(fr, _render(scr.export_script_menu, ("wpkh", "tr"), 0)), \
            "K3: Receiving addresses asked which script type"
        assert _has(fr, _render(scr.home, 2)), "K3: Tools tile highlighted"
        assert _has(fr, _render(scr.generate_warning, 1, 0)), "K3: New key warning"
        left = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        assert not left, f"K3: a key survived the session: {left}"
        print("ok   K3: Scan, Key, Tools, Settings; load, backup, discard, new key")

        # ---- Session K4: a key from a crashed session never reaches this
        # one. bitcoind and the ramdisk both outlive a UI restart, and
        # corky.service has Restart=on-failure, so this is what the board
        # does after a crash. Load a key OUTSIDE the device, then start the
        # device: it must clear it, say so, and show a home screen with no
        # fingerprint on it.
        signer.open_session_xprv(rpc, XPRV_A)
        assert signer.loaded_keys(rpc), "K4: setup failed to load a key"
        r = run_device(datadir, "a" + "draa", work / "framesK4")
        assert r.returncode == 0, f"K4 failed:\n{r.stderr[-1500:]}"
        assert not [w for w in rpc.call("listwallets") if w in signer.SLOTS], \
            "K4: a key from an earlier session survived into this one"
        fr4 = work / "framesK4"
        assert _has(fr4, _render(scr.result, ok=False,
                                 detail="cleared 1 key(s) from an earlier session")), \
            "K4: the device did not say it had cleared an inherited key"
        assert _has(fr4, _render(scr.home, 0)), \
            "K4: home still showed a fingerprint after the clear"
        assert not _has(fr4, _render(scr.home, 0, xfp=xfp_a)), \
            "K4: the inherited key was still named on the home screen"
        print("ok   K4: a key left by a crashed session is cleared at startup")

        # ---- Session K5: export the public key (ticket 12) ----
        # The QR's CONTENT is proven against Sparrow's own zxing in
        # tests/sparrow/test_export_interop.py (rule 8). Here the question
        # is the device: does the panel show that exact code, the same
        # descriptor as text, and Core's real addresses in full.
        signer.close_session(rpc)
        name5 = signer.open_session_xprv(rpc, XPRV_A)
        desc = signer.export_descriptor(rpc, name5, "wpkh")
        want_addrs = signer.receive_addresses(rpc, name5, "wpkh", 3)
        desc_pages = len(scr.text_pages(desc))
        signer.close_session(rpc)
        stick5 = work / "stick5"; stick5.mkdir()
        script = ("ra" + "a" + "a" + "a"              # Keys -> Load a key -> Scan a key -> warning
                  + "da" + "a" + "a"                  # Export public key -> Sparrow -> segwit
                  + "a"                               # leave the QR
                  + "a" * desc_pages                  # the descriptor as text
                  + "a" * 3                           # three address pages
                  + "a" + "da" + "a" + "a"            # Export again -> Bitcoin Core -> medium -> writes, dismiss
                  + "b" + "b" + "draa")
        r = run_device(datadir, script, work / "framesK5",
                       qr_key=key_a, stick=stick5)
        assert r.returncode == 0, (f"K5 failed rc={r.returncode}\n"
                                   f"STDERR:{r.stderr[-1200:]}\n"
                                   f"STDOUT:{r.stdout[-600:]}")
        fr5 = work / "framesK5"
        golden_qr = qrchannel.fit_to_panel(
            qrchannel.text_to_image(desc, panel=(320, 240)), 320, 240)
        buf = io.BytesIO(); golden_qr.save(buf, format="PNG")
        assert _has(fr5, buf.getvalue()), \
            "K5: the panel never showed the export QR"
        assert _has(fr5, _render(scr.export_menu, 0)), "K5: the wallet chooser"
        assert _has(fr5, _render(scr.export_script_menu, ("wpkh", "tr"), 0)), \
            "K5: the script-type chooser"
        assert _has(fr5, _render(scr.export_text, scr.text_pages(desc)[0],
                                 page=0, pages=desc_pages)), \
            "K5: the descriptor as grouped text"
        for i, addr in enumerate(want_addrs):
            assert _has(fr5, _render(scr.address_page, i, addr, "wpkh")), \
                f"K5: receive address {i} was never shown in full"
        written = list(stick5.glob("corky-*-watch.dat"))
        assert len(written) == 1, f"K5: watch-only file not written: {written}"
        assert _has(fr5, _render(scr.result, ok=True,
                                 detail=f"{written[0].name} written")), \
            "K5: the device did not say where the file went"
        assert xfp_a in written[0].name, \
            f"K5: the file is not named by fingerprint: {written[0].name}"
        print(f"ok   K5: export -> QR, text, three addresses, and "
              f"{written[0].name} for a Core laptop")

        # ---- Session K6: the file backup, and restoring from it (13) ----
        # Load A, back it up to the stick with a passphrase, discard it,
        # then load it again from that file. The key that comes back must
        # be the same key, by fingerprint.
        signer.close_session(rpc)
        stick6 = work / "stick6"; stick6.mkdir()
        phrase = text_keys("passphrase", "hunter2")
        script = ("ra" + "a" + "a" + "a"              # Keys -> Load a key -> Scan a key -> warning
                  + "ddda" + "a" + phrase + "a" + "a"  # Backup key -> To a file (1st) -> type -> channel -> dismiss
                  + "da" + "ra"                       # Discard key -> DISCARD
                  + "ra" + "a" + "ddda" + "a" + phrase  # Keys -> Load a key -> Restore from file -> pick -> type
                  + "b" + "b" + "draa")
        r = run_device(datadir, script, work / "framesK6",
                       qr_key=key_a, stick=stick6)
        assert r.returncode == 0, (f"K6 failed rc={r.returncode}\n"
                                   f"STDERR:{r.stderr[-1200:]}")
        backups = signer.find_backups(stick6)
        assert len(backups) == 1, f"K6: backup not written: {list(stick6.iterdir())}"
        assert xfp_a in backups[0].name, f"K6: wrong name {backups[0].name}"
        fr6 = work / "framesK6"
        assert _has(fr6, _render(scr.backup_menu, 0)), \
            "K6: the backup chooser, with the file backup pre-selected"
        assert _has(fr6, _render(scr.restore_menu, [backups[0].name], 0)), \
            "K6: the restore chooser listed the backup by fingerprint"
        assert _has(fr6, _render(scr.result, ok=True,
                                 detail=f"{backups[0].name} written")), \
            "K6: the device did not say the backup was written"
        # The key that came back is the same key, and it is usable.
        restored = signer.restore_encrypted(rpc, backups[0], "hunter2")
        assert signer.master_fingerprint(rpc, wallet=restored) == xfp_a, \
            "K6: the restored key is not the key that was backed up"
        signer.close_session(rpc)
        print(f"ok   K6: backup to {backups[0].name}, discard, restore, "
              f"same fingerprint {xfp_a}")

        # ---- Session K7: a bad file on the stick must not kill the app ----
        # ISSUES D18. corky.service has Restart=on-failure, so an exception
        # here is not one bad screen, it is a restart loop that lasts as
        # long as the file is on the stick. A tester will hit this in the
        # first hour.
        signer.close_session(rpc)
        stick7 = work / "stick7"; stick7.mkdir()
        (stick7 / "junk.psbt").write_bytes(b"this is not a transaction" * 8)
        script = ("ra" + "a" + "a" + "a"  # Keys -> Load a key -> Scan a key -> warning
                  + "a"                 # Sign transaction -> the stick
                  + "a"                 # dismiss whatever it says
                  + "draa")
        r = run_device(datadir, script, work / "framesK7",
                       qr_key=key_a, stick=stick7)
        assert r.returncode == 0, (f"K7: a bad PSBT file crashed the device "
                                   f"rc={r.returncode}\n{r.stderr[-900:]}")
        assert not (stick7 / "junk-signed.psbt").exists(), \
            "K7: junk was signed"
        signer.close_session(rpc)
        print("ok   K7: a bad file on the stick is reported, not fatal")

        # ---- Session K8: an empty file is refused by the file channel ----
        stick8 = work / "stick8"; stick8.mkdir()
        (stick8 / "empty.psbt").write_bytes(b"")
        # The empty file is refused by name, and C leaves. Without the
        # message the device would ask for a stick that is already in it.
        # The dev keypad has no "no key pressed" state: every poll consumes
        # a script key. The spare "a" is the tick on which the loop repaints
        # with the reason, and C then leaves.
        script8 = ("ra" + "a" + "a" + "a" + "a" + "a" + "c" + "draa")
        r = run_device(datadir, script8, work / "framesK8",
                       qr_key=key_a, stick=stick8)
        assert r.returncode == 0, (f"K8: an empty PSBT file crashed the "
                                   f"device rc={r.returncode}\n{r.stderr[-900:]}")
        assert _has(work / "framesK8", _render(
            scr.busy, "empty.psbt: 0 bytes, refusing")), \
            "K8: the empty file was never named on screen"
        signer.close_session(rpc)
        print("ok   K8: an empty file on the stick is named on screen, "
              "not waited on for ever")
        print("ALL PASS")
    finally:
        try:
            rpc.call("stop")
        except Exception:
            pass
        daemon.wait(timeout=30)
        if os.environ.get("KEEP"):
            print("kept:", work)
        else:
            shutil.rmtree(datadir, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
