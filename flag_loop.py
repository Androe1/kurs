"""ZQV - sallanan, parcalanmis bayrak (5 sn, kusursuz dongu).

Referans resmin (assets/snx_flag_ref.webp) kendisi kullanilir, boylece doku,
isik, direk ve arka plan birebir aynidir:
  1. SNX harfleri bulunur, kumas dokusu korunarak silinir.
  2. Ayni perspektif/kivrimla yipranmis ZQV harfleri basilir.
  3. Resim katmanlara ayrilir: arka plan + direk (sabit) ve bayrak (alfa ile).
  4. Bayrak, direkten uca ilerleyen dalgalarla bukulur; kivrimlarin egimine
     gore isik/golge degisir, yirtik uclar ayrica cirpinir.
Butun zaman fazlari t/T'nin TAM SAYI katlari oldugu icin 5. saniyedeki kare
0. kareyle ayni olur: GIF/MP4 dongude kesintisiz gorunur.

    python flag_loop.py                  # output/zqv_flag.mp4 + output/zqv_flag.gif
    python flag_loop.py --still 1.25     # tek kare PNG
"""
import argparse
import math
import os
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "assets", "snx_flag_ref.webp")
FONT = os.path.join(HERE, "fonts", "ArchivoBlack-Regular.ttf")
FPS = 30
DURATION = 5.0
# yazinin oturdugu dortgen (SNX'in kapladigi alan, bayragin perspektifi)
TEXT_QUAD = [[346, 270], [1016, 220], [1030, 434], [344, 500]]


def gnoise(rng, h, w, sx, sy=None):
    n = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), sx, sigmaY=sy or sx)
    return n / (n.std() + 1e-6)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------- 1. SNX'i sil
def channels(im):
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    return r - np.maximum(g, b), 0.299 * r + 0.587 * g + 0.114 * b


def remove_letters(im, rng):
    h, w = im.shape[:2]
    chroma, lum = channels(im)
    red = ndi.binary_closing(chroma > 30, iterations=3)
    holes = ndi.binary_fill_holes(red) & ~red            # kirmizinin icindeki siyah harfler
    lab, n = ndi.label(holes)
    sizes = ndi.sum(holes, lab, range(1, n + 1))
    letters = np.isin(lab, 1 + np.where(sizes > 300)[0])
    near = ndi.binary_dilation(letters, iterations=14)
    hole = ndi.binary_dilation(letters | (near & (lum < 45) & (chroma < 35)), iterations=3)

    # dusuk frekans: yari cozunurlukte inpaint
    small = cv2.resize(im, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    hs = cv2.resize(hole.astype(np.uint8), (w // 2, h // 2), interpolation=cv2.INTER_NEAREST)
    low = cv2.inpaint(np.clip(small, 0, 255).astype(np.uint8), hs, 12, cv2.INPAINT_TELEA).astype(np.float32)
    low = cv2.resize(cv2.GaussianBlur(low, (0, 0), 3), (w, h), interpolation=cv2.INTER_CUBIC)
    # yuksek frekans: kumasin dikey firca izleri + lekeler
    nz = 0.55 * gnoise(rng, h, w, 1.2, 9) + 0.35 * gnoise(rng, h, w, 3, 22) + 0.25 * gnoise(rng, h, w, 0.8)
    spots = gnoise(rng, h, w, 6)
    fill = low * np.exp(0.16 * nz - 0.25 * np.clip(spots - 1.3, 0, None))[..., None]
    soft = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.5)[..., None]
    return im * (1 - soft) + fill * soft


# ------------------------------------------------------------- 2. ZQV'yi bas
def jag(draw, rng, p0, ang, n, step, wid, turn=0.35, squash=0.7):
    px, py = p0
    pts = [(px, py)]
    for _ in range(n):
        ang += rng.uniform(-turn, turn)
        st = rng.uniform(*step)
        px += math.cos(ang) * st
        py += math.sin(ang) * st * squash
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=255, width=max(1, int(wid * (1 - i / len(pts)) + rng.uniform(0, 1.5))))


def stamp_text(clean, text, rng):
    h, w = clean.shape[:2]
    ss = 3
    font = ImageFont.truetype(FONT, 260 * ss)
    gap = 12 * ss
    boxes = [font.getbbox(c) for c in text]
    widths = [b[2] - b[0] for b in boxes]
    cap = font.getbbox("Z")
    cap_h = cap[3] - cap[1]
    fw = sum(widths) + gap * (len(text) - 1)
    pad = 60 * ss
    flat = Image.new("L", (fw + 2 * pad, cap_h + 2 * pad + 80 * ss), 0)
    d = ImageDraw.Draw(flat)
    x = pad
    for c, b, wd in zip(text, boxes, widths):
        d.text((x - b[0], pad - cap[1]), c, font=font, fill=255)
        x += wd + gap
    flat = np.asarray(flat, np.float32) / 255

    src = np.float32([[pad, pad], [pad + fw, pad], [pad + fw, pad + cap_h], [pad, pad + cap_h]])
    hm = cv2.getPerspectiveTransform(src, np.float32(TEXT_QUAD))
    warp = cv2.warpPerspective(flat, hm, (w, h), flags=cv2.INTER_AREA)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = cv2.remap(warp, xx, yy - 6 * np.sin((xx - 350) / 680 * math.pi * 1.3 + 0.4), cv2.INTER_LINEAR)

    a = np.clip((warp - 0.5 + 0.10 * gnoise(rng, h, w, 1.6)) * 3 + 0.5, 0, 1)   # puruzlu kenar

    # yipranma: benekler, catlaklar, Q->V arasi buyuk yirtik
    sp = gnoise(rng, h, w, 1.0)
    speck = np.clip((sp - 2.9 + 0.6 * gnoise(rng, h, w, 30)) * 1.2, 0, 1)
    cr = Image.new("L", (w, h), 0)
    cd = ImageDraw.Draw(cr)
    for k in range(5):
        jag(cd, rng, (600 + rng.uniform(-10, 10), 318 + k * 7 + rng.uniform(-4, 4)),
            0.33 + rng.uniform(-.06, .06), int(rng.integers(30, 48)), (5, 10), rng.uniform(3, 7), 0.25, 1.0)
    for _ in range(8):
        jag(cd, rng, (rng.uniform(380, 1000), rng.uniform(260, 470)), rng.uniform(0, 2 * math.pi),
            int(rng.integers(8, 18)), (4, 9), 2, 0.6)
    cr = np.asarray(cr, np.float32) / 255
    tear_zone = np.clip(cv2.GaussianBlur(cr, (0, 0), 9) * 4, 0, 1)
    speck = np.clip(speck + np.clip((sp - 1.4) * 1.2, 0, 1) * tear_zone, 0, 1)
    a *= 1 - np.clip(speck + cv2.GaussianBlur(cr, (0, 0), 0.7), 0, 1)

    # harflerden kumasa sizan siyah ince catlaklar
    td = Image.new("L", (w, h), 0)
    tdd = ImageDraw.Draw(td)
    for p0, ang in [((360, 430), 2.6), ((362, 452), 3.3), ((540, 452), 0.2), ((585, 470), 2.2),
                    ((800, 395), 0.4), ((1000, 330), -0.2), ((700, 300), -2.2)]:
        jag(tdd, rng, p0, ang, int(rng.integers(6, 12)), (4, 9), 3, 0.5, 1.0)
    a = np.maximum(a, cv2.GaussianBlur(np.asarray(td, np.float32) / 255, (0, 0), 0.6) * 0.95)

    lum = cv2.GaussianBlur(clean.mean(-1), (0, 0), 8) / 120
    ink = np.array([5, 4, 4], np.float32) * (0.5 + lum[..., None]) + gnoise(rng, h, w, 1)[..., None] * 2
    return clean * (1 - a[..., None]) + ink * a[..., None]


# ------------------------------------------------- 3. katmanlara ayir
def hoist_x(y):
    """bayragin direge baglandigi cizgi (resimde hafif egik)."""
    return 271.0 - 0.108 * (y - 100.0)


def separate(plate):
    h, w = plate.shape[:2]
    chroma, lum = channels(plate)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    right = xx > hoist_x(yy) + 2

    # arka plan: gri, dusuk doygunluk; bayrak/direk icermeyen piksellerden push-pull dolgu
    sat = plate.max(-1) - plate.min(-1)
    bg_ok = (sat < 12) & (lum > 28)
    bg_ok = ndi.binary_erosion(bg_ok, iterations=4)
    # once vinyetli gradyana polinom (koselere dogru dogal uzanir), sonra artiga push-pull
    xn, yn = (xx - w / 2) / w, (yy - h / 2) / h
    basis = np.stack([xn ** i * yn ** j for i in range(5) for j in range(5 - i)], -1)
    coef, *_ = np.linalg.lstsq(basis[bg_ok], plate[bg_ok], rcond=None)
    poly = basis @ coef
    wgt = bg_ok.astype(np.float32)
    est = np.zeros_like(plate)
    for sig in (128, 64, 32, 16, 8, 4):
        num = cv2.GaussianBlur((plate - poly) * wgt[..., None], (0, 0), sig)
        den = cv2.GaussianBlur(wgt, (0, 0), sig)[..., None]
        conf = np.clip(den / 0.35, 0, 1)
        est = est * (1 - conf) + num / np.maximum(den, 1e-6) * conf
    bgfit = poly + est

    # alfa: karanlik (siyah kumas/yirtiklar) + kirmizilik
    bl = channels(bgfit)[1]
    a_dark = smooth((bl - lum) / np.maximum(bl - 4.0, 1.0), 0.18, 0.92)
    a_red = smooth(chroma, 8, 40)
    a = np.maximum(a_dark, a_red) * right
    core = ndi.binary_fill_holes(ndi.binary_closing(a > 0.5, iterations=4))
    lab, n = ndi.label(core)
    core = lab == 1 + np.argmax(ndi.sum(core, lab, range(1, n + 1)))      # ana bayrak govdesi
    # govdeye bagli/yakin parcalari tut (koselerdeki karanlik vinyet bayrak degil)
    lab, n = ndi.label(a > 0.06)
    keep = np.unique(lab[ndi.binary_dilation(core, iterations=20) & (lab > 0)])
    a = a * np.isin(lab, keep)
    a = np.maximum(a, ndi.binary_erosion(core, iterations=3)).astype(np.float32)

    # sabit katman: bayragin altinda kalan yere tahmini arka plan + tane
    rng = np.random.default_rng(1)
    grain = gnoise(rng, h, w, 0.7)[..., None] * 2.2
    under = cv2.GaussianBlur(ndi.binary_dilation(a > 0.02, iterations=3).astype(np.float32), (0, 0), 1.0)
    under = (under * right)[..., None]
    static = plate * (1 - under) + (bgfit + grain) * under
    fp = (plate - (1 - a[..., None]) * static) * (a[..., None] > 0)     # on-carpimli bayrak rengi
    return static.astype(np.float32), fp.astype(np.float32), a, chroma


# ------------------------------------------------------------- 4. dalga
class Flag:
    def __init__(self, text):
        rng = np.random.default_rng(7)
        im = np.asarray(Image.open(REF).convert("RGB")).astype(np.float32)
        self.h, self.w = im.shape[:2]
        self.plate = stamp_text(remove_letters(im, rng), text, rng)
        self.static, self.fp, self.a, chroma = separate(self.plate)
        h, w = self.h, self.w
        self.tex = np.concatenate([self.fp, self.a[..., None] * 255], -1)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.X, self.Y = xx, yy
        hx = hoist_x(yy)
        self.u = np.clip((xx - hx) / (1250.0 - hx), 0, 1.1)       # direkten uca 0..1
        self.v = (yy - 90.0) / 560.0                               # ustten alta 0..1
        # yirtik/serbest kisimlar: kirmizi govdeden uzak bolgeler daha cok cirpinir
        body = cv2.GaussianBlur((chroma > 40).astype(np.float32), (0, 0), 25)
        self.loose = cv2.GaussianBlur(1 - smooth(body, 0.05, 0.6), (0, 0), 10)

    def field(self, ph):
        tau = 2 * math.pi
        u, v = self.u, self.v
        amp = smooth(u, 0.0, 0.35) * u ** 0.9
        p1 = tau * (1.10 * u + 0.18 * v - 3 * ph)
        p2 = tau * (2.05 * u - 0.35 * v - 5 * ph + 0.37)
        p3 = tau * (3.60 * u + 0.60 * v - 8 * ph + 0.81)
        dy = amp * (17 * np.sin(p1) + 7 * np.sin(p2) + 2.5 * np.sin(p3))
        dx = amp * (-9 * np.cos(p1) - 3.5 * np.cos(p2))
        # yirtik uclarin cirpintisi
        q1 = tau * (5.0 * u + 2.3 * v - 9 * ph)
        q2 = tau * (7.5 * u - 3.1 * v - 11 * ph + 0.5)
        fl = self.loose * smooth(u, 0.05, 0.4)
        dy += fl * (6 * np.sin(q1) + 3 * np.sin(q2))
        dx += fl * (4 * np.cos(q1 + 0.7))
        # isik: dalganin egimi (kumasin isiga donen/uzaklasan yuzleri)
        slope = amp * (17 * 1.10 * np.cos(p1) + 7 * 2.05 * np.cos(p2) + 2.5 * 3.6 * np.cos(p3))
        return dx.astype(np.float32), dy.astype(np.float32), slope

    def frame(self, ph):
        dx, dy, slope = self.field(ph)
        mx = self.X - dx
        my = self.Y - dy
        s = cv2.remap(self.tex, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = np.clip(s[..., 3:] / 255, 0, 1)
        rgb = np.clip(s[..., :3], 0, None)
        k = np.clip(slope / 45.0, -1, 1)[..., None]
        shade = 1 + 0.30 * k + 0.12 * np.clip(k, 0, 1) ** 2
        rgb = rgb * shade
        out = self.static * (1 - a) + rgb
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="ZQV")
    ap.add_argument("--out", default="output/zqv_flag")
    ap.add_argument("--still", type=float, help="tek kareyi PNG kaydet (saniye)")
    ap.add_argument("--gif-width", type=int, default=960)
    args = ap.parse_args()

    flag = Flag(args.text)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    if args.still is not None:
        Image.fromarray(flag.frame((args.still / DURATION) % 1.0)).save(args.out + "_still.png")
        return

    n = int(round(FPS * DURATION))          # 150 kare; kare n == kare 0 oldugundan yazilmaz
    mp4 = args.out + ".mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{flag.w}x{flag.h}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "14",
         "-preset", "slow", "-tune", "film", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
        stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(flag.frame(i / n).tobytes())
    ff.stdin.close()
    ff.wait()

    # 1080p kopya (lanczos + hafif keskinlestirme)
    mp4_hd = args.out + "_1080p.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf",
                    "scale=1920:1080:flags=lanczos,unsharp=5:5:0.4", "-c:v", "libx264", "-crf", "14",
                    "-preset", "slow", "-tune", "film", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    mp4_hd], check=True)

    # GIF: yuksek kalite + paylasim icin hafif (~10 MB alti) surum
    outs = [mp4, mp4_hd]
    for suffix, width, fps, colors in ((".gif", args.gif_width, FPS, 256), ("_small.gif", 600, 25, 160)):
        vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
              f"[a]palettegen=max_colors={colors}:stats_mode=full[p];"
              "[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", vf, "-loop", "0",
                        args.out + suffix], check=True)
        outs.append(args.out + suffix)
    print("\n".join(outs))


if __name__ == "__main__":
    main()
