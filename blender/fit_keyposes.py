"""Referans videonun anahtar karelerinden okunan eklem noktalarıyla vuruş ve hold pozlarını çözer.

Koordinatlar referansın 960x540 ölçeğindeki ekran pikselleridir (sol üst 0,0).
Taraflar karakterin KENDİ sağı/soludur (kameraya bakan karakterin sağı ekranın solunda):
  Pomni : sağ eli kırmızı, sol eli mavi; sol ayağı kırmızı, sağ ayağı mavi
  Caine : sağ elinde baston, sol eli boş
Çıktı: blender/keyposes.json (kök konumu/dönüşü + kemik quaternion'ları).

    python blender/fit_keyposes.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anim  # noqa: E402
import posefit  # noqa: E402

REF = {
    # Pomni 5.35 s: havada, gövde yatay ve göğüs yere dönük; sol (mavi) el aşağı-sağa uzanır,
    # sağ (kırmızı) el gövdenin solunda geride; ayaklar gövdenin altında sallanır
    "c1_hit": {"char": 1, "ref_t": 5.35,
               "pts": {"head": (495, 185), "neck": (455, 268), "pelvis": (430, 332),
                       "Lshoulder": (520, 272), "Lhand": (622, 370), "Rshoulder": (405, 268), "Rhand": (318, 282),
                       "Lhip": (452, 342), "Lfoot": (450, 395), "Rhip": (410, 338), "Rfoot": (355, 380)},
               "hints": {"front": [("UpperTorso", (0.0, -0.45, -0.9), 1.6), ("Head", (0.0, -1.0, 0.35), 2.0)],
                         "behind": [("Lfoot", 0.6), ("Lknee", 0.3)],
                         "loc0": (0.0, -3.0, 0.0)}},
    # Pomni 5.60 s: sol (mavi) el sağ üste savrulur, sağ (kırmızı) el aşağı yüzer gibi çırpar,
    # sağ (mavi) ayak yana tekmeler, sol (kırmızı) ayak aşağıda
    "c1_hold": {"char": 1, "ref_t": 5.60,
                "pts": {"head": (505, 205), "neck": (455, 305), "pelvis": (440, 372),
                        "Lshoulder": (540, 300), "Lhand": (720, 222), "Rshoulder": (400, 305), "Rhand": (395, 490),
                        "Lhip": (462, 385), "Lfoot": (470, 500), "Rhip": (415, 382), "Rfoot": (300, 355)},
                "hints": {"front": [("UpperTorso", (0.0, -0.5, -0.85), 1.6), ("Head", (0.0, -1.0, 0.3), 2.0)],
                          "behind": [("Lfoot", 0.6), ("Lknee", 0.3)],
                          "loc0": (0.0, -3.0, 0.0)}},
    # Caine 6.20 s: sağa dönerek açılmış; boş sol el sağ üste, bastonlu sağ el sol aşağıda,
    # bacaklar sol alta (kameraya yakın)
    "c2_hit": {"char": 2, "ref_t": 6.20,
               "pts": {"head": (505, 135), "neck": (500, 272), "pelvis": (440, 410),
                       "Lshoulder": (560, 262), "Lhand": (872, 200), "Rshoulder": (452, 272), "Rhand": (292, 390),
                       "Lhip": (462, 415), "Lfoot": (330, 560), "Rhip": (420, 405), "Rfoot": (110, 500)},
               "hints": {"front": [("UpperTorso", (0.5, -0.6, 0.62), 5.0), ("LowerTorso", (0.45, -0.75, 0.45), 3.0), ("Head", (0.3, -0.9, 0.3), 1.5)],
                         "loc0": (0.0, -1.0, 0.0), "depth": 8.0}},
    # Caine 6.40 s: çapraz poz; sağ bacak dizden kırık öne-yukarı, sol bacak düz aşağı-sola
    "c2_hold": {"char": 2, "ref_t": 6.40,
                "pts": {"head": (495, 98), "neck": (520, 250), "pelvis": (470, 345),
                        "Lshoulder": (570, 232), "Lhand": (772, 128), "Rshoulder": (478, 262), "Rhand": (322, 262),
                        "Lhip": (490, 352), "Lfoot": (250, 470), "Rhip": (450, 340), "Rfoot": (268, 302)},
                "hints": {"front": [("UpperTorso", (0.5, -0.6, 0.62), 5.0), ("LowerTorso", (0.45, -0.75, 0.45), 3.0), ("Head", (0.3, -0.9, 0.3), 1.5)],
                          "loc0": (0.0, -1.0, 0.0), "depth": 8.5}},
}


def main():
    out = {}
    for char in (1, 2):
        ch, cam = anim.setup_scene(char, (960, 540))
        pf = posefit.PoseFit(ch.arm, cam, (960, 540))
        x_prev = None
        for name, spec in REF.items():
            if spec["char"] != char:
                continue
            best = None
            # birkaç başlangıçtan çöz, en iyisini al (derinlik belirsizliği)
            starts = [None] + ([x_prev] if x_prev is not None else [])
            rng = np.random.default_rng(3)
            for _ in range(2):
                x0 = np.zeros(6 + sum(len(a) for _, a in posefit.DOF))
                x0[:3] = spec["hints"]["loc0"]
                x0[3:] = rng.uniform(-25, 25, len(x0) - 3)
                starts.append(x0)
            for x0 in starts:
                x, cost = pf.solve(spec["pts"], spec["hints"], x0)
                if best is None or cost < best[1]:
                    best = (x, cost)
            x_prev = best[0]
            out[name] = {**pf.to_pose(best[0]), "ref_t": spec["ref_t"]}
            print(name, "maliyet", round(float(best[1]), 2))
            for k, v in pf.report(best[0], spec["pts"]).items():
                print(f"   {k:10s} bizim ({v[0]:4d},{v[1]:4d})  hedef {spec['pts'][k]}  fark {v[2]} px")
    Path(__file__).with_name("keyposes.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
