"""QUEEN (LiSA) fan yapımı lyric video - görsel sahne (61 saniye, 1920x1080, modern minimal).

Katmanlar (arkadan öne):
  arka plan (queen_bg) -> patlamalar -> 3B dansçılar (queen_dancers, toon render) ->
  sözler (kanji + romaji) -> sahne geçişleri -> flaş -> kenar karartması -> telif notu

Akış (saniye, şarkıyla aynı saat):
   0.0   ince ışık çizgisi açılır; 0.49'da ilk vuruşta patlama, dansçılar belirir
   0.5   dört "Red or Green?" satırı: kırmızı/yeşil bölünmüş ekran, dansçılar işaret eder,
         hecelerde tepinir, "Red Light?"ta donar, 10.85'te zıplar
  12.4   durak: 12.77 kırmızı, 13.32 yeşil flaş; dansçılar donar, çömelir
  14.07  DEV PATLAMA: dansçılar ekranın üstünden fırlar -> fırtına + ANDROE STUDIO, QUEEN / LiSA
  20.7   dansçılar yukarıdan düşer; verse: salınım, pırıltı elleri, keskin pozlar, kovalamaca
         (iki dansçı yer değiştirir), uzanıp yakalama, dönüş, dalga
  34.4   nakarat öncesi: kalp / X / açık kollar, düşünme -> fikir -> kollarla ○, çiçek açma
  48.09  NAKARAT PATLAMASI: zıplama, bulutları yarma, dev ay, idol dansı
  54.86  "Tonight" DEV PATLAMA: konser ışıkları, projektör kolları; son uzun notada gökyüzüne uzanma
  60.09  FİNAL: kraliçe pozu, beyaz flaş, siyahta ANDROE STUDIO

Sözler input/queen_sozler.txt dosyasından okunur (queen.py yükler).
"""
import math
from bisect import bisect_right
from pathlib import Path

import numpy as np
import skia

from queen_bg import ACCENTS, PAINTERS, glow, intro_line
from queen_fx import (ADD, BLUE, CX, CY, CYAN, GOLD, GREEN, H, INK, LIME, MOON, ORANGE, PINK, RAINBOW, RED,
                      VIOLET, W, WHITE, clamp01, col, crown, decay, ease_in, ease_in_out, ease_out,
                      ease_out_elastic, fill, flare_burst, hash01, lerp, mix, noise, note, poly, shockwave, span,
                      stroke)
from queen_timing import BEATS, DURATION, FINAL_HIT, HITS, LINES, SCENES

FONTS = Path(__file__).resolve().parent / "fonts"
FACES = {
    "noto": "NotoSansJP-Black.ttf", "mont": "Montserrat-Black.ttf", "montsemi": "Montserrat-SemiBold.ttf",
    "inter": "Inter-Black.ttf",
}

LAVENDER = (0.75, 0.65, 1.0)
PALE = (0.7, 0.8, 1.0)
RED_HL = (1.0, 0.45, 0.52)                     # koyu kırmızı / yeşil zeminde okunur dolum tonları
GREEN_HL = (0.5, 1.0, 0.72)

# Satır görünümleri (LINES ile aynı sırada). rows: ana (kanji) parçaların yeri (x, y, punto, hizalama),
# dansçıların üstündeki alana yerleşir. hl: söylenirken dolan renk. enter/exit: giriş ve çıkış.
LOOKS = [
    dict(hl=RED_HL, rows=[(CX, 262, 128, "c")], enter="rise", exit="fade"),
    dict(hl=GREEN_HL, rows=[(CX, 232, 170, "c")], enter="punch", exit="zoom"),
    dict(hl=RED_HL, rows=[(CX, 232, 118, "c"), (CX, 408, 128, "c")], enter="punch", exit="scatter"),
    dict(hl=GREEN_HL, rows=[(CX, 228, 176, "c")], enter="punch", exit="scatter"),
    dict(hl=PINK, rows=[(170, 200, 112, "l"), (W - 170, 372, 112, "r")], enter="slide", exit="fade"),
    dict(hl=GOLD, rows=[(CX, 188, 100, "c"), (CX, 360, 168, "c")], enter="rise", exit="zoom",
         row_fill=[WHITE, (1.0, 0.9, 0.62)]),
    dict(hl=CYAN, rows=[]),
    dict(hl=LAVENDER, rows=[(CX, 200, 118, "c"), (CX, 382, 160, "c")], enter="mask", exit="scatter"),
    dict(hl=CYAN, rows=[(CX - 330, 222, 150, "c"), (CX + 330, 392, 150, "c")], enter="rise", exit="drop", wave=14),
    dict(hl=PINK, rows=[(CX, 186, 106, "c"), (CX, 366, 170, "c")], enter="slide", exit="scatter",
         row_hl=[PINK, RED]),
    dict(hl=LIME, rows=[(190, 196, 112, "l"), (W - 190, 378, 124, "r")], enter="rise", exit="fade"),
    dict(hl=CYAN, rows=[(CX, 150, 92, "c"), (CX, 292, 108, "c"), (CX, 448, 148, "c")], enter="mask", exit="scatter",
         row_hl=[CYAN, CYAN, RED]),
    dict(hl=GOLD, rows=[(CX, 188, 112, "c"), (CX, 368, 164, "c")], enter="rise", exit="scatter", rainbow_rows=[1]),
    dict(hl=PALE, rows=[(140, 300, 112, "l"), (140, 462, 112, "l")], enter="mask", exit="fade"),
    dict(hl=PINK, rows=[(CX - 110, 200, 118, "c"), (CX - 110, 380, 132, "c")], enter="rise", exit="scatter",
         sway=True),
    dict(hl=GOLD, rows=[(CX, 262, 122, "c"), (CX, 440, 190, "c")], enter="punch", exit="final", trem_rows=[1],
         rainbow_rows=[1]),
]

# Sahne geçişleri: (zaman, tür, vurgu rengi)
WIPES = [(20.735, "slash", VIOLET), (24.52, "shutter", GOLD), (27.72, "slash_r", CYAN), (29.19, "blinds", LAVENDER),
         (31.60, "slash", CYAN), (34.366, "shutter", PINK), (37.50, "slash_r", LIME), (40.98, "blinds", BLUE),
         (44.56, "slash", PINK)]

CREDIT_TITLE = "LiSA  —  QUEEN"
CREDIT_NOTE = "Fan-made lyric video · Song © LiSA / original rights holders"

# 3B kamera: dansçılar ekranın alt yarısında, ayaklar ~1045 px'te
CAM_EYE, CAM_TARGET, CAM_FOV = (0.0, 1.62, 7.2), (0.0, 1.555, 0.0), 26.0


def strip_parens(s):
    return s.replace("(", "").replace(")", "").strip()


class QueenScene:
    def __init__(self, lyrics, width=1920, height=1080, fps=60, bake_path=None):
        self.width, self.height, self.fps = width, height, fps
        self.duration = DURATION
        self.k = width / W
        self.surface = skia.Surface(width, height)
        self.faces = {k: skia.Typeface.MakeFromFile(str(FONTS / v)) for k, v in FACES.items()}
        self._fonts, self._blobs = {}, {}
        self.lines = self._bind(lyrics)
        self.scene_t = [s[0] for s in SCENES]
        self.bake = None
        if bake_path is not None:
            from queen_choreo import NAMES, load_bake
            from queen_dancers import Dancer, ToonRenderer, look_at, perspective
            self.bake = load_bake(bake_path)
            self.dancers = [Dancer(n) for n in NAMES]
            self.toon = ToonRenderer(width, height)
            self.view = look_at(CAM_EYE, CAM_TARGET)
            self.proj = perspective(CAM_FOV, width / height)

    # ------------------------------------------------------------ veri

    def _bind(self, lyrics):
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

    def accent(self, t):
        name = self.scene_at(t)[0]
        a = ACCENTS.get(name)
        if a is not None:
            return a
        if name == "signal":
            li = intro_line(t)
            if li == 3:
                return RED if 12.7 <= t < 13.3 else GREEN
            return RED if li % 2 == 0 else GREEN
        return RAINBOW[int(t * 3) % len(RAINBOW)]

    # ------------------------------------------------------------ kamera

    def tremolo(self, t):
        if 13.63 <= t < 14.071:
            return 10 * ease_in(span(t, 13.63, 14.071))
        if 46.8 <= t < 48.089:
            return 6 * ease_in(span(t, 46.8, 48.089))
        if 57.72 <= t < FINAL_HIT:
            return 2 + 12 * ease_in(span(t, 57.72, FINAL_HIT))
        return 0.0

    def camera(self, t):
        sx = sy = rot = 0.0
        zoom = 1.0
        for i, (th, pw, kind) in enumerate(HITS):
            if t < th or t > th + 1.5:
                continue
            e = decay(t, th, 0.09 + 0.05 * pw)
            amp = (0, 4, 10, 20, 36)[pw]
            sx += amp * e * noise(t * 38, i * 3)
            sy += amp * e * noise(t * 38, i * 3 + 1)
            rot += 0.04 * amp * e * noise(t * 30, i * 3 + 2)
            zoom += (0, 0.01, 0.025, 0.045, 0.08)[pw] * decay(t, th, 0.11)
        tr = self.tremolo(t)
        if tr > 0:
            sx += tr * noise(t * 55, 901)
            sy += tr * noise(t * 55, 902)
            rot += 0.05 * tr * noise(t * 40, 903)
        zoom += 0.05 * ease_in(span(t, 44.56, 48.089)) * (t < 48.089)
        zoom += 0.07 * ease_in(span(t, 57.72, FINAL_HIT)) * (t < FINAL_HIT)
        zoom += 0.04 * ease_in(span(t, 13.2, 14.071)) * (t < 14.071)
        zoom += 0.01 * self.beat_pulse(t) * (t > 7.268)
        return sx, sy, rot, zoom

    def hit_shake(self, t):
        s = 0.0
        for th, pw, kind in HITS:
            if pw >= 2 and th <= t < th + 0.6:
                s += (0, 0, 6, 12, 18)[pw] * decay(t, th, 0.12)
        return s

    # ------------------------------------------------------------ yazı motoru

    def row_layout(self, text, face, size, x, align, tracking=0.0, max_w=1640):
        font = self.font(face, size)
        glyphs = font.textToGlyphs(text)
        widths = list(font.getWidths(glyphs))
        total = sum(widths) + tracking * (len(widths) - 1)
        if total > max_w:
            size *= max_w / total
            return self.row_layout(text, face, size, x, align, tracking * max_w / total, max_w)
        x0 = x - total / 2 if align == "c" else (x if align == "l" else x - total)
        centers, acc = [], x0
        for w_ in widths:
            centers.append(acc + w_ / 2)
            acc += w_ + tracking
        return size, centers, widths, x0, total

    def draw_row(self, c, t, text, look, row, t_in, hl0, hl1, t_out, seed, fill_rgb=WHITE, hl_rgb=None, extra=None):
        """Kanji satırı: karakter karakter giriş, söylendikçe renk + ince ilerleme çizgisi, çıkış."""
        extra = extra or {}
        x, y, size, align = row
        size, centers, widths, x0, total = self.row_layout(text, "noto", size, x, align)
        n = len(text)
        hl = hl_rgb or look["hl"]
        enter, exit_ = look.get("enter", "rise"), look.get("exit", "fade")
        u_out = span(t, t_out - 0.02, t_out + 0.2)
        if u_out >= 1 or t < t_in - 0.3:
            return size
        base_off = size * 0.36
        mid_x = x0 + total / 2
        mask_u = ease_out(span(t, t_in - 0.12, t_in + 0.2)) if enter == "mask" else 1.0
        if enter == "mask":
            c.save()
            c.clipRect(skia.Rect(x0 - 20, y - size, x0 - 20 + (total + 40) * mask_u, y + size))
        prog = span(t, hl0, hl1)
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            st = 0.018 * i
            u = span(t, t_in - 0.14 + st, t_in + st)
            if enter == "mask":
                u = 1.0 if mask_u > 0 else 0.0
            if u <= 0:
                continue
            dx = dy = rot = 0.0
            sc, a = 1.0, 1.0
            r0 = hash01(i, seed)
            e = ease_out(u)
            if enter == "rise":
                dy = (1 - e) * 44
                sc = lerp(1.12, 1.0, e)
                a = min(1.0, u * 2.2)
            elif enter == "punch":
                sc = lerp(1.7, 1.0, e)
                a = min(1.0, u * 3)
            elif enter == "slide":
                d = -1 if align != "r" else 1
                dx = d * (1 - e) * 160
                a = min(1.0, u * 2)
            th = hl0 + (hl1 - hl0) * (i / max(n, 1)) * 0.94
            hu = span(t, th - 0.02, th + 0.08)
            nudge = math.sin(math.pi * span(t, th - 0.02, th + 0.2))
            dy -= nudge * size * 0.06
            this_hl = hl
            if extra.get("rainbow"):
                this_hl = RAINBOW[(i + int(t * 8)) % len(RAINBOW)]
            fill_now = mix(fill_rgb, this_hl, hu)
            if extra.get("wave"):
                dy += extra["wave"] * math.sin(t * 5.0 + i * 0.9)
            if extra.get("sway"):
                dx += 8 * math.sin(t * 6.3 + i * 0.5)
                rot += 5 * math.sin(t * 6.3 + i * 0.5)
            tr = extra.get("trem", 0.0)
            if tr:
                dx += tr * noise(t * 60, i * 5 + seed)
                dy += tr * noise(t * 60, i * 5 + seed + 1)
            hs = self.hit_shake(t)
            if hs > 0:
                dx += hs * noise(t * 70, i * 11 + seed)
                dy += hs * noise(t * 70, i * 11 + seed + 3)
            if u_out > 0:
                eo = ease_in(u_out)
                if exit_ in ("scatter", "final"):
                    dx += (centers[i] - mid_x) * 0.35 * eo + (r0 - 0.5) * 120 * eo
                    dy += (r0 - 0.5) * 90 * eo - 30 * eo
                    rot += (r0 - 0.5) * 30 * eo
                elif exit_ == "zoom":
                    sc *= 1 + 0.35 * eo
                elif exit_ == "drop":
                    dy += 70 * eo
                else:
                    dy -= 24 * eo
                a *= 1 - u_out
            if a <= 0.01:
                continue
            blob = self.blob("noto", size, ch)
            c.save()
            c.translate(centers[i] + dx, y + dy)
            c.rotate(rot)
            c.scale(sc, sc)
            ox, oy = -widths[i] / 2, base_off
            c.drawTextBlob(blob, ox, oy + size * 0.035, fill(INK, 0.55 * a, blur=size * 0.05))
            if hu > 0:
                c.drawTextBlob(blob, ox, oy, fill(this_hl, 0.45 * a * hu, blur=size * 0.09, blend=ADD))
            c.drawTextBlob(blob, ox, oy, fill(fill_now, a))
            if enter == "punch" and u < 1:               # hareket izi
                for g in (1, 2):
                    c.drawTextBlob(blob, ox, oy - g * 18 * (1 - e), fill(fill_now, 0.18 * a / g))
            c.restore()
        if enter == "mask":
            c.restore()
        # ince ilerleme çizgisi (satırın altında, söylendikçe uzar)
        la = min(1.0, span(t, t_in, t_in + 0.2)) * (1 - u_out)
        if la > 0.01 and prog > 0:
            ly = y + size * 0.55
            c.drawRect(skia.Rect(x0, ly, x0 + total * prog, ly + 3), fill(hl, 0.9 * la))
        return size

    def draw_romaji(self, c, t, text, row, look, t_in, hl0, hl1, t_out, main_size, hl_rgb=None):
        x, y, size, align = row
        rs = max(24.0, min(34.0, main_size * 0.24))
        font = self.font("montsemi", rs)
        tracking = rs * 0.16
        glyphs = font.textToGlyphs(text)
        widths = font.getWidths(glyphs)
        total = sum(widths) + tracking * (len(widths) - 1)
        x0 = x - total / 2 if align == "c" else (x if align == "l" else x - total)
        yy = y + main_size * 0.62 + rs * 1.05
        u = ease_out(span(t, t_in - 0.02, t_in + 0.25))
        u_out = span(t, t_out - 0.02, t_out + 0.14)
        a = u * (1 - u_out)
        if a <= 0.01:
            return
        yy += (1 - u) * 16
        prog = span(t, hl0, hl1)
        hl = hl_rgb or look["hl"]
        xs, acc = [], x0
        for w_ in widths:
            xs.append(acc)
            acc += w_ + tracking
        for pass_, (rgb, clip) in enumerate(((WHITE, None), (hl, x0 + prog * total))):
            if clip is not None:
                if prog <= 0:
                    break
                c.save()
                c.clipRect(skia.Rect(x0 - 10, yy - rs * 1.4, clip, yy + rs * 0.6))
            for ch, px in zip(text, xs):
                if ch == " ":
                    continue
                b = self.blob("montsemi", rs, ch)
                if pass_ == 0:
                    c.drawTextBlob(b, px, yy + 2, fill(INK, 0.6 * a, blur=3))
                c.drawTextBlob(b, px, yy, fill(rgb, a * (0.78 if pass_ == 0 else 1.0)))
            if clip is not None:
                c.restore()

    # ------------------------------------------------------------ özel parçalar

    def draw_rog(self, c, t, part, line_end):
        """'Red or Green?': ekranın tepesinde ince tipografi; kelimeler hece hece yanar."""
        words = strip_parens(part["text"]).split()
        t0 = part["t0"]
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        if t < t0 - 0.1 or u_out >= 1:
            return
        a_all = 1 - u_out
        sizes = (58, 34, 58)
        faces = ("mont", "montsemi", "mont")
        colors = (RED, WHITE, GREEN)
        ws = [self.font(fc, s).measureText(wd.upper()) for fc, s, wd in zip(faces, sizes, words)]
        gap = 26
        total = sum(ws) + gap * (len(ws) - 1)
        x = CX - total / 2
        y = 100
        p = self.beat_pulse(t)
        bi = self.beat_index(t)
        for j, (wd, fc, sz, w_) in enumerate(zip(words, faces, sizes, ws)):
            uj = span(t, t0 + 0.2 * j - 0.06, t0 + 0.2 * j + 0.1)
            if uj > 0:
                a = a_all * uj
                s = 1 + 0.25 * (1 - ease_out(uj))
                c.save()
                c.translate(x + w_ / 2, y)
                c.scale(s, s)
                b = skia.TextBlob.MakeFromString(wd.upper(), self.font(fc, sz))
                c.drawTextBlob(b, -w_ / 2, sz * 0.36 + 3, fill(INK, 0.5 * a, blur=4))
                c.drawTextBlob(b, -w_ / 2, sz * 0.36, fill(colors[j % 3], a))
                c.restore()
            x += w_ + gap
        for side, rgb, on in ((-1, RED, bi % 2 == 0), (1, GREEN, bi % 2 == 1)):
            lx = CX + side * (total / 2 + 44)
            lit = (0.35 + 0.65 * on * p) * a_all
            c.drawCircle(lx, y, 12, stroke(rgb, 2.5, a_all))
            c.drawCircle(lx, y, 7, fill(rgb, lit))
            glow(c, lx, y, 60, rgb, 0.5 * lit)

    def draw_yeah(self, c, t, part, line_end):
        t0 = part["t0"]
        u = span(t, t0 - 0.06, t0 + 0.3)
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        if u <= 0 or u_out >= 1:
            return
        x, y = W - 290, 300
        s = ease_out_elastic(u) * (1 - 0.3 * u_out)
        a = 1 - u_out
        c.save()
        c.translate(x, y)
        c.rotate(-8)
        c.scale(s, s)
        c.drawCircle(0, 0, 92, stroke(GOLD, 3, a))
        c.drawCircle(0, 0, 104 + 30 * (1 - u), stroke(WHITE, 1.5, a * (1 - u)))
        f = self.font("mont", 64)
        text = part["text"].upper()
        w_ = f.measureText(text)
        b = skia.TextBlob.MakeFromString(text, f)
        c.drawTextBlob(b, -w_ / 2, 23, fill(INK, 0.5 * a, blur=4))
        c.drawTextBlob(b, -w_ / 2, 20, fill(GOLD, a))
        c.restore()

    def draw_ratatta(self, c, t, part, look, line_end, seed):
        text = part["text"]
        row = look["rows"][0]
        size, centers, widths, x0, total = self.row_layout(text, "noto", row[2], row[0], row[3])
        groups, i = [], 0
        while i < len(text):
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
            rgb = (RED, GREEN)[g % 2]
            for i in idxs:
                sc = lerp(2.2, 1.0, ease_out(u)) * (1 + 0.4 * ease_in(u_out))
                a = min(1.0, u * 3) * (1 - u_out)
                if a <= 0.01:
                    continue
                c.save()
                c.translate(centers[i] + self.hit_shake(t) * noise(t * 70, i), row[1])
                c.scale(sc, sc)
                b = self.blob("noto", size, text[i])
                ox, oy = -widths[i] / 2, size * 0.36
                c.drawTextBlob(b, ox, oy + 6, fill(INK, 0.55 * a, blur=size * 0.05))
                c.drawTextBlob(b, ox, oy, fill(rgb, 0.5 * a, blur=size * 0.1, blend=ADD))
                c.drawTextBlob(b, ox, oy, fill(WHITE, a))
                c.restore()
            if 0 < t - tg < 0.35:
                shockwave(c, t, tg, centers[idxs[0]], row[1], 200, rgb, dur=0.35, width=3)
        self.draw_romaji(c, t, part["romaji"], row, dict(hl=GOLD), part["t0"], part["t0"], part["t1"], line_end, size)

    def draw_light(self, c, t, part, until, big):
        text = part["text"].upper()
        rgb = RED if text.startswith("RED") else GREEN
        t0 = part["t0"]
        u = span(t, t0 - 0.07, t0 + 0.12)
        u_out = span(t, until - 0.02, until + 0.12)
        if u <= 0 or u_out >= 1:
            return
        a = 1 - u_out
        y, size, band_h = (488, 112, 150) if big else (478, 70, 96)
        slide = (1 - ease_out(u)) * (1 if rgb == RED else -1) * 900
        c.save()
        c.translate(slide, 0)
        c.drawRect(skia.Rect(-200, y - band_h / 2, W + 200, y + band_h / 2), fill(INK, 0.55 * a))
        c.drawRect(skia.Rect(-200, y - band_h / 2, W + 200, y - band_h / 2 + 2), fill(rgb, a))
        c.drawRect(skia.Rect(-200, y + band_h / 2 - 2, W + 200, y + band_h / 2), fill(rgb, a))
        f = self.font("mont", size)
        w_ = f.measureText(text)
        dot = size * 0.2
        total = w_ + dot * 2 + 36
        x = CX - total / 2
        on = 0.7 + 0.3 * math.sin(t * 30)
        c.drawCircle(x + dot, y, dot, fill(rgb, a))
        glow(c, x + dot, y, dot * 6, rgb, 0.55 * on * a)
        b = skia.TextBlob.MakeFromString(text, f)
        hs = self.hit_shake(t)
        jx, jy = hs * noise(t * 70, 5), hs * noise(t * 70, 6)
        c.drawTextBlob(b, x + dot * 2 + 36 + jx, y + size * 0.36 + jy, fill(rgb, a))
        c.restore()

    def draw_chase(self, c, t, part, j, line_end):
        text = strip_parens(part["text"]).upper()
        t0 = part["t0"]
        u = span(t, t0 - 0.1, t0 + 0.05)
        u_out = span(t, line_end - 0.02, line_end + 0.12)
        if u <= 0 or u_out >= 1:
            return
        d = 1 if j == 0 else -1
        y = 300 if j == 0 else 462
        rgb = CYAN if j == 0 else PINK
        f = self.font("mont", 140)
        w_ = f.measureText(text)
        x = CX - w_ / 2 - d * (1 - ease_out(u)) * 1600 + d * 1900 * ease_in(u_out)
        c.save()
        c.translate(x, y)
        c.skew(-0.18 * d, 0)
        b = skia.TextBlob.MakeFromString(text, f)
        for k in range(4):                               # hız çizgileri
            yy = -20 + k * 22
            ln = 240 + 120 * hash01(k, j)
            c.drawLine(-d * 30, yy, -d * (30 + ln * (1.2 - u)), yy, stroke(rgb, 2, 0.6))
        hs = self.hit_shake(t)
        jx, jy = hs * noise(t * 70, 7 + j), hs * noise(t * 70, 9 + j)
        c.drawTextBlob(b, jx, 50 + jy + 6, fill(INK, 0.5, blur=6))
        c.drawTextBlob(b, jx, 50 + jy, fill(rgb, 0.45, blur=16, blend=ADD))
        c.drawTextBlob(b, jx, 50 + jy, fill(WHITE))
        c.restore()

    def draw_moonword(self, c, t, part, line_end):
        text = part["text"].upper()
        t0 = part["t0"]
        u_out = span(t, line_end - 0.02, line_end + 0.14)
        if t < t0 - 0.1 or u_out >= 1:
            return
        a_all = 1 - u_out
        f = self.font("mont", 80)
        tracking = 18
        x = 140
        for i, ch in enumerate(text):
            ui = span(t, t0 - 0.08 + 0.03 * i, t0 + 0.12 + 0.03 * i)
            if ui > 0:
                b = self.blob("mont", 80, ch)
                yy = 150 + (1 - ease_out(ui)) * 30
                c.drawTextBlob(b, x, yy + 29, fill(PALE, 0.5 * ui * a_all, blur=12, blend=ADD))
                c.drawTextBlob(b, x, yy + 29, fill(MOON, ui * a_all))
            x += f.measureText(ch) + tracking

    def draw_tonight(self, c, t, part, next_t, line_end):
        text = part["text"].upper()
        t0 = part["t0"]
        u = span(t, t0 - 0.06, t0 + 0.12)
        if u <= 0:
            return
        shrink = ease_in_out(span(t, next_t - 0.08, next_t + 0.22))
        u_out = span(t, line_end - 0.02, line_end + 0.1)
        a = 1 - u_out
        size = lerp(250, 70, shrink)
        y = lerp(430, 100, shrink)
        f = self.font("mont", size)
        tracking = lerp(8, 30, shrink)
        widths = [f.measureText(ch) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = CX - total / 2
        hs = self.hit_shake(t) + self.tremolo(t) * 0.5
        for i, ch in enumerate(text):
            b = self.blob("mont", size, ch)
            rgb = RAINBOW[(i + int(t * 10)) % len(RAINBOW)]
            sc = lerp(1.5, 1.0, ease_out(u))
            c.save()
            c.translate(x + widths[i] / 2 + hs * noise(t * 60, i), y + hs * noise(t * 60, i + 20))
            c.scale(sc, sc)
            c.drawTextBlob(b, -widths[i] / 2, size * 0.36, fill(rgb, 0.55 * a, blur=size * 0.08, blend=ADD))
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
                    self.draw_rog(c, t, part, end)
                elif kind == "yeah":
                    self.draw_yeah(c, t, part, end)
                elif kind == "ratatta":
                    self.draw_ratatta(c, t, part, look, end, seed)
                elif kind == "light":
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
                    fills, hls = look.get("row_fill"), look.get("row_hl")
                    extra = {}
                    if look.get("wave"):
                        extra["wave"] = look["wave"]
                    if look.get("sway"):
                        extra["sway"] = True
                    if row_i in look.get("trem_rows", []):
                        extra["trem"] = self.tremolo(t) * 1.3 + 2.0 * (t >= part["t0"])
                    if row_i in look.get("rainbow_rows", []):
                        extra["rainbow"] = True
                    text = strip_parens(part["text"])
                    hl = hls[row_i] if hls else None
                    size = self.draw_row(c, t, text, look, row, part["t0"], part["t0"], part["t1"], end, seed,
                                         fill_rgb=fills[row_i] if fills else WHITE, hl_rgb=hl, extra=extra)
                    self.draw_romaji(c, t, strip_parens(part["romaji"]), row, look, part["t0"], part["t0"],
                                     part["t1"], end, size, hl_rgb=hl)
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
        c.translate(0, -out * 700)
        size = lerp(190, 104, move)
        cy = lerp(470, 215, move)
        f = self.font("mont", size)
        widths = [f.measureText(ch) for ch in letters]
        tracking = size * 0.08
        total = sum(widths) + tracking * 5
        x = CX - total / 2
        hs = self.hit_shake(t)
        flash = decay(t, 17.438, 0.3) + decay(t, 15.72, 0.25)
        for i, ch in enumerate(letters):
            ti = beats8[i]
            u = span(t, ti - 0.07, ti + 0.03)
            if u > 0:
                sc = lerp(2.2, 1.0, ease_out(u))
                b = self.blob("mont", size, ch)
                c.save()
                c.translate(x + widths[i] / 2 + hs * noise(t * 70, i), cy + hs * noise(t * 70, i + 9))
                c.scale(sc, sc)
                a = min(1, 3 * u) * (1 - out)
                c.drawTextBlob(b, -widths[i] / 2, size * 0.36, fill(CYAN, 0.35 * a + 0.3 * flash, blur=size * 0.1,
                                                                      blend=ADD))
                c.drawTextBlob(b, -widths[i] / 2, size * 0.36, fill(WHITE, a))
                c.restore()
                if t - ti < 0.35:
                    shockwave(c, t, ti, x + widths[i] / 2, cy, 200, CYAN, dur=0.35, width=3)
            x += widths[i] + tracking
        us = span(t, t_studio - 0.1, t_studio + 0.25)
        if us > 0:
            ss = lerp(60, 40, move)
            fs = self.font("montsemi", ss)
            word = "STUDIO"
            tr = lerp(ss * 1.6, ss * 0.7, ease_out(us))
            ws = [fs.measureText(ch) for ch in word]
            tot = sum(ws) + tr * 5
            xs = CX - tot / 2
            ys = cy + size * 0.6 + ss * 0.6
            for i, ch in enumerate(word):
                c.drawTextBlob(self.blob("montsemi", ss, ch), xs, ys, fill(WHITE, ease_out(us) * (1 - out)))
                xs += ws[i] + tr
            c.drawRect(skia.Rect(CX - tot / 2, ys + ss * 0.4, CX - tot / 2 + tot * ease_out(us), ys + ss * 0.4 + 2),
                       fill(CYAN, 0.9 * (1 - out)))
        uq = span(t, t_queen - 0.06, t_queen + 0.2)
        if uq > 0:
            sc = lerp(1.6, 1.0, ease_out(uq))
            a = min(1, uq * 2) * (1 - out)
            c.save()
            c.translate(CX, 640)
            c.scale(sc, sc)
            cr = crown(0, -205, 170)
            c.drawPath(cr, stroke(GOLD, 5, a))
            for k in range(3):
                c.drawCircle((k - 1) * 46, -212, 8, fill((RED, WHITE, GREEN)[k], a))
            f = self.font("mont", 210)
            word = "QUEEN"
            w_ = f.measureText(word)
            b = skia.TextBlob.MakeFromString(word, f)
            c.drawTextBlob(b, -w_ / 2, 76, fill(GOLD, 0.45 * a, blur=26, blend=ADD))
            shader = skia.GradientShader.MakeLinear([skia.Point(0, -80), skia.Point(0, 80)],
                                                    [col((1.0, 0.95, 0.75), a).toColor(), col(GOLD, a).toColor(),
                                                     col((0.95, 0.6, 0.15), a).toColor()], [0.0, 0.5, 1.0])
            c.drawTextBlob(b, -w_ / 2, 76, skia.Paint(AntiAlias=True, Shader=shader))
            gx = ((t - t_queen) * 1400) % 2400 - 900
            shader = skia.GradientShader.MakeLinear([skia.Point(gx - 100, -150), skia.Point(gx + 100, 150)],
                                                    [col(WHITE, 0).toColor(), col(WHITE, 0.8 * a).toColor(),
                                                     col(WHITE, 0).toColor()])
            pg = skia.Paint(AntiAlias=True, Shader=shader)
            pg.setBlendMode(skia.BlendMode.kSrcATop)
            c.drawTextBlob(b, -w_ / 2, 76, pg)
            ul = span(t, 19.11 - 0.06, 19.11 + 0.25)
            if ul > 0:
                f2 = self.font("montsemi", 52)
                word2 = "L  i  S  A"
                w2 = f2.measureText(word2)
                c.drawTextBlob(skia.TextBlob.MakeFromString(word2, f2), -w2 / 2, 180 - 20 * (1 - ul), fill(WHITE, ul * a))
            c.restore()
        c.restore()

    # ------------------------------------------------------------ patlamalar ve geçişler

    def draw_hits(self, c, t):
        for i, (th, pw, kind) in enumerate(HITS):
            dt = t - th
            if dt < 0 or dt > 1.6:
                continue
            if kind in ("start", "drop", "chorus", "tonight", "final"):
                pal = {"start": (RED, GREEN), "drop": (VIOLET, CYAN), "chorus": (GOLD, PINK, CYAN),
                       "tonight": (PINK, VIOLET, GOLD), "final": (GOLD, CYAN, PINK)}[kind]
                flare_burst(c, t, th, CX, 520, 190 if pw >= 4 else 120, pal, seed=i * 7 + 3, power=pw)
            elif kind in ("red", "green"):
                x = CX - 420 if kind == "red" else CX + 420
                flare_burst(c, t, th, x, 430, 150, (RED, ORANGE) if kind == "red" else (GREEN, CYAN), seed=i * 7)
            elif kind == "chase":
                y = 300 if th < 28.6 else 462
                flare_burst(c, t, th, CX, y, 90, (CYAN, PINK), seed=i * 7, power=2)
            elif kind == "seal":
                for k in range(2):
                    shockwave(c, t, th + 0.05 * k, CX, 366, 420 + 160 * k, RED, dur=0.5, width=5 - 2 * k)
                flare_burst(c, t, th, CX, 366, 70, (RED, PINK), seed=i, power=2)
            elif kind == "correct":
                flare_burst(c, t, th, CX, 400, 110, (RED, GOLD, CYAN), seed=i, power=3)
            elif pw >= 2 and kind in ("bass", "bar", "whip", "clouds", "moon"):
                shockwave(c, t, th, CX, 520, 1100, WHITE, dur=0.45, width=3, a=0.4)

    def flash(self, t):
        best = 0.0
        for th, pw, kind in HITS:
            if th <= t < th + 0.6:
                if kind in ("drop", "chorus", "tonight"):
                    a = decay(t, th, 0.15)
                elif kind == "final":
                    a = 1.0 if t < th + 0.08 else decay(t, th + 0.08, 0.12)
                elif kind == "start":
                    a = 0.8 * decay(t, th, 0.1)
                elif kind == "bolt":
                    a = (0.2 + 0.1 * pw) * decay(t, th, 0.06)
                elif pw >= 3:
                    a = 0.3 * decay(t, th, 0.08)
                else:
                    a = 0.0
                best = max(best, a)
        return best

    def draw_wipes(self, c, t):
        for tw, kind, rgb in WIPES:
            dt = t - tw
            if not -0.16 <= dt <= 0.16:
                continue
            u = (dt + 0.16) / 0.32
            if kind in ("slash", "slash_r"):
                d = 1 if kind == "slash" else -1
                lead = lerp(-1400, W + 1400, ease_in_out(u))
                x_a, x_b = lead - 1300, lead + 1300
                if d < 0:
                    x_a, x_b = W - x_b, W - x_a
                sk = 380
                c.drawPath(poly([(x_a + sk, -50), (x_b + sk, -50), (x_b - sk, H + 50), (x_a - sk, H + 50)]), fill(INK))
                for edge in (x_a, x_b):
                    c.drawLine(edge + sk, -50, edge - sk, H + 50, stroke(rgb, 6))
                    c.drawLine(edge + sk, -50, edge - sk, H + 50, stroke(rgb, 30, 0.25, blur=12))
            elif kind == "shutter":
                n = 6
                for k in range(n):
                    v = clamp01(1 - abs(u - 0.5) * 2 * 1.15)
                    hw = W / n / 2 * ease_out(v)
                    xk = (k + 0.5) * W / n
                    c.drawRect(skia.Rect(xk - hw - 1, -10, xk + hw + 1, H + 10), fill(INK))
                    if hw > 2:
                        c.drawRect(skia.Rect(xk - hw - 1, -10, xk - hw + 2, H + 10), fill(rgb))
            elif kind == "blinds":
                n = 8
                for k in range(n):
                    v = clamp01(1 - abs(u - 0.5) * 2 * 1.15)
                    hh = H / n / 2 * ease_out(v)
                    yk = (k + 0.5) * H / n
                    c.drawRect(skia.Rect(-10, yk - hh - 1, W + 10, yk + hh + 1), fill(INK))
                    if hh > 2:
                        c.drawRect(skia.Rect(-10, yk - hh - 1, W + 10, yk - hh + 2), fill(rgb))

    def draw_end(self, c, t):
        if t < FINAL_HIT + 0.1:
            return
        u = span(t, FINAL_HIT + 0.15, FINAL_HIT + 0.4)
        v = 1 - span(t, DURATION - 0.35, DURATION - 0.05)
        a = u * v
        f = self.font("mont", 80)
        word = "ANDROE STUDIO"
        w_ = f.measureText(word)
        c.drawTextBlob(skia.TextBlob.MakeFromString(word, f), CX - w_ / 2, CY + 28, fill(WHITE, a))
        c.drawRect(skia.Rect(CX - w_ / 2 * u, CY + 66, CX + w_ / 2 * u, CY + 69), fill(CYAN, a))

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
        c.drawRect(skia.Rect(rect.left(), rect.top() + 14, rect.left() + 4, rect.bottom() - 14),
                   fill(mix(RED, GREEN, 0.5 + 0.5 * math.sin(t * 2)), a))
        c.drawPath(note(x1 - w1 - 24, H - 78, 34), fill(GOLD, a))
        c.drawString(CREDIT_TITLE, x1 - w1, H - 78, f1, fill(WHITE, a))
        c.drawString(CREDIT_NOTE, x1 - w2, H - 50, f2, fill((0.85, 0.85, 0.9), a))

    # ------------------------------------------------------------ dansçılar

    def dancer_image(self, t):
        if self.bake is None or t > FINAL_HIT + 0.22:
            return None
        from queen_dancers import JOINT_NAMES
        n = len(self.bake[0]["face"])
        f = min(max(int(round(t * 60)), 0), n - 1)
        vis = [bool(dd["vis"][f]) for dd in self.bake]
        if not any(vis):
            return None
        rim = self.accent(t)
        self.toon.begin(self.view, self.proj, CAM_EYE, rim_col=rim, rim_k=0.75)
        poses = []
        for dd, v in zip(self.bake, vis):
            if not v:
                poses.append(None)
                continue
            Rw = {nm: dd["R"][f, k] for k, nm in enumerate(JOINT_NAMES)}
            Pw = {nm: dd["P"][f, k] for k, nm in enumerate(JOINT_NAMES)}
            poses.append((Rw, Pw))
            height = max(0.0, float(Pw["root"][1]))
            self.toon.shadow((Pw["root"][0], 0.0, Pw["root"][2]), radius=(0.34, 0.2),
                             strength=0.4 / (1 + 3 * height))
        for i, (d, dd, ps) in enumerate(zip(self.dancers, self.bake, poses)):
            if ps is None:
                continue
            Rw, Pw = ps
            self.toon.draw_dancer(d, Rw, Pw, int(dd["face"][f]), [ch[f] for ch in dd["chains"]], dd["skirt"][f],
                                  key=d.name)
        img = self.toon.finish()
        return skia.Image.fromarray(img, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)

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
        img = self.dancer_image(t)
        if img is not None:
            c.drawImageRect(img, skia.Rect(0, 0, W, H), skia.SamplingOptions(skia.FilterMode.kLinear))
        self.draw_lines(c, t)
        c.restore()
        self.draw_wipes(c, t)
        a = self.flash(t)
        if a > 0.003:
            c.drawPaint(fill(WHITE, a))
        if t >= FINAL_HIT + 0.08:
            c.drawPaint(fill(INK, span(t, FINAL_HIT + 0.08, FINAL_HIT + 0.3)))
        self.draw_end(c, t)
        shader = skia.GradientShader.MakeRadial(skia.Point(CX, CY), 1150,
                                                [col(INK, 0).toColor(), col(INK, 0).toColor(), col(INK, 0.5).toColor()],
                                                [0.0, 0.62, 1.0])
        c.drawPaint(skia.Paint(Shader=shader))
        c.restore()

    def post(self, rgb, t):
        """Kromatik sapma ve dev vuruşlarda iki karelik ters renk."""
        ca = 0.0
        for th, pw, kind in HITS:
            if pw >= 2 and th <= t < th + 0.5:
                ca += (0, 0, 4, 7, 12)[pw] * decay(t, th, 0.1)
        ca += self.tremolo(t) * 0.3
        d = int(round(ca * self.k))
        if d >= 1:
            out = rgb.copy()
            out[:, d:, 0] = rgb[:, :-d, 0]
            out[:, :-d, 2] = rgb[:, d:, 2]
            rgb = out
        for th, pw, kind in HITS:
            if pw >= 4 and kind != "final" and th <= t < th + 2.0 / self.fps:
                rgb = 255 - rgb
        return rgb

    def credit_overlay(self, rgb, t):
        """Sağ alttaki yazı en son, flaş ve renk efektlerinin üstüne ayrı katman olarak eklenir."""
        if span(t, 0.5, 0.9) <= 0:
            return rgb
        cw, ch = int(round(760 * self.k)), int(round(140 * self.k))
        if not hasattr(self, "credit_surf"):
            self.credit_surf = skia.Surface(cw, ch)
        with self.credit_surf as c:
            c.clear(skia.Color4f(0, 0, 0, 0))
            c.save()
            c.scale(self.k, self.k)
            c.translate(-(W - 760), -(H - 140))
            self.draw_credit(c, t)
            c.restore()
        ov = self.credit_surf.toarray(colorType=skia.kRGBA_8888_ColorType,
                                      alphaType=skia.kPremul_AlphaType).astype(np.float32)
        out = np.array(rgb, copy=True)
        region = out[-ch:, -cw:].astype(np.float32)
        out[-ch:, -cw:] = (ov[..., :3] + region * (1 - ov[..., 3:] / 255.0) + 0.5).astype(np.uint8)
        return out

    def render(self, t):
        with self.surface as c:
            self.draw(c, t)
        rgb = self.surface.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]
        return np.ascontiguousarray(self.credit_overlay(self.post(rgb, t), t))
