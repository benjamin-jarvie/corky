"""Corky's session state machine: the program the device boots into.

States:
  HOME (2x2: load key / key generation / tools / settings)
    -> LOAD KEY (A-14's modes: descriptor, xprv, codex32, SeedQR, words;
       scanned or typed) or KEY GENERATION (A-19)
    -> key open in Core -> LOAD PSBT (file channel or QR)
    -> REVIEW -> sign -> RESULT, which offers SIGN ANOTHER (back to LOAD
       PSBT with the same key) or POWER OFF. Back from LOAD PSBT or REVIEW
       returns to HOME with the key still loaded.
  Power off lives in SETTINGS (PLAN A-15c).

Every screen comes from screens.py, every wallet operation from signer.py,
every transfer from qrchannel/filechannel. This module holds no crypto and
parses no untrusted bytes; it is the traffic cop.

QR input arrives through a QrSource: on the device that is the camera (M1);
in dev mode it reads payloads from files so every state is exercisable
without hardware.

Dev mode:
    python3 corky/main.py --dev --datadir <dir> --chain regtest \
        --script "<keys>" [--stick-dir DIR] [--qr-psbt FILE]
        [--qr-key FILE] [--frames-dir DIR]
Keys (PLAN A-15c, eight controls): u/d/l/r = d-pad, p = centre press,
a = select/KEY1, b = back or delete/KEY2, c = abort/KEY3. The passphrase
is asked for on screen, never passed as an argument, so it cannot appear
in a process listing.
"""

import argparse
import subprocess
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


class ImageQrSource:
    """Turns a stream of images into decoded QR strings.

    Ticket 04 fixed the contract: a source yields strings and nothing else.
    Every stopping rule lives in qrchannel.scan_psbt, so this class holds no
    policy at all. A tick with no code in view yields None, which is what lets
    the caller's no-progress timeout fire on a still scene.

    Subclasses supply images. That is the only part that needs hardware, which
    is why CameraQrSource below is four lines.
    """

    #: The most recent frame, for a viewfinder. None until one arrives.
    last_image = None

    #: A camera is always a channel worth offering. The dev source overrides
    #: this, because a dev run with no --qr-psbt has nothing to scan.
    available = True

    def images(self):
        raise NotImplementedError

    def scan_key(self):
        # The camera works (M1); SeedQR entry through it does not. Every
        # stopping rule for a key scan is M2 work, so this stays closed
        # rather than shipping a scan with no abort and no timeout.
        raise RuntimeError("SeedQR scanning not wired yet (M2); type the seed")

    def scan_psbt_frames(self):
        for image in self.images():
            # Ticket 04 still holds: this yields strings and nothing else.
            # The image is parked here instead, so a caller that wants a
            # viewfinder can read it without the stream carrying two types.
            self.last_image = image
            if image is None:
                yield None
                continue
            found = qrchannel.decode_image(image)
            if not found:
                yield None
            for payload in found:
                yield payload


class CameraQrSource(ImageQrSource):
    """Device QR source: picamera2 into pyzbar.

    Measured on a Zero 2 W with an ov5647, 2026-09-04: 512x384 at 30fps,
    three times hw/HARDWARE.md's 10fps target, for both RGB888 and YUV420.

    YUV420, because zbar works in greyscale. capture_array returns
    (height * 3 // 2, width) for that format, and the first `height` rows
    are the Y plane, which is the greyscale image already. Handing zbar an
    RGB frame only pays for a conversion it would do itself.
    """

    SIZE = (512, 384)          # hw/HARDWARE.md:75
    BUFFERS = 4

    def __init__(self):
        # Why there is no camera, when there is no camera. Read by the
        # caller; nothing here decides what to do about it.
        self.unavailable = None

    def images(self):
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            cam.configure(cam.create_video_configuration(
                main={"size": self.SIZE, "format": "YUV420"},
                buffer_count=self.BUFFERS))
            cam.start()
        except Exception as exc:
            # A board with no camera must fall through to the USB stick, not
            # take the whole app down (I-8). The caller gets an empty stream
            # and its no-progress timeout does the rest.
            self.unavailable = f"{type(exc).__name__}: {exc}"
            return
        width, height = self.SIZE
        try:
            while True:
                yield cam.capture_array("main")[:height, :width]
        finally:
            cam.stop()
            cam.close()


class DevQrSource:
    """Dev stand-in for the camera: returns file contents as scan payloads."""

    def __init__(self, key_path=None, psbt_path=None):
        self.key_path = key_path
        self.psbt_path = psbt_path

    @property
    def available(self):
        """No file, no frames. state_load offers only channels that exist."""
        return bool(self.psbt_path)

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


# What a PSBT run reports back to the home screen.
SIGN_AGAIN, POWER_OFF, TO_HOME = "again", "off", "home"

# How the board is halted. Under systemd the poweroff is the whole teardown:
# it stops corky-bitcoind.service by that unit's own ExecStop, which runs
# bitcoin-cli stop and waits up to TimeoutStopSec=30. FALLBACK_HALT_CMD and
# an explicit node stop cover a board that runs Corky without systemd.
HALT_CMD = ["systemctl", "poweroff"]
FALLBACK_HALT_CMD = ["halt", "-p"]


def _run(cmd):
    """Run a command and report success. A missing binary is a failure, not
    an exception: subprocess.run(check=False) suppresses a non-zero exit but
    still raises FileNotFoundError, which is exactly the no-systemd case the
    fallback exists for."""
    try:
        return subprocess.run(cmd, check=False).returncode == 0
    except OSError:
        return False


class Session:
    def __init__(self, display, buttons, rpc, stick_dir=None, qr_source=None,
                 passphrase="", animate=False, on_device=False):
        self.display = display
        self.animate = animate
        # on_device gates the two real effects of POWER OFF. The dev harness
        # shares one bitcoind across every scripted session, so a session
        # that stopped the node would fail every session after it.
        self.on_device = on_device
        self.buttons = buttons
        self.rpc = rpc
        self.stick_dir = Path(stick_dir) if stick_dir else None
        self.qr = qr_source or DevQrSource()
        self.passphrase = passphrase
        self.w, self.h = display.width, display.height
        self.wordlist = load_wordlist()
        #: Master fingerprint of the open wallet, or None. Refreshed
        #: whenever a flow returns, because any of them can open or close
        #: a key.
        self.xfp = None

    # -- flow --------------------------------------------------------------

    def run(self):
        try:
            self.state_home()
        finally:
            try:
                signer.close_session(self.rpc)
            except Exception:
                pass
        # state_home only returns when the user chose POWER OFF, on the
        # result screen or in settings. A crash raises instead, and systemd
        # restarts the unit, so the device must NOT halt on that path.
        self.power_off()

    def power_off(self):
        """Cover the screen, then halt the board and its node (I-2).

        Leaving Python is not a power off. bitcoind keeps running under its
        own unit, /run/corky stays mounted, and the ST7789 holds its last
        frame, so the operator reads POWER OFF on a device that is still
        live and still holding a wallet-shaped ramdisk.

        Under systemd the poweroff is the whole teardown, so this does not
        stop the node itself: corky-bitcoind.service does that in its own
        ExecStop, in shutdown order, with a 30 second timeout. Without
        systemd nothing else will, so the fallback stops the node first.

        The ramdisk is NOT wiped here. close_session already deletes the
        wallet directory, which is the only secret-bearing path under
        /run/corky, and the rest is a wallet-only node's own state. The
        tmpfs itself dies with power. Cold-boot RAM remanence stays an M3
        question.

        If the board is still running after both attempts, the screen says
        so. A device that reads POWER OFF while it is live is the whole
        defect (audit D16), and a silent failure repeats it (D17).
        """
        if not self.on_device:
            return
        # Cover the result screen FIRST. The panel keeps its last frame with
        # no power of its own, so whatever is on it when the board dies is
        # what the next person to pick it up reads. The result screen shows
        # an address and an amount; this frame shows neither.
        stop = self._busy("powering off…")
        try:
            if _run(HALT_CMD):
                return          # shutdown started; systemd stops the node
            # No systemd. Nothing else will stop bitcoind, and halting over
            # a live writer can tear a wallet on any build that is not
            # fully RAM-resident.
            node_down = signer.stop_node(self.rpc)
            halted = _run(FALLBACK_HALT_CMD)
        finally:
            stop()
        if halted and node_down:
            return
        detail = ("halt failed; remove power" if not halted
                  else "bitcoind still running; remove power")
        self.display.show(screens.result(self.w, self.h, ok=False,
                                         detail=detail))
        self.buttons.read()

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

    def _show_core_error(self, exc):
        """Put a Core failure on screen instead of taking the app down.

        Core's error strings carry an "error code: -4" line and a blank
        line before the message; the last non-empty line is the part a
        person can act on.
        """
        lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        detail = lines[-1] if lines else str(exc)
        self.display.show(screens.result(self.w, self.h, ok=False,
                                         detail=detail))
        self.buttons.read()

    def state_home(self):
        # 2x2 tiles: load key | key generation / tools | settings.
        # Power off lives inside settings (Ben, 2026-09-01).
        row = col = 0
        while True:
            self.xfp = signer.master_fingerprint(self.rpc)
            selected = row * 2 + col
            self.display.show(screens.home(self.w, self.h, selected,
                                           xfp=self.xfp))
            key = self.buttons.read()
            if key == "u":
                row = (row - 1) % 2
            elif key == "d":
                row = (row + 1) % 2
            elif key == "l":
                col = (col - 1) % 2
            elif key == "r":
                col = (col + 1) % 2
            elif key in ("a", "p"):
                if selected == 3:          # settings
                    if self.state_settings():
                        return             # settings chose power off
                    continue
                # Every flow talks to Core, and Core can refuse. An
                # unhandled RuntimeError used to end the process, leaving
                # the panel frozen on whatever it had last painted, with no
                # message and no way back (found on the board, 2026-09-04:
                # a second generate in one session read as "it bailed").
                # Say what went wrong and return to home instead.
                try:
                    opened = [self.state_seed_menu,  # 0 load key
                              self._seed_generate,   # 1 key generation
                              self.state_tools       # 2 tools
                              ][selected]()
                except RuntimeError as exc:
                    self._show_core_error(exc)
                    opened = False
                # Coming back from a flow always lands on the first tile,
                # so home is in a known state however you got here.
                row = col = 0
                if opened:
                    # A key is loaded in Core: sign PSBTs with it until the
                    # user backs out (D7, -> home, key still loaded) or
                    # chooses POWER OFF on the result screen (D8).
                    while True:
                        outcome = self.state_load()
                        if outcome != SIGN_AGAIN:
                            break
                    if outcome == POWER_OFF:
                        return

    def state_settings(self) -> bool:
        """Settings menu. Returns True if the user chose power off (the
        session ends), False on back. About is informational."""
        selected = 0
        while True:
            self.display.show(screens.settings_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % 2
            elif key == "d":
                selected = (selected + 1) % 2
            elif key == "b":
                return False
            elif key in ("a", "p"):
                if selected == 0:          # power off
                    return True
                # about: show, then any key returns to the settings menu
                self.display.show(screens.about(self.w, self.h))
                self.buttons.read()

    # -- seed entry: the three A-14 modes plus SeedQR ---------------------

    def state_seed_menu(self) -> bool:
        selected = 0
        while True:
            self.display.show(screens.seed_menu(self.w, self.h, selected))
            key = self.buttons.read()
            if key == "u":
                selected = (selected - 1) % 8
            elif key == "d":
                selected = (selected + 1) % 8
            elif key == "b":
                return False
            elif key in ("a", "p"):
                try:
                    return [self._seed_descriptor, self._seed_xprv,
                            self._seed_descriptor_typed, self._seed_xprv_typed,
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
        # S2: the passphrase is asked for here, so every words-based mode
        # (typed and SeedQR) offers it on the same screen.
        self.passphrase = self._ask_passphrase()
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
            elif key in ("a", "p"):
                return 12 if selected == 0 else 24
            elif key == "b":
                return None

    def _text_entry(self, title, charset, secret=False):
        """Drive the paged text grid for one alphabet.

        u/d/l/r move the cursor; l and r at a row edge turn the page, so
        every character is reachable. A types the highlighted character, B
        deletes one, centre-press finishes. C moves to the action bar,
        where CANCEL really cancels and DONE commits. Returns None on
        cancel, which is distinct from the empty string.
        """
        pages = screens.charset_pages(charset)
        text, cur, page, sel = "", 0, 0, None
        while True:
            self.display.show(screens.text_entry(
                self.w, self.h, title, text, cur, charset, page, secret,
                actions_sel=1 if sel is None else sel), sensitive=True)
            key = self.buttons.read()
            n = len(pages[page])
            if sel is not None:            # focus is on the action bar
                if key in ("l", "r"):
                    sel = 1 - sel
                elif key in ("a", "p"):
                    return text if sel == 1 else None
                elif key in ("b", "c"):
                    sel = None
                continue
            # The grid is one strip read left to right: l/r step one cell
            # and cross rows, u/d jump a row, and a page turns only at the
            # strip's ends. Anything cleverer desynchronises the user's
            # mental model from the cursor.
            if key == "u":
                cur = max(0, cur - 8)
            elif key == "d":
                cur = min(n - 1, cur + 8)
            elif key == "l":
                if cur == 0 and page > 0:
                    page -= 1
                    cur = len(pages[page]) - 1
                else:
                    cur = max(0, cur - 1)
            elif key == "r":
                if cur == n - 1 and page + 1 < len(pages):
                    page += 1
                    cur = 0
                else:
                    cur = min(n - 1, cur + 1)
            elif key == "a":
                text += pages[page][cur]
            elif key == "b":
                text = text[:-1]
            elif key == "p":
                return text
            elif key == "c":
                sel = 1              # jump to the action bar

    def _ask_passphrase(self):
        """S2: offer a BIP39 passphrase before deriving. Returns the
        passphrase (possibly empty). A passphrase cannot be verified by the
        device, so the screen says what it does before it is typed."""
        sel = 0
        while True:
            self.display.show(screens.passphrase_prompt(self.w, self.h, sel))
            key = self.buttons.read()
            if key in ("l", "r"):
                sel = 1 - sel
            elif key in ("b", "c"):
                return ""
            elif key in ("a", "p"):
                if sel == 0:
                    return ""
                return self._text_entry("PASSPHRASE", "passphrase",
                                        secret=True) or ""

    def _keymaterial(self, kind):
        """Warning screen (A-14: the QR IS the wallet), then scan."""
        self.display.show(screens.keymaterial_warning(self.w, self.h, kind))
        while True:
            key = self.buttons.read()
            if key in ("a", "p"):
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

    def _seed_descriptor_typed(self):
        """S3: a descriptor typed on the grid, for a camera-less build or a
        descriptor that never existed as a QR."""
        text = self._text_entry("PRIVATE  DESCRIPTOR", "descriptor")
        if not text:
            return False
        stop = self._busy("importing into Core…")
        try:
            signer.open_session_descriptors(self.rpc, [text])
        finally:
            stop()
        return True

    def _seed_xprv_typed(self):
        """S3: an xprv typed on the grid."""
        text = self._text_entry("BIP32  EXTENDED  PRIVATE  KEY", "xprv")
        if not text:
            return False
        stop = self._busy("importing into Core…")
        try:
            signer.open_session_xprv(self.rpc, text)
        finally:
            stop()
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
            elif key in ("a", "p"):
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
        # The passphrase is part of the seed: backing up without asking
        # would encode a DIFFERENT wallet than the words plus passphrase
        # open. Ask here too, exactly as the load path does.
        seed = mnemonic_to_seed(" ".join(words), self._ask_passphrase())
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
        # Wrapping means the line count depends on the panel, so ask the
        # screen rather than counting the source strings.
        max_scroll = screens.generate_scroll_max(self.w, self.h)
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
            elif key in ("a", "p"):
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
            elif key in ("a", "p"):
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
            elif key in ("a", "p"):
                return selected
            elif key == "b":
                return None

    def _collect_words(self):
        total = self._pick_seed_length()
        if total is None:
            return None
        words = []
        while len(words) < total:
            prefix, gi = "", 0
            while True:
                # B on an empty prefix steps back to the previous word, so a
                # word committed by mistake at position 3 of 24 is fixable
                # without abandoning the whole entry (D5).
                candidates = [w for w in self.wordlist
                              if w.startswith(prefix)][:3]
                self.display.show(screens.seed_entry(
                    self.w, self.h, len(words) + 1, total,
                    prefix, tuple(candidates), gi), sensitive=True)
                key = self.buttons.read()
                # 8x4 grid, wrap like the codex32 grid; letters are 0..25.
                if key == "u":
                    gi = (gi - 8) % 32
                elif key == "d":
                    gi = (gi + 8) % 32
                elif key == "l":
                    gi = (gi - 1) % 32
                elif key == "r":
                    gi = (gi + 1) % 32
                elif key == "a":
                    if gi < 26:
                        prefix += screens.ALPHABET[gi]
                elif key == "b":
                    if prefix:
                        prefix = prefix[:-1]
                    elif words:
                        words.pop()           # undo the previous word
                        break
                elif key == "p":
                    if candidates:            # center-press: take the top word
                        words.append(candidates[0])
                        break
                elif key == "c":
                    return None
        return words

    # -- PSBT load: stick first, then QR frames ---------------------------

    def state_load(self):
        """Pick a channel, then run only that one (Ben, 2026-09-04).

        It used to poll the stick and the camera together behind one line,
        "insert stick or show QR". That gave neither channel a screen of its
        own: the camera ran while you were fetching a stick, and the scan
        had nowhere to show what it could see. The two also want different
        patience. A scan that has made no progress for 20s means the aim is
        wrong and should say so; a stick you are still walking to fetch is
        not a fault at any elapsed time.
        """
        # Offer only the channels that exist. On the device both always do,
        # so the menu always appears; a board with no camera would be wrong
        # to offer "Scan QR", and a dev run with no --qr-psbt has nothing to
        # scan. One channel means there is nothing to ask.
        can_qr = getattr(self.qr, "available", True)
        can_stick = bool(self.stick_dir)
        if not can_qr and not can_stick:
            self.display.show(screens.result(
                self.w, self.h, ok=False, detail="no way to load a PSBT"))
            self.buttons.read()
            return TO_HOME
        if not can_stick:
            return self._load_by_qr()
        if not can_qr:
            return self._load_by_stick()
        choice = 0
        while True:
            self.display.show(screens.channel_menu(self.w, self.h, choice))
            key = self.buttons.read()
            if key in ("u", "d"):
                choice = 1 - choice
            elif key in ("a", "p"):
                break
            elif key in ("b", "c"):
                return TO_HOME
        return self._load_by_stick() if choice == 1 else self._load_by_qr()

    def _load_by_stick(self):
        """Wait on the USB stick alone. No timeout: fetching one is not a
        fault, however long it takes. B or C returns to the channel menu."""
        self.display.show(screens.busy(self.w, self.h,
                                       "insert the stick…"))
        while True:
            if self.stick_dir:
                found = filechannel.find_unsigned(self.stick_dir)
                if found and filechannel.wait_stable(found[0]):
                    return self.state_review(
                        filechannel.read_psbt(found[0]), found[0])
            key = self.buttons.pressed()
            if key == "b":
                return self.state_load()
            if key == "c":
                return TO_HOME
            time.sleep(0.2)

    def _load_by_qr(self):
        psbt, source = None, None
        qr_frames = None
        notice = {"text": "hold the QR in view"}

        def on_event(kind, detail):
            # The screen string ticket 03 asked for, and ticket 05's restart.
            # screens.busy already takes a message, so no new screen is needed.
            if kind == "advisory":
                notice["text"] = "large frames: set Sparrow to Low density"
            elif kind == "restart":
                notice["text"] = "different transaction, starting again…"

        scan = qrchannel.PsbtScan(on_event=on_event)
        shown = notice["text"]
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
            progress_before = scan.progress
            try:
                # ONE frame per pass. A camera is an infinite generator, so
                # looping it here never returns: the viewfinder freezes on
                # its last paint and the buttons are never polled. That could
                # not happen while CameraQrSource returned an empty iterator;
                # it appeared the moment a real camera was wired (2026-09-04).
                try:
                    frame = next(qr_frames)
                except StopIteration:
                    qr_frames = None
                    frame = None
                if frame is not None and scan.feed(frame):
                    psbt = scan.psbt_b64
            except qrchannel.ScanTimeout as exc:
                # Ticket 05: say why, then keep waiting rather than dropping
                # the user out of a screen they deliberately opened.
                notice["text"] = f"scan stalled ({exc}); try again"
                scan = qrchannel.PsbtScan(on_event=on_event)
                qr_frames = None
            shown = notice["text"]
            self.display.show(screens.scanning(
                self.w, self.h, getattr(self.qr, "last_image", None), shown,
                scan.progress))
            # Progress, not mere frame consumption, counts as advancing —
            # otherwise an incomplete dev file spins at 50Hz and the
            # back/reject buttons are never polled.
            advanced = psbt is not None or scan.progress > progress_before
            if psbt is not None:
                break
            if not advanced:
                key = self.buttons.pressed()
                # hw/HARDWARE.md gives B and C different jobs and they should
                # keep them here. B is "back one page": you still want to
                # load a transaction, the QR just is not working. C is
                # "abort the current flow", so it leaves altogether. A stall
                # on its own moves you nowhere; ticket 05 settled that it
                # says why and keeps waiting.
                if key == "b":
                    return self.state_load()
                if key == "c":
                    return TO_HOME
            time.sleep(0.02)
        return self.state_review(psbt, source)

    def state_review(self, psbt, source):
        info = signer.describe_psbt(self.rpc, psbt)
        if info["fee_btc"] is None:
            # Missing input data: refuse loudly instead of crashing (a fee
            # the device cannot show is a transaction it must not sign).
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="PSBT lacks input data; fee unknown; refused"))
            self.buttons.read()
            return TO_HOME
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
            elif key in ("a", "p") and sel == 1:
                if len(seen) < pages:
                    # Every output must have been on screen before signing.
                    page, refused = (page + 1) % pages, True
                    seen.add(page)
                    continue
                return self.state_sign(psbt, source)
            elif key == "b":
                return TO_HOME       # back to home, key still loaded (D7)
            elif key == "c" or (key in ("a", "p") and sel == 0):
                self.display.show(screens.result(
                    self.w, self.h, ok=False, detail="rejected by user"))
                self.buttons.read()
                return TO_HOME

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
            self.buttons.read()
            return TO_HOME
        if source is not None:
            out = filechannel.write_signed(source, signed["psbt"])
            detail = f"{out.name} written"
        else:
            frames = qrchannel.psbt_to_frames(signed["psbt"])
            try:
                self._show_qr_loop(frames)
            except qrchannel.QrChannelError as exc:
                # The PSBT IS signed. Losing the run here would unwind past
                # the result screen and throw the signature away, so say
                # what happened and offer the file channel instead.
                self.display.show(screens.result(
                    self.w, self.h, ok=False,
                    detail=f"signed, but not shown: {exc}"))
                self.buttons.read()
                return TO_HOME
            detail = f"shown as {len(frames)} QR frames"
        return self._state_signed(detail)

    def _show_qr_loop(self, frames, delay=0.15):
        """Play the BC-UR animation as a steady, repeating loop.

        A fountain animation must cycle continuously at a readable rate for
        Sparrow or a phone to catch every part; one unpaced pass is not
        readable for any multi-frame PSBT. Any key stops. A single frame is
        a static QR, so it is shown once and waits for a key.
        """
        images = [qrchannel.fit_to_panel(img, self.w, self.h)
                  for img in qrchannel.frames_to_images(
                      frames, panel=(self.w, self.h))]
        if len(images) == 1:
            self.display.show(images[0])
            self.buttons.read()
            return
        if not self.animate:
            # Dev/scripted runs: one deterministic pass, no timing.
            for img in images:
                self.display.show(img)
            return
        stop = threading.Event()

        def wait_for_key():
            self.buttons.read()
            stop.set()

        watcher = threading.Thread(target=wait_for_key, daemon=True)
        watcher.start()
        while not stop.is_set():
            for img in images:
                if stop.is_set():
                    break
                self.display.show(img)
                stop.wait(delay)

    def _state_signed(self, detail):
        """Result screen with SIGN ANOTHER / POWER OFF (Ben, 2026-09-01)."""
        sel = 0
        while True:
            self.display.show(screens.result(
                self.w, self.h, ok=True, detail=detail, actions_sel=sel))
            key = self.buttons.read()
            if key in ("l", "r"):
                sel = 1 - sel
            elif key in ("a", "p"):
                return SIGN_AGAIN if sel == 0 else POWER_OFF
            elif key == "c":
                return POWER_OFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--chain", default="main")
    ap.add_argument("--script", default="")
    ap.add_argument("--stick-dir")
    ap.add_argument("--qr-psbt", help="dev: file of UR frames, one per line")
    ap.add_argument("--qr-key", help="dev: file with SeedQR digits/xprv/descriptor")
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
            animate=not args.dev, on_device=not args.dev).run()


if __name__ == "__main__":
    main()
