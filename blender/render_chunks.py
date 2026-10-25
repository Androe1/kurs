"""scp_cinematic.py'yi küçük kare grupları halinde, her grubu ayrı işlemde render eder.

    python3.11 blender/render_chunks.py --preview --step 2     # önizleme
    python3.11 blender/render_chunks.py --jobs 2               # final, iki işlem paralel

Neden: bpy modülü (EEVEE, ekran kartı olmadan) uzun bir animasyonda her karede bellek
biriktirir ve birkaç düzine kareden sonra bellek sınırına takılabilir. Her grup taze bir
işlemle başlar; zaten yazılmış kareler atlanır, yani yarıda kalan render kaldığı yerden sürer.
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
F_START, F_END = 61, 420
SHOT_BOUNDS = [(61, 180), (181, 300), (301, 420)]  # grup bir planı aşmasın: yalnız o plan kurulur


def chunks(frames, size):
    """Ardışık eksik kareleri plan sınırlarını aşmadan size'lık gruplara böler."""
    out, cur = [], []
    for f in frames:
        shot = next(i for i, (a, b) in enumerate(SHOT_BOUNDS) if a <= f <= b)
        if cur and (len(cur) >= size or f - cur[-1] > STEP or
                    next(i for i, (a, b) in enumerate(SHOT_BOUNDS) if a <= cur[0] <= b) != shot):
            out.append(cur)
            cur = []
        cur.append(f)
    if cur:
        out.append(cur)
    return out


def main():
    global STEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=20, help="işlem başına kare sayısı")
    ap.add_argument("--jobs", type=int, default=1, help="aynı anda çalışan işlem sayısı")
    a = ap.parse_args()
    STEP = a.step
    out = ROOT / ("renders_preview" if a.preview else "renders") / "scp"
    todo = [f for f in range(F_START, F_END + 1, a.step) if not (out / f"{f:04d}.png").exists()]
    groups = chunks(todo, a.chunk)
    print(f"{len(todo)} kare, {len(groups)} grup", flush=True)

    def run(g):
        cmd = [sys.executable, str(HERE / "scp_cinematic.py"), "--step", str(a.step),
               "--frames", f"{g[0]}-{g[-1]}"] + (["--preview"] if a.preview else [])
        r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        done = sum((out / f"{f:04d}.png").exists() for f in g)
        print(f"kare {g[0]}-{g[-1]}: {done}/{len(g)} (çıkış {r.returncode})", flush=True)
        return done == len(g)

    with ThreadPoolExecutor(a.jobs) as ex:
        ok = all(list(ex.map(run, groups)))
    sys.exit(0 if ok else 1)


STEP = 1

if __name__ == "__main__":
    main()
