"""Hareket kalite kontrolü: bir noktanın (göğüs, kök...) kare kare konumundan fizik hatalarını bulur.

    python check_motion.py meta.json [anahtar=chest] [--axis y] [--px 1080]
    python check_motion.py konumlar.csv            # her satır: kare,x,y

meta.json biçimi: {"0": {"chest": [x, y]}, "1": {...}}  (0-1 ekran koordinatı)

Raporlar:
  * hız sıçraması  : ardışık hız farkı ortalama ivmenin çok üstünde -> "duvara çarpma"
  * ölü hold       : havadayken ivmenin ~0 kaldığı uzun aralık -> yerçekimi yok
  * ters sarsıntı  : düşüşten hemen önce hızın ters yöne dönmesi (yukarı zıplayıp düşme)
Sayılar piksel/kare cinsindendir.
"""
import json
import sys

import numpy as np


def load(path, key, axis):
    if path.endswith(".json"):
        m = {int(k): v for k, v in json.load(open(path)).items()}
        i = 0 if axis == "x" else 1
        return np.array([m[f][key][i] for f in sorted(m)])
    d = np.loadtxt(path, delimiter=",")
    return d[:, 1 if axis == "x" else 2]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    path = args[0]
    key = args[1] if len(args) > 1 else "chest"
    axis = opts.get("--axis", "y")
    px = float(opts.get("--px", 1080))
    y = load(path, key, axis) * (px if path.endswith(".json") else 1)
    v = np.diff(y)
    a = np.diff(v)
    print("konum :", np.round(y).astype(int).tolist())
    print("hız   :", np.round(v).astype(int).tolist())
    typ = np.median(np.abs(a)) + 1e-6
    bad = []
    for i, ai in enumerate(a):
        if abs(ai) > 4 * typ + 8:
            bad.append(f"kare {i + 1}: hız {v[i]:+.0f} -> {v[i + 1]:+.0f} (sıçrama {ai:+.0f})")
    # ölü hold: hızın küçük kaldığı (|v| <= 12) 10+ karelik aralıkta hız neredeyse hiç
    # değişmiyorsa yerçekimi yoktur. Gerçek havada kalmada (hang time) hız yavaş da olsa
    # düzenli değişir: yukarı hareket -> 0 -> aşağı hareket.
    dead = []
    i = 0
    while i < len(v):
        if abs(v[i]) <= 12:
            j = i
            while j + 1 < len(v) and abs(v[j + 1]) <= 12:
                j += 1
            n = j - i + 1
            if n >= 10 and (v[j] - v[i]) / n < 0.5:
                dead.append((i, j))
            i = j + 1
        else:
            i += 1
    best = max((j - i + 1 for i, j in dead), default=0)
    # ters sarsıntı: hız işaret değiştirip hemen geri dönerse
    flips = [i for i in range(1, len(v) - 2) if np.sign(v[i]) != np.sign(v[i - 1]) and np.sign(v[i + 1]) != np.sign(v[i]) and abs(v[i]) > 10]
    print("\nsıçramalar:", bad or "yok")
    print("yerçekimsiz donma:", [f"kare {i}-{j}" for i, j in dead] or "yok", "(sorun)" if dead else "(iyi)")
    print("ters sarsıntı:", [f"kare {i}" for i in flips] or "yok")


if __name__ == "__main__":
    main()
