"""Roblox R15 karakterini Blender'a alıp rig'ler (bpy; headless çalışır).

Roblox Studio'nun "Export Selection" çıktısında R15 gövdesi 15 ayrı mesh'tir
(ör. Theandroe1..15) ve aksesuarlar Handle1..N gruplarıdır; hazır bir iskelet
yoktur. Bu modül parçaları konumlarından tanır, Roblox'un Motor6D eklem
düzenine göre kemikleri kurar ve her parçayı kendi kemiğine sert (rigid) bağlar:

  HumanoidRootPart
   └ LowerTorso            (Root)
      ├ UpperTorso         (Waist)
      │  ├ Head            (Neck)      ← kask / taç / başlık aksesuarları
      │  ├ LeftUpperArm    (LeftShoulder) → LeftLowerArm (Elbow) → LeftHand (Wrist)
      │  ├ RightUpperArm   ...
      │  └ Cape1 → Cape2 → Cape3       ← pelerin (UpperTorso attachment'ı), ikincil hareket
      ├ LeftUpperLeg       (LeftHip)  → LeftLowerLeg (Knee) → LeftFoot (Ankle)
      └ RightUpperLeg      ...

Eksenler: dosyada Y yukarı, karakter -Z'ye bakar. Blender'da Z yukarı ve
karakter -Y'ye (ön görünüş kamerasına) bakacak şekilde alınır; ayaklar z=0'da,
LowerTorso x=y=0'da durur. Birim: stud.
"""
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

BODY_BONES = ("LowerTorso", "UpperTorso", "Head",
              "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
              "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot")


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _read_groups(obj_path):
    """OBJ'yi doğrudan okuyup grup -> (konumlar, uv, yüzler, malzeme) çıkarır.
    (Blender içe aktarıcısının grup/malzeme bölmesine güvenmek yerine kendi okuyucumuz.)"""
    v, vt, groups, cur, mat = [], [], {}, None, None
    for line in open(obj_path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "g":
            cur = p[1]
            groups.setdefault(cur, {"faces": [], "mat": None})
        elif p[0] == "usemtl" and cur:
            groups[cur]["mat"] = p[1]
        elif p[0] == "f" and cur:
            groups[cur]["faces"].append([[int(x) - 1 if x else -1 for x in q.split("/")[:2]] for q in p[1:]])
    return np.array(v), np.array(vt), groups


def _to_blender(p):
    # dosya (x, y, z), karakter -Z'ye bakar  ->  Blender (x', y', z'), karakter -Y'ye bakar, Z yukarı
    # -Z (ön) -> -Y olacak şekilde: x' = -x, y' = z, z' = y   (Y ekseni çevresinde 180° + eksen değişimi)
    return np.stack([-p[:, 0], p[:, 2], p[:, 1]], -1)


def _classify(bounds):
    """15 gövde grubunu R15 parça adlarına eşler (yalnızca konumlarla).
    bounds: {grup: (min, max)} Blender koordinatında (karakter -Y'ye bakar, sağı -X)."""
    c = {g: (b[0] + b[1]) / 2 for g, b in bounds.items()}
    size = {g: b[1] - b[0] for g, b in bounds.items()}
    names = list(bounds)
    # gövde: en geniş iki parça; üstteki UpperTorso, alttaki (kısa olan) LowerTorso
    torso = sorted(names, key=lambda g: -size[g][0])[:2]
    upper = max(torso, key=lambda g: size[g][2])
    lower = [g for g in torso if g != upper][0]
    cx = c[upper][0]
    rest = [g for g in names if g not in torso]
    head = max(rest, key=lambda g: c[g][2] - 3 * abs(c[g][0] - cx))
    rest.remove(head)
    out = {upper: "UpperTorso", lower: "LowerTorso", head: "Head"}
    # Karakter -Y'ye (kameraya) bakarken kendi sağı ekranın solundadır = -X tarafı
    for g in rest:
        side = "Right" if c[g][0] < cx else "Left"
        kind = "Arm" if abs(c[g][0] - cx) > 1.1 else "Leg"          # kollar gövdenin iki yanında, dışarıda
        out[g] = (side, kind)
    for side in ("Left", "Right"):
        for kind, labels in (("Arm", ("Hand", "LowerArm", "UpperArm")), ("Leg", ("Foot", "LowerLeg", "UpperLeg"))):
            chain = sorted([g for g, v in out.items() if v == (side, kind)], key=lambda g: c[g][2])
            assert len(chain) == 3, (side, kind, chain)
            for g, lab in zip(chain, labels):
                out[g] = side + lab
    return out


def _overlap_mid(a, b):
    """İki parçanın dikeyde üst üste bindiği bölgenin ortası (eklem yüksekliği)."""
    lo, hi = max(a[0][2], b[0][2]), min(a[1][2], b[1][2])
    return (lo + hi) / 2 if hi > lo else (a[0][2] + b[1][2]) / 2


class R15:
    """Rig'lenmiş bir karakter: armature nesnesi + parça nesneleri."""

    def __init__(self, folder, name, collection=None):
        folder = Path(folder)
        obj_path = next(folder.glob("*.obj"))
        v, vt, groups = _read_groups(obj_path)
        vb = _to_blender(v)
        mats = self._materials(folder, obj_path.with_suffix(".mtl"), name)
        self.name = name
        self.coll = collection or bpy.context.scene.collection

        body = {g: d for g, d in groups.items() if not g.startswith("Handle")}
        idx = {g: sorted({i for f in d["faces"] for i, _ in f}) for g, d in groups.items()}
        bounds = {g: (vb[idx[g]].min(0), vb[idx[g]].max(0)) for g in groups}
        part_of = _classify({g: bounds[g] for g in body})
        self.part_group = {p: g for g, p in part_of.items()}
        # merkez: LowerTorso x,y ortası; ayak tabanı z=0
        lt = bounds[self.part_group["LowerTorso"]]
        feet = min(bounds[self.part_group[f]][0][2] for f in ("LeftFoot", "RightFoot"))
        self.offset = np.array([(lt[0][0] + lt[1][0]) / 2, (lt[0][1] + lt[1][1]) / 2, feet])
        vb = vb - self.offset
        bounds = {g: (b[0] - self.offset, b[1] - self.offset) for g, b in bounds.items()}
        self.bounds = {p: bounds[g] for p, g in self.part_group.items()}

        self.joints = self._joints()
        self.arm = self._armature()
        self.parts = {}
        for g, d in groups.items():
            ob = self._mesh(f"{name}_{g}", vb, vt, d, mats.get(d["mat"]))
            if g in part_of:
                self._attach(ob, part_of[g])
                self.parts[part_of[g]] = ob
            else:
                self.parts[g] = ob
                self._attach_accessory(ob, bounds[g])

    # ---------------------------------------------------------------- malzemeler

    def _materials(self, folder, mtl_path, name):
        mats, cur = {}, None
        for line in open(mtl_path):
            p = line.split()
            if not p:
                continue
            if p[0] == "newmtl":
                cur = p[1]
                mats[cur] = {}
            elif p[0] in ("map_Kd", "map_Bump") and cur:
                mats[cur][p[0]] = folder / p[1]
        out = {}
        for m, maps in mats.items():
            mat = bpy.data.materials.new(f"{name}_{m}")
            mat.use_nodes = True
            nt = mat.node_tree
            bsdf = nt.nodes["Principled BSDF"]
            bsdf.inputs["Roughness"].default_value = 0.55
            if "map_Kd" in maps:
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.image = bpy.data.images.load(str(maps["map_Kd"]))
                tex.interpolation = "Linear"
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
                mat["diffuse_node"] = tex.name
            if "map_Bump" in maps:
                nm = nt.nodes.new("ShaderNodeTexImage")
                nm.image = bpy.data.images.load(str(maps["map_Bump"]))
                nm.image.colorspace_settings.name = "Non-Color"
                nmap = nt.nodes.new("ShaderNodeNormalMap")
                nmap.inputs["Strength"].default_value = 0.6
                nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
                nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
            # iki yüzlü: arka yüzler de dokulu görünür (pelerinin içi gri kalmaz)
            mat.use_backface_culling = False
            out[m] = mat
        return out

    # ---------------------------------------------------------------- iskelet

    def _joints(self):
        b = self.bounds
        mid = lambda p: (b[p][0] + b[p][1]) / 2
        J = {}
        lt, ut, hd = b["LowerTorso"], b["UpperTorso"], b["Head"]
        J["Root"] = mid("LowerTorso")
        J["Waist"] = np.array([0.0, mid("LowerTorso")[1], _overlap_mid(lt, ut)])
        J["Neck"] = np.array([0.0, mid("UpperTorso")[1], _overlap_mid(ut, hd)])
        for s in ("Left", "Right"):
            ua, la, h = b[s + "UpperArm"], b[s + "LowerArm"], b[s + "Hand"]
            J[s + "Shoulder"] = np.array([mid(s + "UpperArm")[0], mid(s + "UpperArm")[1], ua[1][2] - 0.35])
            J[s + "Elbow"] = np.array([mid(s + "LowerArm")[0], mid(s + "LowerArm")[1], _overlap_mid(ua, la)])
            J[s + "Wrist"] = np.array([mid(s + "Hand")[0], mid(s + "Hand")[1], _overlap_mid(la, h)])
            J[s + "HandTip"] = np.array([mid(s + "Hand")[0], mid(s + "Hand")[1], h[0][2]])
            ul, ll, f = b[s + "UpperLeg"], b[s + "LowerLeg"], b[s + "Foot"]
            J[s + "Hip"] = np.array([mid(s + "UpperLeg")[0], mid(s + "UpperLeg")[1], _overlap_mid(lt, ul)])
            J[s + "Knee"] = np.array([mid(s + "LowerLeg")[0], mid(s + "LowerLeg")[1], _overlap_mid(ul, ll)])
            J[s + "Ankle"] = np.array([mid(s + "Foot")[0], mid(s + "Foot")[1], _overlap_mid(ll, f)])
            J[s + "Toe"] = np.array([mid(s + "Foot")[0], f[0][1], f[0][2] + 0.05])     # ayak ucu öne (-Y)
        J["HeadTop"] = np.array([0.0, mid("Head")[1], hd[1][2]])
        return J

    def _armature(self):
        J = self.joints
        data = bpy.data.armatures.new(self.name + "_rig")
        arm = bpy.data.objects.new(self.name + "_rig", data)
        self.coll.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        eb = data.edit_bones

        def bone(name, head, tail, parent=None, connect=False):
            b = eb.new(name)
            b.head, b.tail = Vector(head), Vector(tail)
            b.roll = 0.0
            if parent:
                b.parent = eb[parent]
                b.use_connect = connect
            return b

        up = np.array([0, 0, 1.0])
        bone("HumanoidRootPart", J["Root"], J["Root"] + up * 0.6)
        bone("LowerTorso", J["Root"], J["Waist"] + up * 0.001, "HumanoidRootPart")
        bone("UpperTorso", J["Waist"], J["Neck"], "LowerTorso")
        bone("Head", J["Neck"], J["HeadTop"], "UpperTorso")
        for s in ("Left", "Right"):
            bone(s + "UpperArm", J[s + "Shoulder"], J[s + "Elbow"], "UpperTorso")
            bone(s + "LowerArm", J[s + "Elbow"], J[s + "Wrist"], s + "UpperArm", True)
            bone(s + "Hand", J[s + "Wrist"], J[s + "HandTip"], s + "LowerArm", True)
            bone(s + "UpperLeg", J[s + "Hip"], J[s + "Knee"], "LowerTorso")
            bone(s + "LowerLeg", J[s + "Knee"], J[s + "Ankle"], s + "UpperLeg", True)
            bone(s + "Foot", J[s + "Ankle"], J[s + "Toe"], s + "LowerLeg", True)
        # pelerin zinciri: sırtın arkasında, omuzdan aşağı (ikincil hareket için)
        back = self.bounds["UpperTorso"][1][1] + 0.05
        top = J["Neck"][2] - 0.1
        for i in range(3):
            z0 = top - i * (top - 0.3) / 3
            z1 = top - (i + 1) * (top - 0.3) / 3
            bone(f"Cape{i + 1}", (0, back, z0), (0, back, z1), "UpperTorso" if i == 0 else f"Cape{i}", i > 0)
        bpy.ops.object.mode_set(mode="OBJECT")
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        return arm

    # ---------------------------------------------------------------- mesh

    def _mesh(self, name, vb, vt, d, mat):
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new("UVMap")
        used = sorted({i for f in d["faces"] for i, _ in f})
        remap = {}
        for i in used:
            remap[i] = bm.verts.new(Vector(vb[i]))
        for f in d["faces"]:
            try:
                face = bm.faces.new([remap[i] for i, _ in f])
            except ValueError:            # yinelenen yüz: atla (duplicate yüz temizliği)
                continue
            for loop, (_, t) in zip(face.loops, f):
                if t >= 0:
                    loop[uv_layer].uv = vt[t]
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)          # "Recalculate Outside"
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = False
        ob = bpy.data.objects.new(name, me)
        if mat:
            me.materials.append(mat)
        self.coll.objects.link(ob)
        return ob

    def _attach(self, ob, bone):
        """Parçayı kemiğe sert bağlar (Roblox'taki Motor6D gibi)."""
        pb = self.arm.data.bones[bone]
        ob.parent = self.arm
        ob.parent_type = "BONE"
        ob.parent_bone = bone
        # kemik uzayına geçerken dünya konumunu koru
        bone_world = self.arm.matrix_world @ pb.matrix_local @ Matrix.Translation((0, pb.length, 0))
        ob.matrix_parent_inverse = bone_world.inverted()

    def _attach_accessory(self, ob, bounds):
        """Aksesuar: Roblox attachment mantığı. Baş hizasında olanlar Head'e, sırttan
        aşağı sarkan (pelerin) UpperTorso'daki pelerin kemik zincirine bağlanır."""
        lo, hi = bounds
        if hi[2] - lo[2] > 2.5:                        # boydan sarkan parça = pelerin
            self._skin_cape(ob)
        else:
            self._attach(ob, "Head")

    def _skin_cape(self, ob):
        """Pelerini üç kemiklik zincire yumuşak ağırlıklarla bağlar (yukarıdan aşağı)."""
        ob.parent = self.arm
        ob.parent_type = "OBJECT"
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = self.arm
        top = self.joints["Neck"][2] - 0.1
        zs = [top - i * (top - 0.3) / 3 for i in range(4)]
        centers = [(zs[i] + zs[i + 1]) / 2 for i in range(3)]
        groups = [ob.vertex_groups.new(name=f"Cape{i + 1}") for i in range(3)]
        ut = ob.vertex_groups.new(name="UpperTorso")
        seg = (top - 0.3) / 3
        for v in ob.data.vertices:
            z = v.co.z
            if z > top:
                ut.add([v.index], 1.0, "REPLACE")
                continue
            w = [max(0.0, 1 - abs(z - c) / seg) for c in centers]
            s = sum(w) or 1.0
            # en üstte omuza yapışık kalsın
            anchor = max(0.0, min(1.0, (z - (top - 0.35 * seg)) / (0.35 * seg)))
            for g, wi in zip(groups, w):
                if wi > 0:
                    g.add([v.index], (1 - anchor) * wi / s, "REPLACE")
            if anchor > 0:
                ut.add([v.index], anchor, "REPLACE")

    # ---------------------------------------------------------------- rapor

    def report(self):
        lines = [f"{self.name}: {len(self.arm.data.bones)} kemik"]
        for b in self.arm.data.bones:
            parent = b.parent.name if b.parent else "-"
            h = b.head_local
            lines.append(f"  {b.name:18s} ebeveyn {parent:16s} eklem ({h.x:6.2f}, {h.y:6.2f}, {h.z:6.2f})  uzunluk {b.length:4.2f}")
        lines.append("  parça -> OBJ grubu: " + ", ".join(f"{p}={g}" for p, g in sorted(self.part_group.items())))
        acc = [n for n in self.parts if n.startswith("Handle")]
        lines.append("  aksesuarlar: " + ", ".join(
            f"{n}->{'Cape zinciri (UpperTorso)' if self.parts[n].parent_type == 'OBJECT' else self.parts[n].parent_bone}" for n in acc))
        return "\n".join(lines)
