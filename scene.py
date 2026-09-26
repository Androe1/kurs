"""Androe Studio intro animasyonu - görsel sahne.

Akış (saniye):
  0.12  Simsiyah ekranın derinliklerinden beyaz, 3B eğik kare ikon dönerek gelir.
  0.72  İkon yerine oturur: parlama, eğik kare şok dalgası, küçük parçacıklar.
  0.90  İkon küçülüp yuvarlanarak sağa gider; arkasından ANDROE çıkar.
  1.72  İkon sola döner: ANDROE'yi yutar, arkasından STUDIO çıkar.
  2.56  İkon yeniden sağa gider: STUDIO'yu iter, solundan ANDROE çıkar
        ve logo "ANDROE [ikon] STUDIO" olarak oturur.
  3.30  Logonun üzerinden bir ışık geçer.
  4.35  Her şey yumuşakça kararır; 5.0'da ekran tamamen siyahtır.

Yazılar ikonun "arkasından" çıkar: bir kelime yalnızca ikonun sol (ya da
sağ) kenarının dışında görünür, bu yüzden ikon hareket ettikçe kelimeler
onun altından kayarak ortaya çıkar veya içine girip kaybolur.

Her şey 1920x1080'lik tasarım alanında tanımlıdır; başka bir çözünürlükte
render edilince sahne orantılı ölçeklenir.
"""
import math
from pathlib import Path

import numpy as np
import skia

FONTS = Path(__file__).resolve().parent / "fonts"

# Tasarım alanı ve kamera
W, H = 1920, 1080
CX, CY = W / 2, H / 2
FOCAL = 1500.0          # z=0 düzlemindeki nesneler birebir ölçekte görünür

# Zaman çizelgesi (saniye)
DURATION = 5.0
T_IN = (0.12, 0.72)                                      # ikon dönerek gelir, T_IN[1]'de oturur
T_MOVES = ((0.90, 1.42), (1.72, 2.28), (2.56, 3.10))     # sağa, sola, yeniden sağa
T_GLINT = (3.30, 3.80)
T_OUT = (4.35, 4.92)

# İkon: eğik kare, ortasında kare delik; beyaz ve kalınlıklı (3B)
ICON_TILT = math.radians(15)
ICON_HOLE = 0.196       # delik kenarı / dış kenar
ICON_DEPTH = 0.22       # kalınlık / dış kenar
ICON_BIG = 220.0        # açılıştaki kenar uzunluğu (px)
ICON_SMALL = 96.0       # yazıyla birlikteki kenar uzunluğu (px)
ROLLS = (math.pi, -2 * math.pi, math.pi)                 # hareket başına yuvarlanma
LEAN = math.radians(26)  # hareket ederken ikonun yana yatması
REST_YAW, REST_PITCH = 0.28, 0.16  # durağan hâlde hafif açılı durur (kalınlığı görünsün)
MASK = 0.3              # yazı, ikon merkezinden (kenar x MASK) uzakta görünmeye başlar

# Tipografi
FONT_SIZE, TRACK = 120.0, 0.04
GAP = 46.0              # ikon ile kelimeler arası boşluk

SHUTTER = 0.5           # hareket bulanıklığı: kare süresinin yarısı (180 derece)
BLOOM = ((14.0, 0.20), (46.0, 0.10))  # (bulanıklık, miktar) çiftleri

LIGHT = np.array([-0.35, -0.5, -0.8])
LIGHT /= np.linalg.norm(LIGHT)

WHITE = skia.Color4f(1, 1, 1, 1)


# ---------------------------------------------------------------- yumuşatmalar

def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_in_out_cubic(u):
    return 4 * u**3 if u < 0.5 else 1 - (2 - 2 * u) ** 3 / 2


def ease_in_out_sine(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)


def ease_out_cubic(u):
    return 1 - (1 - u) ** 3


def pulse(x, width):
    """Hızla yükselip yavaşça sönen tepe; x == width iken 1."""
    x = max(x, 0.0) / width
    return x * math.exp(1 - x)


def progress(t, span, ease=ease_in_out_cubic):
    a, b = span
    return ease(clamp01((t - a) / (b - a)))


# ---------------------------------------------------------------- 3B yardımcılar

def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def project(p):
    """3B noktalar (..., 3) -> ekran koordinatları (..., 2)."""
    k = FOCAL / (FOCAL + p[..., 2])
    return np.stack([CX + (p[..., 0] - CX) * k, CY + (p[..., 1] - CY) * k], -1)


def grey(v, a=1.0):
    v = min(max(float(v), 0.0), 1.0)
    return skia.Color4f(v, v, v, float(a))


def path_of(*contours):
    path = skia.Path()
    path.setFillType(skia.PathFillType.kEvenOdd)
    for points in contours:
        path.moveTo(*points[0])
        for p in points[1:]:
            path.lineTo(*p)
        path.close()
    return path


def _hull(points):
    """2B noktaların dış bükey zarfı (ikonun parlama halesi için)."""
    pts = sorted(map(tuple, points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _icon_faces():
    """İkonun yüzleri: (konturlar, normal). Ön/arka yüz delikli, 4 dış yan, 4 iç duvar."""
    outer = np.array([[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]])
    inner = outer * ICON_HOLE
    d = ICON_DEPTH / 2

    def at(points, z):
        return np.column_stack([points, np.full(len(points), z)])

    faces = [([at(outer, -d), at(inner, -d)], (0, 0, -1)),
             ([at(outer, d), at(inner, d)], (0, 0, 1))]
    sides = [(0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0)]   # üst, sağ, alt, sol
    for k, n in enumerate(sides):
        j = (k + 1) % 4
        for ring, sign in ((outer, 1), (inner, -1)):          # iç duvarlar deliğe bakar
            quad = np.array([[*ring[k], -d], [*ring[j], -d], [*ring[j], d], [*ring[k], d]])
            faces.append(([quad], tuple(sign * v for v in n)))
    return faces


ICON_FACES = _icon_faces()
_CAM = np.array([CX, CY, -FOCAL])


class Word:
    """Harf yolları; x=0 mürekkebin sol kenarı, y=0 taban çizgisi."""

    def __init__(self, font, text):
        glyphs = font.textToGlyphs(text)
        self.letters, x = [], 0.0
        for g, adv in zip(glyphs, font.getWidths(glyphs)):
            p = font.getPath(g)
            p.offset(x, 0)
            self.letters.append(p)
            x += adv + TRACK * FONT_SIZE
        left = min(p.computeTightBounds().left() for p in self.letters)
        for p in self.letters:
            p.offset(-left, 0)
        bounds = [p.computeTightBounds() for p in self.letters]
        self.edges = [(b.left(), b.right()) for b in bounds]
        self.width = max(r for _, r in self.edges)
        self.path = skia.Path()
        for p in self.letters:
            self.path.addPath(p)


# ---------------------------------------------------------------- sahne

class Scene:
    def __init__(self, width=1920, height=1080, fps=60, seed=11):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.to_linear = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)
        self._layout()
        self._build_particles(np.random.default_rng(seed))

    # ------------------------------------------------------------ yerleşim

    def _layout(self):
        font = skia.Font(skia.Typeface.MakeFromFile(str(FONTS / "Montserrat-Black.ttf")), FONT_SIZE)
        self.baseline = CY + font.getMetrics().fCapHeight / 2
        self.androe, self.studio = Word(font, "ANDROE"), Word(font, "STUDIO")
        wa, ws = self.androe.width, self.studio.width
        box = ICON_SMALL * (math.cos(ICON_TILT) + math.sin(ICON_TILT))  # eğik ikonun genişliği

        # Her hareketin sonunda grup ekranda ortalanır
        a1 = CX - (wa + GAP + box) / 2                   # ANDROE [ikon]
        x1 = a1 + wa + GAP + box / 2
        x2 = CX - (box + GAP + ws) / 2 + box / 2         # [ikon] STUDIO
        s2 = x2 + box / 2 + GAP
        a3 = CX - (wa + GAP + box + GAP + ws) / 2        # ANDROE [ikon] STUDIO
        x3 = a3 + wa + GAP + box / 2
        self.stops = [CX, x1, x2, x3]

        # Kelimelerin başlangıç kaymaları: başta tamamen ikonun "arkasında" kalsınlar
        r_big, r_small = MASK * ICON_BIG, MASK * ICON_SMALL
        self.a1 = (a1, max(CX - r_big - a1, 0) + 6)      # (son konum, başlangıç kayması)
        self.a1_back = max(x2 - r_small - a1, 0) + 6     # 2. harekette ikonun içine çekilir
        self.s2 = (s2, min(x1 + r_small - (s2 + ws) - 6, -40))
        self.a3 = (a3, max(x2 - r_small - a3, 0) + 6)
        self.final_box = (a3, x3 + (s2 - x2) + ws)

    def _build_particles(self, rng):
        """İkon yerine otururken kenarlarından saçılan küçük eğik kareler."""
        self.particles = []
        for _ in range(22):
            ang = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(260, 720)
            self.particles.append(dict(
                x=CX + math.cos(ang) * ICON_BIG * 0.55, y=CY + math.sin(ang) * ICON_BIG * 0.55,
                vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
                size=rng.uniform(5, 13), spin=rng.uniform(-400, 400),
                life=rng.uniform(0.45, 0.9)))

    # ------------------------------------------------------------ hareket

    def icon_pose(self, t):
        """İkonun (x, y, z, kenar, dönüş matrisi) değerleri."""
        x, size, roll, yaw, pitch = CX, ICON_BIG, 0.0, REST_YAW, REST_PITCH
        for k, span in enumerate(T_MOVES):
            if t <= span[0]:
                break
            u = clamp01((t - span[0]) / (span[1] - span[0]))
            e = ease_in_out_cubic(u)
            x0, x1 = self.stops[k], self.stops[k + 1]
            direction = 1 if x1 > x0 else -1
            x = x0 + (x1 - x0) * e
            roll += ROLLS[k] * e
            yaw -= direction * LEAN * math.sin(math.pi * u)
            pitch += 0.12 * math.sin(math.pi * u)
            if k == 0:
                size = ICON_BIG + (ICON_SMALL - ICON_BIG) * e
            settle = t - span[1]                         # durunca küçük yay salınımı
            if settle > 0:
                roll += direction * math.radians(7) * math.sin(2 * math.pi * 4.5 * settle) * math.exp(-settle / 0.09)
                size *= 1 + 0.06 * pulse(settle, 0.035)

        # Giriş: derinlikten iki tur dönerek gelir, yerine "tık" diye oturur
        e = progress(t, T_IN, ease_out_cubic)
        z = 9000 * (1 - e) ** 2
        yaw -= 4 * math.pi * (1 - e)
        pitch += 0.6 * (1 - e)
        size *= 1 + 0.08 * pulse(t - T_IN[1], 0.05)
        rot = rot_y(yaw) @ rot_x(pitch) @ rot_z(ICON_TILT + roll)
        return x, CY, z, size, rot

    def _icon_glow(self, t):
        """Oturma ve son duruş anlarında ikonun kısa parlaması."""
        return max(pulse(t - T_IN[1], 0.06), 0.8 * pulse(t - T_MOVES[2][1], 0.06))

    def word_states(self, t):
        """Görünen kelimeler: (kelime, sol kenar x, taraf); taraf -1 ikonun solu, +1 sağı."""
        e1, e2, e3 = (progress(t, span) for span in T_MOVES)
        states = []
        if T_MOVES[0][0] < t < T_MOVES[1][1]:
            left, shift = self.a1
            states.append((self.androe, left + shift * (1 - e1) + self.a1_back * e2, -1))
        if t > T_MOVES[1][0]:
            left, shift = self.s2
            states.append((self.studio, left + shift * (1 - e2) + (self.stops[3] - self.stops[2]) * e3, 1))
        if t > T_MOVES[2][0]:
            left, shift = self.a3
            states.append((self.androe, left + shift * (1 - e3), -1))
        return states

    # ------------------------------------------------------------ çizim

    def _icon_polygons(self, pose):
        """İkonun görünen yüzleri, uzaktan yakına: (ekran konturları, gölge, normal)."""
        x, y, z, size, rot = pose
        center = np.array([x, y, z])
        faces = []
        for contours, normal in ICON_FACES:
            n = rot @ np.array(normal, float)
            world = [center + size * c @ rot.T for c in contours]
            mid = world[0].mean(0)
            if np.dot(n, mid - _CAM) >= 0:
                continue
            shade = 0.5 + 0.65 * max(float(n @ LIGHT), 0.0)
            faces.append((mid[2], [project(w) for w in world], shade, n))
        faces.sort(key=lambda f: -f[0])
        return faces

    def _draw_icon(self, c, t, pose):
        glow = self._icon_glow(t)
        faces = self._icon_polygons(pose)
        if glow > 0.01:  # oturma anında etrafına yayılan hale
            hull = path_of(_hull(np.vstack([f[1][0] for f in faces])))
            c.drawPath(hull, skia.Paint(AntiAlias=True, Color4f=grey(1, 0.8 * glow),
                                        BlendMode=skia.BlendMode.kPlus,
                                        ImageFilter=skia.ImageFilters.Blur(24, 24)))
        for _, contours, shade, _ in faces:
            v = shade + (1 - shade) * glow
            # Yan yüzler kenar boşluğu kalmasın diye hafifçe taşırılır; delikli yüzler
            # düz doldurulur (kontur + dolgu, deliği de doldururdu)
            paint = skia.Paint(AntiAlias=True, Color4f=grey(v))
            if len(contours) == 1:
                paint.setStyle(skia.Paint.kStrokeAndFill_Style)
                paint.setStrokeWidth(0.8)
            else:  # ön/arka yüz: sol üstten sağ alta hafif ışık geçişi
                corners = contours[0]
                diag = corners.sum(1)
                a, b = corners[diag.argmin()], corners[diag.argmax()]
                paint.setShader(skia.GradientShader.MakeLinear(
                    [skia.Point(*a), skia.Point(*b)], [grey(v).toColor(), grey(v * 0.9 + 0.1 * glow).toColor()]))
            c.drawPath(path_of(*[k.tolist() for k in contours]), paint)

    def _draw_words(self, c, t, x, size):
        r = MASK * size
        paint = skia.Paint(AntiAlias=True, Color4f=WHITE)
        for word, left, side in self.word_states(t):
            c.save()
            if side < 0:
                c.clipRect(skia.Rect(-W, -H, x - r, 2 * H), skia.ClipOp.kIntersect, True)
            else:
                c.clipRect(skia.Rect(x + r, -H, 2 * W, 2 * H), skia.ClipOp.kIntersect, True)
            c.translate(left, self.baseline)
            c.drawPath(word.path, paint)
            c.restore()

    def _draw_landing(self, c, t):
        dt = t - T_IN[1]
        if dt < 0 or dt > 0.9:
            return
        flash = math.exp(-dt / 0.05)
        shader = skia.GradientShader.MakeRadial(
            skia.Point(CX, CY), 330,
            [grey(1, 0.85 * flash).toColor(), grey(1, 0.2 * flash).toColor(), grey(1, 0).toColor()],
            [0.0, 0.3, 1.0])
        c.drawCircle(CX, CY, 330, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kPlus))

        # İkonla aynı eğiklikte genişleyen, hızla sönen ince şok dalgası
        u = dt / 0.4
        if u <= 1:
            half = ICON_BIG * (0.62 + 0.9 * ease_out_cubic(u))
            paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                               StrokeWidth=5 * (1 - u) + 0.5, Color4f=grey(1, 0.5 * (1 - u) ** 2))
            c.save()
            c.translate(CX, CY)
            c.rotate(math.degrees(ICON_TILT))
            c.drawRect(skia.Rect(-half, -half, half, half), paint)
            c.restore()

        # Saçılan küçük kareler (sürtünmeyle yavaşlar, döner, söner)
        paint = skia.Paint(AntiAlias=True)
        for p in self.particles:
            if dt > p["life"]:
                continue
            u = dt / p["life"]
            travel = 0.22 * (1 - math.exp(-dt / 0.22))
            h = p["size"] * (1 - 0.6 * u) / 2
            paint.setColor4f(grey(1, 0.9 * (1 - u) ** 1.5))
            c.save()
            c.translate(p["x"] + p["vx"] * travel, p["y"] + p["vy"] * travel)
            c.rotate(math.degrees(ICON_TILT) + p["spin"] * dt)
            c.drawRect(skia.Rect(-h, -h, h, h), paint)
            c.restore()

    def _draw_final_ring(self, c, t, x):
        """Logo son yerine oturduğunda ikondan çıkan küçük halka."""
        u = (t - T_MOVES[2][1]) / 0.4
        if 0 <= u <= 1:
            half = ICON_SMALL * (0.6 + 0.45 * ease_out_cubic(u))
            c.save()
            c.translate(x, CY)
            c.rotate(math.degrees(ICON_TILT))
            c.drawRect(skia.Rect(-half, -half, half, half),
                       skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                  StrokeWidth=3.5 * (1 - u) + 0.5, Color4f=grey(1, 0.55 * (1 - u) ** 2)))
            c.restore()

    def _draw_glint(self, c, t, pose):
        """Logonun üzerinden soldan sağa geçen ışık (yazıya ve ikona yapışık parıltı)."""
        u = clamp01((t - T_GLINT[0]) / (T_GLINT[1] - T_GLINT[0]))
        if not 0 < u < 1:
            return
        left, right = self.final_box
        center = left - 120 + (right - left + 240) * ease_in_out_sine(u)
        box = skia.Rect(left - 150, CY - 200, right + 150, CY + 200)
        c.saveLayer(box, skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=0.6 * math.sin(math.pi * u),
                                    ImageFilter=skia.ImageFilters.Blur(10, 10)))
        white = skia.Paint(AntiAlias=True, Color4f=WHITE)
        for word, x, _ in self.word_states(t):
            c.save()
            c.translate(x, self.baseline)
            c.drawPath(word.path, white)
            c.restore()
        for _, contours, _, _ in self._icon_polygons(pose):
            c.drawPath(path_of(*[k.tolist() for k in contours]), white)
        n = np.array([math.cos(math.radians(20)), math.sin(math.radians(20))])  # eğik bant
        mid = np.array([center, CY])
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(*(mid - 75 * n)), skia.Point(*(mid + 75 * n))],
            [grey(1, 0).toColor(), grey(1, 1).toColor(), grey(1, 0).toColor()])
        c.drawRect(box, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kDstIn))
        c.restore()

    def draw(self, c, t):
        """Tek bir anı (t saniye) tuvale çizer."""
        c.clear(skia.ColorBLACK)
        if t >= T_OUT[1] or t < T_IN[0]:
            return
        c.save()
        c.scale(self.k, self.k)

        zoom = 1 + 0.03 * ease_in_out_sine(clamp01(t / DURATION))
        fade = 0.0
        if t > T_OUT[0]:
            fade = progress(t, T_OUT, ease_in_out_sine)
            zoom += 0.03 * fade
        dt = t - T_IN[1]
        shake = 7 * math.exp(-dt / 0.08) if dt >= 0 else 0.0
        c.translate(CX + shake * math.sin(2 * math.pi * 31 * dt + 0.3),
                    CY + shake * math.sin(2 * math.pi * 23 * dt + 1.7))
        c.scale(zoom, zoom)
        c.translate(-CX, -CY)

        if fade > 0:
            paint = skia.Paint(Alphaf=1 - fade)
            if fade > 0.02:
                paint.setImageFilter(skia.ImageFilters.Blur(7 * fade, 7 * fade))
            c.saveLayer(None, paint)

        pose = self.icon_pose(t)
        self._draw_final_ring(c, t, pose[0])
        self._draw_words(c, t, pose[0], pose[3])
        self._draw_icon(c, t, pose)
        self._draw_glint(c, t, pose)
        self._draw_landing(c, t)

        if fade > 0:
            c.restore()
        c.restore()

    # ------------------------------------------------------------ kare üretimi

    def samples(self, t):
        """Hareket bulanıklığı için bir karede kaç alt kare çizileceği."""
        if T_IN[0] - 0.05 < t < T_MOVES[2][1] + 0.3:
            return 8
        if T_OUT[0] < t < T_OUT[1]:
            return 2
        return 1

    def render(self, t):
        """t anındaki kareyi (yükseklik, genişlik, 3) uint8 RGB olarak döndürür."""
        n = self.samples(t)
        if n == 1:
            with self.surface as c:
                self.draw(c, t)
            rgb = self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]
        else:
            acc = np.zeros((self.height, self.width, 3), np.float32)
            for j in range(n):
                tj = t + ((j + 0.5) / n - 0.5) * SHUTTER / self.fps
                with self.surface as c:
                    self.draw(c, tj)
                acc += self.to_linear[self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]]
            rgb = (np.power(np.clip(acc / n, 0, 1), 1 / 2.2) * 255 + 0.5).astype(np.uint8)
        return self._bloom(rgb)

    def _bloom(self, rgb):
        if not rgb.any():
            return rgb
        rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
        img = skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType)
        with self.surface as c:
            c.clear(skia.ColorBLACK)
            c.drawImage(img, 0, 0)
            for sigma, amount in BLOOM:
                c.drawImage(img, 0, 0, skia.SamplingOptions(),
                            skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=amount,
                                       ImageFilter=skia.ImageFilters.Blur(sigma * self.k, sigma * self.k)))
        return self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].copy()

    # ------------------------------------------------------------ ses için olaylar

    def _letter_times(self, word_index, side, span):
        """Bir kelimenin harflerinin tamamen göründüğü anlar (harf sırasına göre)."""
        ts = np.arange(span[0], span[1] + 0.2, 0.001)
        times = [None] * 6
        for t in ts:
            states = [s for s in self.word_states(t) if s[2] == side]
            if not states:
                continue
            word, left, _ = states[word_index]
            x, _, _, size, _ = self.icon_pose(t)
            edge = x - MASK * size if side < 0 else x + MASK * size
            for i, (l, r) in enumerate(word.edges):
                shown = left + r <= edge if side < 0 else left + l >= edge
                if times[i] is None and shown:
                    times[i] = float(t)
        return times

    def events(self):
        """Ses tasarımının görüntüyle eşleşmesi için olay zamanları ve konumları."""
        spin_t = np.arange(T_IN[0], T_IN[1], 0.002)
        spin = []
        for t in spin_t:
            rot = self.icon_pose(t)[4]
            spin.append(abs(rot[2, 2]))             # ikon ekrana ne kadar dönük (0-1)
        words = [
            (self._letter_times(0, -1, T_MOVES[0]), 0),   # ANDROE, 1. hareket
            (self._letter_times(0, 1, T_MOVES[1]), 1),    # STUDIO, 2. hareket
            (self._letter_times(-1, -1, T_MOVES[2]), 2),  # ANDROE, 3. hareket
        ]
        letters = []
        for times, move in words:
            for i, t in enumerate(times):
                if t is None:
                    continue
                word, left, _ = [s for s in self.word_states(t) if s[2] == (1 if move == 1 else -1)][-1]
                l, r = word.edges[i]
                letters.append((t, i, (left + (l + r) / 2) / W))
        return dict(duration=DURATION, spin_in=T_IN, spin=(spin_t.tolist(), spin),
                    land=T_IN[1], moves=[(a, b, self.stops[k] / W, self.stops[k + 1] / W)
                                         for k, (a, b) in enumerate(T_MOVES)],
                    letters=letters, final=T_MOVES[2][1], glint=T_GLINT, out=T_OUT)

