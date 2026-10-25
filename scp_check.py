"""SCP sinematiği için son kontrol: her 0.25 sn'de kare, spektrogram, yükseklik ve tık taraması.

    python scp_check.py output/scp_cinematic.mp4            # -> output/kontrol/

Çıktılar:
  kareler_1..4.jpg   her 0.25 sn'den bir kare (zaman etiketli, 12'li sayfalar)
  spektrogram.png    ffmpeg showspectrumpic (log frekans)
  rapor.json         ebur128 (bütünleşik LUFS, true peak), tık adayları, sondaki kararma eğrisi,
                     yazı zaman çizelgesi (aynı karede iki kelime yok), Blender kontrolleri (meta.json)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage, signal

ROOT = Path(__file__).resolve().parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
STEP = 0.25


def frames(video, out, tmp):
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(video), "-vf",
                    f"select='not(mod(n\\,{round(60 * STEP)}))',scale=640:360", "-vsync", "0",
                    str(Path(tmp) / "f_%03d.png")], check=True)
    pngs = sorted(Path(tmp).glob("f_*.png"))
    font = ImageFont.truetype(str(ROOT / "fonts" / "Montserrat-SemiBold.ttf"), 22)
    sheets = []
    for k in range(0, len(pngs), 12):
        sheet = Image.new("RGB", (4 * 640, 3 * 360))
        for i, p in enumerate(pngs[k:k + 12]):
            im = Image.open(p)
            d = ImageDraw.Draw(im)
            t = (k + i) * STEP
            d.rectangle([0, 0, 92, 30], fill=(0, 0, 0))
            d.text((6, 3), f"{t:5.2f}s", font=font, fill=(255, 220, 60))
            sheet.paste(im, ((i % 4) * 640, (i // 4) * 360))
        path = out / f"kareler_{k // 12 + 1}.jpg"
        sheet.save(path, quality=88)
        sheets.append(str(path))
    return sheets, len(pngs)


def audio(video, tmp):
    wav = Path(tmp) / "a.wav"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "2", "-ar", "48000",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32768.0
    return wav, x


def ebur128(path):
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    tail = r[r.rfind("Summary:"):]
    return {"integrated_lufs": float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1)),
            "true_peak_dbtp": float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1)),
            "lra_lu": float(re.search(r"LRA:\s+([\d.]+) LU", tail).group(1))}


def clicks(x, sr=48000):
    """Tık adayı: ikinci farkın (yüksek frekanslı, anlık sıçrama) 10 ms'lik yerel medyanın çok üstüne
    çıktığı ve aynı anda sinyalin kendisinin de sıçradığı örnekler."""
    d2 = np.abs(np.diff(x, 2, axis=0)).max(1)
    med = ndimage.median_filter(d2, size=int(0.01 * sr)) + 1e-5
    hit = np.nonzero((d2 > 25 * med) & (d2 > 0.03))[0]
    groups = []
    for i in hit:
        if not groups or i - groups[-1][-1] > sr * 0.005:
            groups.append([i])
        else:
            groups[-1].append(i)
    return [round(g[0] / sr, 4) for g in groups]


def tail_curve(x, sr=48000, end=12.0):
    rms = lambda a, b: round(float(20 * np.log10(np.sqrt(np.mean(x[int(a * sr):int(b * sr)] ** 2)) + 1e-12)), 1)
    return {f"{a:.1f}-{a + 0.1:.1f}": rms(a, a + 0.1) for a in np.arange(9.2, end - 0.05, 0.4)} | {
        "son_100ms": rms(end - 0.1, end), "son_ornek": round(float(np.abs(x[-1]).max()), 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", default=str(ROOT / "output" / "scp_cinematic.mp4"))
    ap.add_argument("--out", default=str(ROOT / "output" / "kontrol"))
    ap.add_argument("--meta", default=str(ROOT / "renders" / "scp" / "meta.json"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = {}
    with tempfile.TemporaryDirectory() as tmp:
        rep["kare_sayfalari"], rep["kare_sayisi"] = frames(a.video, out, tmp)
        wav, x = audio(a.video, tmp)
        rep["ses"] = ebur128(a.video)
        rep["ses"]["tik_adaylari_sn"] = clicks(x)
        rep["ses"]["sondaki_kararma_db"] = tail_curve(x)
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(wav), "-lavfi",
                        "showspectrumpic=s=1600x600:legend=1:scale=log:fscale=log:color=intensity",
                        str(out / "spektrogram.png")], check=True)
    sys.path.insert(0, str(ROOT))
    import scp_intro
    text = scp_intro.TextLayer()
    both = [n for n in range(scp_intro.N_FRAMES) if sum(
        w_in <= n / 60 < w_out + scp_intro.TEXT_FADE for _, w_in, w_out in scp_intro.WORDS) > 1]
    full = {w: round(w_out - (w_in + scp_intro.TEXT_FADE), 2) for w, w_in, w_out in scp_intro.WORDS}
    widths = {w: text.masks[w].size[0] / text.ss * scp_intro.TEXT_SCALE0 for w, _, _ in scp_intro.WORDS}
    rep["yazi"] = {"iki_kelime_ayni_karede": both, "tam_okunur_sure_sn": full,
                   "kadraja_sigar": all(v < scp_intro.W * 0.9 for v in widths.values())}
    if Path(a.meta).exists():
        meta = json.loads(Path(a.meta).read_text())
        rep["blender"] = {k: v for k, v in meta.items() if k.startswith("checks_")}
    (out / "rapor.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
