"""Androe Studio logo konseptleri: sembol, yazılı logo ve birleşik lockup SVG'leri üretir."""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

FONTS = Path(__file__).resolve().parent.parent / "fonts"
OUT = Path(__file__).resolve().parent / "konseptler"
BLACK = TTFont(FONTS / "Montserrat-Black.ttf")
SEMI = TTFont(FONTS / "Montserrat-SemiBold.ttf")


def text_path(font, text, cap_h, x, y, track=0.0):
    """Metni path'e çevirir. y = taban çizgisi, cap_h = büyük harf yüksekliği (px). Dönüş: (d, genişlik)."""
    upm_cap = font["OS/2"].sCapHeight
    s = cap_h / upm_cap
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    pen = SVGPathPen(gs)
    cx = 0.0
    names = [cmap[ord(ch)] for ch in text]
    for i, n in enumerate(names):
        tp = TransformPen(pen, (s, 0, 0, -s, x + cx, y))
        gs[n].draw(tp)
        cx += gs[n].width * s
        if i < len(names) - 1:
            cx += track
    # gerçek mürekkep genişliği
    bp = BoundsPen(gs)
    first = gs[names[0]]
    fb = BoundsPen(gs); first.draw(fb)
    last = gs[names[-1]]
    lb = BoundsPen(gs); last.draw(lb)
    lsb = fb.bounds[0] * s
    rsb = (last.width - lb.bounds[2]) * s
    return pen.getCommands(), cx, lsb, rsb


def fit_text(font, text, cap_h, x, y, track=0.0):
    """Mürekkebi tam x'ten başlatır; (d, mürekkep genişliği) döndürür."""
    _, w, lsb, rsb = text_path(font, text, cap_h, 0, 0, track)
    d, _, _, _ = text_path(font, text, cap_h, x - lsb, y, track)
    return d, w - lsb - rsb


def track_to_width(font, text, cap_h, width):
    _, w0, lsb, rsb = text_path(font, text, cap_h, 0, 0, 0)
    ink = w0 - lsb - rsb
    return (width - ink) / (len(text) - 1)


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}">'
            f'<title>{title}</title>{body}</svg>\n')


def rrect(x, y, w, h, r):
    return (f"M{x+r:g} {y:g}H{x+w-r:g}A{r:g} {r:g} 0 0 1 {x+w:g} {y+r:g}V{y+h-r:g}"
            f"A{r:g} {r:g} 0 0 1 {x+w-r:g} {y+h:g}H{x+r:g}A{r:g} {r:g} 0 0 1 {x:g} {y+h-r:g}"
            f"V{y+r:g}A{r:g} {r:g} 0 0 1 {x+r:g} {y:g}Z")


def save(name, w, h, body, title):
    (OUT / name).write_text(svg(w, h, body, title))


def wordmark_block(x, top, width, ink="#000", gap=None):
    """ANDROE (Black) üstte, STUDIO (SemiBold) altta aynı genişlikte. Dönüş: (body, yükseklik)."""
    # ANDROE'yi genişliğe sığdıracak cap yüksekliği
    _, w1, l1, r1 = text_path(BLACK, "ANDROE", 100, 0, 0, 0)
    cap1 = 100 * width / (w1 - l1 - r1)
    d1, _ = fit_text(BLACK, "ANDROE", cap1, x, top + cap1)
    cap2 = cap1 * 0.40
    g = gap if gap is not None else cap1 * 0.26
    tr = track_to_width(SEMI, "STUDIO", cap2, width)
    d2, _ = fit_text(SEMI, "STUDIO", cap2, x, top + cap1 + g + cap2, tr)
    return f'<path fill="{ink}" d="{d1}"/><path fill="{ink}" d="{d2}"/>', cap1 + g + cap2


def write_set(key, title, symbol_body, sym_w=256):
    save(f"{key}-sembol.svg", sym_w, 256, symbol_body, f"{title} sembol")
    # yazılı logo
    wm, h = wordmark_block(0, 0, 600)
    save(f"{key}-yazi.svg", 600, round(h, 2), wm, f"{title} yazılı logo")
    # yatay lockup: sembol + yazı bloğu, yazı bloğu sembolün %62'si yüksekliğinde ortalı
    target_h = 256 * 0.62
    # yükseklik genişlikle orantılı: h/600
    width = target_h / (h / 600)
    gap = 256 * 0.22
    top = (256 - target_h) / 2
    wm2, _ = wordmark_block(sym_w + gap, top, width)
    save(f"{key}-lockup.svg", round(sym_w + gap + width, 2), 256, symbol_body + wm2, f"{title} lockup")


# --- A: Yerleşen Blok — pikselden A, tepe bloğu yerine oturmak üzere havada
def concept_a():
    cell, gap = 38, 6
    pitch = cell + gap
    x0 = (256 - (5 * cell + 4 * gap)) / 2
    y0 = 256 - 18 - (5 * cell + 4 * gap)
    rows = [".XXX.", "X...X", "XXXXX", "X...X", "X...X"]
    d = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch != "X":
                continue
            x, y = x0 + c * pitch, y0 + r * pitch
            if r == 0 and c == 2:
                y -= 26  # havadaki blok
            d.append(rrect(x, y, cell, cell, 7))
    return f'<path d="{"".join(d)}"/>'


# --- B: Zirve — kalın bir Λ ve altındaki kare oyuncu bloğu (A'nın çizgisi = blok)
def concept_b():
    top_y, base_y = 26, 228
    half_top = 14
    out_r = 238
    leg = 58  # tabandaki yatay bacak kalınlığı
    slope = (out_r - (128 + half_top)) / (base_y - top_y)
    in_r = out_r - leg
    apex_y = base_y - (in_r - 128) / slope
    outer = (f"M{128-half_top:g} {top_y}H{128+half_top:g}L{out_r} {base_y}H{in_r}"
             f"L128 {apex_y:.2f}L{256-in_r} {base_y}H{256-out_r}Z")
    s = 40
    sq_bottom = base_y
    sq = rrect(128 - s / 2, sq_bottom - s, s, s, 5)
    return f'<path d="{outer}{sq}"/>'


# --- C: Kartuş — köşesi kesik oyun kartuşu rozeti, içinde negatif A
def cartridge(x, y, w, h, r, cut):
    return (f"M{x+r:g} {y:g}H{x+w-cut:g}L{x+w:g} {y+cut:g}V{y+h-r:g}"
            f"A{r:g} {r:g} 0 0 1 {x+w-r:g} {y+h:g}H{x+r:g}A{r:g} {r:g} 0 0 1 {x:g} {y+h-r:g}"
            f"V{y+r:g}A{r:g} {r:g} 0 0 1 {x+r:g} {y:g}Z")


def concept_c_symbol():
    body = cartridge(20, 20, 216, 216, 26, 52)
    # kartuş tırtıkları (üstte 3 çentik) - negatif
    notches = "".join(rrect(52 + i * 30, 36, 18, 10, 3) for i in range(3))
    dA, wA = fit_text(BLACK, "A", 112, 0, 0)
    # ortala
    _, adv, lsb, rsb = text_path(BLACK, "A", 112, 0, 0)
    ink = adv - lsb - rsb
    dA, _ = fit_text(BLACK, "A", 112, 128 - ink / 2, 128 + 112 / 2 + 14)
    return f'<path fill-rule="evenodd" d="{body}{notches}{dA}"/>'


def concept_c_full():
    """BK tarzı: yazı rozetin içinde (amblem)."""
    W, H = 640, 300
    body = cartridge(0, 0, W, H, 34, 70)
    notches = "".join(rrect(40 + i * 40, 22, 24, 12, 4) for i in range(4))
    inner_w = W - 120
    # yazı bloğunu negatif olarak ekle
    _, w1, l1, r1 = text_path(BLACK, "ANDROE", 100, 0, 0)
    cap1 = 100 * inner_w / (w1 - l1 - r1)
    cap2 = cap1 * 0.40
    g = cap1 * 0.26
    th = cap1 + g + cap2
    top = (H - th) / 2 + 10
    d1, _ = fit_text(BLACK, "ANDROE", cap1, 60, top + cap1)
    tr = track_to_width(SEMI, "STUDIO", cap2, inner_w)
    d2, _ = fit_text(SEMI, "STUDIO", cap2, 60, top + cap1 + g + cap2, tr)
    return W, H, f'<path fill-rule="evenodd" d="{body}{notches}{d1}{d2}"/>'


if __name__ == "__main__":
    if len(sys.argv) > 1:
        OUT = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    write_set("a-blok", "Androe Studio A - Yerleşen Blok", concept_a())
    write_set("b-zirve", "Androe Studio B - Zirve", concept_b())
    sym_c = concept_c_symbol()
    save("c-kartus-sembol.svg", 256, 256, sym_c, "Androe Studio C - Kartuş sembol")
    W, H, emb = concept_c_full()
    save("c-kartus-lockup.svg", W, H, emb, "Androe Studio C - Kartuş amblem")
    wm, h = wordmark_block(0, 0, 600)
    save("c-kartus-yazi.svg", 600, round(h, 2), wm, "Androe Studio C - yazılı logo")
    print("ok")
