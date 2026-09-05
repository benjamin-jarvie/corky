"""Corky's session state machine: the program the device boots into.

States (SeedSigner's shape, map e2e-before-testers tickets 02 and 07):
  HOME (2x2: scan / key / tools / settings)
    SCAN  -> the camera: a transaction for the current key
    KEY   -> the loaded keys by fingerprint, or LOAD A KEY (A-22: a
             descriptor or an xprv, scanned or typed)
          -> one key's menu: sign transaction, export public key,
             receiving addresses, backup key, discard key
    TOOLS -> NEW KEY (A-19: Core's own RNG), then that key's menu
    -> sign: LOAD PSBT (QR or stick) -> REVIEW -> sign -> RESULT, which
       offers SIGN ANOTHER or POWER OFF. Back returns to HOME with the
       keys still loaded (D7).
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
import filechannel
import qrchannel
import hal



MAX_KEY_PAYLOAD = 4096          # a descriptor set is a few hundred chars
_KEY_CHARSET = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "()[]{}#*'/,:;h<>@?!&+=-_.\n\r ")


#: The output-descriptor functions Core defines. A code is a descriptor
#: only if it opens with one of these, so a URL with brackets in it is
#: skipped rather than handed to Core to refuse (ticket 05: anything else
#: is counted and skipped).
DESCRIPTOR_FUNCTIONS = frozenset((
    "pk", "pkh", "wpkh", "sh", "wsh", "combo", "tr", "rawtr",
    "multi", "sortedmulti", "multi_a", "sortedmulti_a", "addr", "raw"))


def _classify_qr(payload):
    """What a scanned code is, by its content alone (ticket 05).

    None means "not for this scan": counted, skipped, keep looking. Core
    is still the only thing that PARSES any of these; this reads the first
    few characters to choose a screen, which is what A-11 permits.
    """
    text = payload.strip()
    if text.lower().startswith("ur:"):
        return "transaction"
    if text.startswith(signer.XPRV_PREFIXES):
        return "xprv"
    head = text.split("(")[0]
    if head in DESCRIPTOR_FUNCTIONS and (text.endswith(")") or "#" in text):
        return "descriptor"
    # A wallet that shows a payment request shows BIP21, not a bare
    # address, so take the address out of it before the shape test.
    if text.lower().startswith("bitcoin:"):
        text = text[len("bitcoin:"):].split("?")[0]
    # One word, no punctuation, about the length of a bech32 or base58
    # address. Core decides whether it is really an address.
    if 20 <= len(text) <= 100 and text.isalnum():
        return "address"
    return None


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

    #: A camera is always a channel worth offering for a PSBT, and always
    #: something the Scan tile can point at. The dev source overrides both,
    #: because a dev run reads files and may have neither.
    available = True
    scannable = True

    def images(self):
        raise NotImplementedError

    def strings(self):
        """Decoded QR text, one per tick, None when nothing is in view.

        Ticket 04's contract: a source yields strings and nothing else, and
        every stopping rule lives in the caller. A PSBT and a key read the
        same way, so they share this one generator.
        """
        for image in self.images():
            # The image is parked here instead of riding the stream, so a
            # caller that wants a viewfinder can read it without the
            # stream carrying two types.
            self.last_image = image
            if image is None:
                yield None
                continue
            found = qrchannel.decode_image(image)
            if not found:
                yield None
            for payload in found:
                yield payload

    def scan_psbt_frames(self):
        return self.strings()


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
        """No PSBT file, no PSBT channel. state_load offers only channels
        that exist."""
        return bool(self.psbt_path)

    @property
    def scannable(self):
        """The Scan tile takes whatever is in front of the lens, which in
        a dev run is either file."""
        return bool(self.psbt_path or self.key_path)

    def strings(self):
        """The dev stand-in for a camera: the key file, then the PSBT
        frames. `scannable` promises whichever of the two exists, so this
        must yield from either rather than insisting on the key file."""
        if self.key_path:
            yield Path(self.key_path).read_text()
        if self.psbt_path:
            for frame in Path(self.psbt_path).read_text().split():
                yield frame
        if not (self.key_path or self.psbt_path):
            raise RuntimeError("no --qr-key or --qr-psbt in this dev session")

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
                 animate=False, on_device=False, card_dir=None):
        self.display = display
        self.animate = animate
        # on_device gates the two real effects of POWER OFF. The dev harness
        # shares one bitcoind across every scripted session, so a session
        # that stopped the node would fail every session after it.
        self.on_device = on_device
        self.buttons = buttons
        self.rpc = rpc
        self.stick_dir = Path(stick_dir) if stick_dir else None
        #: The boot partition, readable in any computer after power-off.
        #: The other medium a file can go to (ticket 15).
        self.card_dir = Path(card_dir) if card_dir else None
        self.qr = qr_source or DevQrSource()
        self.w, self.h = display.width, display.height
        #: Injectable so a scan's timeout can be tested without waiting.
        self.clock = time.monotonic
        #: The keys loaded in Core this session, in slot order (ticket 03),
        #: and the wallet name of the one most recently loaded or chosen.
        #: Refreshed whenever a flow returns, because any of them can open
        #: or close a key.
        self.keys = []
        self.key = None
        #: Fingerprint the home screen shows: the current key's.
        self.xfp = None

    def _refresh_keys(self):
        self.keys = signer.loaded_keys(self.rpc)
        names = [k.name for k in self.keys]
        if self.key not in names:
            self.key = names[-1] if names else None
        self.xfp = next((k.xfp for k in self.keys if k.name == self.key), None)

    # -- flow --------------------------------------------------------------

    def run(self):
        # Nothing from an earlier session may reach this one. bitcoind and
        # the ramdisk both outlive a UI restart, so a crashed session can
        # leave its key loaded in Core; say so rather than adopting it.
        try:
            dropped = signer.clear_on_start(self.rpc)
        except Exception as exc:      # noqa: BLE001 - reported on the panel
            # A clear that fails silently is the whole defect this call
            # exists to prevent: a key from an earlier session, still
            # loaded, on a device that says nothing about it (D17's twin).
            dropped = []
            self._hold(f"could not clear old keys: {str(exc)[:40]}")
        if dropped:
            self._hold(f"cleared {len(dropped)} key(s) from an earlier session")
        teardown = None
        try:
            self.state_home()
        finally:
            try:
                signer.close_session(self.rpc)
            except Exception as exc:      # noqa: BLE001 - reported below
                # D17: this used to be discarded. A teardown that fails is
                # a key still in the node, on a device whose next screen
                # says it is off. Say so instead.
                teardown = exc
        if teardown is not None:
            self._hold(f"key not cleared: {str(teardown)[:44]}")
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
        # SeedSigner's four tiles (ticket 02): Scan | Key / Tools | Settings.
        # Power off lives inside settings (Ben, 2026-09-01).
        row = col = 0
        while True:
            self._refresh_keys()
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
                # message and no way back (found on the board, 2026-09-04).
                # Say what went wrong and return to home instead.
                try:
                    outcome = [self.state_scan,    # 0 scan
                               self.state_keys,    # 1 key
                               self.state_tools,   # 2 tools
                               ][selected]()
                except self.HANDLED as exc:
                    self._show_core_error(exc)
                    outcome = None
                # Coming back from a flow always lands on the first tile,
                # so home is in a known state however you got here.
                row = col = 0
                if outcome == POWER_OFF:
                    return

    def _hold(self, detail, ok=False):
        """Park a message until a key is pressed (D6: a message the user
        cannot read is a message the user cannot act on)."""
        self.display.show(screens.result(self.w, self.h, ok=ok, detail=detail))
        self.buttons.read()

    #: Everything a load, a review or a signature can fail with that is
    #: the world's fault rather than a bug: Core refusing, a bad file, a
    #: pulled stick, an unreadable QR. Named rather than blanket, so a real
    #: defect still crashes loudly in the tests (ISSUES D18).
    HANDLED = (RuntimeError, OSError, filechannel.FileChannelError,
               qrchannel.QrChannelError)

    def _sign_loop(self, load):
        """Sign transactions with the current key until the user leaves:
        SIGN ANOTHER repeats, back goes home (D7, key still loaded), POWER
        OFF ends the session.

        Nothing in here may take the process down. `corky.service` has
        `Restart=on-failure`, so an exception here becomes a restart loop
        that lasts as long as the file is on the stick (D18).
        """
        while True:
            try:
                outcome = load()
            except self.HANDLED as exc:
                self._show_core_error(exc)
                return TO_HOME
            if outcome != SIGN_AGAIN:
                return outcome

    def state_scan(self):
        """The Scan tile: the camera, and whatever it sees (ticket 05).

        One code decides what happens. UR frames are a transaction, an
        extended private key or a descriptor is a key to load, and an
        address is checked against every loaded key. Anything else is
        counted and skipped, as a stray code on a desk should be.
        """
        if not getattr(self.qr, "scannable", True):
            self._hold("no camera on this build")
            return None
        try:
            kind, payload = self._scan_until("hold any QR in view",
                                             _classify_qr)
        except qrchannel.ScanAborted:
            return None
        except qrchannel.ScanTimeout as exc:
            self._hold(str(exc))
            return None
        try:
            if kind == "transaction":
                # The assembler owns a multi-frame scan, so hand the whole
                # job back to it rather than trying to splice this frame in.
                return self._sign_loop(self._load_by_qr)
            if kind == "address":
                return self._check_address(payload)
            text = self._guard_key_payload(payload)
            if kind == "xprv":
                self.key = signer.open_session_xprv(self.rpc, text)
            else:
                self.key = signer.open_session_descriptors(
                    self.rpc, text.splitlines())
        except self.HANDLED as exc:
            self._show_core_error(exc)
            return None
        return self.state_key_menu(self.key)

    def _check_address(self, payload):
        """Whose address is this? Core answers, per loaded key (ticket 05).

        The point is the one a coordinator cannot make for you: that the
        address on the other screen belongs to the key in your hand.
        """
        if not self.keys:
            self._hold("load a key first")
            return None
        address = payload.strip()
        if address.lower().startswith("bitcoin:"):
            address = address[len("bitcoin:"):].split("?")[0]
        for key in self.keys:
            try:
                info = self.rpc.call("getaddressinfo", address,
                                     wallet=key.name)
            except RuntimeError as exc:
                self._show_core_error(exc)
                return None
            if info.get("ismine"):
                self.display.show(screens.verified(
                    self.w, self.h,
                    f"key {(key.xfp or '').upper()}\nowns this address"))
                self.buttons.read()
                return None
        self._hold("no loaded key owns that address")
        return None

    def state_keys(self):
        """The Keys tile. One screen with one title, whether or not the
        device holds a key: the loaded keys by fingerprint, then Load a key
        and New key.

        It used to jump straight past this into a differently titled LOAD A
        KEY when nothing was loaded, so the same tile gave two screens, and
        New key sat under Tools where it did not belong (Ben, 2026-09-05).
        """
        selected = 0
        while True:
            self._refresh_keys()
            keys = self.keys
            n = len(keys) + len(screens.KEYS_ACTIONS)
            selected = self._pick(lambda sel, keys=keys: screens.keys_menu(
                self.w, self.h, keys, sel), n, start=selected)
            if selected is None:
                return None
            action = selected - len(keys)
            if action == 0:                           # Load a key
                if not self.state_load_key():
                    continue
            elif action == 1:                         # New key
                if not self._tool_generate():
                    continue
            else:
                self.key = keys[selected].name
            outcome = self.state_key_menu(self.key)
            if outcome in (POWER_OFF, TO_HOME):
                return outcome

    def state_key_menu(self, name):
        """One key's menu, in Core's words (ticket 07). Export and
        Receiving addresses land with tickets 12 and 14."""
        selected = 0
        while True:
            xfp = signer.master_fingerprint(self.rpc, wallet=name)
            selected = self._pick(lambda sel, xfp=xfp: screens.key_menu(
                self.w, self.h, xfp, sel), len(screens.KEY_MENU_OPTIONS),
                start=selected)
            if selected is None:
                return None
            if selected == 0:                         # Sign transaction
                self.key = name
                outcome = self._sign_loop(self.state_load)
                if outcome in (POWER_OFF, TO_HOME):
                    return outcome
            elif selected == 1:
                self._export(name)
            elif selected == 2:
                self._browse_addresses(name)
            elif selected == 3:
                self._backup(name, xfp)
            elif selected == 4 and self._discard(name, xfp):
                return TO_HOME

    def state_tools(self):
        """Tools is about the device, not about your keys. New key moved to
        the Keys screen on 2026-09-05, which leaves the leak check."""
        while True:
            choice = self._pick(
                lambda sel: screens.tools_menu(self.w, self.h, sel),
                len(screens.TOOLS_OPTIONS))
            if choice is None:
                return None
            if choice == 0:
                self._tool_leak_check()

    # -- export the public key (ticket 12) ---------------------------------

    def _pick(self, render, count, start=0):
        """Run one list screen. Returns the chosen index, or None on back.

        Every menu goes through here: the keys list, a key's menu, Tools,
        Load a key, Settings, the key chooser, export and its sub-menus.
        Ten copies of this loop used to sit beside it (review, 2026-09-05).
        `start` lets a menu reopen on the row the user was on.
        """
        sel = start % count if count else 0
        while True:
            self.display.show(render(sel))
            key = self.buttons.read()
            if key == "u":
                sel = (sel - 1) % count
            elif key == "d":
                sel = (sel + 1) % count
            elif key in ("b", "c"):
                return None
            elif key in ("a", "p"):
                return sel

    def _file_channels(self):
        """The file channels that exist right now, in offer order."""
        found = []
        if self.stick_dir and self.stick_dir.is_dir():
            found.append(("stick", self.stick_dir))
        if self.card_dir and self.card_dir.is_dir():
            found.append(("card", self.card_dir))
        return found

    def _choose_channel(self):
        """Where a file goes. Asked every time (ticket 04). None if the
        user backed out or there is nothing to write to."""
        channels = self._file_channels()
        if not channels:
            self._hold("no stick or card to write to")
            return None
        # Asked every time, even when there is one medium (ticket 04). The
        # screen is what tells you where the file went, and that is the
        # decision, not a formality to skip when the answer looks obvious.
        names = [c for c, _p in channels]
        i = self._pick(lambda sel: screens.choose_channel(
            self.w, self.h, names, sel), len(names))
        return None if i is None else channels[i][1]

    def _export(self, name):
        """Export public key: which wallet, then the form it can read."""
        i = self._pick(lambda sel: screens.export_menu(self.w, self.h, sel),
                       len(screens.EXPORT_TARGETS))
        if i is None:
            return
        _label, _note, kinds = screens.EXPORT_TARGETS[i]
        if not kinds:                      # Bitcoin Core reads a file
            return self._export_file(name)
        kind = kinds[0]
        if len(kinds) > 1:
            j = self._pick(lambda sel: screens.export_script_menu(
                self.w, self.h, kinds, sel), len(kinds))
            if j is None:
                return
            kind = kinds[j]
        self._export_qr(name, kind)

    def _export_qr(self, name, kind):
        """The QR, then the same descriptor as text, then the first three
        addresses in full so the coordinator can be checked against them."""
        desc = signer.export_descriptor(self.rpc, name, kind)
        img = qrchannel.fit_to_panel(
            qrchannel.text_to_image(desc, panel=(self.w, self.h)),
            self.w, self.h)
        self.display.show(img)
        if self.buttons.read() == "c":
            return
        pages = screens.text_pages(desc)
        i = 0
        while True:
            self.display.show(screens.export_text(
                self.w, self.h, pages[i], page=i, pages=len(pages)))
            key = self.buttons.read()
            if key == "c":
                return
            if key in ("b", "u"):
                if i == 0:
                    return
                i -= 1
            elif key in ("a", "p"):
                if i + 1 == len(pages):
                    break
                i += 1
        self._show_addresses(name, kind)

    def _show_addresses(self, name, kind, count=3):
        """The first `count` receive addresses, one per screen. Used at the
        end of an export and after generation, where the list is short and
        finite."""
        return self._page_addresses(name, kind, limit=count)

    #: How many addresses one deriveaddresses call fetches. Paging past the
    #: end of a block fetches the next one, so browsing is unbounded.
    ADDRESS_BLOCK = 10

    def _browse_addresses(self, name):
        """Core's Receiving addresses, on a panel. Receive branch only.

        Core's own window of this name lists a wallet's receiving
        addresses, and that is what a user compares against a coordinator.
        Change addresses are deliberately absent: nobody hands one out, and
        showing them beside the others invites giving one away.
        """
        kinds = ("wpkh", "tr")
        j = self._pick(lambda sel: screens.export_script_menu(
            self.w, self.h, kinds, sel), len(kinds))
        if j is None:
            return
        return self._page_addresses(name, kinds[j])

    def _page_addresses(self, name, kind, limit=None):
        """One address per screen, derived by Core.

        `limit` bounds the walk (the export shows three); without it the
        walk goes on, fetching another block when the index leaves this
        one. One screen means one key map, whichever caller opened it:
        down or right goes on, up or left goes back, B or C leaves.
        `deriveaddresses` is side-effect free, so redrawing does not move
        the wallet's address index.
        """
        i, base, block = 0, 0, []
        while True:
            if not block or not base <= i < base + len(block):
                base = (i // self.ADDRESS_BLOCK) * self.ADDRESS_BLOCK
                try:
                    block = signer.receive_addresses(
                        self.rpc, name, kind, self.ADDRESS_BLOCK, base)
                except RuntimeError as exc:
                    return self._show_core_error(exc)
            self.display.show(screens.address_page(
                self.w, self.h, i, block[i - base], kind))
            key = self.buttons.read()
            if key in ("b", "c"):
                return
            if key in ("u", "l"):
                i = max(0, i - 1)
            elif key in ("a", "p", "d", "r"):
                if limit is not None and i + 1 >= limit:
                    return
                i += 1

    def _export_file(self, name):
        """Bitcoin Core has no QR reader. Core's own backupwallet writes a
        watch-only wallet its GUI restores with File, Restore Wallet."""
        dest = self._choose_channel()
        if dest is None:
            return
        stop = self._busy("writing the watch-only wallet…")
        try:
            out = signer.write_watch_only(self.rpc, name, dest)
        finally:
            stop()
        self._hold(f"{out.name} written", ok=True)

    def _ask_passphrase(self, title):
        """The passphrase, typed on the grid. Blanked on the dev display
        like every other secret-bearing screen."""
        text = self._text_entry(title, "passphrase", secret=True)
        if text is None:
            return None
        if not text:
            self._hold("a passphrase is required")
            return None
        return text

    def _backup(self, name, xfp):
        """Two backups (ticket 04). The file is offered first, because Core
        writes it and the key never passes through Corky to make it. The
        paper backup is the one exposure that is a choice: it asks Core for
        the key so a screen can draw it. Returns True if a backup was made.
        """
        i = self._pick(lambda sel: screens.backup_menu(self.w, self.h, sel),
                       len(screens.BACKUP_OPTIONS))
        if i is None:
            return False
        if i == 0:
            return self._backup_file(name)
        return self._backup_paper(name, xfp)

    def _backup_file(self, name):
        """Core's own encryptwallet then backupwallet. The medium is asked
        every time, because a backup on the card you are booting from is a
        different decision from one on a stick you take away."""
        passphrase = self._ask_passphrase("BACKUP  PASSPHRASE")
        if passphrase is None:
            return False
        dest = self._choose_channel()
        if dest is None:
            return False
        stop = self._busy("Bitcoin Core is encrypting your backup…")
        try:
            out = signer.backup_encrypted(self.rpc, name, passphrase, dest)
        finally:
            stop()
        self._hold(f"{out.name} written", ok=True)
        return True

    def _key_from_file(self):
        """Load a key from a Core wallet backup on a stick or a card."""
        found = []
        for _kind, path in self._file_channels():
            found.extend(signer.find_backups(path))
        if not found:
            self._hold("no backup file on the stick or card")
            return False
        i = self._pick(lambda sel: screens.restore_menu(
            self.w, self.h, [p.name for p in found], sel), len(found))
        if i is None:
            return False
        passphrase = self._ask_passphrase("BACKUP  PASSPHRASE")
        if passphrase is None:
            return False
        stop = self._busy("Bitcoin Core is restoring the key…")
        try:
            self.key = signer.restore_encrypted(self.rpc, found[i], passphrase)
        finally:
            stop()
        return True

    def _backup_paper(self, name, xfp):
        """The paper backup: Core's master xprv for this key, in
        four-character groups over as many pages as it needs."""
        xprv = signer.master_xprv(self.rpc, wallet=name)
        return self._show_backup(xprv, f"KEY  {(xfp or '').upper()}")

    def _discard(self, name, xfp):
        """Discard key asks first; BACK is pre-selected. Returns True when
        the key is gone."""
        selected = 0
        while True:
            self.display.show(screens.confirm_discard(self.w, self.h, xfp,
                                                      selected))
            key = self.buttons.read()
            if key in ("l", "r"):
                selected = 1 - selected
            elif key in ("b", "c"):
                return False
            elif key in ("a", "p"):
                if selected == 0:
                    return False
                signer.close_key(self.rpc, name)
                if self.key == name:
                    self.key = None
                return True

    def state_settings(self) -> bool:
        """Settings menu. Returns True if the user chose power off (the
        session ends), False on back. About is informational."""
        selected = 0
        while True:
            selected = self._pick(
                lambda sel: screens.settings_menu(self.w, self.h, sel),
                len(screens.SETTINGS_OPTIONS), start=selected)
            if selected is None:
                return False
            if selected == 0:              # power off
                return True
            # about: show, then any key returns to the settings menu
            self.display.show(screens.about(self.w, self.h))
            self.buttons.read()

    # -- loading a key: the four Core-native forms (ticket 07) ------------

    def state_load_key(self) -> bool:
        selected = self._pick(
            lambda sel: screens.load_key_menu(self.w, self.h, sel),
            len(screens.LOAD_KEY_OPTIONS))
        if selected is None:
            return False
        try:
            # PLAN A-22: only what Core understands. Corky hands each of
            # these to importdescriptors as an opaque string.
            return [self._key_by_scan,
                    self._key_descriptor_typed,
                    self._key_xprv_typed,
                    self._key_from_file][selected]()
        except self.HANDLED as exc:
            # Hold the message: without a key wait the home screen repaints
            # immediately and the user sees only a flicker.
            self._hold(str(exc)[:60])
            return False

    def _key_by_scan(self):
        """Scan a key: what the camera read decides the form (ticket 05).
        An xprv begins with xprv or tprv; anything else is handed to Core
        as a descriptor, and Core is the one that refuses it."""
        payload = self._keymaterial("key")
        if payload is None:
            return False
        if payload.startswith(signer.XPRV_PREFIXES):
            self.key = signer.open_session_xprv(self.rpc, payload)
        else:
            self.key = signer.open_session_descriptors(
                self.rpc, payload.splitlines())
        return True






    def _text_entry(self, title, charset, secret=False):  # noqa: C901 - one keypad state machine; splitting it would hide the rules
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


    def _keymaterial(self, kind):
        """Warning screen (A-14: the QR IS the wallet), then scan."""
        self.display.show(screens.keymaterial_warning(self.w, self.h, kind))
        while True:
            key = self.buttons.read()
            if key in ("a", "p"):
                try:
                    payload = self._scan_key_guarded().strip()
                except qrchannel.ScanAborted:
                    return None
                except qrchannel.ScanTimeout as exc:
                    self._hold(str(exc))
                    return None
                self.display.show(screens.busy(self.w, self.h,
                                               "importing into Core…"))
                return payload
            if key in ("b", "c"):
                return None

    def _scan_key_guarded(self):
        """Read one static QR carrying key material, with stopping rules.

        Ticket 09, on the M1 map's ticket 05 rules. A tick with nothing in
        view is not a fault; a scan that makes no progress for
        NO_PROGRESS_TIMEOUT seconds gives up and says so; B or C aborts at
        any point; a board with no camera says so at once, because that
        answer will never change (I-8).

        The viewfinder is painted throughout. That is not decoration: on
        the board, aiming blind gave one read in 120 seconds, and the same
        target with a viewfinder gave 53 in 90 (hw/HARDWARE.md).

        The length cap and the charset check are the A-11 guards, applied
        before anything downstream sees the payload. A-22 note: this
        survives the pure-signer cut, because it guards the xprv and
        descriptor scans, which are Core-native forms; only the modes that
        TRANSFORMED what they read went to the lab.
        """
        # This path accepts whatever it reads, then guards it. "Scan a key"
        # means the user is deliberately holding a key up, so a payload
        # that is not one earns a message saying why, not a silent skip.
        # The Scan tile is the opposite case and classifies first, because
        # a general-purpose lens meets stray codes all day (ticket 05).
        return self._guard_key_payload(
            self._scan_until("hold the key QR in view", lambda _p: "key")[1])

    def _scan_until(self, message, classify):
        """Read codes until `classify` accepts one. Returns (kind, payload).

        `classify` returns a kind, or None for a code this scan does not
        want, which is counted and skipped. Every stopping rule lives here
        and nowhere else, which is ticket 04's contract.
        """
        deadline = self.clock() + qrchannel.NO_PROGRESS_TIMEOUT
        stream = self.qr.strings()
        skipped = 0
        while True:
            try:
                payload = next(stream)
            except StopIteration:
                why = getattr(self.qr, "unavailable", None)
                if why:
                    raise RuntimeError(f"no camera: {why}") from None
                payload = None
                stream = self.qr.strings()
            if payload is not None:
                kind = classify(payload)
                if kind:
                    return kind, payload
                # Ticket 05 says count it, skip it, keep scanning. Saying
                # the count is what tells the operator the camera IS
                # reading, and that what it reads is not what is wanted.
                skipped += 1
            caption = message
            if skipped:
                caption = f"{message} ({skipped} skipped)"
            self.display.show(screens.scanning(
                self.w, self.h, getattr(self.qr, "last_image", None),
                caption, 0.0))
            if self.buttons.pressed() in ("b", "c"):
                raise qrchannel.ScanAborted("cancelled")
            if self.clock() > deadline:
                raise qrchannel.ScanTimeout(
                    f"nothing read in {int(qrchannel.NO_PROGRESS_TIMEOUT)}s")
            time.sleep(0.02)

    def _guard_key_payload(self, payload):
        """The A-11 guards, in one place, for any source."""
        raw = payload.encode() if isinstance(payload, str) else payload
        if len(raw) > MAX_KEY_PAYLOAD:
            raise RuntimeError("key payload too large, refusing")
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            raise RuntimeError("key payload has invalid characters") from None
        if not set(text) <= _KEY_CHARSET:
            raise RuntimeError("key payload has invalid characters")
        return text

    def _key_descriptor_typed(self):
        """S3: a descriptor typed on the grid, for a camera-less build or a
        descriptor that never existed as a QR."""
        text = self._text_entry("PRIVATE  DESCRIPTOR", "descriptor")
        if not text:
            return False
        stop = self._busy("importing into Core…")
        try:
            self.key = signer.open_session_descriptors(self.rpc, [text])
        finally:
            stop()
        return True

    def _key_xprv_typed(self):
        """S3: an xprv typed on the grid."""
        text = self._text_entry("BIP32  EXTENDED  PRIVATE  KEY", "xprv")
        if not text:
            return False
        stop = self._busy("importing into Core…")
        try:
            self.key = signer.open_session_xprv(self.rpc, text)
        finally:
            stop()
        return True

    #: The check itself is image/leak-check.sh, written once and read two
    #: ways: by a person over a terminal, and by this screen through
    #: --porcelain. A hardened board has no SSH, so the panel may be the
    #: only place this report can be read.
    LEAK_CHECK = Path(__file__).resolve().parent.parent / "image" / "leak-check.sh"

    def _tool_leak_check(self):
        """Run the leak check and put its rows on the panel.

        The d-pad scrolls, and A, B or C leaves. There is nothing here to
        choose, so no button pretends otherwise.
        """
        stop = self._busy("checking every way off this board…")
        try:
            out = subprocess.run(["bash", str(self.LEAK_CHECK), "--porcelain"],
                                 capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            stop()
            return self._hold(f"leak check did not run: {str(exc)[:38]}")
        finally:
            stop()
        leaks, clear = [], []
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            verdict, label, state = parts[0], parts[1], parts[2]
            if verdict == "FAIL":
                leaks.append((label, state, "red"))
            elif verdict == "ok":
                clear.append((label, state, "normal"))
        rows = leaks + clear          # what you opened this for comes first
        if not rows:
            return self._hold("leak check produced no report")
        cursor = 0
        while True:
            self.display.show(screens.leak_report(self.w, self.h, rows, cursor))
            key = self.buttons.read()
            if key in ("a", "b", "c", "p"):
                return
            if key in ("u", "l"):
                cursor = max(0, cursor - 1)
            elif key in ("d", "r"):
                cursor = min(len(rows) - 1, cursor + 1)

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
            name = signer.generate_wallet(self.rpc)
        finally:
            stop()
        self.key = name
        # The paper backup is the master xprv in Core's own encoding, in
        # four-character groups. No split option: an xprv is a BIP32 node
        # rather than a seed, so there is nothing to split. It is now the
        # SECOND option, because the file backup never reads the key out of
        # Core (Ben, 2026-09-05).
        xfp = signer.master_fingerprint(self.rpc, wallet=name)
        # The backup CHOICE, not the paper one by default (Ben, 2026-09-05).
        # A key Core has just made can be backed up to an encrypted file
        # without ever being drawn on a screen, and that is now the first
        # option. A key with no backup at all is a key nobody can recover,
        # so refusing to back it up still discards it.
        if not self._backup(name, xfp):
            signer.close_key(self.rpc, name)     # only the key just made
            return False
        # The first receive address in full, so the transcription can be
        # checked later against any wallet restored from it. Never
        # truncated, and never getnewaddress: that advances the wallet's
        # index every time the screen is drawn (ticket 06).
        self._show_addresses(name, "wpkh", count=1)
        return True

    def _show_backup(self, text, label):
        """Show one backup string across as many screenfuls as it needs.

        Core's 111-character master xprv overruns one screen; drawing it as
        one column asked the user to transcribe characters that were never
        on the panel. A advances and
        finishes on the last page, B or UP re-shows the previous page for
        checking against paper, C aborts. Returns False on abort."""
        pages = screens.text_pages(text)
        i = 0
        while True:
            self.display.show(screens.backup_page(
                self.w, self.h, pages[i], label,
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
        fault, however long it takes. B or C returns to the channel menu.

        A file that cannot be read says why, on the screen, and the wait
        goes on. Silence here was a real defect: an unreadable file left
        the device asking for a stick that was already in it (D18).
        """
        message = "insert the stick…"
        refused = None          # (path, size) already reported, do not re-read
        while True:
            self.display.show(screens.busy(self.w, self.h, message))
            if self.stick_dir:
                found = filechannel.find_unsigned(self.stick_dir)
                here = None
                if found:
                    try:
                        here = (found[0], found[0].stat().st_size)
                    except OSError:
                        here = None
                if here and here != refused:
                    if filechannel.wait_stable(found[0]):
                        try:
                            psbt = filechannel.read_psbt(found[0])
                        except filechannel.FileChannelError as exc:
                            # Say why, once. Remembering the file by size
                            # keeps the loop polling the buttons instead of
                            # re-reading a file that will not change, and
                            # lets a replaced file be tried again.
                            message = str(exc)[:44]
                            refused = here
                        else:
                            return self.state_review(psbt, found[0])
                    else:
                        message = f"{found[0].name}: still being written…"
            key = self.buttons.pressed()
            if key == "b":
                return self.state_load()
            if key == "c":
                return TO_HOME
            time.sleep(0.2)

    def _load_by_qr(self):  # noqa: C901 - the scan loop the M1 map reviewed line by line; keep it in one place
        psbt, source = None, None
        qr_frames = None
        notice = {"text": "hold the QR in view"}

        def on_event(kind, _detail):
            # The screen string ticket 03 asked for, and ticket 05's restart.
            # screens.busy already takes a message, so no new screen is needed.
            if kind == "advisory":
                notice["text"] = "large frames: set Sparrow to Low density"
            elif kind == "restart":
                notice["text"] = "different transaction, starting again…"

        scan = qrchannel.PsbtScan(on_event=on_event)
        shown = notice["text"]
        while psbt is None:
            # No stick polling here. Ticket 05: the stick is not a Scan
            # thing, and state_load's own rule is that a chosen channel is
            # the only one that runs.
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

    def _key_for(self, psbt):
        """Which loaded key signs this transaction (ticket 03).

        Core's decodepsbt names the fingerprint on every input. One key
        loaded: no screen. Several: the key screen, with the owner
        pre-selected and non-owners greyed. Nobody owns it: a held refusal
        that names the fingerprint the transaction wants. A transaction
        that carries no fingerprints at all is left to the current key and
        Core's own verdict. Returns a wallet name, or None to go home.
        """
        self._refresh_keys()
        if not self.keys:
            self._hold("load a key first")
            return None
        owners = signer.owners(self.rpc, psbt)
        matches = [k for k in self.keys if k.xfp in owners]
        if owners and not matches:
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="no loaded key owns it; wants " + ", ".join(sorted(owners))))
            self.buttons.read()
            return None
        if len(self.keys) == 1:
            return self.keys[0].name
        keys = self.keys
        selected = self._pick(
            lambda sel: screens.choose_key(self.w, self.h, keys, owners, sel),
            len(keys), start=keys.index(matches[0]) if matches else 0)
        if selected is None:
            return None
        self.key = keys[selected].name
        return self.key

    def state_review(self, psbt, source):
        wallet = self._key_for(psbt)
        if wallet is None:
            return TO_HOME
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
                input_total_btc=info["input_total_btc"],
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
                return self.state_sign(psbt, source, wallet)
            elif key == "b":
                return TO_HOME       # back to home, key still loaded (D7)
            elif key == "c" or (key in ("a", "p") and sel == 0):
                self.display.show(screens.result(
                    self.w, self.h, ok=False, detail="rejected by user"))
                self.buttons.read()
                return TO_HOME

    def state_sign(self, psbt, source, wallet):
        stop = self._busy("signing in Core…")
        try:
            signed = signer.sign_psbt(self.rpc, psbt, wallet=wallet)
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
    ap.add_argument("--card-dir")
    ap.add_argument("--qr-psbt", help="dev: file of UR frames, one per line")
    ap.add_argument("--qr-key", help="dev: file with an xprv or descriptor")
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
            animate=not args.dev, on_device=not args.dev,
            card_dir=args.card_dir).run()


if __name__ == "__main__":
    main()
