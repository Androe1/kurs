"""Gül yaprağı dokusu: kullanıcının çizdiği gülden (assets/gul_referans.png) alınan fırça dokusu ve renk paleti.

Doku: çizimin ince ayrıntısı (parlaklığın 3 piksel bulanık hâline oranı: fırça darbeleri, lekeler), yaprak
sınırlarından ve parlak kenar çizgilerinden uzak temiz yamalardan alınır. Her yama, darbeleri dikey
(yaprağın dipten uca v yönü) olacak şekilde döndürülür ve sarmal bir ızgaraya yumuşak kenarlarla
yerleştirilir; sonuç dikişsiz döşenen bir dokudur. Gölgelendirici bu dokuyu yaprağın (a, v)
koordinatlarıyla, çizimdekiyle aynı ölçekte (bir doku pikseli ~ bir ekran pikseli) okur ve yaprak
rengini çarpar. Büyük ölçekli gölge dokuda yoktur; onu sahnenin ışığı verir.

Renk paleti de aynı çizimden ölçülür (kırmızı piksellerin parlaklık yüzdelikleri): gölgeler bordo-siyah,
orta tonlar koyu kan kırmızısı, parlak yerler saf kırmızı; pembemsi vurgu yalnızca en parlak kenarlarda.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.signal import fftconvolve

ASSET = Path(__file__).parent / "assets" / "gul_referans.png"
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    d = (x * x + y * y <= r * r).astype(np.float32)
    return d / d.sum()


def _reference():
    img = np.asarray(Image.open(ASSET).convert("RGB"), np.float32) / 255
    R, G, B = img[..., 0], img[..., 1], img[..., 2]
    red = (R > 0.12) & (R > 2.6 * G) & (R > 1.7 * B)       # yaprak kırmızısı (koyu kıvrımlar dahil)
    return img, srgb_to_linear(img), red


def palette(percentiles=(10, 50, 90, 99)):
    """Referans gülün doğrusal renkleri, parlaklık yüzdeliklerinde (her biri komşu piksellerin ortalaması)."""
    _, lin, red = _reference()
    px = lin[red]
    order = np.argsort(px @ LUMA)
    out = []
    for p in percentiles:
        i = int(len(order) * p / 100)
        out.append(px[order[max(i - 300, 0):i + 300]].mean(0))
    return np.array(out)


def stroke_texture(size=256, patch=26, step=19, seed=0):
    """Referans gülün fırça darbelerinden dikişsiz (döşenebilir) doku: (size, size, 4) float32.

    Çizimin ince ayrıntısı (3 piksel bulanıklığına bölünmüş parlaklık) yaprak sınırlarından uzak, temiz
    yamalardan alınır. Her yama, içindeki darbeler dikey (yaprağın v yönü) olacak şekilde döndürülür ve
    halka biçimli (sarmal) bir ızgaraya yumuşak kenarlarla yerleştirilir. rgb = yaprak rengini çarpan
    doku (ortalaması ~1, çizimdeki küçük renk oynamaları dahil), a = 1."""
    rng = np.random.default_rng(seed)
    img, lin, red = _reference()
    y = np.maximum(lin @ LUMA, 1e-4)
    detail = np.clip(y / ndimage.gaussian_filter(y, 3.0), 0.6, 1.6)
    chroma = lin[red].mean(0) / (lin[red] @ LUMA).mean()
    tint = np.clip(lin / y[..., None] / chroma, 0.5, 2.0)
    # temiz bölge: kırmızı, konturlardan ve parlak kenar çizgilerinden en az 2 piksel uzak
    rim = np.hypot(*np.gradient(ndimage.gaussian_filter(y, 1.0))) > 0.04
    clean = ndimage.binary_erosion(red & ~rim, iterations=2)
    detail = np.where(clean, detail, 1.0)                  # yamaya sızan kontur pikselleri nötr kalsın
    # darbelerin yönü: yapı tensörü (baskın eğim darbelere diktir)
    gy, gx = np.gradient(ndimage.gaussian_filter(detail, 1.0))
    jxx = ndimage.gaussian_filter(gx * gx, 6)
    jyy = ndimage.gaussian_filter(gy * gy, 6)
    jxy = ndimage.gaussian_filter(gx * gy, 6)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # baskın eğim açısı (resim ekseninde)

    r = patch / 2
    cov = fftconvolve(clean.astype(np.float32), _disk(int(r * 1.42)), mode="same")
    cy, cx = np.nonzero(cov > 0.97)
    if len(cy) == 0:
        raise RuntimeError("referans gülde temiz yama bulunamadı")
    # sarmal ızgara: her düğüme rastgele bir temiz yama, yumuşak (kosinüs) ağırlıkla
    acc = np.zeros((size, size, 3), np.float32)
    wsum = np.zeros((size, size), np.float32)
    o = np.arange(patch) - (patch - 1) / 2
    pu, pv = np.meshgrid(o, o)
    win = (np.cos(np.pi * pu / patch) * np.cos(np.pi * pv / patch)) ** 2
    n = int(round(size / step))                    # ızgara aralığı dokuyu tam bölsün (dikiş olmasın)
    for gyi in range(n):
        for gxi in range(n):
            k = rng.integers(len(cy))
            yc, xc = cy[k], cx[k]
            a = theta[yc, xc]                               # eğim yatay olsun -> darbeler dikey
            ca, sa = np.cos(a), np.sin(a)
            px = xc + ca * pu - sa * pv
            py = yc + sa * pu + ca * pv
            d = ndimage.map_coordinates(detail, [py, px], order=1, mode="nearest")
            t = np.stack([ndimage.map_coordinates(tint[..., ch], [py, px], order=1, mode="nearest")
                          for ch in range(3)], -1)
            oy = int(round(gyi * size / n)) + int(rng.integers(-2, 3))
            ox = int(round(gxi * size / n)) + int(rng.integers(-2, 3))
            iy = (oy + np.arange(patch)) % size
            ix = (ox + np.arange(patch)) % size
            acc[np.ix_(iy, ix)] += (d[..., None] * t) * win[..., None]
            wsum[np.ix_(iy, ix)] += win
    tex = acc / np.maximum(wsum, 1e-6)[..., None]
    # örtüşen yamaların ortalaması karşıtlığı biraz düşürür: çizimdeki karşıtlığa geri getir
    lum = tex @ LUMA
    ref_std = detail[clean].std()
    gain = ref_std / max(lum.std(), 1e-6)
    tex = 1.0 + (tex - tex.mean((0, 1))) * gain
    return np.dstack([np.clip(tex, 0.2, 3.0), np.ones((size, size, 1))]).astype(np.float32)
