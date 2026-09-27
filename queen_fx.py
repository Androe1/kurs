"""QUEEN lyric video - 2B çizim yardımcıları ve efektler (skia).

Her efekt zamanın saf fonksiyonudur: görünüşü yalnızca (t - t0) ve sabit bir tohumdan
hesaplanır. Kareler birbirinden bağımsızdır, bu yüzden video paralel render edilebilir.
Tüm ölçüler 1920x1080 tasarım alanındadır.
"""
import math

import numpy as np
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


def star(cx, cy, ro, ri, n=5, rot=0.0):
    pts = []
    for i in range(2 * n):
        a = rot + math.pi * i / n - math.pi / 2
        r = ro if i % 2 == 0 else ri
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


def burst(cx, cy, ri, ro, n, seed, rot=0.0, jitter=0.45):
    """Manga patlama yıldızı: uzunlukları rastgele sivri uçlar."""
    pts = []
    for i in range(2 * n):
        a = rot + math.pi * i / n
        if i % 2 == 0:
            r = ro * (1 - jitter * hash01(i, seed))
        else:
            r = ri * (0.85 + 0.3 * hash01(i, seed, 1))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


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


def flower(cx, cy, r, petals=5, rot=0.0):
    p = skia.Path()
    for i in range(petals):
        a = rot + 2 * math.pi * i / petals
        m = skia.Matrix()
        m.setRotate(math.degrees(a))
        m.postTranslate(cx, cy)
        e = skia.Path()
        e.addOval(skia.Rect(0.12 * r, -0.28 * r, r, 0.28 * r))
        e.transform(m)
        p.addPath(e)
    return p


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


def chevron(cx, cy, s, direction=1):
    d = direction
    return poly([(cx - 0.35 * s * d, cy - 0.5 * s), (cx + 0.15 * s * d, cy - 0.5 * s), (cx + 0.55 * s * d, cy),
                 (cx + 0.15 * s * d, cy + 0.5 * s), (cx - 0.35 * s * d, cy + 0.5 * s), (cx + 0.05 * s * d, cy)])


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


def hanko(c, cx, cy, r, rgb, a=1.0, rot=0.0):
    """Japon mühür damgası: çift halka, pürüzlü mürekkep."""
    c.save()
    c.translate(cx, cy)
    c.rotate(math.degrees(rot))
    c.drawCircle(0, 0, r, stroke(rgb, r * 0.11, a))
    c.drawCircle(0, 0, r * 0.8, stroke(rgb, r * 0.035, a))
    for i in range(14):                                   # mürekkep boşlukları
        ang = 2 * math.pi * hash01(i, 7)
        rr = r * (0.94 + 0.06 * hash01(i, 8))
        c.drawCircle(rr * math.cos(ang), rr * math.sin(ang), r * 0.035 * (0.5 + hash01(i, 9)),
                     fill(INK, a * 0.9))
    c.restore()


# ---------------------------------------------------------------- efektler

def shockwave(c, t, t0, x, y, rmax, rgb, dur=0.5, width=26.0, a=1.0):
    u = (t - t0) / dur
    if not 0 <= u < 1:
        return
    r = rmax * ease_out(u)
    c.drawCircle(x, y, r, stroke(rgb, width * (1 - u) + 1, a * (1 - u) ** 1.5))


def speedlines(c, cx, cy, n, r_in, r_out, rgb, a, seed, width=14.0, t=0.0):
    """Merkeze doğru incelen manga hız çizgileri."""
    p = skia.Path()
    for i in range(n):
        ang = 2 * math.pi * (i + hash01(i, seed)) / n + t * 0.15
        ri = r_in * (1 + 0.6 * hash01(i, seed, int(t * 30)))
        w = width * (0.4 + hash01(i, seed, 3)) / 2
        ca, sa = math.cos(ang), math.sin(ang)
        p.moveTo(cx + ri * ca, cy + ri * sa)
        p.lineTo(cx + r_out * ca - w * sa, cy + r_out * sa + w * ca)
        p.lineTo(cx + r_out * ca + w * sa, cy + r_out * sa - w * ca)
        p.close()
    c.drawPath(p, fill(rgb, a))


def debris(c, t, t0, x, y, n, speed, life, palette, seed, size=14.0, gravity=900.0):
    """Patlamadan saçılan 2B kırıklar (üçgen/dörtgen), sürtünme ve yerçekimiyle."""
    dt = t - t0
    if dt < 0 or dt > life * 1.6:
        return
    drag = 3.2
    for i in range(n):
        ang = 2 * math.pi * hash01(i, seed)
        v = speed * (0.3 + 0.9 * hash01(i, seed, 1))
        k = (1 - math.exp(-drag * dt)) / drag              # sürtünmeli yol
        px = x + math.cos(ang) * v * k
        py = y + math.sin(ang) * v * k + 0.5 * gravity * dt * dt * 0.35
        li = life * (0.5 + hash01(i, seed, 2))
        fade = 1 - span(dt, 0.25 * li, li)
        if fade <= 0:
            continue
        s = size * (0.5 + hash01(i, seed, 3)) * (1 - 0.5 * dt / li)
        rot = hash01(i, seed, 4) * 6.28 + dt * (hash01(i, seed, 5) - 0.5) * 20
        rgb = palette[i % len(palette)]
        c.save()
        c.translate(px, py)
        c.rotate(math.degrees(rot))
        if i % 3 == 0:
            c.drawPath(poly([(-s, -s * 0.6), (s, 0), (-s * 0.5, s * 0.7)]), fill(rgb, fade))
        elif i % 3 == 1:
            c.drawRect(skia.Rect(-s * 0.9, -s * 0.25, s * 0.9, s * 0.25), fill(rgb, fade))
        else:
            c.drawPath(sparkle(0, 0, s * 1.1), fill(rgb, fade))
        c.restore()


def explosion(c, t, t0, x, y, size, palette, seed, power=3):
    """Çok katmanlı 2B patlama: ışık diski, manga yıldızı, şok dalgaları, kıvılcım ve kırıklar."""
    dt = t - t0
    if dt < 0 or dt > 1.8:
        return
    main, second = palette[0], palette[1 % len(palette)]
    # parlayan çekirdek
    if dt < 0.35:
        u = dt / 0.35
        r = size * (0.25 + 0.9 * ease_out(u))
        c.drawCircle(x, y, r * 1.3, fill(main, 0.55 * (1 - u), blur=size * 0.18, blend=ADD))
        c.drawCircle(x, y, r * 0.8, fill(WHITE, (1 - u) ** 2))
    # manga yıldızı (iki katman, dönük)
    if dt < 0.3:
        u = dt / 0.3
        s = size * (0.5 + 1.1 * ease_out(u))
        a = 1 - u ** 2
        c.drawPath(burst(x, y, s * 0.45, s * 1.25, 14, seed, rot=seed), fill(main, a))
        c.drawPath(burst(x, y, s * 0.3, s * 0.85, 11, seed + 1, rot=seed + 0.2), fill(WHITE, a))
    # şok dalgaları
    shockwave(c, t, t0, x, y, size * 2.6, WHITE, dur=0.45, width=size * 0.14)
    shockwave(c, t, t0 + 0.05, x, y, size * 3.4, main, dur=0.6, width=size * 0.09)
    if power >= 4:
        shockwave(c, t, t0 + 0.1, x, y, size * 5.0, second, dur=0.8, width=size * 0.07)
    # ışınsal kıvılcım çizgileri
    if dt < 0.5:
        u = dt / 0.5
        n = 18 if power >= 3 else 10
        for i in range(n):
            ang = 2 * math.pi * (i + hash01(i, seed, 11)) / n
            r0 = size * (0.4 + 2.6 * ease_out(u))
            r1 = r0 + size * (0.5 + 0.8 * hash01(i, seed, 12)) * (1 - u)
            c.drawLine(x + r0 * math.cos(ang), y + r0 * math.sin(ang), x + r1 * math.cos(ang), y + r1 * math.sin(ang),
                       stroke(second if i % 2 else WHITE, size * 0.05 * (1 - u) + 1, 1 - u))
    # kırıklar ve parıltılar
    debris(c, t, t0, x, y, 26 if power >= 3 else 14, size * 5.5, 1.1, palette + (WHITE,), seed, size=size * 0.09)


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


def pattern_image(kind, size=64, rgb=WHITE):
    """Döşenebilir desen: 'dots' (tram), 'stripes' (çapraz şerit), 'grid'."""
    surf = skia.Surface(size, size)
    with surf as c:
        c.clear(skia.Color4f(0, 0, 0, 0))
        if kind == "dots":
            r = size * 0.22
            for x, y in ((0, 0), (size, 0), (0, size), (size, size), (size / 2, size / 2)):
                c.drawCircle(x, y, r, fill(rgb))
        elif kind == "stripes":
            p = poly([(0, 0), (size * 0.5, 0), (0, size * 0.5)])
            p2 = poly([(size, size * 0.5), (size, size), (size * 0.5, size)])
            q = poly([(size * 0.5, 0), (size, 0), (size, size * 0.5), (size * 0.5, size), (0, size), (0, size * 0.5)])
            c.drawPath(q, fill(rgb))
            del p, p2
        elif kind == "grid":
            c.drawLine(0, 0, size, 0, stroke(rgb, 2))
            c.drawLine(0, 0, 0, size, stroke(rgb, 2))
    return surf.makeImageSnapshot()


def tiled(c, image, rgb, a, scale=1.0, rot=0.0, dx=0.0, dy=0.0, rect=None):
    """Desen görüntüsünü tüm alana döşer (renk ve saydamlıkla)."""
    m = skia.Matrix()
    m.setScale(scale, scale)
    m.postRotate(rot)
    m.postTranslate(dx, dy)
    shader = image.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat, skia.SamplingOptions(), m)
    p = skia.Paint(AntiAlias=True, Shader=shader)
    p.setColorFilter(skia.ColorFilters.Blend(col(rgb), skia.BlendMode.kSrcIn))
    p.setAlphaf(clamp01(a))
    c.drawRect(rect or skia.Rect(-200, -200, W + 200, H + 200), p)
