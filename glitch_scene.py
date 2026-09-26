"""Androe Studio - 10 saniyelik karakterli intro (GLITCH Productions açılışından ilham).

Akış (saniye):
  0.35 - 3.05  A N D R O E harfleri tek tek, eğik paneller arasında dönerek gelir;
               her harfte zemin değişir (beyaz / siyah / gri). Son harf ekranı doldurur.
  3.05 - 3.45  Glitch geçişi: görüntü şeritlere bölünür, kayar, beyaza patlar.
  3.45 - 5.35  1. karakter (androe) - siyah, beyaz, gri: aşağıdan fırlar, eğik
               rampanın önünde panikle koşar, sonra boşluğa düşer.
  5.35 - 7.25  2. karakter (androeofficial) - siyah, beyaz, altın: aşağıdan
               dönerek yükselir, kameraya doğru atlar, havada asılı kalır,
               dönerek boşluğa düşer.
  7.25 - 7.65  Altın / siyah / beyaz paneller ekranı süpürür, siyaha kesilir.
  7.65 - 10.0  Siyah zeminde beyaz "ANDROE STUDIO" glitch efektiyle kurulur,
               üzerinden ışık geçer, sonra kararır.

Sağ altta "Inspired by Glitch Productions" yazar; rengi her pikselde altındaki
zeminin tersidir (koyu zeminde beyaz, açık zeminde siyah).

Karakterler Roblox Studio'dan dışa aktarılan R6 modellerdir (characters/),
rig.py ile gerçek 3B olarak pozlanıp çizilir. Hızlı hareketlerde hem hareket
bulanıklığı hem de Spider-Verse tarzı kademeli izler (trail) vardır.
"""
import math
from pathlib import Path

import numpy as np
import skia

from rig import R6Character, Renderer, euler, look_at

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
W, H = 1920, 1080
CX, CY = W / 2, H / 2
DURATION = 10.0

# Renkler
WHITE = (0.96, 0.96, 0.96)
PURE = (1.0, 1.0, 1.0)
BLACK = (0.04, 0.04, 0.045)
GREY = (0.55, 0.55, 0.56)
LIGHT = (0.86, 0.86, 0.87)
GOLD = (0.86, 0.66, 0.22)
GOLD_LIGHT = (0.97, 0.83, 0.45)

# Zaman çizelgesi
LETTERS = "ANDROE"
T_LETTERS = 0.35
BEAT = 0.45
T_GLITCH = (3.05, 3.45)
T_CHAR1 = (3.45, 5.05)
T_CHAR2 = (5.05, 6.75)
T_SWEEP = (6.75, 7.15)
T_LOGO = 7.15
T_OUT = (9.55, 9.95)

# Harf sahneleri: (zemin, harf, gölge kopyaları)
LETTER_STYLE = [
    (WHITE, BLACK, GREY), (BLACK, PURE, GREY), (GREY, PURE, BLACK),
    (WHITE, BLACK, GREY), (BLACK, PURE, GREY), (WHITE, BLACK, GREY),
]

CREDIT = "Inspired by Glitch Productions"


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_in_out(u):
    return 4 * u**3 if u < 0.5 else 1 - (2 - 2 * u) ** 3 / 2


def ease_out(u):
    return 1 - (1 - u) ** 3


def ease_out_back(u, s=2.0):
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def ease_in(u):
    return u**3


def span(t, a, b):
    return clamp01((t - a) / (b - a))


def col(rgb, a=1.0):
    return skia.Color4f(*rgb, a)


def poly(points):
    p = skia.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    p.close()
    return p


def hexagon(x, y, r, rot):
    return poly([(x + r * math.cos(rot + k * math.pi / 3), y + r * math.sin(rot + k * math.pi / 3)) for k in range(6)])


# ---------------------------------------------------------------- karakter hareketleri

def ang(x=0.0, y=0.0, z=0.0):
    return (x, y, z)


# Pomni'nin asılı kalışı referansta art arda birkaç pozdan geçer; aynı akışı anahtar
# pozlarla kurup aralarını Catmull-Rom ile (hız kesintisiz) dolduruyoruz.
# Gövde kalçadan kameraya doğru öne eğik, kafa kalkık kameraya bakar.
FLAIL_KEYS = [
    (0.30, {"torso": ang(x=-0.62), "head": ang(x=0.95, y=0.15),                  # el yukarıdan kameraya uzanır
            "right_arm": ang(x=2.9, z=0.3), "left_arm": ang(x=0.6, z=-0.3),
            "right_leg": ang(x=0.75, z=0.1), "left_leg": ang(x=0.55, z=-0.1)}),
    (0.55, {"torso": ang(x=-0.78, y=0.1), "head": ang(x=1.05, y=-0.1),           # iki kol aşağıya uzanır
            "right_arm": ang(x=1.45, z=0.2), "left_arm": ang(x=1.3, z=-0.25),
            "right_leg": ang(x=0.25, z=0.12), "left_leg": ang(x=0.45, z=-0.12)}),
    (0.80, {"torso": ang(x=-0.55, y=-0.08), "head": ang(x=0.9, y=0.2),           # kollar toplanır, bacak tekmeler
            "right_arm": ang(x=0.95, z=0.65), "left_arm": ang(x=0.5, z=-0.7),
            "right_leg": ang(x=1.25, z=0.1), "left_leg": ang(x=0.2, z=-0.15)}),
    (1.05, {"torso": ang(x=-0.62, y=0.05), "head": ang(x=0.95, y=-0.15),         # kol yukarıda sallanır
            "right_arm": ang(x=2.55, z=0.95), "left_arm": ang(x=1.0, z=-0.4),
            "right_leg": ang(x=0.7, z=0.1), "left_leg": ang(x=0.85, z=-0.1)}),
]


def catmull(keys, t):
    """Anahtar pozlar arasında hızı kesintisiz geçiş (Catmull-Rom)."""
    times = [k[0] for k in keys]
    if t <= times[0]:
        return keys[0][1]
    if t >= times[-1]:
        return keys[-1][1]
    i = max(j for j in range(len(times)) if times[j] <= t)
    u = (t - times[i]) / (times[i + 1] - times[i])
    p0, p1, p2, p3 = (keys[min(max(j, 0), len(keys) - 1)][1] for j in (i - 1, i, i + 1, i + 2))
    out = {}
    for part in p1:
        out[part] = tuple(0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u
                                 + (-a + 3 * b - 3 * c + d) * u ** 3)
                          for a, b, c, d in zip(p0[part], p1[part], p2[part], p3[part]))
    return out


def flail_pose(t):
    """Pomni gibi havada panik; t karakterin sahneye girişinden beri geçen süre."""
    return catmull(FLAIL_KEYS, t)


def launch_pose(t):
    """Aşağıdan fırlatılırken: kollar ve bacaklar hızın etkisiyle aşağıda kalır."""
    w = math.sin(2 * math.pi * 3 * t)
    return {
        "right_arm": ang(x=0.25 + 0.1 * w, z=0.3),
        "left_arm": ang(x=0.15 - 0.1 * w, z=-0.3),
        "right_leg": ang(x=0.15, z=0.08),
        "left_leg": ang(x=-0.1, z=-0.08),
        "head": ang(x=0.35),
    }


def fall_pose(t):
    """Düşerken kollar yukarıda çırpınır, bacaklar açılır."""
    w = math.sin(2 * math.pi * 4 * t)
    up = 2 * math.pi - 2.6                    # kollar yukarıda (öne doğru kalkmış yönden)
    return {
        "right_arm": ang(x=up + 0.3 * w, z=0.5),
        "left_arm": ang(x=up - 0.3 * w, z=-0.5),
        "right_leg": ang(x=0.5 + 0.2 * w, z=0.2),
        "left_leg": ang(x=-0.4 - 0.2 * w, z=-0.2),
        "head": ang(x=-0.3),
    }


def leap_pose(k, h=0.0):
    """Caine gibi dramatik poz (k: 0 toplu, 1 tam açılmış; h: asılı kalışta 0->1 ilerleme).
    Gövde öne eğik ve çapraz; asılıyken kol yavaşça yukarı açılır, bacaklar açılıp kapanır."""
    return {
        "torso": ang(x=(-0.55 - 0.12 * h) * k, y=(0.15 - 0.1 * h) * k),     # kameraya doğru öne eğik
        "head": ang(x=1.05 * k, y=(0.15 - 0.3 * h) * k),                   # kafa kalkık, kameraya bakar
        "right_arm": ang(x=(-0.2 - 0.35 * h) * k, z=(2.6 + 0.55 * h) * k), # kol yukarı-yana açılır
        "left_arm": ang(x=(1.0 + 0.3 * h) * k, z=(-0.55 - 0.2 * h) * k),   # diğeri aşağı-öne
        "right_leg": ang(x=(-0.2 + 0.35 * h) * k, z=(0.6 - 0.25 * h) * k), # biri geride, açık
        "left_leg": ang(x=(1.2 - 0.5 * h) * k, z=(-0.4 + 0.15 * h) * k),   # diğeri dizden öne
    }


def blend_pose(a, b, k):
    """İki poz arasında yumuşak geçiş: her eklemin açıları doğrusal karışır (ani dönüş olmaz)."""
    zero = (0.0, 0.0, 0.0)
    return {part: tuple((1 - k) * p + k * q for p, q in zip(a.get(part, zero), b.get(part, zero)))
            for part in set(a) | set(b)}


def to_matrices(pose):
    return {part: euler(*angles) for part, angles in pose.items()}


def arc(t, t0, rise, hang, top, bottom=-7.0, drop=17.0):
    """Örnek videodan ölçülen dikey hareket: yükseliş -> asılı kalış -> düşüş.

    Yükseliş hafif aşarak (ease-out-back) durur; asılı kalışta yavaş süzülür;
    düşüş sıfır hızla başlayıp yerçekimi gibi hızlanır. Hız hiçbir yerde
    kesintiye uğramaz, bu yüzden hareket akıcıdır.
    """
    u = span(t, t0, t0 + rise)
    y = bottom + (top - bottom) * (ease_out_back(u, 0.7) if u < 1 else 1.0)
    hold = t - (t0 + rise)
    if hold > 0:
        y += 0.18 * math.sin(math.pi * min(hold / hang, 1.0))        # asılıyken hafifçe süzülür
    fall = t - (t0 + rise + hang)
    if fall > 0:
        y -= drop * fall * fall                                        # düşüş: y = g t^2
    return y


def char1_state(t):
    """androe: aşağıdan fırlar, havada panikle çırpınır, sonra boşluğa düşer."""
    a, _ = T_CHAR1
    rise, hang = 0.28, 0.8
    y = arc(t, a, rise, hang, top=1.1)
    u_rise = span(t, a, a + rise)
    u_fall = clamp01((t - a - rise - hang) / 0.45)
    # kollar yükselişin sonunda açılmaya devam eder: dönüş hızı yumuşak kalır
    pose = blend_pose(launch_pose(t), flail_pose(t - a), ease_in_out(span(t, a, a + rise + 0.12)))
    pose = blend_pose(pose, fall_pose(t), ease_in_out(u_fall))
    yaw = -0.6 + 0.15 * math.sin(2 * math.pi * 0.6 * t)            # havada hafifçe döner
    roll = 0.15 * math.sin(2 * math.pi * 0.8 * t + 0.7) + 0.5 * ease_in(u_fall)
    tilt = -0.15 - 0.3 * (1 - ease_out(u_rise)) + 1.6 * ease_in(u_fall)
    x = 0.5 + 0.35 * span(t, a, a + rise + hang) - 1.2 * ease_in(u_fall)
    z = -1.6 * ease_out(u_rise) + 1.0 * u_fall
    return to_matrices(pose), euler(y=yaw, x=tilt, z=roll), np.array([x, y, z])


def char2_state(t):
    """androeofficial: dönerek yükselip kameraya yaklaşır, havada dramatik pozda durur, düşer."""
    a, _ = T_CHAR2
    rise, hang = 0.34, 0.85
    y = arc(t, a, rise, hang, top=0.3, bottom=-8.0)
    u_rise = span(t, a, a + rise)
    u_hang = span(t, a + rise, a + rise + hang)
    u_fall = clamp01((t - a - rise - hang) / 0.45)
    e = ease_out(u_rise)
    pose = blend_pose(launch_pose(t), leap_pose(0.25 + 0.75 * e, ease_in_out(u_hang)), ease_in_out(span(t, a, a + rise + 0.15)))
    fall = fall_pose(t)
    fall["right_arm"] = ang(x=-0.3, z=2.7 + 0.2 * math.sin(2 * math.pi * 4 * t))   # açık kol yukarıda kalır
    pose = blend_pose(pose, fall, ease_in_out(u_fall))
    spin = -2 * math.pi * (1 - e)                                    # yükselirken bir tur döner
    yaw = 0.2 + spin + 0.08 * u_hang + 3.0 * ease_in(u_fall)
    tilt = -0.2 * e + 0.05 * u_hang + 0.8 * ease_in(u_fall)
    roll = -0.35 * e - 0.04 * u_hang + 0.3 * u_fall
    # yükselirken kameraya yaklaşır, asılıyken yavaşça uzaklaşır (ölçülen boy değişimi gibi)
    z = -1.8 * e + 0.9 * ease_in_out(u_hang) + 1.2 * u_fall
    x = -0.5 + 1.0 * e + 0.15 * u_hang + 1.0 * ease_in(u_fall)
    return to_matrices(pose), euler(y=yaw, x=tilt, z=roll), np.array([x, y, z])


# ---------------------------------------------------------------- sahne

class GlitchScene:
    duration = DURATION

    def __init__(self, width=1920, height=1080, fps=60, seed=4):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.to_linear = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)
        self.black_font = skia.Typeface.MakeFromFile(str(FONTS / "Montserrat-Black.ttf"))
        self.semi_font = skia.Typeface.MakeFromFile(str(FONTS / "Montserrat-SemiBold.ttf"))
        self.renderer = Renderer(width, height)
        self.androe = R6Character(ROOT / "characters" / "androe")
        self.official = R6Character(ROOT / "characters" / "androeofficial")
        rng = np.random.default_rng(seed)
        self.shapes = [dict(x=rng.uniform(80, W - 80), y=rng.uniform(80, H - 80), r=rng.uniform(34, 70),
                            kind=rng.integers(2), rot=rng.uniform(0, 6.3), spin=rng.uniform(-1.2, 1.2),
                            depth=rng.uniform(0.4, 1.0), dark=rng.random() < 0.45) for _ in range(9)]
        self.glitch_rng = np.random.default_rng(seed + 1)
        self._logo_layout()
        self._credit_mask()

    # ------------------------------------------------------------ harfler

    def _letter_path(self, ch, size):
        font = skia.Font(self.black_font, size)
        p = font.getPath(font.textToGlyphs(ch)[0])
        b = p.computeTightBounds()
        p.offset(-(b.left() + b.right()) / 2, -(b.top() + b.bottom()) / 2)
        return p

    def _draw_letters(self, c, t):
        i = int((t - T_LETTERS) // BEAT)
        i = min(max(i, 0), len(LETTERS) - 1)
        local = t - T_LETTERS - i * BEAT
        bg, fg, shade = LETTER_STYLE[i]
        prev_bg = LETTER_STYLE[i - 1][0] if i > 0 else BLACK
        c.clear(col(prev_bg).toColor())
        # Yeni zemin eğik bir panel olarak alttan yukarı süpürür
        wipe = ease_out(clamp01(local / 0.14)) if t >= T_LETTERS else 0.0
        edge = H + 260 - (H + 520) * wipe
        c.drawPath(poly([(-50, edge + 180), (W + 50, edge - 180), (W + 50, H + 50), (-50, H + 50)]),
                   skia.Paint(AntiAlias=True, Color4f=col(bg)))
        # Altta ince, eğik ikinci renk şeridi (zemine derinlik verir)
        stripe = (0.5 * (bg[0] + fg[0]),) * 3
        rise = ease_out(clamp01((local - 0.05) / 0.2))
        c.drawPath(poly([(-50, H + 60 - 170 * rise), (W + 50, H + 60 - 60 * rise), (W + 50, H + 60), (-50, H + 60)]),
                   skia.Paint(AntiAlias=True, Color4f=col(stripe)))
        if t < T_LETTERS:
            return
        # Harf: dönerek, büyükten küçülerek gelir; gölge kopyaları renk kayması gibi
        u = clamp01((local - 0.04) / 0.22)
        e = ease_out_back(u) if u < 1 else 1.0
        spin = (-28 if i % 2 else 24) * (1 - ease_out(u))
        scale = 1.55 - 0.55 * e
        size = 470
        if i == len(LETTERS) - 1:                           # son harf ekranı doldurur
            scale *= 1 + 3.5 * ease_in(clamp01((local - 0.18) / 0.3))
        drift = 10 * math.sin(2 * math.pi * 1.3 * local)
        path = self._letter_path(LETTERS[i], size)
        offset = 16 + 30 * (1 - ease_out(u))
        for dx, dy, rgb in ((-offset, -offset * 0.4, shade), (offset * 0.7, offset * 0.5, stripe)):
            c.save()
            c.translate(CX + dx + drift, CY + dy)
            c.rotate(spin)
            c.scale(scale, scale)
            c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=col(rgb, 0.9 * clamp01(u * 3))))
            c.restore()
        c.save()
        c.translate(CX + drift, CY)
        c.rotate(spin)
        c.scale(scale, scale)
        c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=col(fg, clamp01(u * 4))))
        c.restore()

    # ------------------------------------------------------------ karakter sahneleri

    def _stage(self, c, t, accent, dark, t0):
        """Karakter sahnesinin zemini: beyaz zemin, eğik şeritler, süzülen şekiller."""
        c.clear(col(WHITE).toColor())
        local = t - t0
        # Büyük, silik dekor şekilleri (üçgen ve X)
        deco = skia.Paint(AntiAlias=True, Color4f=col(LIGHT))
        c.save()
        c.translate(W - 360 + 20 * local, 230)
        c.rotate(-18 + 4 * local)
        c.drawPath(poly([(0, -170), (190, 130), (-190, 130)]), deco)
        c.restore()
        c.save()
        c.translate(380 - 15 * local, H - 250)
        c.rotate(24 - 5 * local)
        for ang in (45, -45):
            c.save()
            c.rotate(ang)
            c.drawRoundRect(skia.Rect(-190, -52, 190, 52), 12, 12, deco)
            c.restore()
        c.restore()
        # Eğik rampa şeritleri (arkada koyu, önde vurgu rengi)
        slide = 60 * local
        c.drawPath(poly([(-100, H * 0.64 + slide * 0.2), (W + 100, H * 0.82 + slide * 0.2),
                         (W + 100, H + 100), (-100, H + 100)]), skia.Paint(AntiAlias=True, Color4f=col(dark)))
        c.drawPath(poly([(-100, H * 0.75 + slide * 0.2), (W + 100, H * 0.95 + slide * 0.2),
                         (W + 100, H + 100), (-100, H + 100)]), skia.Paint(AntiAlias=True, Color4f=col(accent)))
        c.drawPath(poly([(W * 0.55 - slide, -50), (W + 100, -50), (W + 100, H * 0.12 - slide * 0.1)]),
                   skia.Paint(AntiAlias=True, Color4f=col(accent)))

    def _draw_shapes(self, c, t, accent, dark, t0, front):
        """Karakterin önünde/arkasında süzülen kareler ve altıgenler."""
        local = t - t0
        for k, s in enumerate(self.shapes):
            if (s["depth"] > 0.75) != front:
                continue
            x = s["x"] - 90 * local * s["depth"]
            y = s["y"] + 25 * math.sin(1.6 * local + k)
            rot = s["rot"] + s["spin"] * local
            r = s["r"] * (0.7 + 0.5 * s["depth"])
            paint = skia.Paint(AntiAlias=True, Color4f=col(dark if s["dark"] else accent))
            if s["kind"]:
                c.drawPath(hexagon(x, y, r, rot), paint)
            else:
                c.save()
                c.translate(x, y)
                c.rotate(math.degrees(rot))
                c.drawRect(skia.Rect(-r * 0.8, -r * 0.8, r * 0.8, r * 0.8), paint)
                c.restore()

    def _camera(self, t, t0, t1):
        """Yavaşça yaklaşan kamera; 1. karakter havada daha yüksekte durduğu için kadraj yukarıda."""
        u = span(t, t0, t1)
        ty = 3.9 if t0 == T_CHAR1[0] else 2.6
        # referanstaki gibi hafif yukarıdan bakar: öne eğilen gövde kameraya uzanıyormuş gibi görünür
        return look_at((0.3 * u, ty + 3.4, -14.5 + 1.2 * u), (0.3, ty, 0))

    def _char_image(self, character, state, view):
        """Karakteri çizer ve yalnızca kapladığı alanı döndürür: (görüntü, x, y)."""
        pose, rot, pos = state
        rgba = self.renderer.render(character, pose, rot, pos, view, fov=34)
        ys, xs = np.nonzero(rgba[..., 3] > 0)
        if len(xs) == 0:
            return None, 0, 0
        pad = int(24 * self.k)
        x0, y0 = max(xs.min() - pad, 0), max(ys.min() - pad, 0)
        x1, y1 = min(xs.max() + pad, self.width), min(ys.max() + pad, self.height)
        crop = np.ascontiguousarray(rgba[y0:y1, x0:x1])
        return skia.Image.fromarray(crop, colorType=skia.kRGBA_8888_ColorType), x0, y0

    def _draw_character(self, c, t, character, state_fn, t0, t1, outline_a, outline_b, trail_rgb):
        """Karakteri, renk kaymalı kalın dış çizgisi ve kademeli izleriyle çizer."""
        view = self._camera(t, t0, t1)
        c.save()
        c.scale(1 / self.k, 1 / self.k)                        # GL görüntüsü çıktı çözünürlüğünde
        # Spider-Verse tarzı kademeli izler: geçmiş anlardaki silüetler, renkli ve silik
        for step, alpha in ((3, 0.16), (2, 0.26), (1, 0.38)):
            tt = t - step * 0.05
            if tt < t0:
                continue
            ghost, gx, gy = self._char_image(character, state_fn(tt), self._camera(tt, t0, t1))
            if ghost is None:
                continue
            c.drawImage(ghost, gx, gy, skia.SamplingOptions(),
                        skia.Paint(Alphaf=alpha, ColorFilter=skia.ColorFilters.Blend(col(trail_rgb).toColor(),
                                                                                     skia.BlendMode.kSrcIn)))
        img, x0, y0 = self._char_image(character, state_fn(t), view)
        if img is None:
            c.restore()
            return
        r = 9 * self.k
        for dx, dy, rgb in ((-7, -4, outline_a), (7, 5, outline_b)):
            c.drawImage(img, x0 + dx * self.k, y0 + dy * self.k, skia.SamplingOptions(), skia.Paint(
                ImageFilter=skia.ImageFilters.Dilate(r, r),
                ColorFilter=skia.ColorFilters.Blend(col(rgb).toColor(), skia.BlendMode.kSrcIn)))
        c.drawImage(img, x0, y0)
        c.restore()

    # ------------------------------------------------------------ geçişler ve logo

    def _draw_sweep(self, c, t):
        u = span(t, *T_SWEEP)
        c.clear(col(WHITE).toColor())
        for k, rgb in enumerate((GOLD, BLACK, PURE, BLACK)):
            p = ease_in_out(clamp01(u * 1.6 - k * 0.2))
            if p <= 0:
                continue
            x = -W * 0.4 + (W * 1.8) * p
            c.drawPath(poly([(-100, -100), (x + 300, -100), (x - 300, H + 100), (-100, H + 100)]),
                       skia.Paint(AntiAlias=True, Color4f=col(rgb)))

    def _logo_layout(self):
        font = skia.Font(self.black_font, 132)
        text = "ANDROE STUDIO"
        glyphs = font.textToGlyphs(text)
        xs, x = [], 0.0
        for g, adv in zip(glyphs, font.getWidths(glyphs)):
            xs.append(x)
            x += adv + 0.04 * 132
        paths = []
        for ch, g, gx in zip(text, glyphs, xs):
            p = font.getPath(g)
            p.offset(gx, 0)
            paths.append((ch, p))
        b = skia.Path()
        for _, p in paths:
            b.addPath(p)
        bounds = b.computeTightBounds()
        dx, dy = CX - (bounds.left() + bounds.right()) / 2, CY - (bounds.top() + bounds.bottom()) / 2
        self.logo = []
        rng = np.random.default_rng(12)
        for ch, p in paths:
            if ch == " ":
                continue
            p.offset(dx, dy)
            self.logo.append((p, T_LOGO + 0.1 + rng.uniform(0, 0.55)))
        self.logo_box = (bounds.left() + dx, bounds.top() + dy, bounds.right() + dx, bounds.bottom() + dy)

    def _draw_logo(self, c, t):
        c.clear(col(BLACK).toColor())
        local = t - T_LOGO
        # Silik dekor: sağ üstte üçgen, sol altta X (koyu gri)
        deco = skia.Paint(AntiAlias=True, Color4f=col((0.11, 0.11, 0.12)))
        grow = ease_out(clamp01(local / 0.5))
        c.save()
        c.translate(W - 330, 250)
        c.rotate(-15)
        c.scale(grow, grow)
        c.drawPath(poly([(0, -190), (210, 150), (-210, 150)]), deco)
        c.restore()
        c.save()
        c.translate(340, H - 240)
        c.rotate(22)
        c.scale(grow, grow)
        for ang in (45, -45):
            c.save()
            c.rotate(ang)
            c.drawRoundRect(skia.Rect(-200, -56, 200, 56), 14, 14, deco)
            c.restore()
        c.restore()
        # Harfler rastgele sırayla, dilim kaymalı glitch ile belirir
        rng = np.random.default_rng(int(t * 60))
        for p, appear in self.logo:
            u = clamp01((t - appear) / 0.22)
            if u <= 0:
                continue
            flicker = u < 1 and rng.random() < 0.35
            bounds = p.computeTightBounds()
            if u < 1:                                         # dilimlere bölünmüş, kayan harf
                n = 5
                for s in range(n):
                    y0 = bounds.top() + (bounds.height()) * s / n
                    y1 = bounds.top() + (bounds.height()) * (s + 1) / n
                    shift = (1 - u) * rng.uniform(-60, 60)
                    c.save()
                    c.clipRect(skia.Rect(bounds.left() - 100, y0, bounds.right() + 100, y1))
                    c.translate(shift, 0)
                    c.drawPath(p, skia.Paint(AntiAlias=True, Color4f=col(GREY if flicker else PURE, 0.5 + 0.5 * u)))
                    c.restore()
            else:
                c.drawPath(p, skia.Paint(AntiAlias=True, Color4f=col(PURE)))
        # Ara sıra küçük glitch titremesi
        if T_LOGO + 0.8 < t < 9.4 and int(t * 60) % 37 in (0, 1):
            y = self.logo_box[1] + (self.logo_box[3] - self.logo_box[1]) * rng.random()
            c.save()
            c.clipRect(skia.Rect(0, y, W, y + 18))
            c.translate(rng.uniform(-30, 30), 0)
            for p, _ in self.logo:
                c.drawPath(p, skia.Paint(AntiAlias=True, Color4f=col(GREY)))
            c.restore()
        # Işık süzmesi
        u = span(t, T_LOGO + 1.0, T_LOGO + 1.6)
        if 0 < u < 1:
            l, top, r, bottom = self.logo_box
            box = skia.Rect(l - 120, top - 120, r + 120, bottom + 120)
            c.saveLayer(box, skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=0.7 * math.sin(math.pi * u),
                                        ImageFilter=skia.ImageFilters.Blur(10, 10)))
            for p, _ in self.logo:
                c.drawPath(p, skia.Paint(AntiAlias=True, Color4f=col(PURE)))
            cx = l - 150 + (r - l + 300) * ease_in_out(u)
            shader = skia.GradientShader.MakeLinear([skia.Point(cx - 90, 0), skia.Point(cx + 90, 0)],
                                                    [col(PURE, 0).toColor(), col(PURE).toColor(), col(PURE, 0).toColor()])
            c.drawRect(box, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kDstIn))
            c.restore()

    # ------------------------------------------------------------ çizim

    def draw(self, c, t):
        c.save()
        c.scale(self.k, self.k)
        if t < T_GLITCH[0]:
            self._draw_letters(c, t)
        elif t < T_CHAR1[0]:
            self._draw_letters(c, T_GLITCH[0] - 1e-3)       # glitch son harf üzerinde uygulanır
        elif t < T_CHAR1[1]:
            self._stage(c, t, GREY, BLACK, T_CHAR1[0])
            self._draw_shapes(c, t, GREY, BLACK, T_CHAR1[0], front=False)
            self._draw_character(c, t, self.androe, char1_state, *T_CHAR1, BLACK, GREY, GREY)
            self._draw_shapes(c, t, GREY, BLACK, T_CHAR1[0], front=True)
        elif t < T_CHAR2[1]:
            self._stage(c, t, GOLD, BLACK, T_CHAR2[0])
            self._draw_shapes(c, t, GOLD, BLACK, T_CHAR2[0], front=False)
            self._draw_character(c, t, self.official, char2_state, *T_CHAR2, BLACK, GOLD, GOLD_LIGHT)
            self._draw_shapes(c, t, GOLD, BLACK, T_CHAR2[0], front=True)
        elif t < T_SWEEP[1]:
            self._draw_sweep(c, t)
        else:
            self._draw_logo(c, t)
        c.restore()

    def _post(self, rgb, t):
        """Kare üzerinde son işlemler: glitch geçişi, kararma, sağ alttaki ters renkli yazı."""
        if T_GLITCH[0] <= t < T_GLITCH[1] + 0.12:
            rgb = self._glitch(rgb, t)
        if t > T_OUT[0]:
            rgb = (rgb * (1 - ease_in_out(span(t, *T_OUT)))).astype(np.uint8)
        return self._credit(rgb, t)

    def _glitch(self, rgb, t):
        u = span(t, *T_GLITCH)
        rng = np.random.default_rng(int(t * 600))
        out = rgb.copy()
        w = rgb.shape[1]
        x = 0
        while x < w:                                          # dikey şeritler aşağı-yukarı kayar
            sw = int(rng.integers(12, 90) * self.k)
            shift = int(rng.normal(0, 70 * u) * self.k)
            out[:, x:x + sw] = np.roll(rgb[:, x:x + sw], shift, axis=0)
            if rng.random() < 0.08 * u:
                out[:, x:x + sw] = (np.array(rng.choice([WHITE, BLACK, GREY])) * 255).astype(np.uint8)
            x += sw
        for _ in range(int(10 * u)):                          # küçük renkli bozulma blokları
            bx, by = rng.integers(0, w - 40), rng.integers(0, rgb.shape[0] - 20)
            out[by:by + int(rng.integers(4, 14)), bx:bx + int(rng.integers(30, 220))] = \
                (np.array(rng.choice([PURE, BLACK, GREY, LIGHT])) * 255).astype(np.uint8)
        flash = clamp01((t - T_GLITCH[1] + 0.12) / 0.12) if t < T_GLITCH[1] else 1 - clamp01((t - T_GLITCH[1]) / 0.12)
        return (out * (1 - flash) + 245 * flash).astype(np.uint8)

    def _credit_mask(self):
        """Sağ alttaki yazının maskesi (çıktı çözünürlüğünde)."""
        size = 24 * self.k
        font = skia.Font(self.semi_font, size)
        blob = skia.TextBlob(CREDIT, font)
        width = font.measureText(CREDIT)
        surf = skia.Surface(self.width, self.height)
        with surf as c:
            c.clear(skia.ColorBLACK)
            c.drawTextBlob(blob, self.width - 44 * self.k - width, self.height - 40 * self.k,
                           skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
        self.credit = surf.toarray(colorType=skia.kRGBA_8888_ColorType)[..., 0].astype(np.float32) / 255

    def _credit(self, rgb, t):
        a = clamp01((t - 0.3) / 0.3) * (1 - ease_in_out(span(t, *T_OUT)))
        if a <= 0:
            return rgb
        ys, xs = np.nonzero(self.credit > 0)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        region = rgb[y0:y1, x0:x1].astype(np.float32)
        lum = region @ np.array([0.299, 0.587, 0.114], np.float32)
        ink = np.where(lum < 128, 255.0, 0.0)[..., None]      # koyu zeminde beyaz, açıkta siyah
        m = (self.credit[y0:y1, x0:x1] * a)[..., None]
        out = rgb.copy()
        out[y0:y1, x0:x1] = (region * (1 - m) + ink * m).astype(np.uint8)
        return out

    def samples(self, t):
        if T_CHAR1[0] <= t < T_SWEEP[1]:
            return 5
        if t < T_GLITCH[0]:
            return 4
        return 2

    def render(self, t):
        n = self.samples(t)
        acc = np.zeros((self.height, self.width, 3), np.float32)
        for j in range(n):
            tj = t + ((j + 0.5) / n - 0.5) * 0.5 / self.fps
            with self.surface as c:
                self.draw(c, tj)
            acc += self.to_linear[self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]]
        rgb = (np.power(np.clip(acc / n, 0, 1), 1 / 2.2) * 255 + 0.5).astype(np.uint8)
        return self._post(rgb, t)
