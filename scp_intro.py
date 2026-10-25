"""SCP tarzı 7 saniyelik sinematiği birleştirir: Blender kareleri + sentez ses -> MP4.

Kullanım:
    python3.11 blender/render_chunks.py            # kareler: renders/scp/<plan>/####.png (+ meta.json)
    python scp_intro.py                            # output/scp_cinematic.mp4
    python scp_intro.py --preview                  # renders_preview/scp -> output/taslak/scp_onizleme.mp4

Kurgu: 1 sn siyah, siyahtan yumuşak açılış, üç plan (SECURE / CONTAIN / PROTECT) arasında
çapraz geçiş (her plan kesmenin iki yanına taşan kareleriyle render edilir), sonda kararma.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

from scp_sound import synthesize
from sound import write_wav

ROOT = Path(__file__).resolve().parent
SHOTS = ("secure", "contain", "protect")
FADE_IN, FADE_OUT = 0.3, 0.45


def clip_list(frames_dir, dt, path):
    """concat listesi: adımlı (--step 2) önizlemede numaralar ardışık olmadığı için."""
    pngs = sorted(p for p in frames_dir.glob("*.png") if p.stem.isdigit())
    if not pngs:
        sys.exit(f"Kare yok: {frames_dir}")
    path.write_text("".join(f"file '{p.as_posix()}'\nduration {dt}\n" for p in pngs)
                    + f"file '{pngs[-1].as_posix()}'\n")


def main():
    ap = argparse.ArgumentParser(description="SCP sinematiğini MP4 olarak birleştirir.")
    ap.add_argument("--preview", action="store_true", help="önizleme karelerini kullan")
    ap.add_argument("--frames", help="kare klasörü (varsayılan renders/scp)")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()
    frames = Path(a.frames) if a.frames else ROOT / ("renders_preview" if a.preview else "renders") / "scp"
    out = Path(a.output) if a.output else ROOT / "output" / (
        "taslak/scp_onizleme.mp4" if a.preview else "scp_cinematic.mp4")
    meta = json.loads((frames / "meta.json").read_text())
    fps, total, step = meta["fps"], meta["end"], meta.get("step", 1)
    spans = meta["spans"]
    t = {k: ((spans[k][0] - 1) / fps, spans[k][1] / fps) for k in SHOTS}  # final zaman çizgisinde
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "ses.wav"
        write_wav(wav, synthesize(meta))
        inputs = []
        for k in SHOTS:
            lst = Path(tmp) / f"{k}.txt"
            clip_list(frames / k, step / fps, lst)
            inputs += ["-f", "concat", "-safe", "0", "-i", str(lst)]
        norm = f"fps={fps},format=yuv444p,settb=AVTB"
        a0, a1 = t["secure"]
        b0, b1 = t["contain"]
        c0, _ = t["protect"]
        graph = (f"[0:v]{norm},tpad=start_duration={a0}:color=black,fade=t=in:st={a0}:d={FADE_IN}[a];"
                 f"[1:v]{norm}[b];[2:v]{norm}[c];"
                 f"[a][b]xfade=transition=fade:duration={a1 - b0:.4f}:offset={b0:.4f}[ab];"
                 f"[ab][c]xfade=transition=fade:duration={b1 - c0:.4f}:offset={c0:.4f},"
                 f"fade=t=out:st={total - FADE_OUT}:d={FADE_OUT},"
                 "vignette=angle=PI/5,noise=alls=5:allf=t,"
                 "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]")
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *inputs, "-i", str(wav),
               "-filter_complex", graph, "-map", "[v]", "-map", "3:a", "-map_metadata", "-1",
               "-c:v", "libx264", "-preset", "slow", "-crf", "14",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-af", f"afade=t=out:st={total - FADE_OUT}:d={FADE_OUT}",
               "-c:a", "aac", "-b:a", "320k", "-t", f"{total}", "-movflags", "+faststart", str(out)]
        if subprocess.call(cmd) != 0:
            sys.exit("ffmpeg hata verdi.")
    print(f"Hazır: {out}")


if __name__ == "__main__":
    main()
