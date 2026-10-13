"""Androe Studio - yeni işaretle (logo/final/isaret.svg) "göz açılıyor" intro animasyonu.

Akış (saniye):
  0.25-0.78  karanlıkta ortada ince bir ışık çizgisi uzar          (yükselen gerilim)
  0.78-1.40  işaret o çizgiden göz açılır gibi dikey açılır        (derin vuruş + çan)
  0.95-1.75  işaretten dışa doğru ince bir ışık halkası yayılır
  1.60-2.20  işaretin üzerinden çapraz bir parlama geçer           (ışıltı)
  2.30-3.05  işaret küçülüp sola kayar, ANDROE STUDIO arkasından çıkar (whoosh + notalar)
  3.05-4.90  logo durur, hafifçe nefes alır                        (akor)
  4.90-5.60  yumuşakça kararır

Kullanım:
    python isaret_intro.py                       # output/androe_isaret_intro.mp4
    python isaret_intro.py --still 3.5           # tek kareyi PNG kaydet
    python isaret_intro.py --width 3840 --height 2160 -o output/androe_isaret_intro_4k.mp4
"""
import argparse
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import skia

sys.path.insert(0, str(Path(__file__).resolve().parent / "logo"))
from logo_uret import BLACK, SEMI, text_path, track_to_width  # noqa: E402
from intro import encode, save_png  # noqa: E402
import sound  # noqa: E402

ROOT = Path(__file__).resolve().parent
MARK_SVG = ROOT / "logo" / "final" / "isaret.svg"

BG = (0x0E, 0x0B, 0x1A)
MOR = (0x5D, 0x1E, 0xCA)
LAVANTA = (0xC9, 0xB4, 0xFF)
BEYAZ = (0xFF, 0xFF, 0xFF)

T_LINE = (0.25, 0.78)
T_OPEN = (0.78, 1.40)
T_RING = (0.95, 1.75)
T_SHEEN = (1.60, 2.20)
T_SLIDE = (2.30, 3.05)
T_LETTER = 0.045          # harfler arası gecikme
T_OUT = (4.90, 5.60)
DURATION = 5.60

MARK_BIG = 380.0          # açılıştaki işaret yüksekliği (1080p'de px)
MARK_SMALL = 270.0        # yazıyla birlikteki yükseklik


# ---------------------------------------------------------------- yardımcılar

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, span):
    return clamp((t - span[0]) / (span[1] - span[0]))


def ease_out_cubic(u):
    return 1 - (1 - u) ** 3


def ease_in_out(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_out_back(u, s=1.9):
    u -= 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def mix(a, b, u):
    return tuple(int(round(x + (y - x) * u)) for x, y in zip(a, b))


def color(rgb, alpha=1.0):
    return skia.Color(*rgb, int(round(255 * clamp(alpha))))


def svg_path(d):
    """Mutlak M/L/H/V/C/Q/Z komutlarından skia.Path kurar (işaret ve fontTools çıktısı için yeterli)."""
    p = skia.Path()
    p.setFillType(skia.PathFillType.kEvenOdd)
    toks = re.findall(r"[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    i, cmd, cur = 0, None, (0.0, 0.0)
    num = lambda: float(toks[i])
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd == "Z":
                p.close()
            continue
        if cmd in "ML":
            x, y = float(toks[i]), float(toks[i + 1]); i += 2
            (p.moveTo if cmd == "M" else p.lineTo)(x, y)
            cur = (x, y)
            if cmd == "M":
                cmd = "L"
        elif cmd == "H":
            x = num(); i += 1
            p.lineTo(x, cur[1]); cur = (x, cur[1])
        elif cmd == "V":
            y = num(); i += 1
            p.lineTo(cur[0], y); cur = (cur[0], y)
        elif cmd == "C":
            v = [float(t) for t in toks[i:i + 6]]; i += 6
            p.cubicTo(*v); cur = (v[4], v[5])
        elif cmd == "Q":
            v = [float(t) for t in toks[i:i + 4]]; i += 4
            p.quadTo(*v); cur = (v[2], v[3])
    return p


def letters(font, text, cap, x, base, track=0.0):
    """Metni harf harf path'lere böler (mürekkep x'ten başlar). Dönüş: [(path, merkez_x)]."""
    _, _, lsb, _ = text_path(font, text[0], cap, 0, 0)
    out, cx = [], x - lsb
    for ch in text:
        d, adv, l, r = text_path(font, ch, cap, cx, base)
        out.append((svg_path(d), cx + (l + adv - r) / 2))
        cx += adv + track
    return out


# ---------------------------------------------------------------- sahne

class Scene:
    def __init__(self, width=1920, height=1080, fps=60):
        self.width, self.height, self.fps = width, height, fps
        self.duration = DURATION
        self.k = height / 1080
        d = re.search(r' d="([^"]+)"', MARK_SVG.read_text()).group(1)
        mark = svg_path(d)
        b = mark.computeTightBounds()
        # işaret: merkezi (0,0), yüksekliği 1 olacak şekilde normalize
        m = skia.Matrix()
        s = 1 / b.height()
        m.setScaleTranslate(s, s, -b.centerX() * s, -b.centerY() * s)
        self.mark = skia.Path(mark)
        self.mark.transform(m)
        self.aspect = b.width() / b.height()
        self._layout()

    def _layout(self):
        k, W, H = self.k, self.width, self.height
        h = MARK_SMALL * k
        mw = h * self.aspect
        gap = h * 0.30
        ww = h * 1.75
        total = mw + gap + ww
        left = (W - total) / 2
        self.end_mark_cx = left + mw / 2
        self.cy = H / 2
        # yazı: ANDROE + STUDIO, işaretin dikey ortasına hizalı
        _, w1, l1, r1 = text_path(BLACK, "ANDROE", 100, 0, 0)
        cap1 = 100 * ww / (w1 - l1 - r1)
        cap2 = cap1 * 0.44
        g = cap1 * 0.26
        th = cap1 + g + cap2
        top = self.cy - th / 2
        x0 = left + mw + gap
        tr = track_to_width(SEMI, "STUDIO", cap2, ww)
        self.word_x0 = x0
        self.word_top, self.word_h = top, th
        self.word = ([(p, c, 0) for p, c in letters(BLACK, "ANDROE", cap1, x0, top + cap1)]
                     + [(p, c, 1) for p, c in letters(SEMI, "STUDIO", cap2, x0, top + th, tr)])

    # -- çizim parçaları
    def _mark_at(self, cx, cy, h, sy=1.0):
        p = skia.Path(self.mark)
        m = skia.Matrix()
        m.setScaleTranslate(h, h * sy, cx, cy)
        p.transform(m)
        return p

    def _glow(self, canvas, path, rgb, alpha, sigma):
        paint = skia.Paint(AntiAlias=True, Color=color(rgb, alpha),
                           MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
        canvas.drawPath(path, paint)

    def _background(self, canvas, t, glow):
        W, H, k = self.width, self.height, self.k
        canvas.clear(color(BG))
        if glow <= 0:
            return
        cx = self.mark_cx(t)
        shader = skia.GradientShader.MakeRadial(
            (cx, self.cy), 620 * k,
            [color(MOR, 0.30 * glow), color(MOR, 0.08 * glow), color(MOR, 0)], [0, 0.45, 1])
        canvas.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=shader))

    # -- zamanla değişen değerler
    def mark_cx(self, t):
        u = ease_in_out(prog(t, T_SLIDE))
        return self.width / 2 + (self.end_mark_cx - self.width / 2) * u

    def mark_h(self, t):
        u = ease_in_out(prog(t, T_SLIDE))
        breathe = 1 + 0.006 * np.sin(2 * np.pi * max(0, t - T_SLIDE[1]) / 1.6)
        return (MARK_BIG + (MARK_SMALL - MARK_BIG) * u) * self.k * breathe

    def render(self, t):
        W, H, k = self.width, self.height, self.k
        surface = skia.Surface(W, H)
        canvas = surface.getCanvas()

        u_line = prog(t, T_LINE)
        u_open = prog(t, T_OPEN)
        opened = u_open > 0
        glow = ease_out_cubic(u_open) * (0.85 + 0.15 * np.sin(2 * np.pi * max(0, t - 3) / 1.6))
        self._background(canvas, t, glow)

        cx, cy, h = self.mark_cx(t), self.cy, self.mark_h(t)
        mw = h * self.aspect

        # 1) ışık çizgisi
        if u_line > 0 and u_open < 0.35:
            fade = 1 - clamp(u_open / 0.35)
            half = mw / 2 * ease_out_cubic(u_line) * (1 + 0.04 * u_open)
            thick = (2 + 2 * u_line) * k
            line = skia.Path()
            line.addRRect(skia.RRect.MakeRectXY(skia.Rect(cx - half, cy - thick / 2, cx + half, cy + thick / 2),
                                                thick / 2, thick / 2))
            self._glow(canvas, line, MOR, 0.9 * fade, 14 * k)
            self._glow(canvas, line, LAVANTA, 0.8 * fade, 4 * k)
            canvas.drawPath(line, skia.Paint(AntiAlias=True, Color=color(BEYAZ, fade)))

        # 2) işaret açılır
        if opened:
            sy = max(0.002, ease_out_back(u_open))
            path = self._mark_at(cx, cy, h, sy)
            flash = 1 - clamp((t - T_OPEN[0]) / 0.55)            # açılışta beyazdan mora
            fill = mix(MOR, LAVANTA, 0.12 + 0.88 * flash ** 1.5)
            self._glow(canvas, path, MOR, 0.75 * glow, 30 * k)
            self._glow(canvas, path, LAVANTA, 0.6 * flash, 10 * k)
            canvas.drawPath(path, skia.Paint(AntiAlias=True, Color=color(fill)))

            # 3) parlama: işaretin içine kırpılmış çapraz ışık bandı
            us = prog(t, T_SHEEN)
            if 0 < us < 1:
                canvas.save()
                canvas.clipPath(path, doAntiAlias=True)
                x = cx - mw * 0.9 + mw * 1.8 * ease_in_out(us)
                band = skia.Path()
                bw = mw * 0.16
                band.addPoly([(x - bw, cy + h), (x, cy + h), (x + h * 0.6, cy - h), (x + h * 0.6 - bw, cy - h)], True)
                self._glow(canvas, band, BEYAZ, 0.55 * np.sin(np.pi * us), 10 * k)
                canvas.restore()

        # 4) halka dalgası
        ur = prog(t, T_RING)
        if 0 < ur < 1:
            e = ease_out_cubic(ur)
            rx, ry = mw / 2 * (1.05 + 0.9 * e), h / 2 * (1.05 + 0.9 * e)
            ring = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                              StrokeWidth=(4 - 2.5 * e) * k, Color=color(LAVANTA, 0.95 * (1 - ur) ** 1.3))
            canvas.drawOval(skia.Rect(cx - rx, cy - ry, cx + rx, cy + ry), ring)

        # 5) yazı: işaretin arkasından çıkar (işaretin sağ kenarından açılan kırpma + harf harf yükselme)
        if t >= T_SLIDE[0]:
            edge = cx + mw / 2 + 4 * k
            canvas.save()
            canvas.clipRect(skia.Rect(edge, 0, W, H))
            for i, (p, lc, line) in enumerate(self.word):
                t0 = T_SLIDE[0] + 0.25 + i * T_LETTER + (0.1 if line else 0)
                ul = ease_out_cubic(clamp((t - t0) / 0.5))
                if ul <= 0:
                    continue
                q = skia.Path(p)
                q.offset(-(1 - ul) * 60 * k, 0)
                canvas.drawPath(q, skia.Paint(AntiAlias=True, Color=color(BEYAZ, ul)))
            canvas.restore()

        # 6) kararma
        fade_out = prog(t, T_OUT)
        if fade_out > 0:
            canvas.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color=skia.Color(0, 0, 0, int(255 * ease_in_out(fade_out)))))

        img = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
        return np.ascontiguousarray(img[..., :3])

    # -- ses
    def letter_events(self):
        ev = []
        for i, (p, lc, line) in enumerate(self.word[:6]):            # ANDROE'ye nota
            ev.append((T_SLIDE[0] + 0.25 + i * T_LETTER * 1.6, i, lc / self.width))
        return ev


def synthesize(scene, seed=7):
    rng = np.random.default_rng(seed)
    mx = sound.Mixer(scene.duration)
    sound.charge(mx, T_LINE[0], T_OPEN[0] - 0.005, rng)
    sound.impact(mx, T_OPEN[0], rng)
    sound.glint(mx, T_SHEEN[0] + 0.15)
    sound.swoosh(mx, T_SLIDE[0], T_SLIDE[1], 0.5, scene.end_mark_cx / scene.width, rng, gain=0.22)
    sound.letter_notes(mx, scene.letter_events())
    sound.resolve(mx, T_SLIDE[1], rng)
    sound.pad(mx, T_SLIDE[1] - 0.03, T_OUT[0] + 0.05, scene.duration, rng)

    out = mx.dry + 0.4 * sound.convolve(mx.send, sound.reverb_ir(rng))
    t = np.arange(len(out)) / sound.SR
    fade = np.clip(t / 0.003, 0, 1)
    fade *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - T_OUT[0]) / (scene.duration - T_OUT[0]), 0, 1))
    out *= fade[:, None]
    out = np.tanh(1.3 * out / np.abs(out).max()) / np.tanh(1.3)
    return (out * 10 ** (-1 / 20)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description="Androe Studio yeni işaret intro videosu.")
    ap.add_argument("-o", "--output", default="output/androe_isaret_intro.mp4")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--still", type=float, metavar="SANIYE")
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene = Scene(args.width, args.height, args.fps)
    if args.still is not None:
        path = out.with_name(f"isaret_kare_{args.still:.2f}.png")
        save_png(scene.render(args.still), path)
        print(f"Kaydedildi: {path}")
        return
    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "ses.wav"
        sound.write_wav(wav, synthesize(scene))
        encode(scene, wav, out, args.fps)
    print(f"Hazır: {out}  ({time.time() - start:.0f} sn)")


if __name__ == "__main__":
    main()
