"""QUEEN (LiSA) fan yapımı lyric video - görsel sahne (61 saniye, 1920x1080, 2B).

Akış (saniye, şarkıyla aynı saat):
   0.0   CRT açılışı; 0.49'da ilk vuruşla kırmızı/yeşil ekran patlar
   0.5   dört "Red or Green?" satırı: lamba tabelası, damga gibi inen kanji,
         "Yeah" etiketleri, "Red Light? / Green Light?" şeritleri
  12.4   durak: ekran kararır, 12.77 kırmızı ve 13.32 yeşil dev flaş
  14.07  DEV PATLAMA -> fırtına: şimşeklerle ANDROE STUDIO, ardından QUEEN / LiSA
  20.7   verse: pençe çizikleri, altın parıltılar, "Chase me!", kurdeleler, dalgalar
  34.4   nakarat öncesi: kalp/çarpı, girdap + HP çubuğu, soru işareti -> doğru cevap,
         açan çiçekler; 48.09'a doğru ekran merkeze çöker
  48.09  NAKARAT PATLAMASI -> bulutlar yarılır, dev ay, dans halkaları
  54.86  "Tonight" DEV PATLAMA -> konser ışıkları; son uzun notada yazı ve kamera titrer
  60.09  FİNAL PATLAMASI, beyaz flaş, siyahta ANDROE STUDIO

Sağ altta sürekli: "LiSA - QUEEN" ve fan yapımı olduğunu belirten telif notu.
Sözler input/queen_sozler.txt dosyasından okunur (queen.py yükler).
"""
import math
from bisect import bisect_right
from pathlib import Path

import numpy as np
import skia

from queen_bg import MOON_X, MOON_Y, PAINTERS, glow
from queen_fx import (ADD, BLUE, CX, CY, CYAN, GOLD, GREEN, H, INK, LIME, MOON, ORANGE, PINK, RAINBOW, RED,
                      VIOLET, W, WHITE, burst, clamp01, col, crown, debris, decay, ease_in, ease_in_out, ease_out,
                      ease_out_back, ease_out_elastic, explosion, fill, hanko, hash01, lerp, mix, noise, pattern_image,
                      poly, shockwave, span, sparkle, speedlines, star, stroke)
from queen_timing import BEATS, DURATION, FINAL_HIT, HITS, LINES, SCENES

FONTS = Path(__file__).resolve().parent / "fonts"
FACES = {
    "dela": "DelaGothicOne.ttf", "rock": "RocknRollOne.ttf", "reggae": "ReggaeOne.ttf",
    "anton": "Anton.ttf", "blackops": "BlackOpsOne.ttf", "bungee": "Bungee.ttf",
    "mont": "Montserrat-Black.ttf", "montsemi": "Montserrat-SemiBold.ttf",
}

# Satır görünümleri (LINES ile aynı sırada). rows: ana (kanji) parçaların yerleşimi
# (x, y, punto, hizalama l/c/r). enter/exit: giriş ve çıkış animasyonu.
LOOKS = [
    dict(face="dela", fill=WHITE, shadow=RED, hl=GOLD, rows=[(CX, 610, 150, "c")], enter="stamp", exit="burst"),
    dict(face="dela", fill=WHITE, shadow=GREEN, hl=GOLD, rows=[(CX, 560, 220, "c")], enter="stamp", exit="zoom"),
    dict(face="dela", fill=WHITE, shadow=RED, hl=GOLD, rows=[(CX, 470, 170, "c"), (CX, 720, 175, "c")],
         enter="stamp", exit="burst"),
    dict(face="dela", fill=WHITE, shadow=GREEN, hl=GOLD, rows=[(CX, 560, 240, "c")], enter="stamp", exit="burst"),
    dict(face="reggae", fill=WHITE, shadow=(0.75, 0.04, 0.2), hl=PINK, rows=[(200, 420, 150, "l"), (W - 200, 690, 150, "r")],
         enter="slide", exit="swipe"),
    dict(face="dela", fill=GOLD, shadow=(0.75, 0.3, 0.0), hl=WHITE, rows=[(CX, 350, 130, "c"), (CX, 650, 250, "c")],
         enter="drop", exit="zoom", glint=True),
    dict(face="blackops", fill=WHITE, shadow=INK, hl=WHITE, rows=[]),
    dict(face="rock", fill=WHITE, shadow=VIOLET, hl=CYAN, rows=[(CX, 420, 160, "c"), (CX, 690, 250, "c")],
         enter="pop", exit="burst"),
    dict(face="rock", fill=WHITE, shadow=BLUE, hl=CYAN, rows=[(CX - 360, 450, 210, "c"), (CX + 360, 700, 210, "c")],
         enter="pop", exit="drop", wave=24),
    dict(face="reggae", fill=WHITE, shadow=INK, hl=GOLD, rows=[(CX, 350, 140, "c"), (CX, 660, 260, "c")],
         enter="slide", exit="burst", row_fill=[WHITE, RED], row_shadow=[(0.45, 0.0, 0.2), INK]),
    dict(face="dela", fill=WHITE, shadow=(0.05, 0.45, 0.1), hl=LIME, rows=[(230, 400, 150, "l"), (W - 230, 670, 170, "r")],
         enter="drop", exit="swallow"),
    dict(face="dela", fill=WHITE, shadow=BLUE, hl=CYAN, rows=[(CX, 280, 120, "c"), (CX, 505, 150, "c"), (CX, 720, 220, "c")],
         enter="glitch", exit="burst", row_fill=[WHITE, WHITE, GOLD], row_shadow=[BLUE, BLUE, RED], row_hl=[CYAN, CYAN, WHITE]),
    dict(face="dela", fill=WHITE, shadow=PINK, hl=GOLD, rows=[(CX, 370, 150, "c"), (CX, 670, 230, "c")],
         enter="pop", exit="burst", rainbow_rows=[1]),
    dict(face="dela", fill=WHITE, shadow=BLUE, hl=MOON, rows=[(150, 590, 150, "l"), (150, 830, 150, "l")],
         enter="slide", exit="swipe"),
    dict(face="rock", fill=WHITE, shadow=VIOLET, hl=PINK, rows=[(CX, 470, 150, "c"), (CX, 740, 180, "c")],
         enter="pop", exit="burst", sway=True),
    dict(face="dela", fill=WHITE, shadow=VIOLET, hl=GOLD, rows=[(CX, 470, 165, "c"), (CX, 750, 300, "c")],
         enter="stamp", exit="final", trem_rows=[1], rainbow_hl=True),
]

# Sahne geçişleri: (zaman, tür, renk)
WIPES = [(20.735, "slash", VIOLET), (24.52, "shutter", GOLD), (27.72, "slash_r", CYAN), (29.19, "blinds", WHITE),
         (31.60, "slash", CYAN), (34.366, "shutter", PINK), (37.50, "slash_r", LIME), (40.98, "blinds", BLUE),
         (44.56, "slash", PINK)]

CREDIT_TITLE = "LiSA  —  QUEEN"
CREDIT_NOTE = "Fan-made lyric video · Song © LiSA / original rights holders"


def strip_parens(s):
    return s.replace("(", "").replace(")", "").strip()


class QueenScene:
    def __init__(self, lyrics, width=1920, height=1080, fps=60):
        self.width, self.height, self.fps = width, height, fps
        self.duration = DURATION
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.faces = {k: skia.Typeface.MakeFromFile(str(FONTS / v)) for k, v in FACES.items()}
        self._fonts, self._blobs = {}, {}
        self.dots = pattern_image("dots", 40)
        self.stripes = pattern_image("stripes", 48)
        self.grid = pattern_image("grid", 90)
        self.lines = self._bind(lyrics)
        self.scene_t = [s[0] for s in SCENES]

    # ------------------------------------------------------------ veri

    def _bind(self, lyrics):
        """input/queen_sozler.txt'teki parçaları LINES'taki zamanlarla eşler."""
        if len(lyrics) != len(LINES):
            raise ValueError(f"Söz dosyasında {len(lyrics)} satır var, zamanlamada {len(LINES)} satır bekleniyor.")
        out = []
        for i, (line, (kanji, romaji)) in enumerate(zip(LINES, lyrics)):
            if len(kanji) != len(line["parts"]) or len(romaji) != len(line["parts"]):
                raise ValueError(f"{i + 1}. satırın parça sayısı zamanlamayla uyuşmuyor: {kanji}")
            parts = [dict(kind=k, t0=a, t1=b, text=kj, romaji=rm)
                     for (k, a, b), kj, rm in zip(line["parts"], kanji, romaji)]
            out.append(dict(index=i, end=line["end"], parts=parts, look=LOOKS[i]))
        return out

    def font(self, face, size):
        key = (face, round(size, 1))
        f = self._fonts.get(key)
        if f is None:
            f = skia.Font(self.faces[face], key[1])
            f.setSubpixel(True)
            f.setEdging(skia.Font.Edging.kAntiAlias)
            self._fonts[key] = f
        return f

    def blob(self, face, size, text):
        key = (face, round(size, 1), text)
        b = self._blobs.get(key)
        if b is None:
            b = skia.TextBlob.MakeFromString(text, self.font(face, size))
            self._blobs[key] = b
        return b

    def beat_index(self, t):
        return bisect_right(BEATS, t) - 1

    def beat_pulse(self, t, tau=0.13):
        i = self.beat_index(t)
        return math.exp(-(t - BEATS[i]) / tau) if i >= 0 else 0.0

    def scene_at(self, t):
        i = max(bisect_right(self.scene_t, t) - 1, 0)
        t1 = SCENES[i + 1][0] if i + 1 < len(SCENES) else DURATION
        return SCENES[i][1], SCENES[i][0], t1

    # ------------------------------------------------------------ kamera

    def tremolo(self, t):
        """Sürekli titreme: patlama öncesi yükselişler ve son uzun nota."""
        if 13.63 <= t < 14.071:
            return 12 * ease_in(span(t, 13.63, 14.071))
        if 46.8 <= t < 48.089:
            return 7 * ease_in(span(t, 46.8, 48.089))
        if 57.72 <= t < FINAL_HIT:
            return 3 + 15 * ease_in(span(t, 57.72, FINAL_HIT))
        return 0.0

    def camera(self, t):
        sx = sy = rot = 0.0
        zoom = 1.0
        for i, (th, pw, kind) in enumerate(HITS):
            if t < th or t > th + 1.5:
                continue
            e = decay(t, th, 0.09 + 0.05 * pw)
            amp = (0, 5, 12, 24, 42)[pw]
            sx += amp * e * noise(t * 38, i * 3)
            sy += amp * e * noise(t * 38, i * 3 + 1)
            rot += 0.05 * amp * e * noise(t * 30, i * 3 + 2)
            zoom += (0, 0.012, 0.03, 0.055, 0.1)[pw] * decay(t, th, 0.11)
        tr = self.tremolo(t)
        if tr > 0:
            sx += tr * noise(t * 55, 901)
            sy += tr * noise(t * 55, 902)
            rot += 0.06 * tr * noise(t * 40, 903)
        # yavaş itiş: yükselişlerde kamera içeri girer
        zoom += 0.06 * ease_in(span(t, 44.56, 48.089)) * (t < 48.089)
        zoom += 0.08 * ease_in(span(t, 57.72, FINAL_HIT)) * (t < FINAL_HIT)
        zoom += 0.05 * ease_in(span(t, 13.2, 14.071)) * (t < 14.071)
        zoom += 0.012 * self.beat_pulse(t) * (t > 7.268)
        return sx, sy, rot, zoom

    # ------------------------------------------------------------ yazı motoru

    def row_layout(self, text, face, size, x, align, tracking=0.0, max_w=1700):
        font = self.font(face, size)
        glyphs = font.textToGlyphs(text)
        widths = list(font.getWidths(glyphs))
        total = sum(widths) + tracking * (len(widths) - 1)
        if total > max_w:                                    # sığmazsa küçült
            size *= max_w / total
            return self.row_layout(text, face, size, x, align, tracking * max_w / total, max_w)
        x0 = x - total / 2 if align == "c" else (x if align == "l" else x - total)
        centers, acc = [], x0
        for w_ in widths:
            centers.append(acc + w_ / 2)
            acc += w_ + tracking
        return size, centers, widths, x0, total

    def draw_row(self, c, t, text, look, row, t_in, hl0, hl1, t_out, seed, fill_rgb=None, shadow_rgb=None,
                 hl_rgb=None, extra=None):
        """Kanji satırı: karakter karakter giriş, söylendikçe renk dolumu, vuruş zıplaması, çıkış."""
        extra = extra or {}
        x, y, size, align = row
        face = extra.get("face", look["face"])
        size, centers, widths, x0, total = self.row_layout(text, face, size, x, align)
        chars = list(text)
        n = len(chars)
        base = fill_rgb or look["fill"]
        shadow = shadow_rgb or look["shadow"]
        hl = hl_rgb or look["hl"]
        enter, exit_ = extra.get("enter", look.get("enter", "stamp")), extra.get("exit", look.get("exit", "burst"))
        u_out = span(t, t_out - 0.02, t_out + 0.2)
        if u_out >= 1:
            return
        sh_off = size * 0.055
        stroke_w = size * 0.13
        cy_mid = y
        baseline_off = size * 0.36                       # görsel merkezden taban çizgisine
        mid_x = x0 + total / 2
        for i, ch in enumerate(chars):
            if ch == " ":
                continue
            st = 0.028 * i if enter != "slide" else 0.012 * i
            u = span(t, t_in - 0.11 + st, t_in + st)
            if u <= 0:
                continue
            dx = dy = rot = 0.0
            sc, a = 1.0, 1.0
            r0 = hash01(i, seed)
            if enter == "stamp":
                sc = lerp(2.6, 1.0, ease_out(u))
                rot = (1 - u) * (r0 - 0.5) * 50
                a = min(1.0, u * 3)
            elif enter == "pop":
                sc = ease_out_back(u, 2.6)
                a = min(1.0, u * 4)
            elif enter == "drop":
                dy = -(1 - ease_out_back(u, 1.6)) * 320
                a = min(1.0, u * 3)
            elif enter == "slide":
                d = -1 if align != "r" else 1
                dx = d * (1 - ease_out(u)) * 1100
                a = min(1.0, u * 2)
            elif enter == "glitch":
                if u < 1:
                    dx = (hash01(i, seed, int(t * 60)) - 0.5) * 90 * (1 - u)
                    dy = (hash01(i, seed, int(t * 60) + 7) - 0.5) * 40 * (1 - u)
                    a = 1.0 if hash01(i, int(t * 60)) > 0.3 * (1 - u) else 0.0
            # söylenme anı: renk dolumu ve zıplama
            th = hl0 + (hl1 - hl0) * (i / max(n, 1)) * 0.94
            hu = span(t, th - 0.02, th + 0.07)
            bump = math.sin(math.pi * span(t, th - 0.02, th + 0.16)) * 0.16
            sc *= 1 + bump
            dy -= bump * size * 0.25
            this_hl = hl
            if look.get("rainbow_hl") or extra.get("rainbow"):
                this_hl = RAINBOW[(i + int(t * 8)) % len(RAINBOW)]
            fill_now = mix(base, this_hl, hu)
            # sürekli hareketler
            if extra.get("wave"):
                dy += extra["wave"] * math.sin(t * 5.5 + i * 0.9)
                rot += 6 * math.sin(t * 4 + i)
            if extra.get("sway"):
                dx += 10 * math.sin(t * 6.3 + i * 0.5)
                rot += 8 * math.sin(t * 6.3 + i * 0.5)
            tr = extra.get("trem", 0.0)
            if tr:
                dx += tr * noise(t * 60, i * 5 + seed)
                dy += tr * noise(t * 60, i * 5 + seed + 1)
                rot += tr * 0.4 * noise(t * 50, i * 5 + seed + 2)
            # vuruşlarda harf sarsıntısı
            hs = self.hit_shake(t)
            if hs > 0:
                dx += hs * noise(t * 70, i * 11 + seed)
                dy += hs * noise(t * 70, i * 11 + seed + 3)
            # çıkış
            if u_out > 0:
                e = ease_in(u_out)
                if exit_ in ("burst", "final"):
                    dx += (centers[i] - mid_x) * 1.4 * e + (r0 - 0.5) * 500 * e
                    dy += (-420 * e + 1100 * e * e) * (0.5 + r0)
                    rot += (r0 - 0.5) * 540 * e
                    sc *= 1 + 0.5 * e
                elif exit_ == "zoom":
                    sc *= 1 + 1.6 * e
                    dx += (centers[i] - mid_x) * 1.2 * e
                elif exit_ == "swipe":
                    dx += (-1 if align == "l" else 1) * 1600 * e
                elif exit_ == "drop":
                    dy += 900 * e * e * (0.6 + r0)
                    rot += (r0 - 0.5) * 90 * e
                elif exit_ == "swallow":
                    dx += (CX - centers[i]) * e
                    dy += (CY - cy_mid) * e
                    sc *= 1 - e
                    rot += 360 * e
                a *= 1 - u_out
            if a <= 0.01 or sc <= 0.01:
                continue
            blob = self.blob(face, size, ch)
            c.save()
            c.translate(centers[i] + dx, cy_mid + dy)
            c.rotate(rot)
            c.scale(sc, sc)
            ox, oy = -widths[i] / 2, baseline_off
            c.drawTextBlob(blob, ox + sh_off, oy + sh_off, fill(shadow, a))
            c.drawTextBlob(blob, ox, oy, stroke(INK, stroke_w, a))
            c.drawTextBlob(blob, ox, oy, fill(fill_now, a))
            if look.get("glint"):                            # altın yazının üstünden geçen parıltı
                gx = ((t * 900) % 2600) - 800 - (centers[i] - x0)
                shader = skia.GradientShader.MakeLinear(
                    [skia.Point(gx - 90, -size), skia.Point(gx + 90, size)],
                    [col(WHITE, 0).toColor(), col(WHITE, 0.85 * a).toColor(), col(WHITE, 0).toColor()])
                pg = skia.Paint(AntiAlias=True, Shader=shader)
                pg.setBlendMode(skia.BlendMode.kSrcATop)
                c.drawTextBlob(blob, ox, oy, pg)
            c.restore()

    def draw_romaji(self, c, t, text, row, look, t_in, hl0, hl1, t_out, main_size, hl_rgb=None):
        x, y, size, align = row
        rs = max(30.0, min(46.0, main_size * 0.27))
        font = self.font("montsemi", rs)
        tracking = rs * 0.09
        glyphs = font.textToGlyphs(text)
        widths = font.getWidths(glyphs)
        total = sum(widths) + tracking * (len(widths) - 1)
        x0 = x - total / 2 if align == "c" else (x if align == "l" else x - total)
        yy = y + main_size * 0.56 + rs * 0.95
        u = ease_out(span(t, t_in - 0.06, t_in + 0.22))
        u_out = span(t, t_out - 0.02, t_out + 0.14)
        a = u * (1 - u_out)
        if a <= 0.01:
            return
        yy += (1 - u) * 26
        prog = span(t, hl0, hl1)
        hl = hl_rgb or look["hl"]
        path_x = []
        acc = x0
        for w_ in widths:
            path_x.append(acc)
            acc += w_ + tracking
        for pass_, (rgb, clip) in enumerate(((WHITE, None), (hl, x0 + prog * total))):
            if clip is not None:
                if prog <= 0:
                    break
                c.save()
                c.clipRect(skia.Rect(x0 - 10, yy - rs * 1.4, clip, yy + rs * 0.6))
            for ch, px in zip(text, path_x):
                if ch == " ":
                    continue
                b = self.blob("montsemi", rs, ch)
                if pass_ == 0:
                    c.drawTextBlob(b, px, yy, stroke(INK, rs * 0.2, a * 0.85))
                c.drawTextBlob(b, px, yy, fill(rgb, a * (0.88 if pass_ == 0 else 1.0)))
            if clip is not None:
                c.restore()

    def hit_shake(self, t):
        s = 0.0
        for th, pw, kind in HITS:
            if pw >= 2 and th <= t < th + 0.6:
                s += (0, 0, 7, 14, 22)[pw] * decay(t, th, 0.12)
        return s

    # ------------------------------------------------------------ özel parçalar

    def draw_rog(self, c, t, part, line_end, next_t):
        """'Red or Green?': lamba tabelası, kelimeler hece hece yanar; ana satır gelince tepeye küçülür."""
        words = strip_parens(part["text"]).split()
        t0 = part["t0"]
        u_in = span(t, t0 - 0.08, t0 + 0.12)
        if u_in <= 0:
            return
        shrink = ease_in_out(span(t, next_t - 0.12, next_t + 0.12))
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        a = (1 - u_out)
        if a <= 0:
            return
        cy = lerp(430, 150, shrink)
        sc = lerp(1.0, 0.5, shrink) * ease_out_back(u_in, 2.0)
        c.save()
        c.translate(CX, cy)
        c.scale(sc, sc)
        # tabela gövdesi
        plate = skia.RRect.MakeRectXY(skia.Rect(-640, -150, 640, 150), 60, 60)
        c.drawRRect(plate, fill(INK, 0.88 * a))
        c.drawRRect(plate, stroke(WHITE, 10, a))
        p = self.beat_pulse(t)
        red_on = 0.35 + 0.65 * (self.beat_index(t) % 2 == 0) * p
        green_on = 0.35 + 0.65 * (self.beat_index(t) % 2 == 1) * p
        for lx, rgb, on in ((-520, RED, red_on), (520, GREEN, green_on)):
            c.drawCircle(lx, 0, 92, fill(mix(INK, rgb, 0.3 + 0.7 * on), a))
            glow(c, lx, 0, 260, rgb, 0.5 * on * a)
            c.drawCircle(lx - 28, -28, 22, fill(WHITE, 0.7 * a))
        colors = (RED, WHITE, GREEN)
        sizes = (150, 80, 150)
        font_sizes = [self.font("anton", s) for s in sizes]
        ws = [f.measureText(wd.upper()) for f, wd in zip(font_sizes, words)]
        gap = 34
        total = sum(ws) + gap * (len(ws) - 1)
        x = -total / 2
        for j, (wd, f, w_) in enumerate(zip(words, font_sizes, ws)):
            tw = t0 + 0.2 * j
            uj = span(t, tw - 0.06, tw + 0.08)
            if uj > 0:
                s = 1 + 0.5 * (1 - ease_out(uj))
                c.save()
                c.translate(x + w_ / 2, 0)
                c.scale(s, s)
                b = skia.TextBlob.MakeFromString(wd.upper(), f)
                yb = sizes[j] * 0.36
                c.drawTextBlob(b, -w_ / 2, yb, stroke(INK, sizes[j] * 0.12, a * uj))
                c.drawTextBlob(b, -w_ / 2, yb, fill(colors[j % 3], a * uj))
                c.restore()
            x += w_ + gap
        c.restore()

    def draw_yeah(self, c, t, part, line_end):
        t0 = part["t0"]
        u = span(t, t0 - 0.06, t0 + 0.25)
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        if u <= 0 or u_out >= 1:
            return
        x, y = 300, 885
        s = ease_out_elastic(u) * (1 - u_out)
        c.save()
        c.translate(x, y)
        c.rotate(10 + 6 * math.sin(t * 20) * (1 - u))
        c.scale(s, s)
        c.drawPath(burst(0, 0, 110, 195, 16, seed=int(t0 * 10), rot=t * 0.5), fill(PINK))
        c.drawPath(burst(0, 0, 85, 150, 13, seed=int(t0 * 10) + 3, rot=-t * 0.4), fill(GOLD))
        f = self.font("bungee", 110)
        text = part["text"].upper()
        w_ = f.measureText(text)
        b = skia.TextBlob.MakeFromString(text, f)
        c.drawTextBlob(b, -w_ / 2 + 6, 44, fill(INK))
        c.drawTextBlob(b, -w_ / 2, 38, stroke(INK, 14))
        c.drawTextBlob(b, -w_ / 2, 38, fill(WHITE))
        c.restore()

    def draw_ratatta(self, c, t, part, look, line_end, seed):
        """Kısa satır: her hece ayrı bir damga, kırmızı/yeşil sırayla."""
        text = part["text"]
        row = look["rows"][0]
        size, centers, widths, x0, total = self.row_layout(text, look["face"], row[2], row[0], row[3])
        groups, i = [], 0
        while i < len(text):                             # küçük "ッ" bir sonraki heceyle birlikte iner
            if text[i] in "ッっ" and i + 1 < len(text):
                groups.append([i, i + 1])
                i += 2
            else:
                groups.append([i])
                i += 1
        dur = part["t1"] - part["t0"]
        u_out = span(t, line_end - 0.02, line_end + 0.16)
        for g, idxs in enumerate(groups):
            tg = part["t0"] + dur * g / len(groups)
            u = span(t, tg - 0.07, tg + 0.02)
            if u <= 0:
                continue
            for i in idxs:
                sc = lerp(3.0, 1.0, ease_out(u)) * (1 + 1.5 * ease_in(u_out))
                rgb = (RED, GREEN)[g % 2]
                a = min(1.0, u * 3) * (1 - u_out)
                if a <= 0.01:
                    continue
                c.save()
                c.translate(centers[i] + self.hit_shake(t) * noise(t * 70, i), row[1])
                c.rotate((1 - u) * 30 * (hash01(i, seed) - 0.5))
                c.scale(sc, sc)
                b = self.blob(look["face"], size, text[i])
                ox, oy = -widths[i] / 2, size * 0.36
                c.drawTextBlob(b, ox + 12, oy + 12, fill(rgb, a))
                c.drawTextBlob(b, ox, oy, stroke(INK, size * 0.13, a))
                c.drawTextBlob(b, ox, oy, fill(WHITE, a))
                c.restore()
            if 0 < t - tg < 0.3:                          # her damgada küçük şok halkası
                shockwave(c, t, tg, centers[idxs[0]], row[1], 260, (RED, GREEN)[g % 2], dur=0.3, width=14)
        # romaji
        self.draw_romaji(c, t, part["romaji"], row, dict(hl=GOLD), part["t0"], part["t0"], part["t1"], line_end, size)

    def draw_light(self, c, t, part, line_end, big):
        """'Red Light? / Green Light?': lambası yanan şerit; durakta ekranı kaplar."""
        text = part["text"].upper()
        rgb = RED if text.startswith("RED") else GREEN
        t0 = part["t0"]
        u = span(t, t0 - 0.07, t0 + 0.1)
        nxt = line_end
        u_out = span(t, nxt - 0.02, nxt + 0.12)
        if u <= 0 or u_out >= 1:
            return
        a = 1 - u_out
        if big:
            y, size = (330 if rgb == RED else 800), 190
        else:
            y, size = (318 if rgb == RED else 880), 120
        band_h = size * 1.05
        slide = (1 - ease_out(u)) * (1 if rgb == RED else -1) * 2200
        c.save()
        c.translate(slide, 0)
        c.drawRect(skia.Rect(-200, y - band_h / 2, W + 200, y + band_h / 2), fill(INK, 0.85 * a))
        c.drawRect(skia.Rect(-200, y - band_h / 2, W + 200, y - band_h / 2 + 10), fill(rgb, a))
        c.drawRect(skia.Rect(-200, y + band_h / 2 - 10, W + 200, y + band_h / 2), fill(rgb, a))
        f = self.font("anton", size)
        w_ = f.measureText(text)
        lamp_r = size * 0.36
        total = w_ + lamp_r * 2 + 40
        x = CX - total / 2
        on = 0.6 + 0.4 * math.sin(t * 30)
        c.drawCircle(x + lamp_r, y, lamp_r, fill(rgb, a))
        glow(c, x + lamp_r, y, lamp_r * 3.2, rgb, 0.6 * on * a)
        b = skia.TextBlob.MakeFromString(text, f)
        tx = x + lamp_r * 2 + 40
        hs = self.hit_shake(t)
        jx, jy = hs * noise(t * 70, 5), hs * noise(t * 70, 6)
        c.drawTextBlob(b, tx + 8 + jx, y + size * 0.36 + 8 + jy, fill(INK, a))
        c.drawTextBlob(b, tx + jx, y + size * 0.36 + jy, fill(rgb, a))
        c.restore()

    def draw_chase(self, c, t, part, j, line_end):
        text = strip_parens(part["text"]).upper()
        t0 = part["t0"]
        u = span(t, t0 - 0.1, t0 + 0.05)
        u_out = span(t, line_end - 0.02, line_end + 0.12)
        if u <= 0 or u_out >= 1:
            return
        d = 1 if j == 0 else -1
        y = 390 if j == 0 else 700
        rgb = CYAN if j == 0 else PINK
        f = self.font("blackops", 190)
        w_ = f.measureText(text)
        x = CX - w_ / 2 - d * (1 - ease_out(u)) * 1800 + d * 2000 * ease_in(u_out)
        c.save()
        c.translate(x, y)
        c.skew(-0.25 * d, 0)
        b = skia.TextBlob.MakeFromString(text, f)
        for g in range(4):                               # hareket izi
            c.drawTextBlob(b, -d * g * 60 * (1 - u + 0.3), 68, fill(rgb, 0.18 * (4 - g) / 4))
        hs = self.hit_shake(t)
        jx, jy = hs * noise(t * 70, 7 + j), hs * noise(t * 70, 9 + j)
        c.drawTextBlob(b, 12 + jx, 80 + jy, fill(INK))
        c.drawTextBlob(b, jx, 68 + jy, stroke(INK, 22))
        c.drawTextBlob(b, jx, 68 + jy, fill(rgb))
        c.drawTextBlob(b, jx, 68 + jy, stroke(WHITE, 4, 0.9))
        c.restore()

    def draw_moonword(self, c, t, part, line_end):
        text = part["text"]
        t0 = part["t0"]
        u = span(t, t0 - 0.08, t0 + 0.3)
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        if u <= 0 or u_out >= 1:
            return
        a = (1 - u_out)
        f = self.font("anton", 150)
        tracking = lerp(60, 14, ease_out(u))
        x = 150
        for i, ch in enumerate(text.upper()):
            b = self.blob("anton", 150, ch)
            ui = span(t, t0 - 0.08 + 0.03 * i, t0 + 0.1 + 0.03 * i)
            yy = 380 - (1 - ease_out(ui)) * 80
            c.drawTextBlob(b, x + 7, yy + 7, fill(BLUE, a * ui))
            c.drawTextBlob(b, x, yy, fill(MOON, a * ui))
            x += f.measureText(ch) + tracking

    def draw_tonight(self, c, t, part, next_t, line_end):
        """Dev 'TONIGHT': patlamayla gelir, ana satır başlayınca tepeye küçülür."""
        text = part["text"].upper()
        t0 = part["t0"]
        u = span(t, t0 - 0.06, t0 + 0.12)
        if u <= 0:
            return
        shrink = ease_in_out(span(t, next_t - 0.08, next_t + 0.22))
        u_out = span(t, line_end - 0.02, line_end + 0.1)
        a = 1 - u_out
        size = lerp(330, 120, shrink)
        y = lerp(560, 215, shrink)
        f = self.font("anton", size)
        tracking = lerp(10, 40, shrink)
        widths = [f.measureText(ch) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = CX - total / 2
        hs = self.hit_shake(t) + self.tremolo(t) * 0.6
        for i, ch in enumerate(text):
            b = self.blob("anton", size, ch)
            rgb = RAINBOW[(i + int(t * 10)) % len(RAINBOW)]
            sc = lerp(1.8, 1.0, ease_out(u))
            c.save()
            c.translate(x + widths[i] / 2 + hs * noise(t * 60, i), y + hs * noise(t * 60, i + 20))
            c.scale(sc, sc)
            c.drawTextBlob(b, -widths[i] / 2 + size * 0.04, size * 0.36 + size * 0.04, fill(rgb, a))
            c.drawTextBlob(b, -widths[i] / 2, size * 0.36, stroke(INK, size * 0.08, a))
            c.drawTextBlob(b, -widths[i] / 2, size * 0.36, fill(WHITE, a))
            c.restore()
            x += widths[i] + tracking

    # ------------------------------------------------------------ satırlar

    def draw_lines(self, c, t):
        for line in self.lines:
            first = line["parts"][0]["t0"]
            if t < first - 0.3 or t > line["end"] + 0.3:
                continue
            look, i = line["look"], line["index"]
            parts, end = line["parts"], line["end"]
            row_i = 0
            n_light = 0
            for j, part in enumerate(parts):
                kind = part["kind"]
                next_t = parts[j + 1]["t0"] if j + 1 < len(parts) else end
                seed = i * 17 + j
                if kind == "rog":
                    self.draw_rog(c, t, part, end, next_t)
                elif kind == "yeah":
                    self.draw_yeah(c, t, part, end)
                elif kind == "ratatta":
                    self.draw_ratatta(c, t, part, look, end, seed)
                elif kind == "light":
                    # sonraki ışık gelince önceki şerit kaybolur
                    self.draw_light(c, t, part, next_t if n_light == 0 and j + 1 < len(parts) else end, big=(i == 3))
                    n_light += 1
                elif kind == "chase":
                    self.draw_chase(c, t, part, j, end)
                elif kind == "moon":
                    self.draw_moonword(c, t, part, end)
                elif kind == "tonight":
                    self.draw_tonight(c, t, part, next_t, end)
                elif kind == "main":
                    row = look["rows"][row_i]
                    fills = look.get("row_fill")
                    shadows = look.get("row_shadow")
                    hls = look.get("row_hl")
                    extra = {}
                    if look.get("wave"):
                        extra["wave"] = look["wave"]
                    if look.get("sway"):
                        extra["sway"] = True
                    if row_i in look.get("trem_rows", []):
                        extra["trem"] = self.tremolo(t) * 1.6 + 2.5 * (t >= part["t0"])
                    if row_i in look.get("rainbow_rows", []):
                        extra["rainbow"] = True
                    text = part["text"] if kind != "main" else strip_parens(part["text"])
                    self.draw_row(c, t, text, look, row, part["t0"], part["t0"], part["t1"], end, seed,
                                  fill_rgb=fills[row_i] if fills else None,
                                  shadow_rgb=shadows[row_i] if shadows else None,
                                  hl_rgb=hls[row_i] if hls else None, extra=extra)
                    size = self.row_layout(text, look["face"], row[2], row[0], row[3])[0]
                    self.draw_romaji(c, t, strip_parens(part["romaji"]), row, look, part["t0"], part["t0"],
                                     part["t1"], end, size, hl_rgb=hls[row_i] if hls else None)
                    row_i += 1

    # ------------------------------------------------------------ fırtına başlığı

    def draw_storm_title(self, c, t):
        t0 = 14.071
        if not t0 <= t < 20.9:
            return
        letters = "ANDROE"
        beats8 = [14.28, 14.489, 14.69, 14.884, 15.09, 15.302]
        t_studio, t_move, t_queen, t_out = 15.72, 17.438, 17.438, 20.45
        move = ease_in_out(span(t, t_move - 0.05, t_move + 0.35))
        out = ease_in(span(t, t_out, 20.735))
        c.save()
        c.translate(-out * 2400, 0)
        # ANDROE STUDIO
        size = lerp(210, 110, move)
        cy = lerp(470, 215, move)
        f = self.font("mont", size)
        widths = [f.measureText(ch) for ch in letters]
        tracking = size * 0.06
        total = sum(widths) + tracking * 5
        x = CX - total / 2
        hs = self.hit_shake(t)
        for i, ch in enumerate(letters):
            ti = beats8[i]
            u = span(t, ti - 0.07, ti + 0.03)
            if u > 0:
                sc = lerp(3.0, 1.0, ease_out(u))
                b = self.blob("mont", size, ch)
                flash = decay(t, 17.438, 0.3) + decay(t, 15.72, 0.25)
                c.save()
                c.translate(x + widths[i] / 2 + hs * noise(t * 70, i), cy + hs * noise(t * 70, i + 9))
                c.scale(sc, sc)
                c.drawTextBlob(b, -widths[i] / 2 + 10, size * 0.36 + 10, fill(VIOLET, min(1, 3 * u)))
                c.drawTextBlob(b, -widths[i] / 2, size * 0.36, fill(mix(WHITE, CYAN, 0.25 * flash), min(1, 3 * u)))
                c.restore()
                if t - ti < 0.35:
                    shockwave(c, t, ti, x + widths[i] / 2, cy, 240, CYAN, dur=0.35, width=10)
            x += widths[i] + tracking
        us = span(t, t_studio - 0.1, t_studio + 0.25)
        if us > 0:
            ss = lerp(80, 46, move)
            fs = self.font("montsemi", ss)
            word = "STUDIO"
            tr = lerp(ss * 2.2, ss * 0.55, ease_out(us))
            ws = [fs.measureText(ch) for ch in word]
            tot = sum(ws) + tr * 5
            xs = CX - tot / 2
            ys = cy + size * 0.62 + ss * 0.5
            for i, ch in enumerate(word):
                c.drawTextBlob(self.blob("montsemi", ss, ch), xs, ys, fill(WHITE, ease_out(us)))
                xs += ws[i] + tr
            c.drawRect(skia.Rect(CX - tot / 2, ys + ss * 0.35, CX - tot / 2 + tot * ease_out(us), ys + ss * 0.35 + 5),
                       fill(CYAN, 0.9))
        # QUEEN / LiSA başlık kartı
        uq = span(t, t_queen - 0.06, t_queen + 0.18)
        if uq > 0:
            sc = lerp(2.4, 1.0, ease_out(uq))
            c.save()
            c.translate(CX, 640)
            c.scale(sc, sc)
            c.drawPath(crown(0, -215, 210), fill(GOLD))
            c.drawPath(crown(0, -215, 210), stroke(INK, 10))
            for k in range(3):
                c.drawCircle((k - 1) * 58, -222, 13, fill((RED, CYAN, GREEN)[k]))
            f = self.font("anton", 260)
            word = "QUEEN"
            w_ = f.measureText(word)
            b = skia.TextBlob.MakeFromString(word, f)
            c.drawTextBlob(b, -w_ / 2 + 12, 94 + 12, fill(RED))
            c.drawTextBlob(b, -w_ / 2, 94, stroke(INK, 22))
            c.drawTextBlob(b, -w_ / 2, 94, fill(GOLD))
            gx = ((t - t_queen) * 1600) % 2400 - 900
            shader = skia.GradientShader.MakeLinear([skia.Point(gx - 120, -150), skia.Point(gx + 120, 150)],
                                                    [col(WHITE, 0).toColor(), col(WHITE, 0.9).toColor(),
                                                     col(WHITE, 0).toColor()])
            pg = skia.Paint(AntiAlias=True, Shader=shader)
            pg.setBlendMode(skia.BlendMode.kSrcATop)
            c.drawTextBlob(b, -w_ / 2, 94, pg)
            ul = span(t, 19.11 - 0.06, 19.11 + 0.2)
            if ul > 0:
                f2 = self.font("montsemi", 64)
                word2 = "L i S A"
                w2 = f2.measureText(word2)
                c.drawTextBlob(skia.TextBlob.MakeFromString(word2, f2), -w2 / 2, 210 - 30 * (1 - ul), fill(WHITE, ul))
            c.restore()
        c.restore()

    # ------------------------------------------------------------ vuruş efektleri

    def draw_hits(self, c, t):
        for i, (th, pw, kind) in enumerate(HITS):
            dt = t - th
            if dt < 0 or dt > 1.8:
                continue
            if kind in ("start", "drop", "chorus", "tonight", "final"):
                pal = {"start": (RED, GREEN), "drop": (VIOLET, CYAN), "chorus": (GOLD, PINK, CYAN),
                       "tonight": (PINK, VIOLET, GOLD), "final": (GOLD, CYAN, PINK)}[kind]
                explosion(c, t, th, CX, CY, 260 if pw >= 4 else 170, pal, seed=i * 7 + 3, power=pw)
            elif kind in ("red", "green"):
                x = CX - 420 if kind == "red" else CX + 420
                explosion(c, t, th, x, 560, 200, (RED, ORANGE) if kind == "red" else (GREEN, CYAN), seed=i * 7, power=3)
            elif kind == "chase":
                y = 390 if th < 28.6 else 700
                explosion(c, t, th, CX, y, 120, (CYAN, PINK), seed=i * 7, power=2)
            elif kind == "seal":
                hanko(c, CX, 650, 250 * ease_out_back(clamp01(dt / 0.15), 2.2), RED,
                      a=clamp01(1.0 - span(t, 37.35, 37.55)) * min(1.0, dt / 0.04), rot=-0.2)
                debris(c, t, th, CX, 650, 20, 1400, 0.8, (RED, (0.6, 0.0, 0.1)), seed=i, size=16)
            elif kind == "correct":
                debris(c, t, th, CX, 690, 40, 2200, 1.4, RAINBOW, seed=i, size=18, gravity=1500)
                shockwave(c, t, th, CX, 690, 900, WHITE, dur=0.5, width=30)
            elif kind in ("bass", "bar", "whip", "clouds", "moon", "glare", "scratch", "bolt"):
                if pw >= 2 and kind not in ("bolt", "glare", "scratch"):
                    shockwave(c, t, th, CX, CY, 1100, WHITE, dur=0.45, width=18, a=0.5)
                if kind == "bass":
                    debris(c, t, th, CX, CY, 24, 2400, 1.0, (GOLD, WHITE, RED, GREEN), seed=i, size=16)

    def flash(self, t):
        """Tam ekran flaş rengi ve miktarı."""
        best = (WHITE, 0.0)
        for th, pw, kind in HITS:
            if th <= t < th + 0.6:
                if kind in ("drop", "chorus", "tonight"):
                    a = decay(t, th, 0.16)
                elif kind == "final":
                    a = 1.0 if t < th + 0.08 else decay(t, th + 0.08, 0.12)
                elif kind == "start":
                    a = 0.8 * decay(t, th, 0.1)
                elif kind == "bolt":
                    a = (0.25 + 0.12 * pw) * decay(t, th, 0.06)
                elif pw >= 3:
                    a = 0.35 * decay(t, th, 0.08)
                else:
                    a = 0.0
                if a > best[1]:
                    best = (WHITE, a)
        return best

    def draw_wipes(self, c, t):
        for tw, kind, rgb in WIPES:
            dt = t - tw
            if not -0.16 <= dt <= 0.16:
                continue
            u = (dt + 0.16) / 0.32                       # 0 -> 1, ortada ekran tamamen kaplı
            if kind in ("slash", "slash_r"):
                d = 1 if kind == "slash" else -1
                lead = lerp(-1400, W + 1400, ease_in_out(u))
                x_a, x_b = lead - 1300, lead + 1300
                if d < 0:
                    x_a, x_b = W - x_b, W - x_a
                sk = 420
                c.drawPath(poly([(x_a + sk, -50), (x_b + sk, -50), (x_b - sk, H + 50), (x_a - sk, H + 50)]), fill(rgb))
                for k, cc in enumerate((WHITE, INK)):
                    off = (1 - 2 * k) * 40 + (x_b if d > 0 else x_a)
                    c.drawPath(poly([(off + sk, -50), (off + sk + 26, -50), (off - sk + 26, H + 50), (off - sk, H + 50)]),
                               fill(cc))
            elif kind == "shutter":
                n = 6
                for k in range(n):
                    v = clamp01(1 - abs(u - 0.5) * 2 * 1.15 + (k % 2) * 0.05)
                    hw = W / n / 2 * ease_out(v)
                    xk = (k + 0.5) * W / n
                    c.drawRect(skia.Rect(xk - hw - 1, -10, xk + hw + 1, H + 10), fill(rgb if k % 2 else WHITE))
            elif kind == "blinds":
                n = 8
                for k in range(n):
                    v = clamp01(1 - abs(u - 0.5) * 2 * 1.15)
                    hh = H / n / 2 * ease_out(v)
                    yk = (k + 0.5) * H / n
                    c.drawRect(skia.Rect(-10, yk - hh - 1, W + 10, yk + hh + 1), fill(rgb if k % 2 else INK))

    def draw_end(self, c, t):
        if t < FINAL_HIT + 0.1:
            return
        u = span(t, FINAL_HIT + 0.15, FINAL_HIT + 0.4)
        v = 1 - span(t, DURATION - 0.35, DURATION - 0.05)
        a = u * v
        f = self.font("mont", 86)
        word = "ANDROE STUDIO"
        w_ = f.measureText(word)
        c.drawTextBlob(skia.TextBlob.MakeFromString(word, f), CX - w_ / 2, CY + 30, fill(WHITE, a))
        c.drawRect(skia.Rect(CX - w_ / 2 * u, CY + 70, CX + w_ / 2 * u, CY + 76), fill(CYAN, a))

    def draw_credit(self, c, t):
        a = span(t, 0.5, 0.9)
        if a <= 0:
            return
        f1 = self.font("montsemi", 30)
        f2 = self.font("montsemi", 19)
        w1, w2 = f1.measureText(CREDIT_TITLE), f2.measureText(CREDIT_NOTE)
        wmax = max(w1 + 46, w2)
        x1 = W - 44
        rect = skia.Rect(x1 - wmax - 28, H - 124, x1 + 16, H - 34)
        c.drawRRect(skia.RRect.MakeRectXY(rect, 16, 16), fill(INK, 0.62 * a))
        c.drawRect(skia.Rect(rect.left(), rect.top() + 14, rect.left() + 5, rect.bottom() - 14),
                   fill(mix(RED, GREEN, 0.5 + 0.5 * math.sin(t * 2)), a))
        # nota simgesi
        from queen_fx import note as note_path
        c.drawPath(note_path(x1 - w1 - 24, H - 78, 34), fill(GOLD, a))
        c.drawString(CREDIT_TITLE, x1 - w1, H - 78, f1, fill(WHITE, a))
        c.drawString(CREDIT_NOTE, x1 - w2, H - 50, f2, fill((0.85, 0.85, 0.9), a))

    # ------------------------------------------------------------ kare

    def draw(self, c, t):
        c.save()
        c.scale(self.k, self.k)
        name, s0, s1 = self.scene_at(t)
        sx, sy, rot, zoom = self.camera(t)
        c.save()
        c.translate(CX + sx, CY + sy)
        c.rotate(rot)
        c.scale(zoom, zoom)
        c.translate(-CX, -CY)
        PAINTERS[name](self, c, t)
        if name == "storm":
            self.draw_storm_title(c, t)
        self.draw_hits(c, t)
        self.draw_lines(c, t)
        c.restore()
        self.draw_wipes(c, t)
        rgb, a = self.flash(t)
        if a > 0.003:
            c.drawPaint(fill(rgb, a))
        if t >= FINAL_HIT + 0.08:                        # final: beyazdan siyaha
            c.drawPaint(fill(INK, span(t, FINAL_HIT + 0.08, FINAL_HIT + 0.3)))
        self.draw_end(c, t)
        # kenar karartması
        shader = skia.GradientShader.MakeRadial(skia.Point(CX, CY), 1150,
                                                [col(INK, 0).toColor(), col(INK, 0).toColor(), col(INK, 0.55).toColor()],
                                                [0.0, 0.6, 1.0])
        c.drawPaint(skia.Paint(Shader=shader))
        self.draw_credit(c, t)
        c.restore()

    def post(self, rgb, t):
        """Kromatik sapma ve dev vuruşlarda iki karelik ters renk."""
        orig = rgb
        ca = 0.0
        for th, pw, kind in HITS:
            if pw >= 2 and th <= t < th + 0.5:
                ca += (0, 0, 5, 9, 16)[pw] * decay(t, th, 0.1)
        ca += self.tremolo(t) * 0.35
        d = int(round(ca * self.k))
        if d >= 1:
            out = rgb.copy()
            out[:, d:, 0] = rgb[:, :-d, 0]
            out[:, :-d, 2] = rgb[:, d:, 2]
            rgb = out
        for th, pw, kind in HITS:
            if pw >= 4 and kind != "final" and th <= t < th + 2.0 / self.fps:
                rgb = 255 - rgb if rgb is orig else np.subtract(255, rgb, out=rgb)
        if rgb is not orig:                              # sağ alttaki yazı efektlerden etkilenmez
            y0, x0 = int((H - 130) * self.k), int((W - 700) * self.k)
            rgb[y0:, x0:] = orig[y0:, x0:]
        return rgb

    def render(self, t):
        with self.surface as c:
            self.draw(c, t)
        rgb = self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]
        return np.ascontiguousarray(self.post(rgb, t))
