"""Androe Studio amblem varyasyonları (C - Kartuş yönü): her biri için ikon ve yazılı amblem SVG'si üretir.

Kullanım: python logo/amblem_uret.py  ->  logo/amblemler/NN-ad-ikon.svg, NN-ad-amblem.svg
"""
import math
import sys
from pathlib import Path

from logo_uret import BLACK, SEMI, text_path, fit_text, track_to_width, svg, rrect

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "amblemler"


# ---------- yardımcılar ----------

def poly(pts):
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


def circle(cx, cy, r):
    return f"M{cx - r:g} {cy:g}A{r:g} {r:g} 0 1 0 {cx + r:g} {cy:g}A{r:g} {r:g} 0 1 0 {cx - r:g} {cy:g}Z"


def round_poly(pts, r):
    """Köşeleri r yarıçapıyla yuvarlatılmış çokgen (dışbükey köşeler için)."""
    n = len(pts)
    d = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        ang = math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2))))
        t = min(r / math.tan(ang / 2), l1 / 2, l2 / 2)
        a = (p1[0] + v1[0] / l1 * t, p1[1] + v1[1] / l1 * t)
        b = (p1[0] + v2[0] / l2 * t, p1[1] + v2[1] / l2 * t)
        rr = t * math.tan(ang / 2)
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        sweep = 0 if cross > 0 else 1
        d.append(("M" if i == 0 else "L") + f"{a[0]:.2f} {a[1]:.2f}")
        d.append(f"A{rr:.2f} {rr:.2f} 0 0 {sweep} {b[0]:.2f} {b[1]:.2f}")
    return "".join(d) + "Z"


def cartridge(x, y, w, h, r, cut_tr=0, cut_bl=0):
    """Yuvarlak köşeli dikdörtgen; sağ üst ve/veya sol alt köşe 45° kesik."""
    pts = [(x, y), (x + w - cut_tr, y)] if cut_tr else [(x, y), (x + w, y)]
    if cut_tr:
        pts.append((x + w, y + cut_tr))
    pts.append((x + w, y + h))
    if cut_bl:
        pts += [(x + cut_bl, y + h), (x, y + h - cut_bl)]
    else:
        pts.append((x, y + h))
    return round_poly(pts, r)


def letter_a(cx, cy, cap):
    """Ortalanmış Montserrat Black A (optik merkez için hafif yukarı)."""
    _, adv, lsb, rsb = text_path(BLACK, "A", cap, 0, 0)
    d, _ = fit_text(BLACK, "A", cap, cx - (adv - lsb - rsb) / 2, cy + cap / 2)
    return d


def text_block(cx, cy, width, studio=0.40, gap=0.26):
    """ANDROE / STUDIO bloğu, (cx, cy) merkezli, verilen genişlikte. Dönüş: (d, yükseklik)."""
    _, w1, l1, r1 = text_path(BLACK, "ANDROE", 100, 0, 0)
    cap1 = 100 * width / (w1 - l1 - r1)
    cap2 = cap1 * studio
    g = cap1 * gap
    h = cap1 + g + cap2
    x, top = cx - width / 2, cy - h / 2
    d1, _ = fit_text(BLACK, "ANDROE", cap1, x, top + cap1)
    tr = track_to_width(SEMI, "STUDIO", cap2, width)
    d2, _ = fit_text(SEMI, "STUDIO", cap2, x, top + h, tr)
    return d1 + d2, h


def word(font, text, cx, base, cap, track=0.0):
    _, adv, lsb, rsb = text_path(font, text, cap, 0, 0, track)
    d, _ = fit_text(font, text, cap, cx - (adv - lsb - rsb) / 2, base, track)
    return d


def word_fit(font, text, cx, base, width, max_cap=1e9):
    _, adv, lsb, rsb = text_path(font, text, 100, 0, 0)
    cap = min(100 * width / (adv - lsb - rsb), max_cap)
    return word(font, text, cx, base, cap), cap


def corner_stripes(xr, yb, offsets, w):
    """Sağ alt köşede 45° şeritler (beyaz boşluk olarak çizilir)."""
    return "".join(poly([(xr - o - w, yb), (xr - o, yb), (xr, yb - o), (xr, yb - o - w)]) for o in offsets)


def ev(d, fill="#000"):
    return f'<path fill="{fill}" fill-rule="evenodd" d="{d}"/>'


def notches(x, y, n, w, h, step):
    return "".join(rrect(x + i * step, y, w, h, h / 3) for i in range(n))


# ---------- varyasyonlar: her fonksiyon (ikon_body, (W, H, amblem_body)) döndürür ----------

def v01_kartus():
    ikon = cartridge(20, 20, 216, 216, 26, cut_tr=52) + notches(48, 38, 3, 24, 12, 34) + letter_a(128, 140, 112)
    W, H = 640, 300
    t, _ = text_block(W / 2, H / 2 + 12, W - 120)
    am = cartridge(0, 0, W, H, 34, cut_tr=70) + notches(36, 24, 4, 30, 14, 44) + t
    return ev(ikon), (W, H, ev(am))


def v02_etiketli():
    # siyah kartuş, beyaz etiket, etiketin içinde siyah A
    ikon = (cartridge(24, 16, 208, 224, 24, cut_tr=44) + rrect(52, 64, 152, 148, 16)
            + letter_a(128, 138, 96))
    W, H = 660, 320
    t, _ = text_block(W / 2, 186, W - 160)
    am = (cartridge(0, 0, W, H, 34, cut_tr=64) + notches(40, 22, 5, 26, 12, 40)
          + rrect(44, 58, W - 88, H - 102, 22) + t)
    return ev(ikon), (W, H, ev(am))


def v03_cift_kesik():
    ikon = cartridge(20, 20, 216, 216, 22, cut_tr=56, cut_bl=56) + letter_a(128, 128, 116)
    W, H = 640, 280
    t, _ = text_block(W / 2, H / 2, W - 150)
    am = cartridge(0, 0, W, H, 28, cut_tr=72, cut_bl=72) + t
    return ev(ikon), (W, H, ev(am))


def v04_kalkan():
    def shield(x, y, w, h, r):
        cut = w * 0.16
        pts = [(x + cut, y), (x + w - cut, y), (x + w, y + cut), (x + w, y + h * 0.58),
               (x + w / 2, y + h), (x, y + h * 0.58), (x, y + cut)]
        return round_poly(pts, r)
    ikon = shield(30, 14, 196, 230, 18) + letter_a(128, 112, 100)
    W, H = 560, 400
    am = shield(0, 0, W, H, 30)
    t, _ = text_block(W / 2, 140, W - 90)
    return ev(ikon), (W, H, ev(am + t))


def v05_altigen():
    def hexa(cx, cy, w, h, r):
        k = h / 2 * 0.62  # yan uçların içeri girişi
        pts = [(cx - w / 2 + k, cy - h / 2), (cx + w / 2 - k, cy - h / 2), (cx + w / 2, cy),
               (cx + w / 2 - k, cy + h / 2), (cx - w / 2 + k, cy + h / 2), (cx - w / 2, cy)]
        return round_poly(pts, r)
    ikon = hexa(128, 128, 236, 212, 18) + letter_a(128, 128, 108)
    W, H = 700, 260
    t, _ = text_block(W / 2, H / 2, W - 230)
    return ev(ikon), (W, H, ev(hexa(W / 2, H / 2, W, H, 24) + t))


def v06_piksel():
    def stepped(x, y, w, h, s):
        pts = [(x + 2 * s, y), (x + w - 2 * s, y), (x + w - 2 * s, y + s), (x + w - s, y + s),
               (x + w - s, y + 2 * s), (x + w, y + 2 * s), (x + w, y + h - 2 * s), (x + w - s, y + h - 2 * s),
               (x + w - s, y + h - s), (x + w - 2 * s, y + h - s), (x + w - 2 * s, y + h), (x + 2 * s, y + h),
               (x + 2 * s, y + h - s), (x + s, y + h - s), (x + s, y + h - 2 * s), (x, y + h - 2 * s),
               (x, y + 2 * s), (x + s, y + 2 * s), (x + s, y + s), (x + 2 * s, y + s)]
        return poly(pts)
    ikon = stepped(20, 20, 216, 216, 20) + letter_a(128, 128, 112)
    W, H = 640, 280
    t, _ = text_block(W / 2, H / 2, W - 130)
    return ev(ikon), (W, H, ev(stepped(0, 0, W, H, 22) + t))


def v07_sticker():
    rot = -8
    ikon = rrect(32, 32, 192, 192, 30) + letter_a(128, 128, 104)
    W, H = 700, 360
    bw, bh = 600, 240
    t, _ = text_block(W / 2, H / 2, bw - 110)
    am = rrect((W - bw) / 2, (H - bh) / 2, bw, bh, 34) + t
    return (f'<g transform="rotate({rot} 128 128)">{ev(ikon)}</g>',
            (W, H, f'<g transform="rotate({rot / 2} {W / 2} {H / 2})">{ev(am)}</g>'))


def v08_kurdele():
    def ribbon(x, y, w, h, tail, notch, pad):
        """Arkada V çentikli iki uç, önde beyaz kenarlıklı bant. SVG parçası döndürür."""
        y1, y2 = y + h * 0.32, y + h * 1.32
        tails = (poly([(x, y1), (x + tail * 1.6, y1), (x + tail * 1.6, y2), (x, y2), (x + notch, (y1 + y2) / 2)])
                 + poly([(x + w, y1), (x + w - tail * 1.6, y1), (x + w - tail * 1.6, y2), (x + w, y2),
                         (x + w - notch, (y1 + y2) / 2)]))
        bx, bw = x + tail, w - 2 * tail
        return (f'<path d="{tails}"/>'
                f'<path fill="#fff" d="{rrect(bx - pad, y - pad, bw + 2 * pad, h + 2 * pad, 6 + pad)}"/>'
                f'<path d="{rrect(bx, y, bw, h, 6)}"/>')
    ikon = ev(cartridge(40, 10, 176, 180, 22, cut_tr=40) + letter_a(128, 92, 92)) + ribbon(10, 150, 236, 52, 34, 14, 6)
    W, H = 640, 320
    am = ev(cartridge(50, 0, W - 100, 230, 30, cut_tr=60) + word_fit(BLACK, "ANDROE", W / 2, 148, W - 210)[0])
    am += ribbon(0, 196, W, 88, 60, 24, 8)
    am += f'<path fill="#fff" d="{word(SEMI, "STUDIO", W / 2, 196 + 44 + 18, 36, 22)}"/>'
    return ikon, (W, H, am)


def v09_jeton():
    def coin(cx, cy, r, teeth):
        pts = []
        for i in range(teeth * 2):
            ang = math.pi * i / teeth
            rr = r if i % 2 == 0 else r * 0.93
            for da in (-0.5, 0.5):
                a2 = ang + da * math.pi / teeth
                pts.append((cx + rr * math.cos(a2), cy + rr * math.sin(a2)))
        return poly(pts)
    ikon = coin(128, 128, 118, 24) + circle(128, 128, 92) + circle(128, 128, 80) + letter_a(128, 128, 92)
    # amblem: jeton + üzerinden geçen ANDROE bandı, STUDIO jetonun içinde
    W, H = 680, 340
    cx, cy = W / 2, H / 2 - 6
    band_h = 112
    band = rrect(0, cy - band_h / 2, W, band_h, 22)
    a, cap = word_fit(BLACK, "ANDROE", cx, 0, W - 120, max_cap=band_h * 0.62)
    a, _ = word_fit(BLACK, "ANDROE", cx, cy + cap / 2, W - 120, max_cap=band_h * 0.62)
    coin_d = coin(cx, H / 2, 166, 28) + circle(cx, H / 2, 134)
    sep = f'<path fill="#fff" d="{rrect(-6, cy - band_h / 2 - 12, W + 12, band_h + 24, 30)}"/>'
    studio = word(SEMI, "STUDIO", cx, cy + band_h / 2 + 40, 24, 8)
    am = ev(coin_d) + sep + ev(band + a) + f'<path d="{studio}"/>'
    return ev(ikon), (W, H, am)


def v10_el_konsolu():
    # dikey el konsolu: ekranda A, altta d-pad ve iki tuş
    body = cartridge(40, 8, 176, 240, 24) + rrect(58, 28, 140, 118, 12)
    a = letter_a(128, 87, 74)
    dpad = rrect(64, 178, 48, 16, 4) + rrect(80, 162, 16, 48, 4)
    btn = circle(170, 176, 11) + circle(150, 198, 11)
    ikon = ev(body + a) + f'<path fill="#fff" d="{dpad}{btn}"/>'
    W, H = 760, 300
    shape = rrect(0, 20, W, H - 20, 70) + rrect(150, 48, W - 300, H - 76, 18)
    t, _ = text_block(W / 2, 20 + (H - 20) / 2, W - 360)
    d2 = rrect(40, 140, 72, 24, 6) + rrect(64, 116, 24, 72, 6)
    b2 = circle(W - 92, 132, 16) + circle(W - 60, 172, 16)
    am = ev(shape + t) + f'<path fill="#fff" d="{d2}{b2}"/>'
    return ikon, (W, H, am)


def v11_hiz_seritli():
    ikon = ev(cartridge(20, 20, 216, 216, 26, cut_tr=52) + letter_a(116, 124, 104))
    ikon += f'<path fill="#fff" d="{corner_stripes(236, 236, (30, 62, 94), 14)}"/>'
    W, H = 680, 300
    t, _ = text_block(300, H / 2, 470)
    am = ev(cartridge(0, 0, W, H, 34, cut_tr=70) + t)
    am += f'<path fill="#fff" d="{corner_stripes(W, H, (44, 88, 132), 20)}"/>'
    return ikon, (W, H, am)


def v12_ust_uste():
    # iki üst üste kartuş (stüdyo = birden çok oyun): arkadaki kayık, öndeki A'lı
    back = cartridge(56, 12, 180, 180, 22, cut_tr=44)
    sep = f'<path fill="#fff" d="{cartridge(10, 52, 204, 204, 30, cut_tr=56)}"/>'
    front = cartridge(20, 62, 184, 184, 22, cut_tr=46) + letter_a(112, 162, 92)
    ikon = ev(back) + sep + ev(front)
    W, H = 680, 330
    back2 = cartridge(50, 0, W - 50, 280, 30, cut_tr=60)
    sep2 = f'<path fill="#fff" d="{cartridge(-14, 36, W - 22, 308, 40, cut_tr=72)}"/>'
    t, _ = text_block((W - 50) / 2, 50 + 140, W - 170)
    front2 = cartridge(0, 50, W - 50, 280, 30, cut_tr=60) + t
    return ikon, (W, H, ev(back2) + sep2 + ev(front2))


VARIANTS = [
    ("01-kartus", "Kartuş", v01_kartus),
    ("02-etiketli", "Etiketli Kartuş", v02_etiketli),
    ("03-cift-kesik", "Çift Kesik", v03_cift_kesik),
    ("04-kalkan", "Kalkan", v04_kalkan),
    ("05-altigen", "Altıgen", v05_altigen),
    ("06-piksel", "Piksel Çerçeve", v06_piksel),
    ("07-sticker", "Sticker", v07_sticker),
    ("08-kurdele", "Kurdele", v08_kurdele),
    ("09-jeton", "Arcade Jeton", v09_jeton),
    ("10-konsol", "El Konsolu", v10_el_konsolu),
    ("11-hiz", "Hız Şeritli", v11_hiz_seritli),
    ("12-ust-uste", "Üst Üste", v12_ust_uste),
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for key, name, fn in VARIANTS:
        ikon, (W, H, am) = fn()
        (OUT / f"{key}-ikon.svg").write_text(svg(256, 256, ikon, f"Androe Studio - {name} ikon"))
        (OUT / f"{key}-amblem.svg").write_text(svg(W, H, am, f"Androe Studio - {name} amblem"))
    print(len(VARIANTS), "varyasyon yazıldı ->", OUT)
