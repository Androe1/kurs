"""Karakter animasyonu için fizik katmanı (numpy; motordan bağımsız).

Blender, Roblox, Unity ya da kendi render'ın - hepsinde aynı şekilde kullanılır:
her kare için kök konumu, kök dönüşü ve kemik dönüşleri bu katmandan hesaplanır,
sonra hedef motora (keyframe / CFrame / Transform) yazılır.

Birimler: konum "birim" (stud, metre... tutarlı olsun), zaman kare; fps parametre.
Dönüşler scipy.spatial.transform.Rotation.
"""
import math

import numpy as np
from scipy.spatial.transform import Rotation as R


# ---------------------------------------------------------------- kök yörüngesi

class Ballistic:
    """Serbest uçuş: sabit yerçekimi + sabit yatay momentum, isteğe bağlı 'havada kalma'.

    Kök hiçbir karede duraksamaz: dikey hız her kare aynı miktarda değişir, yatay hız sabit.
    hang=(oran, genişlik_kare): yerçekimi tepe anı çevresinde yumuşakça 'oran' kadar azalır
    (trambolin / çizgi film havada kalma hissi). Hız yine süreklidir.

        traj = Ballistic(apex_frame=19, apex_pos=(x, y, z), horiz_vel=(vx, vy),
                         gravity=150, fps=60, hang=(0.6, 7))
        pos = traj(f); vz = traj.vz(f)            # konum, dikey hız (birim/s)
    """

    def __init__(self, apex_frame, apex_pos, horiz_vel=(0.0, 0.0), gravity=150.0, fps=60,
                 hang=(0.6, 7.0), span=(-60.0, 240.0), step=0.05):
        self.fps = fps
        self.ta = apex_frame
        self.apex = np.asarray(apex_pos, float)
        self.hv = np.asarray(horiz_vel, float) / fps               # birim / kare
        g = gravity / fps ** 2
        fs = np.arange(span[0], span[1], step)
        k, w = hang
        gg = g * (1 - k * np.exp(-((fs - self.ta) / w) ** 2))
        i0 = int(np.argmin(abs(fs - self.ta)))
        v = np.zeros_like(fs)
        z = np.zeros_like(fs)
        z[i0] = self.apex[2]
        for i in range(i0 + 1, len(fs)):                           # tepeden ileri
            v[i] = v[i - 1] - gg[i - 1] * step
            z[i] = z[i - 1] + (v[i - 1] + v[i]) / 2 * step
        for i in range(i0 - 1, -1, -1):                            # tepeden geri
            v[i] = v[i + 1] + gg[i + 1] * step
            z[i] = z[i + 1] - (v[i + 1] + v[i]) / 2 * step
        self.fs, self.zs, self.vs = fs, z, v

    @staticmethod
    def through(pa, fa, pb, fb, gravity=150.0, fps=60, **kw):
        """İki anahtar konumdan (fa'da pa, fb'de pb) geçen yörünge; tepe anı fizikle bulunur."""
        pa, pb = np.asarray(pa, float), np.asarray(pb, float)
        g = gravity / fps ** 2
        ta = (fa + fb) / 2 - (pa[2] - pb[2]) / (g * (fb - fa))
        za = pa[2] + g / 2 * (fa - ta) ** 2
        hv = (pb[:2] - pa[:2]) / (fb - fa) * fps
        apex = np.array([*(pa[:2] + hv / fps * (ta - fa)), za])
        return Ballistic(ta, apex, hv, gravity, fps, **kw)

    def __call__(self, f):
        xy = self.apex[:2] + self.hv * (f - self.ta)
        return np.array([xy[0], xy[1], float(np.interp(f, self.fs, self.zs))])

    def vz(self, f):
        return float(np.interp(f, self.fs, self.vs)) * self.fps


# ---------------------------------------------------------------- yaylar

class Spring:
    """Sönümlü yay (skaler ya da vektör): x'' = w²(hedef - x) - 2ζw x'.

    Bir parçayı hedefe 'kütleyle' götürür: hızlanır, hafifçe aşar, geç oturur.
    freq yüksek = sert (gövde), düşük = gevşek (el, pelerin). zeta<1 hafif aşma.
    """

    def __init__(self, x0, freq, zeta):
        self.x = np.array(x0, float)
        self.v = np.zeros_like(self.x)
        self.w, self.z = 2 * math.pi * freq, zeta

    def step(self, target, dt, sub=12):
        h = dt / sub
        target = np.asarray(target, float)
        for _ in range(sub):
            a = self.w ** 2 * (target - self.x) - 2 * self.z * self.w * self.v
            self.v = self.v + a * h
            self.x = self.x + self.v * h
        return self.x


class RotSpring:
    """Dönüş için yay: bir referans dönüşe göre log-uzayda (rotvec) çalışır."""

    def __init__(self, ref, start, freq, zeta):
        self.ref = ref
        self.s = Spring((ref.inv() * start).as_rotvec(), freq, zeta)

    def step(self, target, dt):
        return self.ref * R.from_rotvec(self.s.step((self.ref.inv() * target).as_rotvec(), dt))


# Önerilen kemik yay ayarları (Hz, sönüm): gövde sert, uçlar gevşek -> kendiliğinden overlap
BONE_SPRING_DEFAULTS = {
    "hips": (8.0, 0.8), "chest": (7.0, 0.7), "head": (5.0, 0.5),
    "upper_arm": (5.0, 0.45), "lower_arm": (4.5, 0.4), "hand": (4.0, 0.4),
    "upper_leg": (5.5, 0.5), "lower_leg": (5.0, 0.45), "foot": (4.5, 0.4),
    "cape": (2.6, 0.4), "root_rot": (6.0, 0.8), "drag": (4.0, 0.55), "camera": (2.0, 0.9),
}


# ---------------------------------------------------------------- ikincil hareket

def world_rot_about(axis, deg):
    n = np.linalg.norm(axis)
    if n < 1e-9 or abs(deg) < 1e-6:
        return np.eye(3)
    return R.from_rotvec(np.asarray(axis) / n * math.radians(deg)).as_matrix()


def drag_angle(drag_value, max_deg=32.0, scale=25.0):
    """Hava sürüklemesi açısı. drag_value = yayla süzülmüş dikey hız (birim/s).
    + : uzuv yerçekimi yönüne (aşağı) döner (yükselirken geride kalır)
    - : yukarı kalkar (düşerken). tanh ile yumuşak doyum."""
    return max_deg * math.tanh(drag_value / scale)


def rotate_bone_world(parent_world_rot, basis, Rw):
    """Kemiği kendi ekleminden dünya uzayında Rw kadar döndürür; yeni yerel dönüşü verir.
    parent_world_rot: kemiğin dünya dönüşü / yerel dönüşü (P = W·pose·basis⁻¹)."""
    P = parent_world_rot
    return np.linalg.inv(P) @ Rw @ P @ basis


def squash_from_speed(v, max_stretch=0.10, scale=35.0):
    """Hıza bağlı squash & stretch (hacim korunur): (sx, sy, sz) ölçeği; sy hareket ekseni."""
    s = 1 + max_stretch * math.tanh(abs(v) / scale)
    return (1 / math.sqrt(s), s, 1 / math.sqrt(s))


def camera_shake(frame, hit_frame, amp_deg=0.6, length=4, decay=1.6):
    """Vuruş anında kısa, sönen kamera sarsıntısı (derece)."""
    k = frame - hit_frame
    return amp_deg * math.exp(-max(k, 0) / decay) * math.sin(k * 2.4) if 0 <= k <= length else 0.0


def handheld(t, amp=(0.35, 0.25, 0.3)):
    """Hafif el kamerası titremesi (derece, x/y/z), t saniye."""
    tau = 2 * math.pi
    return (amp[0] * math.sin(tau * 0.7 * t + 0.3) + 0.4 * amp[0] * math.sin(tau * 1.9 * t),
            amp[1] * math.sin(tau * 1.1 * t + 1.7),
            amp[2] * math.sin(tau * 0.9 * t + 2.2) + 0.3 * amp[2] * math.sin(tau * 2.3 * t))
