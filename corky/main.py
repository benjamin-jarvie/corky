"""Corky's session state machine: the program the device boots into.

States:
  HOME -> SEED MENU (A-14's modes: SeedQR / word entry / descriptor / xprv)
       -> wallet open in Core -> LOAD PSBT (file channel or QR)
       -> REVIEW -> sign -> RESULT -> power off.

Every screen comes from screens.py, every wallet operation from signer.py,
every transfer from qrchannel/filechannel. This module holds no crypto and
parses no untrusted bytes; it is the traffic cop.

QR input arrives through a QrSource: on the device that is the camera (M1);
in dev mode it reads payloads from files so every state is exercisable
without hardware.

Dev mode:
    python3 corky/main.py --dev --datadir <dir> --chain regtest \
        --script "<keys>" [--stick-dir DIR] [--qr-psbt FILE]
        [--qr-key FILE] [--passphrase STR] [--frames-dir DIR]
Keys: u/d = up/down, l/r = left/right, a = select, b = back, c = reject.
"""

import argparse
import string
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signer
import screens
import codex32
import filechannel
import qrchannel
import seedqr
import hal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shim"))
from bip39_shim import load_wordlist  # noqa: E402  (word entry candidates)


MAX_KEY_PAYLOAD = 4096          # a descriptor set is a few hundred chars
_KEY_CHARSET = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "()[]{}#*'/,:;h<>@?!&+=-_.\n\r ")


class CameraQrSource:
    """Device QR source. Camera capture is the M1 deliverable; until it
    lands, QR entry paths report their absence instead of dead-ending."""

    def scan_key(self):
        raise RuntimeError("camera not yet wired (M1); use the USB stick")

    def scan_psbt_frames(self):
        return iter(())


class DevQrSource:
    """Dev stand-in for the camera: returns file contents as scan payloads."""

    def __init__(self, key_path=None, psbt_path=None):
        self.key_path = key_path
        self.psbt_path = psbt_path

    def scan_key(self):
        """One payload: SeedQR digits, xprv or descriptor text."""
        if not self.key_path:
            raise RuntimeError("no --qr-key provided to dev session")
        return Path(self.key_path).read_bytes()

    def scan_psbt_frames(self):
        """Iterates UR frames (one per line in the dev file)."""
        if not self.psbt_path:
            return iter(())
        return iter(Path(self.psbt_path).read_text().split())


class Session:
    def __init__(self, display, buttons, rpc, stick_dir=None, qr_source=None,
                 passphrase="", animate=False):
        self.display = display
        self.animate = animate
        self.buttons = buttons
        self.rpc = rpc
        self.stick_dir = Path(stick_dir) if stick_dir else None
        self.qr = qr_source or DevQrSource()
        self.passphrase = passphrase
        self.w, self.h = display.width, display.height
        self.wordlist = load_wordlist()

    # -- flow --------------------------------------------------------------

    def run(self):
        try:
            self.state_home()
        finally:
            try:
                signer.close_session(self.rpc)
            except Exception:
                pass

    def _busy(self, message):
        """Paint the wait frame; on the device a thread keeps the mark
        turning until the returned stop() runs. The dev harness paints one
        static frame so scripted sessions stay deterministic."""
        self.display.show(screens.busy(self.w, self.h, message))
        if not self.animate:
            return lambda: None
        stop = threading.Event()

        def turn():
            phase = 1
            while not stop.wait(0.15):
                self.display.show(screens.busy(self.w, self.h, message,
                                               phase))
                phase += 1

        worker = threading.Thread(target=turn, daemon=True)
        worker.start()

        def halt():
            stop.set()
            worker.join(timeout=1)
        return halt

    def state_home(self):
        # generate key | load key | tools | power off
        selected = 0
        while True:
            self.display.show(screens.home(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % 4
            elif key == "d":
                selected = (selected + 1) % 4
            elif key == "c":
                return
            if key == "a":
                if selected == 3:      # power off
                    return
                opened = [self._seed_generate,   # generate key
                          self.state_seed_menu,  # load key
                          self.state_tools       # tools
                          ][selected]()
                if opened:
                    # A key is now loaded in Core: go straight on to loading
                    # a PSBT rather than back to HOME.
                    self.state_load()
                    return

    # -- seed entry: the three A-14 modes plus SeedQR ---------------------

    def state_seed_menu(self) -> bool:
        selected = 0
        while True:
            self.display.show(screens.seed_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % 6
            elif key == "d":
                selected = (selected + 1) % 6
            elif key == "b":
                return False
            elif key == "a":
                try:
                    return [self._seed_descriptor, self._seed_xprv,
                            self._seed_codex32_scan, self._seed_codex32_type,
                            self._seed_seedqr, self._seed_words][selected]()
                except Exception as exc:
                    # Hold the message: without a key wait the home screen
                    # repaints immediately and the user sees only a flicker.
                    self.display.show(screens.result(
                        self.w, self.h, ok=False, detail=str(exc)[:60]))
                    self.buttons.read()
                    return False

    def _seed_generate(self):
        """A-19 from the front door (Ben, 2026-09-01): Core generates, the
        backup shows, the session stays open. Same flow as the tools entry."""
        return bool(self._tool_generate())

    def _open_words(self, mnemonic):
        stop = self._busy("checking words, deriving in Core…")
        try:
            signer.open_session(self.rpc, mnemonic, self.passphrase)
        finally:
            stop()
        return True

    def _seed_seedqr(self):
        self.display.show(screens.busy(self.w, self.h, "scan your SeedQR…"))
        raw = self.qr.scan_key()
        if len(raw) > MAX_KEY_PAYLOAD:
            raise RuntimeError("SeedQR payload too large, refusing")
        return self._open_words(seedqr.decode(raw))

    def _seed_words(self):
        """Button-driven word entry (see _collect_words for the loop)."""
        words = self._collect_words()
        if not words:
            return False
        return self._open_words(" ".join(words))


    def _pick_seed_length(self):
        selected = 0
        while True:
            self.display.show(screens.seed_length(self.w, self.h, selected))
            key = self.buttons.read()
            if key in ("u", "d"):
                selected = 1 - selected
            elif key == "a":
                return 12 if selected == 0 else 24
            elif key == "b":
                return None

    def _pick_candidate(self, candidates, word_index, total):
        selected = 0
        while True:
            marked = tuple(candidates[selected:] + candidates[:selected])
            self.display.show(screens.seed_entry(
                self.w, self.h, word_index, total,
                candidates[selected], marked), sensitive=True)
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % len(candidates)
            elif key == "d":
                selected = (selected + 1) % len(candidates)
            elif key == "a":
                return candidates[selected]
            elif key == "b":
                return None

    def _keymaterial(self, kind):
        """Warning screen (A-14: the QR IS the wallet), then scan."""
        self.display.show(screens.keymaterial_warning(self.w, self.h, kind))
        while True:
            key = self.buttons.read()
            if key == "a":
                payload = self._scan_key_guarded().strip()
                self.display.show(screens.busy(self.w, self.h,
                                               "importing into Core…"))
                return payload
            if key in ("b", "c"):
                return None

    def _seed_descriptor(self):
        payload = self._keymaterial("descriptor")
        if payload is None:
            return False
        signer.open_session_descriptors(self.rpc, payload.splitlines())
        return True

    def _seed_xprv(self):
        payload = self._keymaterial("xprv")
        if payload is None:
            return False
        signer.open_session_xprv(self.rpc, payload)
        return True

    # -- codex32 (A-18): import, entry, tools ------------------------------

    @staticmethod
    def _threshold_of(share):
        ch = share[3].lower()
        return int(ch) if ch.isdigit() and ch != "1" else 0

    def _codex32_open(self, shares):
        """Open the wallet from one codex32 secret or k shares. Pure BIP32:
        seed -> xprv via the frozen modules; Core does the rest."""
        self.display.show(screens.busy(self.w, self.h,
                                       "recovering seed, deriving in Core…"))
        if len(shares) == 1 and self._threshold_of(shares[0]) == 0:
            _, seed = codex32.decode_secret(shares[0])
        else:
            secret = codex32.recover(shares)
            _, seed = codex32.decode_secret(secret)
        xprv = codex32.to_xprv(seed, mainnet=(self.rpc.chain == "main"))
        signer.open_session_xprv(self.rpc, xprv)
        return True

    def _scan_key_guarded(self):
        """The single guarded reader for camera key payloads: length cap
        and charset check before anything downstream sees it (PLAN A-11)."""
        raw = self.qr.scan_key()
        if len(raw) > MAX_KEY_PAYLOAD:
            raise RuntimeError("key payload too large, refusing")
        text = raw.decode("ascii")
        if not set(text) <= _KEY_CHARSET:
            raise RuntimeError("key payload has invalid characters")
        return text

    def _seed_codex32_scan(self):
        self.display.show(screens.codex32_scan(self.w, self.h))
        payload = self._scan_key_guarded()
        shares = [ln.strip() for ln in payload.splitlines() if ln.strip()]
        shares = [codex32.validate(sh) for sh in shares]
        return self._codex32_open(shares)

    def _seed_codex32_type(self):
        shares = []
        need = None
        self._retry_share = None
        while need is None or len(shares) < need:
            self.display.show(screens.codex32_shares(
                self.w, self.h,
                tuple(sh[8].upper() for sh in shares), need or "?"))
            entered = self._codex32_entry_one(self._retry_share)
            self._retry_share = None
            if entered is None:
                return False
            try:
                sh = codex32.validate(entered)
            except codex32.Codex32Error as exc:
                # Bad checksum or format: offer edit-in-place on the same
                # string (A re-enters keeping it, B/C abort).
                self.display.show(screens.codex32_error(
                    self.w, self.h, str(exc)[:48]))
                if self.buttons.read() != "a":
                    return False
                self._retry_share = entered
                continue
            if sh in shares:
                # A valid but already-held share: retype fresh, not edit.
                self.display.show(screens.codex32_error(
                    self.w, self.h, "duplicate share"))
                if self.buttons.read() != "a":
                    return False
                continue
            t = self._threshold_of(sh)
            if t == 0:
                return self._codex32_open([sh])
            need = need or t
            shares.append(sh)
            self.display.show(screens.codex32_verified(
                self.w, self.h, f"share {len(shares)} of {need}"))
            self.buttons.read()
        return self._codex32_open(shares)

    def _codex32_entry_one(self, prefill=None):
        """Grid entry with an editable caret.

        U/D move the grid row, L/R move the CARET along the typed string
        (the character shown in gold). A writes the grid letter at the caret
        and advances, so fresh typing at the end appends and a caret parked
        mid-string overwrites one character in place. B deletes at the caret,
        C finishes (empty = abort). `prefill` re-opens a rejected share so
        only the wrong character is fixed, not all of it retyped. The 'ms1'
        prefix is fixed and the caret never enters it."""
        entered = prefill if prefill else "ms1"
        caret, cursor = len(entered), 0
        while True:
            self.display.show(screens.codex32_entry(
                self.w, self.h, entered, cursor, caret), sensitive=True)
            key = self.buttons.read()
            if key == "u":
                cursor = (cursor - 8) % 32
            elif key == "d":
                cursor = (cursor + 8) % 32
            elif key == "l":
                cursor = (cursor - 1) % 32
            elif key == "r":
                cursor = (cursor + 1) % 32
            elif key == "p":
                # Center-press walks the edit caret left, wrapping past the
                # start back to the append slot: reach any character to fix
                # it with the grid, using one key.
                caret = len(entered) if caret <= 3 else caret - 1
            elif key == "a":
                ch = screens.BECH32_CHARSET[cursor]
                if caret == len(entered):
                    entered += ch
                else:
                    entered = entered[:caret] + ch + entered[caret + 1:]
                caret += 1
            elif key == "b":
                if caret < len(entered):
                    entered = entered[:caret] + entered[caret + 1:]
                elif len(entered) > 3:
                    entered = entered[:-1]
                    caret = len(entered)
            elif key == "c":
                return entered if len(entered) > 3 else None

    def state_tools(self) -> bool:
        """Returns True only when a tool left a wallet open in Core."""
        selected = 0
        tools = [self._tool_verify, self._tool_backup]
        while True:
            self.display.show(screens.tools_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % len(tools)
            elif key == "d":
                selected = (selected + 1) % len(tools)
            elif key == "b":
                return False
            elif key == "a":
                try:
                    return bool(tools[selected]())
                except Exception as exc:
                    self.display.show(screens.result(
                        self.w, self.h, ok=False, detail=str(exc)[:60]))
                    self.buttons.read()
                return False

    def _tool_verify(self):
        """The zero-re-exposure check: checksum only, nothing derived.
        Entry is by grid; C on an empty grid aborts (it must not fall
        through to the camera, which would dead-end on hardware)."""
        prefill = None
        while True:
            entered = self._codex32_entry_one(prefill)
            if entered is None:
                return
            try:
                codex32.validate(entered)
                self.display.show(screens.codex32_verified(
                    self.w, self.h, "checksum valid"))
                self.buttons.read()
                return
            except codex32.Codex32Error as exc:
                self.display.show(screens.codex32_error(
                    self.w, self.h, str(exc)[:48]))
                # A re-enters keeping the string (RE-ENTER), B/C abort.
                if self.buttons.read() != "a":
                    return
                prefill = entered

    def _tool_backup(self):
        """Words in -> codex32 out (one string, or a 2-of-3 split).
        Split randomness is derived deterministically from the seed itself
        (HMAC-SHA512, domain-separated): no device RNG exists or is used,
        per the no-entropy-story doctrine; deterministic shares re-derive
        identically, which also makes the backup reproducible."""
        words = self._collect_words()
        if not words:
            return
        from bip39_shim import mnemonic_to_seed
        # The FULL 64-byte BIP39 seed. Truncating to 32 would encode a
        # different master key than the words produce, so a restore from
        # the share would silently open a DIFFERENT WALLET. codex32
        # (BIP93) encodes 16-64 byte seeds, so no truncation is needed.
        seed = mnemonic_to_seed(" ".join(words), self.passphrase)
        ident = codex32.derive_identifier(seed)
        secret = codex32.encode_secret(ident, seed, threshold=0)
        choice = self._pick_split()
        if choice is None:
            return
        if choice == 0:
            outputs = [secret]
        else:
            outputs = codex32.split(seed, 2, 3, ident,
                                    codex32.derive_split_entropy(seed, 2, 3))
        for i, out in enumerate(outputs):
            if not self._show_backup(out.upper(), i + 1, len(outputs)):
                return
        self.display.show(screens.result(
            self.w, self.h, ok=True,
            detail="transcribed; kit worksheets own paper"))
        self.buttons.read()

    def _tool_generate(self):
        """Seed generation and usage EXACTLY as a Bitcoin Core wallet
        (PLAN A-19). Core's createwallet makes the master key with Core's
        own RNG; Corky signs with that very wallet, and the backup shown
        is Core's master xprv read verbatim from Core's descriptors.
        Nothing of ours sits between Core's RNG and the paper. Restore is
        the existing xprv entry mode (pure Core). The tradeoff screen
        says plainly that software entropy cannot be audited as it runs
        and that cards or dice remain the default.
        """
        sel, scroll = 1, 0
        max_scroll = len(screens.GENERATE_LINES) - screens.GEN_VISIBLE
        while True:
            self.display.show(screens.generate_warning(
                self.w, self.h, sel, scroll))
            key = self.buttons.read()
            if key in ("l", "r"):
                sel = 1 - sel
            elif key == "d":
                scroll = min(scroll + 1, max_scroll)
            elif key == "u":
                scroll = max(scroll - 1, 0)
            elif key == "a":
                if sel == 0:
                    return False
                break
            elif key in ("b", "c"):
                return False
        stop = self._busy("Bitcoin Core is generating your key…")
        try:
            xprv = signer.generate_wallet(self.rpc)
        finally:
            stop()
        # The backup IS the master xprv, in Core's own encoding, shown in
        # 4-char groups for transcription. No split option: an xprv is a
        # BIP32 node, not a seed, so codex32 cannot encode it; guardians
        # of an xprv backup use Kaitiaki or the kit's practices instead.
        if not self._show_backup(xprv, 1, 1):
            signer.close_session(self.rpc)
            return False
        address = self.rpc.call("getnewaddress", wallet=signer.WALLET)
        self.display.show(screens.codex32_verified(
            self.w, self.h,
            "first address  " + address[:14] + "…" + address[-6:]))
        self.buttons.read()
        return True

    def _show_backup(self, text, index, total):
        """Show one backup string across as many screenfuls as it needs.

        A 127-character codex32 secret and Core's 111-character master xprv
        both overrun one screen; drawing them as one column asked the user to
        transcribe characters that were never on the panel. A advances and
        finishes on the last page, B or UP re-shows the previous page for
        checking against paper, C aborts. Returns False on abort."""
        pages = screens.share_pages(text)
        i = 0
        while True:
            self.display.show(screens.codex32_share_display(
                self.w, self.h, pages[i], index, total,
                page=i, pages=len(pages)), sensitive=True)
            key = self.buttons.read()
            if key == "c":
                return False
            if key in ("b", "u"):
                if i == 0:
                    return False    # nothing earlier: BACK is ABORT here
                i -= 1
            elif key == "a":
                if i + 1 == len(pages):
                    return True
                i += 1

    def _pick_split(self):
        selected = 0
        while True:
            self.display.show(screens.codex32_split_choice(
                self.w, self.h, selected))
            key = self.buttons.read()
            if key in ("u", "d"):
                selected = 1 - selected
            elif key == "a":
                return selected
            elif key == "b":
                return None

    def _collect_words(self):
        total = self._pick_seed_length()
        if total is None:
            return None
        words = []
        while len(words) < total:
            prefix, cursor = "", 0
            while True:
                candidates = [w for w in self.wordlist
                              if w.startswith(prefix)][:4]
                self.display.show(screens.seed_entry(
                    self.w, self.h, len(words) + 1, total,
                    prefix + string.ascii_lowercase[cursor],
                    tuple(candidates)), sensitive=True)
                key = self.buttons.read()
                if key == "u":
                    cursor = (cursor - 1) % 26
                elif key == "d":
                    cursor = (cursor + 1) % 26
                elif key == "a":
                    prefix += string.ascii_lowercase[cursor]
                    cursor = 0
                elif key == "b":
                    prefix = prefix[:-1]
                elif key == "c":
                    return None
                elif key == "r" and candidates:
                    word = self._pick_candidate(candidates, len(words) + 1,
                                                total)
                    if word:
                        words.append(word)
                        break
        return words

    # -- PSBT load: stick first, then QR frames ---------------------------

    def state_load(self):
        self.display.show(screens.busy(self.w, self.h,
                                       "insert stick or show QR…"))
        psbt, source = None, None
        qr_frames = None
        assembler = qrchannel.FrameAssembler()
        while psbt is None:
            if self.stick_dir:
                found = filechannel.find_unsigned(self.stick_dir)
                if found and filechannel.wait_stable(found[0]):
                    psbt, source = filechannel.read_psbt(found[0]), found[0]
                    break
            # The QR source must be re-obtainable: a camera is a continuous
            # stream, and the dev file source is re-read after exhaustion so
            # an incomplete UR assembly can complete on a later pass.
            if qr_frames is None:
                qr_frames = self.qr.scan_psbt_frames()
            progress_before = assembler.progress
            for frame in qr_frames:
                try:
                    if assembler.feed(frame):
                        psbt = assembler.psbt_b64
                        break
                except qrchannel.QrChannelError:
                    continue
            else:
                qr_frames = None
            # Progress, not mere frame consumption, counts as advancing —
            # otherwise an incomplete dev file spins at 50Hz and the
            # back/reject buttons are never polled.
            advanced = psbt is not None or assembler.progress > progress_before
            if psbt is not None:
                break
            if not advanced:
                key = self.buttons.read()
                if key in ("b", "c"):
                    return
            time.sleep(0.02)
        self.state_review(psbt, source)

    def state_review(self, psbt, source):
        info = signer.describe_psbt(self.rpc, psbt)
        if info["fee_btc"] is None:
            # Missing input data: refuse loudly instead of crashing (a fee
            # the device cannot show is a transaction it must not sign).
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="PSBT lacks input data; fee unknown; refused"))
            return
        outs = [(o["address"], o["amount_btc"]) for o in info["outputs"]]
        pages = max(1, (len(outs) + 1) // 2)
        page, seen, refused, sel = 0, {0}, False, 1
        while True:
            self.display.show(screens.review(
                self.w, self.h, outs, info["fee_btc"],
                info["input_count"], input_total_btc=info["input_total_btc"],
                page=page, unseen_pages=refused, actions_sel=sel))
            key = self.buttons.read()
            if key in ("l", "r"):
                sel = 1 - sel
            elif key == "d":
                page, refused = (page + 1) % pages, False
                seen.add(page)
            elif key == "u":
                page, refused = (page - 1) % pages, False
                seen.add(page)
            elif key == "a" and sel == 1:
                if len(seen) < pages:
                    # Every output must have been on screen before signing.
                    page, refused = (page + 1) % pages, True
                    seen.add(page)
                    continue
                self.state_sign(psbt, source)
                return
            elif key == "c" or (key == "a" and sel == 0):
                self.display.show(screens.result(
                    self.w, self.h, ok=False, detail="rejected by user"))
                return

    def state_sign(self, psbt, source):
        stop = self._busy("signing in Core…")
        try:
            signed = signer.sign_psbt(self.rpc, psbt)
        finally:
            stop()
        if not signed["complete"]:
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="wallet cannot complete this PSBT"))
            return
        if source is not None:
            out = filechannel.write_signed(source, signed["psbt"])
            detail = f"{out.name} written"
        else:
            frames = qrchannel.psbt_to_frames(signed["psbt"])
            for img in qrchannel.frames_to_images(frames):
                self.display.show(img.resize((self.w, self.h)))
            detail = f"shown as {len(frames)} QR frames"
        self.display.show(screens.result(self.w, self.h, ok=True,
                                         detail=detail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--chain", default="main")
    ap.add_argument("--script", default="")
    ap.add_argument("--stick-dir")
    ap.add_argument("--qr-psbt", help="dev: file of UR frames, one per line")
    ap.add_argument("--qr-key", help="dev: file with SeedQR digits/xprv/descriptor")
    ap.add_argument("--passphrase", default="")
    ap.add_argument("--frames-dir", default="frames")
    args = ap.parse_args()

    rpc = signer.Rpc(args.datadir, chain=args.chain)
    if args.dev:
        display = hal.DevDisplay(args.frames_dir)
        buttons = hal.DevButtons(args.script)
        qr = DevQrSource(key_path=args.qr_key, psbt_path=args.qr_psbt)
    else:
        display = hal.DeviceDisplay()
        buttons = hal.DeviceButtons()
        qr = CameraQrSource()

    Session(display, buttons, rpc, stick_dir=args.stick_dir, qr_source=qr,
            animate=not args.dev,
            passphrase=args.passphrase).run()


if __name__ == "__main__":
    main()
