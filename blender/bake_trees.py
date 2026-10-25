"""Poly Haven fir_tree_01'i (~480 MB geometri) çapraz düzlemli "impostor" ağaca pişirir.

    python3.11 blender/bake_trees.py

Ağaç bir kez içe aktarılır, üç açıdan (0/60/120°) ortografik ve şeffaf arka planla render
edilir. Sahne her ağacı bu üç görüntüyü taşıyan üç dikey düzlemle çizer: binlerce ağaç
milyonlarca üçgen yerine birkaç bin üçgen olur, uzakta ve siste gerçek ağaçtan ayırt edilmez.

Çıktı: assets/models/polyhaven/fir_tree_01/impostor_{0,1,2}.png + impostor.json
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "models" / "polyhaven" / "fir_tree_01"
ANGLES = (0, 60, 120)
RES_Y = 1536


def main():
    blend = next(SRC.glob("*.blend"), None)
    if blend:  # Blender'ın kendi dosyası saniyeler içinde açılır (glTF içe aktarıcı dakikalar sürer)
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        bpy.ops.file.find_missing_files(directory=str(SRC / "textures"))
        for o in list(bpy.data.objects):
            if o.type in ("CAMERA", "LIGHT"):
                bpy.data.objects.remove(o)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(next(SRC.glob("*.gltf"))))
    visible = [o for o in bpy.data.objects if o.type == "MESH" and o.visible_get()]
    # .blend'de her ağacın üç detay seviyesi üst üste durur; en detaylısı (LOD0) pişirilir.
    lod0 = [o for o in visible if o.name.endswith("_LOD0")]
    meshes = lod0 or visible
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE_NEXT"
    s.eevee.taa_render_samples = 16
    s.render.film_transparent = True
    s.view_settings.view_transform = "Standard"
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    w = bpy.data.worlds.new("flat")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    s.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 1.5
    s.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    s.collection.objects.link(cam)
    s.camera = cam
    trees = []
    # Dosyada yan yana birkaç ağaç var: her biri ayrı impostor olur.
    for v, tree in enumerate(sorted(meshes, key=lambda o: o.matrix_world.translation.x)):
        for o in visible:
            o.hide_render = o is not tree
        pts = [tree.matrix_world @ Vector(c) for c in tree.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        center = (lo + hi) / 2
        height = hi.z - lo.z
        radius = max(hi.x - center.x, center.x - lo.x, hi.y - center.y, center.y - lo.y)
        width = 2 * radius * 1.04
        print(f"ağaç {v} ({tree.name}):", [round(x, 2) for x in (hi - lo)], flush=True)
        res_x = int(RES_Y * width / (height * 1.02) / 8) * 8
        s.render.resolution_x, s.render.resolution_y = res_x, RES_Y
        cam.data.ortho_scale = height * 1.02
        for k, a in enumerate(ANGLES):
            d = Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0))
            cam.location = center + d * (radius + 20)
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            cam.data.clip_end = 2 * radius + 60
            sun.rotation_euler = (-(d + Vector((0, 0, -1.2)))).to_track_quat("-Z", "Y").to_euler()
            s.render.filepath = str(SRC / f"impostor_{v}_{k}.png")
            bpy.ops.render.render(write_still=True)
            print("yazıldı", s.render.filepath, flush=True)
        trees.append({"height": height, "width": width, "angles": list(ANGLES)})
    (SRC / "impostor.json").write_text(json.dumps({"trees": trees}, indent=2))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
