"""QUEEN (LiSA) fan yapımı lyric video - videoyu üretir (1 dakika, 1920x1080, 60 fps).

Şarkı ve sözler telifli olduğu için repoda yoktur; kullanıcı kendisi sağlar:
    input/queen.mp3          şarkı (tam sürüm; ilk 61 saniyesi kullanılır)
    input/queen_sozler.txt   0:00-1:00 sözleri: her satır "kanji / parçalar | romaji / parçalar"

Kullanım:
    python queen.py                      # output/queen_lyric_video.mp4 (4 çekirdekle paralel)
    python queen.py --still 14.2         # yalnızca o andaki kareyi PNG kaydet
    python queen.py --preview            # hızlı önizleme: 960x540, 30 fps
    python queen.py --sheet 0 61 24      # 24 karelik kontak baskı (kontrol için)
    python queen.py --rebake             # dansçı koreografisini/fiziğini yeniden hesapla

Dansçıların koreografisi ve saç/etek fiziği bir kez hesaplanır (renders/queen_bake.npz,
~1 dakika); queen_choreo.py, queen_dancers.py ya da queen_timing.py değişince kendiliğinden yenilenir.
"""
import os
import argparse
import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

import wave

import imageio_ffmpeg
import numpy as np
import skia

from queen_choreo import save_bake
from queen_scene import QueenScene
from queen_timing import AUDIO_FADE, DURATION, FINAL_HIT
from sound import SR, Mixer, convolve, impact, reverb_ir, write_wav

ROOT = Path(__file__).resolve().parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def load_lyrics(path):
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        kanji, romaji = raw.split("|")
        lines.append(([p.strip() for p in kanji.split(" / ")], [p.strip() for p in romaji.split(" / ")]))
    return lines


def save_png(rgb, path):
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
    skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType).save(str(path), skia.kPNG)


BAKE = ROOT / "renders" / "queen_bake.npz"


def ensure_bake(force=False):
    """Dansçı hareketlerini (iskelet + saç + etek) hesaplayıp önbelleğe yazar."""
    deps = [ROOT / n for n in ("queen_choreo.py", "queen_dancers.py", "queen_timing.py")]
    if force or not BAKE.exists() or BAKE.stat().st_mtime < max(d.stat().st_mtime for d in deps):
        BAKE.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        print("Dansçı koreografisi ve fiziği hesaplanıyor...", flush=True)
        save_bake(str(BAKE))
        print(f"Hazır ({time.time() - start:.0f} sn)")
    return str(BAKE)


def _render_chunk(args):
    """Bir çalışan: kendi kare aralığını render edip ayrı bir video parçası yazar."""
    lyrics, width, height, fps, f0, f1, out, bake = args
    os.environ.setdefault("LP_NUM_THREADS", "1")          # llvmpipe: çalışan başına tek iş parçacığı
    scene = QueenScene(lyrics, width, height, fps, bake_path=bake)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(f0, f1):
        proc.stdin.write(scene.render(i / fps).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg parça kodlarken hata verdi")
    return out


def cut_audio(song, wav):
    """Şarkının ilk DURATION saniyesi; son uzun notadan sonra kısılır ve final patlaması
    (sound.py'deki impact: derin vuruş, çatırtı, kıvılcımlar + yankı) üstüne eklenir."""
    a, b = AUDIO_FADE
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(song), "-t", f"{DURATION}",
           "-af", f"afade=t=out:st={a}:d={b - a},apad=whole_dur={DURATION}", "-ar", str(SR), "-ac", "2",
           "-c:a", "pcm_s16le", str(wav)]
    subprocess.run(cmd, check=True)
    with wave.open(str(wav), "rb") as w:
        music = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32768.0
    rng = np.random.default_rng(7)
    mx = Mixer(DURATION)
    impact(mx, FINAL_HIT, rng)
    boom = mx.dry + 0.5 * convolve(mx.send, reverb_ir(rng, length=2.0, rt60=1.1))
    boom /= max(float(np.abs(boom).max()), 1e-9)
    n = min(len(music), len(boom))
    mix = music[:n] + 0.6 * boom[:n]
    over = np.abs(mix) > 0.9                              # yalnızca taşan tepeleri yumuşak kırp
    mix[over] = np.sign(mix[over]) * (0.9 + 0.1 * np.tanh((np.abs(mix[over]) - 0.9) / 0.1))
    write_wav(wav, mix)


def render_video(lyrics, song, out, width, height, fps, workers, bake):
    frames = round(DURATION * fps)
    # parçalar renders/ altında tutulur; birleştirme başarısız olursa render kaybolmaz
    tmp = ROOT / "renders" / "queen_parts"
    tmp.mkdir(parents=True, exist_ok=True)
    bounds = np.linspace(0, frames, workers * 3 + 1).round().astype(int)
    parts = [tmp / f"part{i:03d}.mp4" for i in range(len(bounds) - 1)]
    jobs = [(lyrics, width, height, fps, int(bounds[i]), int(bounds[i + 1]), parts[i], bake)
            for i in range(len(parts))]
    start = time.time()
    with mp.get_context("spawn").Pool(workers) as pool:
        for n, _ in enumerate(pool.imap(_render_chunk, jobs), 1):
            print(f"\rParça {n}/{len(jobs)}  ({time.time() - start:.0f} sn)", end="", flush=True)
    print()
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    wav = tmp / "ses.wav"
    cut_audio(song, wav)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
           "-map", "0:v", "-map", "1:a", "-map_metadata", "-1", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
           "-t", f"{DURATION}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    for p in parts + [lst, wav]:
        p.unlink(missing_ok=True)


def contact_sheet(lyrics, t0, t1, n, path, bake, cols=6):
    scene = QueenScene(lyrics, 480, 270, 60, bake_path=bake)
    times = np.linspace(t0, t1, n, endpoint=False)
    rows = int(np.ceil(n / cols))
    sheet = np.zeros((rows * 290, cols * 490, 3), np.uint8)
    for i, t in enumerate(times):
        r, c = divmod(i, cols)
        sheet[r * 290:r * 290 + 270, c * 490:c * 490 + 480] = scene.render(float(t))
    save_png(sheet, path)
    print("  ".join(f"{t:.2f}" for t in times))


def main():
    parser = argparse.ArgumentParser(description="QUEEN (LiSA) fan yapımı lyric video")
    parser.add_argument("-o", "--output", default="output/queen_lyric_video.mp4")
    parser.add_argument("--song", default=str(ROOT / "input/queen.mp3"))
    parser.add_argument("--lyrics", default=str(ROOT / "input/queen_sozler.txt"))
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    parser.add_argument("--preview", action="store_true", help="960x540, 30 fps hızlı önizleme")
    parser.add_argument("--still", type=float, metavar="SANIYE", help="yalnızca bu andaki kareyi PNG kaydet")
    parser.add_argument("--sheet", type=float, nargs=3, metavar=("BAS", "SON", "ADET"), help="kontak baskı")
    parser.add_argument("--rebake", action="store_true", help="dansçı hareketlerini yeniden hesapla")
    args = parser.parse_args()

    for p, what in ((args.lyrics, "söz dosyası"), (args.song, "şarkı")):
        if not Path(p).exists() and not (what == "şarkı" and (args.still is not None or args.sheet)):
            sys.exit(f"{what} bulunamadı: {p}")
    lyrics = load_lyrics(args.lyrics)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.preview:
        args.width, args.height, args.fps = 960, 540, 30
        if args.output == parser.get_default("output"):
            out = out.with_name("queen_onizleme.mp4")

    bake = ensure_bake(args.rebake)
    if args.still is not None:
        scene = QueenScene(lyrics, args.width, args.height, args.fps, bake_path=bake)
        path = out.with_name(f"queen_kare_{args.still:.2f}.png")
        save_png(scene.render(args.still), path)
        print(f"Kaydedildi: {path}")
        return
    if args.sheet:
        t0, t1, n = args.sheet
        path = out.with_name(f"queen_kontak_{t0:.0f}_{t1:.0f}.png")
        contact_sheet(lyrics, t0, t1, int(n), path, bake)
        print(f"Kaydedildi: {path}")
        return

    start = time.time()
    render_video(lyrics, args.song, out, args.width, args.height, args.fps, args.workers, bake)
    print(f"Hazır: {out}  ({time.time() - start:.0f} sn)")


if __name__ == "__main__":
    main()
