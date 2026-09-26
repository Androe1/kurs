"""Karakter katmanlarının Blender animasyonu ve render'ı (headless, bpy).

Kullanım (Blender'ın Python modülüyle; `blender -b -P anim.py -- ...` ile de aynıdır):
    python blender/anim.py --char 1 --mode blocking --frames 10,25 --out renders/blocking
    python blender/anim.py --char 2 --mode final --out renders/char2

Çıktı: her kare için şeffaf arka planlı RGBA PNG (+ ayrı alpha/silüet PNG) ve
kompozitörün kullandığı meta.json (her karede yüzün ve gövde ortasının ekran
konumu, karakterin ekrandaki hızı, yüz ifadesi).

Kareler pencere başına göredir (0 = pencerenin ilk karesi):
  karakter 1: sahne kareleri 215-257 (3.58-4.28 s), 42 kare
  karakter 2: sahne kareleri 257-306 (4.28-5.10 s), 49 kare
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r15_rig  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FPS = 60
CHARS = {
    1: {"folder": ROOT / "characters/r15/androe", "name": "androe", "start": 215, "frames": 42},
    2: {"folder": ROOT / "characters/r15/androeofficial", "name": "official", "start": 257, "frames": 49},
}

# ----------------------------------------------------------------------------
# Pozlar. Açılar derece, kemik yerel Euler XYZ (R15 rig'inde):
#   kol/bacak (aşağı bakan kemik): X- öne (kameraya) salla, X+ geriye;
#       sol uzuvda Z- dışa/yukarı aç, sağ uzuvda Z+ dışa/yukarı aç; Y kendi ekseninde burulma
#   dirsek (LowerArm): X- büker (ön kol öne katlanır); diz (LowerLeg): X+ büker
#   gövde/kafa (yukarı bakan kemik): X+ öne eğil, X- geriye; Y+ sola dön (sol omuz geri);
#       Z+ karakterin sağına (ekranın soluna) yan eğil
# Kök (armature nesnesi): konum stud, dönüş derece (dünya XYZ), "sq" squash-stretch (Y boyu).
# Karakter kameraya (-Y) bakar; ekranın sağı +X'tir.
# ----------------------------------------------------------------------------

# Pozlar üç katmandan oluşur:
#   root : kök (armature) konumu stud, dönüşü derece (dünya XYZ), "sq" squash-stretch (%12'ye kadar)
#   fk   : gövde, kafa, el, ayak ve pelerin kemiklerinin yerel Euler açıları (derece)
#   ik   : kol ve bacak IK hedefleri. ("scr", u, v, d) = ekranda (u, v) noktası (0-1, sol üst),
#          lensten d stud uzakta; ("chr", x, y, z) = karakterin kök uzayında nokta.
#          *Pole = dirseğin / dizin yöneldiği nokta (kök uzayında).
# Kemik yerel eksenleri (R15 rig'inde): gövde/kafa X+ öne eğil, Y+ sola dön, Z+ karakterin sağına
# (ekranın soluna) yan eğil. Karakter kameraya (-Y) bakar; ekranın sağı +X.
POSES = {
    # ---------------- karakter 1: vuruş pozu (kol lense uzanır, C çizgisi, kafa ters yöne)
    "c1_hit": {
        "root": {"loc": (0.0, 0.0, 0.2), "rot": (10, 0, -14), "sq": 1.0},
        "fk": {"LowerTorso": (0, 0, 10), "UpperTorso": (16, -18, -14), "Head": (-10, 8, 18),
               "LeftHand": (0, 0, -15), "RightHand": (15, 0, 0), "LeftFoot": (-15, 0, 0), "RightFoot": (25, 0, 0),
               "Cape1": (-20, 0, 0), "Cape2": (-8, 0, 0), "Cape3": (-4, 0, 0)},
        "ik": {"LeftHand": ("scr", 0.80, 0.26, 4.2), "LeftHandPole": ("chr", 2.5, 0.5, 2.0),
               "RightHand": ("chr", -2.0, 1.3, 3.9), "RightHandPole": ("chr", -1.5, -1.5, 3.0),
               "LeftFoot": ("chr", 0.8, -1.1, 0.9), "LeftFootPole": ("chr", 0.6, -3.0, 1.5),
               "RightFoot": ("chr", -0.6, 0.9, 0.45), "RightFootPole": ("chr", -0.6, -3.0, 1.0)},
        "face": "surprised",
    },
    # ---------------- karakter 1: hold ortası (oturmuş, kameraya hafif kaymış, bilek vurgusu)
    "c1_hold": {
        "root": {"loc": (0.0, -0.3, 0.12), "rot": (8, 0, -11), "sq": 1.0},
        "fk": {"LowerTorso": (0, 0, 8), "UpperTorso": (12, -14, -11), "Head": (-8, 5, 15),
               "LeftHand": (-15, 0, -28), "RightHand": (18, 0, 0), "LeftFoot": (-12, 0, 0), "RightFoot": (22, 0, 0),
               "Cape1": (-12, 0, 0), "Cape2": (-6, 0, 0), "Cape3": (-3, 0, 0)},
        "ik": {"LeftHand": ("scr", 0.77, 0.29, 4.6), "LeftHandPole": ("chr", 2.5, 0.5, 2.0),
               "RightHand": ("chr", -1.9, 1.2, 3.6), "RightHandPole": ("chr", -1.5, -1.5, 3.0),
               "LeftFoot": ("chr", 0.75, -1.0, 0.85), "LeftFootPole": ("chr", 0.6, -3.0, 1.5),
               "RightFoot": ("chr", -0.6, 0.8, 0.45), "RightFootPole": ("chr", -0.6, -3.0, 1.0)},
        "face": "grin",
    },
    # ---------------- karakter 2: vuruş pozu (kameraya ≤20° eğik, kollar asimetrik, bir ayak şeritte)
    "c2_hit": {
        "root": {"loc": (0.0, 0.0, 0.0), "rot": (0, 0, 16), "sq": 1.0},
        "fk": {"LowerTorso": (0, 0, -6), "UpperTorso": (18, 14, 8), "Head": (-10, -10, -12),
               "RightHand": (0, 0, 15), "LeftHand": (-15, 0, 0), "RightFoot": (0, 0, 0), "LeftFoot": (30, 0, 0),
               "Cape1": (-24, 0, 4), "Cape2": (-10, 0, 0), "Cape3": (-5, 0, 0)},
        "ik": {"RightHand": ("chr", -2.1, 0.9, 5.4), "RightHandPole": ("chr", -2.0, 2.0, 3.5),
               "LeftHand": ("scr", 0.72, 0.42, 4.6), "LeftHandPole": ("chr", 2.0, 0.0, 1.5),
               "RightFoot": ("chr", -0.5, -0.1, 0.36), "RightFootPole": ("chr", -0.5, -3.0, 1.2),
               "LeftFoot": ("chr", 0.7, 1.3, 1.1), "LeftFootPole": ("chr", 0.6, -3.0, 1.5)},
        "face": "grin",
    },
    # ---------------- karakter 2: hold ortası
    "c2_hold": {
        "root": {"loc": (0.0, -0.2, 0.0), "rot": (0, 0, 13), "sq": 1.0},
        "fk": {"LowerTorso": (0, 0, -5), "UpperTorso": (14, 11, 6), "Head": (-8, -12, -9),
               "RightHand": (0, 0, 18), "LeftHand": (-18, 0, 0), "RightFoot": (0, 0, 0), "LeftFoot": (26, 0, 0),
               "Cape1": (-14, 0, 3), "Cape2": (-6, 0, 0), "Cape3": (-3, 0, 0)},
        "ik": {"RightHand": ("chr", -2.0, 0.8, 5.2), "RightHandPole": ("chr", -2.0, 2.0, 3.5),
               "LeftHand": ("scr", 0.70, 0.44, 5.0), "LeftHandPole": ("chr", 2.0, 0.0, 1.5),
               "RightFoot": ("chr", -0.5, -0.1, 0.36), "RightFootPole": ("chr", -0.5, -3.0, 1.2),
               "LeftFoot": ("chr", 0.7, 1.2, 1.0), "LeftFootPole": ("chr", 0.6, -3.0, 1.5)},
        "face": "determined",
    },
}

# Blocking: anahtar pozların pencere içindeki kareleri (stepped)
BLOCKING = {1: [(10, "c1_hit"), (25, "c1_hold")], 2: [(16, "c2_hit"), (33, "c2_hold")]}

# Kamera: 22 mm, karaktere çok yakın, hafif alttan (göğüs hizasının altından yukarı bakar)
CAMERAS = {
    1: {"lens": 22, "loc": (0.3, -9.2, 1.7), "target": (0.1, 0.0, 3.1)},
    2: {"lens": 22, "loc": (-0.3, -9.0, 1.5), "target": (0.0, 0.0, 3.0)},
}

IK_CHAINS = {"LeftHand": "LeftLowerArm", "RightHand": "RightLowerArm",
             "LeftFoot": "LeftLowerLeg", "RightFoot": "RightLowerLeg"}


def look_rotation(loc, target):
    d = Vector(target) - Vector(loc)
    return d.to_track_quat("-Z", "Y").to_euler()


def setup_scene(char_id, res=(1920, 1080), engine="BLENDER_EEVEE_NEXT"):
    r15_rig.reset_scene()
    info = CHARS[char_id]
    ch = r15_rig.R15(info["folder"], info["name"])
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = True
    sc.render.engine = engine
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    if engine == "BLENDER_EEVEE_NEXT":
        sc.eevee.taa_render_samples = 32
        sc.eevee.use_gtao = True
        sc.eevee.gtao_distance = 0.6
    else:
        sc.cycles.samples = 32
        sc.cycles.use_denoising = True

    # ışıklar: üst-ön yumuşak key, güçlü arka kontur (rim), alçak dolgu; açık dünya
    def light(name, kind, loc, target, energy, size=None, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if size is not None:
            ld.size = size
        ob = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = look_rotation(loc, target)
        return ob

    light("key", "AREA", (-2.5, -5.0, 7.5), (0, 0, 3.2), 900, size=5)
    light("rim", "AREA", (3.5, 5.0, 6.0), (0, 0, 3.5), 1400, size=2.5)
    light("rim2", "AREA", (-4.0, 4.0, 4.5), (0, 0, 3.0), 700, size=2.5)
    light("fill", "AREA", (1.5, -6.0, 1.0), (0, 0, 2.5), 180, size=6)
    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    c = CAMERAS[char_id]
    cam_d.lens = c["lens"]
    cam_d.sensor_width = 36
    cam.location = c["loc"]
    cam.rotation_euler = look_rotation(c["loc"], c["target"])
    setup_ik(ch)
    return ch, cam


def setup_ik(ch):
    """Kollara ve bacaklara pole target'lı IK (zincir 2: üst + alt kemik); hedefler boş nesneler."""
    sc = bpy.context.scene
    ch.ik = {}
    for end, bone in IK_CHAINS.items():
        for key in (end, end + "Pole"):
            e = bpy.data.objects.new(f"{ch.name}_{key}", None)
            e.empty_display_size = 0.2
            sc.collection.objects.link(e)
            ch.ik[key] = e
        pb = ch.arm.pose.bones[bone]
        con = pb.constraints.new("IK")
        con.target = ch.ik[end]
        con.pole_target = ch.ik[end + "Pole"]
        con.pole_angle = math.radians(-90)
        con.chain_count = 2
        con.use_tail = True


def screen_point(cam, u, v, dist):
    """Kameradan bakınca ekranın (u, v) noktasında (0-1, sol üst), lensten dist uzaklıktaki dünya noktası."""
    sc = bpy.context.scene
    cd = cam.data
    aspect = sc.render.resolution_y / sc.render.resolution_x
    half_w = (cd.sensor_width / 2) / cd.lens
    x = (u - 0.5) * 2 * half_w
    y = (0.5 - v) * 2 * half_w * aspect
    d = Vector((x, y, -1.0)).normalized() * dist
    return cam.matrix_world @ d


def apply_pose(ch, cam, pose, frame, interp="CONSTANT"):
    arm = ch.arm
    r = pose["root"]
    arm.location = r["loc"]
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = [math.radians(a) for a in r["rot"]]
    arm.keyframe_insert("location", frame=frame)
    arm.keyframe_insert("rotation_euler", frame=frame)
    bpy.context.view_layer.update()
    s = r.get("sq", 1.0)
    root = arm.pose.bones["HumanoidRootPart"]
    root.scale = (1 / math.sqrt(s), s, 1 / math.sqrt(s))             # hacmi koruyan squash & stretch
    root.keyframe_insert("scale", frame=frame)
    fk = pose.get("fk", {})
    for pb in arm.pose.bones:
        if pb.name == "HumanoidRootPart":
            continue
        e = fk.get(pb.name, (0, 0, 0))
        pb.rotation_quaternion = Euler([math.radians(a) for a in e], "XYZ").to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    for key, spec in pose.get("ik", {}).items():
        e = ch.ik[key]
        if spec[0] == "scr":
            e.location = screen_point(cam, *spec[1:])
        else:
            e.location = arm.matrix_world @ Vector(spec[1:])
        e.keyframe_insert("location", frame=frame)
    for ob in [arm] + list(ch.ik.values()):
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    if int(round(kp.co.x)) == frame:
                        kp.interpolation = interp


def screen_meta(ch, cam, frame):
    """Yüzün ve gövde ortasının ekran konumu (0-1, sol üst köşe başlangıç)."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    sc.frame_set(frame)
    out = {}
    for key, bone, off in (("face", "Head", 0.55), ("chest", "UpperTorso", 0.5)):
        pb = ch.arm.pose.bones[bone]
        p = ch.arm.matrix_world @ (pb.head + (pb.tail - pb.head) * off)
        v = world_to_camera_view(sc, cam, p)
        out[key] = (v.x, 1 - v.y)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", type=int, required=True)
    ap.add_argument("--mode", default="blocking", choices=("blocking",))
    ap.add_argument("--frames", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--engine", default="BLENDER_EEVEE_NEXT")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    res = tuple(int(v) for v in args.res.split("x"))
    ch, cam = setup_scene(args.char, res, args.engine)
    keys = BLOCKING[args.char]
    for f, name in keys:
        apply_pose(ch, cam, POSES[name], f)
    frames = [int(f) for f in args.frames.split(",")] if args.frames else list(range(CHARS[args.char]["frames"] + 1))
    out = Path(args.out or ROOT / "renders" / f"char{args.char}")
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "meta.json"
    meta = {int(k): v for k, v in json.loads(meta_path.read_text()).items()} if meta_path.exists() else {}
    sc = bpy.context.scene
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = str(out / f"{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        pose_name = max((k for k in keys if k[0] <= f), default=keys[0])[1]
        cur = screen_meta(ch, cam, f)
        prev = screen_meta(ch, cam, f - 1)
        speed = math.hypot(cur["chest"][0] - prev["chest"][0], cur["chest"][1] - prev["chest"][1])
        meta[f] = {**cur, "speed": speed, "expr": POSES[pose_name].get("face"),
                   "mask_band": args.char == 2 and f <= 14}
        # ayrı silüet (alpha) katmanı
        img = bpy.data.images.load(sc.render.filepath)
        px = list(img.pixels)
        alpha = [a for a in px[3::4]]
        sil = bpy.data.images.new(f"sil{f}", img.size[0], img.size[1], alpha=False)
        sil.pixels = [v for a in alpha for v in (a, a, a, 1.0)]
        sil.filepath_raw = str(out / f"{f:03d}_alpha.png")
        sil.file_format = "PNG"
        sil.save()
        bpy.data.images.remove(img)
        bpy.data.images.remove(sil)
    meta_path.write_text(json.dumps({str(k): v for k, v in sorted(meta.items())}, indent=1))


if __name__ == "__main__":
    main()
