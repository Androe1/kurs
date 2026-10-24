"""SCP tarzı 7 saniyelik sinematiği birleştirir: Blender kareleri + sentez ses -> MP4.

Kullanım:
    python3.11 blender/scp_cinematic.py            # kareler: renders/scp/####.png (+ meta.json)
    python scp_intro.py                            # output/scp_cinematic.mp4
    python scp_intro.py --preview                  # renders_preview/scp -> output/taslak/scp_onizleme.mp4

İlk 1 saniye siyah (referanstaki gibi), ardından üç plan: SECURE / CONTAIN / PROTECT.
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
    fps, first = meta["fps"], meta["first_frame"]
    total = meta["end"]
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "ses.wav"
        write_wav(wav, synthesize(meta))
        vf = (f"fps={fps},tpad=start_duration={(first - 1) / fps}:color=black,"
              "vignette=angle=PI/5,noise=alls=5:allf=t,"
              "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p")
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
               "-framerate", str(fps / meta.get("step", 1)), "-pattern_type", "glob",
               "-i", str(frames / "[0-9][0-9][0-9][0-9].png"),
               "-i", str(wav), "-map", "0:v", "-map", "1:a", "-map_metadata", "-1",
               "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "14",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-af", f"afade=t=out:st={total - 0.35}:d=0.35",
               "-c:a", "aac", "-b:a", "320k", "-t", f"{total}", "-movflags", "+faststart", str(out)]
        if subprocess.call(cmd) != 0:
            sys.exit("ffmpeg hata verdi.")
    print(f"Hazır: {out}")


if __name__ == "__main__":
    main()
