"""Korku teaser'ı - şeytani gözler: kullanıcının çizimi (assets/seytani_gozler.png) doku olarak kullanılır.

Çizimde arka plan şeffaf, göz akı opak beyaz, fırça darbeleri koyu kızıldır. Çizimdeki göz bebekleri
silinip yerine shader'da animasyonlu göz bebekleri çizilir (açılınca büyükten iğne ucuna büzülür,
titrer). Açılma, darbelerin gözden dışa doğru belirmesi, çizgilerin "kaynaması" ve sarsıntı shader'da.
"""
from pathlib import Path

import numpy as np

ASSET = Path(__file__).parent / "assets" / "seytani_gozler.png"

# Çizim düzleminde (1536 x 1024 piksel) göz bebeklerinin merkezi ve yarıçapı
PUPILS = ((387.3, 539.0), (1146.9, 538.0))
PUPIL_R = 17.5
CENTER = (767.1, 538.5)             # iki gözün ortası; ekranın ortasına oturur
SCREEN_WIDTH = 0.84                 # gözlerin tamamı ekran genişliğinin bu kadarını kaplar
EXTENT_X = (35.0, 1500.0)           # çizimdeki gözlerin yatay kapsamı


def eye_image():
    """(H, W, 4) uint8 RGBA: çizimdeki göz bebekleri göz akı rengiyle kapatılmış."""
    from PIL import Image

    a = np.asarray(Image.open(ASSET).convert("RGBA")).copy()
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    for (px, py) in PUPILS:
        m = (xx - px) ** 2 + (yy - py) ** 2 <= (PUPIL_R + 7.0) ** 2
        a[m] = (255, 255, 255, 255)
    return a


def ref_per_unit(aspect=16 / 9):
    """Ekran yüksekliği birimi başına çizim pikseli."""
    return (EXTENT_X[1] - EXTENT_X[0]) / (SCREEN_WIDTH * aspect)


def eye_lids():
    """Kapak animasyonu için çizimden çıkarılan veriler.

    Dönüş: (aux, lids)
      aux  : (H, W, 4) uint8 - R: göz akına yakın mürekkep ağırlığı (kapak konturu; kapalıyken gizlenir),
             G: temiz göz akı maskesi
      lids : (W, 4) float32 - her sütun için göz akının üst sınırı, alt sınırı, kapalı kapakların
             buluştuğu çizgi (piksel satırı) ve geçerlilik
    """
    from PIL import Image
    from scipy import ndimage as ndi

    a = np.asarray(Image.open(ASSET).convert("RGBA")).astype(np.float32)
    A = a[..., 3] / 255.0
    L = a[..., :3].mean(2)
    sclera = (A > 0.5) & (L > 170)
    lab, n = ndi.label(sclera)
    sizes = ndi.sum(sclera, lab, range(1, n + 1))
    keep = np.zeros_like(sclera)
    for i in np.argsort(sizes)[::-1][:2]:
        keep |= ndi.binary_fill_holes(lab == i + 1)
    h, w = keep.shape
    lids = np.zeros((w, 4), np.float32)
    rows = np.arange(h)
    for x in range(w):
        col = keep[:, x]
        if col.sum() < 3:
            continue
        top, bot = rows[col].min(), rows[col].max()
        lids[x] = (top, bot, 0.0, 1.0)
    valid = lids[:, 3] > 0
    # sınırları yumuşat, kapalı kapak çizgisi göz akının alt üçte birine yakın
    for k in (0, 1):
        v = lids[:, k].copy()
        sm = ndi.uniform_filter1d(np.where(valid, v, 0.0), 9) / np.maximum(ndi.uniform_filter1d(valid.astype(float), 9), 1e-6)
        lids[:, k] = np.where(valid, sm, 0.0)
    lids[:, 2] = lids[:, 0] + 0.62 * (lids[:, 1] - lids[:, 0])
    # göz akına 26 piksel içindeki mürekkep = kapak konturu
    dist = ndi.distance_transform_edt(~keep)
    near = np.clip(1.0 - (dist - 14.0) / 16.0, 0.0, 1.0)
    aux = np.zeros((h, w, 4), np.uint8)
    aux[..., 0] = (near * 255).astype(np.uint8)
    aux[..., 1] = (keep * 255).astype(np.uint8)
    aux[..., 3] = 255
    return aux, lids

