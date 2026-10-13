"""Void Creations - logo intro videosunu üretir (referans videonun ilk 4 saniyesi).

Kullanım:
    pip install -r requirements.txt
    python void_creations.py                  # output/void_creations_intro.mp4
    python void_creations.py --still 1.3      # yalnızca 1.3. saniyedeki kareyi PNG kaydet
    python void_creations.py --dikey          # 9:16 (1080x1920): output/void_creations_intro_9x16.mp4
"""
import argparse
import tempfile
import time
from pathlib import Path

from intro import encode, save_png
from sound import write_wav
import void_scene
from void_scene import VoidScene
from void_sound import synthesize


def main():
    parser = argparse.ArgumentParser(description="Void Creations intro videosunu üretir.")
    parser.add_argument("-o", "--output")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--dikey", action="store_true", help="9:16 dikey video (1080x1920)")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--still", type=float, metavar="SANIYE",
                        help="video yerine yalnızca bu andaki kareyi PNG olarak kaydet")
    args = parser.parse_args()
    if args.dikey:
        void_scene.use_vertical()
    width = args.width or (1080 if args.dikey else 1920)
    height = args.height or (1920 if args.dikey else 1080)
    output = args.output or ("output/void_creations_intro_9x16.mp4" if args.dikey else "output/void_creations_intro.mp4")

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene = VoidScene(width, height, args.fps)

    if args.still is not None:
        path = out.with_name(f"void_kare_{args.still:.2f}.png")
        save_png(scene.render(args.still), path)
        print(f"Kaydedildi: {path}")
        return

    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "ses.wav"
        write_wav(wav, synthesize(scene.events()))
        encode(scene, wav, out, args.fps)
    print(f"Hazır: {out}  ({time.time() - start:.0f} sn)")


if __name__ == "__main__":
    main()
