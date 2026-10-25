"""SCP tarzı 12 saniyelik sinematiği birleştirir: Blender kareleri + 2D katman + sentez ses -> MP4.

Kullanım:
    python3.11 blender/render_chunks.py --step 2   # kareler: renders/scp/<plan>/####.png (+ meta.json)
    python scp_intro.py                            # output/scp_cinematic.mp4
    python scp_intro.py --preview                  # renders_preview/scp -> output/taslak/scp_onizleme.mp4
    python scp_intro.py --still 1.5,4.8            # tek kareler (PNG) -> output/taslak/

Kurgu (60 fps, kare n -> t = n/60 sn; Blender karesi = n + 1):
    0.0 - 0.4   siyahtan hızlı açılış
    0.4 - 3.6   depo          SECURE
    3.6         sert kesme (ses vuruşu)
    3.6 - 6.8   yol           CONTAIN
    6.8         8 karelik siyaha karartma (en koyu an vuruşta)
    6.8 - 9.2   tesis         PROTECT
    9.2         sert kesme, en büyük vuruş: oyun logosu (tam ortada)
    9.2 - 12.0  logo kartı (2.2 sn sabit), son 0.6 sn'de kararır

Yazılar render'dan sonra en üst katmanda çizilir (hiçbir nesne önüne geçemez): aynı yazı tipi,
büyük harf yüksekliği kare yüksekliğinin %9'u, tam merkez; 0.3 sn belirme + ölçek 1.05 -> 1.0,
sabit bekleme, 0.3 sn kaybolma, hafif koyu gölge. İki yazı hiçbir karede birlikte bulunmaz.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from scp_sound import synthesize
from sound import write_wav

ROOT = Path(__file__).resolve().parent
W, H, FPS, END = 1920, 1080, 60, 12.0
N_FRAMES = int(END * FPS)
FONT = ROOT / "fonts" / "Montserrat-SemiBold.ttf"
GAME_LOGO = ROOT / "assets" / "brand" / "game_logo.png"

OPEN = 0.4                       # siyahtan açılış süresi
CUT_HARD, CUT_DIP, CUT_LOGO = 3.6, 6.8, 9.2
DIP_FRAMES = 8                   # siyaha karartma: kesmenin iki yanında 4'er kare
FADE_OUT = 0.6                   # logo kartının sonunda kararma
SHOT_RANGES = {"secure": (0.0, CUT_HARD), "contain": (CUT_HARD, CUT_DIP), "protect": (CUT_DIP, CUT_LOGO)}
# (kelime, belirme başı, kaybolma başı): 0.3 sn belirme, sabit bekleme, 0.3 sn kaybolma
WORDS = (("SECURE", 0.90, 3.00), ("CONTAIN", 4.00, 6.20), ("PROTECT", 7.00, 8.85))
TEXT_FADE, TEXT_SCALE0 = 0.3, 1.05
CAP_FRAC = 0.09                  # büyük harf yüksekliği / kare yüksekliği
TRACK = 0.30                     # harf aralığı (em)
LOGO_FRAC = 0.46                 # oyun logosu yüksekliği / kare yüksekliği (en az %30), tam ortada


def ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- 2D öğeler

def text_sprite(word, scale=2):
    """Kelimenin RGBA görüntüsü (scale kat çözünürlükte); büyük harf yüksekliği CAP_FRAC * H."""
    cap = CAP_FRAC * H * scale
    probe = ImageFont.truetype(str(FONT), 200)
    cap_200 = probe.getbbox("H")[3] - probe.getbbox("H")[1]
    font = ImageFont.truetype(str(FONT), round(200 * cap / cap_200))
    track = TRACK * font.size
    widths = [font.getlength(c) for c in word]
    total = sum(widths) + track * (len(word) - 1)
    top, bottom = font.getbbox("H")[1], font.getbbox("H")[3]
    pad = int(0.6 * cap)
    img = Image.new("L", (int(total + 2 * pad), int(bottom - top + 2 * pad)), 0)
    d = ImageDraw.Draw(img)
    x = pad
    for c, w in zip(word, widths):
        d.text((x, pad - top), c, font=font, fill=255)
        x += w + track
    return img  # alfa maskesi; harflerin optik merkezi görüntü merkezinde


def place_text(mask, scale, ss):
    """Maskeyi (ss kat çözünürlükte) ölçekleyip tam kare boyutunda alfa olarak ortalar."""
    w, h = mask.size
    tw, th = max(1, round(w * scale / ss)), max(1, round(h * scale / ss))
    m = mask.resize((tw, th), Image.LANCZOS)
    canvas = Image.new("L", (W, H), 0)
    canvas.paste(m, ((W - tw) // 2, (H - th) // 2))
    return np.asarray(canvas, np.float32) / 255.0


class TextLayer:
    """Kelime katmanı: beyaz harfler + yumuşak koyu gölge; ölçek animasyonu kare kare."""

    def __init__(self):
        self.ss = 2
        self.masks = {w: text_sprite(w, self.ss) for w, _, _ in WORDS}
        self.cache = {}

    def alpha(self, word, scale):
        key = (word, round(scale, 4))
        if key not in self.cache:
            a = place_text(self.masks[word], scale, self.ss)
            sh = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7))
            sh = np.roll(np.asarray(sh, np.float32) / 255.0, (4, 3), (0, 1))
            self.cache = {key: (a, sh)}  # yalnızca son ölçek tutulur (bellek)
        return self.cache[key]

    def state(self, t):
        """(kelime, opaklık, ölçek) ya da None. Bir anda en fazla bir kelime."""
        live = []
        for word, t_in, t_out in WORDS:
            if t_in <= t < t_out + TEXT_FADE:
                u_in = (t - t_in) / TEXT_FADE
                op = smooth(u_in) if t < t_out else 1 - smooth((t - t_out) / TEXT_FADE)
                sc = TEXT_SCALE0 + (1.0 - TEXT_SCALE0) * ease_out(u_in)
                live.append((word, op, sc))
        assert len(live) <= 1, f"{t:.3f} sn: iki kelime aynı karede"
        return live[0] if live else None

    def apply(self, img, t):
        st = self.state(t)
        if st is None:
            return img
        word, op, sc = st
        a, sh = self.alpha(word, sc)
        img = img * (1 - 0.55 * op * sh[..., None])            # gölge
        white = np.array([0.96, 0.96, 0.94], np.float32)
        return img * (1 - op * a[..., None]) + white * (op * a[..., None])


def game_logo_rgba(height):
    """Kullanıcının oyun logosu: görünür içerik sınırına kırpılır, yüksekliğe ölçeklenir."""
    im = Image.open(GAME_LOGO).convert("RGBA")
    rgb = np.asarray(im)[..., :3].max(-1)
    alpha = np.asarray(im)[..., 3]
    ys, xs = np.nonzero((rgb > 12) & (alpha > 8))
    m = int(0.04 * (ys.max() - ys.min()))  # gölgesi için küçük pay
    box = (max(xs.min() - m, 0), max(ys.min() - m, 0), min(xs.max() + m, im.width), min(ys.max() + m, im.height))
    im = im.crop(box)
    w = round(im.width * height / im.height)
    return im.resize((w, int(height)), Image.LANCZOS)


class LogoCard:
    """Final kartı: siyah zemin, tam ortada oyun logosu (kare yüksekliğinin %46'sı)."""

    def __init__(self):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((xx - W / 2) / (0.6 * W), (yy - H / 2) / (0.6 * H))
        self.base = (0.03 * np.exp(-r ** 2 * 2.2))[..., None] * np.array([1.0, 0.92, 0.78], np.float32)
        g = game_logo_rgba(LOGO_FRAC * H)
        x0, y0 = (W - g.width) // 2, (H - g.height) // 2
        self.logo = np.zeros((H, W, 4), np.float32)
        self.logo[y0:y0 + g.height, x0:x0 + g.width] = np.asarray(g, np.float32) / 255.0
        lum = self.logo[..., :3].max(-1) * self.logo[..., 3]   # yalnızca altın kısımlar parlar
        glow = Image.fromarray((np.clip(lum * 1.6, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(30))
        self.glow = np.asarray(glow, np.float32) / 255.0
        self.bbox = (x0, y0, x0 + g.width, y0 + g.height)

    def render(self, t):
        u = t - CUT_LOGO
        a = self.logo[..., 3:]
        img = self.base * (1 - a) + self.logo[..., :3] * a
        # vuruş anında kısa sıcak parlama; logonun kendisi ilk kareden itibaren sabit
        flash = 0.45 * np.exp(-u / 0.12)
        img = img + (flash + 0.12) * self.glow[..., None] * np.array([1.0, 0.78, 0.42], np.float32)
        fade = 1 - smooth((t - (END - FADE_OUT)) / FADE_OUT)
        return img * fade


# ---------------------------------------------------------------- sahne kareleri

class Frames:
    def __init__(self, root, meta):
        self.root = root
        self.step = meta.get("step", 1)
        self.spans = meta["spans"]

    def get(self, shot, n):
        """Çıkış karesi n için planın render edilmiş karesi (adımlı renderda en yakın önceki)."""
        f0, f1 = self.spans[shot]
        b = min(max(n + 1, f0), f1)
        b = f0 + ((b - f0) // self.step) * self.step
        p = self.root / shot / f"{b:04d}.png"
        if not p.exists():
            sys.exit(f"Kare yok: {p}")
        im = Image.open(p).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.BICUBIC)
        return np.asarray(im, np.float32) / 255.0


def grade(img, rng):
    """Hafif kontrast eğrisi, soğuk gölgeler, vinyet ve ince film greni (yazılardan önce)."""
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    img = img + (np.clip(0.18 - lum, 0, None) * 0.18)[..., None] * np.array([-0.2, 0.0, 0.35], np.float32)
    img = np.clip(img, 0, 1)
    img = img + 0.08 * (img - img * img * (3 - 2 * img))  # S eğrisi (düşük şiddet)
    yy, xx = np.ogrid[0:H, 0:W]
    v = ((xx - W / 2) / (W / 2)) ** 2 * 0.55 + ((yy - H / 2) / (H / 2)) ** 2 * 0.45
    img = img * (1 - 0.32 * np.clip(v, 0, 1.4) ** 1.6)[..., None]
    gr = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
    gr = np.asarray(Image.fromarray(gr).resize((W, H), Image.BILINEAR))
    lum = np.clip(img.mean(-1, keepdims=True), 0, 1)
    img = img + gr[..., None] * 0.016 * (0.35 + lum * (1 - lum) * 2.6)
    return img


def scene_of(t):
    for k, (a, b) in SHOT_RANGES.items():
        if a <= t < b:
            return k
    return None


def brightness(n):
    """Kesme/kararma çarpanı: açılış, 6.8'deki 8 karelik dip."""
    t = n / FPS
    g = smooth(t / OPEN) if t < OPEN else 1.0
    nd = round(CUT_DIP * FPS)
    k = DIP_FRAMES // 2
    if nd - k <= n < nd + k:
        g *= abs(n - (nd - 0.5)) / k
    return g


def compose(n, frames, text, card, rng):
    t = n / FPS
    if t >= CUT_LOGO:
        img = card.render(t)
        img = img + rng.standard_normal((H, W, 1)).astype(np.float32) * 0.006
    else:
        img = frames.get(scene_of(t), n) * brightness(n)
        img = grade(img, rng)
        img = text.apply(img, t)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description="SCP sinematiğini MP4 olarak birleştirir.")
    ap.add_argument("--preview", action="store_true", help="önizleme karelerini kullan")
    ap.add_argument("--frames", help="kare klasörü (varsayılan renders/scp)")
    ap.add_argument("--still", help="yalnızca bu saniyelerdeki kareleri PNG yaz (virgüllü)")
    ap.add_argument("--wav", help="ses dosyasını ayrıca buraya yaz")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()
    frames_dir = Path(a.frames) if a.frames else ROOT / ("renders_preview" if a.preview else "renders") / "scp"
    out = Path(a.output) if a.output else ROOT / "output" / (
        "taslak/scp_onizleme.mp4" if a.preview else "scp_cinematic.mp4")
    meta = json.loads((frames_dir / "meta.json").read_text())
    assert abs(meta["end"] - END) < 1e-6 and meta["cuts"] == [CUT_HARD, CUT_DIP, CUT_LOGO], meta["cuts"]
    frames, text, card = Frames(frames_dir, meta), TextLayer(), LogoCard()
    rng = np.random.default_rng(5)
    out.parent.mkdir(parents=True, exist_ok=True)

    if a.still:
        for s in a.still.split(","):
            n = round(float(s) * FPS)
            p = out.parent / f"{out.stem}_{float(s):05.2f}.png"
            Image.fromarray(compose(n, frames, text, card, rng)).save(p)
            print(p)
        return

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(a.wav) if a.wav else Path(tmp) / "ses.wav"
        write_wav(wav, synthesize({**meta, "words": [t_in for _, t_in, _ in WORDS]}))
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-i", str(wav), "-map", "0:v", "-map", "1:a", "-map_metadata", "-1",
               "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-tune", "film",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-c:a", "aac", "-b:a", "320k", "-t", f"{END}", "-movflags", "+faststart", str(out)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for n in range(N_FRAMES):
            p.stdin.write(compose(n, frames, text, card, rng).tobytes())
            if n % 60 == 0:
                print(f"  {n / FPS:4.1f} sn", flush=True)
        p.stdin.close()
        if p.wait() != 0:
            sys.exit("ffmpeg hata verdi.")
    print(f"Hazır: {out}")


if __name__ == "__main__":
    main()
