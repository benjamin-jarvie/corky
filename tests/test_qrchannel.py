"""QR channel roundtrip tests, no camera needed.
Run: python3 tests/test_qrchannel.py"""

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "corky"))
import qrchannel  # noqa: E402
import base64

failures = []

# 1. Small PSBT -> single static frame
small = base64.b64encode(b"psbt\xff" + os.urandom(200)).decode()
frames = qrchannel.psbt_to_frames(small)
a = qrchannel.FrameAssembler()
done = a.feed(frames[0]) if len(frames) == 1 else None
print(f"ok   small psbt: {len(frames)} frame(s)")
if len(frames) == 1:
    assert done and a.psbt_b64 == small, "single-frame roundtrip mismatch"
    print("ok   static QR roundtrip exact")

# 2. Large PSBT -> multi-frame, delivered in order
big = base64.b64encode(b"psbt\xff" + os.urandom(20000)).decode()
frames = qrchannel.psbt_to_frames(big)
assert len(frames) > 10
a = qrchannel.FrameAssembler()
for f in frames:
    if a.feed(f):
        break
assert a.psbt_b64 == big, "multi-frame roundtrip mismatch"
print(f"ok   animated roundtrip exact ({len(frames)} frames)")

# 3. Lossy camera simulation: a live fountain stream where the camera
#    misses 40% of frames at random. Mixed parts beyond the first cycle
#    recover the gaps (fountain coding's whole job). This mirrors the real
#    device: the coordinator's QR loops forever; the camera catches what it
#    catches.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hw" / "vendor"))
from ur2.ur import UR
from ur2.ur_encoder import UREncoder
from ur2.cbor_lite import CBOREncoder
enc = CBOREncoder()
enc.encodeBytes(base64.b64decode(big))
stream = UREncoder(UR("crypto-psbt", enc.get_bytes()),
                   max_fragment_len=qrchannel.MAX_FRAGMENT_LEN)
a = qrchannel.FrameAssembler()
rng = random.Random(42)
shown = caught = 0
while shown < 5000:
    part = stream.next_part()
    shown += 1
    if rng.random() < 0.4:
        continue  # camera missed this frame
    caught += 1
    if a.feed(part):
        break
assert a.psbt_b64 == big, "lossy roundtrip mismatch"
print(f"ok   lossy stream roundtrip exact (caught {caught} of {shown} shown frames)")

# 4. Hostile input rejected
for bad, why in [("ur:crypto-seed/aaaa", "wrong type"),
                 ("x" * 4000, "oversized"),
                 ("ur:crypto-psbt/<script>", "bad charset")]:
    try:
        qrchannel.FrameAssembler().feed(bad)
        failures.append(f"accepted {why}")
        print(f"FAIL hostile input accepted: {why}")
    except qrchannel.QrChannelError:
        print(f"ok   hostile input rejected: {why}")

# 5. Frames render as images
imgs = qrchannel.frames_to_images(frames[:3])
assert len(imgs) == 3 and imgs[0].size[0] > 50
print(f"ok   frames render to PIL images ({imgs[0].size[0]}px)")

if failures:
    sys.exit(1)
print("\nQR CHANNEL PASS: static, animated, lossy-camera and hostile-input cases")
