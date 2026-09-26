"""Void Creations intro animasyonu - görsel sahne (referans videonun ilk 4 saniyesi).

Akış (saniye):
  0.36  Siyah ekranda silik bir teknik çizim zemini belirir: perspektifte
        daireler, yatay taralı eğik bantlar, artı / çarpı işaretleri ve uzun
        kılavuz çizgileri. Zemin yavaşça döner.
  0.40  Ekranın dışından çok hızlı gelen ince ışık çizgileri V logosunun
        kenarlarına ulaşır, köşelerde dönerek beş kopyanın konturunu çizer.
        Kopyalar 3B'de üst üste dizilidir; eğik bakıldığı için dikey bir
        sütun gibi görünürler.
  1.48  Kamera logoya döner, kopyalar tek logoda birleşir. Bu sırada öndeki
        kopya hızlanan aralıklarla dolu beyaz yanıp söner; zemin kararır.
  2.20  Logo dolar, küçülerek sola kayar ve VOID'in V'si olur: sağındaki
        "OID CREATIONS" harfleri önce ince kontur olarak, hemen ardından eğik
        bir dolgu cephesiyle soldan sağa belirir.
  3.47  Logodaki eğimle aynı açıda bir silme soldan sağa her şeyi siler.
  3.73  Ekran siyah kalır, ses söner.

Ekranda [V logosu]OID CREATIONS dışında yazı yoktur. Her şey 1920x1080
tasarım alanında tanımlıdır; başka bir çözünürlükte orantılı ölçeklenir.
"""
import math
from types import SimpleNamespace

import numpy as np
import skia

from scene import (CX, CY, FONTS, H, W, clamp01, ease_in_out_cubic, ease_in_out_sine, ease_out_cubic,
                   progress, rot_x, rot_y, rot_z)

DURATION = 4.4
FOCAL = 1500.0           # z=0 düzlemindeki nesneler birebir ölçekte görünür

# V logosu: iki dörtgen. Yükseklik 1, sınır kutusunun ortası (0, 0), y aşağı doğru.
# Köşeler logo görselinin kenarlarına alt piksel doğrulukla oturtulan doğrulardan bulundu.
LOGO = (
    ((-0.5157, -0.5), (-0.2090, -0.5), (0.1211, 0.5), (-0.1856, 0.5)),       # sol kol
    ((0.2090, -0.5), (0.5157, -0.5), (0.3067, 0.1332), (0.1569, -0.3206)),   # sağ kol
)
LOGO_PTS = tuple(np.array(p) for p in LOGO)
LOGO_ASPECT = 1.0314     # genişlik / yükseklik
SLANT = math.atan(0.3301)  # logodaki kolların eğimi (18.3°); yazı cepheleri ve silme de bu açıda

# Zaman çizelgesi (saniye)
T_BG_IN = (0.36, 0.64)   # zemin belirir
T_TURN = (1.48, 2.17)    # kamera logoya döner, kopyalar birleşir
# Birleşme ilerlemesi (0 -> 1): referanstaki sütunun yüksekliğinden kare kare ölçüldü
COLLAPSE = ((1.48, 0.0), (1.57, 0.035), (1.63, 0.08), (1.70, 0.16), (1.77, 0.31), (1.83, 0.52),
            (1.90, 0.68), (1.97, 0.78), (2.03, 0.83), (2.10, 0.89), (2.17, 1.0))
T_BG_OUT = (1.50, 1.95)  # zemin kararır
# Öndeki kopyanın dolu yanıp söndüğü aralıklar (referansla aynı kareler; aralar hızlanır)
FLASHES = ((1.525, 1.558), (1.658, 1.725), (1.825, 1.858), (1.925, 1.958), (2.058, 2.092), (2.125, 2.158))
T_SOLID = 2.195          # logo bundan sonra hep dolu
T_LOCK = (2.17, 2.98)    # logo küçülüp sola kayar, grup ortalanır
T_REVEAL = (2.19, 2.78)  # kontur cephesi yazının üzerinden geçer
FILL_LAG = 0.075         # dolgu cephesi konturun bu kadar arkasından gelir
T_WIPE = (3.47, 3.73)    # eğik silme

# Işık çizgileri ve kopya yığını
LINE = 3.2               # kontur / ışık çizgisi kalınlığı (px)
TEXT_LINE = 2.6          # harf konturu kalınlığı (px)
COPIES = 5
STACK_SIZE = 280.0       # kopyaların logo yüksekliği (px)
STACK_GAP = 132.0        # kopyalar arası derinlik (px)
STACK_Y = -22.0          # sütunun ekran merkezine göre yüksekliği
TILT = (math.radians(58), math.radians(55))   # kopyaların eğikliği: başta / dönüşten hemen önce
SPIN = (math.radians(-14), math.radians(-6))  # logo düzlemindeki dönüş
ROLL = (math.radians(3), math.radians(0))     # ekran düzlemindeki dönüş
YAW_SWING = math.radians(16)                   # dönüş sırasında yana salınım
LOGO_BIG = 136.0         # kopyalar birleştiğinde logo yüksekliği (px)

# Her ışık çizgisi bir kopyanın bir kolunu çizer: (kopya, kol, başlangıç, gelmesi istenen yön).
# Yön ekran düzleminde bir ipucudur; çizgi bu yöne en yakın kenarın uzantısından gelir.
# Kopya 4 en üstte (en arkada), 0 en altta (en önde).
SNAKES = (
    (4, 0, 0.39, (-0.5, -1.0)),   # sağ alttan
    (4, 1, 0.45, (-0.5, 1.0)),    # sağ üstten
    (3, 0, 0.51, (0.5, 1.0)),     # sol üstten
    (3, 1, 0.56, (0.5, -1.0)),    # sol alttan
    (2, 1, 0.62, (-0.5, 1.0)),    # sağ üstten
    (2, 0, 0.67, (-0.5, -1.0)),   # sağ alttan
    (1, 0, 0.73, (0.5, 1.0)),     # sol üstten
    (1, 1, 0.78, (0.5, -1.0)),    # sol alttan
    (0, 1, 0.84, (-0.5, 1.0)),    # sağ üstten
    (0, 0, 0.89, (-0.5, -1.0)),   # sağ alttan
)
SNAKE_SPEED = 6500.0     # px/s
SNAKE_TAIL = 800.0       # kenara ulaşmadan önceki görünür çizgi uzunluğu (px)

# Logo + yazı (son hâl): logo VOID'in V'si, ardından "OID CREATIONS". Yerleşim orijinal yazı
# görselinden ölçüldü; birim büyük harf yüksekliği (= logo yüksekliği), x = 0 logonun sol kenarı,
# y = 0 taban çizgisi. Harfler Inter Black (değer: harfin sol mürekkep kenarı); N görseldeki özel
# çizim: düz kenarlı bir çokgen (Inter'in N'sinden dar, eğrisiz).
CAP = 100.0              # büyük harf yüksekliği (px)
LETTERS = (
    ("O", 1.0595), ("I", 2.1569), ("D", 2.5571), ("C", 3.8343), ("R", 4.8942), ("E", 5.8121),
    ("A", 6.6368), ("T", 7.6066), ("I", 8.5768), ("O", 8.9730), ("S", 11.0378),
)
N_POLY = ((10.0708, -1.0), (10.0708, 0.0), (10.3411, 0.0), (10.3411, -0.5354), (10.7080, 0.0),
          (10.9346, 0.0), (10.9346, -1.0), (10.6629, -1.0), (10.6629, -0.4667), (10.3016, -1.0))

# Zemin: perspektifteki bir düzlem (u, v px). Değerler referanstaki yerleşime göre seçildi.
RINGS = (  # (u, v, yarıçap, kendi eğimi, kendi dönüşü) - açılar derece
    (-650, -330, 250, 0, 0), (-470, 170, 135, 25, 10), (560, 240, 390, -12, 0),
    (840, -40, 250, 22, -30), (430, 540, 120, 0, 0), (-270, 580, 330, 15, 60),
    (130, -600, 170, -20, 20), (-930, 430, 200, 0, 0),
)
RIBBONS = (  # yatay taralı eğik bantlar: (başlangıç u, v, açı, uzunluk, genişlik)
    (-1080, -1050, 47, 2900, 330), (-1500, 60, 47, 1500, 220), (380, 250, 47, 1400, 200),
)
HATCH_STEP = 24.0
CROSS_GRIDS = (  # (u0, v0, sütun, satır, çarpı mı)
    (-830, 170, 7, 5, False), (540, -270, 6, 4, True), (-560, -540, 4, 3, True),
)
CROSS_STEP, CROSS_SIZE = 50.0, 9.0
GUIDES = (  # ekran düzleminde uzun kılavuz çizgileri: (açı, merkezden uzaklık)
    (-28, -260), (62, -700), (-74, 520), (30, 210), (-35, 330), (80, 650), (12, -430),
)

SHUTTER = 0.5            # hareket bulanıklığı: kare süresinin yarısı
BLOOM = ((5.0, 0.30), (18.0, 0.24), (55.0, 0.12))  # (bulanıklık, miktar)

WHITE = (1.0, 1.0, 1.0)


def lerp(a, b, u):
    return a + (b - a) * u


def ease_out_soft(u):
    return 1 - (1 - u) ** 1.6


def monotone(t, table):
    """(zaman, değer) çiftlerinden taşmayan (monoton) yumuşak eğri - Fritsch-Carlson."""
    ts, vs = np.array(table, float).T
    if t <= ts[0]:
        return float(vs[0])
    if t >= ts[-1]:
        return float(vs[-1])
    h = np.diff(ts)
    s = np.diff(vs) / h
    m = np.concatenate([[s[0]], (s[:-1] + s[1:]) / 2, [s[-1]]])
    for i, si in enumerate(s):
        if si == 0:
            m[i] = m[i + 1] = 0.0
        else:
            a, b = m[i] / si, m[i + 1] / si
            r = a * a + b * b
            if r > 9:
                m[i], m[i + 1] = 3 * a / math.sqrt(r) * si, 3 * b / math.sqrt(r) * si
    i = int(np.searchsorted(ts, t) - 1)
    u = (t - ts[i]) / h[i]
    h00, h10 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u
    h01, h11 = -2 * u**3 + 3 * u**2, u**3 - u**2
    return float(h00 * vs[i] + h10 * h[i] * m[i] + h01 * vs[i + 1] + h11 * h[i] * m[i + 1])


def stroke(width, alpha=1.0):
    return skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                      StrokeJoin=skia.Paint.kMiter_Join, StrokeMiter=6, Color4f=skia.Color4f(*WHITE, alpha))


def fill(alpha=1.0):
    return skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*WHITE, alpha))


def polyline(points, closed=False):
    path = skia.Path()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    if closed:
        path.close()
    return path


def trim(points, s, e):
    """Kırık çizginin yay uzunluğuna göre [s, e] arasındaki parçası (noktalar)."""
    seg = np.diff(points, axis=0)
    lengths = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(lengths)])
    s, e = max(s, 0.0), min(e, cum[-1])
    if e - s < 0.5:
        return None

    def at(d):
        i = int(min(np.searchsorted(cum, d, side="right") - 1, len(lengths) - 1))
        f = (d - cum[i]) / lengths[i] if lengths[i] > 0 else 0.0
        return points[i] + seg[i] * f, i

    p0, i0 = at(s)
    p1, i1 = at(e)
    return [p0, *points[i0 + 1:i1 + 1], p1]


def exit_distance(p, d):
    """p noktasından d yönünde gidince ekrandan çıkana kadarki uzaklık."""
    best = 4000.0
    for axis, size in ((0, W), (1, H)):
        if d[axis] > 1e-6:
            best = min(best, (size - p[axis]) / d[axis])
        elif d[axis] < -1e-6:
            best = min(best, -p[axis] / d[axis])
    return max(best, 0.0)


def front_region(x):
    """Eğik cephenin ("/", logodaki açıyla) solundaki bölge; x cephenin CY hizasındaki yeri."""
    tan = math.tan(SLANT)
    top, bot = CY - 900, CY + 900
    xt, xb = x + (CY - top) * tan, x + (CY - bot) * tan
    return polyline([(xt, top), (xb, bot), (-4000, bot), (-4000, top)], closed=True)


def box_blur(a, r, axis):
    """Yarıçapı r olan kutu bulanıklığı (kenarların dışı siyah), kümülatif toplamla."""
    if r < 1:
        return a
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=np.float32)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def gaussian(a, sigma):
    """Üç kutu bulanıklığıyla yaklaşık Gauss bulanıklığı."""
    r = max(int(round((math.sqrt(4 * sigma * sigma + 1) - 1) / 2)), 1)
    for _ in range(3):
        a = box_blur(box_blur(a, r, 0), r, 1)
    return a


def upsample2(a):
    """İki kat büyütme (çift doğrusal)."""
    def along(x, axis):
        prev = np.concatenate([np.take(x, [0], axis), np.take(x, np.arange(x.shape[axis] - 1), axis)], axis)
        nxt = np.concatenate([np.take(x, np.arange(1, x.shape[axis]), axis), np.take(x, [-1], axis)], axis)
        even, odd = 0.75 * x + 0.25 * prev, 0.75 * x + 0.25 * nxt
        return np.stack([even, odd], axis + 1).reshape(
            *x.shape[:axis], 2 * x.shape[axis], *x.shape[axis + 1:])
    return along(along(a, 0), 1)


# ---------------------------------------------------------------- zemin

class Backdrop:
    """Perspektifte duran silik teknik çizim düzlemi; kamerayla birlikte döner."""

    def __init__(self):
        self.rings = []
        for u, v, r, tilt, spin in RINGS:
            a = np.linspace(0, 2 * np.pi, 121)
            circle = np.column_stack([r * np.cos(a), r * np.sin(a), np.zeros_like(a)])
            local = rot_z(math.radians(spin)) @ rot_x(math.radians(tilt))
            self.rings.append(circle @ local.T + [u, v, 0])

        segs, alphas = [], []
        for u0, v0, ang, length, width in RIBBONS:
            d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
            n = np.array([-d[1], d[0]])
            a0 = np.array([u0, v0])
            quad = [a0 - n * width / 2, a0 + d * length - n * width / 2,
                    a0 + d * length + n * width / 2, a0 + n * width / 2]
            ys = [q[1] for q in quad]
            for y in np.arange(math.ceil(min(ys) / HATCH_STEP) * HATCH_STEP, max(ys), HATCH_STEP):
                xs = []
                for p, q in zip(quad, quad[1:] + quad[:1]):
                    if (p[1] - y) * (q[1] - y) < 0:
                        xs.append(p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1]))
                if len(xs) >= 2:
                    x0, x1 = min(xs), max(xs)
                    mid = (np.array([(x0 + x1) / 2, y]) - a0) @ d / length
                    segs.append([[x0, y, 0], [x1, y, 0]])
                    alphas.append(math.sin(math.pi * clamp01(mid)) ** 0.7)   # bant uçlarında söner
        self.hatch = np.array(segs, float)
        self.hatch_alpha = np.array(alphas)

        crosses = []
        for u0, v0, cols, rows, diagonal in CROSS_GRIDS:
            for i in range(cols):
                for j in range(rows):
                    x, y, s = u0 + i * CROSS_STEP, v0 + j * CROSS_STEP, CROSS_SIZE
                    if diagonal:
                        crosses += [[[x - s, y - s, 0], [x + s, y + s, 0]], [[x - s, y + s, 0], [x + s, y - s, 0]]]
                    else:
                        crosses += [[[x - s, y, 0], [x + s, y, 0]], [[x, y - s, 0], [x, y + s, 0]]]
        self.crosses = np.array(crosses, float)

    @staticmethod
    def pose(t):
        d = ease_in_out_sine(clamp01((t - 0.3) / (T_TURN[0] - 0.3)))
        u = progress(t, T_TURN, ease_in_out_cubic)
        tilt = math.radians(lerp(lerp(-48, -44, d), -20, u))     # zemin: üstü uzakta
        spin = math.radians(lerp(lerp(-5, 1, d), 18, u))
        roll = math.radians(lerp(lerp(-3, 1.5, d), -8, u))
        rot = rot_z(roll) @ rot_x(tilt) @ rot_z(spin)
        offset = np.array([lerp(lerp(30, -25, d), -80, u), lerp(10, -10, d), lerp(lerp(260, 200, d), -60, u)])
        return rot, offset, roll

    @staticmethod
    def project(points, rot, offset):
        q = points @ rot.T + offset
        s = FOCAL / np.maximum(FOCAL + q[..., 2], 60.0)
        return np.stack([CX + q[..., 0] * s, CY + q[..., 1] * s], -1)

    def draw(self, c, t, alpha):
        if alpha <= 0.003:
            return
        rot, offset, roll = self.pose(t)
        ring_paint = stroke(1.8, 0.24 * alpha)
        for ring in self.rings:
            c.drawPath(polyline(self.project(ring, rot, offset)), ring_paint)

        hatch = self.project(self.hatch, rot, offset)
        for (p, q), a in zip(hatch, self.hatch_alpha):
            if a > 0.02:
                c.drawLine(*p, *q, stroke(3.0, 0.17 * alpha * a))

        cross_paint = stroke(2.2, 0.3 * alpha)
        path = skia.Path()
        for p, q in self.project(self.crosses, rot, offset):
            path.moveTo(*p)
            path.lineTo(*q)
        c.drawPath(path, cross_paint)

        guide_paint = stroke(1.5, 0.2 * alpha)
        drift = np.array([offset[0] * 0.6, offset[1] * 0.6])
        for ang, dist in GUIDES:
            a = math.radians(ang) + roll * 1.4
            d = np.array([math.cos(a), math.sin(a)])
            n = np.array([-d[1], d[0]])
            p = np.array([CX, CY]) + n * dist + drift
            c.drawLine(*(p - d * 2600), *(p + d * 2600), guide_paint)


# ---------------------------------------------------------------- logo + yazı

class Lockup:
    """Son hâl: [V logosu]OID CREATIONS, ekranın ortasında. Koordinatlar 1920x1080 alanında.

    Logo VOID'in V'sidir; harfler ve aralıklar orijinal yazı görselindeki gibidir
    (LETTERS, N_POLY). Logo yüksekliği büyük harf yüksekliğine eşittir.
    """

    def __init__(self):
        tf = skia.Typeface.MakeFromFile(str(FONTS / "Inter-Black.ttf"))
        size = 100 * CAP / skia.Font(tf, 100).getMetrics().fCapHeight
        font = skia.Font(tf, size)

        # x = 0 logonun sol kenarı; y = 0 taban çizgisi
        self.text = skia.Path()
        centers = []
        for ch, x in LETTERS:
            p = font.getPath(font.textToGlyphs(ch)[0])
            b = p.computeTightBounds()
            p.offset(x * CAP - b.left(), 0)
            self.text.addPath(p)
            centers.append(x * CAP + b.width() / 2)
        n_poly = np.array(N_POLY) * CAP
        self.text.addPath(polyline(n_poly, closed=True))
        centers.append(n_poly[:, 0].mean())
        ink = self.text.computeTightBounds()

        self.x0 = CX - ink.right() / 2
        self.x1 = self.x0 + ink.right()
        self.logo_cx = self.x0 + LOGO_ASPECT * CAP / 2
        self.text_x0 = self.x0 + ink.left()
        self.letter_x = sorted(self.x0 + c for c in centers)   # harflerin ortaları (ses için)
        self.text.offset(self.x0, CY + CAP / 2)
        self.logo = skia.Path()
        for poly in LOGO_PTS:
            self.logo.addPath(polyline(poly * CAP + [self.logo_cx, CY], closed=True))
        self.half_slant = CAP / 2 * math.tan(SLANT)

    def view(self, t):
        """Grubun o anki yakınlaştırması ve odak noktası (x)."""
        u = progress(t, T_LOCK, ease_out_cubic)
        return lerp(LOGO_BIG / CAP, 1.0, u), lerp(self.logo_cx, CX, u)

    def fronts(self, t):
        """Kontur ve dolgu cephelerinin CY hizasındaki x konumları."""
        a = self.text_x0 - self.half_slant - 3
        b = self.x1 + self.half_slant + 3

        def at(tt):
            return lerp(a, b, progress(tt, T_REVEAL, ease_out_soft))
        return at(t), at(t - FILL_LAG)

    def wipe(self, t):
        a = self.x0 - self.half_slant - 12
        b = self.x1 + self.half_slant + 12
        return lerp(a, b, progress(t, T_WIPE, ease_in_out_sine))


# ---------------------------------------------------------------- sahne

class VoidScene:
    duration = DURATION

    def __init__(self, width=1920, height=1080, fps=60):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.to_linear = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)
        # doğrusal -> sRGB tablosu karekök alanında: koyu tonlarda da ince basamaklar
        self.to_srgb = (np.power(np.arange(4096) / 4095, 2 / 2.2) * 255 + 0.5).astype(np.uint8)
        self.glow = self._glow_sprite()
        self.rng = np.random.default_rng(3)
        self.backdrop = Backdrop()
        self.lockup = Lockup()
        self._plan_snakes()

    # ------------------------------------------------------------ kopya yığını

    @staticmethod
    def stack_state(t):
        d = ease_in_out_sine(clamp01((t - 0.3) / (T_TURN[0] - 0.3)))   # dönüşten önce yavaş kayma
        u = monotone(t, COLLAPSE)
        ug = u**1.8              # kopyalar arası mesafe biraz geç kapanır: sonda iç içe konturlar
        return SimpleNamespace(
            tilt=lerp(lerp(*TILT, d), 0.0, u),
            spin=lerp(lerp(*SPIN, d), 0.0, u),
            roll=lerp(lerp(*ROLL, d), 0.0, u),
            yaw=YAW_SWING * math.sin(math.pi * u),
            size=lerp(STACK_SIZE * lerp(1.0, 1.05, d), LOGO_BIG, u),
            gap=lerp(STACK_GAP * lerp(1.0, 0.94, d), 0.0, ug),
            y=lerp(STACK_Y, 0.0, u))

    @staticmethod
    def stack_points(st):
        """Kopyaların ekran koordinatları: [kopya][kol] -> (4, 2)."""
        rot = rot_z(st.roll) @ rot_y(st.yaw) @ rot_x(st.tilt) @ rot_z(st.spin)
        out = []
        for k in range(COPIES):
            z = (k - (COPIES - 1) / 2) * st.gap
            arms = []
            for poly in LOGO_PTS:
                p = np.column_stack([poly * st.size, np.full(len(poly), z)]) @ rot.T + [0, st.y, 0]
                s = FOCAL / (FOCAL + p[:, 2])
                arms.append(np.column_stack([CX + p[:, 0] * s, CY + p[:, 1] * s]))
            out.append(arms)
        return out

    def _plan_snakes(self):
        """Her ışık çizgisi için giriş kenarını, yönünü ve ekran dışından gelen uzantıyı seç."""
        self.snakes = []
        for copy, arm, t0, want in SNAKES:
            pts = self.stack_points(self.stack_state(t0))[copy][arm]
            want = np.array(want) / np.hypot(*want)
            n, best = len(pts), None
            for i in range(n):
                for step in (1, -1):
                    d = pts[(i + step) % n] - pts[i]
                    length = np.hypot(*d)
                    if length > 25 and abs(d[1]) > 0.35 * length:   # yatay kenarlardan gelmesin
                        score = d @ want / length
                        if best is None or score > best[0]:
                            best = (score, i, step, d / length)
            _, i, step, d = best
            sn = SimpleNamespace(copy=copy, arm=arm, t0=t0, start=i, step=step,
                                 lead=exit_distance(pts[i], -d) + 80)
            path = self.snake_path(sn, pts)
            sn.total = float(np.hypot(*np.diff(path, axis=0).T).sum())   # giriş + kontur uzunluğu
            sn.entry_x = float(np.clip(path[0][0], 0, W))                # ekrana girdiği yer
            self.snakes.append(sn)

    def snake_path(self, sn, pts):
        n = len(pts)
        order = [pts[(sn.start + sn.step * m) % n] for m in range(n)]
        d = order[1] - order[0]
        d = d / np.hypot(*d)
        return np.array([order[0] - d * sn.lead, *order, order[0]])

    def _draw_stack(self, c, t, tf):
        st = self.stack_state(t)
        pts = self.stack_points(st)
        line = stroke(LINE)
        done = [[False, False] for _ in range(COPIES)]
        for sn in self.snakes:
            e = SNAKE_SPEED * (t - sn.t0)
            if e <= 0:
                continue
            path = self.snake_path(sn, pts[sn.copy][sn.arm])
            total = np.hypot(*np.diff(path, axis=0).T).sum()
            if e >= total:
                done[sn.copy][sn.arm] = True
                continue
            part = trim(path, min(max(e - SNAKE_TAIL, 0.0), sn.lead), e)
            if part is not None:
                c.drawPath(polyline(part), line)
        for k in range(COPIES):
            for j in range(2):
                if done[k][j]:
                    c.drawPath(polyline(pts[k][j], closed=True), line)
        if self.flash_on(tf):
            front = skia.Path()
            for arm in pts[0]:
                front.addPath(polyline(arm, closed=True))
            c.drawPath(front, fill())

    @staticmethod
    def flash_on(t):
        return any(a <= t < b for a, b in FLASHES)

    # ------------------------------------------------------------ logo + yazı

    def _draw_lockup(self, c, t, tf):
        lk = self.lockup
        zoom, focus = lk.view(t)
        c.save()
        c.translate(CX, CY)
        c.scale(zoom, zoom)
        c.translate(-focus, -CY)
        if t > T_WIPE[0]:
            c.clipPath(front_region(lk.wipe(t)), skia.ClipOp.kDifference, True)

        if tf >= T_SOLID:
            c.drawPath(lk.logo, fill())
        else:
            c.drawPath(lk.logo, stroke(LINE / zoom))

        xo, xf = lk.fronts(t)
        c.save()
        c.clipPath(front_region(xo), skia.ClipOp.kIntersect, True)
        c.clipPath(front_region(xf), skia.ClipOp.kDifference, True)
        c.drawPath(lk.text, stroke(TEXT_LINE / zoom))
        c.restore()
        c.save()
        c.clipPath(front_region(xf), skia.ClipOp.kIntersect, True)
        c.drawPath(lk.text, fill())
        c.restore()
        c.restore()

    # ------------------------------------------------------------ ışık

    def _draw_backlight(self, c, t, tf):
        """Sütunun arkasındaki yumuşak ışık; yanıp sönmelerde parlar."""
        a = progress(t, (0.45, 1.05), ease_in_out_sine) * (1 - progress(t, (1.65, 1.98), ease_in_out_sine))
        if self.flash_on(tf):
            a += 0.5
        if a <= 0.003:
            return
        y = CY + self.stack_state(t).y
        c.drawImageRect(self.glow, skia.Rect(CX - 600, y - 600, CX + 600, y + 600),
                        skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=min(a / 2, 1.0)))

    @staticmethod
    def _glow_sprite():
        """Arka ışık için önceden çizilmiş yumuşak daire (tam ekran gradyandan çok daha hızlı)."""
        surf = skia.Surface(256, 256)
        with surf as c:
            c.clear(skia.ColorTRANSPARENT)
            shader = skia.GradientShader.MakeRadial(
                (128, 128), 128, [skia.Color4f(1, 1, 1, 0.26), skia.Color4f(1, 1, 1, 0.09),
                                  skia.Color4f(1, 1, 1, 0)], [0.0, 0.4, 1.0])
            c.drawRect(skia.Rect(0, 0, 256, 256), skia.Paint(Shader=shader))
        return surf.makeImageSnapshot()

    # ------------------------------------------------------------ kare üretimi

    def draw(self, c, t, tf):
        c.clear(skia.ColorBLACK)
        c.save()
        c.scale(self.k, self.k)
        bg = progress(t, T_BG_IN, ease_in_out_sine) * (1 - progress(t, T_BG_OUT, ease_in_out_sine))
        self.backdrop.draw(c, t, bg)
        self._draw_backlight(c, t, tf)
        if t < T_TURN[1]:
            self._draw_stack(c, t, tf)
        else:
            self._draw_lockup(c, t, tf)
        c.restore()

    def samples(self, t):
        """Hareket bulanıklığı için bir karede kaç alt kare çizileceği."""
        if 0.36 < t < 1.35:
            return 6
        if 1.45 < t < T_TURN[1]:
            return 8
        return 1                 # yazı evresi keskin: ince harf konturları bulanıklıkla yayılmasın

    def render(self, t):
        """t anındaki kareyi (yükseklik, genişlik, 3) uint8 RGB olarak döndürür.

        Sahne gri tonlamalıdır (siyah üzerine beyaz), bu yüzden alt kareler tek
        kanalda, doğrusal ışıkta toplanır.
        """
        n = self.samples(t)
        if n == 1:
            with self.surface as c:
                self.draw(c, t, t)
            grey = self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., 0].copy()
        else:
            acc = np.zeros((self.height, self.width), np.float32)
            for j in range(n):
                tj = t + ((j + 0.5) / n - 0.5) * SHUTTER / self.fps
                with self.surface as c:
                    self.draw(c, tj, t)   # yanıp sönme karenin kendi zamanına bağlı: keskin kalır
                acc += np.take(self.to_linear, self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., 0])
            grey = np.take(self.to_srgb, (np.sqrt(np.minimum(acc / n, 1.0)) * 4095 + 0.5).astype(np.uint16))
        return self._bloom(grey)

    def _bloom(self, grey):
        """Işık halesi: bulanık kopyalar yarım çözünürlükte, ondalık hassasiyetle hesaplanır
        ve tek seferde 8 bite çevrilir (koyu gradyanlarda bantlaşma olmasın diye hafif titreşimle)."""
        if not grey.any():
            return np.repeat(grey[..., None], 3, -1)
        g = grey.astype(np.float32)
        h, w = g.shape
        small = np.pad(g, ((0, h % 2), (0, w % 2)), mode="edge")
        small = small.reshape(small.shape[0] // 2, 2, small.shape[1] // 2, 2).mean((1, 3))
        halo = np.zeros_like(small)
        for sigma, amount in BLOOM:
            halo += amount * gaussian(small, sigma * self.k / 2)
        out = g + upsample2(halo)[:h, :w]
        out += self.rng.random(out.shape, np.float32) - 0.5
        out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
        return np.repeat(out[..., None], 3, -1)

    # ------------------------------------------------------------ ses için olaylar

    def events(self):
        """Ses için olaylar: zamanlar (saniye) ve ekrandaki yatay konumlar (-1 sol .. 1 sağ).

        Anlık olaylar (yanıp sönme, logonun dolması) göründükleri ilk karenin zamanına
        yuvarlanır; ses görüntüyle aynı karede başlar.
        """
        lk = self.lockup

        def frame(t):
            return math.ceil(t * self.fps - 1e-6) / self.fps

        def pan(t, x):
            zoom, focus = lk.view(t)
            return float(np.clip(2 * (CX + zoom * (x - focus)) / W - 1, -1, 1))

        snakes = [dict(t0=sn.t0, arrive=sn.t0 + sn.lead / SNAKE_SPEED, done=sn.t0 + sn.total / SNAKE_SPEED,
                       pan=2 * sn.entry_x / W - 1) for sn in self.snakes]
        ts = np.arange(T_REVEAL[0], T_REVEAL[1] + FILL_LAG + 0.002, 0.001)
        fill = np.array([lk.fronts(t)[1] for t in ts])
        letters = []
        for x in lk.letter_x:                  # dolgu cephesi harfin ortasından geçtiği an
            t = float(ts[np.argmax(fill >= x)])
            letters.append((t, pan(t, x)))
        return dict(duration=DURATION, snakes=snakes, turn=T_TURN,
                    flashes=[(frame(a), frame(b)) for a, b in FLASHES], solid=frame(T_SOLID),
                    reveal=[(float(t), pan(t, lk.fronts(t)[0])) for t in np.linspace(*T_REVEAL, 24)],
                    letters=letters,
                    wipe=[(float(t), pan(t, lk.wipe(t))) for t in np.linspace(*T_WIPE, 16)])
