"""QUEEN lyric video - sahne arka planları (2B).

Her fonksiyon bir sahnenin arka planını ve o sahneye ait simgeleri çizer:
  signal   kırmızı/yeşil ikiye bölünmüş ekran, tram noktaları, trafik lambaları
  storm    mor fırtına göğü, yağmur, katmanlı bulutlar, şimşekler
  scar     kızıl zemin, pençe çizikleri, yükselen kalpler
  glare    altın parıltılar: önce yumuşak ve küçük, sonra keskin yıldız patlamaları
  chase    camgöbeği/pembe bölünme, hız çizgileri, akan oklar
  robe     uçuşan kurdeleler ve tüyler
  yura     dalgalanan şeritler, kabarcıklar
  lovehate kalpler ve çarpılar arasında zikzak bölünme
  swallow  dönen girdap, içine çekilen simgeler, oyun HP çubuğu
  answer   kayan ızgara, soru işaretleri, doğru cevap halkası
  bloom    ekranı saran açan çiçekler
  moon     gece göğü, yarılan bulutlar, dev ay
  tonight  konser sahnesi: hareketli ışık huzmeleri, ses halkaları
"""
import math

import skia

from queen_fx import (ADD, BLUE, CX, CY, CYAN, GOLD, GREEN, H, INK, LIME, MOON, NIGHT, ORANGE, PINK, RAINBOW,
                      RED, VIOLET, W, WHITE, burst, chevron, clamp01, col, crown, decay, ease_in, ease_in_out,
                      ease_out, ease_out_back, ease_out_elastic, fill, flower, hash01, heart, lerp, lightning, mix,
                      noise, note, poly, span, sparkle, speedlines, star, stroke, tiled)


def linear(c, x0, y0, x1, y1, colors, pos=None, rect=None, blend=None):
    shader = skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)],
                                            [col(*cc).toColor() if isinstance(cc[0], tuple) else col(cc).toColor()
                                             for cc in colors], pos)
    p = skia.Paint(AntiAlias=True, Shader=shader)
    if blend is not None:
        p.setBlendMode(blend)
    c.drawRect(rect or skia.Rect(-300, -300, W + 300, H + 300), p)


def glow(c, x, y, r, rgb, a, blend=ADD):
    """Radyal degrade ile ucuz parlama."""
    if a <= 0.003 or r <= 1:
        return
    shader = skia.GradientShader.MakeRadial(skia.Point(x, y), r, [col(rgb, a).toColor(), col(rgb, a * 0.35).toColor(),
                                                                   col(rgb, 0).toColor()], [0.0, 0.35, 1.0])
    p = skia.Paint(AntiAlias=True, Shader=shader)
    p.setBlendMode(blend)
    c.drawCircle(x, y, r, p)


def cloud(c, x, y, s, rgb, a, seed):
    """Düz renkli 2B bulut: üst üste daireler (saydamlık tek katmanda birleşir)."""
    c.saveLayerAlpha(None, int(255 * clamp01(a)))
    p = fill(rgb)
    for i in range(7):
        ox = (i - 3) * 0.3 * s + (hash01(i, seed) - 0.5) * 0.15 * s
        oy = -0.18 * s * math.sin(math.pi * i / 6) * (0.6 + 0.8 * hash01(i, seed, 1))
        r = s * (0.22 + 0.14 * math.sin(math.pi * i / 6) + 0.06 * hash01(i, seed, 2))
        c.drawCircle(x + ox, y + oy, r, p)
    c.drawRect(skia.Rect(x - 0.95 * s, y, x + 0.95 * s, y + 0.2 * s), p)
    c.restore()


def traffic_light(c, x, y, s, red_on, green_on, a=1.0):
    """Yatay trafik lambası: kırmızı, sarı, yeşil."""
    body = skia.RRect.MakeRectXY(skia.Rect(x - 1.6 * s, y - 0.62 * s, x + 1.6 * s, y + 0.62 * s), 0.3 * s, 0.3 * s)
    c.drawRRect(body, fill(INK, a))
    c.drawRRect(body, stroke(WHITE, 0.07 * s, a * 0.9))
    for k, (rgb, on) in enumerate(((RED, red_on), (GOLD, 0.0), (GREEN, green_on))):
        lx = x + (k - 1) * 1.05 * s
        c.drawCircle(lx, y, 0.4 * s, fill(mix(INK, rgb, 0.25 + 0.75 * on), a))
        if on > 0.02:
            glow(c, lx, y, 1.5 * s, rgb, 0.55 * on * a)
            c.drawCircle(lx - 0.12 * s, y - 0.12 * s, 0.1 * s, fill(WHITE, 0.7 * on * a))


# ---------------------------------------------------------------- sahneler

def paint_boot(S, c, t):
    c.clear(col(INK))
    u = span(t, 0.08, 0.40)
    v = ease_in(span(t, 0.40, 0.488))
    w = W * ease_out(u)
    h = 4 + v * H
    if u > 0:
        c.drawRect(skia.Rect(CX - w / 2, CY - h / 2, CX + w / 2, CY + h / 2), fill(WHITE, 0.9))
        glow(c, CX, CY, 260 + 600 * v, CYAN, 0.35 * u)


def intro_line(t):
    """0-14 sn arasında hangi 'Red or Green?' satırındayız (0-3)."""
    for i, end in enumerate((4.10, 7.24, 10.98)):
        if t < end:
            return i
    return 3


def paint_signal(S, c, t):
    li = intro_line(t)
    stop = 12.376 <= t < 14.071                     # durak: bas ve davul susar
    band = t >= 7.268                               # bas girdikten sonra daha yoğun
    p = S.beat_pulse(t)
    lean = (1, -1, 1, 0)[li]                        # hangi renk baskın (+1 kırmızı)
    lean_s = lean + 0.8 * math.sin(t * 2.1) * (li == 3)
    split = CX - lean_s * 230 + 60 * math.sin(t * 1.3)
    tilt = 240 + 60 * math.sin(t * 0.7)
    base = 0.34 + (0.14 if band else 0.06) * p
    if stop:
        base = 0.1
    red_bg, green_bg = mix(INK, RED, base), mix(INK, GREEN, base * 0.75)
    c.drawPath(poly([(-300, -300), (split + tilt, -300), (split - tilt, H + 300), (-300, H + 300)]), fill(red_bg))
    c.drawPath(poly([(split + tilt, -300), (W + 300, -300), (W + 300, H + 300), (split - tilt, H + 300)]), fill(green_bg))
    # tram noktaları ve kayan çapraz şeritler
    tiled(c, S.dots, INK, 0.45, scale=0.55, rot=45, dx=t * 12)
    if band and not stop:
        tiled(c, S.stripes, WHITE, 0.05 + 0.05 * p, scale=2.2, rot=0, dx=t * 420, dy=0)
    # bölünme çizgisi: sarı-siyah uyarı bandı
    c.save()
    edge = poly([(split + tilt - 34, -300), (split + tilt + 34, -300), (split - tilt + 34, H + 300), (split - tilt - 34, H + 300)])
    c.clipPath(edge, doAntiAlias=True)
    c.drawPaint(fill(GOLD, 0.9 if not stop else 0.35))
    tiled(c, S.stripes, INK, 0.95, scale=0.9, rot=0, dx=t * 160)
    c.restore()
    # köşelerde trafik lambaları (vuruşta yanıp söner)
    beat_i = S.beat_index(t)
    red_on = (beat_i % 2 == 0) * p + 0.25
    green_on = (beat_i % 2 == 1) * p + 0.25
    if not stop:
        traffic_light(c, 230, 120, 58, red_on, 0.15, 0.85)
        traffic_light(c, W - 230, 120, 58, 0.15, green_on, 0.85)
    # büyük renk flaşları (durak vuruşları)
    for th, rgb in ((12.771, RED), (13.32, GREEN)):
        e = decay(t, th, 0.22)
        if e > 0.01:
            c.drawPaint(fill(rgb, 0.75 * e))
            speedlines(c, CX, CY, 70, 260, 1400, INK, 0.5 * e, seed=int(th * 10), width=26)
    # patlama öncesi içe çöküş: hız çizgileri merkeze akar
    if 13.63 <= t < 14.071:
        u = span(t, 13.63, 14.071)
        speedlines(c, CX, CY, 90, lerp(900, 120, ease_in(u)), 1500, WHITE, 0.5 * u, seed=77, width=18, t=t)
        c.drawCircle(CX, CY, lerp(1300, 10, ease_in(u)), stroke(WHITE, 8 + 30 * u, u))


def paint_storm(S, c, t):
    t0 = 14.071
    bolts = ((14.071, 3), (15.72, 2), (17.438, 3), (19.11, 2), (16.9, 1), (18.35, 1), (20.05, 1))
    sky = 0.0
    for th, pw in bolts:
        dt = t - th
        if 0 <= dt < 0.3:
            sky = max(sky, (1 - dt / 0.3) * (0.35 + 0.2 * pw) * (0.6 + 0.4 * (math.sin(dt * 80) > 0)))
    p = S.beat_pulse(t)
    top = mix((0.13, 0.04, 0.27), (0.7, 0.62, 1.0), sky)
    mid = mix((0.05, 0.02, 0.12), (0.35, 0.3, 0.6), sky)
    linear(c, 0, 0, 0, H, [top, mid, INK], [0.0, 0.55, 1.0])
    # uzak ve yakın bulut katmanları
    for layer, (spd, yy, ss, shade) in enumerate(((40, 120, 420, 0.13), (90, 60, 520, 0.08), (160, 190, 360, 0.18))):
        for k in range(5):
            x = (k * 520 + 300 * layer - (t - t0) * spd) % (W + 1100) - 500
            rgb = mix((0.05, 0.02, 0.1), (0.5, 0.45, 0.8), sky * (0.5 + 0.5 * layer / 2) + shade)
            cloud(c, x, yy + 40 * hash01(k, layer), ss * (0.8 + 0.4 * hash01(k, layer, 3)), rgb, 0.95, seed=k + 10 * layer)
    # şimşekler
    for i, (th, pw) in enumerate(bolts):
        x0 = W * (0.15 + 0.7 * hash01(i, 5))
        x1 = x0 + (hash01(i, 6) - 0.5) * 700
        lightning(c, t, th, x0, -20, x1, 250 + 450 * hash01(i, 7) + 200 * (pw == 3), seed=i * 13 + 1,
                  width=6 + 3 * pw, dur=0.2 + 0.08 * pw)
    # yağmur
    rain = skia.Path()
    ang = math.radians(74)
    dx, dy = math.cos(ang), math.sin(ang)
    for i in range(170):
        sp = 1900 + 900 * hash01(i, 21)
        ln = 50 + 70 * hash01(i, 22)
        x = (hash01(i, 23) * (W + 600) + (t - t0) * sp * dx) % (W + 600) - 300
        y = (hash01(i, 24) * (H + 400) + (t - t0) * sp * dy) % (H + 400) - 200
        rain.moveTo(x, y)
        rain.lineTo(x + dx * ln, y + dy * ln)
    c.drawPath(rain, stroke((0.8, 0.8, 1.0), 2.2, 0.25 + 0.3 * sky))
    # zemin sisi ve vuruş nabzı
    glow(c, CX, H + 120, 900, VIOLET, 0.25 + 0.2 * p)
    tiled(c, S.dots, INK, 0.3, scale=0.5, rot=45)


def paint_scar(S, c, t):
    t0 = 20.735
    p = S.beat_pulse(t)
    linear(c, 0, 0, W, H, [(0.28, 0.0, 0.08), (0.12, 0.0, 0.05), INK], [0.0, 0.5, 1.0])
    glow(c, CX, CY, 900, (0.9, 0.05, 0.25), 0.25 + 0.15 * p)
    tiled(c, S.dots, PINK, 0.06, scale=0.6, rot=30)
    # pençe çizikleri: her vuruşta üç paralel eğri çizgi ekranı yırtar
    for j, th in enumerate((20.9, 21.41, 22.13, 23.93)):
        dt = t - th
        if dt < 0:
            continue
        reveal = ease_out(clamp01(dt / 0.12))
        fade = 0.25 + 0.75 * math.exp(-dt / 0.5)
        ang = math.radians(-28 + 56 * hash01(j, 3))
        cxj = W * (0.2 + 0.6 * hash01(j, 4))
        cyj = H * (0.25 + 0.5 * hash01(j, 5))
        for k in range(3):
            off = (k - 1) * 70
            path = skia.Path()
            n = 16
            for s_i in range(n + 1):
                s = s_i / n * reveal
                x = cxj + (s - 0.5) * 1500 * math.cos(ang) - off * math.sin(ang)
                y = cyj + (s - 0.5) * 1500 * math.sin(ang) + off * math.cos(ang) + 60 * math.sin(s * math.pi)
                if s_i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            c.drawPath(path, stroke(PINK, 34 * (1 - 0.4 * k / 2), 0.45 * fade, blur=16, blend=ADD))
            c.drawPath(path, stroke(WHITE, 9, fade))
    # yükselen kalpler
    for i in range(22):
        life = 3.2 + 2 * hash01(i, 31)
        ph = ((t - t0) / life + hash01(i, 32)) % 1.0
        x = W * hash01(i, 33) + 40 * math.sin(t * 2 + i)
        y = H + 80 - ph * (H + 200)
        s = 30 + 50 * hash01(i, 34)
        c.drawPath(heart(x, y, s, 0.3 * math.sin(t * 3 + i)), fill(PINK if i % 3 else RED, 0.35 * math.sin(math.pi * ph)))


def paint_glare(S, c, t):
    t0, tg = 24.52, 26.11
    g = ease_out(span(t, tg - 0.05, tg + 0.25))     # ikinci parça: keskin parıltılara geçiş
    p = S.beat_pulse(t)
    linear(c, 0, 0, 0, H, [mix((0.1, 0.06, 0.0), (0.45, 0.2, 0.0), g), mix(INK, (0.22, 0.08, 0.0), g), INK],
           [0.0, 0.6, 1.0])
    glow(c, CX, CY, 1000, mix(GOLD, ORANGE, g), 0.18 + 0.2 * g + 0.12 * p)
    # yumuşak parıltılar -> keskin yıldız patlamaları
    for i in range(46):
        x, y = W * hash01(i, 41), H * hash01(i, 42)
        tw = 0.5 + 0.5 * math.sin(t * (4 + 5 * hash01(i, 43)) + 6.28 * hash01(i, 44))
        if g < 1:
            r = (10 + 26 * hash01(i, 45)) * (0.4 + 0.8 * tw)
            c.drawPath(sparkle(x, y, r, rot=0.0), fill(WHITE if i % 3 else GOLD, (1 - g) * (0.3 + 0.7 * tw)))
        if g > 0:
            r = (30 + 60 * hash01(i, 46)) * (0.5 + 0.7 * tw) * g
            rot = t * (1.5 if i % 2 else -1.5)
            c.drawPath(star(x, y, r, r * 0.22, 4, rot), fill(GOLD if i % 2 else WHITE, g * (0.35 + 0.65 * tw)))
            c.drawRect(skia.Rect(x - 4 * r, y - 2, x + 4 * r, y + 2), fill(WHITE, 0.5 * g * tw))
    # zil vuruşlarında büyük parlama ışınları
    for j, th in enumerate((24.65, 25.40, 25.95, 26.11)):
        e = decay(t, th, 0.18)
        if e > 0.02:
            x, y = W * (0.2 + 0.6 * hash01(j, 47)), H * (0.2 + 0.6 * hash01(j, 48))
            c.drawPath(star(x, y, 700 * e + 80, 18, 4, 0.3 * j), fill(WHITE, 0.6 * e))
            glow(c, x, y, 400, GOLD, 0.6 * e)


def paint_chase(S, c, t):
    t0 = 27.72
    p = S.beat_pulse(t)
    split = CX + 300 * math.sin((t - t0) * 3)
    c.drawPath(poly([(-300, -300), (split + 380, -300), (split - 380, H + 300), (-300, H + 300)]),
               fill(mix(INK, CYAN, 0.55 + 0.15 * p)))
    c.drawPath(poly([(split + 380, -300), (W + 300, -300), (W + 300, H + 300), (split - 380, H + 300)]),
               fill(mix(INK, PINK, 0.55 + 0.15 * p)))
    tiled(c, S.dots, INK, 0.35, scale=0.5, rot=45)
    speedlines(c, CX, CY, 80, 380, 1500, WHITE, 0.35, seed=int(t * 30), width=20, t=t)
    # akan oklar
    for row in range(6):
        y = 90 + row * 180
        d = 1 if row % 2 else -1
        for k in range(9):
            x = (k * 260 + d * (t - t0) * 1900 + row * 90) % (W + 520) - 260
            c.drawPath(chevron(x, y, 70, d), fill(WHITE if row % 2 else INK, 0.35))


def paint_robe(S, c, t):
    t0 = 29.19
    linear(c, 0, 0, W, H, [(0.05, 0.3, 0.38), (0.25, 0.18, 0.45), (0.08, 0.04, 0.2)], [0.0, 0.55, 1.0])
    glow(c, CX, CY, 900, (0.7, 0.9, 1.0), 0.18)
    # kurdeleler: iki sinüs eğrisi arasında kalan akan şeritler
    for r in range(5):
        amp = 90 + 50 * hash01(r, 51)
        k = 0.004 + 0.002 * hash01(r, 52)
        w = 40 + 60 * hash01(r, 53)
        spd = 2.2 + 1.5 * hash01(r, 54)
        yb = 150 + r * 200
        top, bot = [], []
        for i in range(0, 41):
            x = -100 + i * (W + 200) / 40
            ph = x * k - (t - t0) * spd + r
            y = yb + amp * math.sin(ph)
            ww = w * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(ph * 0.7 + r)))
            top.append((x, y - ww))
            bot.append((x, y + ww))
        rgb = (WHITE, (0.8, 0.7, 1.0), GOLD, CYAN, PINK)[r]
        c.drawPath(poly(top + bot[::-1]), fill(rgb, 0.28))
        c.drawPath(poly(top, close=False), stroke(WHITE, 3, 0.5))
    # süzülen tüyler
    for i in range(16):
        ph = ((t - t0) * 0.12 + hash01(i, 55)) % 1.0
        x = W * hash01(i, 56) + 120 * math.sin(t * 1.5 + i)
        y = -60 + ph * (H + 120)
        rot = 40 * math.sin(t * 2 + i)
        c.save()
        c.translate(x, y)
        c.rotate(rot)
        c.drawOval(skia.Rect(-12, -46, 12, 46), fill(WHITE, 0.55))
        c.drawLine(0, -50, 0, 60, stroke((0.8, 0.8, 1.0), 2.5, 0.8))
        c.restore()


def paint_yura(S, c, t):
    t0 = 31.60
    linear(c, 0, 0, 0, H, [(0.0, 0.25, 0.45), (0.02, 0.1, 0.3), (0.0, 0.03, 0.12)], [0.0, 0.5, 1.0])
    for r in range(9):
        yb = 60 + r * 125
        pts = []
        for i in range(41):
            x = -100 + i * (W + 200) / 40
            pts.append((x, yb + 34 * math.sin(x * 0.006 + (t - t0) * 2.4 + r * 0.8)))
        c.drawPath(poly(pts, close=False), stroke(mix(CYAN, BLUE, r / 8), 10, 0.25))
    for i in range(30):                                   # kabarcıklar
        ph = ((t - t0) * (0.18 + 0.1 * hash01(i, 61)) + hash01(i, 62)) % 1.0
        x = W * hash01(i, 63) + 30 * math.sin(t * 3 + i)
        y = H + 40 - ph * (H + 80)
        r = 8 + 26 * hash01(i, 64)
        c.drawCircle(x, y, r, stroke(WHITE, 3, 0.5 * math.sin(math.pi * ph)))
        c.drawCircle(x - r * 0.35, y - r * 0.35, r * 0.18, fill(WHITE, 0.6 * math.sin(math.pi * ph)))
    glow(c, CX, H * 0.2, 800, CYAN, 0.18)


def paint_lovehate(S, c, t):
    t0 = 34.366
    p = S.beat_pulse(t)
    split = CX + 160 * math.sin((t - t0) * 1.6)
    zig = []
    for i in range(13):
        y = -60 + i * (H + 120) / 12
        zig.append((split + (40 if i % 2 else -40), y))
    left = [(-300, -300)] + [(zig[0][0], -300)] + zig + [(zig[-1][0], H + 300), (-300, H + 300)]
    c.drawPaint(fill(mix(INK, (0.35, 0.0, 0.05), 0.8 + 0.2 * p)))
    c.drawPath(poly(left), fill(mix(INK, PINK, 0.75 + 0.15 * p)))
    for i in range(18):                                   # sol: kalpler, sağ: çarpılar
        x0 = W * hash01(i, 71)
        y0 = ((hash01(i, 72) * H + (t - t0) * 60) % (H + 200)) - 100
        s = 50 + 60 * hash01(i, 73)
        if x0 < split:
            c.drawPath(heart(x0, y0, s * 1.2, 0.3 * math.sin(t * 2 + i)), fill(WHITE, 0.3))
        else:
            c.save()
            c.translate(x0, y0)
            c.rotate(45 + 20 * math.sin(t + i))
            pnt = fill(RED, 0.45)
            c.drawRect(skia.Rect(-s * 0.5, -s * 0.12, s * 0.5, s * 0.12), pnt)
            c.drawRect(skia.Rect(-s * 0.12, -s * 0.5, s * 0.12, s * 0.5), pnt)
            c.restore()
    c.drawPath(poly(zig, close=False), stroke(WHITE, 10, 0.9))
    tiled(c, S.dots, INK, 0.2, scale=0.5, rot=45)


def paint_swallow(S, c, t):
    t0 = 37.50
    c.drawPaint(fill((0.02, 0.1, 0.04)))
    rot = (t - t0) * 70
    arms = 7
    for a in range(arms):                                # girdap kolları
        pts = []
        for i in range(30):
            s = i / 29
            ang = math.radians(rot + a * 360 / arms) + s * 4.2
            r = 40 + s * 1300
            pts.append((CX + r * math.cos(ang), CY + r * math.sin(ang)))
        c.drawPath(poly(pts, close=False), stroke(mix((0.02, 0.1, 0.04), LIME, 0.35 + 0.1 * (a % 2)), 70, 0.9))
    glow(c, CX, CY, 500, LIME, 0.3)
    # içine çekilen simgeler
    for i in range(24):
        life = 2.2 + hash01(i, 81)
        ph = ((t - t0) / life + hash01(i, 82)) % 1.0
        r = lerp(1100, 30, ease_in(ph))
        ang = 6.28 * hash01(i, 83) + ph * 5
        x, y = CX + r * math.cos(ang), CY + r * math.sin(ang)
        s = 60 * (1 - ph) + 8
        a = math.sin(math.pi * ph) * 0.8
        kind = i % 4
        rgb = (PINK, GOLD, CYAN, WHITE)[kind]
        if kind == 0:
            c.drawPath(heart(x, y, s, ang), fill(rgb, a))
        elif kind == 1:
            c.drawPath(star(x, y, s * 0.6, s * 0.25, 5, ang), fill(rgb, a))
        elif kind == 2:
            c.drawPath(note(x, y, s * 0.8), fill(rgb, a))
        else:
            c.drawPath(sparkle(x, y, s * 0.6, ang), fill(rgb, a))


def paint_answer(S, c, t):
    t0, tb, tc = 40.98, 41.82, 43.06
    ok = ease_out(span(t, tc - 0.02, tc + 0.2))
    c.drawPaint(fill(mix((0.02, 0.04, 0.16), (0.2, 0.05, 0.08), ok)))
    tiled(c, S.grid, BLUE, 0.35, scale=1.4, dx=-(t - t0) * 90, dy=(t - t0) * 40)
    # soru işaretleri: doğru cevap gelince uçup gider
    font = S.font("bungee", 120)
    for i in range(16):
        x = W * hash01(i, 91) + 20 * noise(t * 6, i)
        y = H * hash01(i, 92) + 20 * noise(t * 6, i + 50) - ok * 900 * (0.5 + hash01(i, 93))
        s = 0.6 + 0.9 * hash01(i, 94)
        c.save()
        c.translate(x, y)
        c.rotate(25 * noise(t * 2, i + 90))
        c.scale(s, s)
        c.drawString("?", -35, 40, font, fill(CYAN if i % 2 else WHITE, 0.4 * (1 - ok)))
        c.restore()
    # ikinci parça: şimşek ve mavi flaş
    e = decay(t, tb, 0.2)
    if e > 0.01:
        c.drawPaint(fill(CYAN, 0.35 * e))
    lightning(c, t, tb, 250, -10, 700, 700, seed=411, rgb=CYAN, width=8)
    lightning(c, t, tb + 0.05, W - 250, -10, W - 750, 650, seed=412, rgb=CYAN, width=7)
    # doğru cevap halkası (quiz programlarındaki kırmızı daire)
    if ok > 0:
        r = 330 * ease_out_back(clamp01((t - tc) / 0.22), 2.4)
        c.drawCircle(CX, 690, r, stroke(RED, 58, 0.85))
        c.drawCircle(CX, 690, r, stroke(WHITE, 8, 0.5))
        font2 = S.font("blackops", 64)
        c.drawString("CORRECT!!", 70, 150, font2, fill(GOLD, ok))


def paint_bloom(S, c, t):
    t0, t1 = 44.56, 48.089
    u = span(t, t0, t1)
    linear(c, 0, 0, W, H, [mix((0.35, 0.02, 0.25), (0.7, 0.2, 0.05), u), mix((0.12, 0.0, 0.12), (0.4, 0.05, 0.1), u),
                           INK], [0.0, 0.6, 1.0])
    glow(c, CX, CY, 1000, mix(PINK, GOLD, u), 0.2 + 0.25 * u)
    n = 46
    for i in range(n):                                   # zamana yayılmış açan çiçekler
        tb = t0 + 0.1 + 3.3 * (i / n) ** 0.8
        dt = t - tb
        if dt < 0:
            continue
        g = ease_out_elastic(clamp01(dt / 0.6))
        x, y = W * hash01(i, 101), H * hash01(i, 102)
        r = (60 + 110 * hash01(i, 103)) * g
        rot = dt * (0.8 if i % 2 else -0.8) + hash01(i, 104) * 6
        rgb = RAINBOW[i % len(RAINBOW)]
        c.drawPath(flower(x, y, r, 5 + i % 3, rot), fill(rgb, 0.85))
        c.drawCircle(x, y, r * 0.22, fill(WHITE if i % 2 else GOLD))
    for i in range(40):                                  # uçuşan yapraklar
        ph = ((t - t0) * 0.35 + hash01(i, 105)) % 1.0
        x = W * hash01(i, 106) + 150 * math.sin(t * 1.3 + i)
        y = -40 + ph * (H + 80)
        c.save()
        c.translate(x, y)
        c.rotate(t * 120 + i * 20)
        c.drawOval(skia.Rect(-16, -8, 16, 8), fill(PINK if i % 2 else WHITE, 0.7))
        c.restore()
    if t > 47.55:                                        # nakarat öncesi: halka merkeze çöker
        v = span(t, 47.55, t1)
        c.drawCircle(CX, CY, lerp(1300, 20, ease_in(v)), stroke(WHITE, 10 + 40 * v, v))
        speedlines(c, CX, CY, 90, lerp(900, 150, ease_in(v)), 1500, WHITE, 0.45 * v, seed=99, width=16, t=t)


MOON_X, MOON_Y, MOON_R = 1420, 400, 270


def paint_moon(S, c, t):
    t0, tsplit, tface, tdance = 48.089, 48.42, 50.40, 51.49
    p = S.beat_pulse(t)
    linear(c, 0, 0, 0, H, [(0.02, 0.03, 0.14), (0.05, 0.02, 0.2), (0.01, 0.0, 0.05)], [0.0, 0.6, 1.0])
    for i in range(120):                                 # yıldızlar
        x, y = W * hash01(i, 111), H * 0.85 * hash01(i, 112)
        tw = 0.5 + 0.5 * math.sin(t * (2 + 4 * hash01(i, 113)) + 6.28 * hash01(i, 114))
        r = 1.5 + 3 * hash01(i, 115) * tw
        c.drawCircle(x, y, r, fill(WHITE, 0.3 + 0.7 * tw))
        if hash01(i, 116) > 0.9:
            c.drawPath(sparkle(x, y, 14 * tw + 4), fill(WHITE, 0.8 * tw))
    face = ease_out(span(t, tface - 0.05, tface + 0.4))
    reveal = ease_out(span(t, tsplit - 0.03, tsplit + 0.55))
    # ay: parlama, ışınlar, kraterler
    glow(c, MOON_X, MOON_Y, MOON_R * (2.6 + 0.6 * face), (0.7, 0.8, 1.0), 0.25 + 0.3 * face + 0.1 * p)
    if face > 0:
        rays = skia.Path()
        for k in range(16):
            a0 = math.radians((t - t0) * 12 + k * 22.5)
            a1 = a0 + math.radians(5)
            R = MOON_R * (2.2 + 0.5 * face)
            rays.moveTo(MOON_X, MOON_Y)
            rays.lineTo(MOON_X + R * math.cos(a0), MOON_Y + R * math.sin(a0))
            rays.lineTo(MOON_X + R * math.cos(a1), MOON_Y + R * math.sin(a1))
            rays.close()
        c.drawPath(rays, fill(MOON, 0.12 * face, blend=ADD))
    c.drawCircle(MOON_X, MOON_Y, MOON_R, fill(MOON))
    for k in range(7):
        a = 6.28 * hash01(k, 117)
        rr = MOON_R * 0.65 * hash01(k, 118)
        cr = MOON_R * (0.08 + 0.12 * hash01(k, 119))
        c.drawCircle(MOON_X + rr * math.cos(a), MOON_Y + rr * math.sin(a), cr, fill((0.86, 0.82, 0.74)))
    c.drawCircle(MOON_X, MOON_Y, MOON_R, stroke(WHITE, 6, 0.8))
    # dans halkaları ve notalar
    if t >= tdance - 0.2:
        d = ease_out(span(t, tdance - 0.2, tdance + 0.3))
        for k in range(3):
            r = MOON_R * (1.35 + 0.35 * k) + 12 * p
            eff = skia.DashPathEffect.Make([40.0, 26.0], (t - t0) * (140 if k % 2 else -140))
            pnt = stroke((PINK, CYAN, GOLD)[k], 10, 0.8 * d)
            pnt.setPathEffect(eff)
            c.drawCircle(MOON_X, MOON_Y, r, pnt)
        for i in range(12):
            ph = ((t - tdance) * 0.4 + hash01(i, 121)) % 1.0
            x = W * hash01(i, 122) + 60 * math.sin(t * 3 + i)
            y = H + 40 - ph * (H + 100)
            c.drawPath(note(x, y, 60 + 40 * hash01(i, 123)), fill((PINK, CYAN, GOLD, WHITE)[i % 4],
                                                                   d * math.sin(math.pi * ph)))
    # bulutlar: ayın önünü kapatır, nakaratın ikinci parçasıyla ikiye yarılır
    for side in (-1, 1):
        for k in range(3):
            x = MOON_X + side * (160 + 120 * k) + side * reveal * (900 + 200 * k)
            y = MOON_Y - 120 + 150 * k
            cloud(c, x, y, 420 - 60 * k, (0.16 + 0.05 * k, 0.15 + 0.05 * k, 0.3 + 0.06 * k), 0.98, seed=k * 3 + side)
    for k in range(4):                                   # alt kenarda sürüklenen bulutlar
        x = (k * 620 - (t - t0) * 60) % (W + 800) - 400
        cloud(c, x, H - 40, 460, (0.07, 0.06, 0.18), 0.95, seed=40 + k)


def paint_tonight(S, c, t):
    t0, t_long = 54.86, 57.72
    p = S.beat_pulse(t)
    h = ease_in(span(t, 58.375, 60.093))                 # uzun notaya doğru yükselen yoğunluk
    linear(c, 0, 0, 0, H, [(0.08, 0.0, 0.16), (0.03, 0.0, 0.08), INK], [0.0, 0.55, 1.0])
    # hareketli ışık huzmeleri
    for i in range(9):
        bx = 120 + i * (W - 240) / 8
        ang = math.radians(-90 + 32 * math.sin(t * (1.1 + 0.3 * hash01(i, 131)) + i * 1.3))
        ln = 1500
        spread = math.radians(5 + 3 * hash01(i, 132))
        rgb = RAINBOW[(i + int((t - t0) * 2)) % len(RAINBOW)]
        tip0 = (bx + ln * math.cos(ang - spread), H + 60 + ln * math.sin(ang - spread))
        tip1 = (bx + ln * math.cos(ang + spread), H + 60 + ln * math.sin(ang + spread))
        shader = skia.GradientShader.MakeLinear([skia.Point(bx, H + 60), skia.Point((tip0[0] + tip1[0]) / 2, (tip0[1] + tip1[1]) / 2)],
                                                [col(rgb, 0.55 + 0.25 * p).toColor(), col(rgb, 0).toColor()])
        pnt = skia.Paint(AntiAlias=True, Shader=shader)
        pnt.setBlendMode(ADD)
        c.drawPath(poly([(bx, H + 60), tip0, tip1]), pnt)
    # lazerler
    for i in range(6):
        a = math.radians(20 + 140 * hash01(i, 133) + 30 * math.sin(t * 2 + i))
        x0 = W * hash01(i, 134)
        c.drawLine(x0, H, x0 + 2500 * math.cos(a), H - 2500 * math.sin(a),
                   stroke((PINK, CYAN, LIME)[i % 3], 3, 0.35 + 0.3 * p, blend=ADD))
    # ses halkaları: vuruşlarda, son uzun notada sürekli
    for j in range(6):
        ph = ((t - t0) * (1.2 + 1.8 * h) + j / 6) % 1.0
        if t >= t_long - 0.1 or j % 2 == 0:
            c.drawCircle(CX, 760, 80 + ph * 1100, stroke(RAINBOW[j % len(RAINBOW)], 16 * (1 - ph) + 2, 0.6 * (1 - ph)))
    glow(c, CX, H + 100, 1000, VIOLET, 0.35 + 0.25 * p + 0.3 * h)
    tiled(c, S.dots, INK, 0.25, scale=0.5, rot=45)


def paint_end(S, c, t):
    c.clear(col(INK))


PAINTERS = {
    "boot": paint_boot, "signal": paint_signal, "storm": paint_storm, "scar": paint_scar, "glare": paint_glare,
    "chase": paint_chase, "robe": paint_robe, "yura": paint_yura, "lovehate": paint_lovehate,
    "swallow": paint_swallow, "answer": paint_answer, "bloom": paint_bloom, "moon": paint_moon,
    "tonight": paint_tonight, "end": paint_end,
}
