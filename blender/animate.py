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

# Karakter başına: anahtar pozların kareleri ve fizik ayarları
CHOREO = {
    1: {"hit": ("c1_hit", 10), "hold": ("c1_hold", 25), "launch_blend": 0.4, "swim": (8, 38),
        "spin": 0.0, "apex": 19,
        "offset": (0.0, 2.6, 0.15), "vy_scale": 0.35},   # kameradan geride; kameraya doğru kayma azaltıldı
    2: {"hit": ("c2_hit", 16), "hold": ("c2_hold", 33), "launch_blend": 0.5, "swim": None,
        "spin": -1.2, "apex": 24},        # rad/s: kendi sağına (üstten bakınca saat yönünde) dönmeye devam eder
}
GRAVITY = 150.0              # stud/s²  (karakter 6 stud boyunda; çizgi film yerçekimi, gerçeğin ~4.5 katı)


class Ballistic:
    """Kökün yörüngesi: sabit yerçekimli parabol + sabit yatay momentum.

    Vuruş (fa) ve hold (fb) karelerindeki çözülmüş kök konumlarından geçer; tepe anı
    ta ve tepe yüksekliği za bu iki noktadan ve g'den hesaplanır. Hız hiçbir karede
    sıçramaz, ivme her karede aynıdır (gerçek serbest uçuş)."""

    def __init__(self, H, D, fa, fb, apex=None):
        g = GRAVITY / FPS ** 2                                     # stud / kare²
        self.g = g
        zh, zd = H.loc[2], D.loc[2]
        self.ta = (fa + fb) / 2 - (zh - zd) / (g * (fb - fa))
        self.za = zh + g / 2 * (fa - self.ta) ** 2
        if apex is not None:                                       # tepe anı pencere ortasında
            self.za = max(zh, zd) + 0.25
            self.ta = apex
        self.v = (D.loc[:2] - H.loc[:2]) / (fb - fa)
        self.p = H.loc[:2]
        self.fa = fa

        # Havada kalma (hang time): yerçekimi tepe anının çevresinde yumuşakça %60 azalır.
        # Hız yine süreklidir; yalnızca tepe civarındaki yavaşlık uzar (trambolin hissi).
        self.hang = (0.6, 7.0)
        fs = np.arange(-40.0, 140.0, 0.05)
        gg = self.g * (1 - self.hang[0] * np.exp(-((fs - self.ta) / self.hang[1]) ** 2))
        i0 = int(np.argmin(abs(fs - self.ta)))
        v = np.zeros_like(fs)
        z = np.zeros_like(fs)
        z[i0] = self.za
        for i in range(i0 + 1, len(fs)):                       # tepeden ileri
            v[i] = v[i - 1] - gg[i - 1] * 0.05
            z[i] = z[i - 1] + (v[i - 1] + v[i]) / 2 * 0.05
        for i in range(i0 - 1, -1, -1):                        # tepeden geri
            v[i] = v[i + 1] + gg[i + 1] * 0.05
            z[i] = z[i + 1] - (v[i + 1] + v[i]) / 2 * 0.05
        self.fs, self.zs, self.vs = fs, z, v

    def __call__(self, f):
        xy = self.p + self.v * (f - self.fa)
        return np.array([xy[0], xy[1], float(np.interp(f, self.fs, self.zs))])

    def vz(self, f):
        return float(np.interp(f, self.fs, self.vs)) * FPS          # stud/s


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


BONE_SPRING = {  # (frekans Hz, sönüm): gövde sert, uçlar gevşek -> doğal overlap
    "LowerTorso": (8.0, 0.8), "UpperTorso": (7.0, 0.7), "Head": (5.0, 0.5),
    "LeftUpperArm": (5.0, 0.45), "RightUpperArm": (5.0, 0.45), "LeftLowerArm": (4.5, 0.4),
    "RightLowerArm": (4.5, 0.4), "LeftHand": (4.0, 0.4), "RightHand": (4.0, 0.4),
    "LeftUpperLeg": (5.5, 0.5), "RightUpperLeg": (5.5, 0.5), "LeftLowerLeg": (5.0, 0.45),
    "RightLowerLeg": (5.0, 0.45), "LeftFoot": (4.5, 0.4), "RightFoot": (4.5, 0.4),
}


class Spring3:
    """Vektör için sönümlü yay (kemik dönüşünün log-uzay vektörü)."""

    def __init__(self, x0, freq, zeta):
        self.x = np.array(x0, float)
        self.v = np.zeros(3)
        self.w, self.z = 2 * math.pi * freq, zeta

    def step(self, target, dt, sub=12):
        h = dt / sub
        for _ in range(sub):
            a = self.w ** 2 * (target - self.x) - 2 * self.z * self.w * self.v
            self.v += a * h
            self.x += self.v * h
        return self.x


def bake(char, ch, cam, nframes):
    bones = [b.name for b in ch.arm.data.bones]
    sk = posefit.Skeleton(ch.arm)
    cfg = CHOREO[char]
    H, fa = Pose.from_key(cfg["hit"][0]), cfg["hit"][1]
    D, fb = Pose.from_key(cfg["hold"][0]), cfg["hold"][1]
    Z = rest(bones)
    traj = Ballistic(H, D, fa, fb, cfg.get("apex"))
    traj.p = traj.p + np.asarray(cfg.get("offset", (0, 0, 0)))[:2]
    traj.v = traj.v * np.array([1.0, cfg.get("vy_scale", 1.0)])
    traj.zs = traj.zs + cfg.get("offset", (0, 0, 0))[2]

    # hedef pozlar: fırlarken toplu, vuruş, hold; sonrası hold (düşüşte kollar/bacaklar fizikle kalkar)
    launch = H.blend(Z, cfg["launch_blend"], bones)
    key_f = [0, fa, fb, nframes + 8]
    key_p = [launch, H, D, D]
    bone_t = {b: Track(key_f, rots=[p.bone(b) for p in key_p]) for b in bones}

    # kök dönüşü: vuruş->hold arasındaki açısal hız, öncesinde ve sonrasında sönerek sürer
    dR = (H.rot.inv() * D.rot).as_rotvec() / (fb - fa)             # rad / kare (kök uzayında)
    def root_target(f):
        if f < fa:
            k = -(1 - math.exp(-(fa - f) / 8)) * 8                  # geriye doğru sönen süreklilik
        elif f > fb:
            k = (fb - fa) + (1 - math.exp(-(f - fb) / 5)) * 5
        else:
            k = f - fa
        r = H.rot * R.from_rotvec(dR * k)
        if cfg["spin"]:
            r = R.from_euler("z", cfg["spin"] * (f - fa) / FPS) * r   # kendi sağına sürekli dönüş
        return r
    root_ref = D.rot
    root_spring = Spring3((root_ref.inv() * root_target(-12)).as_rotvec(), 6.0, 0.8)

    # kemik yayları, başlangıçta hedefte dinlenir
    springs = {b: Spring3((D.bone(b).inv() * bone_t[b](-12)).as_rotvec(), *BONE_SPRING[b])
               for b in BONE_SPRING}
    drag_s = Spring3(np.zeros(3), 4.0, 0.55)
    cape_s = Spring3(np.zeros(3), 2.6, 0.4)
    dt = 1 / FPS
    down = np.array([0, 0, -1.0])
    # ısınma: yayları -12. kareden başlat (ilk karede sıçrama olmasın)
    for f in range(-12, 0):
        rt = root_target(f)
        root_spring.step((root_ref.inv() * rt).as_rotvec(), dt)
        for b, sp in springs.items():
            sp.step((D.bone(b).inv() * bone_t[b](f)).as_rotvec(), dt)
        drag_s.step(np.array([traj.vz(f), 0, 0]), dt)
        cape_s.step(np.array([-traj.vz(f), 0, 0]), dt)

    frames = []
    for f in range(nframes + 1):
        loc = traj(f)
        root = root_ref * R.from_rotvec(root_spring.step((root_ref.inv() * root_target(f)).as_rotvec(), dt))
        W = root.as_matrix()

        # 1) hedef pozu kur (Pomni: yüzer gibi çırpan kollar hedefe eklenir)
        target = {b: bone_t[b](f).as_matrix() for b in bones}
        if cfg["swim"]:
            a, b_ = cfg["swim"]
            env = float(np.clip((f - a) / 5, 0, 1) * np.clip((b_ - f) / 5, 0, 1))
            if env > 0:
                pose = sk.fk(target)
                side = W @ pose["UpperTorso"][:3, 0]
                for arm_, ph in (("LeftUpperArm", 0.0), ("RightUpperArm", math.pi)):
                    ang = 28 * env * math.sin(2 * math.pi * 3.0 * f / FPS + ph)
                    P = W @ pose[arm_][:3, :3] @ np.linalg.inv(target[arm_])
                    target[arm_] = np.linalg.inv(P) @ world_rot_about(side, ang) @ P @ target[arm_]

        # 2) kemikler hedefe yayla gider (kütle + momentum: hızlanır, aşar, oturur)
        basis = dict(target)
        for b, sp in springs.items():
            x = sp.step((D.bone(b).inv() * R.from_matrix(target[b])).as_rotvec(), dt)
            basis[b] = (D.bone(b) * R.from_rotvec(x)).as_matrix()
        pose = sk.fk(basis)

        def rotate_world(bone, Rw):
            P = W @ pose[bone][:3, :3] @ np.linalg.inv(basis[bone])
            basis[bone] = np.linalg.inv(P) @ Rw @ P @ basis[bone]

        # 3) hava sürüklemesi: yükselirken uzuvlar aşağıda kalır, düşerken yukarı kalkar
        s_ = drag_s.step(np.array([traj.vz(f), 0, 0]), dt)[0]
        for limb, lower, k in (("LeftUpperArm", "LeftLowerArm", 1.0), ("RightUpperArm", "RightLowerArm", 0.9),
                               ("LeftUpperLeg", "LeftLowerLeg", 0.8), ("RightUpperLeg", "RightLowerLeg", 0.75)):
            ang = 32 * math.tanh(s_ / 25) * k
            for bone, kk in ((limb, 1.0), (lower, 0.5)):
                pose = sk.fk(basis)
                d = W @ pose[bone][:3, 1]
                rotate_world(bone, world_rot_about(np.cross(d, down), ang * kk))

        # 4) pelerin: sırta yakın, gövde boyunca; düşerken havalanır (zincir gecikmeli)
        c_ = cape_s.step(np.array([-traj.vz(f), 0, 0]), dt)[0]
        pose = sk.fk(basis)
        tr = pose["UpperTorso"][:3, :3] @ np.linalg.inv(sk.rest["UpperTorso"][:3, :3])
        back = W @ tr @ np.array([0, 1.0, 0])
        feet = W @ tr @ np.array([0, 0, -1.0])
        for i in (1, 2, 3):
            lift = float(np.clip(math.tanh(c_ / 25), -1, 1)) * (0.8 + 0.2 * i)
            want = feet + back * (0.2 + 0.9 * max(lift, 0)) + down * (0.3 + 0.4 * max(-lift, 0))
            pose = sk.fk(basis)
            d = W @ pose[f"Cape{i}"][:3, 1]
            want = want / (np.linalg.norm(want) + 1e-9)
            full = math.degrees(math.acos(float(np.clip(np.dot(d, want), -1, 1))))
            rotate_world(f"Cape{i}", world_rot_about(np.cross(d, want), 0.75 * full))

        # 5) squash & stretch: hıza göre dikey uzama, tepede normal (hacim korunur)
        sq = 1 + 0.1 * math.tanh(abs(traj.vz(f)) / 35)
        frames.append((loc, root, basis, sq))
    return frames, fa


def camera_track(char, cam, nframes, hit_f, frames=None):
    base = anim.CAMERAS[char]
    loc0, tgt0 = Vector(base["loc"]), Vector(base["target"])
    out = []
    # kamera karakteri hafif gecikmeyle takip eder (tilt): kökün yüksekliğinin %25'i, yaylı
    follow = Spring3(np.zeros(3), 2.0, 0.9)
    zref = frames[hit_f][0][2] if frames else 0.0
    for _ in range(12):
        follow.step(np.array([0, 0, 0.25 * ((frames[0][0][2] if frames else 0) - zref)]), 1 / FPS)
    for f in range(nframes + 1):
        dz = follow.step(np.array([0, 0, 0.25 * ((frames[f][0][2] if frames else 0) - zref)]), 1 / FPS)[2]
        tgt = tgt0 + Vector((0, 0, max(dz, -1.2)))
        u = f / nframes
        push = 0.06 * (3 * u * u - 2 * u ** 3)                     # yavaş yaklaşma (~%6)
        loc = loc0 + (tgt - loc0) * push
        rot = anim.look_rotation(loc, tgt)
        t = f / FPS
        hand = [0.35 * math.sin(2 * math.pi * 0.7 * t + 0.3) + 0.15 * math.sin(2 * math.pi * 1.9 * t),
                0.25 * math.sin(2 * math.pi * 1.1 * t + 1.7),
                0.3 * math.sin(2 * math.pi * 0.9 * t + 2.2) + 0.1 * math.sin(2 * math.pi * 2.3 * t)]
        k = f - hit_f
        shake = 0.6 * math.exp(-max(k, 0) / 1.6) * math.sin(k * 2.4) if 0 <= k <= 4 else 0.0
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
    cams = camera_track(args.char, cam, n, hit_f, frames)
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
