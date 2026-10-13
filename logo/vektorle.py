"""AI taslağını (ai-taslaklar/05.webp) temiz, simetrik bir vektör işarete çevirir.

Adımlar: rengi maskele -> simetri eksenini bul -> sol yarıyı aynala (kusursuz simetri)
-> büyütüp yumuşat -> potrace ile Bezier eğrilerine çevir -> 256'lık tuvale oturt.
Kullanım: python logo/vektorle.py  ->  logo/final/isaret.svg
Gerekenler: opencv-python-headless, potracer, numpy
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import potrace

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "ai-taslaklar" / "05.webp"
OUT = ROOT / "final"
UP = 2          # büyütme katsayısı (yumuşak kenar için)
BLUR = 11       # büyütülmüş görüntüde yumuşatma çekirdeği


def load_mask(path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = (hsv[..., 1] > 80) & (hsv[..., 2] > 60)          # doygun mor pikseller
    color = np.median(img[mask], axis=0)[::-1]                # BGR -> RGB
    return mask.astype(np.uint8) * 255, color


def symmetric(mask):
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = mask[y0:y1, x0:x1].astype(np.float32)
    # en iyi ayna eksenini ara (bbox merkezinin çevresinde)
    best, axis = None, None
    w = m.shape[1]
    for a in np.arange(w / 2 - 8, w / 2 + 8, 0.5):
        k = int(round(a))
        half = min(k, w - k)
        left = m[:, k - half:k]
        right = m[:, k:k + half][:, ::-1]
        err = np.abs(left - right).mean()
        if best is None or err < best:
            best, axis = err, k
    left = m[:, :axis]
    return np.hstack([left, left[:, ::-1]]).astype(np.uint8), best


def trace(mask):
    mask = cv2.copyMakeBorder(mask, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=0)  # kenara değmesin
    big = cv2.resize(mask, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (BLUR, BLUR), 0)
    bm = big > 127
    bmp = potrace.Bitmap(bm)
    path = bmp.trace(turdsize=200, alphamax=1.2, opticurve=True, opttolerance=2.0)
    # potracer, bitmap'in dış çerçevesini de bir eğri olarak verir: onu at
    def frame(c):
        xs = [c.start_point.x] + [sg.end_point.x for sg in c.segments]
        ys = [c.start_point.y] + [sg.end_point.y for sg in c.segments]
        return min(xs) <= 1 and min(ys) <= 1 and max(xs) >= bm.shape[1] - 1 and max(ys) >= bm.shape[0] - 1
    curves = [c for c in path if not frame(c)]
    return curves, bm.shape


def to_d(path, scale, dx, dy):
    f = lambda p: f"{p.x * scale + dx:.2f} {p.y * scale + dy:.2f}"
    out = []
    for curve in path:
        out.append("M" + f(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                out.append("L" + f(seg.c) + "L" + f(seg.end_point))
            else:
                out.append("C" + f(seg.c1) + " " + f(seg.c2) + " " + f(seg.end_point))
        out.append("Z")
    return "".join(out)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    mask, color = load_mask(SRC)
    sym, err = symmetric(mask)
    path, (h, w) = trace(sym)
    # 256 yüksekliğe değil, uzun kenar 232 olacak şekilde 256x256 tuvale ortala
    s = 232 / max(h, w)
    dx, dy = (256 - w * s) / 2, (256 - h * s) / 2
    d = to_d(path, s, dx, dy)
    hexcol = "#%02X%02X%02X" % tuple(int(c) for c in color)
    (OUT / "isaret.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">'
        f'<title>Androe Studio işaret</title><path fill="#000" fill-rule="evenodd" d="{d}"/></svg>\n')
    print(f"simetri hatası: {err:.4f}  eğri sayısı: {len(path)}  oran: {w}x{h}  renk: {hexcol}")
