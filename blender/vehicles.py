"""Prosedürel askerî araçlar (headless bpy): 8x8 zırhlı personel taşıyıcı ve 6x6 kamyon.

Ölçüler gerçek araçlara yakındır (APC ~7.0 x 2.7 x 2.9 m, kamyon ~7.6 x 2.5 x 3.2 m).
Kural: ön +X, yukarı +Z, taban z=0. Döndürülecek/ışık bağlanacak parçalar özel
özelliklerle işaretlenir (scp_cinematic.drive / rig_vehicle / beacon_lights bunları arar):

  "body"       süspansiyon sarsıntısı uygulanan gövde empty'si (tekerlekler hariç her şey)
  "wheel"      tekerlek yarıçapı; Y ekseni etrafında döner
  "headlight"  far konumu (empty; spot ışık buraya bağlanır)
  "beacon"     dönen tepe lambası
  "antenna"    kökünden sallanan anten
  "jerrycan"   bidon takılacak nokta (empty)
"""
import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def _link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def _empty(name, loc, parent=None, **props):
    e = _link(bpy.data.objects.new(name, None), parent)
    e.location = loc
    for k, v in props.items():
        e[k] = v
    return e


def _sock(node, name, kind, out=False):
    socks = node.outputs if out else node.inputs
    return next(s for s in socks if s.name == name and s.type == kind)


# --------------------------------------------------------------------------- malzemeler

def paint_material(name, camo=((0.05, 0.056, 0.034), (0.034, 0.03, 0.02), (0.016, 0.017, 0.014)),
                   mud=(0.035, 0.027, 0.017), camo_scale=0.55, mud_top=1.25):
    """Üç tonlu orman kamuflajı + ince renk dalgalanması + altta çamur (nesne Z'sine göre)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    camo_n = nt.nodes.new("ShaderNodeTexNoise")
    camo_n.inputs["Scale"].default_value = camo_scale
    camo_n.inputs["Detail"].default_value = 1.5
    camo_n.inputs["Distortion"].default_value = 0.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*camo[0], 1)
    el[1].position, el[1].color = 0.47, (*camo[1], 1)
    e3 = el.new(0.6)
    e3.color = (*camo[2], 1)
    nt.links.new(tc.outputs["Object"], camo_n.inputs["Vector"])
    nt.links.new(camo_n.outputs["Fac"], ramp.inputs["Fac"])
    # ince doku: boya dalgalanması ve çizik bump'ı
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 18
    fine.inputs["Detail"].default_value = 8
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    var = nt.nodes.new("ShaderNodeMix")
    var.data_type = "RGBA"
    var.blend_type = "MULTIPLY"
    _sock(var, "Factor", "VALUE").default_value = 0.35
    nt.links.new(ramp.outputs["Color"], _sock(var, "A", "RGBA"))
    nt.links.new(fine.outputs["Color"], _sock(var, "B", "RGBA"))
    # çamur maskesi: alçakta yoğun, gürültüyle dağınık
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    hmap = nt.nodes.new("ShaderNodeMapRange")
    hmap.inputs["From Min"].default_value = 0.3
    hmap.inputs["From Max"].default_value = mud_top
    hmap.inputs["To Min"].default_value = 1.0
    hmap.inputs["To Max"].default_value = -0.2
    nt.links.new(sep.outputs["Z"], hmap.inputs["Value"])
    mn = nt.nodes.new("ShaderNodeTexNoise")
    mn.inputs["Scale"].default_value = 3.5
    mn.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], mn.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(hmap.outputs["Result"], add.inputs[0])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    nt.links.new(mn.outputs["Fac"], sub.inputs[0])
    sub.inputs[1].default_value = 0.5
    nt.links.new(sub.outputs[0], add.inputs[1])
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = 0.35
    mask.inputs["From Max"].default_value = 0.6
    nt.links.new(add.outputs[0], mask.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(mask.outputs["Result"], _sock(mix, "Factor", "VALUE"))
    nt.links.new(var.outputs[2], _sock(mix, "A", "RGBA"))
    _sock(mix, "B", "RGBA").default_value = (*mud, 1)
    nt.links.new(_sock(mix, "Result", "RGBA", out=True), p.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.52
    rough.inputs["To Max"].default_value = 0.92
    nt.links.new(mask.outputs["Result"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.025
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    p.inputs["Metallic"].default_value = 0.15
    return m


def simple(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    return m


def canvas_material():
    m = simple("canvas_cover", (0.06, 0.06, 0.038), 0.95)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 0.9
    wave.inputs["Distortion"].default_value = 9
    wave.inputs["Detail"].default_value = 4
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.07
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


_MATS = {}


def mats():
    if not _MATS:
        _MATS.update(
            paint=paint_material("vehicle_paint"),
            paint_dark=paint_material("vehicle_paint_dark", camo=((0.03, 0.033, 0.022),) * 3),
            rubber=simple("tire_rubber", (0.014, 0.013, 0.012), 0.88),
            rim=simple("rim_paint", (0.035, 0.038, 0.026), 0.6, 0.2),
            steel=simple("vehicle_steel", (0.06, 0.06, 0.062), 0.45, 0.8),
            gun=simple("gun_parkerized", (0.02, 0.02, 0.021), 0.5, 0.7),
            glass=simple("armored_glass", (0.006, 0.008, 0.01), 0.04, 0.0),
            head=simple("headlamp", (1, 1, 1), 0.15, emit=(1, 0.92, 0.78), strength=60),
            tail=simple("taillamp", (0.6, 0.02, 0.01), 0.3, emit=(1, 0.03, 0.01), strength=12),
            amber=simple("amber_marker", (0.8, 0.4, 0.02), 0.3, emit=(1, 0.45, 0.02), strength=10),
            beacon=simple("beacon_lens", (1, 0.05, 0.03), 0.2, emit=(1, 0.04, 0.02), strength=70),
            stencil=simple("stencil_white", (0.55, 0.55, 0.5), 0.75),
            canvas=canvas_material(),
            wood=simple("bed_wood", (0.07, 0.05, 0.03), 0.85),
            black=simple("black_plastic", (0.012, 0.012, 0.012), 0.6),
        )
    return _MATS


# --------------------------------------------------------------------------- mesh kurucu

class VB:
    """bmesh tabanlı parça kurucu: kutu, silindir, profil ekstrüzyonu, loft, döndürme."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _tag(self, faces, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        mi = self.mats.index(mat)
        for f in faces:
            f.material_index = mi

    def _faces_of(self, verts):
        return {f for v in verts for f in v.link_faces}

    def boxm(self, matrix, mat):
        g = bmesh.ops.create_cube(self.bm, size=1.0, matrix=matrix)
        self._tag(self._faces_of(g["verts"]), mat)

    def box(self, size, loc, mat, rot=(0, 0, 0)):
        self.boxm(Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(size)), mat)

    def cyl(self, r1, r2, depth, loc, mat, rot=(0, 0, 0), segs=16):
        g = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=depth,
                                  matrix=Matrix.LocRotScale(Vector(loc), Euler(rot), None))
        self._tag(self._faces_of(g["verts"]), mat)

    def cyl_between(self, a, b, r, mat, segs=10):
        a, b = Vector(a), Vector(b)
        d = b - a
        q = d.to_track_quat("Z", "Y")
        g = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=d.length,
                                  matrix=Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4())
        self._tag(self._faces_of(g["verts"]), mat)

    def prism(self, pts_xz, thick, mat, y=0.0):
        a = [self.bm.verts.new((x, y - thick / 2, z)) for x, z in pts_xz]
        b = [self.bm.verts.new((x, y + thick / 2, z)) for x, z in pts_xz]
        faces = [self.bm.faces.new(list(reversed(a))), self.bm.faces.new(b)]
        n = len(a)
        faces += [self.bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])) for i in range(n)]
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        self._tag(faces, mat)

    def loft(self, rings, mat, cap=True):
        """rings: aynı sayıda noktalı halkalar (Vector listesi). Kapalı kabuk üretir."""
        vs = [[self.bm.verts.new(p) for p in ring] for ring in rings]
        n = len(vs[0])
        faces = []
        for r0, r1 in zip(vs, vs[1:]):
            faces += [self.bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j])) for j in range(n)]
        if cap:
            faces += [self.bm.faces.new(list(reversed(vs[0]))), self.bm.faces.new(vs[-1])]
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        self._tag(faces, mat)

    def revolve(self, profile, segs, mat, matrix=Matrix()):
        """profile: [(r, y)] kapalı döngü; Y ekseni etrafında döndürür."""
        rings = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            rings.append([self.bm.verts.new(matrix @ Vector((r * math.cos(a), y, r * math.sin(a))))
                          for r, y in profile])
        n = len(profile)
        faces = []
        for i in range(segs):
            r0, r1 = rings[i], rings[(i + 1) % segs]
            faces += [self.bm.faces.new((r0[j], r1[j], r1[(j + 1) % n], r0[(j + 1) % n])) for j in range(n)]
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        self._tag(faces, mat)

    def build(self, name, parent=None, loc=(0, 0, 0), bevel=0.0, smooth=35):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        for p in me.polygons:
            p.use_smooth = True
        if hasattr(me, "set_sharp_from_angle"):
            me.set_sharp_from_angle(angle=math.radians(smooth))
        o = _link(bpy.data.objects.new(name, me), parent)
        o.location = loc
        if bevel:
            b = o.modifiers.new("bevel", "BEVEL")
            b.width, b.segments, b.limit_method, b.angle_limit = bevel, 2, "ANGLE", math.radians(30)
            b.harden_normals = True
        return o


def bolts(vb, pts, axis, mat, r=0.016, h=0.014):
    rot = {"y": (math.pi / 2, 0, 0), "x": (0, math.pi / 2, 0), "z": (0, 0, 0)}[axis]
    for p in pts:
        vb.cyl(r, r * 0.8, h, p, mat, rot, segs=6)


def text_decal(body, txt, loc, rot, size, font):
    cu = bpy.data.curves.new("stencil", "FONT")
    cu.body = txt
    if font:
        cu.font = bpy.data.fonts.load(str(font), check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.extrude = 0.0015
    cu.materials.append(mats()["stencil"])
    o = _link(bpy.data.objects.new("stencil", cu), body)
    o.location, o.rotation_euler = loc, rot
    return o


# --------------------------------------------------------------------------- tekerlek

def wheel(name, r=0.56, w=0.42, rim_r=0.33, lugs=34, parent=None, loc=(0, 0, 0), mirror=False):
    """Arazi lastiği: yuvarlatılmış profil + V desenli diş blokları, jant, göbek, bijonlar."""
    M = mats()
    vb = VB()
    h = w / 2
    prof = [(rim_r, -h + 0.02), (r - 0.09, -h - 0.01), (r - 0.035, -h + 0.005), (r - 0.008, -h + 0.04),
            (r, -h + 0.09), (r, h - 0.09), (r - 0.008, h - 0.04), (r - 0.035, h - 0.005), (r - 0.09, h + 0.01),
            (rim_r, h - 0.02)]
    vb.revolve(prof, 48, M["rubber"])
    for i in range(lugs):
        for side in (-1, 1):
            a = 2 * math.pi * (i + (0.5 if side > 0 else 0)) / lugs
            radial = Vector((math.cos(a), 0, math.sin(a)))
            tang = Vector((-math.sin(a), 0, math.cos(a)))
            axial = Vector((0, 1, 0))
            c = 0.42 * side
            t2 = tang * math.cos(c) + axial * math.sin(c)
            a2 = axial * math.cos(c) - tang * math.sin(c)
            rot = Matrix((t2, a2, radial)).transposed().to_4x4()
            center = radial * (r + 0.012) + axial * (side * h * 0.42)
            vb.boxm(Matrix.Translation(center) @ rot @ Matrix.Diagonal((0.075, h * 0.62, 0.03, 1)), M["rubber"])
    # jant: iç çanak, dış disk, göbek, bijonlar, CTIS valfi
    vb.cyl(rim_r, rim_r, w - 0.06, (0, 0, 0), M["rim"], (math.pi / 2, 0, 0), segs=32)
    vb.cyl(rim_r * 0.92, rim_r * 0.92, 0.02, (0, h - 0.02, 0), M["rim"], (math.pi / 2, 0, 0), segs=32)
    vb.cyl(0.13, 0.1, 0.09, (0, h + 0.02, 0), M["rim"], (-math.pi / 2, 0, 0), segs=20)
    vb.cyl(0.045, 0.045, 0.05, (0, h + 0.07, 0), M["steel"], (-math.pi / 2, 0, 0), segs=12)
    for k in range(10):
        a = 2 * math.pi * k / 10
        vb.cyl(0.014, 0.014, 0.03, (0.19 * math.cos(a), h + 0.0, 0.19 * math.sin(a)), M["steel"],
               (math.pi / 2, 0, 0), segs=6)
    vb.cyl_between((0.05, h + 0.06, 0.03), (0.24, h - 0.01, 0.12), 0.008, M["black"], 6)
    o = vb.build(name, parent, loc, bevel=0.006, smooth=50)
    o["wheel"] = r
    if mirror:
        o.scale = (1, -1, 1)
    return o


# --------------------------------------------------------------------------- 8x8 APC

def _hull_ring(x, zb, wb, zv, wl, zl0, zf, ws, zs1, wr, zr, zt):
    half = [(wb, zv), (wl, zl0), (wl, zf), (ws, zf), (ws, zs1), (wr, zr)]
    pts = [(0, zb)] + half + [(0, zt)] + [(-y, z) for y, z in reversed(half)]
    return [Vector((x, y, z)) for y, z in pts]


def apc(font=None, label="E-11"):
    """8x8 tekerlekli zırhlı personel taşıyıcı (Stryker/LAV sınıfı, genel tasarım)."""
    M = mats()
    paint, dark = M["paint"], M["paint_dark"]
    body = _empty("apc_body", (0, 0, 0), body=True)
    parts = [body]

    # --- gövde: V tabanlı, sponsonlu, eğik ön zırhlı loft
    st = [(-3.50, .80, .55, .84, .86, .92, 1.20, 1.30, 1.62, 1.08, 2.00, 2.01),
          (-3.42, .70, .60, .76, .92, .86, 1.20, 1.36, 1.68, 1.12, 2.10, 2.11),
          (2.30, .66, .60, .74, .92, .86, 1.20, 1.36, 1.68, 1.12, 2.10, 2.11),
          (2.95, .66, .60, .74, .92, .86, 1.20, 1.36, 1.60, 1.10, 1.78, 1.79),
          (3.38, .74, .55, .80, .90, .90, 1.18, 1.30, 1.36, 1.08, 1.42, 1.43),
          (3.52, .92, .40, .95, .80, 1.00, 1.14, 1.18, 1.22, 1.00, 1.28, 1.29)]
    vb = VB()
    vb.loft([_hull_ring(*s) for s in st], paint)
    vb.build("apc_hull", body, bevel=0.02)

    vb = VB()
    # cıvatalı ek zırh panelleri (iki yan, sponson duvarı üzerinde)
    for sy in (-1, 1):
        for xc in (-2.85, -1.66, -0.47, 0.72, 1.86):
            y = sy * (1.36 + 0.016)
            vb.box((1.13, 0.03, 0.4), (xc, y, 1.44), paint)
            bolts(vb, [(xc + dx, y + sy * 0.017, 1.44 + dz) for dx in (-0.51, -0.17, 0.17, 0.51)
                       for dz in (-0.16, 0.16)], "y", M["steel"])
        # çamurluk lastikleri
        for xm in (-1.72, 1.6):
            vb.box((0.03, 0.4, 0.42), (xm, sy * 1.14, 0.98), M["rubber"])
        # yan aynalar
        vb.box((0.04, 0.3, 0.04), (3.0, sy * 1.42, 1.7), M["steel"], (0, 0, sy * 0.3))
        vb.box((0.05, 0.2, 0.26), (3.0, sy * 1.6, 1.78), M["black"])
        # farlar: kafesli gövde + mercek
        for yy in (0.62, 0.86):
            vb.box((0.16, 0.2, 0.15), (3.38, sy * yy, 1.3), dark)
            vb.box((0.012, 0.15, 0.1), (3.465, sy * yy, 1.3), M["head"])
            for dz in (-0.04, 0.0, 0.04):
                vb.box((0.012, 0.21, 0.008), (3.48, sy * yy, 1.3 + dz), M["steel"])
        # çeki kancaları
        vb.box((0.16, 0.06, 0.06), (3.55, sy * 0.55, 0.98), M["steel"])
        vb.box((0.06, 0.06, 0.14), (3.62, sy * 0.55, 1.03), M["steel"])
        # arka stop lambaları
        vb.box((0.02, 0.14, 0.08), (-3.52, sy * 0.95, 1.55), M["tail"])
        vb.box((0.02, 0.08, 0.08), (-3.52, sy * 0.95, 1.43), M["amber"])
        # eğik yan yüzeyde küçük el tutamakları
        for xh in (-2.0, 0.2):
            vb.box((0.32, 0.03, 0.03), (xh, sy * 1.27, 1.86), M["steel"])
    # arka rampa çerçevesi ve kapı tutamağı
    vb.box((0.03, 1.66, 0.05), (-3.51, 0, 1.92), dark)
    vb.box((0.03, 1.66, 0.05), (-3.51, 0, 0.98), dark)
    for sy in (-1, 1):
        vb.box((0.03, 0.05, 0.98), (-3.51, sy * 0.81, 1.45), dark)
    vb.box((0.05, 0.2, 0.04), (-3.53, 0.3, 1.45), M["steel"])
    # tavan: kapaklar, periskoplar, motor ızgarası, egzoz
    vb.cyl(0.38, 0.38, 0.07, (-0.6, 0.45, 2.14), dark, segs=28)
    vb.box((0.12, 0.3, 0.06), (-0.98, 0.45, 2.15), M["steel"])
    vb.box((1.0, 0.8, 0.05), (-2.4, 0.0, 2.13), dark)
    vb.cyl(0.3, 0.3, 0.06, (2.05, 0.55, 2.13), dark, segs=24)
    for k, dy in enumerate((-0.2, 0.0, 0.2)):
        vb.box((0.1, 0.16, 0.08), (2.38, 0.55 + dy, 2.06), M["glass"], (0, -0.45, 0))
    vb.box((0.9, 0.72, 0.04), (1.2, -0.55, 2.13), dark)
    for k in range(9):
        vb.box((0.06, 0.68, 0.03), (0.82 + k * 0.095, -0.55, 2.16), dark, (0, 0.5, 0))
    vb.cyl(0.07, 0.07, 0.55, (1.25, -1.2, 1.95), M["steel"], (math.pi / 2, 0, 0.0), segs=12)
    vb.box((0.5, 0.06, 0.25), (1.25, -1.33, 1.92), dark)
    # yan eğimde kazma-kürek
    vb.box((1.1, 0.04, 0.05), (-1.0, 1.25, 1.83), M["wood"], (0.55, 0, 0))
    vb.box((0.28, 0.02, 0.22), (-0.38, 1.24, 1.83), M["steel"], (0.55, 0, 0))
    vb.build("apc_details", body, bevel=0.006)

    # --- uzaktan kumandalı silah kulesi (M2 .50 + sensör + sis bombası atar)
    vb = VB()
    vb.cyl(0.46, 0.46, 0.12, (0, 0, 0.06), dark, segs=32)
    vb.box((0.72, 0.62, 0.3), (0.0, 0, 0.27), paint)
    vb.box((0.55, 0.14, 0.17), (0.18, 0.0, 0.5), M["gun"])                 # gövde
    vb.cyl(0.042, 0.042, 0.42, (0.66, 0.0, 0.52), M["gun"], (0, math.pi / 2, 0), segs=14)  # namlu ceketi
    for k in range(6):
        vb.cyl(0.046, 0.046, 0.025, (0.5 + k * 0.06, 0.0, 0.52), M["gun"], (0, math.pi / 2, 0), segs=14)
    vb.cyl(0.024, 0.022, 0.75, (1.22, 0.0, 0.52), M["gun"], (0, math.pi / 2, 0), segs=12)
    vb.cyl(0.034, 0.034, 0.09, (1.63, 0.0, 0.52), M["gun"], (0, math.pi / 2, 0), segs=12)
    vb.box((0.3, 0.16, 0.2), (0.0, 0.25, 0.48), M["paint_dark"])          # mühimmat kutusu
    vb.box((0.3, 0.24, 0.24), (0.12, -0.36, 0.5), paint)                   # sensör kutusu
    vb.box((0.02, 0.18, 0.16), (0.27, -0.36, 0.5), M["glass"])
    vb.cyl(0.04, 0.04, 0.02, (0.285, -0.31, 0.5), M["glass"], (0, math.pi / 2, 0), segs=16)
    for sy in (-1, 1):
        for k in range(4):
            vb.cyl(0.04, 0.04, 0.2, (0.15, sy * (0.38 + 0.08 * (k % 2)), 0.2 + 0.08 * (k // 2)), dark,
                   (0, math.radians(60), sy * 0.35), segs=10)
    vb.build("apc_rws", body, (-0.35, -0.15, 2.12), bevel=0.005)

    # --- tepe lambası, antenler, bidon noktaları, yazı
    bb = VB()
    bb.cyl(0.08, 0.08, 0.04, (0, 0, 0.02), M["black"], segs=16)
    bb.cyl(0.075, 0.06, 0.13, (0, 0, 0.1), M["beacon"], segs=16)
    bea = bb.build("beacon", body, (-2.7, -0.75, 2.12))
    bea["beacon"] = True
    for sy in (-1, 1):
        ab = VB()
        ab.box((0.1, 0.1, 0.12), (0, 0, 0.06), M["black"])
        ab.cyl(0.006, 0.003, 2.3, (0, 0, 1.27), M["black"], segs=6)
        ant = ab.build("antenna", body, (-3.15, sy * 0.95, 2.05))
        ant["antenna"] = True
    for dy in (-0.45, 0.45):
        _empty("jerrycan_pt", (-3.62, dy, 1.0), body, jerrycan=True)
    if label:
        text_decal(body, label, (2.0, -1.395, 1.33), (math.pi / 2, 0, 0), 0.2, font)
        text_decal(body, label, (2.0, 1.395, 1.33), (math.pi / 2, 0, math.pi), 0.2, font)
        text_decal(body, "MTF", (-1.6, -1.395, 1.33), (math.pi / 2, 0, 0), 0.16, font)
    for sy in (-1, 1):
        for yy in (0.62, 0.86):
            _empty("headlight", (3.5, sy * yy, 1.3), body, headlight=True)

    # --- 8 tekerlek
    for i, x in enumerate((-2.45, -1.15, 0.85, 2.15)):
        for sy in (-1, 1):
            parts.append(wheel(f"apc_wheel_{i}{'LR'[sy > 0]}", loc=(x, sy * 1.14, 0.56), mirror=sy < 0))
    return parts


# --------------------------------------------------------------------------- 6x6 kamyon

def _arch(y0, z0, z1, r, n=6):
    """Branda kesiti: iki yan duvar ve yuvarlatılmış üst köşeler (soldan sağa)."""
    pts = [(-y0, z0), (-y0, z1 - r)]
    for k in range(1, n):
        a = math.pi - (math.pi / 2) * k / n
        pts.append((-y0 + r + r * math.cos(a), z1 - r + r * math.sin(a)))
    pts += [(-y0 + r, z1), (y0 - r, z1)]
    for k in range(1, n):
        a = math.pi / 2 - (math.pi / 2) * k / n
        pts.append((y0 - r + r * math.cos(a), z1 - r + r * math.sin(a)))
    pts += [(y0, z1 - r), (y0, z0)]
    return pts


def truck(font=None, label="MTF"):
    """6x6 askerî kamyon (FMTV sınıfı, genel tasarım): kabin, ahşap kasa, kemerli branda."""
    M = mats()
    paint, dark = M["paint"], M["paint_dark"]
    body = _empty("truck_body", (0, 0, 0), body=True)
    parts = [body]
    vb = VB()
    # şasi
    for sy in (-1, 1):
        vb.box((7.0, 0.1, 0.28), (0.1, sy * 0.45, 0.98), dark)
    for x in (-3.0, -1.9, -0.5, 1.0, 2.4):
        vb.box((0.1, 0.9, 0.18), (x, 0, 0.98), dark)
    # kabin (önden bakışta hafif eğik ön cam)
    vb.prism([(1.95, 1.25), (3.75, 1.25), (3.8, 2.05), (3.64, 2.86), (3.46, 2.97), (1.95, 2.97)], 2.4, paint)
    for sy in (-1, 1):
        vb.box((0.02, 1.02, 0.66), (3.72, sy * 0.56, 2.45), M["glass"], (0, -0.197, 0))
        vb.box((0.86, 0.02, 0.56), (2.95, sy * 1.205, 2.42), M["glass"])        # yan cam
        vb.box((0.02, 0.025, 1.45), (2.48, sy * 1.21, 1.95), dark)              # kapı çizgileri
        vb.box((0.02, 0.025, 1.45), (3.5, sy * 1.21, 1.95), dark)
        vb.box((0.14, 0.03, 0.03), (2.62, sy * 1.225, 1.92), M["steel"])        # kapı kolu
        vb.box((0.42, 0.24, 0.04), (2.95, sy * 1.15, 1.02), M["steel"])         # basamaklar
        vb.box((0.42, 0.24, 0.04), (2.95, sy * 1.15, 0.72), M["steel"])
        vb.cyl_between((3.62, sy * 1.2, 2.6), (3.62, sy * 1.5, 2.65), 0.015, M["steel"])  # ayna kolu
        vb.box((0.05, 0.24, 0.42), (3.6, sy * 1.55, 2.42), M["black"])
        vb.box((0.08, 0.3, 0.16), (3.98, sy * 0.95, 1.18), dark)                # far yuvası
        vb.box((0.01, 0.22, 0.11), (4.025, sy * 0.95, 1.18), M["head"])
        vb.box((0.03, 0.06, 0.05), (3.6, sy * 0.9, 2.99), M["amber"])
        vb.box((0.05, 0.1, 0.12), (-3.7, sy * 1.05, 1.15), M["tail"])           # stop
    vb.box((0.03, 0.06, 0.05), (3.6, 0, 2.99), M["amber"])
    # ızgara ve tampon
    vb.box((0.04, 1.6, 0.55), (3.79, 0, 1.68), dark)
    for k in range(12):
        vb.box((0.03, 0.035, 0.5), (3.815, -0.72 + k * 0.131, 1.68), M["black"])
    vb.box((0.26, 2.5, 0.3), (3.92, 0, 1.05), paint)
    for sy in (-1, 1):
        vb.box((0.14, 0.06, 0.06), (4.08, sy * 0.5, 0.95), M["steel"])
        vb.box((0.06, 0.06, 0.14), (4.14, sy * 0.5, 1.0), M["steel"])
    # şnorkel, egzoz, yakıt tankı, akü kutusu, stepne
    vb.cyl(0.1, 0.1, 1.55, (3.3, -1.3, 2.3), dark, segs=16)
    vb.cyl(0.13, 0.13, 0.16, (3.3, -1.3, 3.12), M["black"], segs=16)
    vb.cyl(0.075, 0.075, 2.0, (1.85, 1.0, 2.0), M["steel"], segs=12)
    vb.cyl(0.29, 0.29, 1.0, (0.6, -1.0, 0.98), dark, (0, math.pi / 2, 0), segs=24)
    vb.box((0.7, 0.45, 0.4), (0.6, 1.0, 0.98), dark)
    vb.cyl(0.4, 0.4, 0.06, (0.2, 1.0, 0.98), M["steel"], (0, math.pi / 2, 0), segs=20)
    # kasa: taban, ahşap kenarlar, ön pano
    vb.box((5.3, 2.45, 0.12), (-0.95, 0, 1.3), dark)
    for sy in (-1, 1):
        for k in range(3):
            vb.box((5.3, 0.04, 0.17), (-0.95, sy * 1.21, 1.47 + k * 0.19), M["wood"])
        for x in (-3.5, -2.2, -0.9, 0.4, 1.6):
            vb.box((0.06, 0.06, 0.62), (x, sy * 1.235, 1.65), M["steel"])       # dikmeler
    vb.box((0.05, 2.45, 0.62), (1.67, 0, 1.65), M["wood"])
    # branda: kemerlerde dolgun, aralarda hafif sarkık
    rings = []
    xs = [-3.6 + i * 0.1325 for i in range(41)]
    for x in xs:
        sag = 0.03 * (0.5 - 0.5 * math.cos(2 * math.pi * ((x + 3.6) / 1.325)))
        rings.append([Vector((x, y * (1 - sag * 0.3), z - sag * (z > 2.4))) for y, z in
                      _arch(1.24, 1.9, 3.15, 0.38)])
    vb.loft(rings, M["canvas"])
    vb.cyl(0.09, 0.09, 2.3, (-3.62, 0, 2.95), M["canvas"], (math.pi / 2, 0, 0), segs=12)  # sarılı arka kapak
    for x in (-3.0, -1.6, -0.2, 1.2):
        for sy in (-1, 1):
            vb.box((0.03, 0.02, 0.3), (x, sy * 1.25, 2.0), M["black"])           # bağlama ipleri
    # tavan taret halkası
    vb.cyl(0.42, 0.42, 0.1, (2.7, 0.45, 3.02), dark, segs=28)
    vb.box((0.04, 2.5, 0.04), (-3.75, 0, 1.25), M["steel"])
    vb.build("truck_body_mesh", body, bevel=0.012)
    if label:
        text_decal(body, label, (2.75, -1.215, 1.6), (math.pi / 2, 0, 0), 0.22, font)
        text_decal(body, label, (2.75, 1.215, 1.6), (math.pi / 2, 0, math.pi), 0.22, font)
    for sy in (-1, 1):
        _empty("headlight", (4.05, sy * 0.95, 1.18), body, headlight=True)
    for i, x in enumerate((-2.65, -1.35, 2.4)):
        for sy in (-1, 1):
            parts.append(wheel(f"truck_wheel_{i}{'LR'[sy > 0]}", r=0.58, w=0.4, rim_r=0.34,
                               loc=(x, sy * 1.0, 0.58), mirror=sy < 0))
    return parts
