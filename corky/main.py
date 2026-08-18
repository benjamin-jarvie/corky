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
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signer
import screens
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
            elif key == "c":
                return

    # -- seed entry: the three A-14 modes plus SeedQR ---------------------

    def state_seed_menu(self) -> bool:
        selected = 0
        while True:
            self.display.show(screens.seed_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % 4
            elif key == "d":
                selected = (selected + 1) % 4
            elif key == "b":
                return False
            elif key == "a":
                try:
                    return [self._seed_seedqr, self._seed_words,
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
        return self._open_words(seedqr.decode(self.qr.scan_key()))

    def _seed_words(self):
        """Button-driven word entry. Per letter: u/d cycles a-z, a appends.
        r opens the candidate list (u/d select, a accept word), b backspaces."""
        total = self._pick_seed_length()
        if total is None:
            return False
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
                elif key == "r" and candidates:
                    word = self._pick_candidate(candidates, len(words) + 1,
                                                total)
                    if word:
                        words.append(word)
                        break
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
                raw = self.qr.scan_key()
                if len(raw) > MAX_KEY_PAYLOAD:
                    raise RuntimeError("key payload too large, refusing")
                payload = raw.decode("ascii").strip()
                if not set(payload) <= _KEY_CHARSET:
                    raise RuntimeError("key payload has invalid characters")
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
            advanced = False
            for frame in qr_frames:
                advanced = True
                try:
                    if assembler.feed(frame):
                        psbt = assembler.psbt_b64
                        break
                except qrchannel.QrChannelError:
                    continue
            else:
                qr_frames = None
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
        outs = [(o["address"], Decimal(str(o["amount_btc"])))
                for o in info["outputs"]]
        pages = max(1, (len(outs) + 2) // 3)
        page, seen = 0, {0}
        while True:
            self.display.show(screens.review(
                self.w, self.h, outs, Decimal(str(info["fee_btc"])),
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
    else:
        display = hal.DeviceDisplay()
        buttons = hal.DeviceButtons()
    qr = DevQrSource(key_path=args.qr_key, psbt_path=args.qr_psbt)

    Session(display, buttons, rpc, stick_dir=args.stick_dir, qr_source=qr,
            passphrase=args.passphrase).run()


if __name__ == "__main__":
    main()
