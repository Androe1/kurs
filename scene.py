"""Androe Studio intro animasyonu - görsel sahne.

Akış (saniye):
  0.18  Simsiyah ekranda beyaz bir yapı bloğu (üstü çıkıntılı küp) belirir.
  0.92  Küp enerji toplar ve yüzlerce küçük bloğa ayrılarak patlar.
  1.0   Bloklar soldan sağa uçar, ANDROE harflerini alttan üste inşa eder.
  2.14  Bir ışık taraması blok harfleri pürüzsüz yazıya çevirir.
  2.36  Altında STUDIO açılır, logo ekranda kalır.
  4.30  Her şey yumuşakça kararır; 5.0'da ekran tamamen siyahtır.

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
T_POP = 0.18            # küp belirir
T_CHARGE = 0.62         # küp sıkışıp enerji toplamaya başlar
T_BURST = 0.92          # küp patlar
T_LETTER = 1.62         # ilk harfin son bloğunun yerine oturduğu an
LETTER_STEP = 0.09      # harflerin tamamlanma aralığı
T_SWEEP = (2.14, 2.46)  # blok harfler -> pürüzsüz yazı
T_STUDIO = (2.36, 2.95)
T_GLINT = (3.30, 3.80)
T_OUT = (4.30, 4.88)

# Tipografi
WORD, SUB = "ANDROE", "STUDIO"
WORD_SIZE, WORD_TRACK = 196.0, 0.045
SUB_SIZE, SUB_TRACK = 44.0, 0.62
LINE_GAP = 36.0         # ANDROE tabanı ile STUDIO'nun üstü arası
SUB_LINE_MARGIN = 30.0  # STUDIO ile yan çizgiler arası

# Bloklar
CELL = 14               # harf ızgarasının hücre boyu (px)
BLOCK = CELL - 2.5      # yerine oturan bloğun kenarı (aradaki boşluk derz gibi durur)
CUBE = 210.0            # açılıştaki büyük küpün kenarı
BUILD_SPREAD = 0.30     # bir harfin alt sırasından üst sırasına inşa süresi
DUST_RATIO = 0.14       # tarama geçince toz olup uçuşan blok oranı

# Işık taraması (eğik bir çizgi olarak soldan sağa geçer)
SWEEP_ANGLE = 0.2
SWEEP_DIR = np.array([math.cos(SWEEP_ANGLE), math.sin(SWEEP_ANGLE)])
SWEEP_W = 70.0          # blok -> yazı geçişinin genişliği

SHUTTER = 0.5           # hareket bulanıklığı: kare süresinin yarısı (180 derece)
BLOOM = ((14.0, 0.20), (46.0, 0.10))  # (bulanıklık, miktar) çiftleri

LIGHT = np.array([-0.45, -0.75, -0.62])
LIGHT /= np.linalg.norm(LIGHT)

WHITE = skia.Color4f(1, 1, 1, 1)


# ---------------------------------------------------------------- yumuşatmalar

def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(a, b, x):
    u = clamp01((x - a) / (b - a))
    return u * u * (3 - 2 * u)


def ease_in_out_cubic(u):
    return np.where(u < 0.5, 4 * u**3, 1 - (2 - 2 * u) ** 3 / 2)


def ease_in_out_sine(u):
    return 0.5 - 0.5 * np.cos(np.pi * u)


def ease_out_cubic(u):
    return 1 - (1 - u) ** 3


def ease_out_back(u, s=2.2):
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def ease_out_expo(u):
    return (1 - 2.0 ** (-10 * u)) / (1 - 2.0**-10)


def pulse(x, width):
    """Hızla yükselip yavaşça sönen tepe; x == width iken 1."""
    x = np.maximum(x, 0.0) / width
    return x * np.exp(1 - x)


# ---------------------------------------------------------------- 3B yardımcılar

_V = np.array([[x, y, z] for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)])
_FACES = np.array([[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1],
                   [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]])
_NORMALS = np.array([[-1, 0, 0], [1, 0, 0], [0, -1, 0],
                     [0, 1, 0], [0, 0, -1], [0, 0, 1]], float)
_TOP = 2                 # y ekranda aşağı baktığı için -y yüzü küpün üstü
_CAM = np.array([CX, CY, -FOCAL])
_RING = np.linspace(0, 2 * np.pi, 28, endpoint=False)


def rotation(ang):
    """Euler açıları (..., 3) -> dönüş matrisleri (..., 3, 3); R = Rz @ Rx @ Ry."""
    ang = np.asarray(ang, float)
    c, s = np.cos(ang), np.sin(ang)
    o, z = np.ones(ang.shape[:-1]), np.zeros(ang.shape[:-1])
    shape = ang.shape[:-1] + (3, 3)
    rx = np.stack([o, z, z, z, c[..., 0], -s[..., 0], z, s[..., 0], c[..., 0]], -1)
    ry = np.stack([c[..., 1], z, s[..., 1], z, o, z, -s[..., 1], z, c[..., 1]], -1)
    rz = np.stack([c[..., 2], -s[..., 2], z, s[..., 2], c[..., 2], z, z, z, o], -1)
    return rz.reshape(shape) @ rx.reshape(shape) @ ry.reshape(shape)


def project(p):
    """3B noktalar (..., 3) -> ekran koordinatları (..., 2)."""
    k = FOCAL / (FOCAL + p[..., 2])
    return np.stack([CX + (p[..., 0] - CX) * k, CY + (p[..., 1] - CY) * k], -1)


def lambert(normals):
    return 0.40 + 0.62 * np.clip(normals @ LIGHT, 0, None)


def cube_geometry(pos, rot, size):
    """N küp için ekrandaki yüz dörtgenleri, görünürlük ve gölgelendirme."""
    verts = pos[:, None, :] + size[:, None, None] * np.einsum("nij,vj->nvi", rot, _V)
    normals = np.einsum("nij,fj->nfi", rot, _NORMALS)
    centers = pos[:, None, :] + 0.5 * size[:, None, None] * normals
    visible = np.einsum("nfi,nfi->nf", normals, centers - _CAM) < 0
    return project(verts)[:, _FACES], visible, lambert(normals)


def polygon(points):
    path = skia.Path()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    path.close()
    return path


def convex_hull(points):
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


def grey(v, a=1.0):
    v = float(min(max(v, 0.0), 1.0))
    return skia.Color4f(v, v, v, float(a))


def cube_pose(t):
    """Açılış küpünün ölçeği, Euler açıları ve parlama miktarı."""
    u = float(clamp01((t - T_POP) / 0.34))
    scale = float(ease_out_back(u)) if u < 1 else 1.0
    charge = float(clamp01((t - T_CHARGE) / (T_BURST - T_CHARGE)))
    scale *= 1 - 0.14 * charge**3                     # patlamadan önce sıkışır
    spin = (0.75 - 1.1 * (1 - float(ease_out_cubic(u)))
            + 1.2 * max(t - T_POP, 0) + 7.0 * max(t - T_CHARGE, 0) ** 2)
    return scale, np.array([0.46, spin, -0.16]), charge**3


# ---------------------------------------------------------------- sahne

class Scene:
    def __init__(self, width=1920, height=1080, fps=60, seed=11):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.to_linear = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)
        rng = np.random.default_rng(seed)
        self._layout_text()
        self._build_voxels(rng)
        self._build_dust(rng)

    # ------------------------------------------------------------ hazırlık

    def _layout_text(self):
        font_a = skia.Font(skia.Typeface.MakeFromFile(str(FONTS / "Montserrat-Black.ttf")), WORD_SIZE)
        font_s = skia.Font(skia.Typeface.MakeFromFile(str(FONTS / "Montserrat-SemiBold.ttf")), SUB_SIZE)
        cap_a = font_a.getMetrics().fCapHeight
        cap_s = font_s.getMetrics().fCapHeight

        top = CY - (cap_a + LINE_GAP + cap_s) / 2 - 4
        base_a = top + cap_a
        self.sub_base = base_a + LINE_GAP + cap_s
        self.sub_mid = self.sub_base - cap_s / 2

        # ANDROE: harf harf yerleştir, mürekkep sınırlarına göre ortala
        paths, x = [], 0.0
        glyphs = font_a.textToGlyphs(WORD)
        for g, adv in zip(glyphs, font_a.getWidths(glyphs)):
            p = font_a.getPath(g)
            p.offset(x, 0)
            paths.append(p)
            x += adv + WORD_TRACK * WORD_SIZE
        left = min(p.computeTightBounds().left() for p in paths)
        right = max(p.computeTightBounds().right() for p in paths)
        for p in paths:
            p.offset(CX - (left + right) / 2, base_a)
        self.letters = paths
        self.word = skia.Path()
        for p in paths:
            self.word.addPath(p)
        b = self.word.computeTightBounds()
        self.word_box = (b.left(), b.top(), b.right(), b.bottom())
        self.word_center = np.array([(b.left() + b.right()) / 2, (b.top() + b.bottom()) / 2])
        self.layer_box = skia.Rect(b.left() - 90, b.top() - 90, b.right() + 90, b.bottom() + 90)

        # Işık taramasının ekseni boyunca yazının kapladığı aralık
        corners = np.array([[b.left(), b.top()], [b.right(), b.top()],
                            [b.left(), b.bottom()], [b.right(), b.bottom()]])
        proj = (corners - self.word_center) @ SWEEP_DIR
        self.proj_min, self.proj_max = proj.min(), proj.max()

        # STUDIO: harf aralığı canlandırılacağı için glifler ayrı tutulur
        glyphs = font_s.textToGlyphs(SUB)
        self.sub_paths = [font_s.getPath(g) for g in glyphs]
        self.sub_adv = list(font_s.getWidths(glyphs))
        self.sub_ink = (self.sub_paths[0].computeTightBounds().left(),
                        self.sub_paths[-1].computeTightBounds().right())

    def _letter_cells(self):
        """Harfleri blok ızgarasına çevirir: hücre merkezleri, harf no, sıra oranı."""
        masks = []
        for p in self.letters:
            surf = skia.Surface(W, H)
            with surf as c:
                c.clear(skia.ColorBLACK)
                c.drawPath(p, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
            masks.append(surf.toarray()[..., 0].astype(np.float32) / 255)
        masks = np.stack(masks)
        total = masks.sum(0)

        l, t, r, b = self.word_box
        cols = int(math.ceil((r - l) / CELL)) + 1
        rows = int(math.ceil((b - t) / CELL)) + 1

        def coverage(img, ox, oy):
            x0, y0 = int(l) - ox, int(t) - oy
            area = img[..., y0:y0 + rows * CELL, x0:x0 + cols * CELL]
            return area.reshape(area.shape[:-2] + (rows, CELL, cols, CELL)).mean((-3, -1))

        def ambiguity(offset):
            cov = coverage(total, *offset)
            return np.minimum(cov, 1 - cov).sum()

        # Izgarayı, harf kenarlarına en iyi oturacak şekilde kaydır
        best = min(((ox, oy) for oy in range(CELL) for ox in range(CELL)), key=ambiguity)
        cov = coverage(masks, *best)                     # (harf, sıra, sütun)
        filled = cov.sum(0) > 0.5
        rr, cc = np.nonzero(filled)
        letter = cov[:, rr, cc].argmax(0)
        x0, y0 = int(l) - best[0], int(t) - best[1]
        centers = np.stack([x0 + (cc + 0.5) * CELL, y0 + (rr + 0.5) * CELL], -1)

        row_frac = np.zeros(len(rr))
        for k in range(len(self.letters)):
            m = letter == k
            lo, hi = rr[m].min(), rr[m].max()
            row_frac[m] = (hi - rr[m]) / max(hi - lo, 1)  # 0 = en alt sıra, 1 = en üst
        return centers.astype(float), letter, row_frac

    def _build_voxels(self, rng):
        target, letter, row_frac = self._letter_cells()
        n = len(target)
        self.n = n
        self.target = target
        self.letter = letter
        self.target3 = np.column_stack([target, np.zeros(n)])
        self.proj = (target - self.word_center) @ SWEEP_DIR

        # Her harf alttan üste inşa edilir; harfin son bloğu tam `done` anında oturur
        done = T_LETTER + LETTER_STEP * letter
        land = done - BUILD_SPREAD * (1 - row_frac) - rng.uniform(0, 0.035, n)
        for k in range(len(self.letters)):
            m = letter == k
            land[m] += done[m][0] - land[m].max()
        dur = rng.uniform(0.34, 0.46, n)
        start = np.maximum(land - dur, T_BURST + 0.10 + rng.uniform(0, 0.06, n))
        self.land, self.start, self.dur = land, start, land - start
        self.letter_done = [T_LETTER + LETTER_STEP * k for k in range(len(self.letters))]

        # Patlama anında bloklar büyük küpün içini dolduran bir kafeste durur
        scale_b, ang_b, _ = cube_pose(T_BURST)
        rot_b = rotation(ang_b)
        side = math.ceil(n ** (1 / 3))
        grid = (np.stack(np.meshgrid(*[np.arange(side)] * 3, indexing="ij"), -1)
                .reshape(-1, 3) + 0.5) / side - 0.5
        local = grid[rng.choice(len(grid), n, replace=False)]
        origin = np.array([CX, CY, 0.0])
        p0 = origin + CUBE * scale_b * local @ rot_b.T

        direction = (p0 - origin) / (np.linalg.norm(p0 - origin, axis=1, keepdims=True) + 1e-6)
        direction += rng.normal(0, 0.45, (n, 3))
        direction /= np.linalg.norm(direction, axis=1, keepdims=True)
        direction *= [1.75, 0.95, 1.0]                 # yazı yatay olduğu için yana savrulur
        dist = rng.uniform(150, 380, n) * (0.55 + 0.8 * np.linalg.norm(local, axis=1))
        disp = direction * dist[:, None]
        disp[:, 2] = np.clip(disp[:, 2], -520, 300)

        # Bulutun solundaki bloklar soldaki harflere gider: uçuşlar düzenli görünür
        src = np.argsort((p0 + disp)[:, 0] + rng.normal(0, 60, n))
        dst = np.argsort(target[:, 0] + rng.normal(0, 60, n))
        self.p0 = np.empty_like(p0)
        self.disp = np.empty_like(disp)
        self.p0[dst], self.disp[dst] = p0[src], disp[src]
        self.drift = rng.normal(0, 18, (n, 3))
        self.rot0 = ang_b + rng.normal(0, 0.05, (n, 3))
        self.spin_fast = rng.normal(0, 8.0, (n, 3))
        self.spin_slow = rng.normal(0, 1.0, (n, 3))
        self.frag = CUBE * scale_b / side / BLOCK     # patlama anında parça / blok boyu

        # Uçuş sonunda en yakın "düz" duruşa oturur (küp simetrisi: 90 derecenin katları)
        _, ang_land, _ = self._explode(land)
        self.snap = np.round(ang_land / (np.pi / 2)) * (np.pi / 2)

    def _build_dust(self, rng):
        """Tarama geçerken bazı bloklar toz gibi havalanıp söner."""
        ts = np.linspace(T_SWEEP[0], T_SWEEP[1], 400)
        # blok, tarama çizgisi üzerinden SWEEP_W/2 geçince kopar
        t_pass = np.interp(self.proj + SWEEP_W / 2, self._sweep(ts), ts)
        pick = rng.random(self.n) < DUST_RATIO
        self.is_dust = pick
        self.dust_t = np.where(pick, t_pass, np.inf)
        self.dust = [dict(i=i, t=t_pass[i],
                          v=(rng.uniform(-40, 90), rng.uniform(-260, -90)),
                          spin=rng.uniform(-200, 200),
                          life=rng.uniform(0.8, 1.6))
                     for i in np.nonzero(pick)[0]]

    # ------------------------------------------------------------ hareket

    def _explode(self, t):
        dt = np.broadcast_to(np.maximum(np.asarray(t, float) - T_BURST, 0), (self.n,))[:, None]
        pos = self.p0 + self.disp * (1 - np.exp(-dt / 0.2)) + self.drift * dt
        ang = self.rot0 + self.spin_fast * 0.35 * (1 - np.exp(-dt / 0.35)) + self.spin_slow * dt
        size = 1 + (self.frag - 1) * np.exp(-dt[:, 0] / 0.28)
        return pos, ang, size

    def _sweep(self, t):
        u = ease_in_out_sine(clamp01((np.asarray(t) - T_SWEEP[0]) / (T_SWEEP[1] - T_SWEEP[0])))
        return self.proj_min - 5 + (self.proj_max + SWEEP_W + 10 - self.proj_min) * u

    # ------------------------------------------------------------ çizim

    def _draw_cube(self, c, t):
        scale, ang, glow = cube_pose(t)
        if t < T_POP or t >= T_BURST or scale <= 1e-3:
            return
        size = CUBE * scale
        rot = rotation(ang)
        pos = np.array([[CX, CY, 0.0]])
        quads, visible, shades = cube_geometry(pos, rot[None], np.array([size]))
        quads, visible, shades = quads[0], visible[0], shades[0]

        if glow > 0.01:  # enerji toplarken etrafına yayılan hale
            hull = polygon(convex_hull(quads.reshape(-1, 2)))
            c.drawPath(hull, skia.Paint(AntiAlias=True, Color4f=grey(1, 0.9 * glow),
                                        BlendMode=skia.BlendMode.kPlus,
                                        ImageFilter=skia.ImageFilters.Blur(28, 28)))

        paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStrokeAndFill_Style, StrokeWidth=0.8)
        for f in np.nonzero(visible)[0]:
            v = shades[f] + (1 - shades[f]) * glow
            paint.setColor4f(grey(v))
            c.drawPath(polygon(quads[f].tolist()), paint)

        if visible[_TOP]:  # üst yüzdeki 2x2 çıkıntı (yapı bloğu işareti)
            top = shades[_TOP] + (1 - shades[_TOP]) * glow
            studs = []
            for ox, oz in ((-.25, -.25), (.25, -.25), (-.25, .25), (.25, .25)):
                ring = np.stack([ox + 0.15 * np.cos(_RING), np.full(_RING.shape, -0.5),
                                 oz + 0.15 * np.sin(_RING)], -1)
                cap = ring + [0, -0.09, 0]
                base_w = pos[0] + size * ring @ rot.T
                cap_w = pos[0] + size * cap @ rot.T
                studs.append((cap_w[:, 2].mean(), project(base_w), project(cap_w)))
            for _, base, cap in sorted(studs, key=lambda s: -s[0]):
                paint.setColor4f(grey(top * 0.62 + 0.38 * glow))
                c.drawPath(polygon(convex_hull(np.vstack([base, cap]))), paint)
                paint.setColor4f(grey(top))
                c.drawPath(polygon(cap.tolist()), paint)

    def _draw_burst(self, c, t):
        dt = t - T_BURST
        if dt < 0 or dt > 0.7:
            return
        flash = math.exp(-dt / 0.05)
        shader = skia.GradientShader.MakeRadial(
            skia.Point(CX, CY), 320,
            [grey(1, 0.9 * flash).toColor(), grey(1, 0.22 * flash).toColor(), grey(1, 0).toColor()],
            [0.0, 0.3, 1.0])
        c.drawCircle(CX, CY, 320, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kPlus))
        # Genişleyen eğik kare şok dalgaları
        for delay, width in ((0.0, 6.0), (0.07, 3.5)):
            u = (dt - delay) / 0.55
            if not 0 <= u <= 1:
                continue
            e = float(ease_out_cubic(u))
            half = CUBE * (0.9 + 4.2 * e) / 2
            paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                               StrokeWidth=width * (1 - u) + 0.6, Color4f=grey(1, 0.6 * (1 - u) ** 2))
            c.save()
            c.translate(CX, CY)
            c.rotate(-12 - 8 * e)
            c.drawRect(skia.Rect(-half, -half, half, half), paint)
            c.restore()

    def _draw_voxels(self, c, t, sweep):
        if t < T_BURST:
            return
        pos_e, ang_e, size_e = self._explode(t)
        e = ease_in_out_cubic(clamp01((t - self.start) / self.dur))
        pos = pos_e + (self.target3 - pos_e) * e[:, None]
        ang = ang_e + (self.snap - ang_e) * e[:, None]
        size = BLOCK * (size_e + (1 - size_e) * e)
        glow = np.maximum(math.exp(-(t - T_BURST) / 0.10), e**4)

        alpha = smoothstep(sweep - SWEEP_W, sweep, self.proj)
        landed = t >= self.land
        flying = np.nonzero(~landed)[0]

        paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStrokeAndFill_Style, StrokeWidth=0.8)
        behind, front = [], []
        if len(flying):
            quads, visible, shades = cube_geometry(pos[flying], rotation(ang[flying]), size[flying])
            shades = shades + (1 - shades) * glow[flying, None]
            for j in np.argsort(-pos[flying, 2]):
                item = (quads[j], visible[j], shades[j])
                (behind if pos[flying[j], 2] >= 0 else front).append(item)

        def draw_flying(items):
            for quad, vis, shade in items:
                for f in np.nonzero(vis)[0]:
                    paint.setColor4f(grey(shade[f]))
                    c.drawPath(polygon(quad[f].tolist()), paint)

        draw_flying(behind)

        # Yerine oturan bloklar: düz kareler, oturunca hafif "tık" büyümesi
        since = t - self.land
        pop = 1 + 0.32 * pulse(since, 0.03)
        flat = skia.Paint(AntiAlias=True)
        alpha = np.where(self.is_dust, 1.0, alpha)  # toz blokları kopana dek tam görünür
        show = landed & np.where(self.is_dust, t < self.dust_t, alpha > 0.002)
        for i in np.nonzero(show)[0]:
            h = BLOCK * pop[i] * (0.3 + 0.7 * alpha[i]) / 2
            x, y = self.target[i]
            flat.setColor4f(grey(1, alpha[i]))
            c.drawRect(skia.Rect(x - h, y - h, x + h, y + h), flat)

        fresh = np.nonzero(landed & (since < 0.3))[0]
        if len(fresh):  # oturma anındaki kısa parlama
            c.saveLayer(self.layer_box, skia.Paint(BlendMode=skia.BlendMode.kPlus,
                                                   ImageFilter=skia.ImageFilters.Blur(7, 7)))
            for i in fresh:
                h = BLOCK * 0.8
                x, y = self.target[i]
                flat.setColor4f(grey(1, 0.75 * pulse(since[i], 0.04)))
                c.drawRect(skia.Rect(x - h, y - h, x + h, y + h), flat)
            c.restore()

        draw_flying(front)

    def _mask(self, c, stops):
        """Katmanı tarama ekseni boyunca (konum, opaklık) duraklarına göre maskeler."""
        lo, hi = stops[0][0], stops[-1][0]
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(*(self.word_center + lo * SWEEP_DIR)),
             skia.Point(*(self.word_center + hi * SWEEP_DIR))],
            [grey(1, a).toColor() for _, a in stops],
            [(s - lo) / (hi - lo) for s, _ in stops])
        c.drawRect(self.layer_box, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kDstIn))

    def _draw_word(self, c, sweep):
        if sweep <= self.proj_min:
            return
        paint = skia.Paint(AntiAlias=True, Color4f=WHITE)
        if sweep - SWEEP_W >= self.proj_max:
            c.drawPath(self.word, paint)
            return
        c.saveLayer(self.layer_box, None)
        c.drawPath(self.word, paint)
        self._mask(c, [(sweep - SWEEP_W, 1), (sweep, 0)])
        c.restore()

    def _draw_light(self, c, center, width, strength, blur):
        """Yazının üzerinden geçen ışık bandı (yazıya yapışık parıltı)."""
        if strength <= 0.005:
            return
        c.saveLayer(self.layer_box, skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=float(strength),
                                               ImageFilter=skia.ImageFilters.Blur(blur, blur)))
        c.drawPath(self.word, skia.Paint(AntiAlias=True, Color4f=WHITE))
        self._mask(c, [(center - width, 0), (center, 1), (center + width, 0)])
        c.restore()

    def _draw_sweep(self, c, t, sweep):
        if not T_SWEEP[0] <= t <= T_SWEEP[1] + 0.05:
            return
        u = float(clamp01((t - T_SWEEP[0]) / (T_SWEEP[1] - T_SWEEP[0])))
        strength = math.sin(math.pi * u) ** 0.6
        center = sweep - SWEEP_W / 2
        self._draw_light(c, center, 60, 0.9 * strength, 9)
        # Yazının üzerinden geçen yumuşak, eğik ışık huzmesi (uçları sönümlü)
        mid = self.word_center + center * SWEEP_DIR
        d = np.array([-SWEEP_DIR[1], SWEEP_DIR[0]])
        a, b = mid - 190 * d, mid + 190 * d
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(*a), skia.Point(*b)],
            [grey(1, 0).toColor(), grey(1, 0.3 * strength).toColor(), grey(1, 0).toColor()])
        c.drawLine(*a, *b, skia.Paint(AntiAlias=True, Shader=shader, StrokeWidth=34,
                                      BlendMode=skia.BlendMode.kPlus,
                                      ImageFilter=skia.ImageFilters.Blur(16, 16)))

    def _draw_dust(self, c, t):
        paint = skia.Paint(AntiAlias=True)
        for d in self.dust:
            age = t - d["t"]
            if age < 0 or age > d["life"]:
                continue
            u = age / d["life"]
            lift = 0.35 * (1 - math.exp(-age / 0.35))    # önce hızlı kopar, sonra süzülür
            x = self.target[d["i"], 0] + d["v"][0] * (lift + 0.3 * age)
            y = self.target[d["i"], 1] + d["v"][1] * (lift + 0.3 * age)
            h = BLOCK * (0.8 - 0.55 * u) / 2
            paint.setColor4f(grey(1, 0.95 * (1 - u) ** 1.4))
            c.save()
            c.translate(x, y)
            c.rotate(d["spin"] * age)
            c.drawRect(skia.Rect(-h, -h, h, h), paint)
            c.restore()

    def _draw_sub(self, c, t):
        u = float(clamp01((t - T_STUDIO[0]) / (T_STUDIO[1] - T_STUDIO[0])))
        if u <= 0:
            return
        e = float(ease_out_expo(u))
        alpha = float(smoothstep(0, 0.45, u))
        blur = 5 * (1 - float(smoothstep(0, 0.6, u)))

        def ink_width(track):
            return sum(self.sub_adv[:-1]) + track * (len(self.sub_adv) - 1) + self.sub_ink[1] - self.sub_ink[0]

        track = (0.12 + (SUB_TRACK - 0.12) * e) * SUB_SIZE
        x = CX - ink_width(track) / 2 - self.sub_ink[0]
        y = self.sub_base + 10 * (1 - e)
        paint = skia.Paint(AntiAlias=True, Color4f=grey(1, alpha))
        if blur > 0.05:
            paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
        for p, adv in zip(self.sub_paths, self.sub_adv):
            c.save()
            c.translate(x, y)
            c.drawPath(p, paint)
            c.restore()
            x += adv + track

        # STUDIO'nun iki yanından ANDROE genişliğine uzanan ince çizgiler
        lu = float(ease_in_out_cubic(clamp01((t - T_STUDIO[0] - 0.12) / 0.5)))
        if lu > 0:
            inner = ink_width(SUB_TRACK * SUB_SIZE) / 2 + SUB_LINE_MARGIN
            outer = (self.word_box[2] - self.word_box[0]) / 2
            reach = inner + (outer - inner) * lu
            line = skia.Paint(AntiAlias=True, Color4f=grey(1, 0.92), StrokeWidth=2.5)
            for sign in (-1, 1):
                c.drawLine(CX + sign * inner, self.sub_mid, CX + sign * reach, self.sub_mid, line)

    def _draw_glint(self, c, t):
        u = float(clamp01((t - T_GLINT[0]) / (T_GLINT[1] - T_GLINT[0])))
        if 0 < u < 1:
            center = self.proj_min - 80 + (self.proj_max - self.proj_min + 160) * float(ease_in_out_sine(u))
            self._draw_light(c, center, 70, 0.6 * math.sin(math.pi * u), 10)

    def draw(self, c, t):
        """Tek bir anı (t saniye) tuvale çizer."""
        c.clear(skia.ColorBLACK)
        if t >= T_OUT[1]:
            return
        c.save()
        c.scale(self.k, self.k)

        zoom = 1 + 0.035 * float(ease_in_out_sine(clamp01(t / DURATION)))
        fade = 0.0
        if t > T_OUT[0]:
            fade = float(ease_in_out_sine(clamp01((t - T_OUT[0]) / (T_OUT[1] - T_OUT[0]))))
            zoom += 0.03 * fade
        dt = t - T_BURST
        shake = 11 * math.exp(-dt / 0.09) if dt >= 0 else 0.0
        c.translate(CX + shake * math.sin(2 * math.pi * 31 * dt + 0.3),
                    CY + shake * math.sin(2 * math.pi * 23 * dt + 1.7))
        c.rotate(0.05 * shake * math.sin(2 * math.pi * 17 * dt))
        c.scale(zoom, zoom)
        c.translate(-CX, -CY)

        if fade > 0:
            paint = skia.Paint(Alphaf=1 - fade)
            if fade > 0.02:
                paint.setImageFilter(skia.ImageFilters.Blur(7 * fade, 7 * fade))
            c.saveLayer(None, paint)

        sweep = float(self._sweep(t))
        self._draw_cube(c, t)
        self._draw_voxels(c, t, sweep)
        self._draw_word(c, sweep)
        self._draw_sweep(c, t, sweep)
        self._draw_dust(c, t)
        self._draw_sub(c, t)
        self._draw_glint(c, t)
        self._draw_burst(c, t)

        if fade > 0:
            c.restore()
        c.restore()

    # ------------------------------------------------------------ kare üretimi

    def samples(self, t):
        """Hareket bulanıklığı için bir karede kaç alt kare çizileceği."""
        if T_BURST - 0.03 < t < T_BURST + 0.25:
            return 12
        if T_POP - 0.05 < t < T_SWEEP[1] + 0.1:
            return 8
        if t < T_STUDIO[1] + 0.1:
            return 4
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

    def events(self):
        """Ses tasarımının görüntüyle eşleşmesi için olay zamanları."""
        left, right = self.word_box[0], self.word_box[2]
        xn = (self.target[:, 0] - left) / (right - left)
        letters = []
        for k, done in enumerate(self.letter_done):
            letters.append((done, float(xn[self.letter == k].mean())))
        return dict(duration=DURATION, pop=T_POP, charge=T_CHARGE, burst=T_BURST,
                    landings=list(zip(self.land.tolist(), xn.tolist())),
                    letters=letters, sweep=T_SWEEP, studio=T_STUDIO,
                    glint=T_GLINT, out=T_OUT)
