"""Karakter animasyonu: anahtar pozlar + fizik katmanları, kamera ve render (headless bpy).

    python blender/animate.py --char 1 --preview      # hızlı önizleme (Workbench, 640x360)
    python blender/animate.py --char 1                # final: EEVEE, 1920x1080, gerçek motion blur

Anahtar pozlar (vuruş ve hold) blender/fit_keyposes.py ile referansın eklem
noktalarından çözülür (keyposes.json). Bu dosya aralarını ve öncesini/sonrasını
fizikle kurar:

  1. Kök yörüngesi (trambolin): alttan hızla fırlar, tepeye yaklaşırken yavaşlar,
     hafifçe aşıp oturur; asılıyken çok yavaş çöker (moving hold); düşmeden önce
     küçük bir toplanma (anticipation) ve ardından hızlanarak düşer.
  2. Poz eğrileri: her kemik quaternion'u anahtarlar arasında monoton kübik eğriyle
     (PCHIP, log uzayında) geçer - anahtarı istemsizce aşmaz; aşma/oturma
     ayrı anahtarlarla verilir. Kemiklere kademeli gecikme (lead & follow):
     kök -> gövde -> omuz -> kol -> el, kalça -> bacak -> ayak, en son kafa.
  3. Sürükleme (drag): kol ve bacaklar kökün düşey hızına sönümlü yayla tepki verir;
     yükselirken aşağıda kalır, tepede süzülüp yetişir, düşerken yukarı kalkar
     (dünya uzayında yerçekimi yönüne doğru döndürülür, alt uzuv ekstra gecikmeli).
  4. Pomni: asılıyken kollar yüzer gibi sırayla çırpar. Caine: havada kendi sağına döner.
  5. Pelerin: üç kemiklik zincir, düşey hıza gecikmeli yay (düşerken havalanır).
  6. Squash & stretch: kök kemiğinde hacmi koruyan ölçek (en fazla %12).
  7. Kamera: 22 mm, hafif alttan; yavaş yaklaşma (~%6), el kamerası titremesi (~0.4°),
     vuruş karesinde 3 karelik sarsıntı.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation as R

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anim  # noqa: E402
import posefit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FPS = 60
KEYPOSES = json.loads((Path(__file__).with_name("keyposes.json")).read_text())

# kemik gecikmeleri (kare): lead & follow
DELAY = {"HumanoidRootPart": 0, "LowerTorso": 0.0, "UpperTorso": 0.7, "Head": 2.2,
         "LeftUpperArm": 1.2, "RightUpperArm": 1.2, "LeftLowerArm": 2.0, "RightLowerArm": 2.0,
         "LeftHand": 2.8, "RightHand": 2.8, "LeftUpperLeg": 1.0, "RightUpperLeg": 1.0,
         "LeftLowerLeg": 1.8, "RightLowerLeg": 1.8, "LeftFoot": 2.6, "RightFoot": 2.6,
         "Cape1": 0, "Cape2": 0, "Cape3": 0}


# ---------------------------------------------------------------- poz yardımcıları

class Pose:
    """Kök (konum, dönüş) + kemik quaternion'ları (scipy sırası x,y,z,w)."""

    def __init__(self, loc, rot, quats):
        self.loc = np.asarray(loc, float)
        self.rot = rot                    # scipy Rotation
        self.q = quats                    # {kemik: Rotation}

    @staticmethod
    def from_key(name):
        k = KEYPOSES[name]
        quats = {b: R.from_quat([q[1], q[2], q[3], q[0]]) for b, q in k["quat"].items()}
        return Pose(k["loc"], R.from_euler("xyz", k["rot"], degrees=True), quats)

    def bone(self, b):
        return self.q.get(b, R.identity())

    def blend(self, other, t, bones):
        from scipy.spatial.transform import Slerp
        def sl(a, b):
            return Slerp([0, 1], R.concatenate([a, b]))([t])[0]
        return Pose(self.loc * (1 - t) + other.loc * t, sl(self.rot, other.rot),
                    {b: sl(self.bone(b), other.bone(b)) for b in bones})

    def moved(self, dloc=(0, 0, 0), world_rot=None):
        rot = self.rot if world_rot is None else R.from_euler("xyz", world_rot, degrees=True) * self.rot
        return Pose(self.loc + np.asarray(dloc, float), rot, dict(self.q))


def rest(bones):
    return Pose((0, 0, 0), R.identity(), {b: R.identity() for b in bones})


class Track:
    """Anahtarlar arası PCHIP; dönüşler ilk anahtara göre log uzayında (süreklilik korunur)."""

    def __init__(self, frames, rots=None, vecs=None):
        self.f = np.asarray(frames, float)
        if rots is not None:
            self.base = rots[0]
            rv = []
            prev = None
            for r in rots:
                v = (self.base.inv() * r).as_rotvec()
                if prev is not None and np.dot(v, prev) < 0 and np.linalg.norm(v) > 2.5:
                    v = v - 2 * math.pi * v / np.linalg.norm(v)
                rv.append(v)
                prev = v
            self.p = PchipInterpolator(self.f, np.array(rv), axis=0, extrapolate=False)
            self.kind = "rot"
        else:
            self.p = PchipInterpolator(self.f, np.asarray(vecs, float), axis=0, extrapolate=False)
            self.kind = "vec"

    def __call__(self, f):
        f = min(max(f, self.f[0]), self.f[-1])
        v = self.p(f)
        return self.base * R.from_rotvec(v) if self.kind == "rot" else v

    def deriv(self, f):
        f = min(max(f, self.f[0]), self.f[-1])
        return self.p.derivative()(f)


# ---------------------------------------------------------------- koreografi

def choreo(char, bones):
    """(anahtarlar, squash anahtarları, vuruş karesi, özel katmanlar) döndürür."""
    Z = rest(bones)
    if char == 1:
        H, D = Pose.from_key("c1_hit"), Pose.from_key("c1_hold")
        keys = [
            (0, H.blend(Z, 0.45, bones).moved((2.2, 0.4, -7.5), (-30, 0, 20))),   # sağ alttan fırlar
            (5, H.blend(Z, 0.2, bones).moved((0.9, 0.15, -2.2), (-12, 0, 8))),
            (8, H.blend(Z, 0.05, bones).moved((0.15, 0.0, -0.25), (-2, 0, 1))),
            (9, H.moved((0.0, 0.0, 0.14))),                                         # hafif aşma
            (10, H.moved((0.0, 0.0, 0.08))),                                        # vuruş pozu
            (13, H),
            (16, H.blend(D, 0.3, bones)),                                           # oturma
            (25, D),                                                                # hold ortası
            (33, D.moved((0, -0.1, -0.12))),                                        # yavaşça çöker
            (36, D.blend(Z, 0.22, bones).moved((0, -0.15, 0.1))),                   # toplanma
            (39, D.moved((0.1, -0.35, -2.0), (12, 0, -4))),                         # düşüş (kameraya)
            (42, D.moved((0.3, -0.9, -7.5), (25, 0, -10))),
        ]
        squash = [(0, 1.1), (5, 1.08), (9, 0.95), (11, 1.02), (13, 1.0), (34, 1.0), (36, 0.93),
                  (38, 1.08), (42, 1.1)]
        return keys, squash, 10, {"swim": (12, 36), "float": (14, 34)}
    H, D = Pose.from_key("c2_hit"), Pose.from_key("c2_hold")
    keys = [
        (0, H.blend(Z, 0.55, bones).moved((-0.6, 0.3, -6.5), (0, 0, 55))),         # şeridin arkasından
        (6, H.blend(Z, 0.35, bones).moved((-0.3, 0.15, -2.6), (0, 0, 30))),        # kendi sağına dönerek
        (11, H.blend(Z, 0.12, bones).moved((0.0, 0.0, -0.6), (0, 0, 8))),
        (14, H.blend(Z, 0.02, bones).moved((0.0, 0.0, 0.12), (0, 0, 1))),          # aşma
        (16, H.moved((0.0, 0.0, 0.06))),                                           # vuruş pozu
        (19, H.moved((0.0, 0.0, -0.02), (0, 0, -2))),
        (22, H.blend(D, 0.3, bones)),                                              # oturma
        (33, D),                                                                   # hold ortası
        (40, D.moved((0.0, 0.0, -0.1), (0, 0, -12))),                             # kendi sağına dönmeye devam
        (43, D.blend(Z, 0.2, bones).moved((0.0, 0.0, 0.12), (0, 0, -15))),          # toplanma
        (46, D.moved((0.3, -0.4, -2.0), (0, 0, -24))),                             # süzülüp düşer
        (49, D.moved((0.6, -1.0, -6.5), (0, 0, -40))),
    ]
    squash = [(0, 1.1), (11, 1.05), (14, 0.95), (17, 1.03), (20, 1.0), (41, 1.0), (43, 0.93),
              (45, 1.08), (49, 1.1)]
    return keys, squash, 16, {"float": (20, 41)}


# ---------------------------------------------------------------- fizik katmanları

def spring(target, dt, freq, zeta):
    """Sönümlü yay: x'' = w²(hedef - x) - 2ζw x'  (alt adımlarla)."""
    w = 2 * math.pi * freq
    x = v = 0.0
    out = []
    sub = 10
    h = dt / sub
    for tg in target:
        for _ in range(sub):
            a = w * w * (tg - x) - 2 * zeta * w * v
            v += a * h
            x += v * h
        out.append(x)
    return np.array(out)


def world_rot_about(axis, deg):
    n = np.linalg.norm(axis)
    if n < 1e-9 or abs(deg) < 1e-6:
        return np.eye(3)
    return R.from_rotvec(axis / n * math.radians(deg)).as_matrix()


def bake(char, ch, cam, nframes):
    bones = [b.name for b in ch.arm.data.bones]
    sk = posefit.Skeleton(ch.arm)
    keys, squash, hit_f, extra = choreo(char, bones)
    fr = [k[0] for k in keys]
    loc_t = Track(fr, vecs=[k[1].loc for k in keys])
    if "float" in extra:
        a0, a1 = extra["float"]
        base_loc = loc_t

        class Floating:
            """Hold boyunca trambolin sonrası hafif süzülme: ~0.5 s periyotlu, sönen iniş-çıkış."""
            f = base_loc.f

            def __call__(self, fr_):
                return base_loc(fr_) + np.array([0, 0, self._bob(fr_)])

            def deriv(self, fr_):
                h = 0.01
                return base_loc.deriv(fr_) + np.array([0, 0, (self._bob(fr_ + h) - self._bob(fr_ - h)) / (2 * h)])

            @staticmethod
            def _bob(fr_):
                if not a0 < fr_ < a1:
                    return 0.0
                u = (fr_ - a0) / (a1 - a0)
                env = math.sin(math.pi * u)
                return 0.16 * env * math.sin(2 * math.pi * (fr_ - a0) / 30)

        loc_t = Floating()
    rot_t = Track(fr, rots=[k[1].rot for k in keys])
    bone_t = {b: Track(fr, rots=[k[1].bone(b) for k in keys]) for b in bones}
    sq_t = Track([s[0] for s in squash], vecs=[[s[1]] for s in squash])

    # kökün düşey hızı (stud/s) ve ondan yaylar (60 fps adımında hesap, ince ayrıntı için 4x)
    F = np.arange(-6, nframes + 1, 0.25)
    vz = np.array([loc_t.deriv(f)[2] * FPS for f in F])
    drag = spring(vz, 0.25 / FPS, freq=5.5, zeta=0.6)            # uzuvlar
    cape = spring(-vz, 0.25 / FPS, freq=2.4, zeta=0.35)          # pelerin (daha yumuşak)

    def at(series, f, delay):
        return float(np.interp(f - delay, F, series))

    # yukarı/aşağı yönünü bulmak için pelerin işareti: +X dönüşü kuyruğu geriye (+Y) mi atar?
    t0 = sk.point(sk.fk({}), "Cape1", 1.0)[1]
    t1 = sk.point(sk.fk({"Cape1": R.from_euler("x", 30, degrees=True).as_matrix()}), "Cape1", 1.0)[1]
    cape_sign = 1 if t1 > t0 else -1

    frames = []
    for f in range(nframes + 1):
        loc = loc_t(f)
        root = rot_t(f)
        basis = {b: bone_t[b](f - DELAY.get(b, 0)).as_matrix() for b in bones}
        W = root.as_matrix()
        pose = sk.fk(basis)

        def rotate_world(bone, Rw):
            # kemiği dünya uzayında Rw kadar döndür (kendi ekleminden)
            P = W @ pose[bone][:3, :3] @ np.linalg.inv(basis[bone])
            basis[bone] = np.linalg.inv(P) @ Rw @ P @ basis[bone]

        down = np.array([0, 0, -1.0])
        # 1) sürükleme: + değer uzvu yerçekimi yönüne (aşağı), - değer yukarı döndürür
        for limb, lower, dl in (("LeftUpperArm", "LeftLowerArm", 1.0), ("RightUpperArm", "RightLowerArm", 1.3),
                                ("LeftUpperLeg", "LeftLowerLeg", 1.6), ("RightUpperLeg", "RightLowerLeg", 1.9)):
            s = at(drag, f, dl)
            ang = 24 * math.tanh(s / 30)
            for bone, k in ((limb, 1.0), (lower, 0.45)):
                pose = sk.fk(basis)
                d = W @ pose[bone][:3, 1]                          # kemik yönü (dünyada)
                if bone == lower:
                    ang_b = 24 * math.tanh(at(drag, f, dl + 2.0) / 30) * k
                else:
                    ang_b = ang * k
                axis = np.cross(d, down)                           # d'yi aşağıya çeviren eksen
                rotate_world(bone, world_rot_about(axis, ang_b))
        # 2) Pomni: yüzer gibi çırpınan kollar (sırayla, gövdenin yan ekseni çevresinde)
        if "swim" in extra:
            a, b = extra["swim"]
            env = np.clip((f - a) / 4, 0, 1) * np.clip((b - f) / 4, 0, 1)
            if env > 0:
                pose = sk.fk(basis)
                side = W @ pose["UpperTorso"][:3, 0]
                for arm, lower, ph in (("LeftUpperArm", "LeftLowerArm", 0.0), ("RightUpperArm", "RightLowerArm", math.pi)):
                    w = 2 * math.pi * 3.0 / FPS
                    rotate_world(arm, world_rot_about(side, 24 * env * math.sin(w * f + ph)))
                    pose = sk.fk(basis)
                    rotate_world(lower, world_rot_about(side, 14 * env * math.sin(w * (f - 2.5) + ph)))
        # 3) pelerin: dünyada yerçekimiyle sarkar; hız yayıyla gecikmeli savrulur
        #    (yükselirken aşağı çekilir, düşerken havalanır). Zincir halkaları sırayla gecikir.
        pose = sk.fk(basis)
        tr = pose["UpperTorso"][:3, :3] @ np.linalg.inv(sk.rest["UpperTorso"][:3, :3])
        back = W @ tr @ np.array([0, 1.0, 0])
        feet = W @ tr @ np.array([0, 0, -1.0])
        for i, dl in ((1, 2.0), (2, 3.0), (3, 4.0)):
            lift = float(np.clip(math.tanh(at(cape, f, dl) / 30), -1, 1))       # + düşerken
            # sırta yakın, gövde boyunca ayaklara doğru; hafif yerçekimi, düşerken geriye havalanır
            want = feet + back * (0.2 + 0.9 * max(lift, 0)) + down * (0.3 + 0.4 * max(-lift, 0))
            pose = sk.fk(basis)
            d = W @ pose[f"Cape{i}"][:3, 1]
            want = want / (np.linalg.norm(want) + 1e-9)
            full = math.degrees(math.acos(float(np.clip(np.dot(d, want), -1, 1))))
            rotate_world(f"Cape{i}", world_rot_about(np.cross(d, want), 0.75 * full))
        # 4) hold sırasında kafada küçük nefes / bakış hareketi (2-3°)
        nod = R.from_euler("xyz", [2.0 * math.sin(f * 0.21), 2.5 * math.sin(f * 0.13 + 1), 0], degrees=True)
        basis["Head"] = basis["Head"] @ nod.as_matrix()
        sq = float(np.clip(sq_t(f)[0], 0.88, 1.12))
        frames.append((loc, root, basis, sq))
    return frames, hit_f


def camera_track(char, cam, nframes, hit_f):
    base = anim.CAMERAS[char]
    loc0, tgt = Vector(base["loc"]), Vector(base["target"])
    out = []
    for f in range(nframes + 1):
        u = f / nframes
        push = 0.06 * (3 * u * u - 2 * u ** 3)                     # yavaş yaklaşma (~%6)
        loc = loc0 + (tgt - loc0) * push
        rot = anim.look_rotation(loc, tgt)
        t = f / FPS
        hand = [0.35 * math.sin(2 * math.pi * 0.7 * t + 0.3) + 0.15 * math.sin(2 * math.pi * 1.9 * t),
                0.25 * math.sin(2 * math.pi * 1.1 * t + 1.7),
                0.3 * math.sin(2 * math.pi * 0.9 * t + 2.2) + 0.1 * math.sin(2 * math.pi * 2.3 * t)]
        k = f - hit_f
        shake = 1.1 * math.exp(-max(k, 0) / 1.6) * math.sin(k * 2.4) if 0 <= k <= 4 else 0.0
        e = Euler((rot.x + math.radians(hand[0] + shake), rot.y + math.radians(hand[1]),
                   rot.z + math.radians(hand[2] - 0.6 * shake)), "XYZ")
        out.append((loc, e))
    return out


def apply(ch, cam, frames, cams):
    arm = ch.arm
    arm.rotation_mode = "QUATERNION"
    for pb in arm.pose.bones:
        for con in pb.constraints:
            con.influence = 0.0                                    # IK FK'ye bake edildi
    for f, ((loc, root, basis, sq), (cl, ce)) in enumerate(zip(frames, cams)):
        arm.location = loc
        q = root.as_quat()
        arm.rotation_quaternion = (q[3], q[0], q[1], q[2])
        arm.keyframe_insert("location", frame=f)
        arm.keyframe_insert("rotation_quaternion", frame=f)
        for pb in arm.pose.bones:
            if pb.name == "HumanoidRootPart":
                pb.scale = (1 / math.sqrt(sq), sq, 1 / math.sqrt(sq))
                pb.keyframe_insert("scale", frame=f)
                continue
            q = R.from_matrix(basis[pb.name]).as_quat()
            pb.rotation_quaternion = (q[3], q[0], q[1], q[2])
            pb.keyframe_insert("rotation_quaternion", frame=f)
        cam.location = cl
        cam.rotation_euler = ce
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    for ob in (arm, cam):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"


def configure(preview):
    sc = bpy.context.scene
    sc.frame_start = 0
    if preview:
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "STUDIO"
        sc.display.shading.color_type = "TEXTURE"
        sc.render.resolution_x, sc.render.resolution_y = 640, 360
        sc.render.use_motion_blur = False
    else:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        sc.eevee.taa_render_samples = 32
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = 0.6
        sc.eevee.motion_blur_steps = 8
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", type=int, required=True)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--frames", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    n = anim.CHARS[args.char]["frames"]
    ch, cam = anim.setup_scene(args.char)
    configure(args.preview)
    frames, hit_f = bake(args.char, ch, cam, n)
    cams = camera_track(args.char, cam, n, hit_f)
    apply(ch, cam, frames, cams)
    sc = bpy.context.scene
    sc.frame_end = n
    out = Path(args.out or ROOT / ("renders_preview" if args.preview else "renders") / f"char{args.char}")
    out.mkdir(parents=True, exist_ok=True)
    todo = [int(x) for x in args.frames.split(",")] if args.frames else list(range(n + 1))
    meta_path = out / "meta.json"
    meta = {int(k): v for k, v in json.loads(meta_path.read_text()).items()} if meta_path.exists() else {}
    for f in todo:
        sc.frame_set(f)
        sc.render.filepath = str(out / f"{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        cur = anim.screen_meta(ch, cam, f)
        prev = anim.screen_meta(ch, cam, max(f - 1, 0))
        speed = math.hypot(cur["chest"][0] - prev["chest"][0], cur["chest"][1] - prev["chest"][1])
        meta[f] = {**cur, "speed": speed, "mask_band": args.char == 2 and f <= 13}
        print(f"kare {f}/{n}", flush=True)
    meta_path.write_text(json.dumps({str(k): v for k, v in sorted(meta.items())}, indent=1))


if __name__ == "__main__":
    main()
