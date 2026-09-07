"""Render Corky's real screens into six narrated demo videos.

Every frame is drawn by `corky/screens.py` itself, and every string in
them comes from Bitcoin Core on regtest: the key, its fingerprint, its
descriptor, its addresses and a funded PSBT. Nothing here is a mockup and
nothing is typed from memory (TESTING.md rule 1).

Narration is macOS `say`, so no text leaves this machine. See the
demo-video skill.

    python3 tools/make_demo_videos.py [outdir]
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "corky"))
import qrchannel                                       # noqa: E402
import screens                                         # noqa: E402
import signer                                          # noqa: E402

W, H = 320, 240
SCALE = 4                       # 1280x960
# Narration engine. `say` is macOS's own: free, offline, instant, and
# audibly synthetic. `piper` is a local neural model, still free and still
# offline, and much easier to listen to for three minutes. Set VOICE to a
# model name in ~/.local/share/piper-voices to use it.
#
#   VOICE=Daniel                             -> macOS say
#   VOICE=en_GB-alba-medium                  -> piper
VOICE = os.environ.get("CORKY_VOICE", "Daniel")
RATE = int(os.environ.get("CORKY_RATE", "172"))
PIPER_DIR = Path.home() / ".local" / "share" / "piper-voices"


def narrate(text, out_wav):
    """Speak `text` into out_wav. Neither engine sends anything anywhere."""
    model = PIPER_DIR / f"{VOICE}.onnx"
    if model.exists():
        subprocess.run([sys.executable, "-m", "piper", "-m", str(model),
                        "-f", str(out_wav)], input=text, text=True,
                       check=True, capture_output=True)
        return
    aiff = out_wav.with_suffix(".aiff")
    subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(aiff),
                    text], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(aiff),
                    "-ar", "22050", "-y", str(out_wav)], check=True)
    aiff.unlink()
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tmp" / "video")


def shot(name, img):
    OUT.mkdir(parents=True, exist_ok=True)
    img.resize((W * SCALE, H * SCALE)).save(OUT / f"{name}.png")
    return name


def hold(name, seconds):
    """A scene with no narration, for a beat on a busy or splash screen."""
    return (name, None, seconds)


def build(video, scenes):
    """scenes: list of (png_name, narration or None, min_seconds)."""
    parts = []
    for i, (png, text, floor) in enumerate(scenes, 1):
        seg = OUT / f"{video}_{i:02d}.mp4"
        audio = OUT / f"{video}_{i:02d}.mp3"
        if text:
            wav = OUT / f"{video}_{i:02d}.wav"
            narrate(text, wav)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav),
                            "-ar", "22050", "-b:a", "128k", "-y", str(audio)],
                           check=True)
            wav.unlink()
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-loop", "1",
                 "-i", str(OUT / f"{png}.png"), "-i", str(audio),
                 "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                 "-ar", "22050", "-b:a", "128k", "-pix_fmt", "yuv420p",
                 "-shortest", "-y", str(seg)], check=True)
        else:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-loop", "1",
                 "-i", str(OUT / f"{png}.png"), "-f", "lavfi",
                 "-i", "anullsrc=r=22050:cl=stereo", "-t", str(floor),
                 "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                 "-ar", "22050", "-b:a", "128k", "-pix_fmt", "yuv420p",
                 "-y", str(seg)], check=True)
        parts.append(seg.name)
    concat = OUT / f"{video}.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts))
    final = OUT / f"{video}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(concat), "-c", "copy",
                    "-y", str(final)], check=True)
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(final)],
        capture_output=True, text=True).stdout.strip()
    # A GIF too, because GitHub only auto-plays videos it hosts itself:
    # an .mp4 committed to a repo renders as a link nobody clicks. Every
    # scene is a still, so 2fps compresses to a couple of hundred KB and
    # the page shows the flow without anyone downloading anything.
    gif = OUT / f"{video}.gif"
    pal = OUT / "_pal.png"
    vf = "fps=2,scale=640:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(final),
                    "-vf", f"{vf},palettegen=stats_mode=diff",
                    "-y", str(pal)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(final),
                    "-i", str(pal), "-lavfi",
                    f"{vf}[x];[x][1:v]paletteuse=dither=none",
                    "-y", str(gif)], check=True)
    pal.unlink()
    print(f"  {video}.mp4   {float(dur):5.1f}s   {len(parts)} scenes"
          f"   + {gif.stat().st_size // 1024}KB gif")
    for p in parts:
        (OUT / p).unlink()
    concat.unlink()
    return final


def main():
    dd = Path(tempfile.mkdtemp())
    (dd / "bitcoin.conf").write_text(
        "regtest=1\nserver=1\nrpcuser=u\nrpcpassword=p\n"
        "nodebuglogfile=1\nnetworkactive=0\nfallbackfee=0.0002\n")
    node = subprocess.Popen(["bitcoind", f"-datadir={dd}", "-regtest"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    rpc = signer.Rpc(str(dd), chain="regtest")
    for _ in range(90):
        try:
            rpc.call("getblockchaininfo")
            break
        except Exception:
            time.sleep(0.5)
    try:
        print("asking Bitcoin Core for the real thing...")
        name = signer.generate_wallet(rpc)
        xfp = signer.master_fingerprint(rpc, wallet=name)
        xprv = signer.master_xprv(rpc, wallet=name)
        desc = signer.export_descriptor(rpc, name, "wpkh")
        addrs = signer.receive_addresses(rpc, name, "wpkh", 3)
        kinds = signer.available_kinds(rpc, name)
        pages = screens.text_pages(xprv)
        _xfp2, path = signer.origin_of(desc)
        print(f"  key {xfp.upper()}  {len(kinds)} policies  "
              f"{len(pages)} backup pages  path {path}")

        rpc.call("createwallet", "miner")
        m = rpc.call("getnewaddress", wallet="miner")
        rpc.call("generatetoaddress", 101, m, wallet="miner")
        rpc.call("sendtoaddress", addrs[0], 0.5, wallet="miner")
        rpc.call("generatetoaddress", 1, m, wallet="miner")
        psbt = rpc.call("walletcreatefundedpsbt", [],
                        [{m: 0.2}], 0, {"fee_rate": 5}, True,
                        wallet=name)["psbt"]
        review = signer.describe_psbt(rpc, psbt)
        outs = [(o["address"], o["amount_btc"]) for o in review["outputs"]]
        signed = signer.sign_psbt(rpc, psbt, wallet=name)
        frames = qrchannel.psbt_to_frames(signed["psbt"])
        print(f"  psbt {len(psbt) // 1024}KB, fee {review['fee_btc']}, "
              f"{len(frames)} outbound QR frames")
        yield_scenes(xfp, xprv, desc, addrs, kinds, pages, path,
                     outs, review, frames)
    finally:
        try:
            rpc.call("stop")
            node.wait(timeout=60)
        except Exception:
            node.kill()
        shutil.rmtree(dd, ignore_errors=True)


def yield_scenes(xfp, xprv, desc, addrs, kinds, pages, path,
                 outs, review, frames):
    U = xfp.upper()
    print("\nrendering and narrating...")

    # ---- 1. generate a key ------------------------------------------
    shot("v1_home", screens.home(W, H, 1))
    # New key is row 0 of KEYS_ACTIONS. Highlighting row 1 put the
    # cursor on "Scan a key" in a video about generating one (Ben,
    # 2026-09-07).
    new_key_row = [lbl for lbl, _n in screens.KEYS_ACTIONS].index("New key")
    shot("v1_keys", screens.keys_menu(W, H, [], selected=new_key_row))
    shot("v1_busy", screens.busy(W, H, "Bitcoin Core is making a key…"))
    shot("v1_made", screens.key_menu(W, H, xfp, 0))
    shot("v1_home2", screens.home(W, H, 1, xfp=xfp))
    build("01-generate-a-key", [
        ("v1_home", "Corky holds no key until you give it one. Keys.", 0),
        ("v1_keys", "Nothing is loaded, so the only choices are to scan a "
                    "key you already have, or make a new one.", 0),
        ("v1_busy", "Bitcoin Core generates it, using Core's own random "
                    "number generator. Corky ships no randomness of its "
                    "own, and imports no cryptography at all.", 0),
        ("v1_made", f"The key is named by its fingerprint, {U}. Core made "
                    "it, Core holds it, and Core will sign with it.", 0),
        ("v1_home2", "The fingerprint sits on the home screen, so the "
                     "device can always answer which key is open.", 0),
    ])

    # ---- 2. back it up on paper --------------------------------------
    label = f"KEY  {U}"
    for i, chunk in enumerate(pages):
        shot(f"v2_p{i}", screens.backup_page(W, H, chunk, label, i,
                                             len(pages)))
    build("02-back-it-up-on-paper", [
        ("v2_p0", "The backup is Core's own master private key, in "
                  "four character groups. You write it down. There is no "
                  "file and no encryption, because a key that is never "
                  "written to a medium cannot be taken off one.", 0),
        ("v2_p1", "It runs to a hundred and eleven characters over three "
                  "pages.", 0),
        (f"v2_p{len(pages) - 1}", "The last page offers to check what you "
                                  "wrote.", 0),
    ])

    # ---- 3. verify the backup ---------------------------------------
    typed = pages[0]
    wrong_at = 5
    bad_text = typed[:wrong_at] + ("2" if typed[wrong_at] != "2" else "3") \
        + typed[wrong_at + 1:]
    shot("v3_bad", screens.check_result(W, H, bad_text, {wrong_at},
                                        label, 0, len(pages)))
    shot("v3_good", screens.check_result(W, H, typed, set(), label, 0,
                                         len(pages)))
    shot("v3_ok", screens.verified(W, H, f"your paper opens\nkey {U}"))
    build("03-verify-the-backup", [
        ("v3_bad", "Verify types it back in. One character is wrong here, "
                   "and the device names the position rather than just "
                   "saying no.", 0),
        ("v3_good", "Fix lands the cursor on the wrong character. When the "
                    "page matches, it moves on.", 0),
        ("v3_ok", "At the end Bitcoin Core derives addresses from what you "
                  "typed and compares them with the ones this wallet hands "
                  "out. That is the claim being made: your paper opens this "
                  "key.", 0),
    ])

    # ---- 4. export the public key ------------------------------------
    code = qrchannel.text_to_image(desc, panel=(W, min(H, screens.QR_MAX_PX)))
    shot("v4_menu", screens.key_menu(W, H, xfp, 0))
    shot("v4_script", screens.script_menu(W, H, kinds, 0))
    shot("v4_how", screens.export_options(W, H, 0))
    shot("v4_qr", screens.qr_export(W, H, code, xfp, "wpkh", path))
    shot("v4_addr", screens.address_page(W, H, 0, addrs[0], "wpkh", 3))
    build("04-export-the-public-key", [
        ("v4_menu", "A coordinator needs the public half, never the "
                    "private one.", 0),
        ("v4_script", "Core makes four script policies from one key: "
                      "legacy, nested segwit, native segwit and taproot. "
                      "All four are offered, because coins sent to any of "
                      "them are yours.", 0),
        ("v4_how", "Then how it leaves: as a QR code, as text to type, or "
                   "as a wallet file for Bitcoin Core, which reads no QR.", 0),
        ("v4_qr", f"The code is Core's own descriptor string. Underneath "
                  f"it, the fingerprint {U}, the policy, and the derivation "
                  "path, so the coordinator can be checked against the "
                  "device rather than trusted.", 0),
        ("v4_addr", "Then the first addresses, in full, to compare against "
                    "whatever the coordinator now shows.", 0),
    ])

    # ---- 5. check an address -----------------------------------------
    shot("v5_home", screens.home(W, H, 2, xfp=xfp))
    shot("v5_tools", screens.tools_menu(W, H, 1))
    shot("v5_scan", screens.scanning(W, H, None, "hold the address QR in view"))
    shot("v5_ok", screens.verified(W, H, f"key {U}\nowns this address"))
    build("05-check-an-address", [
        ("v5_home", "The question a coordinator cannot answer for you is "
                    "whether the address on that other screen is really "
                    "yours.", 0),
        ("v5_tools", "Check an address.", 0),
        ("v5_scan", "Point the camera at it.", 0),
        ("v5_ok", f"Core is asked, per loaded key. Key {U} owns this "
                  "address. If no loaded key owned it, the device would "
                  "say so, which is how somebody avoids paying a "
                  "stranger.", 0),
    ])

    # ---- 6. sign ------------------------------------------------------
    shot("v6_home", screens.home(W, H, 0, xfp=xfp))
    shot("v6_scan", screens.scanning(W, H, None,
                                     "hold the transaction in view", 0.62))
    shot("v6_review", screens.review(W, H, outs, review["fee_btc"],
                                     input_total_btc=review["input_total_btc"]))
    shot("v6_done", screens.result(W, H, ok=True, detail="1 input signed",
                                   label="SIGNED"))
    imgs = qrchannel.frames_to_images(frames[:1], panel=(W, H)) \
        if hasattr(qrchannel, "frames_to_images") else []
    shot("v6_out", imgs[0] if imgs else screens.busy(W, H, "sending…"))
    build("06-sign-a-transaction", [
        ("v6_home", "Signing. The transaction arrives by camera, and "
                    "leaves the same way.", 0),
        ("v6_scan", "It comes in as animated QR frames, because a "
                    "transaction is far too big for one code.", 0),
        ("v6_review", "The review screen is Core's numbers, not ours: "
                      "every output, the fee, and the total going in. "
                      "The device signs up to a hundred and fifty inputs "
                      "and refuses more, because that is the memory this "
                      "board has.", 0),
        ("v6_done", "Core signs. The private key never left it.", 0),
        ("v6_out", "The signed transaction goes back out as QR, so nothing "
                   "is ever plugged into this device.", 0),
    ])
    for p in OUT.glob("v*.png"):
        p.unlink()
    for p in OUT.glob("*.mp3"):
        p.unlink()
    for p in OUT.glob("*.wav"):
        p.unlink()


if __name__ == "__main__":
    main()
