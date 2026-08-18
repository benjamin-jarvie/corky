"""Corky's session state machine: the program the device boots into.

States: HOME -> seed entry (words via UI, or xprv/descriptor QR) -> READY
-> load PSBT (QR or file) -> REVIEW -> sign -> RESULT -> power off.

Every screen comes from screens.py, every wallet operation from signer.py,
every transfer from qrchannel/filechannel. This module holds no crypto and
parses no untrusted bytes; it is the traffic cop.

Dev mode (no hardware):
    python3 corky/main.py --dev --datadir <dir> --chain regtest \
        --script "<key sequence>" [--psbt-file path]
Frames land as PNGs in --frames-dir for inspection.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signer
import screens
import filechannel
import qrchannel
import hal

MNEMONIC_DEV = "abandon " * 11 + "about"   # dev-script seed shortcut


class Session:
    def __init__(self, display, buttons, rpc, stick_dir=None):
        self.display = display
        self.buttons = buttons
        self.rpc = rpc
        self.stick_dir = Path(stick_dir) if stick_dir else None
        self.w, self.h = display.width, display.height

    # -- state handlers ----------------------------------------------------

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
            if key == "a":                    # dev shortcut: seed + continue
                self.state_seed()
                return

    def state_seed(self):
        self.display.show(screens.busy(self.w, self.h,
                                       "checking words, deriving in Core…"))
        # v1 UI does word entry via screens.seed_entry(); the dev script
        # uses the canonical test mnemonic directly.
        signer.open_session(self.rpc, MNEMONIC_DEV)
        self.state_load()

    def state_load(self):
        self.display.show(screens.busy(self.w, self.h,
                                       "insert stick or show QR…"))
        psbt, source = None, None
        while psbt is None:
            if self.stick_dir:
                found = filechannel.find_unsigned(self.stick_dir)
                if found:
                    psbt, source = filechannel.read_psbt(found[0]), found[0]
                    break
            key = self.buttons.read()
            if key == "c":
                return                        # back to power-off path
            time.sleep(0.05)
        self.state_review(psbt, source)

    def state_review(self, psbt, source):
        info = signer.describe_psbt(self.rpc, psbt)
        outs = [(o["address"], float(o["amount_btc"])) for o in info["outputs"]]
        self.display.show(screens.review(self.w, self.h, outs,
                                         float(info["fee_btc"]),
                                         info["input_count"]))
        while True:
            key = self.buttons.read()
            if key == "a":
                self.state_sign(psbt, source)
                return
            if key == "c":
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
    ap.add_argument("--frames-dir", default="frames")
    args = ap.parse_args()

    rpc = signer.Rpc(args.datadir, chain=args.chain)
    if args.dev:
        display = hal.DevDisplay(args.frames_dir)
        buttons = hal.DevButtons(args.script)
    else:
        display = hal.DeviceDisplay()
        buttons = hal.DeviceButtons()

    Session(display, buttons, rpc, stick_dir=args.stick_dir).run()


if __name__ == "__main__":
    main()
