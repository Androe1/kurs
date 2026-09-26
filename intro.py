"""Androe Studio - 5 saniyelik logo intro videosunu üretir.

Kullanım:
    pip install -r requirements.txt
    python intro.py                                  # output/androe_studio_intro.mp4
    python intro.py --width 3840 --height 2160 -o output/androe_studio_intro_4k.mp4
    python intro.py --still 3.0                      # yalnızca 3. saniyedeki kareyi PNG kaydet
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import skia

from scene import DURATION, Scene
from sound import synthesize, write_wav


def save_png(rgb, path):
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
    skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType).save(str(path), skia.kPNG)


def encode(scene, wav, out, fps):
    """Kareleri doğrudan ffmpeg'e aktarır ve sesle birlikte MP4 (H.264 + AAC) yazar."""
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.width}x{scene.height}",
           "-r", str(fps), "-i", "-", "-i", str(wav),
           "-map", "0:v", "-map", "1:a", "-map_metadata", "-1",
           "-c:v", "libx264", "-preset", "slow", "-crf", "14",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = round(DURATION * fps)
    for i in range(frames):
        proc.stdin.write(scene.render(i / fps).tobytes())
        print(f"\rKare {i + 1}/{frames}", end="", flush=True)
    proc.stdin.close()
    print()
    if proc.wait() != 0:
        sys.exit("ffmpeg video kodlarken hata verdi.")


def main():
    parser = argparse.ArgumentParser(description="Androe Studio intro videosunu üretir.")
    parser.add_argument("-o", "--output", default="output/androe_studio_intro.mp4")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--still", type=float, metavar="SANIYE",
                        help="video yerine yalnızca bu andaki kareyi PNG olarak kaydet")
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene = Scene(args.width, args.height, args.fps)

    if args.still is not None:
        path = out.with_name(f"kare_{args.still:.2f}.png")
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
