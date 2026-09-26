"""Korku oyunu için 15 saniyelik teaser: kan damlası güle dönüşür, süzülür, kan birikintisinde
halka halka dalga açar; kamera karanlığa bakar, iki şeytani göz açılır, COMING SOON.

Kullanım:
    pip install -r requirements.txt
    python horror_teaser.py                    # output/horror_teaser.mp4
    python horror_teaser.py --still 8.6        # yalnızca bu andaki kareyi PNG kaydet
    python horror_teaser.py --storyboard       # anahtar anlardan film şeridi (PNG)

Linux sunucuda `libegl1` gerekir (ekran kartı gerekmez, Mesa llvmpipe ile çalışır).
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np

from horror_scene import Scene
from horror_sound import synthesize
from intro import save_png
from sound import write_wav

STORYBOARD = (0.9, 1.6, 2.5, 3.2, 3.8, 4.6, 5.4, 6.8, 8.3, 8.6, 9.2, 10.2, 11.36, 12.2, 13.8, 14.3)


def encode(scene, wav, out, fps, crf=18):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.width}x{scene.height}",
           "-r", str(fps), "-i", "-", "-i", str(wav),
           "-map", "0:v", "-map", "1:a", "-map_metadata", "-1",
           "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
           "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = round(scene.duration * fps)
    start = time.time()
    for i in range(frames):
        proc.stdin.write(scene.render(i / fps).tobytes())
        el = time.time() - start
        print(f"\rKare {i + 1}/{frames}  ({el / (i + 1):.2f} sn/kare, kalan ~{el / (i + 1) * (frames - i - 1) / 60:.0f} dk)",
              end="", flush=True)
    proc.stdin.close()
    print()
    if proc.wait() != 0:
        sys.exit("ffmpeg video kodlarken hata verdi.")


def storyboard(scene, path, times=STORYBOARD, cols=4):
    import skia
    tiles = []
    for t in times:
        img = scene.render(t)
        th = img[::4, ::4]
        surf = skia.Surface(th.shape[1], th.shape[0])
        c = surf.getCanvas()
        rgba = np.dstack([th, np.full(th.shape[:2], 255, np.uint8)])
        c.drawImage(skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType), 0, 0)
        c.drawString(f"{t:.2f} sn", 8, 22, skia.Font(None, 18), skia.Paint(Color=skia.ColorWHITE, AntiAlias=True))
        tiles.append(surf.makeImageSnapshot().toarray()[..., :3])
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    rows[-1] = np.hstack([rows[-1], np.zeros((rows[-1].shape[0], rows[0].shape[1] - rows[-1].shape[1], 3), np.uint8)])
    save_png(np.vstack(rows), path)


def main():
    parser = argparse.ArgumentParser(description="Korku oyunu teaser videosunu üretir.")
    parser.add_argument("-o", "--output", default="output/horror_teaser.mp4")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--still", type=float, metavar="SANIYE",
                        help="video yerine yalnızca bu andaki kareyi PNG olarak kaydet")
    parser.add_argument("--storyboard", action="store_true", help="anahtar anlardan film şeridi kaydet")
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene = Scene(args.width, args.height, args.fps)

    if args.still is not None:
        path = out.with_name(f"horror_kare_{args.still:.2f}.png")
        save_png(scene.render(args.still), path)
        print(f"Kaydedildi: {path}")
        return
    if args.storyboard:
        path = out.with_name("horror_storyboard.png")
        storyboard(scene, path)
        print(f"Kaydedildi: {path}")
        return

    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "ses.wav"
        write_wav(wav, synthesize(scene.events()))
        encode(scene, wav, out, args.fps)
    print(f"Hazır: {out}  ({(time.time() - start) / 60:.1f} dk)")


if __name__ == "__main__":
    main()
