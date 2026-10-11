"""ZQV - sallanan, parcalanmis bayrak (5 sn, kusursuz dongu).

Bayrak dokusu (kirmizi/siyah, yirtik kenarlar, ZQV yazisi) kodla uretilir,
her karede dalga bozulmasiyla pole'a bagli bir bayrak gibi sallandirilir.
Butun dalga fazlari t/T'nin TAM SAYI katlari oldugu icin 5. saniyedeki kare
0. kareyle ayni olur: GIF/MP4 dongude kesintisiz gorunur.

    python flag_loop.py                 # output/zqv_flag.mp4 + output/zqv_flag.gif
    python flag_loop.py --text ZQV --still 1.25
"""
import argparse
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720          # cikis cozunurlugu
FPS = 30
DURATION = 5.0            # saniye = tam bir dongu
TW, TH = 1000, 580        # bayrak dokusu boyutu
X0, Y0 = 250, 110          # dokunun ekrandaki sol-ust kosesi
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Montserrat-Black.ttf")


# ---------------------------------------------------------------- yardimcilar
def noise(w, h, sx, sy, rng):
    """sx x sy piksellik hucrelerle yumusak (bikubik) rastgele alan, 0..1."""
    small = rng.random((h // sy + 3, w // sx + 3)).astype(np.float32)
    img = Image.fromarray(small, mode="F").resize((w + 2 * sx, h + 2 * sy), Image.BICUBIC)
    return np.clip(np.asarray(img)[sy:sy + h, sx:sx + w], 0, 1)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------ bayrak dokusu
def build_texture(text, seed=7):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:TH, 0:TW].astype(np.float32)

    # dikey fircali kirmizi kumas
    streak = 0.5 * noise(TW, TH, 3, 70, rng) + 0.3 * noise(TW, TH, 2, 26, rng) + 0.2 * noise(TW, TH, 7, 140, rng)
    stain = noise(TW, TH, 45, 45, rng)
    base = np.clip(0.30 + 1.0 * (streak - 0.35) + 0.35 * (stain - 0.5), 0, 1)
    dark = np.array([95, 4, 14], np.float32)
    bright = np.array([238, 26, 46], np.float32)
    col = dark + (bright - dark) * base[..., None]
    col *= 1 - 0.55 * smooth(noise(TW, TH, 30, 30, rng), 0.62, 0.9)[..., None]   # leke

    # yirtik kenar maskesi (ust/alt dikey, sag yatay iplikler)
    def teeth(n, sx, seedoff):
        r = np.random.default_rng(seed + seedoff)
        a = np.interp(np.arange(n), np.arange(n // sx + 2) * sx, r.random(n // sx + 2))
        c = np.interp(np.arange(n), np.arange(n // 90 + 2) * 90, r.random(n // 90 + 2))
        return np.clip(a * 2.6 - 1.25, 0, 1) ** 0.8 * (0.35 + 0.65 * c)

    ytop = 14 + 78 * (1 - teeth(TW, 7, 1))
    ybot = TH - 14 - 78 * (1 - teeth(TW, 7, 2))
    xr = TW - 14 - 100 * (1 - teeth(TH, 7, 3))
    fray_v = (noise(TW, TH, 2, 16, rng) - 0.5) * 34
    fray_h = (noise(TW, TH, 16, 2, rng) - 0.5) * 34
    m_top = yy - ytop[None, :] + fray_v
    m_bot = ybot[None, :] - yy + fray_v
    m_r = xr[:, None] - xx + fray_h
    m = np.minimum(np.minimum(m_top, m_bot), m_r)
    m = np.minimum(m, xx + 40)
    alpha = np.clip(m / 2.2 + 0.5, 0, 1)

    # siniri izleyen siyah bant (kirmizi iplikler iceri uzanir)
    dist = np.minimum(np.minimum(yy - ytop[None, :], ybot[None, :] - yy), xr[:, None] - xx)
    black = np.clip(1 - dist / 85 + (streak - 0.5) * 1.0, 0, 1)
    black = smooth(black, 0.32, 0.72)
    col *= (1 - black)[..., None]

    # yazi
    font = ImageFont.truetype(FONT, 300)
    glyphs = list(text)
    track = 26
    widths = [font.getbbox(g)[2] - font.getbbox(g)[0] for g in glyphs]
    total = sum(widths) + track * (len(glyphs) - 1)
    mask = Image.new("L", (TW, TH), 0)
    d = ImageDraw.Draw(mask)
    x = (TW - total) / 2 - 10
    cy = TH / 2 + 4
    for g, w_ in zip(glyphs, widths):
        d.text((x - font.getbbox(g)[0], cy), g, font=font, fill=255, anchor="lm")
        x += w_ + track
    # hafif egim/yipranma
    t = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.1)), np.float32) / 255
    holes = smooth(noise(TW, TH, 3, 3, rng) * (0.5 + 0.7 * noise(TW, TH, 50, 50, rng)), 0.74, 0.86)
    t *= 1 - holes
    crack = Image.new("L", (TW, TH), 0)
    cd = ImageDraw.Draw(crack)
    for _ in range(9):
        px, py = rng.uniform(TW * 0.25, TW * 0.75), rng.uniform(TH * 0.3, TH * 0.7)
        ang = rng.uniform(-0.7, 0.7)
        pts = [(px, py)]
        for _ in range(int(rng.integers(8, 16))):
            ang += rng.uniform(-0.8, 0.8)
            px += math.cos(ang) * rng.uniform(6, 16)
            py += math.sin(ang) * rng.uniform(6, 16)
            pts.append((px, py))
        cd.line(pts, fill=255, width=int(rng.integers(2, 5)))
    t *= 1 - np.asarray(crack.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    ink = np.array([10, 4, 7], np.float32)
    col = col * (1 - t[..., None]) + ink * t[..., None]

    return np.clip(col, 0, 255) / 255, alpha.astype(np.float32)


# ----------------------------------------------------------- sabit katmanlar
def build_background(rng):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W * 0.58) / (W * 0.62), (yy - H * 0.42) / (H * 0.78))
    g = 188 - 150 * np.clip(r, 0, 1.4) ** 1.7
    g += (rng.random((H, W)) - 0.5) * 7                     # sabit tane
    return np.stack([g, g, g * 1.01], -1) / 255


def build_pole():
    s = 2
    img = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    px, pw = 236 * s, 26 * s
    for i in range(pw):                                     # silindirik gradyan
        k = i / pw
        v = int(14 + 52 * math.sin(math.pi * k) ** 3 * (1 - 0.6 * k))
        d.line([(px - pw // 2 + i, 70 * s), (px - pw // 2 + i, H * s)], fill=(v, v, v + 2, 255))
    d.ellipse([px - 19 * s, 28 * s, px + 19 * s, 66 * s], fill=(18, 18, 20, 255))
    d.ellipse([px - 11 * s, 33 * s, px - 2 * s, 42 * s], fill=(90, 90, 94, 255))
    for yv in (104, 300, 520):                              # baglama halkalari
        d.rectangle([px - 15 * s, yv * s, px + 15 * s, (yv + 8) * s], fill=(10, 10, 11, 255))
    img = img.resize((W, H), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    return a[..., :3], a[..., 3:]


# --------------------------------------------------------------------- kare
class Renderer:
    def __init__(self, text):
        rng = np.random.default_rng(3)
        rgb, alpha = build_texture(text)
        self.tex = np.concatenate([rgb * alpha[..., None], alpha[..., None]], -1).astype(np.float32)
        self.bg = build_background(rng)
        self.pole_rgb, self.pole_a = build_pole()
        self.Y, self.X = np.mgrid[0:H, 0:W].astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rv = np.hypot((xx - W / 2) / (W * 0.75), (yy - H / 2) / (H * 0.85))
        self.vig = (1 - 0.55 * np.clip(rv, 0, 1.2) ** 2.2)[..., None].astype(np.float32)

    def frame(self, ph):
        """ph = t / DURATION (0..1). Tum fazlar ph'nin tam sayi katlari."""
        X, Y = self.X, self.Y
        tau = 2 * math.pi
        u = np.clip((X - X0) / TW, 0, 1.15)
        v0 = (Y - Y0) / TH
        amp = u ** 1.15

        a1 = tau * (1.7 * u + 0.30 * v0 - ph)
        a2 = tau * (3.3 * u + 0.50 * v0 - 2 * ph + 0.21)
        a3 = tau * (5.9 * u + 0.80 * v0 - 3 * ph + 0.60)
        s1, s2, s3 = np.sin(a1), np.sin(a2), np.sin(a3)
        c1, c2, c3 = np.cos(a1), np.cos(a2), np.cos(a3)

        tail = smooth(u, 0.6, 1.0)                        # uc kisim daha cirpinik
        flutter = tail * (6 * np.sin(tau * (9.0 * u + 5.5 * v0 - 2 * ph)) +
                          3 * np.sin(tau * (14.0 * u - 3 * v0 - 3 * ph + 0.3)))
        dy = amp * (78 * s1 + 30 * s2 + 10 * s3) + flutter - 40 * u
        dx = amp * (20 * c1 + 8 * c2)

        tx = (X - X0) + dx
        ty = (Y - Y0) - dy

        # cift dogrusal ornekleme
        x0 = np.floor(tx).astype(np.int32)
        y0 = np.floor(ty).astype(np.int32)
        fx = (tx - x0)[..., None]
        fy = (ty - y0)[..., None]
        ok = (x0 >= 0) & (x0 < TW - 1) & (y0 >= 0) & (y0 < TH - 1)
        x0c = np.clip(x0, 0, TW - 2)
        y0c = np.clip(y0, 0, TH - 2)
        T = self.tex
        s = ((T[y0c, x0c] * (1 - fx) + T[y0c, x0c + 1] * fx) * (1 - fy) +
             (T[y0c + 1, x0c] * (1 - fx) + T[y0c + 1, x0c + 1] * fx) * fy)
        s *= ok[..., None]
        rgb, a = s[..., :3], s[..., 3:]

        # kumas kivrimlarindan isik/golge
        slope = amp * (78 * 1.7 * c1 + 30 * 3.3 * c2 + 10 * 5.9 * c3)
        shade = (1 - 0.0030 * slope - 0.07 * s1)[..., None]
        rgb = rgb * shade + 0.10 * np.clip(-slope / 280, 0, 1)[..., None] * a * np.array([1.0, 0.25, 0.3], np.float32)

        out = self.bg * (1 - a) + rgb
        out = out * (1 - self.pole_a) + self.pole_rgb * self.pole_a
        out = out * self.vig
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="ZQV")
    ap.add_argument("--out", default="output/zqv_flag")
    ap.add_argument("--still", type=float, help="tek kareyi PNG kaydet (saniye)")
    ap.add_argument("--gif-width", type=int, default=800)
    args = ap.parse_args()

    r = Renderer(args.text)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    if args.still is not None:
        Image.fromarray(r.frame((args.still / DURATION) % 1.0)).save(args.out + "_still.png")
        return

    n = int(round(FPS * DURATION))          # 150 kare; kare n == kare 0 oldugundan yazilmaz
    mp4 = args.out + ".mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
         "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
        stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(r.frame(i / n).tobytes())
    ff.stdin.close()
    ff.wait()

    gif = args.out + ".gif"
    vf = (f"fps={FPS},scale={args.gif_width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=160:stats_mode=full[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", vf, "-loop", "0", gif], check=True)
    print(mp4, gif)


if __name__ == "__main__":
    main()
