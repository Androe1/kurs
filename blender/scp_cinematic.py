"""SCP tarzı 12 saniyelik sinematik (headless bpy): depo -> yol -> tesis (+ 2D logo kartı).

    python3.11 blender/render_chunks.py --preview --step 2   # önizleme (640x360)
    python3.11 blender/render_chunks.py --step 2             # final: 1920x1080, 30 fps render
    python3.11 blender/scp_cinematic.py --preview --still 60,300,480
    python3.11 blender/scp_cinematic.py --shot secure --check  # yalnızca kurulum kontrolleri

Kurgu (t = final videodaki saniye; yazılar ve logo scp_intro.py'de 2D katman olarak basılır):

  kare   1-216  (0.0-3.6)  SECURE  - tavanlı depo: kasalar, silah rafında M4A1'ler, kirişe asılı
                                     lamba, kapıdan giren projektör huzmesi; kamera yavaşça kayar
  kare 217-408  (3.6-6.8)  CONTAIN - gece orman yolu, iki 8x8 zırhlı araç önden geçer
  kare 409-552  (6.8-9.2)  PROTECT - kamera tesis kapısına ve SCP amblemine yaklaşır

Kurulumdan sonra kontroller yazdırılır ve meta.json'a yazılır: zemine oturma (ışın atışıyla),
ön plan nesnesinin kadraj kaplaması, kameranın bir objenin içine girip girmediği.

Çıktı: renders/scp/<plan>/####.png (+ meta.json: ses ve kurgu için olay zamanları).
"""
import argparse
import json
import math
import os
import random
import re
import sys
from pathlib import Path

import bpy  # noqa: I001  (bmesh, bpy'den sonra yüklenebilir)
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vehicles  # noqa: E402
sys.path.insert(0, str(ROOT))
import scp_logo  # noqa: E402
ASSETS = ROOT / "assets" / "models"
FONT = ROOT / "fonts" / "Inter-Light.otf"

FPS = 60
# Blender karesi f <-> final videoda t = (f - 1) / 60 sn. Planlar sert kesme / siyaha karartma ile
# ayrılır (taşma yok); 9.2-12.0 sn SCP logosu scp_intro.py'de 2D çizilir.
F_START, F_END = 1, 552
SHOTS = {  # ad: (ilk kare, son kare, sahnenin dünya ofseti)
    "secure": (1, 216, Vector((0, 0, 0))),       # 0.0-3.6 sn  depo
    "contain": (217, 408, Vector((500, 0, 0))),  # 3.6-6.8 sn  yol
    "protect": (409, 552, Vector((1000, 0, 0))),  # 6.8-9.2 sn  tesis
}
END_TIME = 12.0

# Modelin yönü: ileri (namlu / aracın önü) +X, yukarı +Z, taban z=0.
# file: assets/models altındaki klasör (Poly Haven, CC0; assets/fetch_polyhaven.py indirir)
# only: yalnızca adı bu ekle biten parçalar; lid: kapağı arka menteşeden açılacak parça.
ASSET_SPECS = {
    "rifle": {"length": 0.84},
    "rifle_fde": {"length": 0.84},  # çöl rengi (FDE) dipçik/kabza  # M4A1 (prosedürel; assets/models/rifle.glb konursa o kullanılır)
    "crate": {"length": 1.25, "file": "polyhaven/wooden_military_crate"},
    "crate_open": {"length": 1.25, "file": "polyhaven/wooden_military_crate", "lid": "_lid"},
    "crate_olive": {"length": 0.8, "file": "polyhaven/old_military_crate", "only": "_a"},
    "crate_olive_open": {"length": 0.8, "file": "polyhaven/old_military_crate", "only": "_b"},
    "ammo": {"length": 0.26, "file": "polyhaven/ammo_box", "rot": (0, 0, 90)},
    "jerrycan": {"length": 0.37, "file": "polyhaven/metal_jerrycan_green"},
    "generator": {"length": 0.82, "file": "polyhaven/portable_generator"},
    "hang_lamp": {"height": 1.36, "file": "polyhaven/hanging_industrial_lamp"},
    "barrier": {"length": 1.55, "file": "polyhaven/concrete_road_barrier"},
    "fence": {"length": 1.91, "file": "polyhaven/modular_chainlink_fence", "only": "_fence_double"},
    "log": {"length": 3.05, "file": "polyhaven/dead_tree_trunk"},
    "stump": {"length": 1.43, "file": "polyhaven/tree_stump_01"},
    "apc": {"length": 7.0},
    "truck": {"length": 7.5},
    "pine": {"height": 1.0},  # ağaçlar sahnede ayrıca ölçeklenir
}


# --------------------------------------------------------------------------- yardımcılar

def frame_time(f):
    """Blender karesi -> final videodaki saniye."""
    return (f - 1) / FPS


def material(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit is not None:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    return m


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = link(bpy.data.objects.new(name, None), parent)
    e.location = loc
    return e


class Builder:
    """bmesh ile parça parça blok model: kutu, silindir, koni, halka."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _tag(self, verts, mat):
        mi = self._mi(mat)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = mi

    def box(self, size, loc, mat, rot=(0, 0, 0)):
        g = bmesh.ops.create_cube(self.bm, size=1.0,
                                  matrix=Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(size)))
        self._tag(g["verts"], mat)

    def cyl(self, r1, r2, depth, loc, mat, rot=(0, 0, 0), segs=16):
        g = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2,
                                  depth=depth, matrix=Matrix.LocRotScale(Vector(loc), Euler(rot), None))
        self._tag(g["verts"], mat)

    def prism(self, pts_xz, thick, mat, y=0.0):
        """XZ düzleminde verilen yan profili Y boyunca thick kalınlığında ekstrüde eder."""
        bm = self.bm
        a = [bm.verts.new((x, y - thick / 2, z)) for x, z in pts_xz]
        b = [bm.verts.new((x, y + thick / 2, z)) for x, z in pts_xz]
        faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
        n = len(pts_xz)
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
        mi = self._mi(mat)
        for f in faces:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(bm, faces=faces)

    def ring(self, r_in, r_out, thick, mat, segs=128, y=0.0):
        """XZ düzleminde halka (annulus), Y boyunca thick kalınlığında."""
        bm = self.bm
        rows = []
        for yy in (y - thick / 2, y + thick / 2):
            for r in (r_out, r_in):
                rows.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs), yy,
                                           r * math.sin(2 * math.pi * i / segs))) for i in range(segs)])
        fo, fi, bo, bi = rows
        faces = []
        for i in range(segs):
            j = (i + 1) % segs
            faces += [bm.faces.new((fo[i], fo[j], fi[j], fi[i])), bm.faces.new((bo[i], bi[i], bi[j], bo[j])),
                      bm.faces.new((fo[i], bo[i], bo[j], fo[j])), bm.faces.new((fi[i], fi[j], bi[j], bi[i]))]
        mi = self._mi(mat)
        for f in faces:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(bm, faces=faces)

    def build(self, name, bevel=0.0):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        for p in me.polygons:
            p.use_smooth = True
        obj = link(bpy.data.objects.new(name, me))
        if bevel:
            b = obj.modifiers.new("bevel", "BEVEL")
            b.width, b.segments, b.limit_method, b.harden_normals = bevel, 2, "ANGLE", True
        return obj


def spot(name, loc, target, power, color=(1, 1, 1), size=40, blend=0.4, dist=90, parent=None,
         volume=1.0, shadow=False):
    """Spot ışık. Gölge yalnızca görüntüde fark edilen anahtar ışıklarda açılır: işlemciyle çalışan
    EEVEE'de gölge haritaları kare süresinin büyük kısmını yer (ölçüm: 431 sn -> 75 sn)."""
    d = bpy.data.lights.new(name, "SPOT")
    d.energy, d.color = power, color
    d.spot_size, d.spot_blend = math.radians(size), blend
    d.use_custom_distance, d.cutoff_distance = True, dist
    d.volume_factor, d.use_shadow = volume, shadow
    if hasattr(d, "shadow_resolution_limit"):
        d.shadow_resolution_limit = 0.004
    o = link(bpy.data.objects.new(name, d), parent)
    o.location = loc
    if target is not None:
        aim(o, target)
    return o


def area(name, loc, target, power, size, color=(1, 1, 1)):
    """Geniş, yumuşak dolgu ışığı (kendisi render'da görünmez, ışık noktası oluşturmaz)."""
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.color, d.size, d.use_shadow = power, color, size, False
    o = link(bpy.data.objects.new(name, d))
    o.location = loc
    aim(o, target)
    return o


def point(name, loc, power, color, radius=0.05, dist=40, parent=None):
    d = bpy.data.lights.new(name, "POINT")
    d.energy, d.color, d.shadow_soft_size = power, color, radius
    d.use_custom_distance, d.cutoff_distance = True, dist
    d.use_shadow = False  # nokta ışıklar (bokeh, ampul parıltısı) gölgesiz: küp gölge haritaları çok pahalı
    o = link(bpy.data.objects.new(name, d), parent)
    o.location = loc
    return o


def aim(obj, target):
    """-Z eksenini hedefe çevirir (kamera ve spot ışıkları)."""
    pos = obj.matrix_world.translation if obj.parent else obj.location
    obj.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


def key(obj, frame, loc=None, rot=None, interp="BEZIER"):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert("rotation_euler", frame=frame)
    set_interp(obj, interp)


def set_interp(obj, interp):
    ad = obj.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def look_rot(src, dst):
    return (Vector(dst) - Vector(src)).to_track_quat("-Z", "Y").to_euler()


# --------------------------------------------------------------------------- dış modeller

def base_name(obj):
    """Blender'ın eklediği .001 sonekini atar ("5.56x45.001" -> "5.56x45")."""
    return re.sub(r"\.\d{3}$", "", obj.name)


def find_asset(name, spec, overrides):
    """Önce assets/models/<ad>.* (kullanıcının modeli), sonra models.json / ASSET_SPECS 'file'."""
    for ext in (".glb", ".gltf", ".fbx", ".obj", ".blend"):
        hits = sorted(ASSETS.glob(f"{name}{ext}")) or sorted(ASSETS.glob(f"{name}_*{ext}"))
        if hits:
            return hits[0]
    rel = overrides.get("file") or spec.get("file")
    if rel:
        p = ASSETS / rel
        if p.is_dir():
            hits = sorted(p.glob("*.gltf")) + sorted(p.glob("*.glb"))
            return hits[0] if hits else None
        return p if p.exists() else None
    return None


def import_asset(path):
    before = set(bpy.data.objects)
    ext = path.suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        with bpy.data.libraries.load(str(path)) as (src, dst):
            dst.objects = src.objects
        for o in dst.objects:
            if o is not None:
                bpy.context.scene.collection.objects.link(o)
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o)
    return new


def open_lid(objs, suffix, angle=-105):
    """Kapağı arka üst kenarındaki menteşe çevresinde döndürür (model uzayında)."""
    lid = next((o for o in objs if o.type == "MESH" and base_name(o).endswith(suffix)), None)
    if lid is None:
        return
    bpy.context.view_layer.update()
    pts = [lid.matrix_world @ Vector(c) for c in lid.bound_box]
    hinge = Vector((0, max(p.y for p in pts), max(p.z for p in pts)))
    rot = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(angle), 4, "X") @ Matrix.Translation(-hinge)
    for o in [lid] + [c for c in objs if c.parent is lid]:
        if o.parent is None or o is lid:
            o.matrix_world = rot @ o.matrix_world


def normalize(root, objs, spec, overrides):
    """Modeli root altında +X ileri, taban z=0, merkez x=y=0 olacak şekilde ölçekler."""
    pivot = empty(root.name + "_pivot", parent=root)
    for o in objs:
        if o.parent is None:
            o.parent = pivot
    pivot.rotation_euler = [math.radians(a) for a in overrides.get("rot", spec.get("rot", (0, 0, 0)))]
    bpy.context.view_layer.update()
    inv = root.matrix_world.inverted()
    pts = [inv @ o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    dim = hi - lo
    s = spec["length"] / max(dim.x, 1e-6) if "length" in spec else spec["height"] / max(dim.z, 1e-6)
    s *= overrides.get("scale", 1.0)
    pivot.scale = (s, s, s)
    pivot.location = -Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)) * s
    return root


_TEMPLATES = {}


def clone(template, name):
    """Şablon hiyerarşinin mesh paylaşan kopyası (aynı modeli tekrar tekrar içe aktarmamak için)."""
    mapping = {}
    for o in [template] + list(template.children_recursive):
        c = o.copy()
        link(c)
        mapping[o] = c
    for o, c in mapping.items():
        if o.parent in mapping:
            c.parent = mapping[o.parent]
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    root = mapping[template]
    root.name = name
    root.parent = None
    root.location, root.rotation_euler, root.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    for c in mapping.values():
        c.hide_render = c.hide_viewport = False
    return root


def proxy_box(name, spec):
    b = Builder()
    L = spec.get("length", spec.get("height", 1.0))
    b.box((L, L * 0.45, L * 0.4), (0, 0, L * 0.2), M["olive"])
    return [b.build(name + "_proxy", bevel=0.01)]


def asset(name, proxy=None):
    """Dış model varsa onu, yoksa blok modeli döndürür; ikisi de bir root empty altında."""
    if name in _TEMPLATES:
        return clone(_TEMPLATES[name], name)
    spec = ASSET_SPECS[name]
    overrides = {}
    manifest = ASSETS / "models.json"
    if manifest.exists():
        overrides = json.loads(manifest.read_text()).get(name, {})
    path = find_asset(name, spec, overrides)
    root = empty(name)
    if path:
        objs = import_asset(path)
        drop = set(overrides.get("drop", spec.get("drop", [])))
        if drop:  # istenmeyen parçalar (ör. modelle gelen tek mermi) ve alt nesneleri
            gone = {o for o in objs if base_name(o) in drop}
            gone |= {c for o in gone for c in o.children_recursive}
            for o in gone:
                objs.remove(o)
                bpy.data.objects.remove(o)
        only = overrides.get("only", spec.get("only"))
        if only:
            keep = {o for o in objs if o.type == "MESH" and base_name(o).endswith(only)}
            for o in [o for o in objs if o.type == "MESH" and o not in keep]:
                objs.remove(o)
                bpy.data.objects.remove(o)
        if spec.get("lid"):
            open_lid(objs, spec["lid"])
        normalize(root, objs, spec, overrides)
        root["external"] = path.name
        print(f"[model] {name}: {path.relative_to(ROOT) if ROOT in path.parents else path.name}")
    else:
        for o in (proxy or (lambda: proxy_box(name, spec)))():
            o.parent = root
        print(f"[model] {name}: blok model (assets/models/{name}.glb yok)")
    # Şablon: gizli kopya saklanır, sonraki çağrılar ondan çoğaltılır.
    tmpl = clone(root, name + "_template")
    for c in [tmpl] + list(tmpl.children_recursive):
        c.hide_render = c.hide_viewport = True
    if "external" in root:
        tmpl["external"] = root["external"]
    _TEMPLATES[name] = tmpl
    return root


# --------------------------------------------------------------------------- blok modeller

M = {}


def make_materials():
    M["olive"] = material("olive", (0.05, 0.06, 0.035), 0.65)
    M["olive2"] = material("olive_dark", (0.03, 0.035, 0.022), 0.75)
    M["tire"] = material("tire", (0.012, 0.012, 0.012), 0.9)
    M["gun"] = material("gunmetal", (0.02, 0.02, 0.022), 0.42, 0.7)
    M["anodized"] = material("anodized_black", (0.018, 0.018, 0.02), 0.48, 0.5)
    M["parkerized"] = material("parkerized", (0.022, 0.022, 0.022), 0.55, 0.65)
    M["fde"] = material("fde_polymer", (0.22, 0.16, 0.09), 0.65)
    M["lens"] = material("lens", (0.02, 0.03, 0.04), 0.05, 0.3)
    M["polymer"] = material("polymer", (0.025, 0.025, 0.025), 0.7)
    M["canvas"] = material("canvas", (0.07, 0.07, 0.045), 0.95)
    M["glass"] = material("glass", (0.01, 0.012, 0.015), 0.08, 0.2)
    M["head"] = material("headlight", (1, 1, 1), 0.2, emit=(1, 0.93, 0.8), strength=40)
    M["red"] = material("beacon_red", (1, 0.05, 0.03), 0.3, emit=(1, 0.04, 0.02), strength=60)
    M["green"] = material("nvg_green", (0.2, 1, 0.3), 0.3, emit=(0.15, 1, 0.25), strength=45)
    M["lamp"] = material("floodlamp", (1, 1, 1), 0.2, emit=(0.85, 0.92, 1), strength=70)
    M["bark"] = material("bark", (0.035, 0.025, 0.018), 0.95)
    M["needle"] = material("needles", (0.012, 0.025, 0.014), 0.9)
    M["concrete"] = material("concrete", (0.16, 0.16, 0.155), 0.85)
    M["steel"] = material("steel", (0.12, 0.12, 0.13), 0.4, 0.8)
    M["hazard"] = material("hazard", (0.6, 0.45, 0.02), 0.6)
    M["wire"] = material("wire", (0.2, 0.2, 0.2), 0.35, 0.9)
    M["emblem"] = material("emblem", (0.78, 0.78, 0.76), 0.3, 0.85, emit=(1, 1, 1), strength=0.25)
    M["emblem_plate"] = material("emblem_plate", (0.05, 0.05, 0.055), 0.5, 0.6)
    M["ground"] = ground_material()
    M["road"] = material("road", (0.025, 0.024, 0.022), 0.35)
    M["dust"] = material("dust", (0.8, 0.78, 0.72), 0.5)  # ışık yok: yalnızca huzmelerde görünür
    M["grass"] = grass_material()
    M["contact"] = contact_material()
    M["concrete_floor"] = floor_material()
    M["corrugated"] = corrugated_material()
    M["ceiling"] = material("ceiling", (0.03, 0.032, 0.035), 0.8, 0.3)
    M["rack"] = material("rack", (0.035, 0.04, 0.03), 0.55, 0.6)
    M["lamp_warm"] = material("lamp_warm", (1, 0.85, 0.6), 0.3, emit=(1, 0.78, 0.5), strength=25)
    M["sodium"] = material("sodium_lens", (1, 0.85, 0.6), 0.3, emit=(1, 0.8, 0.5), strength=40)
    M["weed"] = weed_material()
    M["crate"] = material("crate_wood", (0.06, 0.07, 0.04), 0.8)
    M["stencil"] = material("stencil", (0.55, 0.45, 0.08), 0.7)
    M["foam"] = material("foam", (0.015, 0.015, 0.015), 0.95)
    M["rope"] = material("rope", (0.25, 0.2, 0.12), 0.9)


def contact_material():
    """Temas gölgesi: merkezde koyu, kenara doğru yumuşakça şeffaflaşan leke."""
    m = bpy.data.materials.new("contact_shadow")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0, 0, 0, 1)
    p.inputs["Roughness"].default_value = 1.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = (1.0, 1.0, 0.0)
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.12
    mr.inputs["From Max"].default_value = 0.5
    mr.inputs["To Min"].default_value = 0.7
    mr.inputs["To Max"].default_value = 0.0
    mr.interpolation_type = "SMOOTHSTEP"
    nt.links.new(tc.outputs["Generated"], sub.inputs[0])
    nt.links.new(sub.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], p.inputs["Alpha"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m


def floor_material():
    """Depo beton zemini: lekeli, hafif pürüzlü, ince çatlak bump'ı."""
    m = material("concrete_floor", (0.09, 0.09, 0.085), 0.75)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 1.2
    n.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.048, 1)
    ramp.color_ramp.elements[1].color = (0.13, 0.13, 0.125, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.45
    rr.inputs["To Max"].default_value = 0.9
    nt.links.new(n.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], p.inputs["Roughness"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 40
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def corrugated_material():
    """Oluklu metal duvar: dalga dokusuyla oluk bump'ı, koyu boya ve pas lekeleri."""
    m = material("corrugated", (0.05, 0.055, 0.05), 0.5, 0.6)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "X"
    wave.inputs["Scale"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    rust = nt.nodes.new("ShaderNodeTexNoise")
    rust.inputs["Scale"].default_value = 2.5
    rust.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], rust.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[0].color = (0.05, 0.055, 0.05, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.09, 0.05, 0.03, 1)
    nt.links.new(rust.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    return m


def weed_material():
    m = material("weed", (0.035, 0.04, 0.02), 0.7)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (0.06, 0.07, 0.02, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3
    nt.links.new(p.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m.use_backface_culling = False
    return m


def ground_material():
    m = bpy.data.materials.new("forest_floor")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.018, 0.016, 0.011, 1)
    ramp.color_ramp.elements[1].color = (0.03, 0.04, 0.02, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 12
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    p.inputs["Roughness"].default_value = 0.85
    return m


def proxy_rifle():
    b = Builder()
    g, pl = M["gun"], M["polymer"]
    b.box((0.36, 0.06, 0.085), (0.0, 0, 0), g)                      # gövde
    b.box((0.30, 0.058, 0.065), (0.32, 0, 0.005), pl)               # el kundağı
    b.cyl(0.012, 0.012, 0.22, (0.57, 0, 0.01), g, (0, math.pi / 2, 0))   # namlu
    b.cyl(0.018, 0.018, 0.06, (0.69, 0, 0.01), g, (0, math.pi / 2, 0))   # alev gizleyici
    b.box((0.62, 0.022, 0.014), (0.12, 0, 0.05), g)                  # ray
    b.cyl(0.022, 0.022, 0.2, (0.02, 0, 0.09), g, (0, math.pi / 2, 0))    # dürbün
    b.box((0.06, 0.05, 0.06), (0.02, 0, 0.065), g)
    b.box((0.26, 0.04, 0.085), (-0.31, 0, -0.012), pl, (0, 0.08, 0))  # dipçik
    b.box((0.05, 0.045, 0.12), (-0.08, 0, -0.08), pl, (0, -0.35, 0))  # tabanca kabzası
    b.box((0.075, 0.03, 0.21), (0.07, 0, -0.13), pl, (0, 0.22, 0))    # şarjör
    b.cyl(0.016, 0.016, 0.09, (0.33, 0.04, -0.005), g, (0, math.pi / 2, 0))  # fener
    return [b.build("rifle_proxy", bevel=0.004)]


CRATE_L, CRATE_W, CRATE_H = 1.25, 0.52, 0.46  # Poly Haven wooden_military_crate ölçüsü


def proxy_crate(open_=False):
    """Askerî tüfek kasası: zeytin yeşili ahşap, çıtalar, sarı şablon bandı, kilitler."""
    b = Builder()
    L, W, H = CRATE_L, CRATE_W, CRATE_H
    wood, dark = M["crate"], M["olive2"]
    if open_:
        b.box((L, W, 0.03), (0, 0, 0.015), wood)
        for sy in (-1, 1):
            b.box((L, 0.03, H), (0, sy * (W / 2 - 0.015), H / 2), wood)
        for sx in (-1, 1):
            b.box((0.03, W, H), (sx * (L / 2 - 0.015), 0, H / 2), wood)
        b.box((L - 0.06, W - 0.06, 0.05), (0, 0, 0.055), M["foam"])
        b.box((L, W, 0.04), (0, W / 2 + 0.17, H + 0.1), wood, (math.radians(-62), 0, 0))  # kapak
    else:
        b.box((L, W, H), (0, 0, H / 2), wood)
        b.box((L * 0.98, W + 0.004, 0.06), (0, 0, H * 0.62), M["stencil"])
    for sx in (-1, 1):  # kenar çıtaları ve kilitler
        b.box((0.06, W + 0.02, H + 0.02), (sx * (L / 2 - 0.12), 0, H / 2), dark)
        b.box((0.07, 0.02, 0.05), (sx * 0.3, -W / 2 - 0.01, H * 0.8), M["steel"])
    for sx in (-1, 1):  # halat kulplar
        b.box((0.02, 0.16, 0.03), (sx * (L / 2 + 0.01), 0, H * 0.6), M["rope"])
    return [b.build("crate_open_proxy" if open_ else "crate_proxy", bevel=0.006)]


def proxy_ammo():
    b = Builder()
    b.box((0.3, 0.16, 0.2), (0, 0, 0.1), M["olive"])
    b.box((0.31, 0.17, 0.025), (0, 0, 0.19), M["olive2"])
    b.box((0.1, 0.03, 0.02), (0, 0, 0.215), M["steel"])
    b.box((0.2, 0.165, 0.04), (0, 0, 0.11), M["stencil"])
    return [b.build("ammo_proxy", bevel=0.004)]


def rail(b, x0, x1, loc_yz, mat, axis="top"):
    """Picatinny ray: taban + 5.2 mm aralıklı dişler. axis: top / bottom / left / right."""
    y, z = loc_yz
    n = int((x1 - x0) / 0.0104)
    size = {"top": (x1 - x0, 0.021, 0.006), "bottom": (x1 - x0, 0.021, 0.006),
            "left": (x1 - x0, 0.006, 0.021), "right": (x1 - x0, 0.006, 0.021)}[axis]
    b.box(size, ((x0 + x1) / 2, y, z), mat)
    off = {"top": (0, 0, 0.004), "bottom": (0, 0, -0.004), "left": (0, 0.004, 0), "right": (0, -0.004, 0)}[axis]
    tooth = (0.0052, 0.022, 0.004) if axis in ("top", "bottom") else (0.0052, 0.004, 0.022)
    for i in range(n):
        b.box(tooth, (x0 + 0.005 + i * 0.0104, y + off[1], z + off[2]), mat)


def proxy_m4(furniture=None):
    """M4A1 karabina, gerçek ölçülerde (toplam ~0.84 m, 14.5" namlu): +X namlu, +Z yukarı.

    Üst/alt gövde, düz üst pikatinni ray, quad rail el kundağı, A2 arpacık, kuş kafesi alev
    gizleyici, kavisli 30'luk STANAG şarjör, tabanca kabzası, tampon borusu + teleskopik dipçik,
    red dot nişangah, dikey ön tutamak ve taktik fener.
    """
    b = Builder()
    al, st, pl = M["anodized"], M["parkerized"], furniture or M["polymer"]
    # gövde
    b.box((0.225, 0.05, 0.056), (0.005, 0, 0.028), al)                     # üst gövde
    b.box((0.03, 0.052, 0.026), (0.06, 0, 0.014), al)                      # kovan kapağı bölgesi
    b.cyl(0.009, 0.009, 0.025, (-0.03, -0.031, 0.034), al, (0, math.pi / 2, 0), segs=10)  # forward assist
    b.box((0.03, 0.04, 0.008), (-0.12, 0, 0.05), al)                       # kurma kolu
    b.prism([(-0.088, -0.002), (0.092, -0.002), (0.092, -0.03), (0.088, -0.072), (0.02, -0.072),
             (0.016, -0.046), (-0.03, -0.046), (-0.07, -0.042), (-0.088, -0.02)], 0.048, al)  # alt gövde
    b.box((0.05, 0.01, 0.004), (-0.005, 0, -0.066), st)                    # tetik korkuluğu
    b.box((0.004, 0.01, 0.024), (0.018, 0, -0.056), st)
    b.box((0.006, 0.006, 0.022), (-0.002, 0, -0.054), st, (0, 0.3, 0))     # tetik
    rail(b, -0.1, 0.115, (0, 0.06), al)
    # 30'luk STANAG şarjör: öne doğru kavisli
    back = [(0.024 + 0.04 * t * t, -0.07 - 0.172 * t) for t in [i / 8 for i in range(9)]]
    front = [(0.084 + 0.06 * t * t, -0.07 - 0.168 * t) for t in [i / 8 for i in range(9)]]
    b.prism(back + list(reversed(front)), 0.024, st)
    b.prism([(0.058, -0.24), (0.15, -0.233), (0.152, -0.25), (0.06, -0.256)], 0.028, pl)  # taban
    # A2 kabza
    b.prism([(-0.038, -0.044), (-0.072, -0.152), (-0.108, -0.147), (-0.1, -0.12), (-0.08, -0.044)], 0.03, pl)
    # tampon borusu ve SOPMOD tarzı dipçik
    b.cyl(0.0155, 0.0155, 0.2, (-0.19, 0, 0.026), al, (0, math.pi / 2, 0), segs=16)
    b.prism([(-0.255, 0.05), (-0.41, 0.058), (-0.43, 0.06), (-0.432, -0.072), (-0.412, -0.078),
             (-0.36, -0.03), (-0.3, -0.004), (-0.255, 0.002)], 0.044, pl)
    b.box((0.016, 0.046, 0.14), (-0.438, 0, -0.006), M["tire"])            # dipçik pedi
    b.prism([(-0.27, 0.05), (-0.4, 0.056), (-0.4, 0.076), (-0.3, 0.07)], 0.05, pl)  # yanak desteği
    # el kundağı (quad rail) ve namlu
    b.box((0.19, 0.05, 0.05), (0.215, 0, 0.026), al)
    for ax, yz in (("top", (0, 0.055)), ("bottom", (0, -0.003)), ("left", (0.029, 0.026)),
                   ("right", (-0.029, 0.026))):
        rail(b, 0.125, 0.305, yz, al, ax)
    b.cyl(0.0095, 0.0095, 0.16, (0.38, 0, 0.026), st, (0, math.pi / 2, 0), segs=14)
    b.prism([(0.312, 0.034), (0.35, 0.034), (0.338, 0.102), (0.326, 0.102)], 0.02, st)  # A çerçeveli arpacık
    b.box((0.003, 0.003, 0.012), (0.332, 0, 0.11), st)
    b.cyl(0.011, 0.011, 0.045, (0.475, 0, 0.026), st, (0, math.pi / 2, 0), segs=12)  # alev gizleyici
    # red dot + montaj
    b.box((0.05, 0.03, 0.02), (-0.015, 0, 0.075), al)
    b.cyl(0.021, 0.021, 0.11, (-0.015, 0, 0.105), al, (0, math.pi / 2, 0), segs=20)
    b.cyl(0.024, 0.024, 0.02, (0.045, 0, 0.105), al, (0, math.pi / 2, 0), segs=20)
    b.cyl(0.019, 0.019, 0.004, (0.056, 0, 0.105), M["lens"], (0, math.pi / 2, 0), segs=20)
    b.box((0.02, 0.02, 0.012), (-0.015, -0.025, 0.105), al)                 # ayar düğmesi
    # dikey tutamak ve fener
    b.cyl(0.014, 0.012, 0.095, (0.245, 0, -0.052), pl, segs=14)
    b.cyl(0.012, 0.012, 0.085, (0.26, -0.036, 0.026), al, (0, math.pi / 2, 0), segs=14)
    b.cyl(0.0125, 0.0125, 0.004, (0.304, -0.036, 0.026), M["lens"], (0, math.pi / 2, 0), segs=14)
    o = b.build("m4a1", bevel=0.0015)
    # kökeni alt-orta noktaya taşı (dış modellerle aynı kural)
    xs = [v.co.x for v in o.data.vertices]
    zs = [v.co.z for v in o.data.vertices]
    o.data.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, 0, -min(zs))))
    return [o]


def proxy_apc():
    """Detaylı prosedürel 8x8 zırhlı araç (blender/vehicles.py) + arka kapıda iki bidon."""
    parts = vehicles.apc(FONT)
    body = parts[0]
    for pt in [o for o in body.children if o.get("jerrycan")]:
        place("jerrycan", (0, 0, 0), math.pi / 2, parent=pt)
    return parts


def proxy_truck():
    return vehicles.truck(FONT)


def proxy_pine():
    b = Builder()
    b.cyl(0.035, 0.02, 1.0, (0, 0, 0.5), M["bark"], segs=8)
    tiers = 11
    for i in range(tiers):
        u = i / (tiers - 1)
        r = (0.24 * (1 - u) + 0.04) * (1.0 if i % 2 else 0.85)
        b.cyl(r, r * 0.25, 0.13, (0, 0, 0.2 + u * 0.74), M["needle"], (0, 0, i * 0.9), segs=14)
    o = b.build("pine_proxy")
    d = o.modifiers.new("organic", "DISPLACE")
    tex = bpy.data.textures.new("pine_noise", "CLOUDS")
    tex.noise_scale = 0.05
    d.texture, d.strength = tex, 0.03
    return [o]


PROXIES = {
    "rifle": proxy_m4,
    "rifle_fde": lambda: proxy_m4(M["fde"]),
    "crate": proxy_crate,
    "crate_open": lambda: proxy_crate(open_=True),
    "ammo": proxy_ammo,
}


def impostor_material(img_path, name):
    """Hafif impostor malzemesi: doku rengi + alfa (işlemciyle çalışan EEVEE'de pahalı katmanlar yok)."""
    img = bpy.data.images.load(str(img_path), check_existing=True)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], p.inputs["Alpha"])
    p.inputs["Roughness"].default_value = 0.85
    m.use_backface_culling = False
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    return m


def impostor_tree():
    """blender/bake_trees.py'nin pişirdiği göknarlar: her çeşit üç çapraz düzlem (yükseklik 1)."""
    d = ASSETS / "polyhaven" / "fir_tree_01"
    meta_p = d / "impostor.json"
    if not meta_p.exists():
        return None
    meshes = []
    for v, tree in enumerate(json.loads(meta_p.read_text())["trees"]):
        aspect = tree["width"] / tree["height"]
        me = bpy.data.meshes.new(f"fir_impostor_{v}")
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        for k, a in enumerate(tree["angles"]):
            me.materials.append(impostor_material(d / f"impostor_{v}_{k}.png", f"fir_{v}_{k}"))
            ang = math.radians(a)
            right = Vector((math.cos(ang), math.sin(ang), 0))  # pişirme kamerasının sağ ekseni
            hw = aspect * 1.02 / 2
            vs = [bm.verts.new(right * x + Vector((0, 0, z))) for x, z in
                  ((-hw, -0.01), (hw, -0.01), (hw, 1.01), (-hw, 1.01))]
            f = bm.faces.new(vs)
            f.material_index = k
            for loop, (u, w) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                loop[uv].uv = (u, w)
        bm.to_mesh(me)
        bm.free()
        meshes.append(me)
    print(f"[model] pine: {len(meshes)} göknar çeşidi (fir_tree_01 impostor)")
    return meshes


def realize_tree_template(root):
    """Ağaç root'unu tek mesh'e indirger (binlerce bağlantılı kopya için)."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    bm = bmesh.new()
    mats = []
    for o in meshes:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(deps))
        me.transform(root.matrix_world.inverted() @ o.matrix_world)
        offset = len(mats)
        mats += list(me.materials)
        for p in me.polygons:
            p.material_index += offset
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new("pine")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for o in list(root.children_recursive) + [root]:
        bpy.data.objects.remove(o)
    return me


# --------------------------------------------------------------------------- dünya parçaları

def ground(center, size=180, mat=None):
    me = bpy.data.meshes.new("ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=90, y_segments=90, size=size / 2)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat or M["ground"])
    o = link(bpy.data.objects.new("ground", me))
    o.location = center + Vector((0, 0, -0.28))
    d = o.modifiers.new("terrain", "DISPLACE")
    tex = bpy.data.textures.new("terrain", "CLOUDS")
    tex.noise_scale = 6
    d.texture, d.strength, d.mid_level = tex, 0.5, 0.5
    return o


def road(center, length, width, along_x=True):
    b = Builder()
    size = (length, width, 0.05) if along_x else (width, length, 0.05)
    b.box(size, (0, 0, -0.025), M["road"])  # üst yüzey tam z=0: tekerlekler/bariyerler buna oturur
    o = b.build("road")
    o.location = center
    return o


def forest(pine_mesh, center, half, count, keep_out, seed, h=(9, 17)):
    """center etrafında half=(hx,hy) alanına ağaç serper; keep_out: [(x0,x1,y0,y1)] yerel."""
    meshes = pine_mesh if isinstance(pine_mesh, list) else [pine_mesh]
    rng = random.Random(seed)
    placed = 0
    tries = 0
    while placed < count and tries < count * 20:
        tries += 1
        x = rng.uniform(-half[0], half[0])
        y = rng.uniform(-half[1], half[1])
        if any(x0 < x < x1 and y0 < y < y1 for x0, x1, y0, y1 in keep_out):
            continue
        t = link(bpy.data.objects.new("pine", rng.choice(meshes)))
        t.visible_shadow = False  # alfa maskeli ağaç gölgeleri işlemcide kareyi ~10 kat yavaşlatıyor
        s = rng.uniform(*h)
        t.location = center + Vector((x, y, -0.2))
        t.scale = (s * rng.uniform(0.8, 1.1), s * rng.uniform(0.8, 1.1), s)
        t.rotation_euler = (rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(0, 6.28))
        placed += 1


def fog(center, size, density=0.05, ground_boost=3.0, color=(0.75, 0.82, 1.0)):
    """Yere yakın yoğunlaşan sis kutusu."""
    b = Builder()
    m = bpy.data.materials.new("fog")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*color, 1)
    vol.inputs["Anisotropy"].default_value = 0.45
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rng_ = nt.nodes.new("ShaderNodeMapRange")
    rng_.inputs["From Min"].default_value = 0
    rng_.inputs["From Max"].default_value = 7
    rng_.inputs["To Min"].default_value = density * ground_boost
    rng_.inputs["To Max"].default_value = density
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.08
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.4
    ramp.inputs["To Max"].default_value = 1.4
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], rng_.inputs["Value"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(rng_.outputs["Result"], mul.inputs[0])
    nt.links.new(ramp.outputs["Result"], mul.inputs[1])
    nt.links.new(mul.outputs["Value"], vol.inputs["Density"])
    nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    b.box(size, (0, 0, size[2] / 2 - 0.5), m)
    o = b.build("fog")
    o.location = center
    return o


def emblem(loc, radius, depth=0.09, parent=None):
    """Tesis kapısındaki SCP amblemi: scp_logo'daki aynı vektör (120° aralıklı üç halka parçası,
    merkeze bakan üç eş ok, iç halka) XZ düzleminde ekstrüde edilir; ön yüz -Y'ye bakar."""
    shp = scp_logo.shapes()
    b = Builder()
    for poly in shp["polygons"]:
        b.prism([(x * radius, y * radius) for x, y in poly], depth, M["emblem"])
    r_in, r_out = shp["inner_ring"]
    b.ring(r_in * radius, r_out * radius, depth, M["emblem"])
    b.box((2.2 * radius, 0.05, 2.2 * radius), (0, depth / 2 + 0.03, 0), M["emblem_plate"])  # arka plaka
    o = b.build("emblem", bevel=0.004)
    o.location = loc
    if parent:
        o.parent = parent
    return o


# --------------------------------------------------------------------------- araç kurulumları

def rig_vehicle(root, power=1800, lights_on=True):
    """Blok modeldeki işaretli boşluklara ışık bağlar (dış modelde kendi konumlarını kullanır)."""
    heads = [o for o in root.children_recursive if o.get("headlight")]
    if root.get("external"):
        L = ASSET_SPECS[root.name.split(".")[0]].get("length", 7)
        heads = [empty("headlight", (L / 2 + 0.05, y, 1.3), root) for y in (-0.9, 0.9)]
    lights = []
    if lights_on:
        for h in heads:
            s = spot("head_beam", (0, 0, 0), None, power, (1, 0.93, 0.82), 55, 0.5, 70, parent=h)
            s.rotation_euler = (0, math.radians(-86), 0)  # -Z -> +X, hafif aşağı
            lights.append(s)
    return lights


def beacon_lights(root, f0, f1, rps=1.6):
    b = next((o for o in root.children_recursive if o.get("beacon")), None)
    if b is None:
        b = empty("beacon", (-1.8, -0.8, 2.3), root)
    spin = empty("beacon_spin", (0, 0, 0.12), b)
    for k in (0, 1):
        s = spot("beacon_beam", (0, 0, 0), None, 900, (1, 0.05, 0.02), 35, 0.6, 45, parent=spin)
        s.rotation_euler = (math.radians(85), 0, k * math.pi)
    point("beacon_glow", (0, 0, 0.15), 60, (1, 0.05, 0.02), 0.1, 25, parent=b)
    spin.rotation_euler = (0, 0, 0)
    spin.keyframe_insert("rotation_euler", index=2, frame=f0)
    spin.rotation_euler = (0, 0, 2 * math.pi * rps * (f1 - f0) / FPS)
    spin.keyframe_insert("rotation_euler", index=2, frame=f1)
    set_interp(spin, "LINEAR")


def drive(root, path, wheel_r=0.55):
    """path: [(kare, x)] doğrusal; tekerlekler kat edilen yola göre döner, gövde hafif sallanır."""
    y, z = root.location.y, root.location.z
    for f, x in path:
        key(root, f, loc=(x, y, z), interp="LINEAR")
    wheels = [o for o in root.children_recursive if "wheel" in o]
    (f0, x0), (f1, x1) = path[0], path[-1]
    for w in wheels:
        w.rotation_euler = (0, 0, 0)
        w.keyframe_insert("rotation_euler", index=1, frame=f0)
        w.rotation_euler = (0, (x1 - x0) / float(w.get("wheel", wheel_r)), 0)
        w.keyframe_insert("rotation_euler", index=1, frame=f1)
        set_interp(w, "LINEAR")
    body = next((o for o in root.children_recursive if o.get("body")), None) or next(
        (o for o in root.children if o.type == "MESH" or o.name.endswith("_pivot")), None)
    if body is not None:  # süspansiyon: yalpa, yunuslama, zıplama
        fc_noise(body, "rotation_euler", 0, strength=0.008, scale=9)
        fc_noise(body, "rotation_euler", 1, strength=0.006, scale=12)
        fc_noise(body, "location", 2, strength=0.02, scale=6)
    for ant in [o for o in root.children_recursive if o.get("antenna")]:  # antenler sallanır
        fc_noise(ant, "rotation_euler", 1, strength=0.12, scale=5)
        fc_noise(ant, "rotation_euler", 0, strength=0.05, scale=4)


def fc_noise(obj, path, index, strength, scale, phase=None):
    obj.keyframe_insert(path, index=index, frame=F_START)
    fc = obj.animation_data.action.fcurves.find(path, index=index)
    mod = fc.modifiers.new("NOISE")
    mod.strength, mod.scale = strength, scale
    mod.phase = phase if phase is not None else random.uniform(0, 100)
    return mod


def camera(name, lens, loc, target, fstop=4.0, focus=None):
    d = bpy.data.cameras.new(name)
    d.lens, d.sensor_width = lens, 36
    d.clip_start = 0.05
    d.dof.use_dof = True
    d.dof.aperture_fstop = fstop
    if focus is not None:
        d.dof.focus_object = focus
    o = link(bpy.data.objects.new(name, d))
    o.location = loc
    aim(o, target)
    return o


def handheld(cam, amount=1.0):
    for i in range(3):
        fc_noise(cam, "rotation_euler", i, strength=0.0035 * amount, scale=22, phase=i * 13.7)


# --------------------------------------------------------------------------- planlar

def place(name, loc, rz=0.0, parent=None, rot=None, settle=False):
    """Modeli yerleştirir; settle=True ise sahne kurulunca altındaki yüzeye oturtulur (SETTLE)."""
    o = asset(name, PROXIES.get(name))
    if parent is not None:
        o.parent = parent
    o.location = loc
    o.rotation_euler = rot if rot is not None else (0, 0, rz)
    if settle:
        SETTLE.append(o)
    return o


def crate_stack(name, loc, layout, rz=0.0):
    """layout: [(model, x, y, z, rz)] yerel; kasa yığınını bir empty altında kurar."""
    root = empty(name, loc)
    root.rotation_euler = (0, 0, rz)
    for model, x, y, z, r in layout:
        place(model, (x, y, z), r, parent=root, settle=True)
    return root


def span(name):
    """Planın render aralığı (Blender kareleri). Geçişler sert kesme / siyaha karartma: taşma yok."""
    f0, f1, _ = SHOTS[name]
    return f0, f1


def smoothstep(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def focus_track(cam, r0, r1, fn):
    """Odak mesafesini kare kare anahtarlar (rack focus). fn(f) -> metre."""
    d = cam.data.dof
    d.focus_object = None
    for f in range(r0, r1 + 1):
        d.focus_distance = max(0.2, fn(f))
        cam.data.keyframe_insert("dof.focus_distance", frame=f)


def dust(name, center, size, count, seed, r0, r1, drift=(0.04, 0.02, -0.01), radius=(0.002, 0.005)):
    """Işık huzmelerinde görünen toz zerreleri (kendi ışığı yok)."""
    rng = random.Random(seed)
    bm = bmesh.new()
    for _ in range(count):
        p = Vector((rng.uniform(-0.5, 0.5) * size[0], rng.uniform(-0.5, 0.5) * size[1],
                    rng.uniform(-0.5, 0.5) * size[2]))
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rng.uniform(*radius),
                                   matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["dust"])
    o = link(bpy.data.objects.new(name, me))
    o.visible_shadow = False
    c = Vector(center)
    dt = (r1 - r0) / FPS
    key(o, r0, loc=c, rot=(0, 0, 0), interp="LINEAR")
    key(o, r1, loc=c + Vector(drift) * dt, rot=(0, 0, 0.08 * dt), interp="LINEAR")
    return o


# --------------------------------------------------------------------------- 3D çimen

def grass_material():
    """Yaprak başına renk (köşe rengi 'col') + arkadan süzülen ışık için yarı saydamlık."""
    m = bpy.data.materials.new("grass")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "col"
    nt.links.new(at.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.6
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(at.outputs["Color"], tr.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3
    nt.links.new(p.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m.use_backface_culling = False
    return m


GRASS_COLORS = [(0.08, 0.11, 0.035), (0.055, 0.085, 0.03), (0.12, 0.12, 0.045), (0.17, 0.145, 0.07),
                (0.1, 0.08, 0.045), (0.07, 0.1, 0.045)]


def grass(name, loc, count, seed, r0, r1, height=(0.25, 0.85), spread=0.4, wind=(0.6, 0.25, 0)):
    """3D çimen kümesi: her yaprak V kesitli (katlanmış) şerit; boy, eğim ve renk yaprak başına
    değişir. Rüzgâr: uçlara ağırlıklı vertex group + hareketli dokulu iki Displace modifier'ı,
    böylece her yaprak kendi fazında sallanır, kökler yerinde kalır."""
    rng = random.Random(seed)
    sx, sy = spread if isinstance(spread, tuple) else (spread, spread * 0.7)
    bm = bmesh.new()
    col = bm.loops.layers.color.new("col")
    dl = bm.verts.layers.deform.verify()
    for _ in range(count):
        base = Vector((rng.gauss(0, sx), rng.gauss(0, sy), 0))
        h = rng.uniform(*height) * (0.5 if rng.random() < 0.25 else 1.0)
        ang = rng.uniform(0, 2 * math.pi)
        lean_dir = Vector((math.cos(ang), math.sin(ang), 0))
        lean = lean_dir * h * rng.uniform(0.08, 0.5)
        side = Vector((-lean_dir.y, lean_dir.x, 0))
        w0 = rng.uniform(0.004, 0.011)
        c = Vector(rng.choice(GRASS_COLORS)) * rng.uniform(0.8, 1.25)
        tip_dry = rng.random() < 0.35
        prev = None
        for k in range(6):
            t = k / 5
            ctr = base + lean * (t * t) + Vector((0, 0, h * t))
            w = w0 * (1 - 0.92 * t)
            fold = lean_dir * w * 0.7  # V kesit: kenarlar orta damardan öne katlanır
            trio = [bm.verts.new(ctr - side * w + fold), bm.verts.new(ctr), bm.verts.new(ctr + side * w + fold)]
            for v in trio:
                v[dl][0] = t * t
            if prev:
                for a, b2 in ((0, 1), (1, 2)):
                    f = bm.faces.new((prev[a], prev[b2], trio[b2], trio[a]))
                    for lp in f.loops:
                        tt = (lp.vert.co.z - base.z) / max(h, 1e-3)
                        cc = c.lerp(Vector((0.21, 0.17, 0.08)), tt * 0.8) if tip_dry else c * (0.85 + 0.3 * tt)
                        lp[col] = (*cc, 1.0)
            prev = trio
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["grass"])
    o = link(bpy.data.objects.new(name, me))
    o.location = loc
    o.vertex_groups.new(name="sway")
    wind_e = empty(name + "_wind", loc)
    key(wind_e, r0, loc=loc, interp="LINEAR")
    key(wind_e, r1, loc=Vector(loc) + Vector(wind) * (r1 - r0) / FPS, interp="LINEAR")
    for axis, sc, st in (("X", 0.7, 0.07), ("Y", 1.1, 0.045)):
        tex = bpy.data.textures.new(f"{name}_wind_{axis}", "CLOUDS")
        tex.noise_scale = sc
        d = o.modifiers.new(f"wind_{axis}", "DISPLACE")
        d.texture, d.direction, d.strength, d.mid_level = tex, axis, st, 0.5
        d.texture_coords, d.texture_coords_object, d.vertex_group = "OBJECT", wind_e, "sway"
    o.visible_shadow = False
    return o


# --------------------------------------------------------------------------- yerleşim kontrolleri

SETTLE = []  # zemine/altındaki nesneye oturtulacak kök nesneler (place(..., settle=True))


def world_bbox(o):
    objs = [o] + list(o.children_recursive)
    pts = [m.matrix_world @ Vector(c) for m in objs if m.type == "MESH" and not m.hide_render for c in m.bound_box]
    if not pts:
        return None
    return Vector([min(q[i] for q in pts) for i in range(3)]), Vector([max(q[i] for q in pts) for i in range(3)])


def support_z(o, lo, hi, probe=0.06):
    """Nesnenin altındaki yüzeyin yüksekliği: nesne gizlenip tabanının 3x3 noktasından aşağı ışın."""
    hidden = [m for m in [o] + list(o.children_recursive) if m.type == "MESH" and not m.hide_viewport]
    for m in hidden:
        m.hide_viewport = True
    vl = bpy.context.view_layer
    vl.update()
    dg = bpy.context.evaluated_depsgraph_get()
    best = None
    for fx in (0.2, 0.5, 0.8):
        for fy in (0.2, 0.5, 0.8):
            orig = Vector((lo.x + (hi.x - lo.x) * fx, lo.y + (hi.y - lo.y) * fy, lo.z + probe))
            hit, loc, *_ = bpy.context.scene.ray_cast(dg, orig, Vector((0, 0, -1)), distance=5)
            if hit:
                best = loc.z if best is None else max(best, loc.z)
    for m in hidden:
        m.hide_viewport = False
    vl.update()
    return best


def settle(objs, tol=0.002):
    """Her nesneyi (alttan üste) altındaki yüzeye oturtur: havada ya da gömülü kalmasın."""
    for o in sorted(objs, key=lambda o: world_bbox(o)[0].z if world_bbox(o) else 0):
        bb = world_bbox(o)
        if bb is None:
            continue
        z = support_z(o, *bb)
        if z is not None and abs(bb[0].z - z) > tol:
            mw = o.matrix_world.copy()
            mw.translation.z -= bb[0].z - z
            o.matrix_world = mw
            bpy.context.view_layer.update()


def check_grounded(objs, tol=0.005):
    """Doğrulama: her nesnenin alt sınırı altındaki yüzeyle aynı yükseklikte mi? (rapor + liste)"""
    bad = []
    for o in objs:
        bb = world_bbox(o)
        if bb is None:
            continue
        z = support_z(o, *bb)
        gap = None if z is None else bb[0].z - z
        if gap is None or abs(gap) > tol:
            bad.append((o.name, gap))
    print(f"[kontrol] zemin: {len(objs)} nesne, {len(bad)} sorunlu {bad[:8]}", flush=True)
    return bad


def contact_shadow(o, strength=0.6):
    """Temas gölgesi: nesnenin altına yumuşak kenarlı koyu bir leke (ambient occlusion yerine)."""
    bb = world_bbox(o)
    if bb is None:
        return None
    lo, hi = bb
    c = (lo + hi) / 2
    b = Builder()
    b.box(((hi.x - lo.x) * 1.35 + 0.12, (hi.y - lo.y) * 1.35 + 0.12, 0.001), (0, 0, 0), M["contact"])
    d = b.build("contact_shadow")
    d.location = (c.x, c.y, lo.z + 0.0015)
    d.visible_shadow = False
    return d


def camera_clear(cam, frames, skip=("fog", "ground", "floor", "road", "pine", "dust", "contact", "grass",
                                   "warehouse")):
    """Kamera hiçbir objenin sınır kutusunun içine girmiyor mu? (kare kare)"""
    scene = bpy.context.scene
    boxes = []
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render and not o.name.startswith(skip):
            bb = world_bbox(o)
            if bb:
                boxes.append((o.name, bb))
    hits = set()
    for f in frames:
        scene.frame_set(f)
        p = cam.matrix_world.translation
        for name, (lo, hi) in boxes:
            if all(lo[i] - 0.05 < p[i] < hi[i] + 0.05 for i in range(3)):
                hits.add((f, name))
    print(f"[kontrol] kamera-obje: {len(hits)} çakışma {sorted(hits)[:6]}", flush=True)
    return hits


def frame_coverage(cam, objs, frames):
    """Nesnelerin ekranda kapladığı alan oranı (izdüşüm sınır kutusu, kadraja kırpılmış)."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    worst = 0.0
    for f in frames:
        scene.frame_set(f)
        pts = []
        for o in objs:
            for m in [o] + list(o.children_recursive):
                if m.type == "MESH":
                    pts += [world_to_camera_view(scene, cam, m.matrix_world @ Vector(c)) for c in m.bound_box]
        xs = [min(max(q.x, 0), 1) for q in pts if q.z > 0]
        ys = [min(max(q.y, 0), 1) for q in pts if q.z > 0]
        if xs:
            worst = max(worst, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    return worst


# --------------------------------------------------------------------------- yapılar

def street_lamp(base, arm_dir, height=6.4, power=6500, target=None, color=(1.0, 0.86, 0.62), head_visible=True):
    """Direkli sokak lambası: ışık kaynağı görünür bir gövdeye bağlı (havada ışık yok)."""
    arm = Vector(arm_dir).normalized()
    b = Builder()
    b.cyl(0.11, 0.08, 0.25, (0, 0, 0.125), M["steel"], segs=12)
    b.cyl(0.075, 0.055, height, (0, 0, height / 2), M["steel"], segs=12)
    tip = arm * 1.5 + Vector((0, 0, height))
    b.box((1.6, 0.07, 0.07), (arm.x * 0.8, arm.y * 0.8, height - 0.05), M["steel"],
          (0, 0, math.atan2(arm.y, arm.x)))
    b.box((0.55, 0.26, 0.12), (tip.x, tip.y, tip.z - 0.08), M["steel"], (0, 0, math.atan2(arm.y, arm.x)))
    b.box((0.44, 0.18, 0.02), (tip.x, tip.y, tip.z - 0.15), M["sodium"], (0, 0, math.atan2(arm.y, arm.x)))
    o = b.build("street_lamp")
    o.location = base
    head = Vector(base) + Vector((tip.x, tip.y, tip.z - 0.17))
    spot("street_light", head, target or (head - Vector((0, 0, 5))), power, color, 95, 0.9, 30, shadow=True)
    return o


def warehouse(O):
    """Depo binası: düz beton zemin, oluklu metal duvarlar, büyük kapı, tavan ve çelik kirişler."""
    b = Builder()
    b.box((18, 18, 0.2), (0, 0, -0.1), M["concrete_floor"])
    W, D, H, door_w, door_h = 8.0, 8.0, 5.0, 2.8, 3.8
    t = 0.25
    Hw = H + 0.2  # duvarlar tavan levhasının içine kadar uzanır: birleşim yerinden ışık sızmaz
    b.box((W - door_w, t, Hw), (-(W + door_w) / 2, D, Hw / 2), M["corrugated"])
    b.box((W - door_w, t, Hw), ((W + door_w) / 2, D, Hw / 2), M["corrugated"])
    b.box((2 * door_w, t, Hw - door_h), (0, D, (Hw + door_h) / 2), M["corrugated"])
    for sx in (-1, 1):
        b.box((t, 2 * D + t, Hw), (sx * W, 0, Hw / 2), M["corrugated"])
        b.box((0.3, 0.32, door_h), (sx * (door_w + 0.15), D - 0.1, door_h / 2), M["steel"])  # kapı kasası
    b.box((2 * W, 2 * D, 0.2), (0, 0, H + 0.1), M["ceiling"])
    for y in (-3.6, -0.9, 2.2, 5.2):  # I-kesitli tavan kirişleri
        b.box((2 * W, 0.22, 0.03), (0, y, 4.42), M["steel"])
        b.box((2 * W, 0.03, 0.36), (0, y, 4.6), M["steel"])
        b.box((2 * W, 0.22, 0.03), (0, y, 4.78), M["steel"])
    for sx in (-1, 1):  # duvar lambaları (kafesli, görünür kaynak)
        b.box((0.12, 0.22, 0.3), (sx * (W - 0.18), 4.0, 3.0), M["steel"])
        b.box((0.03, 0.16, 0.2), (sx * (W - 0.25), 4.0, 3.0), M["lamp_warm"])
    shell = b.build("warehouse", bevel=0.0)
    shell.location = O
    for sx in (-1, 1):
        point("wall_lamp", O + Vector((sx * (W - 0.4), 4.0, 3.0)), 60, (1, 0.8, 0.55), 0.08, 9)
    return shell, 4.42  # kiriş alt yüzü


def gun_rack(loc, rz=0.0):
    """Silah rafı: taban kızağı, dipçik yuvası, üstte yuvalı ray; 4 M4A1 farklı açılarla yaslı."""
    root = empty("gun_rack", loc)
    root.rotation_euler = (0, 0, rz)
    b = Builder()
    b.box((1.5, 0.42, 0.06), (0, 0, 0.03), M["rack"])
    b.box((1.5, 0.05, 0.1), (0, -0.16, 0.11), M["rack"])
    for sx in (-1, 1):
        b.box((0.06, 0.06, 0.7), (sx * 0.72, 0.15, 0.38), M["rack"])
        b.box((0.06, 0.36, 0.06), (sx * 0.72, 0.0, 0.03), M["rack"])
    b.box((1.5, 0.05, 0.05), (0, 0.15, 0.68), M["rack"])
    for x in (-0.48, -0.16, 0.16, 0.48):
        b.box((0.012, 0.05, 0.05), (x - 0.045, 0.12, 0.715), M["rack"])
        b.box((0.012, 0.05, 0.05), (x + 0.045, 0.12, 0.715), M["rack"])
    rk = b.build("rack", bevel=0.004)
    rk.parent = root
    rifles = []
    for (x, lean, yaw, roll, name) in ((-0.48, 11, -6, -2, "rifle"), (-0.16, 14, 4, 3, "rifle_fde"),
                                       (0.16, 12, -3, -4, "rifle"), (0.48, 13, 7, 2, "rifle")):
        r = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(-lean), 3, "X")
             @ Matrix.Rotation(math.radians(roll), 3, "Y") @ Matrix.Rotation(math.radians(-88), 3, "Y"))
        rifles.append(place(name, (x, -0.04, 0.5), rot=r.to_euler(), parent=root, settle=True))
    return root, rk, rifles


def shot_secure(pine):
    """Depo: tavanlı, duvarlı bir depoda silah kasaları ve silah rafı; kamera ilk kareden sahneyi
    gösterir, yavaşça yana kayar. Ön plandaki küçük kasa yığını kadrajın en fazla %20'si."""
    f0, f1, O = SHOTS["secure"]
    r0, r1 = span("secure")
    events = {}
    shell, beam_z = warehouse(O)
    fog(O + Vector((0, 12, 0)), (40, 52, 14), density=0.007, ground_boost=1.6)
    forest(pine, O + Vector((0, 30, 0)), (40, 16), 120, [], seed=1)  # kapıdan görünen orman
    H, OH = CRATE_H, 0.27
    crate_stack("pile_left", O + Vector((-3.0, 1.3, 0)), [
        ("crate", 0, 0, 0, 0), ("crate", 0, 0.56, 0, 0.02), ("crate", 0.05, 0.28, H, -0.04),
        ("crate_olive", 0.1, 0.3, 2 * H, 0.06), ("ammo", 0.85, -0.15, 0, 0.3), ("ammo", 0.83, -0.12, 0.18, 0.1),
        ("jerrycan", -0.95, -0.25, 0, 1.45), ("jerrycan", -1.0, 0.25, 0, 1.62)], rz=0.12)
    crate_stack("pile_right", O + Vector((2.85, 1.7, 0)), [
        ("crate", 0, 0, 0, 0), ("crate", 0, 0.56, 0, 0), ("crate_olive", 0.1, 0.25, H, 0.04),
        ("crate_olive", 0.0, 0.3, H + OH, -0.05), ("generator", -1.15, -0.3, 0, 0.5),
        ("ammo", 0.95, -0.4, 0, -0.2), ("ammo", 0.95, -0.1, 0, 0.1)], rz=-0.18)
    crate_stack("pile_back", O + Vector((0.4, 4.6, 0)), [
        ("crate", x, y, z, 0) for x in (-1.35, 0, 1.35) for y in (0, 0.56) for z in (0, H)])
    place("crate_open", O + Vector((0.2, -0.7, 0)), 0.05, settle=True)
    rack, rack_mesh, rifles = gun_rack(O + Vector((-1.55, -0.95, 0)), 0.18)
    SETTLE.append(rack)
    ammo_c = place("crate_olive_open", O + Vector((1.6, -1.15, 0)), -0.3, settle=True)
    for dx in (-0.2, 0.08):
        place("ammo", (dx, 0.0, 0.06), math.pi / 2, parent=ammo_c, settle=True)
    # kasanın üstünde yan yatırılmış bir M4 (yatay, kasaya oturur)
    place("rifle", O + Vector((2.8, 1.95, 1.3)), rot=(math.radians(90), 0, -0.15), settle=True)
    # lambalar: kirişlere zincirle asılı (modelin zinciri kirişin alt yüzüne değer); her ışığın
    # kaynağı görünür bir armatür. Ana lamba ve raf lambası gölgeli.
    lamp_h = ASSET_SPECS["hang_lamp"]["height"]
    for i, (x, y, tx, ty, pw, sh) in enumerate(((1.25, -0.9, 0.2, -0.4, 3800, True),
                                                 (-1.55, -0.9, -1.55, -0.95, 2600, True),
                                                 (2.7, 2.2, 2.5, 1.6, 2200, False),
                                                 (-2.9, 2.2, -3.0, 1.4, 2200, False))):
        lamp = O + Vector((x, y, beam_z - lamp_h))
        place("hang_lamp", lamp)
        spot(f"work_light_{i}", lamp + Vector((0, 0, 0.02)), O + Vector((tx, ty, 0)), pw, (1, 0.86, 0.66), 110,
             0.8, 25, shadow=sh)
    area("ceiling_fill", O + Vector((0, 0.5, 4.3)), O + Vector((0, 0.5, 0)), 420, 7.0, (0.85, 0.88, 1.0))
    # kapıdan giren projektör: kaynak duvarın üstünde, kadraj dışında; huzme sisi kapıdan delerek girer
    spot("door_light", O + Vector((1.2, 14, 7.5)), O + Vector((0, -3, -5.5)), 26000, (0.78, 0.86, 1.0), 38,
         0.85, 40, shadow=True)
    spot("fill", O + Vector((0.5, -7.5, 3.2)), O + Vector((0, 0, 0.8)), 220, (0.8, 0.85, 1.0), 70, 0.9, 16)
    # ön plan: kameraya yakın küçük kasa yığını (sol kenar), arkadan kenar ışığı
    fg = crate_stack("pile_fg", O + Vector((-1.95, -4.3, 0)), [
        ("crate", 0, 0, 0, math.pi / 2 + 0.05), ("crate", 0.02, 0.0, H, math.pi / 2 - 0.04),
        ("crate", -0.01, 0.02, 2 * H, math.pi / 2 + 0.03), ("crate_olive", 0.02, 0.05, 3 * H, math.pi / 2 - 0.1)])
    spot("fg_rim", O + Vector((-3.3, -2.4, 2.8)), O + Vector((-1.95, -4.3, 1.0)), 900, (0.85, 0.9, 1.0), 40,
         0.6, 8)
    settle(SETTLE)
    settle(SETTLE)  # ikinci tur: üst üste duran nesneler alttakiler oturduktan sonra yeniden hizalanır
    for o in SETTLE:
        if o.parent is None or o.parent.name.startswith(("pile_", "gun_rack")):
            bb = world_bbox(o)
            if bb and bb[0].z < 0.01:  # yalnızca zemine değenlere temas gölgesi
                contact_shadow(o)
    events["grounded_bad"] = len(check_grounded(SETTLE))

    c0, c1 = O + Vector((-0.75, -6.6, 1.48)), O + Vector((0.45, -5.95, 1.52))
    cam = camera("cam_secure", 32, c0, c0 + Vector((0, 6, 0.2)), 2.8)
    for f in range(r0, r1 + 1):
        u = (f - f0) / (f1 - f0)
        e = 0.4 * smoothstep(u) + 0.6 * u
        p = c0.lerp(c1, e)
        key(cam, f, loc=p, rot=look_rot(p, O + Vector((p.x * 0.3, 1.0, 1.62))), interp="LINEAR")
    handheld(cam, 0.5)
    target = O + Vector((0.2, -0.7, 0.6))
    focus_track(cam, r0, r1, lambda f: (target - c0.lerp(c1, 0.4 * smoothstep((f - f0) / (f1 - f0))
                                                         + 0.6 * (f - f0) / (f1 - f0))).length)
    events["fg_coverage"] = round(frame_coverage(cam, [fg], range(r0, r1 + 1, 12)), 3)
    print(f"[kontrol] ön plan kaplama: {events['fg_coverage']:.0%}", flush=True)
    events["camera_hits"] = len(camera_clear(cam, range(r0, r1 + 1, 6)))
    return cam, events


def shot_contain(pine):
    """Gece orman yolu: alçak kamera yol kenarında, yolun aşağısına bakar. İki zırhlı araç uzaktan
    farlarıyla yaklaşır ve kameranın yanından arka arkaya geçer (3/4 önden: gövde, farlar, tekerlekler
    hep görünür). Kamera öndeki aracı hafifçe takip eder; odak araçtan araca kayar."""
    f0, f1, O = SHOTS["contain"]
    r0, r1 = span("contain")
    events = {}
    lane, road_y = -5.9, -4.5
    ground(O)
    road(O + Vector((-30, road_y, 0)), 160, 6)
    fog(O + Vector((-30, 0, 0)), (130, 70, 30), density=0.0065, ground_boost=2.2)
    forest(pine, O + Vector((-30, 21, 0)), (60, 19), 210, [], seed=3)                 # karşı kenar
    forest(pine, O + Vector((-40, -26, 0)), (45, 12), 110, [(28, 60, -14, 14)], seed=4)  # kamera tarafı
    # sokak lambaları: karşı kenarda direkler, kollar yola uzanır (ışık hep görünür bir gövdeye bağlı)
    for x in (-3.0, -19.0, -35.0):
        street_lamp(O + Vector((x, -0.9, 0)), (0, -1, 0), target=O + Vector((x, lane, 0)))
    spot("veh_key", O + Vector((-3.0, -15.0, 5.0)), O + Vector((-9.0, lane, 1.2)), 9000, (0.82, 0.88, 1.0), 50,
         0.9, 30, shadow=True)
    spot("veh_rim", O + Vector((-14.0, 6.0, 9.0)), O + Vector((-6.0, lane, 1.6)), 7000, (0.65, 0.78, 1.0), 45,
         0.9, 30, shadow=True)
    spot("grass_fill", O + Vector((1.5, -13.5, 2.2)), O + Vector((-4.0, -8.2, 0.2)), 500, (0.8, 0.85, 1.0), 55,
         0.9, 15, shadow=True)

    # Konvoy: iki zırhlı araç aynı (yakın) şeritte, 1.6 sn arayla kameranın yanından geçer.
    v = 8.0
    passes = (5.15, 6.75)  # araç merkezinin kameranın hizasından (x=0) geçtiği an (sn)
    events["apc_pass"], events["apc_speed"], events["apc_lanes"] = list(passes), v, [lane, lane]
    apcs = []
    for t_mid in passes:
        apc = asset("apc", proxy_apc)
        apc.location = O + Vector((0, lane, 0))
        bpy.context.view_layer.update()
        wheels = [m for m in apc.children_recursive if "wheel" in m]
        lowest = min((m.matrix_world @ Vector(c)).z for m in wheels for c in m.bound_box)
        apc.location.z -= lowest  # tekerlek dişleri yolun üst yüzüne (z=0) değsin
        drive(apc, [(f, O.x + v * (frame_time(f) - t_mid)) for f in (r0, r1)])
        rig_vehicle(apc, 2000)
        beacon_lights(apc, r0, r1)
        apcs.append(apc)
    grass("grass_shoulder", O + Vector((-6.0, -8.0, 0)), 900, 21, r0, r1, (0.15, 0.55), (6.5, 0.25))
    grass("grass_fg", O + Vector((-2.2, -11.6, 0)), 260, 22, r0, r1, (0.3, 0.85), (0.9, 0.5))
    grass("grass_far", O + Vector((-18.0, -8.1, 0)), 700, 23, r0, r1, (0.2, 0.6), (8.0, 0.3))
    dust("dust_contain", O + Vector((-8.0, -5.5, 1.4)), (22, 6, 2.8), 260, 12, r0, r1, drift=(0.25, 0.05, 0.0))

    cpos = O + Vector((0.0, -10.4, 0.75))
    cam = camera("cam_contain", 28, cpos, O + Vector((-30, lane, 1.4)), 2.8)
    for f in (r0, r1):
        u = (f - f0) / (f1 - f0)
        key(cam, f, rot=look_rot(cpos, O + Vector((-30 + 15 * u, lane + 0.6, 1.5 - 0.1 * u))), interp="LINEAR")
    handheld(cam, 0.8)
    for o in bpy.data.objects:  # yakın araçlar sisi perdelemesin diye bu planda tüm spotlar gölgeli
        if o.type == "LIGHT" and o.data.type == "SPOT":
            o.data.use_shadow = True

    def subject(f):  # odak: kadrajdaki öndeki araç (geçip çıkınca arkadaki)
        t = frame_time(f)
        xs = [v * (t - tm) for tm in passes]
        x = next((x for x in xs if x < -3.5), xs[-1])
        return (Vector((x, lane, 1.2)) - Vector((0, -10.4, 0.75))).length

    focus_track(cam, r0, r1, subject)
    # ses için dinleyici geometrisi (scp_sound.pass_by): kamera konumu ve plan ortasındaki sağ yönü
    fwd = (O + Vector((-22.5, lane + 0.6, 1.45)) - cpos).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    events["listener"], events["listener_right"] = list(cpos - O), list(right)
    events["camera_hits"] = len(camera_clear(cam, range(r0, r1 + 1, 6)))
    events["fg_coverage"] = {a.name: frame_coverage(cam, [a], range(r0, r1 + 1, 24)) for a in apcs}
    return cam, events


def shot_protect(pine):
    """Tesis kapısı: kamera yol boyunca kapıya ve SCP amblemine yaklaşır (yazı 2D katmanda)."""
    f0, f1, O = SHOTS["protect"]
    r0, r1 = span("protect")
    events = {}
    ground(O)
    road(O + Vector((0, 14, 0)), 40, 7, along_x=False)
    fog(O + Vector((0, 20, 0)), (100, 80, 30), density=0.0075, ground_boost=2.2)
    forest(pine, O + Vector((0, 45, 0)), (60, 18), 160, [], seed=5)
    forest(pine, O + Vector((-32, 15, 0)), (14, 25), 50, [], seed=6)
    forest(pine, O + Vector((32, 15, 0)), (14, 25), 50, [], seed=7)

    W = 30.0
    gb = Builder()
    c = M["concrete"]
    for sx in (-1, 1):
        gb.box((W - 4.6, 1.0, 5), (sx * (W + 4.6) / 2, W, 2.5), c)
    gb.box((9, 1.4, 3.6), (0, W, 6.6), c)
    gb.box((1.2, 1.4, 5), (-4.0, W, 2.5), c)
    gb.box((1.2, 1.4, 5), (4.0, W, 2.5), c)
    gb.box((3.4, 0.2, 4.6), (-1.72, W, 2.3), M["steel"])
    gb.box((3.4, 0.2, 4.6), (1.72, W, 2.3), M["steel"])
    for k in range(9):
        gb.box((0.45, 0.05, 0.35), (-4.0 + k * 1.0, W - 0.72, 5.05), M["hazard"], (0, 0.6, 0))
    for x in (-6.5, 6.5):
        gb.box((0.25, 0.25, 9), (x, W - 1.5, 4.5), M["steel"])
        gb.box((0.9, 0.5, 0.4), (x, W - 1.75, 9.0), M["steel"])
        gb.box((0.8, 0.05, 0.3), (x, W - 2.0, 9.0), M["lamp"])
    for k in range(4):
        gb.box((0.12, 0.05, 0.12), (-1.2 + k * 0.8, W - 0.73, 4.65), M["green"])
    for x in [-26 + 4 * i for i in range(14)]:
        if abs(x) > 5:
            gb.box((0.3, 0.3, 0.1), (x, W - 0.62, 5.0), M["steel"])   # lamba gövdesi
            gb.box((0.25, 0.08, 0.12), (x, W - 0.54, 4.85), M["lamp"])
    gate = gb.build("gate", bevel=0.02)
    gate.location = O
    bpy.ops.mesh.primitive_torus_add(major_radius=0.36, minor_radius=0.012, major_segments=16,
                                     minor_segments=4, rotation=(0, math.pi / 2, 0))
    tmp = bpy.context.active_object
    coil = tmp.data
    coil.materials.append(M["wire"])
    bpy.data.objects.remove(tmp)
    for x in [(-W + 0.5) + i * 0.35 for i in range(int((2 * W - 1) / 0.35))]:
        if abs(x) < 4.6:
            continue
        o = link(bpy.data.objects.new("coil", coil))
        o.location = O + Vector((x, W, 5.4))
        o.rotation_euler = (0, 0.25, 0)
    emblem(O + Vector((0, W - 0.75, 6.6)), 1.6)
    for x in (-6.5, 6.5):
        spot("flood", O + Vector((x, W - 2.1, 8.9)), O + Vector((x * 0.3, 15, 0)), 3200,
             (0.85, 0.92, 1), 55, 0.5, 80, shadow=True)
    spot("emblem_key", O + Vector((0, W - 6, 2)), O + Vector((0, W - 0.75, 6.6)), 2600, (1, 1, 1), 30, 0.5, 20)
    tw = Builder()
    for dx in (-1, 1):
        for dy in (-1, 1):
            tw.box((0.2, 0.2, 10), (12 + dx * 1.1, W - 4 + dy * 1.1, 5), M["steel"])
    tw.box((3.2, 3.2, 2.2), (12, W - 4, 11), M["olive2"])
    tw.box((3.6, 3.6, 0.2), (12, W - 4, 12.2), M["olive2"])
    tw.box((0.1, 0.05, 0.1), (11.0, W - 5.62, 11.2), M["green"])
    tw.box((0.1, 0.05, 0.1), (11.4, W - 5.62, 11.2), M["green"])
    tw.box((0.5, 0.5, 0.4), (12, W - 5.8, 11.6), M["steel"])  # projektör gövdesi
    tw.build("tower").location = O
    piv = empty("search_pivot", O + Vector((12, W - 5.8, 11.6)))
    spot("search", (0, 0, 0), None, 15000, (0.9, 0.95, 1), 9, 0.3, 120, parent=piv).rotation_euler = (
        math.radians(-70), 0, 0)
    key(piv, r0, rot=(0, 0, math.radians(30)), interp="LINEAR")
    key(piv, r1, rot=(0, 0, math.radians(-5)), interp="LINEAR")

    for i, (x, y, rz) in enumerate(((-9.5, 21, math.radians(-70)), (9.0, 19.5, math.radians(-115)))):
        tr = asset("truck", proxy_truck)
        tr.location = O + Vector((x, y, 0.0))
        tr.rotation_euler = (0, 0, rz)
        SETTLE.append(tr)
        rig_vehicle(tr, lights_on=False)  # park halinde: farlar kapalı (yolda kaynaksız ışık lekesi yok)
    for sx in (-1, 1):
        for k in range(10):
            y = 8.5 + k * 1.91
            place("fence", O + Vector((sx * 5.2, y + 0.95, 0)), math.pi / 2, settle=True)
            pb = Builder()
            pb.cyl(0.04, 0.04, 2.6, (0, 0, 1.3), M["steel"], segs=8)
            pb.build("fence_post").location = O + Vector((sx * 5.2, y, 0))
    for x, y, rz in ((-2.2, 17.5, 0.08), (-0.6, 17.6, -0.05), (1.6, 21.0, 0.1), (3.1, 21.1, -0.04),
                     (-3.0, 24.0, 0.0), (-1.4, 24.1, 0.06)):
        place("barrier", O + Vector((x, y, 0)), rz, settle=True)
    settle(SETTLE)
    settle(SETTLE)
    events["grounded_bad"] = len(check_grounded(SETTLE))
    for k, (x, y) in enumerate(((-3.0, 0.5), (2.9, 0.0), (-4.2, 5.0), (4.1, 6.5))):
        grass(f"grass_p{k}", O + Vector((x, y, 0)), 220, 30 + k, r0, r1, (0.2, 0.75), 0.45)

    p0, p1 = O + Vector((-0.15, -1.2, 2.0)), O + Vector((0.45, 6.5, 1.7))
    emb_c = O + Vector((0, W - 0.75, 6.6))
    cam = camera("cam_protect", 24, p0, emb_c, 4.0)
    for f in range(r0, r1 + 1):
        u = (f - f0) / (f1 - f0)
        p = p0.lerp(p1, 0.35 * smoothstep(u) + 0.65 * u)
        # amblem kadrajın üst üçte birinde kalsın (ortadaki 2D yazıyla üst üste binmesin)
        aim_pt = emb_c - Vector((0, 0, 0.22 * (emb_c.y - p.y)))
        key(cam, f, loc=p, rot=look_rot(p, aim_pt), interp="LINEAR")
    handheld(cam, 0.4)
    focus_track(cam, r0, r1, lambda f: (emb_c - p0.lerp(p1, (f - f0) / (f1 - f0))).length)
    events["camera_hits"] = len(camera_clear(cam, range(r0, r1 + 1, 6)))
    return cam, events


# --------------------------------------------------------------------------- sahne ve render

def setup_scene(preview, shot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.frame_start, s.frame_end = F_START, F_END
    s.render.fps = FPS
    s.render.engine = "BLENDER_EEVEE_NEXT"
    e = s.eevee
    e.taa_render_samples = 4 if preview else QUALITY["samples"]
    e.volumetric_tile_size = "16" if preview else QUALITY["vol_tile"]
    e.volumetric_samples = 24 if preview else QUALITY["vol_samples"]
    e.volumetric_start, e.volumetric_end = 0.1, 140
    for k, v in (("use_volumetric_shadows", True), ("use_shadows", True),
                 ("use_raytracing", not preview and QUALITY["raytracing"]), ("use_gtao", True)):
        if hasattr(e, k):
            setattr(e, k, v)
    if hasattr(e, "bokeh_max_size"):
        e.bokeh_max_size = 60
    if hasattr(e, "motion_blur_steps"):  # dönen tekerlekler için çok adımlı hareket bulanıklığı
        e.motion_blur_steps = 3 if shot == "contain" and not preview else 1
    s.render.use_motion_blur = not preview
    s.render.motion_blur_shutter = 0.7  # 30 fps çıktıda ~125° obtüratör
    s.render.resolution_x, s.render.resolution_y = (640, 360) if preview else (1920, 1080)
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.render.image_settings.file_format = "PNG"
    s.view_settings.view_transform = "AgX"
    try:
        s.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    s.view_settings.exposure = 0.0
    w = bpy.data.worlds.new("night")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.008, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1
    s.world = w
    if shot != "secure":  # depo içinde ay ışığı yok (gölgesiz güneş duvarlardan geçerdi)
        moon = bpy.data.lights.new("moon", "SUN")
        moon.energy, moon.color, moon.angle = 0.1, (0.6, 0.7, 1.0), 0.02
        moon.use_shadow = False
        mo = link(bpy.data.objects.new("moon", moon))
        mo.rotation_euler = (math.radians(55), 0, math.radians(160))
    s.use_nodes = True
    nt = s.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    gl = nt.nodes.new("CompositorNodeGlare")
    gl.glare_type, gl.threshold, gl.size, gl.mix = "FOG_GLOW", 1.0, 7, -0.6
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
    nt.links.new(gl.outputs["Image"], comp.inputs["Image"])
    return s


# Final kalite (ekran kartı olmadan, işlemciyle kare başına süreyi makul tutan değerler).
QUALITY = {"samples": 16, "vol_tile": "8", "vol_samples": 48, "raytracing": False}
SHOT_FUNCS = {"secure": shot_secure, "contain": shot_contain, "protect": shot_protect}


def build(preview, name):
    """Tek bir planı kurar (bellek: her işlem yalnızca kendi planını taşır)."""
    s = setup_scene(preview, name)
    _TEMPLATES.clear()  # önceki planın nesneleri sahne sıfırlanınca silindi
    vehicles._MATS.clear()
    SETTLE.clear()
    make_materials()
    pine = impostor_tree() or realize_tree_template(asset("pine", proxy_pine))
    random.seed(7 + list(SHOTS).index(name))  # plan başına sabit tohum
    cam, events = SHOT_FUNCS[name](pine)
    s.camera = cam
    s.frame_start, s.frame_end = span(name)
    events.update({"cuts": [frame_time(SHOTS[k][1] + 1) for k in SHOTS], "end": END_TIME,
                   "spans": {k: list(span(k)) for k in SHOTS}, f"checks_{name}": {
                       k: events.get(k) for k in ("grounded_bad", "fg_coverage", "camera_hits")}})
    for k in ("grounded_bad", "fg_coverage", "camera_hits"):
        events.pop(k, None)
    return s, events


def shot_of(frame):
    return next(k for k, (f0, f1, _) in SHOTS.items() if f0 <= frame <= f1)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--shot", choices=list(SHOTS), help="render edilecek plan (yoksa üçü sırayla)")
    ap.add_argument("--still", help="tek kare ya da virgüllü liste (ör. 100,300,480)")
    ap.add_argument("--frames", help="planın içinde bir aralık, ör. 217-300")
    ap.add_argument("--step", type=int, default=1, help="her N karede bir render (2 = 30 fps)")
    ap.add_argument("--out", help="çıktı klasörü (varsayılan renders/scp veya renders_preview/scp)")
    ap.add_argument("--save-blend", action="store_true", help="sahneyi .blend olarak da kaydet")
    ap.add_argument("--check", action="store_true", help="yalnızca sahneyi kur ve kontrolleri yazdır")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else ROOT / ("renders_preview" if a.preview else "renders") / "scp"
    out.mkdir(parents=True, exist_ok=True)

    if a.still:
        frames = [int(f) for f in a.still.split(",")]
        for name in dict.fromkeys(a.shot or shot_of(f) for f in frames):
            s, _ = build(a.preview, name)
            for f in [f for f in frames if (a.shot or shot_of(f)) == name]:
                s.frame_set(f)
                s.render.filepath = str(out / f"still_{f:04d}.png")
                bpy.ops.render.render(write_still=True)
        return

    for name in [a.shot] if a.shot else list(SHOTS):
        s, events = build(a.preview, name)
        meta_path = out / "meta.json"  # her plan olaylarını ortak meta.json'a ekler
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta.update({"fps": FPS, "first_frame": F_START, "step": a.step, **events})
        meta_path.write_text(json.dumps(meta, indent=2))
        if a.check:
            continue
        if a.save_blend:
            bpy.ops.wm.save_as_mainfile(filepath=str(out / f"scp_{name}.blend"))
        if a.frames:
            s.frame_start, s.frame_end = map(int, a.frames.split("-"))
        s.frame_step = a.step
        (out / name).mkdir(exist_ok=True)
        s.render.filepath = str(out / name / "####")
        bpy.ops.render.render(animation=True)


def run():
    main()
    sys.stdout.flush()
    os._exit(0)  # bpy modülü glTF dokularını bırakırken çıkışta çökebiliyor; kareler yazıldı


if __name__ == "__main__":
    run()
