"""Several keys, on the device: scripted dev-HAL sessions for map
e2e-before-testers tickets 03 and 10. Run: python3 tests/e2e_keys.py
(needs bitcoind)."""
import collections
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


def _grid_route(pages, start, target):
    """Shortest presses from one grid cell to another, found by search.

    A cell is (page, index). The rules are re-stated here from the
    SCREEN's shape alone (screens.charset_pages), not read out of
    main._grid_move, and the route is searched for rather than written
    down. A helper that encodes a route agrees with whatever the code does
    to produce that route; this one can only agree about the rules, and a
    disagreement shows up as a wrong character in the round trip
    (TESTING.md rule 2).
    """
    def moves(page, cur):
        n = len(pages[page])
        row, col, last = cur // 8, cur % 8, (n - 1) // 8
        if row == 0 and page > 0:
            prev = len(pages[page - 1])
            yield "u", (page - 1, min(((prev - 1) // 8) * 8 + col, prev - 1))
        else:
            yield "u", (page, max(0, cur - 8))
        if row == last and page + 1 < len(pages):
            yield "d", (page + 1, min(col, len(pages[page + 1]) - 1))
        else:
            yield "d", (page, min(n - 1, cur + 8))
        if cur == 0 and page > 0:
            yield "l", (page - 1, len(pages[page - 1]) - 1)
        else:
            yield "l", (page, max(0, cur - 1))
        if cur == n - 1 and page + 1 < len(pages):
            yield "r", (page + 1, 0)
        else:
            yield "r", (page, min(n - 1, cur + 1))

    seen, queue = {start: []}, collections.deque([start])
    while queue:
        at = queue.popleft()
        if at == target:
            return seen[at]
        for press, nxt in moves(*at):
            if nxt not in seen:
                seen[nxt] = seen[at] + [press]
                queue.append(nxt)
    raise AssertionError(f"no route from {start} to {target}")


def grid_presses(charset, want):
    """Presses that type `want` on the grid, without the closing press."""
    pages = scr.charset_pages(charset)
    at, out = (0, 0), []
    for ch in want:
        tp = next(i for i, pg in enumerate(pages) if ch in pg)
        target = (tp, pages[tp].index(ch))
        out += _grid_route(pages, at, target) + ["a"]
        at = target
    return "".join(out)


def text_keys(charset, want):
    """Presses that type `want` and commit it with the centre press."""
    return grid_presses(charset, want) + "p"


def home_press(tile, start=0):
    """Presses that pick a home tile, computed from the real 2x2 grid.

    HOME_TILES is laid out two to a row, and state_home wraps both axes.
    Counting these by hand is TESTING.md rule 11's defect in its other
    form: the script agrees with the code and neither agrees with the
    screen.
    """
    names = [label for label, _icon in scr.HOME_TILES]
    target = names.index(tile)
    row, col = divmod(target, 2)
    start_row, start_col = divmod(start, 2)
    return ("d" * ((row - start_row) % 2)
            + "r" * ((col - start_col) % 2) + "a")


def tools_press(action, start=0):
    """Presses that pick an action on the TOOLS screen."""
    names = [label for label, _note in scr.TOOLS_OPTIONS]
    return "d" * (names.index(action) - start) + "a"


def key_menu_press(action, start=0):
    """Presses that pick an action on one key's menu."""
    names = [label for label, _note in scr.KEY_MENU_OPTIONS]
    return "d" * (names.index(action) - start) + "a"


def keys_press(n_keys, action, start=0):
    """Presses that pick `action` on the KEYS screen, computed from the
    real menu rather than counted by hand.

    The screen lists the loaded keys, then screens.KEYS_ACTIONS. Every time
    that list or the key count changed, hand-written "dda" strings across
    eight sessions went quietly wrong, which is TESTING.md rule 2: the
    helper must not repeat the code's assumptions, it must derive them.
    """
    names = [label for label, _note in scr.KEYS_ACTIONS]
    target = n_keys + names.index(action)
    return "d" * (target - start) + "a"


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
        script1 = ("ra"                                  # Keys tile
                   + keys_press(0, "Scan a key")         # nothing loaded yet
                   + "a"         # accept the warning: the key loads
                   + "b"         # back to KEYS, which now lists it
                   + keys_press(1, "Scan a key")         # one key loaded now
                   + "a"         # accept the warning: refused, same key
                   + "a"         # dismiss the refusal
                   + "b"         # KEYS -> home
                   + "draa")     # settings -> power off
        r = run_device(datadir, script1, work / "framesK1", qr_key=key_a)
        assert r.returncode == 0, f"K1 rc={r.returncode}\n{r.stderr[-900:]}"
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
        script = ("ra" + keys_press(0, "Scan a key") + "a"   # Keys -> Scan -> warning
                  + "b" + "b"                     # key menu -> Keys -> home
                  + "a" + "a"                     # Sign tile: nobody owns it, dismiss
                  + "ra" + keys_press(1, "Type private key")
                  + text_keys("xprv", xprv_b)
                  + "b" + "b"                     # key menu -> Keys -> home
                  + "a"                           # Sign tile
                  + "a" + "a" + "ra")             # confirm B, sign, power off
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

        # ---- Session K3: every menu, walked (tickets 02, 05, 07) ----
        # Home is Scan, Keys, Tools, Settings. The Scan tile reads whatever
        # is in front of it, and here that is an xprv, so it loads the key
        # and lands on its menu with no detour. Then Receiving addresses,
        # Backup key on paper, Discard key. Then Tools, which holds the leak
        # check alone. Then Keys, New key, which is the first row there now.
        script = ("ra" + keys_press(0, "Scan a key") + "a"  # Keys -> Scan a key -> warning
                  + "da" + "dda" + "b"            # Receiving addresses -> page on, back
                  + "da" + "aaa"                  # Backup key -> 3 pages, paper is the only kind
                  + "da" + "ra"                   # Discard key -> confirm: DISCARD
                  + "da" + "a" + "c"              # Tools -> Check for leaks -> C leaves
                  + "b"                           # Tools -> home
                  + "ra" + keys_press(0, "New key")   # Keys -> New key, done
                  + "dda" + "aaa"                 # Backup key -> 3 pages
                  + "b" + "b"                     # key menu -> keys -> home
                  + "draa")
        r = run_device(datadir, script, work / "framesK3", qr_key=key_a)
        assert r.returncode == 0, f"K3 failed:\n{r.stderr[-1500:]}"
        fr = work / "framesK3"
        assert _has(fr, _render(scr.home, 0)), "K3: home without a key"
        assert _has(fr, _render(scr.key_menu, xfp_a, 0)), \
            "K3: scanning an xprv did not land on that key's menu"
        assert _has(fr, _render(scr.key_menu, xfp_a, 2)), "K3: Backup key highlighted"
        assert _has(fr, _render(scr.key_menu, xfp_a, 2)), \
            "K3: Backup key was never the selected row"
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
        assert _has(fr, _render(scr.keys_menu, [], 0)), \
            "K3: the KEYS screen offers New key first with nothing loaded"
        assert _has(fr, _render(scr.busy, "checking every way off this board…")), \
            "K3: the leak check never ran"
        assert _has(fr, _render(scr.key_menu, xfp_a, 1)), \
            "K3: Receiving addresses highlighted"
        # The address itself cannot be asserted here: this session ends
        # with the key discarded, so by the time these checks run there is
        # no wallet to ask what its first address was. The version of this
        # that tried was guarded by `if "corky" in listwallets`, which is
        # never true two lines above an assertion that no slot is loaded,
        # so it never ran at all (two-axis review, 2026-09-05). What CAN
        # be said is that the screen was reached with no chooser first.
        assert _has(fr, _render(scr.key_menu, xfp_a, 1)), \
            "K3: Receiving addresses was never the selected row"
        assert _has(fr, _render(scr.home, 2)), "K3: Tools tile highlighted"
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
        signer.close_session(rpc)
        stick5 = work / "stick5"; stick5.mkdir()
        # Script type, then HOW it leaves, then the key, then the addresses
        # to compare it against (map D2, revised on the board 2026-09-05).
        # This session takes the file route, because that is the one that
        # writes something a check can find. A completed export leaves the
        # flow rather than dropping back on the script type.
        script = ("ra" + "da" + "a"                   # Keys -> Scan a key -> warning
                  + "a"                               # Export public key
                  + "a"                               # SCRIPT TYPE -> Native segwit
                  + "dda"                             # EXPORT AS -> Wallet file
                  + "a" + "a"                         # channel -> dismiss
                  + "a" * 3                           # the three addresses
                  + "b" + "b" + "draa")
        r = run_device(datadir, script, work / "framesK5",
                       qr_key=key_a, stick=stick5)
        assert r.returncode == 0, (f"K5 failed rc={r.returncode}\n"
                                   f"STDERR:{r.stderr[-1200:]}\n"
                                   f"STDOUT:{r.stdout[-600:]}")
        fr5 = work / "framesK5"
        # The QR carries its policy name in the letterbox, so four codes
        # that look identical can be told apart (map ticket T0). The
        # caption is part of the shipped frame, so it is part of the
        # golden one.
        # The QR is not shown in this session, which takes the file route.
        # What the panel drew for it is proved against Sparrow's own zxing
        # in tests/sparrow/test_export_interop.py, which is the decoder
        # that matters (TESTING.md rule 8).
        xfp5, path5 = signer.origin_of(desc)
        assert xfp5 == xfp_a and path5.startswith("m/84h/"), \
            f"K5: Core wrote an unexpected origin: {xfp5} {path5}"
        # Every key presents all four since D6, and the wallet this session
        # used is already closed, so the list is EXPORT_ORDER rather than a
        # live lookup.
        assert _has(fr5, _render(scr.script_menu, signer.EXPORT_ORDER, 0)), \
            "K5: the script type was not asked before the QR"
        assert _has(fr5, _render(scr.export_options, 0)), \
            "K5: the export destination was never asked"
        # The addresses come AFTER a successful export, because they are
        # what you compare against the coordinator that just read it.
        # total=3 because the walk after an export is bounded, and the
        # screen draws a different bar for a list with a known end (D3).
        for i, addr in enumerate(want_addrs):
            assert _has(fr5, _render(scr.address_page, i, addr, "wpkh",
                                     total=3)), \
                f"K5: address {i} was not shown after the export"
        written = list(stick5.glob("corky-*-watch.dat"))
        assert len(written) == 1, f"K5: watch-only file not written: {written}"
        assert _has(fr5, _render(scr.result, ok=True, label="DONE",
                                 detail=f"{written[0].name} written")), \
            "K5: the device did not say where the file went, under DONE"
        assert not _has(fr5, _render(scr.result, ok=True,
                                     detail=f"{written[0].name} written")), \
            "K5: writing a wallet file still draws SIGNED"
        assert xfp_a in written[0].name, \
            f"K5: the file is not named by fingerprint: {written[0].name}"
        print(f"ok   K5: export -> script type, destination, "
              f"{written[0].name}, then the addresses to compare")

        # ---- Session K7: a bad file on the stick must not kill the app ----
        # ISSUES D18. corky.service has Restart=on-failure, so an exception
        # here is not one bad screen, it is a restart loop that lasts as
        # long as the file is on the stick. A tester will hit this in the
        # first hour.
        signer.close_session(rpc)
        stick7 = work / "stick7"; stick7.mkdir()
        (stick7 / "junk.psbt").write_bytes(b"this is not a transaction" * 8)
        script = ("ra" + keys_press(0, "Scan a key") + "a"  # Keys -> Scan -> warning
                  + "b" + "b"           # key menu -> Keys -> home
                  + "a"                 # Sign tile -> the stick
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
        script8 = ("ra" + keys_press(0, "Scan a key") + "a"
                   + "b" + "b"          # key menu -> Keys -> home
                   + "a"                # Sign tile -> the stick
                   + "a" + "c" + "draa")
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

        # ---- Session K9: VERIFY types the paper backup back in (Ben) ----
        # The last backup page has always offered VERIFY and always just
        # gone back to the menu. This is the flow it promises: type each
        # page back, get told exactly which characters are wrong, fix them
        # in place, and have Bitcoin Core confirm the whole key at the end.
        #
        # Page 1 is typed with a deliberate error at position 5, so the
        # verdict screen has to name that position and FIX has to land on
        # it. Rule 1: the key is a real one Core opens and signs with, and
        # every press is computed from the navigation rules, never counted.
        signer.close_session(rpc)
        pages9 = scr.text_pages(XPRV_A)
        assert len(pages9) == 3, f"K9: expected 3 backup pages, got {len(pages9)}"
        wrong_at = 5
        right = pages9[0][wrong_at]
        typo = "2" if right != "2" else "3"
        assert typo in scr.BASE58, "K9: the substitute is not a base58 character"
        page1_bad = pages9[0][:wrong_at] + typo + pages9[0][wrong_at + 1:]

        script = ("ra" + keys_press(0, "Scan a key") + "a"   # Keys -> Scan
                  + "dda"                        # Backup key: paper, no chooser
                  + "aa" + "ra"                  # 3 pages, then CHECK IT
                  + text_keys("xprv", page1_bad)  # page 1, one wrong
                  + "a"                          # verdict: FIX is selected
                  + grid_presses("xprv", right) + "p"   # overwrite, CHECK
                  + "a"                          # verdict: matches, go on
                  + text_keys("xprv", pages9[1]) + "a"
                  + text_keys("xprv", pages9[2]) + "a"
                  + "a"                          # Core's verdict, dismissed
                  + "b" + "b" + "draa")
        r = run_device(datadir, script, work / "framesK9", qr_key=key_a)
        assert r.returncode == 0, f"K9 failed:\n{r.stderr[-1500:]}"
        fr9 = work / "framesK9"
        # Every screen in the check shows key material, so hal.DevDisplay
        # blanks those frames: what the verdict SAID is asserted in
        # tests/test_backup_check.py, where the screens are rendered
        # directly. What this session proves is the part only a real
        # device and a real node can: the flow runs end to end on Core's
        # own key and Core agrees at the end.
        assert _has(fr9, _render(scr.verified,
                                 f"your paper opens\nkey {xfp_a.upper()}")), \
            "K9: Core never confirmed the typed key opens this wallet"
        # And Core really is the one deciding: the same call on a different
        # key must not agree, or the check above proves nothing.
        other = signer.master_xprv(rpc, wallet=signer.generate_wallet(rpc))
        assert (signer.identity_of_key(rpc, XPRV_A)
                != signer.identity_of_key(rpc, other)), \
            "K9: Core reads two different keys as the same key"
        try:
            signer.identity_of_key(rpc, page1_bad + pages9[0][:1])
            raise AssertionError("K9: Core accepted a mistyped key")
        except RuntimeError as exc:
            assert XPRV_A[:20] not in str(exc) and typo not in str(exc)[:8], \
                f"K9: the refusal leaked key material: {exc}"
        signer.close_session(rpc)
        print("ok   K9: VERIFY types the backup back, names the wrong "
              "character, and Core confirms the key")

        # ---- Session K10: a key survives being walked away from --------
        # Map ticket N3, in Ben's words: keys "need to persist unless
        # turned off essentially". tests/test_key_persistence.py proves
        # nothing drops one on a clock, and walks the menus against a
        # stub. What it could not do is the half the ticket actually asks
        # for: that the key which comes back is "still able to sign".
        #
        # So: load a key, go somewhere else entirely, come back, and sign
        # a real transaction that only that key owns. If anything expired
        # it in between, the signature does not complete.
        # watchB already holds A's public descriptors and mined the chain,
        # so it can both fund an address of A's and take the change back.
        signer.close_session(rpc)
        name10 = signer.open_session_xprv(rpc, XPRV_A)
        pubs10 = signer.public_descriptors(rpc, wallet=name10)
        rpc.call("createwallet", "watch10", True, True, "", False, True)
        rpc.call("importdescriptors",
                 [{"desc": d, "active": True, "timestamp": "now",
                   "range": [0, 200], "internal": "/1/*" in d}
                  for d in pubs10], wallet="watch10")
        # watchB is watch-only and cannot spend, so K10 mines its own
        # coins into a wallet that holds keys.
        rpc.call("createwallet", "miner10")
        mine10 = rpc.call("getnewaddress", wallet="miner10")
        rpc.call("generatetoaddress", 101, mine10, wallet="miner10")
        fund10 = rpc.call("getnewaddress", wallet="watch10")
        rpc.call("sendtoaddress", fund10, 1.0, wallet="miner10")
        rpc.call("generatetoaddress", 1, mine10, wallet="miner10")
        back10 = rpc.call("getnewaddress", wallet="miner10")
        psbt10 = rpc.call("walletcreatefundedpsbt", [],
                          [{back10: 0.4}], 0, {"fee_rate": 5}, True,
                          wallet="watch10")["psbt"]
        frames10 = work / "psbt10.txt"
        frames10.write_text("\n".join(qrchannel.psbt_to_frames(psbt10)))
        signer.close_session(rpc)

        script = ("ra" + keys_press(0, "Scan a key") + "a"   # Keys -> Scan
                  + "b" + "b"                     # key menu -> Keys -> home
                  # walk away: Tools, the leak check, out again
                  + "da" + "a" + "c" + "b"
                  # and Settings, About, out again
                  + "dra" + "da" + "a" + "b"
                  # back to the key, through its whole menu, and out
                  + "ra" + "a" + "b" + "b"
                  # now sign, with the key that has been sitting there
                  + "a" + "a" + "ra")
        r = run_device(datadir, script, work / "framesK10",
                       qr_key=key_a, qr_psbt=frames10)
        assert r.returncode == 0, f"K10 failed:\n{r.stderr[-1500:]}"
        last10 = _shots(work / "framesK10")[-1].read_bytes()
        assert any(last10 == _render(scr.result, ok=True,
                                     detail=f"shown as {n} QR frames",
                                     actions_sel=1)
                   for n in range(1, 90)), \
            "K10: the key did not sign after being walked away from"
        left10 = [w for w in rpc.call("listwallets") if w in signer.SLOTS]
        assert not left10, f"K10: a key survived power off: {left10}"
        print("ok   K10: a key walked away from and returned to still signs, "
              "and is gone at power off")

        # ---- Session K11: Check an address, which had no test at all ----
        # Audit A5 measured it: the whole Tools feature was uncovered, 27
        # statements including the branch that says nobody owns it. It
        # answers the one question a coordinator cannot answer for you,
        # which is whether the address on that other screen belongs to a
        # key in your hand, so getting it wrong is how someone pays a
        # stranger.
        signer.close_session(rpc)
        name11 = signer.open_session_xprv(rpc, XPRV_A)
        mine11 = signer.receive_addresses(rpc, name11, "wpkh", 1)[0]
        not_mine11 = rpc.call("getnewaddress", wallet="watchB")
        signer.close_session(rpc)

        for label, addr, want in (
                ("an address the key owns", mine11, "owned"),
                ("an address it does not", not_mine11, "not owned")):
            # Two codes, in the order the camera sees them: the key to
            # load, then the address to check. One file with one code
            # could not do this, so the first version of K11 scanned the
            # ADDRESS as the key, loaded nothing, and never reached the
            # verdict screen (devil's advocate on A5, 2026-09-06).
            qr11 = work / f"addr-{want.replace(' ', '')}.txt"
            qr11.write_text(f"{XPRV_A}\n{addr}\n")
            script11 = ("ra" + keys_press(0, "Scan a key") + "a"  # load A
                        + "b" + "b"                  # key menu -> Keys -> home
                        + home_press("tools")
                        + tools_press("Check an address")
                        + "a"                        # dismiss the verdict
                        + "b" + "draa")
            r11 = run_device(datadir, script11, work / f"framesK11-{want}",
                             qr_key=qr11)
            assert r11.returncode == 0, \
                f"K11 ({label}) failed:\n{r11.stderr[-900:]}"
            fr11 = work / f"framesK11-{want}"
            owned = _has(fr11, _render(
                scr.verified, f"key {xfp_a.upper()}\nowns this address"))
            refused = _has(fr11, _render(
                scr.result, ok=False, label="FAILED",
                detail="no loaded key owns that address"))
            if want == "owned":
                assert owned and not refused, \
                    f"K11: {label} was not recognised as owned"
            else:
                assert refused and not owned, (
                    f"K11: {label} was claimed as owned, which is how "
                    "somebody pays a stranger")
        signer.close_session(rpc)
        print("ok   K11: Check an address says which key owns one, and "
              "refuses one no key owns")

        # ---- Session K12: walk every policy on the address screen ----
        # Audit A5 measured _next_kind as never called by anything: the
        # LEFT/RIGHT walk that reaches a legacy or nested address is the
        # whole reason the chooser was taken off the front of this screen
        # (Ben, 2026-09-05), and no test had ever pressed either key. A
        # wrong step here shows the operator an address from a policy the
        # screen does not name, which is how a receive goes to a script
        # the coordinator is not watching.
        name12 = signer.open_session_xprv(rpc, XPRV_A)
        order12 = signer.available_kinds(rpc, name12)
        first12 = {k: signer.receive_addresses(rpc, name12, k, 1)[0]
                   for k in order12}
        signer.close_session(rpc)
        # RIGHT once per policy walks the whole ring and comes home; the
        # final LEFT proves the walk goes both ways.
        script12 = ("ra" + keys_press(0, "Scan a key") + "a"
                    # loading a key lands on that key's own menu
                    + key_menu_press("Receiving addresses")
                    + "r" * len(order12)        # all the way round
                    + "l"                       # and one step back
                    + "b" + "b" + "b" + "draa")
        r12 = run_device(datadir, script12, work / "framesK12", qr_key=key_a)
        assert r12.returncode == 0, f"K12 failed:\n{r12.stderr[-900:]}"
        # Every policy's own first address must have been painted, each
        # under its own title. Rule 11: assert what the screen says, not
        # the number of steps taken to get there.
        missing12 = [k for k in order12
                     if not _has(work / "framesK12",
                                 _render(scr.address_page, 0, first12[k], k))]
        assert not missing12, (
            f"K12: LEFT/RIGHT never showed these policies: {missing12}; "
            f"the walk covers {order12}")
        signer.close_session(rpc)
        print(f"ok   K12: LEFT/RIGHT walks all {len(order12)} policies on "
              "the address screen and returns to the first")
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
