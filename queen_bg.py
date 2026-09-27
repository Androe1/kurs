"""QUEEN lyric video - sahne arka planları (modern, minimal, 2B).

Görsel dil: koyu degrade zeminler, sahne başına tek vurgu rengi, ince çizgiler, yumuşak
ışık küreleri, seyrek parçacıklar. Tram noktası, kalın kontur, manga yıldızı yok.
Dansçılar ekranın alt yarısında durur; zeminde sahnenin rengiyle hafif bir ışık halkası.

  signal   kırmızı / yeşil degrade ikiye bölünmüş ekran, nabız atan iki ışık küresi
  storm    mor fırtına göğü, ince yağmur, yumuşak bulutlar, şimşekler
  scar     kızıl degrade, parlayan ince pençe çizikleri, ince çizgi kalpler
  glare    sıcak altın ışık, dört köşeli parıltılar, yatay lens parlamaları
  chase    camgöbeği / pembe degrade, hızla akan ince çizgiler
  robe     yarı saydam kurdeleler, tüyler
  yura     dalgalanan ince çizgiler, kabarcıklar
  lovehate pembe / koyu bölünme, ince çizgi kalpler ve çarpılar
  swallow  dönen ince halkalar, merkeze çekilen parçacıklar
  answer   ince ızgara, soru işaretleri, şimşek, doğru cevap halkası
  bloom    sıcak degrade, bokeh ışıkları, uçuşan yapraklar
  moon     gece göğü, yarılan bulutlar, parlayan ay, dans halkaları
  tonight  konser ışıkları, lazerler, ses halkaları
"""
import math

import skia

from queen_fx import (ADD, BLUE, CX, CY, CYAN, GOLD, GREEN, H, INK, LIME, MOON, ORANGE, PINK, RAINBOW, RED, VIOLET,
                      W, WHITE, clamp01, col, decay, ease_in, ease_out, ease_out_back, fill, hash01, heart, lerp,
                      lightning, mix, noise, poly, span, sparkle, stroke)


def linear(c, x0, y0, x1, y1, colors, pos=None, rect=None, blend=None, alpha=1.0):
    shader = skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)],
                                            [col(cc, alpha).toColor() for cc in colors], pos)
    p = skia.Paint(AntiAlias=True, Shader=shader)
    if blend is not None:
        p.setBlendMode(blend)
    c.drawRect(rect or skia.Rect(-300, -300, W + 300, H + 300), p)


def glow(c, x, y, r, rgb, a, blend=ADD):
    """Radyal degrade ile yumuşak ışık küresi."""
    if a <= 0.003 or r <= 1:
        return
    shader = skia.GradientShader.MakeRadial(skia.Point(x, y), r, [col(rgb, a).toColor(), col(rgb, a * 0.3).toColor(),
                                                                   col(rgb, 0).toColor()], [0.0, 0.4, 1.0])
    p = skia.Paint(AntiAlias=True, Shader=shader)
    p.setBlendMode(blend)
    c.drawCircle(x, y, r, p)


def soft_cloud(c, x, y, s, rgb, a, seed):
    """Yumuşak kenarlı bulut: üst üste degrade daireler."""
    for i in range(6):
        ox = (i - 2.5) * 0.3 * s + (hash01(i, seed) - 0.5) * 0.2 * s
        oy = -0.12 * s * math.sin(math.pi * i / 5) * (0.5 + hash01(i, seed, 1))
        r = s * (0.3 + 0.12 * hash01(i, seed, 2))
        shader = skia.GradientShader.MakeRadial(skia.Point(x + ox, y + oy), r,
                                                [col(rgb, a).toColor(), col(rgb, a * 0.85).toColor(),
                                                 col(rgb, 0).toColor()], [0.0, 0.7, 1.0])
        c.drawCircle(x + ox, y + oy, r, skia.Paint(AntiAlias=True, Shader=shader))


def dot_grid(c, rgb, a, step=64, r=1.6, dx=0.0, dy=0.0):
    """Seyrek, küçük nokta ızgarası (tram değil; ince doku)."""
    if a <= 0.005:
        return
    p = skia.Path()
    x0 = dx % step - step
    y0 = dy % step - step
    y = y0
    while y < H + step:
        x = x0
        while x < W + step:
            p.addCircle(x, y, r)
            x += step
        y += step
    c.drawPath(p, fill(rgb, a))


def streaks(c, t, n, rgb, a, speed, seed, y0=0, y1=H, length=(80, 260), width=2.0, direction=1):
    """Yatay akan ince ışık çizgileri."""
    path = skia.Path()
    for i in range(n):
        y = y0 + (y1 - y0) * hash01(i, seed)
        ln = length[0] + (length[1] - length[0]) * hash01(i, seed, 1)
        sp = speed * (0.6 + 0.8 * hash01(i, seed, 2))
        x = (hash01(i, seed, 3) * (W + 800) + direction * t * sp) % (W + 800) - 400
        path.moveTo(x, y)
        path.lineTo(x - direction * ln, y)
    c.drawPath(path, stroke(rgb, width, a))


def floor_glow(c, t, rgb, a=0.35):
    """Dansçıların bastığı zeminde yumuşak ışık halkası ve ince ufuk çizgisi."""
    shader = skia.GradientShader.MakeRadial(skia.Point(CX, 1045), 900, [col(rgb, a).toColor(), col(rgb, 0).toColor()])
    p = skia.Paint(AntiAlias=True, Shader=shader)
    p.setBlendMode(ADD)
    c.save()
    c.scale(1.0, 0.18)
    c.translate(0, 1045 / 0.18 - 1045)
    c.drawCircle(CX, 1045, 900, p)
    c.restore()


# ---------------------------------------------------------------- sahneler

def paint_boot(S, c, t):
    c.clear(col(INK))
    u = span(t, 0.08, 0.40)
    v = ease_in(span(t, 0.40, 0.488))
    w = W * ease_out(u)
    h = 2 + v * H
    if u > 0:
        c.drawRect(skia.Rect(CX - w / 2, CY - h / 2, CX + w / 2, CY + h / 2), fill(WHITE, 0.9))
        glow(c, CX, CY, 200 + 700 * v, CYAN, 0.3 * u)


def intro_line(t):
    for i, end in enumerate((4.10, 7.24, 10.98)):
        if t < end:
            return i
    return 3


def paint_signal(S, c, t):
    li = intro_line(t)
    stop = 12.376 <= t < 14.071
    band = t >= 7.268
    p = S.beat_pulse(t)
    lean_ = (1, -1, 1, 0)[li] + 0.8 * math.sin(t * 2.1) * (li == 3)
    split = CX - lean_ * 180 + 50 * math.sin(t * 1.1)
    tilt = 220
    k = 0.08 if stop else 1.0
    red_a = mix(INK, (0.3, 0.02, 0.07), k)
    red_b = mix(INK, (0.1, 0.0, 0.03), k)
    grn_a = mix(INK, (0.0, 0.2, 0.12), k)
    grn_b = mix(INK, (0.0, 0.06, 0.05), k)
    c.save()
    c.clipPath(poly([(-300, -300), (split + tilt, -300), (split - tilt, H + 300), (-300, H + 300)]), doAntiAlias=True)
    linear(c, 0, 0, split, H, [red_a, red_b])
    c.restore()
    c.save()
    c.clipPath(poly([(split + tilt, -300), (W + 300, -300), (W + 300, H + 300), (split - tilt, H + 300)]), doAntiAlias=True)
    linear(c, W, 0, split, H, [grn_a, grn_b])
    c.restore()
    dot_grid(c, WHITE, 0.05 if not stop else 0.02, step=56, r=1.4, dx=t * 8)
    # iki "lamba": vuruşta nabız atan ışık küreleri
    bi = S.beat_index(t)
    red_on = 0.35 + 0.65 * (bi % 2 == 0) * p
    grn_on = 0.35 + 0.65 * (bi % 2 == 1) * p
    glow(c, split - 620, 330, 520, RED, 0.28 * red_on * (0.6 if stop else 1))
    glow(c, split + 620, 700, 520, GREEN, 0.24 * grn_on * (0.6 if stop else 1))
    # bölünme çizgisi: ince, parlayan
    c.drawLine(split + tilt, -300, split - tilt, H + 300, stroke(WHITE, 2.0, 0.85))
    c.drawLine(split + tilt, -300, split - tilt, H + 300, stroke(WHITE, 14.0, 0.12, blur=8))
    if band and not stop:
        streaks(c, t, 24, WHITE, 0.08 + 0.08 * p, 900, seed=31, y0=80, y1=H - 80)
    for th, rgb in ((12.771, RED), (13.32, GREEN)):
        e = decay(t, th, 0.2)
        if e > 0.01:
            c.drawPaint(fill(rgb, 0.55 * e))
    if 13.63 <= t < 14.071:
        u = span(t, 13.63, 14.071)
        for k2 in range(3):
            r = lerp(1300, 10, ease_in(clamp01(u * 1.1 - 0.05 * k2)))
            c.drawCircle(CX, CY, r, stroke(WHITE, 2 + 6 * u, 0.7 * u))
    floor_glow(c, t, RED if li % 2 == 0 else GREEN, 0.25)


def paint_storm(S, c, t):
    t0 = 14.071
    bolts = ((14.071, 3), (15.72, 2), (17.438, 3), (19.11, 2), (16.9, 1), (18.35, 1), (20.05, 1))
    sky = 0.0
    for th, pw in bolts:
        dt = t - th
        if 0 <= dt < 0.3:
            sky = max(sky, (1 - dt / 0.3) * (0.3 + 0.18 * pw) * (0.6 + 0.4 * (math.sin(dt * 80) > 0)))
    top = mix((0.08, 0.03, 0.18), (0.55, 0.5, 0.85), sky)
    mid = mix((0.03, 0.02, 0.08), (0.25, 0.22, 0.45), sky)
    linear(c, 0, 0, 0, H, [top, mid, INK], [0.0, 0.55, 1.0])
    for layer, (spd, yy, ss, shade) in enumerate(((30, 90, 520, 0.12), (70, 40, 620, 0.07), (130, 170, 440, 0.16))):
        for k in range(5):
            x = (k * 560 + 300 * layer - (t - t0) * spd) % (W + 1200) - 500
            rgb = mix((0.06, 0.03, 0.12), (0.5, 0.46, 0.8), sky * (0.5 + 0.25 * layer) + shade)
            soft_cloud(c, x, yy + 40 * hash01(k, layer), ss * (0.8 + 0.4 * hash01(k, layer, 3)), rgb, 0.9,
                       seed=k + 10 * layer)
    for i, (th, pw) in enumerate(bolts):
        x0 = W * (0.15 + 0.7 * hash01(i, 5))
        x1 = x0 + (hash01(i, 6) - 0.5) * 700
        lightning(c, t, th, x0, -20, x1, 250 + 450 * hash01(i, 7) + 200 * (pw == 3), seed=i * 13 + 1,
                  width=3 + 2 * pw, dur=0.2 + 0.08 * pw)
    rain = skia.Path()
    ang = math.radians(76)
    dx, dy = math.cos(ang), math.sin(ang)
    for i in range(150):
        sp = 1900 + 900 * hash01(i, 21)
        ln = 40 + 60 * hash01(i, 22)
        x = (hash01(i, 23) * (W + 600) + (t - t0) * sp * dx) % (W + 600) - 300
        y = (hash01(i, 24) * (H + 400) + (t - t0) * sp * dy) % (H + 400) - 200
        rain.moveTo(x, y)
        rain.lineTo(x + dx * ln, y + dy * ln)
    c.drawPath(rain, stroke((0.8, 0.8, 1.0), 1.4, 0.22 + 0.3 * sky))
    glow(c, CX, H + 150, 1000, VIOLET, 0.2 + 0.2 * S.beat_pulse(t))


def paint_scar(S, c, t):
    t0 = 20.735
    p = S.beat_pulse(t)
    linear(c, 0, 0, W, H, [(0.2, 0.0, 0.06), (0.08, 0.0, 0.04), INK], [0.0, 0.5, 1.0])
    glow(c, CX, 320, 900, (0.9, 0.1, 0.3), 0.18 + 0.1 * p)
    for j, th in enumerate((20.9, 21.41, 22.13, 23.93)):
        dt = t - th
        if dt < 0:
            continue
        reveal = ease_out(clamp01(dt / 0.12))
        fade = 0.2 + 0.8 * math.exp(-dt / 0.5)
        ang = math.radians(-24 + 48 * hash01(j, 3))
        cxj = W * (0.2 + 0.6 * hash01(j, 4))
        cyj = H * (0.2 + 0.35 * hash01(j, 5))
        for k in range(3):
            off = (k - 1) * 46
            path = skia.Path()
            n = 16
            for s_i in range(n + 1):
                s = s_i / n * reveal
                x = cxj + (s - 0.5) * 1500 * math.cos(ang) - off * math.sin(ang)
                y = cyj + (s - 0.5) * 1500 * math.sin(ang) + off * math.cos(ang) + 50 * math.sin(s * math.pi)
                path.moveTo(x, y) if s_i == 0 else path.lineTo(x, y)
            c.drawPath(path, stroke(PINK, 16, 0.3 * fade, blur=10, blend=ADD))
            c.drawPath(path, stroke(WHITE, 2.5, fade))
    for i in range(14):
        life = 3.2 + 2 * hash01(i, 31)
        ph = ((t - t0) / life + hash01(i, 32)) % 1.0
        x = W * hash01(i, 33) + 30 * math.sin(t * 2 + i)
        y = H - ph * (H + 100)
        s = 26 + 30 * hash01(i, 34)
        c.drawPath(heart(x, y, s, 0.2 * math.sin(t * 2 + i)), stroke(PINK, 2.0, 0.45 * math.sin(math.pi * ph)))
    floor_glow(c, t, PINK, 0.22)


def paint_glare(S, c, t):
    tg = 26.11
    g = ease_out(span(t, tg - 0.05, tg + 0.25))
    p = S.beat_pulse(t)
    linear(c, 0, 0, 0, H, [mix((0.08, 0.05, 0.0), (0.3, 0.14, 0.0), g), mix(INK, (0.12, 0.05, 0.0), g), INK],
           [0.0, 0.6, 1.0])
    glow(c, CX, 360, 950, mix(GOLD, ORANGE, g), 0.14 + 0.16 * g + 0.08 * p)
    for i in range(40):
        x, y = W * hash01(i, 41), H * 0.85 * hash01(i, 42)
        tw = 0.5 + 0.5 * math.sin(t * (4 + 5 * hash01(i, 43)) + 6.28 * hash01(i, 44))
        r = (8 + 18 * hash01(i, 45)) * (0.4 + 0.8 * tw) * (1 + 1.6 * g)
        c.drawPath(sparkle(x, y, r, rot=g * 0.4 * (1 if i % 2 else -1), thin=0.12 - 0.06 * g),
                   fill(WHITE if i % 3 else GOLD, 0.25 + 0.6 * tw))
        if g > 0 and i % 3 == 0:
            c.drawRect(skia.Rect(x - 5 * r, y - 0.8, x + 5 * r, y + 0.8), fill(WHITE, 0.45 * g * tw))
    for j, th in enumerate((24.65, 25.40, 25.95, 26.11)):
        e = decay(t, th, 0.18)
        if e > 0.02:
            x, y = W * (0.2 + 0.6 * hash01(j, 47)), H * (0.15 + 0.4 * hash01(j, 48))
            c.drawRect(skia.Rect(-100, y - 1.5, W + 100, y + 1.5), fill(WHITE, 0.6 * e))
            glow(c, x, y, 380, GOLD, 0.5 * e)
    floor_glow(c, t, GOLD, 0.25)


def paint_chase(S, c, t):
    t0 = 27.72
    p = S.beat_pulse(t)
    split = CX + 260 * math.sin((t - t0) * 3)
    c.save()
    c.clipPath(poly([(-300, -300), (split + 380, -300), (split - 380, H + 300), (-300, H + 300)]), doAntiAlias=True)
    linear(c, 0, 0, split, H, [(0.0, 0.2, 0.28), (0.0, 0.07, 0.12)])
    c.restore()
    c.save()
    c.clipPath(poly([(split + 380, -300), (W + 300, -300), (W + 300, H + 300), (split - 380, H + 300)]), doAntiAlias=True)
    linear(c, W, 0, split, H, [(0.3, 0.02, 0.18), (0.1, 0.0, 0.08)])
    c.restore()
    c.drawLine(split + 380, -300, split - 380, H + 300, stroke(WHITE, 2, 0.8))
    streaks(c, t, 40, CYAN, 0.35, 2600, seed=71, y0=40, y1=H - 40, length=(120, 420), width=2.2)
    streaks(c, t, 26, PINK, 0.3, 2200, seed=72, y0=40, y1=H - 40, length=(100, 300), width=1.6, direction=-1)
    glow(c, CX, 400, 700, CYAN, 0.12 + 0.12 * p)
    floor_glow(c, t, CYAN, 0.28)


def paint_robe(S, c, t):
    t0 = 29.19
    linear(c, 0, 0, W, H, [(0.03, 0.14, 0.2), (0.12, 0.08, 0.24), (0.04, 0.02, 0.1)], [0.0, 0.55, 1.0])
    glow(c, CX, 300, 850, (0.7, 0.85, 1.0), 0.14)
    for r in range(5):
        amp = 70 + 40 * hash01(r, 51)
        kk = 0.004 + 0.002 * hash01(r, 52)
        w = 26 + 40 * hash01(r, 53)
        spd = 2.0 + 1.3 * hash01(r, 54)
        yb = 120 + r * 190
        top, bot = [], []
        for i in range(41):
            x = -100 + i * (W + 200) / 40
            ph = x * kk - (t - t0) * spd + r
            y = yb + amp * math.sin(ph)
            ww = w * (0.3 + 0.7 * (0.5 + 0.5 * math.sin(ph * 0.7 + r)))
            top.append((x, y - ww))
            bot.append((x, y + ww))
        rgb = (WHITE, (0.8, 0.72, 1.0), GOLD, CYAN, PINK)[r]
        c.drawPath(poly(top + bot[::-1]), fill(rgb, 0.12))
        c.drawPath(poly(top, close=False), stroke(rgb, 1.6, 0.55))
    for i in range(12):
        ph = ((t - t0) * 0.12 + hash01(i, 55)) % 1.0
        x = W * hash01(i, 56) + 100 * math.sin(t * 1.5 + i)
        y = -60 + ph * (H + 120)
        c.save()
        c.translate(x, y)
        c.rotate(40 * math.sin(t * 2 + i))
        c.drawOval(skia.Rect(-8, -34, 8, 34), stroke(WHITE, 1.5, 0.6))
        c.drawLine(0, -38, 0, 44, stroke(WHITE, 1.2, 0.6))
        c.restore()
    floor_glow(c, t, (0.7, 0.6, 1.0), 0.22)


def paint_yura(S, c, t):
    t0 = 31.60
    linear(c, 0, 0, 0, H, [(0.0, 0.16, 0.3), (0.0, 0.06, 0.18), (0.0, 0.02, 0.07)], [0.0, 0.5, 1.0])
    for r in range(10):
        yb = 50 + r * 110
        pts = []
        for i in range(41):
            x = -100 + i * (W + 200) / 40
            pts.append((x, yb + 28 * math.sin(x * 0.006 + (t - t0) * 2.4 + r * 0.8)))
        c.drawPath(poly(pts, close=False), stroke(mix(CYAN, BLUE, r / 9), 1.6, 0.35))
    for i in range(26):
        ph = ((t - t0) * (0.18 + 0.1 * hash01(i, 61)) + hash01(i, 62)) % 1.0
        x = W * hash01(i, 63) + 30 * math.sin(t * 3 + i)
        y = H + 40 - ph * (H + 80)
        r = 6 + 20 * hash01(i, 64)
        c.drawCircle(x, y, r, stroke(WHITE, 1.4, 0.45 * math.sin(math.pi * ph)))
    glow(c, CX, 260, 800, CYAN, 0.14)
    floor_glow(c, t, CYAN, 0.25)


def paint_lovehate(S, c, t):
    t0 = 34.366
    p = S.beat_pulse(t)
    split = CX + 150 * math.sin((t - t0) * 1.6)
    c.save()
    c.clipPath(poly([(-300, -300), (split + 260, -300), (split - 260, H + 300), (-300, H + 300)]), doAntiAlias=True)
    linear(c, 0, 0, split, H, [mix((0.34, 0.05, 0.2), (0.45, 0.08, 0.28), p), (0.12, 0.02, 0.08)])
    c.restore()
    c.save()
    c.clipPath(poly([(split + 260, -300), (W + 300, -300), (W + 300, H + 300), (split - 260, H + 300)]), doAntiAlias=True)
    linear(c, W, 0, split, H, [(0.1, 0.02, 0.05), INK])
    c.restore()
    c.drawLine(split + 260, -300, split - 260, H + 300, stroke(WHITE, 2, 0.8))
    for i in range(16):
        x0 = W * hash01(i, 71)
        y0 = ((hash01(i, 72) * H + (t - t0) * 50) % (H + 200)) - 100
        s = 30 + 30 * hash01(i, 73)
        if x0 < split:
            c.drawPath(heart(x0, y0, s * 1.2, 0.3 * math.sin(t * 2 + i)), stroke(PINK, 2.2, 0.5))
        else:
            c.save()
            c.translate(x0, y0)
            c.rotate(45 + 20 * math.sin(t + i))
            c.drawLine(-s * 0.4, 0, s * 0.4, 0, stroke(RED, 2.2, 0.55))
            c.drawLine(0, -s * 0.4, 0, s * 0.4, stroke(RED, 2.2, 0.55))
            c.restore()
    floor_glow(c, t, PINK, 0.25)


def paint_swallow(S, c, t):
    t0 = 37.50
    linear(c, 0, 0, 0, H, [(0.0, 0.12, 0.06), (0.0, 0.05, 0.03), INK], [0.0, 0.5, 1.0])
    cy = 330
    for k in range(7):
        r = 80 + k * 110
        eff = skia.DashPathEffect.Make([18.0 + 6 * k, 22.0], (t - t0) * (60 + 12 * k) * (1 if k % 2 else -1))
        pnt = stroke(mix(LIME, GREEN, k / 6), 1.8, 0.45 - 0.04 * k)
        pnt.setPathEffect(eff)
        c.drawCircle(CX, cy, r, pnt)
    glow(c, CX, cy, 420, LIME, 0.22)
    for i in range(60):
        life = 1.8 + hash01(i, 81)
        ph = ((t - t0) / life + hash01(i, 82)) % 1.0
        r = lerp(1000, 20, ease_in(ph))
        ang = 6.28 * hash01(i, 83) + ph * 4
        x, y = CX + r * math.cos(ang), cy + r * math.sin(ang) * 0.8
        c.drawCircle(x, y, 2.5 + 3 * (1 - ph), fill(WHITE if i % 3 else LIME, math.sin(math.pi * ph) * 0.8))
    floor_glow(c, t, LIME, 0.22)


def paint_answer(S, c, t):
    t0, tb, tc = 40.98, 41.82, 43.06
    ok = ease_out(span(t, tc - 0.02, tc + 0.2))
    linear(c, 0, 0, 0, H, [mix((0.02, 0.04, 0.14), (0.16, 0.03, 0.06), ok), INK])
    grid = skia.Path()
    off = (t - t0) * 40
    for k in range(-2, 26):
        x = k * 90 - off % 90
        grid.moveTo(x, 0)
        grid.lineTo(x, H)
    for k in range(-2, 14):
        y = k * 90 + (off * 0.5) % 90
        grid.moveTo(0, y)
        grid.lineTo(W, y)
    c.drawPath(grid, stroke(BLUE, 1.0, 0.18))
    font = S.font("montsemi", 90)
    for i in range(12):
        x = W * hash01(i, 91) + 16 * noise(t * 6, i)
        y = H * 0.75 * hash01(i, 92) + 16 * noise(t * 6, i + 50) - ok * 900 * (0.5 + hash01(i, 93))
        s = 0.5 + 0.8 * hash01(i, 94)
        c.save()
        c.translate(x, y)
        c.rotate(20 * noise(t * 2, i + 90))
        c.scale(s, s)
        c.drawString("?", -25, 30, font, fill(CYAN if i % 2 else WHITE, 0.35 * (1 - ok)))
        c.restore()
    e = decay(t, tb, 0.2)
    if e > 0.01:
        c.drawPaint(fill(CYAN, 0.25 * e))
    lightning(c, t, tb, 250, -10, 700, 600, seed=411, rgb=CYAN, width=4)
    lightning(c, t, tb + 0.05, W - 250, -10, W - 750, 560, seed=412, rgb=CYAN, width=3.5)
    if ok > 0:
        r = 300 * ease_out_back(clamp01((t - tc) / 0.22), 2.0)
        c.drawCircle(CX, 400, r, stroke(RED, 10, 0.9))
        c.drawCircle(CX, 400, r * 1.08, stroke(RED, 2, 0.5))
        f2 = S.font("montsemi", 30)
        c.drawString("C O R R E C T", 90, 110, f2, fill(RED, ok))
    floor_glow(c, t, mix(CYAN, RED, ok), 0.22)


def paint_bloom(S, c, t):
    t0, t1 = 44.56, 48.089
    u = span(t, t0, t1)
    linear(c, 0, 0, W, H, [mix((0.24, 0.02, 0.18), (0.45, 0.14, 0.04), u), mix((0.08, 0.0, 0.08), (0.2, 0.04, 0.06), u),
                           INK], [0.0, 0.6, 1.0])
    glow(c, CX, 320, 950, mix(PINK, GOLD, u), 0.16 + 0.2 * u)
    for i in range(34):                                   # bokeh
        tb = t0 + 3.3 * (i / 34) ** 0.8
        a = ease_out(clamp01((t - tb) / 0.5))
        if a <= 0:
            continue
        x, y = W * hash01(i, 101), H * 0.8 * hash01(i, 102)
        r = (30 + 80 * hash01(i, 103)) * a
        rgb = RAINBOW[i % len(RAINBOW)]
        c.drawCircle(x, y, r, fill(rgb, 0.16))
        c.drawCircle(x, y, r, stroke(rgb, 1.5, 0.45))
    for i in range(36):
        ph = ((t - t0) * 0.35 + hash01(i, 105)) % 1.0
        x = W * hash01(i, 106) + 150 * math.sin(t * 1.3 + i)
        y = -40 + ph * (H + 80)
        c.save()
        c.translate(x, y)
        c.rotate(t * 120 + i * 20)
        c.drawOval(skia.Rect(-10, -5, 10, 5), fill(PINK if i % 2 else WHITE, 0.6))
        c.restore()
    if t > 47.55:
        v = span(t, 47.55, t1)
        for k2 in range(3):
            r = lerp(1300, 10, ease_in(clamp01(v * 1.1 - 0.05 * k2)))
            c.drawCircle(CX, CY, r, stroke(WHITE, 2 + 6 * v, 0.7 * v))
    floor_glow(c, t, mix(PINK, GOLD, u), 0.28)


MOON_X, MOON_Y, MOON_R = 1480, 250, 165


def paint_moon(S, c, t):
    t0, tsplit, tface, tdance = 48.089, 48.42, 50.40, 51.49
    p = S.beat_pulse(t)
    linear(c, 0, 0, 0, H, [(0.02, 0.03, 0.12), (0.04, 0.02, 0.15), (0.01, 0.0, 0.05)], [0.0, 0.6, 1.0])
    for i in range(110):
        x, y = W * hash01(i, 111), H * 0.8 * hash01(i, 112)
        tw = 0.5 + 0.5 * math.sin(t * (2 + 4 * hash01(i, 113)) + 6.28 * hash01(i, 114))
        c.drawCircle(x, y, 1.0 + 2.0 * hash01(i, 115) * tw, fill(WHITE, 0.25 + 0.6 * tw))
    face = ease_out(span(t, tface - 0.05, tface + 0.4))
    reveal = ease_out(span(t, tsplit - 0.03, tsplit + 0.55))
    glow(c, MOON_X, MOON_Y, MOON_R * (3.0 + 0.8 * face), (0.7, 0.8, 1.0), 0.2 + 0.25 * face + 0.08 * p)
    shader = skia.GradientShader.MakeRadial(skia.Point(MOON_X - MOON_R * 0.3, MOON_Y - MOON_R * 0.3), MOON_R * 1.5,
                                            [col(WHITE).toColor(), col(MOON).toColor(), col((0.85, 0.83, 0.78)).toColor()],
                                            [0.0, 0.5, 1.0])
    c.drawCircle(MOON_X, MOON_Y, MOON_R, skia.Paint(AntiAlias=True, Shader=shader))
    if t >= tdance - 0.2:
        d = ease_out(span(t, tdance - 0.2, tdance + 0.3))
        for k in range(3):
            r = MOON_R * (1.4 + 0.35 * k) + 10 * p
            eff = skia.DashPathEffect.Make([30.0, 22.0], (t - t0) * (120 if k % 2 else -120))
            pnt = stroke((PINK, CYAN, GOLD)[k], 2.2, 0.75 * d)
            pnt.setPathEffect(eff)
            c.drawCircle(MOON_X, MOON_Y, r, pnt)
    for side in (-1, 1):
        for k in range(3):
            x = MOON_X + side * (120 + 90 * k) + side * reveal * (900 + 200 * k)
            y = MOON_Y - 60 + 90 * k
            soft_cloud(c, x, y, 360 - 50 * k, (0.14 + 0.04 * k, 0.13 + 0.04 * k, 0.26 + 0.05 * k), 0.95, seed=k * 3 + side)
    for k in range(4):
        x = (k * 620 - (t - t0) * 50) % (W + 800) - 400
        soft_cloud(c, x, H - 150, 480, (0.06, 0.05, 0.16), 0.7, seed=40 + k)
    floor_glow(c, t, (0.6, 0.7, 1.0), 0.3)


def paint_tonight(S, c, t):
    t0, t_long = 54.86, 57.72
    p = S.beat_pulse(t)
    hgh = ease_in(span(t, 58.375, 60.093))
    linear(c, 0, 0, 0, H, [(0.05, 0.0, 0.1), (0.02, 0.0, 0.05), INK], [0.0, 0.55, 1.0])
    for i in range(9):
        bx = 120 + i * (W - 240) / 8
        ang = math.radians(-90 + 32 * math.sin(t * (1.1 + 0.3 * hash01(i, 131)) + i * 1.3))
        ln = 1500
        spread = math.radians(3 + 2 * hash01(i, 132))
        rgb = RAINBOW[(i + int((t - t0) * 2)) % len(RAINBOW)]
        tip0 = (bx + ln * math.cos(ang - spread), H + 60 + ln * math.sin(ang - spread))
        tip1 = (bx + ln * math.cos(ang + spread), H + 60 + ln * math.sin(ang + spread))
        shader = skia.GradientShader.MakeLinear([skia.Point(bx, H + 60),
                                                 skia.Point((tip0[0] + tip1[0]) / 2, (tip0[1] + tip1[1]) / 2)],
                                                [col(rgb, 0.38 + 0.2 * p).toColor(), col(rgb, 0).toColor()])
        pnt = skia.Paint(AntiAlias=True, Shader=shader)
        pnt.setBlendMode(ADD)
        c.drawPath(poly([(bx, H + 60), tip0, tip1]), pnt)
    for i in range(6):
        a = math.radians(20 + 140 * hash01(i, 133) + 30 * math.sin(t * 2 + i))
        x0 = W * hash01(i, 134)
        c.drawLine(x0, H, x0 + 2500 * math.cos(a), H - 2500 * math.sin(a),
                   stroke((PINK, CYAN, LIME)[i % 3], 1.5, 0.3 + 0.25 * p, blend=ADD))
    for j in range(6):
        ph = ((t - t0) * (1.2 + 1.8 * hgh) + j / 6) % 1.0
        if t >= t_long - 0.1 or j % 2 == 0:
            c.drawCircle(CX, 330, 60 + ph * 1100, stroke(RAINBOW[j % len(RAINBOW)], 3 * (1 - ph) + 1, 0.55 * (1 - ph)))
    glow(c, CX, H + 100, 1000, VIOLET, 0.3 + 0.2 * p + 0.3 * hgh)
    floor_glow(c, t, RAINBOW[int((t - t0) * 4) % len(RAINBOW)], 0.3)


def paint_end(S, c, t):
    c.clear(col(INK))


PAINTERS = {
    "boot": paint_boot, "signal": paint_signal, "storm": paint_storm, "scar": paint_scar, "glare": paint_glare,
    "chase": paint_chase, "robe": paint_robe, "yura": paint_yura, "lovehate": paint_lovehate,
    "swallow": paint_swallow, "answer": paint_answer, "bloom": paint_bloom, "moon": paint_moon,
    "tonight": paint_tonight, "end": paint_end,
}

# Dansçılardaki kenar ışığının rengi (sahnenin vurgusu)
ACCENTS = {
    "boot": WHITE, "signal": None, "storm": VIOLET, "scar": PINK, "glare": GOLD, "chase": CYAN,
    "robe": (0.75, 0.65, 1.0), "yura": CYAN, "lovehate": PINK, "swallow": LIME, "answer": CYAN, "bloom": GOLD,
    "moon": (0.65, 0.75, 1.0), "tonight": None, "end": WHITE,
}
