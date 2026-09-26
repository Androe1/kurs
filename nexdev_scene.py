"""NexDev intro animasyonu - görsel sahne (7 saniye).

Akış (saniye):
  0.2   Simsiyah ekranda beş küp sırayla takla atarak belirir; ön yüzlerinde
        stüdyonun işlerinin sembolleri: çekiç (build), parıltı (VFX),
        hoparlör (SFX), tel kafes küp (modelleme), </> (script).
  2.0   Küpler dalga hâlinde sağa sola döner.
  2.85  Rubik küpü gibi karışırlar: sağa, sola, ileri, geri dönerken tek sıraya
        dizilirler, altıncı küp de gelir.
  4.0   Her küp son kez döner ve logonun harfleri çözülür: N e x D e v.
  4.75  Küplerin gövdesi erir, harfler toplanıp "NexDev" logosuna dönüşür
        (Inter Black; Nex beyaz, Dev sarı - logonun aynısı).
  5.6   Logonun üzerinden ışık geçer; 6.35'ten sonra her şey kararır.

Ekranda logodan başka yazı yoktur. Küp yüzlerindeki semboller ve harfler
dokudur (texture); küp döndükçe perspektifle birlikte eğilirler.
Tüm ölçüler 1920x1080 tasarım alanındadır.
"""
import math

import numpy as np
import skia

from scene import (CX, CY, FOCAL, FONTS, W, Scene, clamp01, ease_in_out_cubic, ease_in_out_sine,
                   grey, progress, project, pulse, rot_x, rot_y)

DURATION = 7.0
YELLOW = (1.0, 0.8, 0.41)        # logodaki sarı (#FFCC69)
WHITE = (1.0, 1.0, 1.0)
FACE = (0.085, 0.085, 0.09)      # küp yüzü rengi

CUBE = 152.0                     # küp kenarı (px)
ROW_PITCH = 205.0                # sembol sırasındaki küpler arası
GRID_PITCH = CUBE + 16           # harf sırasındaki küpler arası
TEX = 384                        # yüz dokusu çözünürlüğü

SKILLS = ("build", "vfx", "sfx", "model", "script")
LETTERS = (("N", WHITE), ("e", WHITE), ("x", WHITE), ("D", YELLOW), ("e", YELLOW), ("v", YELLOW))

DUST_BOX = (380, 250, 1540, 830)  # toz parçacıklarının dolaştığı alan (köşelerden uzak)
T_WAVE = 2.0                     # sembol küplerinin dalga dönüşü
T_SNAP = 4.62                    # tüm harfler çözülür
T_MELT = (4.75, 5.35)            # küpler erir, harfler logoya toplanır
T_GLINT = (5.6, 6.1)
T_OUT = (6.35, 6.92)

LOGO_SIZE, LOGO_TRACK = 206.0, -0.018  # logodaki Inter Black, sıkı harf aralığı
LETTER_ON_CUBE = 130.0           # küp yüzündeki harfin punto karşılığı

LIGHT = np.array([-0.35, -0.5, -0.8]) / np.linalg.norm([-0.35, -0.5, -0.8])
_V = np.array([[x, y, z] for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)])
_FACES = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
_NORMALS = np.array([[-1, 0, 0], [1, 0, 0], [0, -1, 0], [0, 1, 0], [0, 0, -1], [0, 0, 1]], float)
_CAM = np.array([CX, CY, -FOCAL])


def color(rgb, a=1.0):
    return skia.Color4f(*rgb, a)


def turn(axis, angle):
    return rot_x(angle) if axis == "x" else rot_y(angle)


# ---------------------------------------------------------------- yüz dokuları

def _symbol(c, name, font_black):
    """Sembolleri 0..TEX karelik alanın ortasına çizer."""
    s = TEX / 256
    c.save()
    c.translate(TEX / 2, TEX / 2)
    c.scale(s, s)
    fill = skia.Paint(AntiAlias=True, Color4f=color(YELLOW))
    line = skia.Paint(AntiAlias=True, Color4f=color(YELLOW), Style=skia.Paint.kStroke_Style,
                      StrokeWidth=11, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    if name == "build":                          # çekiç
        c.rotate(-40)
        c.drawRoundRect(skia.Rect(-11, -18, 11, 92), 6, 6, fill)
        c.drawRoundRect(skia.Rect(-60, -66, 44, -22), 8, 8, fill)
        c.drawRect(skia.Rect(44, -58, 62, -30), fill)
    elif name == "vfx":                          # parıltılar
        def star(x, y, r):
            pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
            p = skia.Path()
            p.moveTo(*pts[0])
            for q in pts[1:] + pts[:1]:
                p.quadTo(x, y, *q)
            p.close()
            c.drawPath(p, fill)
        star(-12, 10, 70)
        star(52, -52, 26)
        star(58, 50, 16)
    elif name == "sfx":                          # hoparlör ve ses dalgaları
        c.drawPath(_poly([(-78, -22), (-46, -22), (-4, -60), (-4, 60), (-46, 22), (-78, 22)]), fill)
        for r in (34, 62):
            c.drawArc(skia.Rect(-4 - r, -r, -4 + r, r), -45, 90, False, line)
    elif name == "model":                        # tel kafes küp
        h = 62
        hexagon = [(0, -h), (h * 0.87, -h / 2), (h * 0.87, h / 2), (0, h), (-h * 0.87, h / 2), (-h * 0.87, -h / 2)]
        c.drawPath(_poly(hexagon), line)
        for q in ((h * 0.87, -h / 2), (-h * 0.87, -h / 2), (0, h)):
            c.drawLine(0, 0, *q, line)
        for q in hexagon:
            c.drawCircle(*q, 9, fill)
    elif name == "script":                       # kod: </>
        font = skia.Font(font_black, 96)
        blob = skia.TextBlob("</>", font)
        b = blob.bounds()
        c.drawTextBlob(blob, -(b.left() + b.right()) / 2, 34, fill)
    c.restore()


def _poly(points):
    p = skia.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    p.close()
    return p


def _letter_path(font, ch):
    """Harf yolu: yatayda mürekkep ortası x=0; büyük harf yüksekliğinin ortası y=0.

    Böylece küçük harfler (e, x, v) büyüklerle aynı taban çizgisine oturur,
    tıpkı logodaki gibi.
    """
    p = font.getPath(font.textToGlyphs(ch)[0])
    b = p.computeTightBounds()
    p.offset(-(b.left() + b.right()) / 2, font.getMetrics().fCapHeight / 2)
    return p


def _centered_symbol(name, font_black):
    """Sembolü ayrı bir yüzeye çizer, mürekkep sınırlarını ölçüp dokunun tam ortasına kaydırır."""
    surf = skia.Surface(TEX, TEX)
    with surf as c:
        c.clear(skia.ColorTRANSPARENT)
        _symbol(c, name, font_black)
    ink = surf.toarray(colorType=skia.kRGBA_8888_ColorType)[..., 3] > 8
    ys, xs = np.nonzero(ink)
    dx = TEX / 2 - (xs.min() + xs.max() + 1) / 2
    dy = TEX / 2 - (ys.min() + ys.max() + 1) / 2
    out = skia.Surface(TEX, TEX)
    with out as c:
        c.clear(skia.ColorTRANSPARENT)
        c.drawImage(surf.makeImageSnapshot(), dx, dy)
    return out.makeImageSnapshot()


def _face_texture(content, font_black):
    surf = skia.Surface(TEX, TEX)
    with surf as c:
        c.clear(skia.ColorTRANSPARENT)
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(TEX, TEX)],
            [color(tuple(v * 1.5 for v in FACE)).toColor(), color(FACE).toColor()])
        c.drawRect(skia.Rect(0, 0, TEX, TEX), skia.Paint(Shader=shader))
        border = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=TEX * 0.02,
                            Color4f=color((0.26, 0.26, 0.27)))
        m = TEX * 0.03
        c.drawRoundRect(skia.Rect(m, m, TEX - m, TEX - m), TEX * 0.04, TEX * 0.04, border)
        if content in SKILLS:
            c.drawImage(_centered_symbol(content, font_black), 0, 0)
        elif content != "blank":
            ch, rgb = content
            font = skia.Font(font_black, LETTER_ON_CUBE * TEX / CUBE)
            c.save()
            c.translate(TEX / 2, TEX / 2)
            c.drawPath(_letter_path(font, ch), skia.Paint(AntiAlias=True, Color4f=color(rgb)))
            c.restore()
    return surf.makeImageSnapshot().withDefaultMipmaps()


# ---------------------------------------------------------------- küp hareketi

class Cube:
    """Bir küpün hareket planı: 90 derecelik dönüşler, konum geçişleri, belirme anı."""

    def __init__(self, pos, pop, first):
        self.pos = pos                   # başlangıç konumu (x, y)
        self.pop = pop                   # belirme anı
        self.moves = []                  # (t0, t1, (x, y))
        self.turns = []                  # (t0, t1, eksen, yön, içerik)
        self.first = first

    def finish(self):
        """Her dönüş sonundaki duruşu, öne bakan yüzü ve dokunun köşe sırasını hesaplar."""
        rot = np.eye(3)
        self.keys = [self._key(rot, self.first)]
        for t0, t1, axis, sign, content in self.turns:
            rot = turn(axis, sign * math.pi / 2) @ rot
            self.keys.append(self._key(rot, content))

    @staticmethod
    def _key(rot, content):
        normals = _NORMALS @ rot.T
        face = int(np.argmin(normals[:, 2]))
        corners = (_V[_FACES[face]] @ rot.T)[:, :2]
        tl = int(np.argmin(corners.sum(1)))
        order = [_FACES[face][(tl + k) % 4] for k in range(4)]
        nxt = (_V[order[1]] @ rot.T)[0]
        if nxt <= corners[tl, 0] + 1e-6:  # saat yönünün tersiyse çevir
            order = [order[0]] + order[1:][::-1]
        return rot, face, order, content

    def state(self, t):
        """(konum, dönüş matrisi, ölçek, gösterilen yüzler {yüz: (içerik, köşe sırası)})."""
        x, y = self.pos
        for t0, t1, (nx, ny) in self.moves:
            if t > t0:
                e = ease_in_out_cubic(clamp01((t - t0) / (t1 - t0)))
                x, y = x + (nx - x) * e, y + (ny - y) * e
        scale = ease_out_back(clamp01((t - self.pop) / 0.36)) if t < self.pop + 0.36 else 1.0

        rot, shown = self.keys[0][0], {self.keys[0][1]: self.keys[0]}
        for k, (t0, t1, axis, sign, _) in enumerate(self.turns):
            if t <= t0:
                break
            prev, cur = self.keys[k], self.keys[k + 1]
            u = clamp01((t - t0) / (t1 - t0))
            wobble = 0.0
            if t > t1:                          # yerine otururken küçük esneme
                s = t - t1
                wobble = math.radians(6) * math.sin(2 * math.pi * 6 * s) * math.exp(-s / 0.07)
            rot = turn(axis, sign * (math.pi / 2 * ease_in_out_cubic(u) + wobble)) @ prev[0]
            shown = {prev[1]: prev, cur[1]: cur} if u < 1 else {cur[1]: cur}
        return np.array([x, y, 0.0]), rot, scale, shown


def ease_out_back(u, s=1.9):
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


# ---------------------------------------------------------------- sahne

class NexDevScene(Scene):
    duration = DURATION

    def __init__(self, width=1920, height=1080, fps=60, seed=3):
        self.width, self.height, self.fps = width, height, fps
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.to_linear = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)
        self.black = skia.Typeface.MakeFromFile(str(FONTS / "Inter-Black.ttf"))
        contents = ["blank", *SKILLS, *LETTERS]
        self.textures = {c: _face_texture(c, self.black) for c in contents}
        rng = np.random.default_rng(seed)
        self._plan(rng)
        self.dust = [(rng.uniform(DUST_BOX[0], DUST_BOX[2]), rng.uniform(DUST_BOX[1], DUST_BOX[3]),
                      rng.uniform(-12, 12), rng.uniform(-18, -4), rng.uniform(1.0, 2.6), rng.uniform(0, 6.3),
                      YELLOW if rng.random() < 0.45 else WHITE, rng.uniform(0.12, 0.4)) for _ in range(70)]
        self.sparks = []
        for i in range(48):
            x = CX + (rng.uniform(0, 6) - 3) * GRID_PITCH
            ang = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(250, 700)
            self.sparks.append((x, CY + rng.uniform(-60, 60), math.cos(ang) * speed * 1.3,
                                math.sin(ang) * speed, rng.uniform(4, 10), rng.uniform(-400, 400),
                                rng.uniform(0.4, 0.85), YELLOW if x > CX else WHITE))
        self._logo()

    def _plan(self, rng):
        row_y = CY
        grid = [(CX + (i - 2.5) * GRID_PITCH, CY) for i in range(6)]
        self.cubes = []
        for i in range(6):
            if i < 5:
                cube = Cube((CX + (i - 2) * ROW_PITCH, row_y), 0.2 + 0.13 * i, "blank")
                cube.turns.append((cube.pop, cube.pop + 0.42, "x", -1, SKILLS[i]))    # takla ile belir
                t = T_WAVE + 0.07 * i                                                  # dalga
                cube.turns.append((t, t + 0.34, "y", 1 if i % 2 else -1, SKILLS[i]))
            else:
                cube = Cube((grid[5][0] + 420, grid[5][1]), 3.0, SKILLS[rng.integers(5)])
            # Rubik karışması: sağ/sol/ileri/geri dönüşler, sonra harf çözülür
            wave = 0.045 * i
            scramble = [SKILLS[(i + k + 1) % 5] for k in range(2)]
            plan = [(2.85, 0.42, "y" if i % 2 else "x", 1 if i < 3 else -1, scramble[0]),
                    (3.42, 0.34, "x" if i % 2 else "y", -1 if i % 3 else 1, scramble[1]),
                    (3.98, 0.36, "y", 1 if i < 3 else -1, LETTERS[i])]
            for t0, dur, axis, sign, content in plan:
                if t0 + wave > cube.pop:
                    cube.turns.append((t0 + wave, t0 + wave + dur, axis, sign, content))
            cube.moves.append((2.85 + wave, 3.4 + wave, grid[i]))
            cube.finish()
            self.cubes.append(cube)

    def _logo(self):
        """Son logo: tek satır "NexDev" (Nex beyaz, Dev sarı), ekranda ortalanmış."""
        font = skia.Font(self.black, LOGO_SIZE)
        text = "".join(ch for ch, _ in LETTERS)
        glyphs = font.textToGlyphs(text)
        centers, bounds, x = [], [], 0.0
        for g, adv in zip(glyphs, font.getWidths(glyphs)):
            b = font.getPath(g).computeTightBounds()
            centers.append(x + (b.left() + b.right()) / 2)
            bounds.append((x + b.left(), x + b.right()))
            x += adv + LOGO_TRACK * LOGO_SIZE
        offset = CX - (bounds[0][0] + bounds[-1][1]) / 2
        self.logo = [(cx + offset, CY) for cx in centers]
        self.logo_box = (bounds[0][0] + offset, bounds[-1][1] + offset)
        self.letter_paths = [_letter_path(skia.Font(self.black, 100), ch) for ch, _ in LETTERS]

    # ------------------------------------------------------------ çizim

    def _draw_cubes(self, c, t, alpha, flash):
        items = []
        for cube in self.cubes:
            if t < cube.pop:
                continue
            pos, rot, scale, shown = cube.state(t)
            if scale <= 0.01:
                continue
            items.append((pos[2], pos, rot, scale * CUBE, shown))
        items.sort(key=lambda it: -it[0])
        sampling = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)
        src = [skia.Point(0, 0), skia.Point(TEX, 0), skia.Point(TEX, TEX), skia.Point(0, TEX)]
        for _, pos, rot, size, shown in items:
            verts = pos + size * _V @ rot.T
            screen = project(verts)
            normals = _NORMALS @ rot.T
            for f, face in enumerate(_FACES):
                center = verts[face].mean(0)
                if np.dot(normals[f], center - _CAM) >= 0:
                    continue
                shade = 0.55 + 0.6 * max(float(normals[f] @ LIGHT), 0.0)
                if f in shown:
                    _, _, order, content = shown[f]
                else:
                    order, content = face, "blank"
                m = skia.Matrix()
                m.setPolyToPoly(src, [skia.Point(*screen[v]) for v in order])
                c.save()
                c.concat(m)
                c.drawImageRect(self.textures[content], skia.Rect(0, 0, TEX, TEX), sampling,
                                skia.Paint(AntiAlias=True, Alphaf=alpha))
                dim = skia.Paint(AntiAlias=True, Color4f=grey(0, alpha * (1 - min(shade, 1.0))))
                c.drawRect(skia.Rect(0, 0, TEX, TEX), dim)
                c.drawRect(skia.Rect(0, 0, TEX, TEX),       # kenarlarda ince ışık çizgisi
                           skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=TEX * 0.014,
                                      Color4f=grey(1, alpha * 0.16 * shade)))
                if flash > 0.01:
                    c.drawRect(skia.Rect(0, 0, TEX, TEX),
                               skia.Paint(AntiAlias=True, Color4f=grey(1, 0.3 * flash * alpha),
                                          BlendMode=skia.BlendMode.kPlus))
                c.restore()

    def _draw_logo(self, c, t, fade_in):
        """Küpler erirken yüzlerdeki harflerin yerini alan, toplanıp logoya dönüşen düz harfler."""
        if fade_in <= 0:
            return
        # küpler tamamen kaybolduktan sonra harfler logoya toplanır (çift görüntü olmasın)
        e = ease_in_out_cubic(clamp01((t - T_MELT[0] - 0.18) / (T_MELT[1] - T_MELT[0])))
        near = FOCAL / (FOCAL - CUBE / 2)             # küpün ön yüzü kameraya biraz daha yakın
        for i, cube in enumerate(self.cubes):
            pos = cube.state(t)[0]
            start = (CX + (pos[0] - CX) * near, CY + (pos[1] - CY) * near)
            end = self.logo[i]
            x = start[0] + (end[0] - start[0]) * e
            y = start[1] + (end[1] - start[1]) * e
            size = LETTER_ON_CUBE * near + (LOGO_SIZE - LETTER_ON_CUBE * near) * e
            c.save()
            c.translate(x, y)
            c.scale(size / 100, size / 100)
            c.drawPath(self.letter_paths[i], skia.Paint(AntiAlias=True, Color4f=color(LETTERS[i][1], fade_in)))
            c.restore()

    def _draw_sparks(self, c, t):
        """Harfler çözüldüğünde küplerden saçılan küçük sarı ve beyaz kareler."""
        d = t - T_SNAP
        if d < 0 or d > 0.9:
            return
        paint = skia.Paint(AntiAlias=True)
        for x, y, vx, vy, size, spin, life, rgb in self.sparks:
            if d > life:
                continue
            u = d / life
            travel = 0.25 * (1 - math.exp(-d / 0.25))
            h = size * (1 - 0.6 * u) / 2
            paint.setColor4f(color(rgb, 0.9 * (1 - u) ** 1.5))
            c.save()
            c.translate(x + vx * travel, y + vy * travel)
            c.rotate(spin * d)
            c.drawRect(skia.Rect(-h, -h, h, h), paint)
            c.restore()

    def _draw_dust(self, c, t):
        """Arka planda, ortada süzülen ince toz parçacıkları (köşelere hiç gitmez)."""
        a = clamp01(t / 0.6)
        if a <= 0:
            return
        paint = skia.Paint(AntiAlias=True)
        for x, y, vx, vy, r, phase, rgb, depth in self.dust:
            px = DUST_BOX[0] + (x + vx * t - DUST_BOX[0]) % (DUST_BOX[2] - DUST_BOX[0])
            py = DUST_BOX[1] + (y + vy * t - DUST_BOX[1]) % (DUST_BOX[3] - DUST_BOX[1])
            edge = min(px - DUST_BOX[0], DUST_BOX[2] - px, py - DUST_BOX[1], DUST_BOX[3] - py)
            twinkle = 0.55 + 0.45 * math.sin(2 * math.pi * 0.7 * t + phase)
            paint.setColor4f(color(rgb, a * depth * twinkle * clamp01(edge / 80)))
            c.drawCircle(px, py, r, paint)

    def _draw_pop_rings(self, c, t):
        """Her küp belirdiğinde genişleyip sönen sarı kare halka."""
        for cube in self.cubes:
            u = (t - cube.pop - 0.08) / 0.45
            if not 0 <= u <= 1:
                continue
            x, y = cube.state(t)[0][:2]
            half = CUBE * (0.55 + 0.35 * (1 - (1 - u) ** 3))
            c.drawRect(skia.Rect(x - half, y - half, x + half, y + half),
                       skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3 * (1 - u) + 0.5,
                                  Color4f=color(YELLOW, 0.55 * (1 - u) ** 2)))

    def _draw_snap_light(self, c, t):
        """Harfler çözüldüğünde: yatay ışık çizgisi ve sıcak bir parlama."""
        d = t - T_SNAP
        if d < 0 or d > 0.8:
            return
        u = d / 0.8
        width = 1500 * (1 - (1 - min(d / 0.25, 1)) ** 3)
        fade = (1 - u) ** 2
        streak = skia.GradientShader.MakeLinear(
            [skia.Point(CX - width / 2, CY), skia.Point(CX + width / 2, CY)],
            [color(YELLOW, 0).toColor(), color((1, 0.95, 0.85), fade).toColor(), color(YELLOW, 0).toColor()])
        for h, blur in ((2.5, 0), (14, 10)):
            paint = skia.Paint(AntiAlias=True, Shader=streak, BlendMode=skia.BlendMode.kPlus)
            if blur:
                paint.setImageFilter(skia.ImageFilters.Blur(blur, blur))
            c.drawRect(skia.Rect(CX - width / 2, CY - h / 2, CX + width / 2, CY + h / 2), paint)
        glow = skia.GradientShader.MakeRadial(
            skia.Point(CX, CY), 520, [color(YELLOW, 0.35 * fade).toColor(), color(YELLOW, 0).toColor()])
        c.drawCircle(CX, CY, 520, skia.Paint(Shader=glow, BlendMode=skia.BlendMode.kPlus))

    def _draw_backlight(self, c, t):
        """Final logonun arkasındaki yumuşak, hafifçe nefes alan sarı hale."""
        a = clamp01((t - T_MELT[0] - 0.2) / 0.6)
        if a <= 0:
            return
        a *= 0.16 + 0.04 * math.sin(2 * math.pi * 0.8 * t)
        left, right = self.logo_box
        mid = (left + right) / 2
        shader = skia.GradientShader.MakeRadial(
            skia.Point(0, 0), 1, [color(YELLOW, a).toColor(), color(YELLOW, 0).toColor()])
        c.save()
        c.translate(mid, CY)
        c.scale((right - left) * 0.75, 190)
        c.drawCircle(0, 0, 1, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kPlus))
        c.restore()

    def _draw_reflection(self, c, t, cube_alpha, flash, logo_alpha):
        """Küplerin ve logonun altta, zeminde silik yansıması."""
        floor = CY + CUBE / 2 + 16
        box = skia.Rect(CX - 900, floor, CX + 900, floor + 240)
        c.saveLayer(box, skia.Paint(Alphaf=0.16))
        c.save()
        c.translate(0, 2 * floor)
        c.scale(1, -1)
        if cube_alpha > 0.003:
            self._draw_cubes(c, t, cube_alpha, flash)
        self._draw_logo(c, t, logo_alpha)
        c.restore()
        mask = skia.GradientShader.MakeLinear(
            [skia.Point(0, floor), skia.Point(0, floor + 200)],
            [grey(1, 1).toColor(), grey(1, 0).toColor()])
        c.drawRect(box, skia.Paint(Shader=mask, BlendMode=skia.BlendMode.kDstIn))
        c.restore()

    def _draw_glint(self, c, t):
        u = clamp01((t - T_GLINT[0]) / (T_GLINT[1] - T_GLINT[0]))
        if not 0 < u < 1:
            return
        left, right = self.logo_box
        box = skia.Rect(left - 120, CY - 200, right + 120, CY + 200)
        c.saveLayer(box, skia.Paint(BlendMode=skia.BlendMode.kPlus, Alphaf=0.6 * math.sin(math.pi * u),
                                    ImageFilter=skia.ImageFilters.Blur(10, 10)))
        self._draw_logo(c, T_MELT[1] + 1, 1.0)
        center = left - 100 + (right - left + 200) * ease_in_out_sine(u)
        n = np.array([math.cos(math.radians(20)), math.sin(math.radians(20))])
        mid = np.array([center, CY])
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(*(mid - 70 * n)), skia.Point(*(mid + 70 * n))],
            [grey(1, 0).toColor(), grey(1, 1).toColor(), grey(1, 0).toColor()])
        c.drawRect(box, skia.Paint(Shader=shader, BlendMode=skia.BlendMode.kDstIn))
        c.restore()

    def draw(self, c, t):
        c.clear(skia.ColorBLACK)
        if t >= T_OUT[1]:
            return
        c.save()
        c.scale(self.k, self.k)
        zoom = 1 + 0.035 * ease_in_out_sine(clamp01(t / DURATION))
        fade = progress(t, T_OUT, ease_in_out_sine) if t > T_OUT[0] else 0.0
        zoom += 0.03 * fade
        d = t - T_SNAP
        shake = 6 * math.exp(-d / 0.08) if d >= 0 else 0.0
        c.translate(CX + shake * math.sin(2 * math.pi * 29 * d), CY + shake * math.sin(2 * math.pi * 23 * d + 1))
        c.scale(zoom, zoom)
        c.translate(-CX, -CY)
        if fade > 0:
            paint = skia.Paint(Alphaf=1 - fade)
            if fade > 0.02:
                paint.setImageFilter(skia.ImageFilters.Blur(7 * fade, 7 * fade))
            c.saveLayer(None, paint)

        melt = clamp01((t - T_MELT[0]) / (T_MELT[1] - T_MELT[0]))
        cube_alpha = 1 - ease_in_out_sine(clamp01(melt * 3.2 - 0.2))
        flash = pulse(d, 0.05) if d > 0 else 0.0
        logo_alpha = clamp01(melt * 5)
        self._draw_dust(c, t)
        self._draw_backlight(c, t)
        self._draw_reflection(c, t, cube_alpha, flash, logo_alpha)
        self._draw_pop_rings(c, t)
        if cube_alpha > 0.003:
            self._draw_cubes(c, t, cube_alpha, flash)
        self._draw_sparks(c, t)
        self._draw_logo(c, t, logo_alpha)
        self._draw_snap_light(c, t)
        self._draw_glint(c, t)
        if fade > 0:
            c.restore()
        c.restore()

    def _bloom(self, rgb):
        """Parlama yalnızca harflerin etrafına hale ekler; içlerindeki logo rengini değiştirmez.

        Toplamalı parlama sarıyı açıp soluklaştırırdı; "lighten" ile her pikselde
        özgün renk ile bulanık hâlin parlak olanı seçilir.
        """
        if not rgb.any():
            return rgb
        rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
        img = skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType)
        with self.surface as c:
            c.clear(skia.ColorBLACK)
            c.drawImage(img, 0, 0)
            for sigma, amount in ((12.0, 0.6), (40.0, 0.35)):
                c.saveLayer(None, skia.Paint(BlendMode=skia.BlendMode.kLighten))
                c.drawImage(img, 0, 0, skia.SamplingOptions(),
                            skia.Paint(Alphaf=amount,
                                       ImageFilter=skia.ImageFilters.Blur(sigma * self.k, sigma * self.k)))
                c.restore()
        return self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].copy()

    def samples(self, t):
        if 0.15 < t < T_MELT[1] + 0.2:
            return 8
        if T_OUT[0] < t < T_OUT[1]:
            return 2
        return 1

    # ------------------------------------------------------------ ses için olaylar

    def events(self):
        pops, flips = [], []
        for i, cube in enumerate(self.cubes):
            x = cube.pos[0] / W
            pops.append((cube.pop, x, i))
            for t0, t1, *_ in cube.turns:
                gx = (cube.state(t1)[0][0]) / W
                flips.append((t0, t1, gx))
        return dict(duration=DURATION, pops=pops, flips=flips, wave=T_WAVE, gather=(2.85, 3.5),
                    snap=T_SNAP, melt=T_MELT, glint=T_GLINT, out=T_OUT)
