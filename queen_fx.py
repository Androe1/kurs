"""QUEEN lyric video - 2B çizim yardımcıları ve efektler (skia).

Her efekt zamanın saf fonksiyonudur: görünüşü yalnızca (t - t0) ve sabit bir tohumdan
hesaplanır. Kareler birbirinden bağımsızdır, bu yüzden video paralel render edilebilir.
Tüm ölçüler 1920x1080 tasarım alanındadır.
"""
import math

import skia

W, H = 1920, 1080
CX, CY = W / 2, H / 2

# Renkler (0-1 RGB)
INK = (0.035, 0.02, 0.06)
WHITE = (1.0, 1.0, 1.0)
RED = (1.0, 0.13, 0.25)
GREEN = (0.12, 1.0, 0.42)
GOLD = (1.0, 0.8, 0.18)
PINK = (1.0, 0.22, 0.62)
CYAN = (0.1, 0.88, 1.0)
VIOLET = (0.56, 0.3, 1.0)
ORANGE = (1.0, 0.48, 0.08)
LIME = (0.72, 1.0, 0.1)
BLUE = (0.2, 0.45, 1.0)
NIGHT = (0.03, 0.04, 0.13)
MOON = (1.0, 0.96, 0.84)
RAINBOW = (RED, ORANGE, GOLD, LIME, GREEN, CYAN, BLUE, VIOLET, PINK)


# ---------------------------------------------------------------- matematik

def clamp01(x):
    return min(max(x, 0.0), 1.0)


def lerp(a, b, u):
    return a + (b - a) * u


def mix(c0, c1, u):
    return tuple(lerp(a, b, u) for a, b in zip(c0, c1))


def span(t, a, b):
    return clamp01((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out(u):
    return 1 - (1 - u) ** 3


def ease_in(u):
    return u ** 3


def ease_in_out(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (2 - 2 * u) ** 3 / 2


def ease_out_back(u, s=1.9):
    u -= 1
    return 1 + u * u * ((s + 1) * u + s)


def ease_out_elastic(u):
    if u <= 0 or u >= 1:
        return clamp01(u)
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * 2 * math.pi / 3) + 1


def hash01(*keys):
    """Tekrarlanabilir sözde rastgele sayı [0, 1)."""
    x = 0.0
    for i, k in enumerate(keys):
        x += (k + 0.618 * i) * (12.9898 + 31.7 * i)
    s = math.sin(x) * 43758.5453
    return s - math.floor(s)


def noise(x, seed=0):
    """Yumuşak 1B değer gürültüsü [-1, 1]."""
    i = math.floor(x)
    f = x - i
    a, b = hash01(i, seed) * 2 - 1, hash01(i + 1, seed) * 2 - 1
    return a + (b - a) * f * f * (3 - 2 * f)


def decay(t, t0, tau):
    """t0'da 1 olan, sonra üstel sönen zarf (t0'dan önce 0)."""
    return math.exp(-(t - t0) / tau) if t >= t0 else 0.0


# ---------------------------------------------------------------- boya

def col(rgb, a=1.0):
    return skia.Color4f(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(clamp01(a)))


def fill(rgb, a=1.0, blur=0.0, blend=None):
    p = skia.Paint(AntiAlias=True, Color4f=col(rgb, a))
    if blur > 0.3:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    return p


def stroke(rgb, width, a=1.0, blur=0.0, blend=None, cap=skia.Paint.kRound_Cap):
    p = fill(rgb, a, blur, blend)
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(width)
    p.setStrokeCap(cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


ADD = skia.BlendMode.kPlus
SCREEN = skia.BlendMode.kScreen


# ---------------------------------------------------------------- şekiller

def poly(points, close=True):
    p = skia.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p




def sparkle(cx, cy, r, rot=0.0, thin=0.18):
    """Dört köşeli, kenarları içe kavisli parıltı."""
    p = skia.Path()
    tips = [(cx + r * math.cos(rot + k * math.pi / 2), cy + r * math.sin(rot + k * math.pi / 2)) for k in range(4)]
    p.moveTo(*tips[0])
    for k in range(1, 5):
        q = tips[k % 4]
        p.quadTo(cx + (tips[k - 1][0] + q[0] - 2 * cx) * thin, cy + (tips[k - 1][1] + q[1] - 2 * cy) * thin, *q)
    p.close()
    return p


def heart(cx, cy, s, rot=0.0):
    p = skia.Path()
    p.moveTo(0, 0.35)
    p.cubicTo(-0.55, -0.05, -0.5, -0.62, -0.02, -0.38)
    p.lineTo(0, -0.37)
    p.lineTo(0.02, -0.38)
    p.cubicTo(0.5, -0.62, 0.55, -0.05, 0, 0.35)
    p.close()
    m = skia.Matrix()
    m.setScale(s, s)
    m.postRotate(math.degrees(rot))
    m.postTranslate(cx, cy)
    p.transform(m)
    return p


def crown(cx, cy, s):
    pts = [(-0.5, 0.3), (-0.56, -0.28), (-0.27, 0.0), (0.0, -0.42), (0.27, 0.0), (0.56, -0.28), (0.5, 0.3)]
    return poly([(cx + x * s, cy + y * s) for x, y in pts])



def note(cx, cy, s):
    """Sekizlik nota."""
    p = skia.Path()
    head = skia.Path()
    head.addOval(skia.Rect(-0.3, -0.18, 0.12, 0.14))
    m = skia.Matrix()
    m.setRotate(-24)
    head.transform(m)
    p.addPath(head)
    p.addRect(skia.Rect(0.02, -0.95, 0.12, -0.02))
    p.moveTo(0.12, -0.95)
    p.cubicTo(0.2, -0.7, 0.55, -0.62, 0.38, -0.25)
    p.cubicTo(0.45, -0.55, 0.25, -0.62, 0.12, -0.7)
    p.close()
    m = skia.Matrix()
    m.setScale(s, s)
    m.postTranslate(cx, cy)
    p.transform(m)
    return p



def bolt_points(x0, y0, x1, y1, seed, depth=5, jag=0.22):
    """Orta nokta kaydırmalı şimşek çizgisi."""
    pts = [(x0, y0), (x1, y1)]
    amp = jag * math.hypot(x1 - x0, y1 - y0)
    for level in range(depth):
        out = [pts[0]]
        for i in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy) + 1e-9
            off = (hash01(seed, level, i) * 2 - 1) * amp
            out.append(((ax + bx) / 2 - dy / ln * off, (ay + by) / 2 + dx / ln * off))
            out.append(pts[i + 1])
        pts = out
        amp *= 0.55
    return pts



# ---------------------------------------------------------------- efektler

def shockwave(c, t, t0, x, y, rmax, rgb, dur=0.5, width=26.0, a=1.0):
    u = (t - t0) / dur
    if not 0 <= u < 1:
        return
    r = rmax * ease_out(u)
    c.drawCircle(x, y, r, stroke(rgb, width * (1 - u) + 1, a * (1 - u) ** 1.5))





def lightning(c, t, t0, x0, y0, x1, y1, seed, rgb=(0.75, 0.85, 1.0), dur=0.32, width=9.0):
    dt = t - t0
    if not 0 <= dt < dur:
        return 0.0
    flick = 1.0 if dt < 0.05 else (0.35 + 0.65 * (math.sin(dt * 90) > 0)) * (1 - dt / dur)
    pts = bolt_points(x0, y0, x1, y1, seed)
    path = poly(pts, close=False)
    c.drawPath(path, stroke(rgb, width * 3.5, flick * 0.5, blur=18, blend=ADD))
    c.drawPath(path, stroke(WHITE, width, flick))
    for b in range(3):                                   # dallar
        i = int(len(pts) * (0.25 + 0.2 * b))
        bx, by = pts[i]
        ang = math.atan2(y1 - y0, x1 - x0) + (0.6 if b % 2 else -0.6)
        ln = 0.25 * math.hypot(x1 - x0, y1 - y0)
        br = bolt_points(bx, by, bx + ln * math.cos(ang), by + ln * math.sin(ang), seed + 10 + b, depth=4)
        c.drawPath(poly(br, close=False), stroke(WHITE, width * 0.45, flick * 0.8))
    return flick




def flare_burst(c, t, t0, x, y, size, palette, seed, power=3):
    """Modern patlama: parlayan çekirdek, ince genişleyen halkalar, ışınsal kıvılcım çizgileri,
    sürtünmeyle yavaşlayan parlak parçacıklar. Manga yıldızı ve üçgen kırık yok."""
    dt = t - t0
    if dt < 0 or dt > 1.6:
        return
    main, second = palette[0], palette[1 % len(palette)]
    if dt < 0.45:                                          # çekirdek ışığı
        u = dt / 0.45
        r = size * (0.6 + 2.6 * ease_out(u))
        shader = skia.GradientShader.MakeRadial(skia.Point(x, y), r, [col(WHITE, (1 - u) ** 1.5).toColor(),
                                                                       col(main, 0.6 * (1 - u)).toColor(),
                                                                       col(main, 0).toColor()], [0.0, 0.25, 1.0])
        p = skia.Paint(AntiAlias=True, Shader=shader)
        p.setBlendMode(ADD)
        c.drawCircle(x, y, r, p)
    for k, (dl, dur, rmax, w) in enumerate(((0.0, 0.5, 3.2, 5.0), (0.06, 0.65, 4.4, 3.0), (0.12, 0.8, 5.6, 2.0))):
        if k == 2 and power < 4:
            break
        u = (dt - dl) / dur
        if 0 <= u < 1:
            c.drawCircle(x, y, size * rmax * ease_out(u), stroke(WHITE if k == 0 else (main, second)[k % 2],
                                                                  w * (1 - u) + 0.8, (1 - u) ** 1.3))
    if dt < 0.5:                                           # ışınsal kıvılcım çizgileri
        u = dt / 0.5
        n = 26 if power >= 3 else 14
        path = skia.Path()
        for i in range(n):
            ang = 2 * math.pi * (i + hash01(i, seed, 11)) / n
            r0 = size * (0.5 + 3.4 * ease_out(u))
            r1 = r0 + size * (0.6 + 1.2 * hash01(i, seed, 12)) * (1 - u)
            path.moveTo(x + r0 * math.cos(ang), y + r0 * math.sin(ang))
            path.lineTo(x + r1 * math.cos(ang), y + r1 * math.sin(ang))
        c.drawPath(path, stroke(WHITE, 2.2, 1 - u))
    drag = 3.0
    k_path = {}
    for i in range(34 if power >= 3 else 18):              # parlak parçacıklar
        ang = 2 * math.pi * hash01(i, seed, 21)
        v = size * 7 * (0.3 + 0.9 * hash01(i, seed, 22))
        kk = (1 - math.exp(-drag * dt)) / drag
        px, py = x + math.cos(ang) * v * kk, y + math.sin(ang) * v * kk + 120 * dt * dt
        life = 0.6 + 0.7 * hash01(i, seed, 23)
        a = 1 - span(dt, 0.3 * life, life)
        if a <= 0:
            continue
        rgb = (WHITE, main, second)[i % 3]
        k_path.setdefault((rgb, round(a, 2)), skia.Path()).addCircle(px, py, 2.0 + 3.0 * hash01(i, seed, 24) * (1 - dt))
    for (rgb, a), path in k_path.items():
        c.drawPath(path, fill(rgb, a))
