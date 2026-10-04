#!/usr/bin/env python3
"""Önizleme: run.mjs'in (LOG_FILE) yazdığı DUMP karelerini çok kamera açısından çizer.
Kullanım: python preview.py guitar.log out.png [--frames 0,10,20] [--views front,side,threeq,top]
Roblox: karakter -Z'ye bakar, +X karakterin sağıdır. Kameralar ortografik."""
import json, sys, argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CHAINS = [
    ["Root", "Waist", "Neck"],
    ["Waist", "RightShoulder", "RightElbow", "RightWrist", "RightTip"],
    ["Waist", "LeftShoulder", "LeftElbow", "LeftWrist", "LeftTip"],
    ["Root", "RightHip", "RightKnee", "RightAnkle"],
    ["Root", "LeftHip", "LeftKnee", "LeftAnkle"],
]
COL = {"Right": "#e67e22", "Left": "#2980b9"}

def basis(view):
    # (sağ, yukarı) ekran eksenleri (dünya vektörü) - ortografik
    V = {
        "front":  (np.array([-1, 0, 0]), np.array([0, 1, 0])),   # kamera -Z'de, +Z'ye bakar
        "back":   (np.array([1, 0, 0]),  np.array([0, 1, 0])),
        "side":   (np.array([0, 0, -1]), np.array([0, 1, 0])),   # kamera +X'te... karakterin sağından
        "sideL":  (np.array([0, 0, 1]),  np.array([0, 1, 0])),
        "threeq": (np.array([-0.7071, 0, -0.7071]), np.array([0, 1, 0])),
        "top":    (np.array([-1, 0, 0]), np.array([0, 0, -1])),
        "low":    (np.array([-1, 0, 0]), np.array([0, 0.85, 0.5])),
    }
    return V[view]

def proj(p, view):
    r, u = basis(view)
    p = np.array(p)
    return p @ r, p @ u

def draw(ax, fr, view, center, span):
    j = dict(fr["j"])
    j["RightTip"] = fr["RightTip"]; j["LeftTip"] = fr["LeftTip"]
    for ch in CHAINS:
        pts = [j[n] for n in ch if n in j]
        xs, ys = zip(*[proj(p, view) for p in pts])
        side = "Right" if ch[1].startswith("Right") or (len(ch) > 1 and "Right" in ch[1]) else ("Left" if "Left" in ch[1] else None)
        ax.plot(xs, ys, "-", lw=2.2, color=COL.get(side, "#444"))
    # kafa
    hx, hy = proj(fr["head"], view)
    ax.add_patch(plt.Circle((hx, hy), 0.55, fill=False, color="#444", lw=1.5))
    # pelvis-omuz çizgileri
    for a, b in (("RightShoulder", "LeftShoulder"), ("RightHip", "LeftHip")):
        (x1, y1), (x2, y2) = proj(j[a], view), proj(j[b], view)
        ax.plot([x1, x2], [y1, y2], "-", lw=2, color="#555")
    # eklemler
    for n, p in j.items():
        x, y = proj(p, view); ax.plot(x, y, "o", ms=3, color="#222")
    # avuç içi oku (parmak yönü zaten kol sonu)
    for side in ("Left", "Right"):
        w = np.array(j[side + "Wrist"]); pn = np.array(fr[side + "Palm"])
        x1, y1 = proj(w, view); x2, y2 = proj(w + pn * 0.35, view)
        ax.plot([x1, x2], [y1, y2], "-", lw=1, color=COL[side], alpha=0.6)
    # enstrüman
    for g in fr["geo"]:
        xs, ys = zip(*[proj(p, view) for p in g["p"]])
        ax.plot(xs, ys, "-", lw=1.4, color=g["c"])
    ax.set_xlim(center[0] - span, center[0] + span); ax.set_ylim(center[1] - span, center[1] + span)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log"); ap.add_argument("out")
    ap.add_argument("--frames", default="0")
    ap.add_argument("--views", default="front,side,threeq,top")
    ap.add_argument("--span", type=float, default=4.0)
    a = ap.parse_args()
    frames = [json.loads(l[5:]) for l in open(a.log) if l.startswith("DUMP ")]
    idx = [int(x) for x in a.frames.split(",")]
    views = a.views.split(",")
    fig, axs = plt.subplots(len(idx), len(views), figsize=(3.6 * len(views), 3.6 * len(idx)), squeeze=False)
    for r, i in enumerate(idx):
        fr = frames[min(i, len(frames) - 1)]
        c = np.array(fr["j"]["Waist"])
        for cidx, v in enumerate(views):
            cx, cy = proj(c, v)
            draw(axs[r][cidx], fr, v, (cx, cy + 0.6), a.span)
            axs[r][cidx].set_title(f"t={fr['t']:.2f} {v} err={fr['err'][0]:.2f}/{fr['err'][1]:.2f} reach={fr['reach'][0]:.2f}/{fr['reach'][1]:.2f}", fontsize=7)
    plt.tight_layout(); plt.savefig(a.out, dpi=70)
    print("kaydedildi", a.out, len(frames), "kare")

main()
