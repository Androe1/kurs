"""Androe Studio intro animasyonu - görsel sahne.

Akış (saniye):
  0.12  Simsiyah ekranın derinliklerinden beyaz, 3B eğik kare ikon dönerek gelir.
  0.72  İkon yerine oturur: parlama, eğik kare şok dalgası, küçük parçacıklar.
  0.85  İkon küçülüp yuvarlanarak sağa gider; arkasından ANDROE çıkar.
  1.58  İkon sola döner: ANDROE'yi yutar, arkasından STUDIO çıkar.
  2.33  İkon yeniden sağa gider: STUDIO'yu iter, solundan ANDROE çıkar.
  2.92  İkon çevresindeki ışığı içine çeker (yazılar gümüşe söner), kenarı
        bize dönecek şekilde döner, ince bir ışık çizgisine dönüşür ve tek
        bir ışık noktasına çöker. Kelimeler süzülerek birleşir.
  3.28  Işık noktasından iki yana yayılan ışık dalgaları geçtikleri yeri
        bembeyaz yapar: ekranda yalnızca "ANDROE STUDIO" kalır.
  4.40  Her şey yumuşakça kararır; 5.0'da ekran tamamen siyahtır.

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
T_MOVES = ((0.85, 1.33), (1.58, 2.08), (2.33, 2.83))     # sağa, sola, yeniden sağa
T_EXIT = (2.92, 3.28)      # ikon ışığı toplar, kenarı bize döner ve bir noktaya çöker
T_GLIDE = (2.98, 3.52)     # kelimeler süzülerek birleşir
T_SHINE = (3.28, 3.95)     # ışık noktasından iki yana yayılan dalgalar yazıyı beyazlatır
T_OUT = (4.40, 4.92)

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
WORD_SPACE = 0.32       # son hâlde ANDROE ile STUDIO arası (em)
DIM = 0.6               # ikon ışığı çekerken yazıların sönük (gümüş) parlaklığı

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
    duration = DURATION

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
        s3 = s2 + (x3 - x2)
        final_left = CX - (wa + WORD_SPACE * FONT_SIZE + ws) / 2
        self.glide = (final_left - a3, final_left + wa + WORD_SPACE * FONT_SIZE - s3)
        self.final_box = (final_left, final_left + wa + WORD_SPACE * FONT_SIZE + ws)
        self.spark_x = final_left + wa + WORD_SPACE * FONT_SIZE / 2   # iki kelimenin tam ortası

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

        # Çıkış: kenarı bize dönecek şekilde döner, incelir ve kelimelerin ortasına kayar
        e = progress(t, T_EXIT, lambda u: u ** 2.2)
        yaw += (math.pi / 2 - REST_YAW) * e
        pitch *= 1 - e
        size *= 1 - 0.25 * e
        x += (self.spark_x - self.stops[3]) * progress(t, T_EXIT)
        rot = rot_y(yaw) @ rot_x(pitch) @ rot_z(ICON_TILT + roll)
        return x, CY, z, size, rot

    def _icon_glow(self, t):
        """Oturma ve son duruş anlarında ikonun kısa parlaması."""
        charge = progress(t, T_EXIT, lambda u: u ** 1.5)       # çıkarken ışığı toplar
        return max(pulse(t - T_IN[1], 0.06), 0.8 * pulse(t - T_MOVES[2][1], 0.06), charge)

    def word_states(self, t):
        """Görünen kelimeler: (kelime, sol kenar x, taraf); taraf -1 ikonun solu, +1 sağı."""
        e1, e2, e3 = (progress(t, span) for span in T_MOVES)
        g = progress(t, T_GLIDE)
        states = []
        if T_MOVES[0][0] < t < T_MOVES[1][1]:
            left, shift = self.a1
            states.append((self.androe, left + shift * (1 - e1) + self.a1_back * e2, -1))
        if t > T_MOVES[1][0]:
            left, shift = self.s2
            states.append((self.studio, left + shift * (1 - e2) + (self.stops[3] - self.stops[2]) * e3
                           + self.glide[1] * g, 1))
        if t > T_MOVES[2][0]:
            left, shift = self.a3
            states.append((self.androe, left + shift * (1 - e3) + self.glide[0] * g, -1))
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
        if t < T_EXIT[0]:                        # yazılar ikonun kenarlarından çıkar
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
            return

        # İkon ışığı çekerken yazılar gümüşe söner (üstten alta hafif metalik geçiş)
        level = DIM + (1 - DIM) * (1 - progress(t, T_EXIT, ease_in_out_sine))
        top, bottom = self.baseline - FONT_SIZE * 0.73, self.baseline
        silver = skia.GradientShader.MakeLinear(
            [skia.Point(0, top), skia.Point(0, bottom)],
            [grey(min(level * 1.12, 1)).toColor(), grey(level * 0.86).toColor()])
        self._paint_words(c, t, skia.Paint(AntiAlias=True, Shader=silver))

        # Işık dalgaları ortadan iki yana yayılır; geçtikleri yer bembeyaz olur
        front = self._shine_front(t)
        if front > 0:
            left, right = self.final_box
            box = skia.Rect(left - 60, top - 60, right + 60, bottom + 60)
            c.saveLayer(box, None)
            self._paint_words(c, t, skia.Paint(AntiAlias=True, Color4f=WHITE))
            cx, soft = self.spark_x, 70.0
            span = max(front, 1.0) + soft
            shader = skia.GradientShader.MakeLinear(
                [skia.Point(cx - span, 0), skia.Point(cx + span, 0)],
                [grey(1, 0).toColor(), grey(1, 1).toColor(), grey(1, 1).toColor(), grey(1, 0).toColor()],
                [0.0, soft / (2 * span), 1 - soft / (2 * span), 1.0])
            c.drawRect(box, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kDstIn))
            c.restore()

    def _paint_words(self, c, t, paint):
        for word, left, _ in self.word_states(t):
            c.save()
            c.translate(left, self.baseline)
            c.drawPath(word.path, paint)
            c.restore()

    def _shine_front(self, t):
        """Işık dalgasının kelimelerin ortasından uzaklığı (px)."""
        reach = max(self.spark_x - self.final_box[0], self.final_box[1] - self.spark_x) + 80
        return reach * progress(t, T_SHINE, ease_out_cubic)

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

    def _draw_collapse(self, c, t, pose):
        """İkon kenarı bize dönünce ince bir ışık çizgisi olur, sonra parlayan bir noktaya çöker."""
        x, size = pose[0], pose[3]
        u_in = clamp01((t - T_EXIT[0]) / (T_EXIT[1] - T_EXIT[0]))
        d = t - T_EXIT[1]
        if u_in < 0.55 or d > 0.7:
            return
        if d < 0:                                    # ışık çizgisi belirir
            height = size * 1.05
            alpha = (u_in - 0.55) / 0.45
        else:                                        # çizgi noktaya çöker
            height = size * 1.05 * (1 - ease_out_cubic(clamp01(d / 0.14)))
            alpha = 1.0
        if height > 1:
            line = skia.GradientShader.MakeLinear(
                [skia.Point(x, CY - height / 2), skia.Point(x, CY + height / 2)],
                [grey(1, 0).toColor(), grey(1, alpha).toColor(), grey(1, 0).toColor()])
            for w, blur in ((3.0, 0), (16.0, 10)):
                paint = skia.Paint(AntiAlias=True, Shader=line, BlendMode=skia.BlendMode.kPlus)
                if blur:
                    paint.setImageFilter(skia.ImageFilters.Blur(blur, blur))
                c.drawRect(skia.Rect(x - w / 2, CY - height / 2, x + w / 2, CY + height / 2), paint)
        if d >= 0:                                   # parlayan nokta: dört kollu ışık yıldızı
            glow = pulse(d, 0.06)
            for length, width, a in ((240, 2.5, 0.9), (90, 2.0, 0.7)):
                horizontal = length * (0.4 + 0.6 * ease_out_cubic(clamp01(d / 0.2)))
                vertical = horizontal * 0.45
                for (dx, dy) in ((horizontal, 0), (0, vertical)):
                    ray = skia.GradientShader.MakeLinear(
                        [skia.Point(x - dx - 1e-3, CY - dy - 1e-3), skia.Point(x + dx + 1e-3, CY + dy + 1e-3)],
                        [grey(1, 0).toColor(), grey(1, a * glow).toColor(), grey(1, 0).toColor()])
                    c.drawRect(skia.Rect(x - max(dx, width), CY - max(dy, width), x + max(dx, width), CY + max(dy, width)),
                               skia.Paint(AntiAlias=True, Shader=ray, BlendMode=skia.BlendMode.kPlus))
            core = skia.GradientShader.MakeRadial(skia.Point(x, CY), 70,
                                                  [grey(1, glow).toColor(), grey(1, 0).toColor()])
            c.drawCircle(x, CY, 70, skia.Paint(Shader=core, BlendMode=skia.BlendMode.kPlus))

    def _draw_shine(self, c, t):
        """İki yana yayılan ışık dalgalarının yazıya yapışık parıltısı."""
        u = clamp01((t - T_SHINE[0]) / (T_SHINE[1] - T_SHINE[0]))
        if not 0 < u < 1:
            return
        front = self._shine_front(t)
        left, right = self.final_box
        box = skia.Rect(left - 150, CY - 200, right + 150, CY + 200)
        c.saveLayer(box, skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=0.85 * (1 - u) ** 0.7,
                                    ImageFilter=skia.ImageFilters.Blur(9, 9)))
        self._paint_words(c, t, skia.Paint(AntiAlias=True, Color4f=WHITE))
        cx, w = self.spark_x, 60.0
        a, b = cx - front - w, cx + front + w
        if b - a > 4 * w:
            stops = [0.0, w / (b - a), 2 * w / (b - a), 1 - 2 * w / (b - a), 1 - w / (b - a), 1.0]
            colors = [0, 1, 0, 0, 1, 0]
        else:
            stops, colors = [0.0, 0.5, 1.0], [0, 1, 0]
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(a, 0), skia.Point(b, 0)], [grey(1, v).toColor() for v in colors], stops)
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
        self._draw_words(c, t, pose[0], pose[3])
        if t < T_EXIT[1]:
            self._draw_icon(c, t, pose)
        self._draw_collapse(c, t, pose)
        self._draw_shine(c, t)
        self._draw_landing(c, t)

        if fade > 0:
            c.restore()
        c.restore()

    # ------------------------------------------------------------ kare üretimi

    def samples(self, t):
        """Hareket bulanıklığı için bir karede kaç alt kare çizileceği."""
        if T_IN[0] - 0.05 < t < T_SHINE[1] + 0.1:
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
                    letters=letters, exit=T_EXIT, final=T_EXIT[1], glide=T_GLIDE,
                    glint=T_SHINE, out=T_OUT)

