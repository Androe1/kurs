"""Androe Studio logo kiti: seçilen işaretten (final/isaret.svg) renkli/tek renk sürümler,
uygulama ikonu, yatay ve dikey lockup'lar üretir.

Kullanım: python logo/kit_uret.py  ->  logo/final/
"""
import re
from pathlib import Path

from logo_uret import BLACK, SEMI, text_path, fit_text, track_to_width, svg, rrect

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "final"

MOR = "#5D1ECA"      # ana marka rengi (taslaktan ölçüldü)
GECE = "#0E0B1A"     # koyu zemin
BEYAZ = "#FFFFFF"

D = re.search(r' d="([^"]+)"', (OUT / "isaret.svg").read_text()).group(1)
# işaretin 256'lık tuvaldeki kutusu (vektorle.py: uzun kenar 232, ortalı; oran 1524x1086)
MW = 232.0
MH = 232.0 * 1086 / 1524
MX, MY = (256 - MW) / 2, (256 - MH) / 2


def mark(x, y, h, fill):
    """İşareti sol üst köşesi (x, y), yüksekliği h olacak şekilde yerleştirir."""
    s = h / MH
    return (f'<g transform="translate({x:.2f} {y:.2f}) scale({s:.4f}) translate({-MX:.2f} {-MY:.2f})">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{D}"/></g>')


def wordmark(x, top, width, fill):
    """ANDROE (Black) + altında aynı genişlikte aralıklı STUDIO (SemiBold). Dönüş: (svg, yükseklik)."""
    _, w1, l1, r1 = text_path(BLACK, "ANDROE", 100, 0, 0)
    cap1 = 100 * width / (w1 - l1 - r1)
    cap2 = cap1 * 0.44
    g = cap1 * 0.26
    d1, _ = fit_text(BLACK, "ANDROE", cap1, x, top + cap1)
    tr = track_to_width(SEMI, "STUDIO", cap2, width)
    d2, _ = fit_text(SEMI, "STUDIO", cap2, x, top + cap1 + g + cap2, tr)
    return f'<path fill="{fill}" d="{d1}{d2}"/>', cap1 + g + cap2


def bg(w, h, color):
    return f'<rect width="{w:g}" height="{h:g}" fill="{color}"/>' if color else ""


def save(name, w, h, body, title):
    (OUT / name).write_text(svg(round(w, 2), round(h, 2), body, f"Androe Studio - {title}"))


def horizontal(ink, word_ink, back=None, pad=0):
    h = 160
    mw = MW * h / MH
    gap = h * 0.28
    ww = h * 1.55
    wm, wh = wordmark(pad + mw + gap, pad + (h - 0) / 2 - 0, ww, word_ink)
    # yazı bloğunu işaretin dikey ortasına hizala
    top = pad + (h - wh) / 2
    wm, _ = wordmark(pad + mw + gap, top, ww, word_ink)
    W, H = pad * 2 + mw + gap + ww, pad * 2 + h
    return W, H, bg(W, H, back) + mark(pad, pad, h, ink) + wm


def stacked(ink, word_ink, back=None, pad=0):
    h = 200
    mw = MW * h / MH
    ww = mw * 0.92
    gap = h * 0.22
    _, wh = wordmark(0, 0, ww, word_ink)
    W, H = pad * 2 + mw, pad * 2 + h + gap + wh
    wm, _ = wordmark(pad + (mw - ww) / 2, pad + h + gap, ww, word_ink)
    return W, H, bg(W, H, back) + mark(pad, pad, h, ink) + wm


def app_icon(tile, ink):
    r = 56
    h = 256 * 0.50
    w = MW * h / MH
    return f'<path fill="{tile}" d="{rrect(0, 0, 256, 256, r)}"/>' + mark((256 - w) / 2, (256 - h) / 2, h, ink)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    full = lambda fill: f'<path fill="{fill}" fill-rule="evenodd" d="{D}"/>'
    save("isaret-mor.svg", 256, 256, full(MOR), "işaret (mor)")
    save("isaret-siyah.svg", 256, 256, full("#000"), "işaret (siyah)")
    save("isaret-beyaz.svg", 256, 256, full(BEYAZ), "işaret (beyaz)")
    save("app-ikonu.svg", 256, 256, app_icon(MOR, BEYAZ), "uygulama ikonu")
    save("app-ikonu-koyu.svg", 256, 256, app_icon(GECE, MOR), "uygulama ikonu (koyu)")
    for name, args, title in [
        ("yatay.svg", (MOR, GECE), "yatay logo"),
        ("yatay-siyah.svg", ("#000", "#000"), "yatay logo (siyah)"),
        ("yatay-koyu.svg", (MOR, BEYAZ, GECE, 48), "yatay logo (koyu zemin)"),
        ("yatay-beyaz.svg", (BEYAZ, BEYAZ, MOR, 48), "yatay logo (mor zemin)"),
    ]:
        W, H, body = horizontal(*args)
        save(name, W, H, body, title)
    for name, args, title in [
        ("dikey.svg", (MOR, GECE), "dikey logo"),
        ("dikey-koyu.svg", (MOR, BEYAZ, GECE, 48), "dikey logo (koyu zemin)"),
    ]:
        W, H, body = stacked(*args)
        save(name, W, H, body, title)
    wm, wh = wordmark(0, 0, 600, GECE)
    save("yazi.svg", 600, wh, wm, "yazılı logo")
    print("kit yazıldı ->", OUT)
