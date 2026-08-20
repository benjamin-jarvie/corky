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
                 passphrase=""):
        self.display = display
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

    def state_home(self):
        self.display.show(screens.home(self.w, self.h))
        while True:
            key = self.buttons.read()
            if key == "a":
                if self.state_seed_menu():
                    self.state_load()
                    return
                self.display.show(screens.home(self.w, self.h))
            elif key == "r":
                self.state_tools()
                self.display.show(screens.home(self.w, self.h))
            elif key == "c":
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
                    return [self._seed_seedqr, self._seed_words,
                            self._seed_codex32_scan, self._seed_codex32_type,
                            self._seed_descriptor, self._seed_xprv][selected]()
                except Exception as exc:
                    self.display.show(screens.result(
                        self.w, self.h, ok=False, detail=str(exc)[:60]))
                    return False

    def _open_words(self, mnemonic):
        self.display.show(screens.busy(self.w, self.h,
                                       "checking words, deriving in Core…"))
        signer.open_session(self.rpc, mnemonic, self.passphrase)
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
        while need is None or len(shares) < need:
            self.display.show(screens.codex32_shares(
                self.w, self.h,
                tuple(sh[8].upper() for sh in shares), need or "?"))
            entered = self._codex32_entry_one()
            if entered is None:
                return False
            try:
                sh = codex32.validate(entered)
                if sh in shares:
                    raise codex32.Codex32Error("duplicate share")
            except codex32.Codex32Error as exc:
                self.display.show(screens.codex32_error(
                    self.w, self.h, str(exc)[:48]))
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

    def _codex32_entry_one(self):
        """Grid entry: d-pad moves the 4x8 cursor, A picks, B deletes,
        C finishes (empty = abort)."""
        entered, cursor = "ms1", 0
        while True:
            self.display.show(screens.codex32_entry(
                self.w, self.h, entered, cursor), sensitive=True)
            key = self.buttons.read()
            if key == "u":
                cursor = (cursor - 8) % 32
            elif key == "d":
                cursor = (cursor + 8) % 32
            elif key == "l":
                cursor = (cursor - 1) % 32
            elif key == "r":
                cursor = (cursor + 1) % 32
            elif key == "a":
                entered += screens.BECH32_CHARSET[cursor]
            elif key == "b":
                entered = entered[:-1] if len(entered) > 3 else entered
            elif key == "c":
                return entered if len(entered) > 3 else None

    def state_tools(self):
        selected = 0
        while True:
            self.display.show(screens.tools_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key in ("u", "d"):
                selected = 1 - selected
            elif key == "b":
                return
            elif key == "a":
                try:
                    [self._tool_verify, self._tool_backup][selected]()
                except Exception as exc:
                    self.display.show(screens.result(
                        self.w, self.h, ok=False, detail=str(exc)[:60]))
                    self.buttons.read()
                return

    def _tool_verify(self):
        """The zero-re-exposure check: checksum only, nothing derived.
        Entry is by grid; C on an empty grid aborts (it must not fall
        through to the camera, which would dead-end on hardware)."""
        entered = self._codex32_entry_one()
        if entered is None:
            return
        try:
            codex32.validate(entered)
            self.display.show(screens.codex32_verified(
                self.w, self.h, "checksum valid"))
        except codex32.Codex32Error as exc:
            self.display.show(screens.codex32_error(
                self.w, self.h, str(exc)[:48]))
        self.buttons.read()

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
            self.display.show(screens.codex32_share_display(
                self.w, self.h, out.upper(), i + 1, len(outputs)),
                sensitive=True)
            if self.buttons.read() == "c":
                return
        self.display.show(screens.result(
            self.w, self.h, ok=True,
            detail="transcribed; kit worksheets own paper"))
        self.buttons.read()

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
                detail="PSBT lacks input data; fee unknown — refused"))
            return
        outs = [(o["address"], o["amount_btc"]) for o in info["outputs"]]
        pages = max(1, (len(outs) + 2) // 3)
        page, seen = 0, {0}
        while True:
            self.display.show(screens.review(
                self.w, self.h, outs, info["fee_btc"],
                info["input_count"], input_total_btc=info["input_total_btc"],
                page=page))
            key = self.buttons.read()
            if key == "d":
                page = (page + 1) % pages
                seen.add(page)
            elif key == "u":
                page = (page - 1) % pages
                seen.add(page)
            elif key == "a":
                if len(seen) < pages:
                    # Every output must have been on screen before signing.
                    page = (page + 1) % pages
                    seen.add(page)
                    continue
                self.state_sign(psbt, source)
                return
            elif key == "c":
                self.display.show(screens.result(
                    self.w, self.h, ok=False, detail="rejected by user"))
                return

    def state_sign(self, psbt, source):
        self.display.show(screens.busy(self.w, self.h, "signing in Core…"))
        signed = signer.sign_psbt(self.rpc, psbt)
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
            passphrase=args.passphrase).run()


if __name__ == "__main__":
    main()
