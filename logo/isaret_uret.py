"""Androe Studio özgün işaretler (3. tur): fonttan bağımsız, geometriyle kurulmuş semboller.

Her işaret için: sembol (siyah), uygulama ikonu (koyu kare üstünde beyaz) ve yatay lockup.
Kullanım: python logo/isaret_uret.py  ->  logo/isaretler/
Gerekenler: fonttools, shapely
"""
import math
import sys
from pathlib import Path

from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from shapely import affinity

from logo_uret import BLACK, SEMI, text_path, fit_text, svg

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "isaretler"
RES = 16  # yay çözünürlüğü


# ---------- geometri yardımcıları ----------

def soft(g, r):
    """Dış (dışbükey) köşeleri r ile yuvarlar."""
    return g.buffer(-r, join_style="round", quad_segs=RES).buffer(r, join_style="round", quad_segs=RES)


def soft_in(g, r):
    """İç (içbükey) köşeleri r ile yuvarlar."""
    return g.buffer(r, join_style="round", quad_segs=RES).buffer(-r, join_style="round", quad_segs=RES)


def gap_line(p, q, w):
    return LineString([p, q]).buffer(w / 2, cap_style="flat", join_style="mitre")


def stroke(pts, w, cap="round", join="round"):
    return LineString(pts).buffer(w / 2, cap_style=cap, join_style=join, quad_segs=RES)


def to_d(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    out = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            c = list(ring.coords)[:-1]
            out.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in c) + "Z")
    return "".join(out)


def fit(g, size=216, center=(128, 128)):
    """Geometriyi 256'lık tuvalde en uzun kenarı `size` olacak şekilde ortalar (optik merkez 2px yukarı)."""
    x0, y0, x1, y1 = g.bounds
    s = size / max(x1 - x0, y1 - y0)
    g = affinity.scale(g, s, s, origin=(x0, y0))
    x0, y0, x1, y1 = g.bounds
    return affinity.translate(g, center[0] - (x0 + x1) / 2, center[1] - 2 - (y0 + y1) / 2)


def tri(apex, base_y, half):
    return Polygon([apex, (apex[0] + half, base_y), (apex[0] - half, base_y)])


# ---------- işaretler ----------

def m01_kup_a():
    """İzometrik küp; alttan açılan V ile A'ya dönüşür. Blok = Roblox, küp = inşa."""
    T, UR, LR, B, LL, UL, C = (128, 20), (222, 74), (222, 182), (128, 236), (34, 182), (34, 74), (128, 128)
    cube = Polygon([T, UR, LR, B, LL, UL])
    g = 12
    gaps = unary_union([gap_line(C, UL, g), gap_line(C, UR, g)])
    notch = Polygon([(128, 134), (76, 244), (180, 244)])
    shape = cube.difference(gaps).difference(notch)
    return soft(shape, 6)


def m02_elmas_tepe():
    """Kalın Λ, tepesinde ayrı duran elmas: ödül/hedef. A'nın tepesi bir kazanım."""
    outer = tri((128, 10), 236, 112)
    inner = tri((128, 118), 237, 50)
    lam = outer.difference(inner)
    dia = affinity.rotate(box(128 - 30, 66 - 30, 128 + 30, 66 + 30), 45, origin=(128, 66))
    shape = lam.difference(dia.buffer(12, join_style="mitre")).union(dia)
    return soft(shape, 5)


def m03_oynat_a():
    """Dolu üçgen A; iç boşluğu sağa bakan 'oynat' üçgeni."""
    outer = soft(tri((128, 14), 236, 114), 14)
    legs = Polygon([(128, 190), (96, 240), (160, 240)])
    play = soft(Polygon([(112, 116), (112, 172), (156, 144)]), 4)
    return outer.difference(legs).difference(play)


def m05_katlanmis():
    """Tek bir şerit tepede katlanır: sol bacak önde, sağ bacak arkada (katlama boşluğu)."""
    left = Polygon([(18, 236), (80, 236), (150, 92), (120, 18)])
    right = Polygon([(120, 18), (176, 18), (238, 236), (176, 236)])
    cut = left.buffer(10, join_style="mitre")
    shape = right.difference(cut).union(left)
    cross = box(102, 166, 196, 200).difference(cut)
    return soft(shape.union(cross), 5)


def m07_rutbe():
    """İç içe iki Λ: rütbe/seviye işareti, birlikte A siluetini verir."""
    big = tri((128, 14), 236, 116).difference(tri((128, 86), 237, 78))
    small = tri((128, 128), 236, 60).difference(tri((128, 186), 237, 30))
    return soft(unary_union([big, small]), 5)


def m09_iki_parca():
    """Λ ortadan ikiye ayrılır, sağ yarım yerine oturmak üzere hafif yukarıda."""
    a = tri((128, 20), 236, 110).difference(tri((128, 124), 237, 46))
    left = a.intersection(box(0, 0, 128 - 7, 256))
    right = affinity.translate(a.intersection(box(128 + 7, 0, 256, 256)), 0, -18)
    return soft(unary_union([left, right]), 5)


def m_negatif_blok():
    """Dolu bir blok; içine negatif alanla A oyulmuş (alttan V, üstte kare göz)."""
    block = soft(box(20, 20, 236, 236), 44)
    v = Polygon([(128, 112), (70, 237), (186, 237)])
    eye = soft(box(110, 64, 146, 100), 6)
    return soft_in(block.difference(v), 6).difference(eye)


def m_kule():
    """Üst üste dizilmiş bloklar bir A kurar: tepe, ara çubuk, iki ayak."""
    g = 12
    r = 12
    top = box(96, 20, 160, 72)
    mid = box(62, 72 + g, 194, 136)
    l = box(28, 136 + g, 112, 236)
    rr = box(144, 136 + g, 228, 236)
    return unary_union([soft(p, r) for p in (top, mid, l, rr)])


def m_dugum():
    """Üç blok-düğüm ve aralarındaki bağlar: üçgen bir ağ, A siluetinde. Sistem kuran stüdyo."""
    nodes = [(128, 44), (48, 212), (208, 212)]
    s = 64
    blocks = [soft(box(x - s / 2, y - s / 2, x + s / 2, y + s / 2), 16) for x, y in nodes]
    links = [stroke([nodes[0], nodes[1]], 26, cap="flat"), stroke([nodes[0], nodes[2]], 26, cap="flat"),
             stroke([(84, 150), (172, 150)], 26, cap="flat")]
    return unary_union(blocks + links)


def m_katman():
    """Dolu üçgen, yatay bir boşlukla iki katmana ayrılır; alttan açılan V ile A. Üst üste kurulan katmanlar."""
    t = soft(tri((128, 16), 236, 116), 10)
    band = box(0, 132, 256, 150)
    notch = Polygon([(128, 172), (98, 240), (158, 240)])
    return t.difference(band).difference(notch)


MARKS = [
    ("01-kup-a", "Küp A", m01_kup_a, "İzometrik küp alttan açılınca A olur"),
    ("02-elmas-tepe", "Elmas Tepe", m02_elmas_tepe, "A'nın tepesi ayrı bir elmas: hedef/ödül"),
    ("03-oynat-a", "Oynat A", m03_oynat_a, "A'nın iç boşluğu bir 'oynat' üçgeni"),
    ("04-katlanmis", "Katlanmış Şerit", m05_katlanmis, "Tepede katlanan tek şerit"),
    ("05-rutbe", "Rütbe", m07_rutbe, "İç içe iki chevron: seviye atlamak"),
    ("06-iki-parca", "İki Parça", m09_iki_parca, "İki yarım, yerine oturmak üzere"),
    ("07-negatif-blok", "Negatif Blok", m_negatif_blok, "Dolu bloğa oyulmuş A"),
    ("08-kule", "Blok Kule", m_kule, "Üst üste dizilen dört blok A kurar"),
    ("09-dugum", "Düğüm", m_dugum, "Bloklar ve bağlar: üçgen ağ"),
    ("10-katman", "Katman", m_katman, "İki katmana ayrılmış üçgen A"),
]


def word_d(font, text, x, base, cap):
    d, w = fit_text(font, text, cap, x, base)
    return d, w


def lockup(sym_d, ink="#000"):
    """Sembol + 'Androe Studio' (Androe Black, Studio SemiBold) tek satır."""
    cap = 256 * 0.30
    x = 256 + 256 * 0.20
    base = 128 + cap / 2
    d1, w1 = word_d(BLACK, "Androe", x, base, cap)
    d2, w2 = word_d(SEMI, "Studio", x + w1 + cap * 0.32, base, cap)
    W = x + w1 + cap * 0.32 + w2
    return W, f'<path fill="{ink}" d="{sym_d}"/><path fill="{ink}" d="{d1}{d2}"/>'


def app_icon(sym_d):
    tile = to_d(soft(box(0, 0, 256, 256), 56))
    return (f'<path fill="#111" d="{tile}"/>'
            f'<g transform="translate(128 128) scale(0.6) translate(-128 -128)"><path fill="#fff" d="{sym_d}"/></g>')


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for key, name, fn, _ in MARKS:
        g = fit(fn().buffer(0))
        d = to_d(g)
        (OUT / f"{key}-sembol.svg").write_text(svg(256, 256, f'<path d="{d}"/>', f"Androe Studio - {name}"))
        (OUT / f"{key}-app.svg").write_text(svg(256, 256, app_icon(d), f"Androe Studio - {name} uygulama ikonu"))
        W, body = lockup(d)
        (OUT / f"{key}-lockup.svg").write_text(svg(round(W, 2), 256, body, f"Androe Studio - {name} lockup"))
    print(len(MARKS), "işaret yazıldı ->", OUT)
