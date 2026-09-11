"""Core Signer's session state machine: the program the device boots into.

States. Every tile is a JOB, not a device (Ben, 2026-09-05). The camera is
a means: Sign uses it for a transaction, Keys for a key, Tools to check an
address. Naming the first tile after the camera made it the place
everything happened, and then no word fitted it.

  HOME (2x2: sign / keys / tools / settings)
    SIGN  -> a transaction, from the camera or a stick
          -> REVIEW -> sign -> RESULT, which offers SIGN ANOTHER or
             POWER OFF. Back returns to HOME, keys still loaded (D7).
    KEYS  -> the loaded keys by fingerprint, then New key, Scan a key,
             Type private key (A-22: only forms Core reads)
          -> one key: export public key, receiving addresses, backup
             key, discard key
    TOOLS -> the device, not your keys: check for leaks, check an address
  Power off lives in SETTINGS (PLAN A-15c).

Every screen comes from screens.py, every wallet operation from signer.py,
every transfer from qrchannel/filechannel. This module holds no crypto and
parses no untrusted bytes; it is the traffic cop.

QR input arrives through a QrSource: on the device that is the camera (M1);
in dev mode it reads payloads from files so every state is exercisable
without hardware.

Dev mode:
    python3 coresigner/main.py --dev --datadir <dir> --chain regtest \
        --script "<keys>" [--stick-dir DIR] [--qr-psbt FILE]
        [--qr-key FILE] [--frames-dir DIR]
Keys (PLAN A-15c, eight controls): u/d/l/r = d-pad, p = centre press,
a = select/KEY1, b = back or delete/KEY2, c = abort/KEY3. Key material
reaches Bitcoin Core through `bitcoin-cli -stdin`, never as an argument,
so it cannot appear in a process listing (signer.Rpc.call, S4).
"""

import argparse
import os
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
# The QR sources moved to coresigner/qrsource.py on 2026-09-08. They are the
# one place in Core Signer where the dev harness substitutes for hardware,
# which is a real seam; the other groupings inside Session are not,
# because they all reach into the same shared session state. Only the two
# main() picks between are imported: re-exporting the base class as well
# would make main.py look like their home, which it is not.
from qrsource import CameraQrSource, DevQrSource


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


#: The most inputs this board will sign, and it is a memory limit.
#:
#: Measured with the M0 gate on a Pi Zero 2 W, 2026-09-06, on the shape
#: that costs the most: inputs funded 100 to a transaction, the way an
#: exchange pays a batch of withdrawals. Every input carries the whole
#: transaction that paid it, so that shape is 2,778 bytes per input
#: against 378 for an ordinary payment.
#:
#:   150 inputs   121MB headroom   PASS
#:   175 inputs   114MB headroom   PASS
#:   200 inputs    78MB headroom   FAIL   (100MB required)
#:   250 inputs    72MB headroom   FAIL
#:
#: 150 is the largest count measured to pass with room to spare, and the
#: cliff between 175 and 200 is 36MB, so the line is drawn below it
#: rather than on it.
#:
#: This is bitcoind's memory and not Core Signer's. Core Signer's own process was cut
#: from 56MB to 45MB by not reading previous transactions it never used,
#: and the headroom moved 2MB. No further work of ours raises this
#: number; a board with more RAM does.
MAX_SIGNABLE_INPUTS = 150

#: The same ceiling for a QUORUM, which costs more per input: a witness
#: script and a derivation entry per cosigner rather than one, and M9
#: undropped both for the review screen.
#:
#: **Measured on the Zero 2 W, 2026-09-11**, swap off, funding batch 100,
#: `m0/m0_gate.py --inputs N --quorum 2-of-3`. MemAvailable low-water,
#: against the 100MB the gate requires:
#:
#:     2-of-3   100   146MB      single-sig   150   139MB
#:              120   129MB                   175   123MB
#:              150   107MB
#:              175    92MB  FAIL
#:
#: **A 2-of-3 at 150 passes.** The cap is not 150 for the same reason the
#: single-sig cap is not 175: the line is drawn below the cliff rather
#: than on it. 150 would leave 7MB over the limit where the single-sig
#: cap leaves 39MB, and the fall from 150 to 175 is 15MB. 120 leaves
#: 29MB, which is the margin the number above already buys.
#:
#: A dev-machine estimate put this at 120 by scaling the decode cost,
#: which a 2-of-3 raises 1.23x. The ratio was right and the inference
#: was crude: bitcoind's own RSS carries it on the board, 97MB against
#: 117MB at 150 inputs, and a cap follows where the 100MB line falls
#: rather than the other cap times a ratio. The number landed in the
#: right place for a reason it did not have until it was measured.
MAX_SIGNABLE_MULTISIG_INPUTS = 120

# What a PSBT run reports back to the home screen.
SIGN_AGAIN, POWER_OFF, TO_HOME = "again", "off", "home"

#: How far Bitcoin Core's `ismine` reaches, and therefore how far "Check
#: an address" can see. A FLOOR, not a ceiling: index 0 to 999 of a
#: freshly loaded key answer True. Measured against v31.1 by binary
#: search on 2026-09-08, at the default keypool and again at
#: `-keypool=50`:
#:
#:   freshly generated (createwallet)     keypool - 1        999, then 49
#:   freshly imported (importdescriptors) the LARGER of that
#:                                        and the declared
#:                                        range end          999, then 200
#:   the same imported key, after it
#:   has signed                                             1000
#:
#: Three facts fall out of that. The declared `range` in
#: signer._desc_entry is [0, 200] and does not bind, because Core Signer sets
#: no keypool and Core's default is 1000. The two ways in are bounded by
#: different things and agree only at those defaults. And the reach GROWS
#: with use, because Core tops the keypool up ahead of the highest index
#: handed out, so no single number is exact for a wallet with a history.
#:
#: A floor is the honest thing to quote, and the screen quotes it: "not
#: in the first 1000 addresses", never "this key does not own that". A
#: verification tool that says a mistaken no is worse than one that says
#: what it checked. tests/test_keys.py measures all three rows and fails
#: if the floor moves. The comment here used to name the keypool alone,
#: which is right for one of the two paths (two-axis review, 2026-09-08).
ADDRESS_CHECK_DEPTH = 1000

#: A channel loader returns this when B was pressed: go back to the
#: channel menu. It used to `return self.state_load()`, which is mutual
#: recursion, and the stack grew by a frame every time somebody pressed
#: back. 500 presses raised RecursionError and took the UI down with it,
#: measured 2026-09-07. On a device whose only recovery is a restart, and
#: whose restart clears the loaded key, a button doing that is a way to
#: lose your session by fidgeting.
BACK_TO_CHANNELS = "channels"

# How the board is halted. Under systemd the poweroff is the whole teardown:
# it stops coresigner-bitcoind.service by that unit's own ExecStop, which runs
# bitcoin-cli stop and waits up to TimeoutStopSec=30. FALLBACK_HALT_CMD and
# an explicit node stop cover a board that runs Core Signer without systemd.
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


def _next_kind(kind, key, order):
    """The next script policy, walking `order` either way.

    Core makes four and one private key opens all four, so LEFT and RIGHT
    walk every policy this key HAS rather than flipping between two (map
    ticket T0). `order` comes from signer.available_kinds, because a key
    that arrived by scan has fewer than a key Core generated.
    """
    if not order:
        # order[0] on an empty tuple is the same IndexError that ended
        # the process in _page_addresses and _export. Its one caller is
        # guarded now, so this is unreachable today and one line to keep
        # unreachable tomorrow (2026-09-07).
        return kind
    if kind not in order:
        return order[0]
    step = 1 if key == "r" else -1
    return order[(order.index(kind) + step) % len(order)]


def _grid_move(key, pages, page, cur):
    """One step of the character grid, shared by every typed screen.

    The grid is one strip read left to right: L and R step a cell and
    cross rows, U and D jump a row. A page turns at the strip's ends with
    L or R, and ALSO when U or D would leave the top or bottom row, which
    is the cheap way across and lands on the same column.

    **That second rule is worth 62 presses, and the first version of this
    docstring claimed 710.** The claim came from comparing the shortest
    route under the new rules against the OLD TEST HELPER's route, which
    walked to the end of the strip on every page turn because it was
    written that way. Comparing like with like, by searching for the
    shortest route under each rule set, typing the whole key costs 646
    presses under the old rules and 584 under the new.

    So most of the saving was never the code's: it came from replacing a
    helper that wrote a route down with one that searches for it. Rule 6
    exists for exactly this, and it caught me
    (tests/test_ui_cost.py measures the current cost).

    Returns the new (page, cur). An unrelated key gives them back unchanged.
    """
    n = len(pages[page])
    if key == "u":
        if cur < 8 and page > 0:
            page -= 1
            return page, min(((len(pages[page]) - 1) // 8) * 8 + cur % 8,
                             len(pages[page]) - 1)
        return page, max(0, cur - 8)
    if key == "d":
        if cur // 8 == (n - 1) // 8 and page + 1 < len(pages):
            page += 1
            return page, min(cur % 8, len(pages[page]) - 1)
        return page, min(n - 1, cur + 8)
    if key == "l":
        if cur == 0 and page > 0:
            return page - 1, len(pages[page - 1]) - 1
        return page, max(0, cur - 1)
    if key == "r":
        if cur == n - 1 and page + 1 < len(pages):
            return page + 1, 0
        return page, min(n - 1, cur + 1)
    return page, cur


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
        own unit, /run/coresigner stays mounted, and the ST7789 holds its last
        frame, so the operator reads POWER OFF on a device that is still
        live and still holding a wallet-shaped ramdisk.

        Under systemd the poweroff is the whole teardown, so this does not
        stop the node itself: coresigner-bitcoind.service does that in its own
        ExecStop, in shutdown order, with a 30 second timeout. Without
        systemd nothing else will, so the fallback stops the node first.

        The ramdisk is NOT wiped here. close_session already deletes the
        wallet directory, which is the only secret-bearing path under
        /run/coresigner, and the rest is a wallet-only node's own state. The
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
        # The other funnel, redacted for the same reason as _hold.
        self.display.show(screens.result(self.w, self.h, ok=False,
                                         detail=signer.redact(detail)))
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
                    outcome = [self.state_sign,    # 0 sign
                               self.state_keys,    # 1 keys
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
        cannot read is a message the user cannot act on).

        DONE, not SIGNED: this screen carries every message the device
        parks, and only one of them is a signature.

        REDACTED HERE, because this is the funnel. Ten call sites put
        `str(exc)` on this screen, and Rpc.call only redacts what Core
        writes to STDERR: a failure Core reports in the JSON body, or any
        future message built some other way, arrives unredacted.
        Redacting per caller means ten places to remember and one to
        forget. screens.result would be the better seam still, but
        screens.py is Layer 3 and may not import the redactor.
        """
        self.display.show(screens.result(self.w, self.h, ok=ok,
                                         detail=signer.redact(detail),
                                         label="DONE" if ok else "FAILED"))
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

        Nothing in here may take the process down. `coresigner.service` has
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

    def state_sign(self):
        """The Sign tile: a transaction, from the camera or a stick.

        One job, one home. The camera used to be the tile, which made it
        the place everything happened and left no word that fitted it
        (Ben, 2026-09-05). It is a means now, used here for a transaction,
        under Keys for a key, and under Tools to check an address.
        """
        self._refresh_keys()
        if not self.keys:
            self._hold("load a key first")
            return None
        return self._sign_loop(self.state_load)

    def _tool_check_address(self):
        """Point the camera at an address and ask Core whose it is.

        The one question a coordinator cannot answer for you: whether the
        address on that other screen belongs to a key in your hand.
        """
        self._refresh_keys()
        if not self.keys:
            self._hold("load a key first")
            return
        try:
            _kind, payload = self._scan_until(
                "hold the address QR in view",
                lambda p: "address" if _classify_qr(p) == "address" else None)
        except qrchannel.ScanAborted:
            return
        except qrchannel.ScanTimeout as exc:
            return self._hold(str(exc))
        except self.HANDLED as exc:
            return self._show_core_error(exc)
        self._check_address(payload)

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
        # NOT "no loaded key owns that address". Core answers ismine from
        # the addresses it has DERIVED, which for a freshly loaded key is
        # index 0 to 999: beyond that an address the key really does own
        # comes back False. A verification tool that says a mistaken no is
        # worse than one that says what it checked, so it says what it
        # checked. See ADDRESS_CHECK_DEPTH for why that is a floor and how
        # it was measured.
        self._hold(f"not in the first {ADDRESS_CHECK_DEPTH} addresses "
                   f"of any loaded key")
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
            if action >= 0:
                if not self._load_key(action):
                    continue
            else:
                self.key = keys[selected].name
            outcome = self.state_key_menu(self.key)
            if outcome in (POWER_OFF, TO_HOME):
                return outcome
            # Come back to the key you were just working with, not to the
            # row number you happened to be on. Loading a key adds a row at
            # the top, so the old number pointed at something else.
            self._refresh_keys()
            selected = next((i for i, k in enumerate(self.keys)
                             if k.name == self.key), 0)

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
            if selected == 0:
                self._export(name)
            elif selected == 1:
                self._browse_addresses(name)
            elif selected == 2:
                self._backup_paper(name, xfp)
            elif selected == 3 and self._discard(name, xfp):
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
            elif choice == 1:
                self._tool_check_address()

    # -- export the public key (ticket 12) ---------------------------------

    def _pick(self, render, count, start=0):
        """Run one list screen. Returns the chosen index, or None on back.

        Every menu goes through here: the keys list, a key's menu, Tools,
        Load a key, Settings, the key chooser, export and its sub-menus.
        Ten copies of this loop used to sit beside it (review, 2026-09-05).
        `start` lets a menu reopen on the row the user was on.

        An EMPTY menu returns at once. It used to set sel to 0 and wait
        for a press, and the first d-pad key divided by count: a
        ZeroDivisionError, which is not in HANDLED, so it ended the
        process rather than painting an error. `_export` can reach it,
        because `available_kinds` returns only the policies a wallet
        actually holds and `signer` documents that a wallet imported as a
        bare descriptor need not hold any (found reading main.py,
        2026-09-07).
        """
        if not count:
            return None
        sel = start % count
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
        """The file channels that exist right now, in offer order.

        On the device a channel counts only when something is MOUNTED
        there. `/mnt/usb` is an ordinary directory on the boot card when no
        stick is in the port, so a directory test said "stick" whether or
        not a stick existed: the file went to the SD card's root
        filesystem, and the screen said it was written, naming no place
        (Ben, on the board, 2026-09-05, found as a watch-only file sitting
        in /mnt/usb with no stick attached).

        Only public data takes this chooser now: the watch-only wallet
        file Bitcoin Core needs because it reads no QR, and PSBTs. The
        encrypted key backup went with PLAN A-24, so the worst a wrong
        destination costs is a public file in the wrong place.

        In dev there is nothing mounted anywhere, so a directory is the
        channel; the mount rule is the device's, and
        tests/test_channels.py runs it by faking the mount check.
        """
        found = []
        for name, path in (("stick", self.stick_dir), ("card", self.card_dir)):
            if path and path.is_dir() and self._is_mounted(path):
                found.append((name, path))
        return found

    def _is_mounted(self, path):
        """Is anything actually mounted at `path`? Only asked on device."""
        return os.path.ismount(path) if self.on_device else True

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
        """Script type, then how it leaves, then the key, then the
        addresses to check it against (map D2, revised by Ben on the board
        2026-09-05).

        SeedSigner's shape, minus the two questions we proved were noise.
        It asks signature type, script type and coordinator before the QR.
        Single-sig makes the first meaningless, and the coordinator chooser
        made an identical QR four times out of five (R3).

        Ben's own earlier objection was to choosing a destination "before
        getting the key", and this does not contradict it: that chooser
        asked a question with the same answer nearly every time, and this
        one picks between photons, your fingers and a file, which are
        genuinely different things.
        """
        order = signer.available_kinds(self.rpc, name)
        if not order:
            # Nothing to offer. Saying so beats a menu with no rows.
            return self._hold("this key has no policies to export")
        # The cosigner rows sit under the four policies (M1 decision 3).
        # `order` stays the four, and the extra rows are indexed past it,
        # so `available_kinds` keeps meaning what it always did.
        path = signer.cosigner_path(self.rpc)
        shown = "m/" + path.replace("h", "'")
        # The SAME list screens draws, so the label and the handler cannot
        # drift apart (TESTING.md rule 11).
        rows = screens.script_rows(order, shown)
        selected = 0
        while True:
            selected = self._pick(
                lambda sel, o=order, p=shown: screens.script_menu(
                    self.w, self.h, o, sel, cosigner_path=p),
                len(rows), start=selected)
            if selected is None:
                return
            kind = rows[selected][2]
            if kind == screens.COSIGNER_KIND:
                if self._export_cosigner(name, path):
                    return
                continue
            if kind == screens.ADVANCED_KIND:
                if self._export_advanced(name):
                    return
                continue
            # A completed export leaves the flow. It used to drop back on
            # the script type, which read as "that did not work" after an
            # export that had worked (Ben, on the board).
            if self._export_one(name, kind):
                return

    #: Which account the NAMED cosigner rows derive at. One session's
    #: choice, never written anywhere, like every other thing this device
    #: holds.
    cosigner_account = 0

    def _export_advanced(self, name):
        """The nested path, the account number, and a typed path.

        M1 decision 3 puts these one level down, which is Coldcard's
        structure: "the free-text row is one level down, where it is not
        reached by accident, and it is the only route to a blinded xpub".

        Returns True when an export finished, which ends the whole flow.
        """
        while True:
            nested = signer.cosigner_path(self.rpc, "sh-wsh",
                                          self.cosigner_account)
            rows = screens.advanced_rows("m/" + nested.replace("h", "'"),
                                         self.cosigner_account)
            chosen = self._pick(
                lambda sel, r=rows: screens.advanced_menu(
                    self.w, self.h, r, sel),
                len(rows))
            if chosen is None:
                return False
            kind = rows[chosen][2]
            if kind == screens.NESTED_KIND:
                if self._export_cosigner(name, nested):
                    return True
            elif kind == screens.ACCOUNT_KIND:
                picked = self._pick(
                    lambda sel: screens.account_menu(self.w, self.h, sel),
                    screens.ACCOUNTS, start=self.cosigner_account)
                if picked is not None:
                    self.cosigner_account = picked
            elif self._export_typed_path(name):
                return True

    def _export_typed_path(self, name):
        """Any path at all, typed, and echoed back before it leaves.

        The echo is M2's, and the reason is M1's: a typed path is the only
        route to a blinded xpub, and blinding is where a typo cannot be
        recovered from. Core builds the checksum, so the thing being
        checked is Core's reading of the path and not Core Signer's.
        """
        typed = self._text_entry("DERIVATION  PATH", "path")
        if not typed:
            return False
        # `48h/1h/0h/2h` is the shape signer wants. A person types what
        # they read off a coordinator, which usually carries the m/ and
        # may use either hardened mark.
        path = typed.strip().replace("'", "h").strip("/")
        if path.startswith("m/"):
            path = path[2:]
        stop = self._busy("asking Core about that path…")
        try:
            checksum = signer.cosigner_qr(
                self.rpc, name, path).rsplit("#", 1)[1]
        except RuntimeError as exc:
            stop()          # before _hold blocks; see _tool_leak_check
            self._hold(signer.redact(str(exc))[:60])
            return False
        finally:
            stop()
        # An ACTION BAR, so LEFT and RIGHT move and A chooses, which is
        # `_discard`'s loop and not `_pick`'s: `_pick` drives list rows
        # with UP and DOWN. BACK is pre-selected, so the export is
        # chosen and never landed on.
        shown = "m/" + path.replace("h", "'")
        selected = 0
        while True:
            self.display.show(screens.path_echo(self.w, self.h, shown,
                                                checksum, selected))
            key = self.buttons.read()
            if key in ("l", "r"):
                selected = 1 - selected
            elif key in ("b", "c"):
                return False
            elif key in ("a", "p"):
                if selected == 0:
                    return False
                return self._export_cosigner(name, path)

    def _export_cosigner(self, name, path):
        """This key as ONE COSIGNER of somebody else's quorum.

        Two routes and two payloads, which is map M8 measured against
        Sparrow's own importers. The QR carries a whole descriptor,
        because the scan path refuses a bare key expression. The file
        carries that bare expression, because the file importer refuses
        the wrapper. One question reaches the person and the difference
        never does.

        Both screens name the entry to pick in the coordinator. Ben,
        2026-09-10: "the coordinator is going to ask what device type so
        we need to let them know which to choose too." Sparrow's airgapped
        import is an accordion of devices, each with its own Scan and
        Import File buttons, so the person picks the device first either
        way.
        """
        choice = self._pick(
            lambda sel: screens.cosigner_options(self.w, self.h, sel),
            len(screens.COSIGNER_OPTIONS))
        if choice is None:
            return False
        if choice == 0:
            stop = self._busy("building the cosigner code…")
            try:
                payload = signer.cosigner_qr(self.rpc, name, path)
            finally:
                stop()
            # BEFORE the code, because that is the order the person
            # works in: Sparrow's airgapped import is an accordion of
            # devices, each with its own Scan button, so they pick
            # Specter DIY and then point the camera. Saying it after the
            # code is dismissed is saying it too late.
            self._hold("in your coordinator choose Specter DIY, then Scan",
                       ok=True)
            return bool(self._export_qr(name, payload,
                                        screens.COSIGNER_KIND))
        dest = self._choose_channel()
        if dest is None:
            return False
        stop = self._busy("writing the cosigner file…")
        try:
            out = signer.write_cosigner(self.rpc, name, path, dest)
        finally:
            stop()
        self._hold(f"{out.name}: in your coordinator choose Specter DIY, "
                   "then Import File", ok=True)
        return True

    def _export_one(self, name, kind):
        """One policy, out by one route, then the addresses to compare.

        Returns True when the export finished, which ends the flow, and
        False when the user backed out of it, which returns them to the
        script type they came from.
        """
        desc = signer.export_descriptor(self.rpc, name, kind)
        choice = self._pick(
            lambda sel: screens.export_options(self.w, self.h, sel),
            len(screens.EXPORT_OPTIONS))
        if choice is None:
            return False
        shown = [self._export_qr, self._export_text,
                 self._export_file][choice](name, desc, kind)
        if not shown:
            return False
        # The addresses are the check on the export: they are what you
        # compare against the coordinator that just read it. They belong
        # here, AFTER a successful export, rather than opening by
        # themselves at the end of one (Ben, both times).
        self._page_addresses(name, kind, limit=3)
        return True

    #: How long each masked render of the export QR is held. Slow enough
    #: that a scanner locks on one frame rather than straddling two, and
    #: an eighth of the cycle, so the whole set is offered in 2.4s.
    EXPORT_MASK_DELAY = 0.3

    def _export_qr(self, _name, desc, kind):
        """The code, with the fingerprint, the policy and the path on it.

        All three identify what a coordinator is being handed, and Ben
        asked for all three on the screen with the code. They sit in the
        letterbox above and below, so the code itself is untouched.

        **The code cycles through the eight QR mask patterns.** Every
        frame carries this same descriptor whole, so a coordinator reads
        whichever one it catches and needs no support for anything: each
        is an ordinary static QR of identical text.

        It is here because a single static render fails. Roughly one
        descriptor in a hundred gets a mask Sparrow's zxing cannot read
        at this size, and it is the same mask every time, so that key's
        export never worked (ISSUES.md E-5: 4 of 440 measured against
        Sparrow's own scanner). Pixel density, error correction and every
        fixed mask were tested and none of them is the cause. Across 120
        real descriptors the worst had **7 of 8 masks readable**, so
        showing all eight is what takes the failure to nothing.
        """
        xfp, path = signer.origin_of(desc)
        # Sized against QR_MAX_PX, not the panel, so the light card and the
        # line underneath both have room. screens.qr_export does the rest.
        codes = qrchannel.text_to_images(
            desc, panel=(self.w, min(self.h, screens.QR_MAX_PX)))
        frames = [screens.qr_export(self.w, self.h, c, xfp, kind, path)
                  for c in codes]
        if not self.animate:
            # Scripted runs paint one deterministic pass and then read,
            # the way _show_qr_loop does, so a session stays reproducible.
            for img in frames:
                self.display.show(img)
            while True:
                key = self.buttons.read()
                if key in ("b", "c"):
                    return False
                if key in ("a", "p"):
                    return True
        answer = {}
        stop = threading.Event()

        def wait_for_key():
            while True:
                key = self.buttons.read()
                if key in ("a", "p", "b", "c"):
                    answer["key"] = key
                    stop.set()
                    return

        threading.Thread(target=wait_for_key, daemon=True).start()
        while not stop.is_set():
            for img in frames:
                if stop.is_set():
                    break
                self.display.show(img)
                stop.wait(self.EXPORT_MASK_DELAY)
        return answer.get("key") in ("a", "p")

    def _export_text(self, _name, desc, kind):
        """The same descriptor as text, for typing into a coordinator."""
        pages = screens.text_pages(desc)
        i = 0
        while True:
            self.display.show(screens.export_text(
                self.w, self.h, pages[i], page=i, pages=len(pages),
                title=screens.SCRIPT_LABELS[kind].upper()))
            key = self.buttons.read()
            if key == "c":
                return False
            if key in ("b", "u"):
                if i == 0:
                    return False
                i -= 1
            elif key in ("a", "p", "d"):
                if i + 1 == len(pages):
                    return True
                i += 1

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
        # Native segwit first, LEFT or RIGHT to switch to taproot on the
        # screen itself. Asking which script type before showing a single
        # address was a gate in front of the thing you came to see.
        return self._page_addresses(name, "wpkh")

    def _page_addresses(self, name, kind, limit=None):
        """One address per screen, derived by Core.

        `limit` bounds the walk (the export shows three); without it the
        walk goes on, fetching another block when the index leaves this
        one. One screen means one key map, whichever caller opened it:
        down or right goes on, up or left goes back, B or C leaves.
        `deriveaddresses` is side-effect free, so redrawing does not move
        the wallet's address index.
        """
        order = signer.available_kinds(self.rpc, name)
        if not order:
            # order[0] on an empty tuple is an IndexError, which is not in
            # HANDLED and so ends the process. Same root as the empty
            # export menu fixed alongside this: available_kinds returns
            # only the policies a wallet HOLDS, and a wallet imported as a
            # bare descriptor need not hold any (2026-09-07).
            return self._hold("this key derives no addresses")
        if kind not in order:
            kind = order[0]
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
                self.w, self.h, i, block[i - base], kind, total=limit))
            key = self.buttons.read()
            if key in ("b", "c"):
                return
            if key in ("l", "r"):
                # Switch script policy here rather than gating the screen
                # behind a chooser (Ben, 2026-09-05). All four of Core's,
                # in the same order the export walks them (map T0), so a
                # legacy or nested address of this wallet is reachable
                # instead of merely existing.
                kind = _next_kind(kind, key, order)
                i, base, block = 0, 0, []
            elif key == "u":
                i = max(0, i - 1)
            elif key in ("a", "p", "d"):
                if limit is not None and i + 1 >= limit:
                    return
                i += 1

    def _export_file(self, name, _desc=None, _kind=None):
        """Bitcoin Core has no QR reader. Core's own backupwallet writes a
        watch-only wallet its GUI restores with File, Restore Wallet.

        Takes the same three arguments as the other two export routes so
        they can share one dispatch, and returns True when a file was
        written.
        """
        dest = self._choose_channel()
        if dest is None:
            return False
        stop = self._busy("writing the watch-only wallet…")
        try:
            out = signer.write_watch_only(self.rpc, name, dest)
        finally:
            stop()
        self._hold(f"{out.name} written", ok=True)
        return True

    def _backup_paper(self, name, xfp):
        """Backup key. Core's master private key, in four-character groups
        over as many pages as it needs, and there is no other kind.

        There used to be a choice: paper, or a file Core encrypted with a
        passphrase. The file is gone (PLAN A-24). One card slot on this
        board is the boot card, and a private key on the boot card was the
        thing PLAN A-23 kept hedging about. A key that is never written to
        a medium cannot be taken off one.

        The last page offers VERIFY, and VERIFY now types the key back in
        and checks it (Ben, 2026-09-05: it "just takes me back to the
        menu"). Checking is offered, never forced: a writer who wants to
        check later can come back to Backup key and do it then.
        """
        label = f"KEY  {(xfp or '').upper()}"
        xprv = signer.master_xprv(self.rpc, wallet=name)
        outcome = self._show_backup(xprv, label)
        if outcome is None:
            return False
        if outcome == "check":
            self._verify_backup(xprv, label, xfp, name)
        return True

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

    def _load_key(self, action) -> bool:
        """One of the ways to get a key, chosen from the Keys screen.

        Flat, with no LOAD A KEY screen between (Ben, 2026-09-05). The
        order matches screens.KEYS_ACTIONS: make one, or bring one in two
        ways. PLAN A-22: every way in hands Core a string it understands,
        and Core Signer transforms none of them.

        Restore from file went with the encrypted backup (A-24). Paper is
        the only way the key leaves, so paper is the only way it comes
        back, by scanning it or typing it.
        """
        ways = [self._tool_generate,
                self._key_by_scan,
                self._key_xprv_typed]
        try:
            return bool(ways[action]())
        except self.HANDLED as exc:
            # Hold the message: without a key wait, the Keys screen
            # repaints at once and the user sees only a flicker.
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
            if sel is not None:            # focus is on the action bar
                if key in ("l", "r"):
                    sel = 1 - sel
                elif key in ("a", "p"):
                    return text if sel == 1 else None
                elif key in ("b", "c"):
                    sel = None
                continue
            if key in ("u", "d", "l", "r"):
                page, cur = _grid_move(key, pages, page, cur)
            elif key == "a":
                text += pages[page][cur]
            elif key == "b":
                if not text:
                    # Nothing to delete, so B is what B is everywhere else
                    # on this device: back. Without this the screen had no
                    # visible way out and the button did nothing at all
                    # (Ben, on the board, 2026-09-05).
                    return None
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
            self._scan_until("hold the key QR in view", lambda _p: "key",
                             sensitive=True)[1])

    def _scan_until(self, message, classify, sensitive=False):
        """Read codes until `classify` accepts one. Returns (kind, payload).

        `classify` returns a kind, or None for a code this scan does not
        want, which is counted and skipped. Every stopping rule lives here
        and nowhere else, which is ticket 04's contract.

        `sensitive` marks the VIEWFINDER, not the payload. A scan looking
        for a key points a camera at a key, and the frame it paints is a
        photograph of one. hal.DevDisplay writes every frame it is given
        to a PNG unless it is told not to, so scanning a key wrote a
        picture of that key onto a developer's disk, and nothing noticed
        until audit A2 (2026-09-06). The address scan is not marked,
        because an address is public.
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
                # And READING A CODE IS PROGRESS, so the clock starts
                # again. This deadline was set once before the loop and
                # never moved, which made it a total time limit wearing a
                # no-progress name: a scan that decoded a stray code on
                # every single tick still died at 20 seconds saying
                # "nothing read", while the camera was working perfectly
                # (found reading main.py, 2026-09-07). qrchannel.PsbtScan
                # has always reset on progress; this now agrees with it.
                deadline = self.clock() + qrchannel.NO_PROGRESS_TIMEOUT
            caption = message
            if skipped:
                caption = f"{message} ({skipped} skipped)"
            self.display.show(screens.scanning(
                self.w, self.h, getattr(self.qr, "last_image", None),
                caption, 0.0), sensitive=sensitive)
            if self.buttons.pressed() in ("b", "c"):
                raise qrchannel.ScanAborted("cancelled")
            if self.clock() > deadline:
                # Two different failures, and they want different answers
                # from the person holding the device: aim it, or hold up
                # something else.
                # The deadline resets on every read, so whatever else is
                # true, NOTHING has been read for the last `secs`. Say
                # that first, because it is the fact that is always true,
                # and add the skip count because it changes the advice:
                # some skips means the camera works and is pointed at the
                # wrong thing, none means aim it or look at the lens.
                #
                # Keying the whole message off the cumulative count told a
                # camera that read three strays and then went blind to
                # hold up something else, which is the wrong advice from
                # the very change that exists to separate the two
                # (two-axis review, 2026-09-08).
                secs = int(qrchannel.NO_PROGRESS_TIMEOUT)
                raise qrchannel.ScanTimeout(
                    f"nothing read in {secs}s"
                    + (f"; {skipped} skipped earlier" if skipped else ""))
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

    def _key_xprv_typed(self):
        """S3: a master private key typed on the grid."""
        text = self._text_entry("MASTER  PRIVATE  KEY", "xprv")
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
            # stop() HERE as well as in the finally, and it is not
            # redundant: finally runs after this handler, and _hold paints
            # a screen and then blocks on a button. Without this call the
            # spinner thread is still alive and repaints over the error
            # every 150ms, so the operator waits on a busy screen that
            # will never finish. Measured 2026-09-07 while trying to
            # delete it as duplication.
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
            if verdict in ("FAIL", "huh"):
                # "huh" is a check the script could not answer. It shows
                # with the leaks, because a question nobody answered is
                # not a pass, and because a verdict this parser does not
                # recognise used to be dropped on the floor: the row
                # simply never reached the screen (audit of image/,
                # 2026-09-08).
                leaks.append((label, state, "leak"))
            elif verdict in ("ok", "note"):
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
        """New key: Core makes one, and that is the whole flow.

        It used to show a screen of tradeoffs you had to accept, then walk
        you into a backup you could not leave without losing the key. Both
        are gone (Ben, 2026-09-05). Clicking New key makes a key. The
        tradeoffs are the README's job, where there is room to state them
        properly, and Backup key is a row on the key's own menu, chosen
        when you want it.

        A-19 still holds underneath: `createwallet` makes the master key
        with Core's own RNG and Core Signer signs with that very wallet. Nothing
        of ours sits between Core's RNG and your paper.
        """
        stop = self._busy("Bitcoin Core is generating your key…")
        try:
            self.key = signer.generate_wallet(self.rpc)
        finally:
            stop()
        return True

    def _show_backup(self, text, label):
        """Show one backup string across as many screenfuls as it needs.

        Core's 111-character master private key overruns one screen;
        drawing it as one column asked the user to transcribe characters
        that were never on the panel. A advances, B or UP re-shows the
        previous page for checking against paper, C aborts.

        On the LAST page the action bar is live: DONE finishes, and
        CHECK IT goes on to type the backup back in. Returns "done",
        "check", or None if the user abandoned it.
        """
        pages = screens.text_pages(text)
        i, sel = 0, 0
        while True:
            self.display.show(screens.backup_page(
                self.w, self.h, pages[i], label,
                page=i, pages=len(pages), actions_sel=sel), sensitive=True)
            key = self.buttons.read()
            last = i + 1 == len(pages)
            if key == "c":
                return None
            if key in ("b", "u"):
                if i == 0:
                    return None     # nothing earlier: BACK is ABORT here
                i -= 1
                sel = 0
            elif key in ("l", "r") and last:
                sel = 1 - sel
            elif key in ("a", "p", "d"):
                # DOWN turns the page, as it does on the export's text
                # pages. It did nothing here, so the same gesture worked
                # on one paged screen and not the other.
                if last:
                    if key == "d":
                        continue
                    return "check" if sel == 1 else "done"
                i += 1

    # -- checking a written backup (Ben, 2026-09-05) ----------------------

    def _verify_backup(self, text, label, xfp, name):
        """Type the written backup back in, one page at a time, and find
        out whether the paper is right.

        The last backup page offered VERIFY and then just went back, which
        is a label that lies. This is the flow it promised.

        Page by page, because a page is what the writer copied and a
        mistake should cost one page and not all 111 characters. The
        per-character comparison is Core Signer's, because only Core Signer is holding
        both strings; the verdict on the WHOLE key is Core's, and it is
        put as "do the addresses this key derives match the ones this
        wallet hands out". Both must agree before this says the paper is
        good. (It cited `getdescriptorinfo` until 2026-09-07, which audit
        A6 had already replaced.)

        Returns True when the paper is proven, False when the user leaves.
        """
        pages = screens.text_pages(text)
        typed = []
        for i, page in enumerate(pages):
            got = self._check_page(label, i, len(pages), page)
            if got is None:
                return False
            typed.append(got)
        return self._confirm_typed_key("".join(typed), name, xfp)

    def _confirm_typed_key(self, typed, name, xfp):
        """Core reads what was typed and says whether it is the same key.

        The pages already matched character by character, so a comparison
        against Core Signer's own copy of the backup could only ever agree: it
        would ask whether a string equals itself. Audit A6 (2026-09-06)
        deleted that comparison and every suite stayed green, which is the
        proof it was checking nothing.

        So the question is put to the wallet instead. Core derives receive
        addresses from what was typed, Core reports what the loaded wallet
        hands out, and Core Signer compares the two lists Core returned (PLAN
        A-11). That is the claim the screen makes.
        """
        stop = self._busy("Bitcoin Core is reading what you typed…")
        try:
            same = signer.opens_wallet(self.rpc, name, typed)
        except RuntimeError as exc:
            stop()          # before _hold blocks; see _tool_leak_check
            self._hold(str(exc)[:60])
            return False
        finally:
            stop()
        if not same:
            self._hold("that key does not open this wallet")
            return False
        self.display.show(screens.verified(
            self.w, self.h,
            "your paper opens\n"
            f"key {(xfp or '').upper()}"))
        self.buttons.read()
        return True

    def _check_page(self, label, i, pages, want):
        """One page typed back and judged. Returns the text, or None.

        Loops entry -> verdict -> entry, so FIX returns to the same
        characters with the caret already on the first wrong one. The
        writer never hunts for the mistake the device has already found.
        """
        typed, caret = "", 0
        while True:
            typed, caret = self._check_entry(label, i, pages, len(want),
                                             typed, caret)
            if typed is None:
                return None
            wrong = {n for n, ch in enumerate(typed)
                     if n >= len(want) or ch != want[n]}
            wrong |= set(range(len(typed), len(want)))
            sel = 1
            while True:
                self.display.show(screens.check_result(
                    self.w, self.h, typed, wrong, label, i, pages),
                    sensitive=True)
                key = self.buttons.read()
                if wrong and key in ("l", "r"):
                    sel = 1 - sel
                elif key in ("a", "p"):
                    if not wrong:
                        return typed
                    if sel == 0:
                        return None
                    caret = min(wrong)      # FIX: land on the first one
                    break
                elif key in ("b", "c"):
                    if not wrong:
                        return typed
                    break

    def _check_entry(self, label, i, pages, want_len, typed,  # noqa: C901 - one keypad state machine, like _text_entry
                     caret):
        """The typing surface for a check. Returns (text, caret), or
        (None, 0) if the user left.

        Three focuses, cycled with C: the character grid, the typed text,
        and the action bar. The text focus is what Ben asked for: L and R
        walk the caret through what you have typed, so a wrong character
        forty along is fixed where it is, instead of deleting the forty
        after it. A writes the highlighted character AT the caret, which
        is an overwrite when the caret sits on an existing character.
        """
        charset = "xprv"
        grid = screens.charset_pages(charset)
        cur, page, focus, sel = 0, 0, "grid", 1
        while True:
            title = (f"{label}  ·  TYPE  {i + 1}/{pages}" if pages > 1
                     else f"{label}  ·  TYPE  IT  BACK")
            self.display.show(screens.text_entry(
                self.w, self.h, title, typed, cur, charset, page,
                actions_sel=sel, caret=caret,
                actions=("ABORT", "CHECK"),
                hint=screens.CHECK_HINTS[focus] % (len(typed), want_len)),
                sensitive=True)
            key = self.buttons.read()
            if focus == "bar":
                if key in ("l", "r"):
                    sel = 1 - sel
                elif key in ("a", "p"):
                    return (typed, caret) if sel == 1 else (None, 0)
                elif key in ("b", "c"):
                    focus = "grid"
            elif focus == "text":
                if key == "l":
                    caret = max(0, caret - 1)
                elif key == "r":
                    caret = min(len(typed), caret + 1)
                elif key == "b" and caret < len(typed):
                    typed = typed[:caret] + typed[caret + 1:]
                elif key == "a":
                    focus = "grid"      # back to the grid to overwrite it
                elif key == "p":
                    return typed, caret  # centre press finishes, everywhere
                elif key == "c":
                    focus = "bar"
            elif key in ("u", "d", "l", "r"):
                page, cur = _grid_move(key, grid, page, cur)
            elif key == "a":
                typed = typed[:caret] + grid[page][cur] + typed[caret + 1:]
                caret = min(len(typed), caret + 1)
            elif key == "b":
                if not typed:
                    return None, 0
                if caret > 0:
                    typed = typed[:caret - 1] + typed[caret:]
                    caret -= 1
            elif key == "p":
                return typed, caret
            elif key == "c":
                focus = "text"


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
        choice = 0
        while True:
            if not can_stick:
                outcome = self._load_by_qr()
            elif not can_qr:
                outcome = self._load_by_stick()
            else:
                while True:
                    self.display.show(
                        screens.channel_menu(self.w, self.h, choice))
                    key = self.buttons.read()
                    if key in ("u", "d"):
                        choice = 1 - choice
                    elif key in ("a", "p"):
                        break
                    elif key in ("b", "c"):
                        return TO_HOME
                outcome = (self._load_by_stick() if choice == 1
                           else self._load_by_qr())
            if outcome == BACK_TO_CHANNELS:
                # Only one channel to offer, so back means all the way out.
                if not (can_qr and can_stick):
                    return TO_HOME
                continue
            return outcome

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
                return BACK_TO_CHANNELS
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
            # Not marked sensitive, deliberately. A PSBT is a transaction,
            # not a key, and the dev PNGs of this viewfinder are how a
            # camera problem gets debugged. The residual risk is a
            # developer pointing THIS scanner at a key QR by mistake, on a
            # dev machine, which is a smaller thing than losing the only
            # view into the scan loop (audit A2, 2026-09-06).
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
                    return BACK_TO_CHANNELS
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
        # A quorum costs more per input, so it gets its own ceiling
        # rather than one conservative number for everything, which would
        # refuse ordinary batches this board is measured signing (Ben,
        # 2026-09-11). `timelocks` joins `quorum` because a miniscript
        # policy carries a witness script per input the same way; its
        # cost is not measured, and refusing early is the safe side.
        heavy = bool(info["quorum"] or info["timelocks"])
        cap = MAX_SIGNABLE_MULTISIG_INPUTS if heavy else MAX_SIGNABLE_INPUTS
        if info["input_count"] > cap:
            # Refusing beats dying half way through. Measured on the
            # board, 250 batch-funded inputs leave 72MB where 100MB is
            # required, and the kernel kills whichever process asks for
            # the next page. That can be bitcoind holding the only copy
            # of a signature.
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail=f"{info['input_count']} inputs; this board signs "
                       f"up to {cap}"))
            self.buttons.read()
            return TO_HOME
        if info["fee_btc"] is None:
            # Missing input data: refuse loudly instead of crashing (a fee
            # the device cannot show is a transaction it must not sign).
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="PSBT lacks input data; fee unknown; refused"))
            self.buttons.read()
            return TO_HOME
        # M1 decision 2 and M3 decisions 2 and 3: the review screen says
        # which wallet this signature is for, and who else is in it.
        ours = next((k.xfp for k in self.keys if k.name == wallet), None)
        outs = [(o["address"], o["amount_btc"]) for o in info["outputs"]]
        pages = max(1, (len(outs) + 1) // 2)
        page, seen, refused, sel = 0, {0}, False, 1
        while True:
            self.display.show(screens.review(
                self.w, self.h, outs, info["fee_btc"],
                input_total_btc=info["input_total_btc"],
                page=page, unseen_pages=refused, actions_sel=sel,
                quorum=info["quorum"], cosigners=info["cosigners"],
                ours=ours, timelocks=info["timelocks"],
                spend_lock=info["spend_lock"]))
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
                return self._sign_and_deliver(psbt, source, wallet)
            elif key == "b":
                return TO_HOME       # back to home, key still loaded (D7)
            elif key == "c" or (key in ("a", "p") and sel == 0):
                self.display.show(screens.result(
                    self.w, self.h, ok=False, detail="rejected by user"))
                self.buttons.read()
                return TO_HOME

    def _sign_and_deliver(self, psbt, source, wallet):
        stop = self._busy("signing in Core…")
        try:
            # The fingerprint lets Core derive where the PSBT says when
            # the loaded policies sign nothing, which is every quorum and
            # every blinded path (M1 decision 2).
            signed = signer.sign_psbt(
                self.rpc, psbt, wallet=wallet,
                xfp=next((k.xfp for k in self.keys if k.name == wallet),
                         None))
        finally:
            stop()
        if not signed["added"]:
            # M3 decision 1: an INCOMPLETE PSBT is now the correct and
            # final outcome for a cosigner, so `complete` stopped being
            # the test. What is still a failure is signing NOTHING, and
            # that is what this refuses. The review screen has already
            # said "2 of 3", so a person reaching the SIGNED screen has
            # been told the transaction needs others.
            self.display.show(screens.result(
                self.w, self.h, ok=False,
                detail="this key signed nothing on that PSBT"))
            self.buttons.read()
            return TO_HOME
        detail = None
        if source is not None:
            try:
                out = filechannel.write_signed(source, signed["psbt"])
                detail = f"{out.name} written"
            except (filechannel.FileChannelError, OSError) as exc:
                # THE PSBT IS ALREADY SIGNED. Letting this unwind throws
                # the signature away and the user has to scan and approve
                # the whole transaction again, which is the one thing this
                # screen exists to avoid. The QR path below has said so
                # since it was written; the file path did not, and audit
                # A3 then made write_signed refuse a short write, which
                # gave a full stick a brand new way to lose a signature
                # (found reading main.py, 2026-09-07).
                #
                # So fall through to the screen. It cannot be full, it
                # cannot be unplugged, and it cannot be mounted read-only.
                # "file channel" is CONTEXT.md's word for stick and card
                # together, which is exactly what can have failed here.
                # "file" was not a word this codebase defines.
                self._hold(f"file channel failed: {str(exc)[:34]}")
        if detail is None:
            frames = qrchannel.psbt_to_frames(signed["psbt"])
            try:
                self._show_qr_loop(frames)
            except qrchannel.QrChannelError as exc:
                # Both channels gone. Nothing left but to say so.
                # Through _hold, not screens.result directly: _hold is
                # where a message gets redacted, and this was the one
                # exception on its way to the panel that went around it
                # (two-axis review, 2026-09-08).
                self._hold(f"signed, but not shown: {exc}")
                return TO_HOME
            detail = f"shown as {len(frames)} QR frames"
        return self._state_signed(detail, signed["complete"])

    def _show_qr_loop(self, frames, delay=0.15):
        """Play the BC-UR animation as a steady, repeating loop.

        A fountain animation must cycle continuously at a readable rate for
        Sparrow or a phone to catch every part; one unpaced pass is not
        readable for any multi-frame PSBT. Any key stops. A single frame is
        a static QR, so it is shown once and waits for a key.
        """
        # Sized against the CARD's budget, not the panel's, because the
        # frames now sit on the same gold-edged card the export uses
        # (screens.qr_frame). The budget is the short side less the pad
        # and the stroke on both edges, and it happens to cost nothing:
        # an outbound frame is 212px either way on both panels.
        budget = min(self.w, self.h) - 2 * (screens.QR_CARD_PAD
                                            + screens.STROKE)
        images = [screens.qr_frame(self.w, self.h, img)
                  for img in qrchannel.frames_to_images(
                      frames, panel=(budget, budget))]
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

    def _state_signed(self, detail, complete=True):
        """Result screen with SIGN ANOTHER / POWER OFF (Ben, 2026-09-01).

        `complete` separates a finished transaction from ONE SHARE of
        one. Both are signed, and only one of them can move the money,
        so the screen that used to say SIGNED for both now says which
        (map M6, Ben's call 2026-09-10). CONTEXT.md calls the second a
        share.
        """
        label = "SIGNED" if complete else "SHARE"
        note = ("ready to send" if complete
                else "needs another signature")
        sel = 0
        while True:
            self.display.show(screens.result(
                self.w, self.h, ok=True, detail=detail, actions_sel=sel,
                label=label, note=note))
            key = self.buttons.read()
            if key in ("l", "r"):
                sel = 1 - sel
            elif key in ("a", "p"):
                return SIGN_AGAIN if sel == 0 else POWER_OFF
            elif key == "b":
                # BACK was dead here. Everywhere else on this device it
                # leaves the screen, and D7 already settled that leaving
                # a transaction goes home with the key still loaded. A
                # button that does nothing is the defect Ben reported off
                # the board on 2026-09-05, in a different menu.
                return TO_HOME
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
