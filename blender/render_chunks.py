"""scp_cinematic.py'yi plan plan, küçük kare grupları halinde ve her grubu ayrı işlemde render eder.

    python3.11 blender/render_chunks.py --preview --step 2     # önizleme
    python3.11 blender/render_chunks.py                        # final
    python3.11 blender/render_chunks.py --shot contain --jobs 2

Neden: bpy modülü (EEVEE, ekran kartı olmadan) uzun bir animasyonda her karede bellek
biriktirir ve birkaç düzine kareden sonra bellek sınırına takılabilir. Her grup taze bir
işlemle başlar; zaten yazılmış kareler atlanır, yani yarıda kalan render kaldığı yerden sürer.
Kareler renders[_preview]/scp/<plan>/####.png altına yazılır.
"""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# scp_cinematic.SHOTS ve HANDLE ile aynı olmalı (bpy'yi yüklememek için burada tekrarlanır).
SHOTS = {"secure": (1, 216), "contain": (217, 408), "protect": (409, 552)}
F_START, F_END, HANDLE = 1, 552, 0


def span(name):
    f0, f1 = SHOTS[name]
    return max(F_START, f0 - HANDLE), min(F_END, f1 + HANDLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--shot", choices=list(SHOTS), action="append")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=16, help="işlem başına kare sayısı")
    ap.add_argument("--jobs", type=int, default=1, help="aynı anda çalışan işlem sayısı")
    a = ap.parse_args()
    out = ROOT / ("renders_preview" if a.preview else "renders") / "scp"
    groups = []
    for name in a.shot or list(SHOTS):
        r0, r1 = span(name)
        todo = [f for f in range(r0, r1 + 1, a.step) if not (out / name / f"{f:04d}.png").exists()]
        cur = []
        for f in todo:
            if cur and (len(cur) >= a.chunk or f - cur[-1] != a.step):
                groups.append((name, cur))
                cur = []
            cur.append(f)
        if cur:
            groups.append((name, cur))
    total = sum(len(g) for _, g in groups)
    print(f"{total} kare, {len(groups)} grup", flush=True)
    t0 = time.time()
    done_frames = [0]

    def run(job):
        name, g = job
        cmd = [sys.executable, str(HERE / "scp_cinematic.py"), "--shot", name, "--step", str(a.step),
               "--frames", f"{g[0]}-{g[-1]}"] + (["--preview"] if a.preview else [])
        r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok = sum((out / name / f"{f:04d}.png").exists() for f in g)
        done_frames[0] += ok
        el = time.time() - t0
        eta = el / max(done_frames[0], 1) * (total - done_frames[0])
        print(f"{name} {g[0]}-{g[-1]}: {ok}/{len(g)} (çıkış {r.returncode}) | {done_frames[0]}/{total} kare, "
              f"kalan ~{eta / 60:.0f} dk", flush=True)
        return ok == len(g)

    with ThreadPoolExecutor(a.jobs) as ex:
        ok = all(list(ex.map(run, groups)))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
