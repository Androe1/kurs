"""Referans karelerden okunan 2B eklem noktalarına göre R15 pozu çözer.

Açıları elle tahmin etmek yerine: referansta her eklemin ekrandaki yeri (kafa,
boyun, kalça, omuzlar, eller, kalçalar, ayaklar) verilir; kök konumu/dönüşü ve
eklem açıları, kameradan bakınca karakterin eklemleri o noktalara düşecek
şekilde en küçük kareler ile bulunur (scipy.optimize.least_squares).

Karakterin oranları referanstan farklı olduğu için uzuvlarda KONUM yerine
YÖN eşlenir (omuzdan ele, kalçadan ayağa ekrandaki doğrultu); gövde çizgisi
(kafa-boyun-kalça) konumla eşlenir. Eklem sınırları ve anlamsal ipuçları
(ör. "göğüs yere bakıyor") ek terimler olarak eklenir.

Kemik dönüşleri Blender'daki gibi hesaplanır (numpy ile ileri kinematik) ve
sonuç quaternion olarak rig'e yazılır.
"""
import math

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

# Çözülen serbestlik dereceleri: (kemik, eksenler)
DOF = [("UpperTorso", "xyz"), ("LowerTorso", "xyz"), ("Head", "xyz"),
       ("LeftUpperArm", "xyz"), ("LeftLowerArm", "x"), ("RightUpperArm", "xyz"), ("RightLowerArm", "x"),
       ("LeftUpperLeg", "xyz"), ("LeftLowerLeg", "x"), ("RightUpperLeg", "xyz"), ("RightLowerLeg", "x")]

LIMITS = {  # derece (alt, üst) eksen başına; yoksa ±180
    "Head": ((-30, 30), (-40, 40), (-30, 30)),
    "UpperTorso": ((-40, 60), (-50, 50), (-35, 35)),
    "LowerTorso": ((-20, 30), (-25, 25), (-20, 20)),
}


class Skeleton:
    """Armature'ın dinlenme verisi + numpy ileri kinematik (Blender ile aynı formül)."""

    def __init__(self, arm):
        self.names = [b.name for b in arm.data.bones]
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
        self.rest = {b.name: np.array(b.matrix_local) for b in arm.data.bones}
        self.length = {b.name: b.length for b in arm.data.bones}
        self.local = {n: (self.rest[n] if self.parent[n] is None
                          else np.linalg.inv(self.rest[self.parent[n]]) @ self.rest[n]) for n in self.names}
        self.order = []
        seen = set()
        while len(self.order) < len(self.names):
            for n in self.names:
                if n not in seen and (self.parent[n] is None or self.parent[n] in seen):
                    self.order.append(n)
                    seen.add(n)

    def fk(self, basis):
        """basis: {kemik: 3x3 dönüş}. Dönüş: {kemik: 4x4 poz matrisi (armature uzayı)}."""
        out = {}
        for n in self.order:
            b = np.eye(4)
            if n in basis:
                b[:3, :3] = basis[n]
            p = self.parent[n]
            out[n] = (self.local[n] if p is None else out[p] @ self.local[n]) @ b
        return out

    def point(self, pose, bone, t=0.0):
        """Kemiğin başından (t=0) kuyruğuna (t=1) bir nokta, armature uzayında."""
        return (pose[bone] @ np.array([0, t * self.length[bone], 0, 1]))[:3]


class Camera:
    def __init__(self, cam, res):
        self.world_inv = np.linalg.inv(np.array(cam.matrix_basis))      # (matrix_world sahne güncellenene dek eski kalır)
        self.f = cam.data.lens / cam.data.sensor_width           # yatay sensör uyumu
        self.aspect = res[0] / res[1]

    def project(self, p):
        c = self.world_inv @ np.append(p, 1.0)
        z = -c[2]
        return np.array([0.5 + c[0] / z * self.f, 0.5 - c[1] / z * self.f * self.aspect])


def _keypoints(sk, pose, world):
    def w(bone, t):
        return (world @ np.append(sk.point(pose, bone, t), 1.0))[:3]
    return {
        "head": w("Head", 0.45), "neck": w("UpperTorso", 1.0), "pelvis": w("LowerTorso", 0.0),
        "Lshoulder": w("LeftUpperArm", 0.0), "Lhand": w("LeftHand", 0.6),
        "Rshoulder": w("RightUpperArm", 0.0), "Rhand": w("RightHand", 0.6),
        "Lhip": w("LeftUpperLeg", 0.0), "Lfoot": w("LeftFoot", 0.3),
        "Rhip": w("RightUpperLeg", 0.0), "Rfoot": w("RightFoot", 0.3),
        "Lelbow": w("LeftLowerArm", 0.0), "Relbow": w("RightLowerArm", 0.0),
        "Lknee": w("LeftLowerLeg", 0.0), "Rknee": w("RightLowerLeg", 0.0),
    }


def _front(pose, rest, bone, world_rot):
    """Kemiğin taşıdığı parçanın 'ön' yönü (dinlenmede -Y) dünyada."""
    delta = pose[bone][:3, :3] @ np.linalg.inv(rest[bone][:3, :3])
    return world_rot @ delta @ np.array([0, -1.0, 0])


class PoseFit:
    def __init__(self, arm, cam, res):
        self.sk = Skeleton(arm)
        self.cam = Camera(cam, res)
        self.res = res
        self.bend_sign = self._bend_signs()

    def _bend_signs(self):
        """Dirsek öne (el kameraya), diz geriye bükülsün: işareti ileri kinematikle bul."""
        signs = {}
        for bone, child, want in (("LeftLowerArm", "LeftHand", -1), ("RightLowerArm", "RightHand", -1),
                                  ("LeftLowerLeg", "LeftFoot", +1), ("RightLowerLeg", "RightFoot", +1)):
            r = Rotation.from_euler("x", 60, degrees=True).as_matrix()
            y = self.sk.point(self.sk.fk({bone: r}), child, 1.0)[1]
            y0 = self.sk.point(self.sk.fk({}), child, 1.0)[1]
            signs[bone] = 1 if (y - y0) * want > 0 else -1
        return signs

    # --- parametre vektörü: kök konumu (3), kök dönüşü (3, derece), DOF açıları (derece)
    def unpack(self, x):
        loc, rot = x[:3], x[3:6]
        basis, i = {}, 6
        for bone, axes in DOF:
            ang = np.zeros(3)
            for a in axes:
                ang["xyz".index(a)] = x[i]
                i += 1
            if bone in self.bend_sign:
                ang[0] = abs(ang[0]) * self.bend_sign[bone]
            basis[bone] = Rotation.from_euler("XYZ", ang, degrees=True).as_matrix()
        return loc, rot, basis

    def world(self, loc, rot):
        m = np.eye(4)
        m[:3, :3] = Rotation.from_euler("xyz", rot, degrees=True).as_matrix()
        m[:3, 3] = loc
        return m

    def _full_len(self, start, pose, world):
        """Uzuv tam açıkken ekrandaki yaklaşık boyu (piksel): omuzdan/kalçadan uca, kameraya dik."""
        chain = {"Lshoulder": ("LeftUpperArm", "LeftLowerArm", "LeftHand"),
                 "Rshoulder": ("RightUpperArm", "RightLowerArm", "RightHand"),
                 "Lhip": ("LeftUpperLeg", "LeftLowerLeg", "LeftFoot"),
                 "Rhip": ("RightUpperLeg", "RightLowerLeg", "RightFoot")}[start]
        length = sum(self.sk.length[b] for b in chain[:2]) + 0.6 * self.sk.length[chain[2]]
        p = (world @ np.append(self.sk.point(pose, chain[0], 0.0), 1.0))[:3]
        c = self.cam.world_inv @ np.append(p, 1.0)
        return length / -c[2] * self.cam.f * self.res[0]

    def residuals(self, x, target, hints):
        loc, rot, basis = self.unpack(x)
        pose = self.sk.fk(basis)
        world = self.world(loc, rot)
        kp = _keypoints(self.sk, pose, world)
        px = {k: self.cam.project(v) * np.array(self.res) for k, v in kp.items()}
        tgt = {k: np.array(v) * np.array(self.res) / np.array((960, 540)) for k, v in target.items()}
        r = []
        # gövde çizgisi: konum
        for k, wgt in (("head", 1.0), ("neck", 1.2), ("pelvis", 1.0)):
            if k in tgt:
                r.extend((px[k] - tgt[k]) * wgt / 10)
        # uzuvlar: yön (oranlar farklı) + ekrandaki boy (gövde boyuna oranla) + zayıf konum çekimi.
        # Boy terimi, uzvun kameraya dik uzatılıp ekranda noktaya dönüşmesini engeller.
        scale = 1.0
        if "neck" in tgt and "pelvis" in tgt:
            scale = np.linalg.norm(px["neck"] - px["pelvis"]) / (np.linalg.norm(tgt["neck"] - tgt["pelvis"]) + 1e-6)
        for a, b in (("Lshoulder", "Lhand"), ("Rshoulder", "Rhand"), ("Lhip", "Lfoot"), ("Rhip", "Rfoot")):
            if b not in tgt:
                continue
            start = tgt.get(a, px[a])
            d_t = tgt[b] - start
            d_o = px[b] - px[a]
            r.extend((d_o / (np.linalg.norm(d_o) + 1e-6) - d_t / (np.linalg.norm(d_t) + 1e-6)) * 8.0)
            want = min(np.linalg.norm(d_t) * scale, 0.9 * self._full_len(a, pose, world))
            r.append((np.linalg.norm(d_o) - want) / (want + 1e-6) * 3.0)
            r.extend((px[b] - tgt[b]) * 0.25 / 10)
        # anlamsal ipuçları: parçanın ön yönü (dünya)
        wr = world[:3, :3]
        for bone, want, wgt in hints.get("front", []):
            f = _front(pose, self.sk.rest, bone, wr)
            r.extend((f - np.asarray(want) / np.linalg.norm(want)) * wgt)
        # derinlik sırası: "behind" listesindeki noktalar kalçadan en az m stud daha uzakta (arkada)
        dp = -(self.cam.world_inv @ np.append(kp["pelvis"], 1.0))[2]
        for k, m in hints.get("behind", []):
            dk = -(self.cam.world_inv @ np.append(kp[k], 1.0))[2]
            r.append(max(0.0, dp + m - dk) * 6.0)
        # kameraya uzaklık (kadraj ölçeği): kalçanın kamera derinliği
        if "depth" in hints:
            c = self.cam.world_inv @ np.append(kp["pelvis"], 1.0)
            r.append((-c[2] - hints["depth"]) * 3.0)
        # sade kalsın: açılar küçük tercih edilir (aşırı burulma yok)
        r.extend(x[6:] / 180.0 * 0.6)
        return np.array(r)

    def solve(self, target, hints, x0=None):
        n = 6 + sum(len(a) for _, a in DOF)
        if x0 is None:
            x0 = np.zeros(n)
            x0[:3] = hints.get("loc0", (0, 0, 0))
        lo, hi = np.full(n, -180.0), np.full(n, 180.0)
        lo[:3], hi[:3] = -20, 20
        i = 6
        for bone, axes in DOF:
            lim = LIMITS.get(bone)
            for a in axes:
                if lim:
                    lo[i], hi[i] = lim["xyz".index(a)]
                if bone in self.bend_sign:
                    lo[i], hi[i] = 0, 125
                i += 1
        x0 = np.clip(x0, lo + 1e-6, hi - 1e-6)
        res = least_squares(self.residuals, x0, bounds=(lo, hi), args=(target, hints), max_nfev=600, x_scale=np.r_[np.ones(3), np.full(n - 3, 20.0)])
        return res.x, res.cost

    def to_pose(self, x):
        """Çözümü anim.py poz biçimine çevirir (kök + her kemiğin quaternion'u)."""
        loc, rot, basis = self.unpack(x)
        quats = {b: Rotation.from_matrix(m).as_quat()[[3, 0, 1, 2]].tolist() for b, m in basis.items()}
        return {"loc": [float(v) for v in loc], "rot": [float(v) for v in rot], "quat": quats}

    def report(self, x, target):
        loc, rot, basis = self.unpack(x)
        pose = self.sk.fk(basis)
        kp = _keypoints(self.sk, pose, self.world(loc, rot))
        out = {}
        for k, v in target.items():
            p = self.cam.project(kp[k]) * np.array((960, 540))
            out[k] = (round(float(p[0])), round(float(p[1])), round(float(math.dist(p, v))))
        return out
