"""ZQV - 6 saniyelik karanlık yazı animasyonunu üretir.

Kullanım:
    pip install -r requirements.txt
    python zqv.py                  # output/zqv_intro.mp4
    python zqv.py --still 3.0      # yalnızca 3. saniyedeki kareyi PNG kaydet
"""
import argparse
import tempfile
import time
from pathlib import Path

from intro import encode, save_png
from sound import write_wav
from zqv_scene import ZQVScene
from zqv_sound import synthesize


def main():
    parser = argparse.ArgumentParser(description="ZQV karanlık animasyon videosunu üretir.")
    parser.add_argument("-o", "--output", default="output/zqv_intro.mp4")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--still", type=float, metavar="SANIYE",
                        help="video yerine yalnızca bu andaki kareyi PNG olarak kaydet")
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene = ZQVScene(args.width, args.height, args.fps)

    if args.still is not None:
        path = out.with_name(f"zqv_kare_{args.still:.2f}.png")
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
