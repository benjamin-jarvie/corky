"""Boot splash: paint the brand frame, then exit.

The dedicated entrypoint imports only hal and screens. The signing stack
(signer, codex32, the channels) stays out on purpose: the frame lands
seconds earlier on the single-core Pi, and a fault in a signing-side
module cannot dark the boot screen. corky-splash.service runs this
before corky-bitcoind.service; the session itself is corky/main.py.
"""

import argparse

import hal
import screens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--frames-dir", default="frames")
    args = ap.parse_args()
    display = (hal.DevDisplay(args.frames_dir) if args.dev
               else hal.DeviceDisplay())
    display.show(screens.splash(display.width, display.height))


if __name__ == "__main__":
    main()
