"""Camera bring-up with a viewfinder. RUN ON THE BOARD.

    sudo python3 tests/hw_camera.py [--seconds 90]

Paints what the camera sees onto the LCD, so the operator can aim, and
reports every QR it decodes. Without this you are pointing a lens at a
target with no feedback, which is exactly as useless as it sounds.

Uses the shipping CameraQrSource, so what passes here is evidence about
the code the device runs, not about a copy of it.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))

from PIL import Image, ImageDraw          # noqa: E402
import hal                                 # noqa: E402
import qrchannel                           # noqa: E402
import main as corky_main                  # noqa: E402


def viewfinder(display, frame, line1, line2, rotate=0, fill=False):
    """The greyscale camera frame, scaled to the panel, with two captions.

    `rotate` turns the picture for the operator's eyes only. The camera is
    mounted at an angle to the panel on this build, so the raw frame arrives
    sideways. Nothing decodes this image: zbar reads a QR at any orientation,
    so rotating before decode would buy nothing and cost a copy per frame.
    """
    img = Image.fromarray(frame, mode="L").convert("RGB")
    if rotate:
        img = img.rotate(rotate, expand=True)
    # The camera is mounted 90 degrees to the panel, so an upright picture is
    # portrait and the panel is landscape. That cannot both fill the screen
    # and keep the whole field of view; the mount decides it, not the code.
    if fill:
        # Fill the panel, losing the edges of the view.
        scale = max(display.width / img.width, display.height / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.NEAREST)
        left = (img.width - display.width) // 2
        top = (img.height - display.height) // 2
        img = img.crop((left, top, left + display.width, top + display.height))
    else:
        # Keep the whole field of view, losing screen width to black bars.
        img.thumbnail((display.width, display.height), Image.NEAREST)
        canvas = Image.new("RGB", (display.width, display.height), "#000000")
        canvas.paste(img, ((display.width - img.width) // 2,
                           (display.height - img.height) // 2))
        img = canvas
    d = ImageDraw.Draw(img)
    for y, text, fill in ((4, line1, "#7CFF7C"), (display.height - 18, line2, "#FFD37C")):
        d.rectangle([0, y - 2, display.width, y + 16], fill="#000000")
        d.text((6, y), text, fill=fill)
    return img


# Optional: the exact frame we are pointing the camera at, so the rig can
# say "identical" rather than "looks about right".
_exp = Path("/tmp/expected_frame.txt")
EXPECTED = _exp.read_text().strip() if _exp.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--rotate", type=int, default=90,
                    help="degrees counter-clockwise, viewfinder only")
    # Ben's call, 2026-09-04: fill the panel. The camera is mounted 90
    # degrees to it, so an upright picture is portrait on a landscape
    # screen; that gives up either screen width or field of view, and he
    # chose to keep the screen. --no-fill letterboxes instead.
    ap.add_argument("--fill", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="fill the panel by cropping (default), or letterbox")
    parsed = ap.parse_args()
    seconds, rotate, fill = parsed.seconds, parsed.rotate, parsed.fill

    display = hal.DeviceDisplay()
    src = corky_main.CameraQrSource()
    assembler = qrchannel.FrameAssembler()

    print(f"panel {display.width}x{display.height}, camera {src.SIZE[0]}x{src.SIZE[1]}")
    print(f"aim at the QR; {seconds:.0f}s\n")

    t0 = time.time()
    frames = decodes = 0
    seen = set()
    done = False
    for frame in src.images():
        frames += 1
        found = qrchannel.decode_image(frame)
        status = "aim at the QR"
        for payload in found:
            decodes += 1
            if payload not in seen:
                seen.add(payload)
                mark = ""
                if EXPECTED is not None:
                    mark = ("  == SPARROW'S BYTES EXACTLY" if payload == EXPECTED
                            else "  != expected frame")
                print(f"[{time.time()-t0:5.1f}s] {len(payload)} chars  "
                      f"{payload[:52]}{mark}")
            try:
                if assembler.feed(payload):
                    done = True
            except qrchannel.QrChannelError as exc:
                status = f"rejected: {exc}"
        if seen:
            status = f"got {len(seen)} distinct, {decodes} reads"
        fps = frames / max(time.time() - t0, 0.001)
        display.show(viewfinder(
            display, frame, status,
            f"{fps:4.1f} fps  rot {rotate} {'fill' if fill else 'fit'}",
            rotate, fill))
        if done:
            print("\nSEQUENCE COMPLETE")
            break
        if time.time() - t0 > seconds:
            break

    dt = time.time() - t0
    print(f"\n{frames} frames in {dt:.1f}s = {frames/dt:.1f} fps")
    print(f"{decodes} reads, {len(seen)} distinct payloads")
    if src.unavailable:
        print("camera unavailable:", src.unavailable)
    return 0 if seen else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\naborted")
        sys.exit(2)
