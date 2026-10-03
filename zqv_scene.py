"""ZQV - 6 saniyelik karanlık, kasvetli yazı animasyonu (görsel sahne).

Akış (saniye):
  0.0   Simsiyah boşluk; soğuk, ağır bir sis yavaşça kıpırdar.
  0.9   Z, Q, V sırayla bulanıklıktan çıkar; ampul gibi titreyerek yanar.
  2.4   ZQV tam görünür; yavaş bir kamera yaklaşması, nefes alan ışık, kül tozları.
  2.7   Yazının altında ince bir çizgi iki yana uzar.
  4.0   Üç kısa bozulma (RGB kayması, şerit kaymaları, kırmızı parıltı).
  4.7   Harfler duman gibi dağılır: bulanıklaşır, yukarı süzülür, aralıklar açılır.
  5.5   Sis de söner, ekran kararır.

Tüm ölçüler 1920x1080 tasarım alanındadır; render çözünürlüğe göre ölçeklenir.
"""
import math
from pathlib import Path

import numpy as np
import skia

DURATION = 6.0
W, H = 1920, 1080
FONT = "Inter-Black.ttf"
FONT_SIZE = 330.0
TRACK = 0.09                      # harf aralığı (punto oranı)

T_LETTERS = (0.9, 1.4, 1.9)       # Z, Q, V belirme anları
T_REVEAL = 0.9                    # tek harfin bulanıklıktan çıkma süresi
T_LINE = (2.7, 3.7)
T_GLITCH = (4.02, 4.2, 4.42)      # bozulma darbeleri
T_DISSOLVE = (4.7, 5.55)
T_OUT = (5.3, 5.95)

BG = np.array([0.010, 0.012, 0.018], np.float32)
FOG = np.array([0.30, 0.38, 0.47], np.float32)      # soğuk gri-mavi sis
INK = np.array([0.66, 0.70, 0.75], np.float32)      # solgun, soğuk gri-beyaz yazı
BLOOD = np.array([0.55, 0.03, 0.05], np.float32)

FOG_RES = (240, 135)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def smooth(u):
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def window(t, a, b):
    return smooth((t - a) / (b - a))


def _noise_grid(rng, size, cutoff):
    """FFT ile alçak geçirilmiş, kenarları birleşen (tileable) gürültü; 0 ortalı, birim sapmalı."""
    n = rng.standard_normal(size)
    f = np.fft.fft2(n)
    fy = np.fft.fftfreq(size[0])[:, None]
    fx = np.fft.fftfreq(size[1])[None, :]
    f *= np.exp(-(fx**2 + fy**2) / (2 * cutoff**2))
    out = np.fft.ifft2(f).real
    return ((out - out.mean()) / out.std()).astype(np.float32)


def _flicker(t, t0, dur=0.9):
    """Bozuk ampul: belirmeden sonra sönüp yanan, giderek kararlı hâle gelen parlaklık."""
    u = (t - t0) / dur
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    rise = smooth(u * 1.6)
    # hızlı, rastgele görünen ama deterministik açılıp kapanmalar
    wob = math.sin(u * 61) * math.sin(u * 37 + 1.3) + 0.6 * math.sin(u * 113)
    gate = 1.0 if wob > -0.15 - 0.9 * u else 0.12
    return rise * (gate * (1 - u) + u)


class ZQVScene:
    duration = DURATION

    def __init__(self, width=1920, height=1080, fps=60, seed=7):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.rng = np.random.default_rng(seed)
        fonts = Path(__file__).resolve().parent / "fonts"
        self.font = skia.Font(skia.Typeface.MakeFromFile(str(fonts / FONT)), FONT_SIZE)
        self.surface = skia.Surface(width, height)
        self.layer = skia.Surface(width, height)
        self.fog_surface = skia.Surface(width, height)

        # sis: üç katman, farklı hız ve ölçekte
        self.fog_noise = [_noise_grid(self.rng, (FOG_RES[1], FOG_RES[0]), c) for c in (0.020, 0.035, 0.07)]
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        nx, ny = (xx / width - 0.5) * 2, (yy / height - 0.5) * 2
        self.vignette = np.clip(1 - (nx**2 * 0.62 + ny**2 * 0.9) * 0.62, 0, 1) ** 1.6
        self.nx, self.ny = nx, ny
        self.rows = np.arange(height)

        # harf yerleşimi
        glyphs = self.font.textToGlyphs("ZQV")
        widths = self.font.getWidths(glyphs)
        gap = TRACK * FONT_SIZE
        total = sum(widths) + gap * 2
        x = (W - total) / 2
        self.letters = []
        for ch, w in zip("ZQV", widths):
            self.letters.append((ch, x, w))
            x += w + gap
        self.baseline = H / 2 + self.font.getMetrics().fCapHeight / 2 - 8
        self.cap = self.font.getMetrics().fCapHeight

        # kül / toz parçacıkları
        n = 150
        r = self.rng
        self.dust = np.stack([
            r.uniform(0, W, n), r.uniform(0, H, n),                 # x, y
            r.uniform(-8, 8, n), r.uniform(-20, -5, n),              # hız x, y (px/sn)
            r.uniform(0.8, 3.2, n), r.uniform(0, 6.28, n),           # yarıçap, faz
            r.uniform(0.08, 0.38, n), (r.random(n) < 0.12) * 1.0,    # parlaklık, kırmızı mı
        ], 1)

    # ------------------------------------------------------------ yardımcılar

    def _arr(self, surface):
        return surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].astype(np.float32) / 255.0

    def _letter_state(self, i, t):
        """Harfin o andaki (alfa, bulanıklık, x kayması, y kayması, ölçek)."""
        t0 = T_LETTERS[i]
        flick = _flicker(t, t0)
        appear = window(t, t0, t0 + T_REVEAL)
        blur = 26 * (1 - appear) ** 2
        scale = 1.07 - 0.07 * appear
        # duman gibi dağılma
        d = window(t, T_DISSOLVE[0] + 0.07 * i, T_DISSOLVE[1] + 0.05 * i)
        blur += 34 * d**1.4
        dy = -90 * d**1.7 - 10 * d
        dx = (i - 1) * 70 * d**1.5 + 14 * math.sin(i * 2.1) * d
        alpha = flick * (1 - d**0.8)
        # nefes: yavaş parlaklık dalgası
        alpha *= 0.9 + 0.1 * math.sin(2 * math.pi * t / 2.6 + i * 0.7)
        return alpha, blur, dx, dy, scale * (1 + 0.05 * d) * (1 + 0.07 * smooth(t / DURATION))

    def _text_mask(self, t):
        """Yazı katmanı (0..1 gri). Her harf kendi bulanıklığı, kayması, alfasıyla çizilir."""
        with self.layer as c:
            c.clear(skia.ColorBLACK)
            c.scale(self.k, self.k)
            for i, (ch, x, w) in enumerate(self.letters):
                a, blur, dx, dy, s = self._letter_state(i, t)
                if a < 0.003:
                    continue
                c.save()
                c.translate(x + w / 2 + dx, self.baseline - self.cap / 2 + dy)
                c.scale(s, s)
                paint = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(a, a, a, 1))
                if blur > 0.3:
                    paint.setImageFilter(skia.ImageFilters.Blur(blur * self.k, blur * self.k))
                c.drawSimpleText(ch, -w / 2, self.cap / 2, self.font, paint)
                c.restore()
        return self._arr(self.layer)[..., 0]

    def _blur(self, mask, sigma):
        img = skia.Image.fromarray(
            np.ascontiguousarray(np.dstack([np.repeat((mask * 255).astype(np.uint8)[..., None], 3, 2),
                                            np.full(mask.shape, 255, np.uint8)])),
            colorType=skia.kRGBA_8888_ColorType)
        with self.fog_surface as c:
            c.clear(skia.ColorBLACK)
            c.drawImage(img, 0, 0, skia.SamplingOptions(),
                        skia.Paint(ImageFilter=skia.ImageFilters.Blur(sigma * self.k, sigma * self.k)))
        return self._arr(self.fog_surface)[..., 0]

    def _fog(self, t):
        """Üç katmanlı, yavaş akan sis; (H, W) 0..1."""
        small = np.zeros((FOG_RES[1], FOG_RES[0]), np.float32)
        for n, (grid, sx, sy, amp) in enumerate(zip(self.fog_noise, (5.0, -8.0, 12.0), (1.2, -2.0, 0.8),
                                                    (0.55, 0.32, 0.18))):
            ox, oy = sx * t, sy * t
            ix, fx = int(math.floor(ox)), ox - math.floor(ox)
            iy, fy = int(math.floor(oy)), oy - math.floor(oy)
            a = np.roll(grid, (iy, ix), (0, 1))
            b = np.roll(grid, (iy, ix + 1), (0, 1))
            c_ = np.roll(grid, (iy + 1, ix), (0, 1))
            d = np.roll(grid, (iy + 1, ix + 1), (0, 1))
            small += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c_ * (1 - fx) + d * fx) * fy)
        small = np.clip(0.5 + 0.34 * small, 0, 1) ** 2.2
        img = skia.Image.fromarray(
            np.ascontiguousarray(np.dstack([np.repeat((small * 255).astype(np.uint8)[..., None], 3, 2),
                                            np.full(small.shape, 255, np.uint8)])),
            colorType=skia.kRGBA_8888_ColorType)
        with self.fog_surface as c:
            c.clear(skia.ColorBLACK)
            c.drawImageRect(img, skia.Rect(0, 0, self.width, self.height),
                            skia.SamplingOptions(skia.FilterMode.kLinear))
        return self._arr(self.fog_surface)[..., 0]

    def _dust_layer(self, t):
        with self.layer as c:
            c.clear(skia.ColorBLACK)
            c.scale(self.k, self.k)
            for x0, y0, vx, vy, r, ph, a, red in self.dust:
                x = (x0 + vx * t + 14 * math.sin(t * 0.7 + ph)) % W
                y = (y0 + vy * t) % H
                tw = 0.6 + 0.4 * math.sin(t * 1.3 + ph * 3)
                col = skia.Color4f(0.55 * a * tw, 0.02 * a * tw, 0.03 * a * tw, 1) if red else \
                    skia.Color4f(a * tw, a * tw, a * tw * 1.1, 1)
                p = skia.Paint(AntiAlias=True, Color4f=col)
                if r > 2:
                    p.setImageFilter(skia.ImageFilters.Blur(r * 0.5 * self.k, r * 0.5 * self.k))
                c.drawCircle(x, y, r, p)
        return self._arr(self.layer)

    # ------------------------------------------------------------ kare

    def glitch_amount(self, t):
        g = 0.0
        for t0 in T_GLITCH:
            d = t - t0
            if 0 <= d < 0.14:
                g = max(g, 1 - d / 0.14)
        return g

    def render(self, t):
        h, w = self.height, self.width
        g = self.glitch_amount(t)
        out_fade = 1 - window(t, *T_OUT)

        mask = self._text_mask(t)

        # bozulma: şerit kaymaları + RGB ayrımı
        if g > 0:
            rng = np.random.default_rng(int(t * 1000) // 16)
            band_h = int(h * 0.03)
            bands = rng.random(h // band_h + 1) < 0.5
            shifts = (rng.uniform(-1, 1, h // band_h + 1) * 70 * g * self.k).astype(int)
            shift_rows = np.repeat(shifts * bands, band_h)[:h]
            idx = (np.arange(w)[None, :] - shift_rows[:, None]) % w
            mask = np.take_along_axis(mask, idx, 1)
        split = int((1.6 + 13 * g) * self.k)
        mr = np.roll(mask, split, 1)
        mb = np.roll(mask, -split, 1)
        text = np.dstack([mr, mask, mb])

        halo = self._blur(mask, 22)
        halo2 = self._blur(mask, 70)

        fog = self._fog(t)
        # arka ışık: üstten gelen soğuk huzme, nefes alıyor
        breathe = 0.82 + 0.18 * math.sin(2 * math.pi * t / 3.4)
        beam = np.exp(-(self.nx / 0.55) ** 2) * np.clip(1 - (self.ny + 1) / 2.0, 0, 1) ** 1.3
        fog_gain = (0.42 + 0.20 * window(t, 0.6, 2.5)) * breathe
        fog_gain = fog_gain * (1 - 0.8 * window(t, 5.2, 5.9))
        img = BG[None, None, :] + (fog * (0.35 + 0.65 * beam))[..., None] * FOG[None, None, :] * fog_gain

        # yazı, hale, ince çizgi
        lit = np.clip(0.55 + 0.45 * (halo2 * 1.4), 0, 1)
        img += halo[..., None] * INK[None, None, :] * 0.16 + halo2[..., None] * FOG[None, None, :] * 0.30
        # sis yazının önünden geçer: harfleri hafifçe yer
        fog_over = 1 - 0.35 * fog[..., None]
        img = img * 1.0 + text * INK[None, None, :] * fog_over * (0.92 + 0.08 * lit[..., None])

        # kırmızı bozulma parıltısı
        if g > 0:
            img += (self._blur(mask, 40)[..., None] * BLOOD[None, None, :]) * 1.8 * g
            img += (mr - mask).clip(0)[..., None] * BLOOD[None, None, :] * 1.5 * g

        # ince çizgi
        la = window(t, *T_LINE)
        if 0 < la and out_fade > 0:
            y = int((self.baseline + 74) * self.k)
            half = 330 * self.k * (la ** 0.8)
            xs = np.arange(w) - w / 2
            prof = np.clip(1 - np.abs(xs) / max(half, 1), 0, 1) ** 0.7
            line = prof * 0.38 * (1 - window(t, *T_DISSOLVE))
            for dy, a in ((0, 1.0), (-1, 0.25), (1, 0.25), (-3, 0.06), (3, 0.06)):
                if 0 <= y + dy < h:
                    img[y + dy] += line[:, None] * INK[None, :] * a

        # kül parçacıkları
        img += self._dust_layer(t) * 0.9

        # kontrast eğrisi, vinyet, kapanış
        flick_all = 1.0
        if 2.0 < t < 4.0:
            flick_all -= 0.04 * max(0.0, math.sin(t * 43) * math.sin(t * 17.3) - 0.55) * 4
        img *= self.vignette[..., None] * flick_all * out_fade ** 1.2

        # film greni
        grain = self.rng.standard_normal((h, w)).astype(np.float32)
        img += grain[..., None] * 0.016 * (0.4 + img.mean(2, keepdims=True) * 2)

        # hafif soğuk renk eğimi, siyahları ezme
        img = np.clip(img, 0, 1)
        img = img ** 1.08
        return (img * 255 + 0.5).astype(np.uint8)

    def samples(self, t):
        return 1

    # ------------------------------------------------------------ ses için olaylar

    def events(self):
        return dict(duration=DURATION, letters=T_LETTERS, glitch=T_GLITCH, dissolve=T_DISSOLVE,
                    out=T_OUT, line=T_LINE)
