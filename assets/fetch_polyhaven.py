"""SCP sinematiğinin Poly Haven (CC0) modellerini indirir: assets/models/polyhaven/<id>/.

    python assets/fetch_polyhaven.py            # 2k dokular
    python assets/fetch_polyhaven.py --res 1k   # daha hafif

Her model için glTF dosyası, .bin ve dokuları (glTF'in kendi listesinden) indirilir.
Modellerin sahnedeki adları assets/models/models.json'da eşlenir.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://dl.polyhaven.org/file/ph-assets/Models"
UA = {"User-Agent": "kurs-scp-cinematic/1.0 (Blender sahne kurulumu)"}
OUT = Path(__file__).resolve().parent / "models" / "polyhaven"

MODELS = [
    "wooden_military_crate", "old_military_crate", "ammo_box", "bolt_action_rifle_7_62",
    "metal_jerrycan_green", "portable_generator", "hanging_industrial_lamp",
    "tree_stump_01", "dead_tree_trunk",  # (fir/pine_tree_01 ~1 GB; ağaçlar prosedürel)
    "concrete_road_barrier", "modular_chainlink_fence",
]


def get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        path.write_bytes(r.read())


def fetch(asset, res):
    d = OUT / asset
    base = f"{BASE}/gltf/{res}/{asset}"
    gltf = d / f"{asset}_{res}.gltf"
    get(f"{base}/{gltf.name}", gltf)
    g = json.loads(gltf.read_text())
    uris = [b["uri"] for b in g.get("buffers", [])] + [i["uri"] for i in g.get("images", [])]
    for u in uris:
        # dokular glTF klasöründe değil, Models/jpg/<res>/<id>/ altında
        url = f"{BASE}/jpg/{res}/{asset}/{Path(u).name}" if u.startswith("textures/") else f"{base}/{u}"
        get(url, d / u)
    return len(uris)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k", choices=["1k", "2k", "4k"])
    ap.add_argument("models", nargs="*", default=MODELS)
    a = ap.parse_args()
    failed = []
    for m in a.models:
        try:
            n = fetch(m, a.res)
            print(f"ok   {m} ({n} dosya)")
        except Exception as e:  # noqa: BLE001 - tek modelin hatası diğerlerini durdurmasın
            print(f"HATA {m}: {e}")
            failed.append(m)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
