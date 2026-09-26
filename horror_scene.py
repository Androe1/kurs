"""Korku oyunu teaser'ı - 15 saniyelik sahne: zaman çizelgesi, fizik, kamera ve ışık.

Akış (saniye):
  0.00  zifiri karanlık
  0.70  tepede spot ışık titreyerek yanar, huzmede toz süzülür
  0.95  kan yukarıdan ağır ağır iner, ucunda damla şişer; iki damla karanlığa düşer
  2.75  damla titrer ve döner; yüzeyinden yapraklar çıkar, dıştan içe açılarak gül olur
  5.25  iplik kopar; gül düşen yaprak gibi sağa sola yatarak süzülür, üstünden kan damlar
  8.35  gül kan birikintisine değer: halka halka dalga, taç sıçraması, iki yaprak kopar
  9.85  kamera yukarı, karanlığa döner; ışık titreyip söner
 10.95  tam karanlık ve sessizlik
 11.15  kapalı şeytani gözler karanlıktan belirir, bir kez seğirir
 11.75  kapaklar açılır, göz bebekleri iğne ucuna büzülür, kamera sarsılır
 12.95  kesme
 13.15  COMING SOON

Tüm hareketler fizikle hesaplanır (bkz. .claude/skills/character-physics): gül düşen yaprak
modeliyle (APW levha modeli + safra torku; hız sürekli) süzülür, sıvıya değince temas kuvveti
kademeli devreye giren yaylarla oturur; kopan yapraklar hava direnciyle sallanarak düşer;
kamera gülü yaylarla takip eder.
"""
import math

import numpy as np
from scipy.spatial.transform import Rotation as Rot

from horror_gl import look_at, perspective
from horror_rose import Rose, grid_normals

DURATION = 15.0

T_LIGHT = 0.70
T_OOZE = (0.95, 2.35)
T_DRIPS = (1.55, 2.55)
T_MORPH = (2.75, 5.05)
T_BUD = 3.05                # yaprakların sıvıdan çıktığı an
T_SNAP = 5.25
T_LAND = 8.35
T_FLICKER = 9.30
T_TILT = (9.85, 10.95)
T_DARK = 10.95
T_EYES_SHOW = 11.15         # kapalı gözler karanlıktan belirir
T_EYES = 11.75              # kapaklar açılır
T_CUT = 12.95
T_TITLE = 13.15
T_END_FADE = (14.45, 15.0)
FLASHES = ((9.345, 9.38), (10.38, 10.415))   # ışık sönük kaldığı 2 karede gözler bilinçaltı görünür
T_ESCALATE = (12.3, 12.95)                   # gözler giderken artan sarsıntı ve kararma

ROSE_SCALE = 0.5
MORPH_Y = 2.2
MORPH_X = 0.22              # dönüşüm biraz sağda: yaprak gibi süzülüş sola açılır, iniş havuzun ortasına yakın
SWING_YAW = math.radians(20.0)   # salınım düzlemi kameraya göre hafif dönük (derinlik hissi)
REST_Y = 0.045              # gül sıvıda yüzerken merkezinin yüksekliği
CONTACT_Y = REST_Y + 0.02   # alt yapraklar yüzeye değdiği an
ANCHOR = np.array([MORPH_X, 3.4, 0.0])
G = 9.81

SPOT_POS = np.array([0.3, 5.2, 0.45])
SPOT_TARGET = np.array([-0.06, 0.3, 0.0])


# ---------------------------------------------------------------- yardımcılar

def clamp01(x):
    return min(max(x, 0.0), 1.0)


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = clamp01(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def span(t, a, b):
    return clamp01((t - a) / (b - a))


def ease_out(x, p=3.0):
    return 1 - (1 - clamp01(x)) ** p


def ease_out_back(x, s=1.4):
    x = clamp01(x) - 1
    return 1 + x * x * ((s + 1) * x + s)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class Spring:
    """Sönümlü yay: x'' = w²(hedef - x) - 2ζw x' (hızlanır, hafif aşar, geç oturur)."""

    def __init__(self, x0, freq, zeta):
        self.x = np.array(x0, float)
        self.v = np.zeros_like(self.x)
        self.w, self.z = 2 * math.pi * freq, zeta

    def step(self, target, dt):
        a = self.w ** 2 * (np.asarray(target, float) - self.x) - 2 * self.z * self.w * self.v
        self.v = self.v + a * dt
        self.x = self.x + self.v * dt
        return self.x


class Track:
    """Önceden hesaplanmış, zamana göre örneklenen eğri (sabit adımlı)."""

    def __init__(self, t0, dt, values):
        self.t0, self.dt = t0, dt
        self.v = np.asarray(values, float)

    def __call__(self, t):
        f = (t - self.t0) / self.dt
        i = int(np.clip(math.floor(f), 0, len(self.v) - 2))
        u = min(max(f - i, 0.0), 1.0)
        return self.v[i] * (1 - u) + self.v[i + 1] * u


# ---------------------------------------------------------------- gülün hareketi

def leaf_flutter(l, beta, istar, keel, mu2, theta0, g, T, dt=5e-4):
    """Düşen yaprak (flutter) fiziği: Andersen–Pesavento–Wang (2005) yarı-durağan düz levha modeli.

    Ekran düzleminde (x yatay, y yukarı) ince bir levha: gövde eksenlerinde hız (u: kiriş boyunca,
    v: dik), eğim θ, açısal hız ω. Kuvvetler: sabit yerçekimi (kaldırma payı düşülmüş), eklenen kütle,
    dolaşımdan (sirkülasyon) doğan kaldırma, yöne bağlı sürükleme, dönme sönümü. Çiçek başının ağır
    tabanı yaprakların altında olduğu için bir de safra torku (keel) vardır: gülü dik tutmaya çalışır.
    Sonuç kendiliğinden oluşan sağa-sola süzülmedir: levha bir yana kayar, ucunda burnunu kaldırıp
    yavaşlar, diğer yana döner. Dönüş: t, x, y, θ, vx, vy dizileri.
    """
    rho_f = 1.0
    h = l * beta
    rho_s = istar * rho_f * l / h
    m = rho_s * l * h
    mp = (rho_s - rho_f) * l * h
    m11 = rho_f * math.pi * h * h / 4
    m22 = rho_f * math.pi * l * l / 4
    inertia = m * (l * l + h * h) / 12 + rho_f * math.pi * l ** 4 / 128
    A, B, CT, CR = 1.4, 1.0, 1.2, math.pi

    def deriv(st):
        x, y, th, u, v, w = st
        V = math.hypot(u, v) + 1e-9
        cos2a = (u * u - v * v) / (V * V)
        gam = CT * l * u * v / V + 0.5 * CR * l * l * w
        F = 0.5 * rho_f * l * (A - B * cos2a) * V
        du = ((m + m22) * w * v - rho_f * gam * v - mp * g * math.sin(th) - F * u) / (m + m11)
        dv = (-(m + m11) * w * u + rho_f * gam * u - mp * g * math.cos(th) - F * v) / (m + m22)
        tau = math.pi * rho_f * l ** 4 / 32 * (0.004 + mu2 * abs(w)) * w + keel * mp * g * l * math.sin(th)
        dw = ((m11 - m22) * u * v - tau) / inertia
        return np.array([u * math.cos(th) - v * math.sin(th), u * math.sin(th) + v * math.cos(th), w, du, dv, dw])

    st = np.array([0.0, 0.0, theta0, 0.0, 0.0, 0.0])
    n = int(T / dt) + 1
    out = np.empty((n, 6))
    out[0] = st
    for i in range(1, n):
        k1 = deriv(st)
        k2 = deriv(st + dt / 2 * k1)
        k3 = deriv(st + dt / 2 * k2)
        k4 = deriv(st + dt * k3)
        st = st + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        out[i] = st
    t = np.arange(n) * dt
    th = out[:, 2]
    vx = out[:, 3] * np.cos(th) - out[:, 4] * np.sin(th)
    vy = out[:, 3] * np.sin(th) + out[:, 4] * np.cos(th)
    return t, out[:, 0], out[:, 1], th, vx, vy


class RoseMotion:
    """Gülün kökü: askıda hafif sallanma; iplik kopunca düşen yaprak fiziğiyle sağa-sola süzülerek
    iner; sıvıya değince dikeyde sönümlü yay, yatay hız sıvıda söner, eğim burulma yayıyla
    sallanarak düzelir. Tüm hızlar süreklidir."""

    # düşen yaprak modelinin parametreleri (boyutsuz; zaman ölçeği g ile ayarlanır)
    LEAF = dict(l=1.05, beta=1 / 8, istar=0.45, keel=0.25, mu2=1.3, theta0=0.45)

    def __init__(self, dt=1 / 600):
        drop = MORPH_Y - CONTACT_Y
        fall_T = T_LAND - T_SNAP
        # önce g0 ile çöz, düşüş süresini ölç; şekil aynı kalır, zaman 1/sqrt(g) ile ölçeklenir
        g0 = 6.5
        t0, _, y0, _, _, _ = leaf_flutter(g=g0, T=6.0, **self.LEAF)
        tc = float(np.interp(-drop, y0[::-1], t0[::-1]))
        self.g = g0 * (tc / fall_T) ** 2
        lt, lx, ly, lth, lvx, lvy = leaf_flutter(g=self.g, T=fall_T + 0.2, **self.LEAF)
        self.leaf = (lt, lx, ly, lth, lvx, lvy)

        ts = np.arange(0, DURATION + 0.1, dt)
        x = np.full_like(ts, MORPH_X)
        y = np.empty_like(ts)
        vx = np.zeros_like(ts)
        vy = np.zeros_like(ts)
        bank = np.zeros_like(ts)
        yaw = np.empty_like(ts)
        sy = sb = None
        yaw_v = 0.0
        yaw_a = math.radians(100.0)                            # açılırken yaptığı sarmal dönüş
        for i, t in enumerate(ts):
            if t < T_SNAP:
                y[i] = MORPH_Y
                yaw[i] = yaw_a * smoother(span(t, T_MORPH[0], T_MORPH[1] + 0.1))
            elif t < T_LAND:
                tau = t - T_SNAP
                x[i] = MORPH_X + np.interp(tau, lt, lx)
                y[i] = MORPH_Y + np.interp(tau, lt, ly)
                vx[i] = np.interp(tau, lt, lvx)
                vy[i] = np.interp(tau, lt, lvy)
                bank[i] = np.interp(tau, lt, lth)
                yaw_v += (math.radians(22.0) - yaw_v) * min(dt / 0.8, 1.0)
                yaw[i] = yaw[i - 1] + yaw_v * dt
            else:
                if sy is None:
                    sy = True
                    y_c, v_c = y[i - 1], vy[i - 1]
                    sb = Spring(bank[i - 1], 1.9, 0.3)          # kaldırma kuvveti gülü düzeltir, sallanır
                    sb.v = np.array((bank[i - 1] - bank[i - 2]) / dt)
                    xv = vx[i - 1]
                    w_y, z_y = 2 * math.pi * 2.2, 0.7
                # sıvıya gömüldükçe temas kuvveti büyür (ilk 60 ms'de kademeli): ivme tek karede sıçramaz
                ramp = smooth(span(t, T_LAND, T_LAND + 0.06))
                bob = 0.003 * math.sin(2 * math.pi * 1.1 * (t - T_LAND - 0.35)) * math.exp(-(t - T_LAND) / 1.6) \
                    * smooth(span(t, T_LAND + 0.2, T_LAND + 0.5))
                a_y = ramp * (w_y ** 2 * (REST_Y + bob - y_c) - 2 * z_y * w_y * v_c) - (1 - ramp) * self.g * 0.0
                v_c += a_y * dt
                y_c += v_c * dt
                y[i], vy[i] = y_c, v_c
                xv *= math.exp(-dt * ramp / 0.14)                # sıvı yatay kaymayı hızla durdurur
                x[i] = x[i - 1] + xv * dt
                vx[i] = xv
                bank[i] = float(sb.step(0.0, dt))
                yaw_v += (math.radians(2.5) - yaw_v) * min(dt / 0.7, 1.0)
                yaw[i] = yaw[i - 1] + yaw_v * dt
        self.ts, self.x, self.y, self.vx, self.vy, self.bank, self.yaw = ts, x, y, vx, vy, bank, yaw
        self.vt = float(np.abs(vy).max())
        self.dt = dt

    def _s(self, arr, t):
        return float(np.interp(t, self.ts, arr))

    def position(self, t):
        sway = 0.0
        if t < T_SNAP:     # iplikte asılıyken hafif sarkaç
            sway = 0.004 * math.sin(2 * math.pi * 0.62 * t + 0.4) * smooth(span(t, T_BUD, T_BUD + 0.6))
        dx = self._s(self.x, t) - MORPH_X                 # salınım düzleminde yatay yol
        return np.array([MORPH_X + dx * math.cos(SWING_YAW) + sway, self._s(self.y, t),
                         -dx * math.sin(SWING_YAW) + 0.4 * sway])

    def velocity(self, t):
        return self._s(self.vy, t)

    def velocity_xy(self, t):
        vx = self._s(self.vx, t)
        return np.array([vx * math.cos(SWING_YAW), self._s(self.vy, t), -vx * math.sin(SWING_YAW)])

    def rotation(self, t):
        """Önce kendi ekseninde dönüş (yaw), sonra salınım düzleminde yatış (bank)."""
        axis = np.array([math.sin(SWING_YAW), 0.0, math.cos(SWING_YAW)])
        return Rot.from_rotvec(axis * self._s(self.bank, t)) * Rot.from_euler("y", self._s(self.yaw, t))


# ---------------------------------------------------------------- yaprakların ikincil hareketi

def ripple_height(rows, x, z, t):
    """Zemin shader'ındaki dalga yüksekliğinin aynısı (yüzen yapraklar dalgaya binsin)."""
    h = 0.0
    for x0, z0, t0, amp, lam, speed, decay, _ in rows:
        tau = t - t0
        if tau <= 0:
            continue
        d = math.hypot(x - x0, z - z0)
        xx = speed * tau - d
        if xx < -0.04:
            continue
        lam2 = lam * (1 - 0.4 * smooth(xx / 0.5))
        env = smooth((xx + 0.035) / 0.055) * math.exp(-max(xx, 0.0) / (0.1 + 0.22 * min(tau, 2.0)))
        h += amp * env * math.sin(2 * math.pi * xx / lam2) * math.exp(-tau / decay) / math.sqrt(1 + d / 0.04)
    return h


class PetalDynamics:
    """Yaprakların ikincil hareketi (overlap & follow-through).

    Her yaprak tabanındaki menteşe etrafında kütleli, az sönümlü bir yaydır: gülün ivmesi (atalet)
    ve hava akışı (sürükleme basıncı) yaprağı açar ya da kapar; yaprak gecikmeyle tepki verir, aşar,
    sallanarak oturur. Dış yapraklar büyük ve gevşektir (≈3 Hz), içtekiler sert (≈8 Hz): farklı
    frekanslar çakışan hareketi kendiliğinden üretir. Hava hızının karesiyle büyüyen bant sınırlı
    titreşim yaprak uçlarını rüzgarda çırpındırır.
    """

    def __init__(self, rose, motion, t0, t1, detach=(), dt=1 / 600, seed=5):
        rng = np.random.default_rng(seed)
        n = rose.n
        ts = np.arange(t0, t1, dt)
        pos = np.array([motion.position(t) for t in ts])
        vel = np.gradient(pos, dt, axis=0)
        acc = np.gradient(vel, dt, axis=0)
        k = np.array([p.k for p in rose.petals])
        alpha = np.array([p.alpha for p in rose.petals])
        phi = np.array([p.phi for p in rose.petals])
        gain = 0.25 + 0.75 * k ** 2
        w = 2 * math.pi * (3.0 + 5.0 * (1 - k) ** 1.5)
        zeta = 0.22
        loose = np.ones(n)
        for i in detach:
            loose[i] = 2.2                               # kopacak yapraklar gevşemiştir
        d = np.zeros(n)
        dv = np.zeros(n)
        D = np.zeros((len(ts), n))
        DV = np.zeros((len(ts), n))
        U = np.zeros(len(ts))
        er_l = np.stack([np.sin(phi), np.zeros(n), np.cos(phi)], -1)
        for j, t in enumerate(ts):
            R = motion.rotation(t)
            er = R.apply(er_l)
            up = R.apply([0.0, 1.0, 0.0])
            n_out = er * np.cos(alpha)[:, None] - up[None, :] * np.sin(alpha)[:, None]
            u = -vel[j]
            speed = float(np.linalg.norm(u))
            inert = -(n_out @ acc[j])                     # atalet: gül yavaşlarsa yapraklar açılır
            aero = speed * (n_out @ u)                    # hava basıncı: düşerken dış yaprakları kapar
            post = loose if t >= T_LAND else 1.0
            target = gain * (0.035 * inert + 0.2 * aero) * post
            a = w ** 2 * (target - d) - 2 * zeta * w * dv
            dv = dv + a * dt
            d = d + dv * dt
            D[j], DV[j], U[j] = d, dv, speed
        self.ts, self.D, self.DV, self.U = ts, D, DV, U
        self.k = k
        # rüzgarda titreme: yaprak başına üç rastgele frekanslı yumuşak salınım
        self.fl_f = rng.uniform(5.5, 9.5, (n, 3))
        self.fl_p = rng.uniform(0, 2 * math.pi, (n, 3))
        self.wave_f = rng.uniform(3.0, 4.5, n)
        self.u_ref = max(float(U.max()), 1e-3)

    def at(self, t):
        """(sapma, sapma hızı, hava hızı oranı) dizileri."""
        f = (t - self.ts[0]) / (self.ts[1] - self.ts[0])
        if f <= 0:
            return np.zeros(len(self.k)), np.zeros(len(self.k)), 0.0
        i = int(min(math.floor(f), len(self.ts) - 2))
        u = min(f - i, 1.0)
        D = self.D[i] * (1 - u) + self.D[i + 1] * u
        DV = self.DV[i] * (1 - u) + self.DV[i + 1] * u
        U = self.U[i] * (1 - u) + self.U[i + 1] * u
        return D, DV, U / self.u_ref

    def flex(self, t, i, D=None, s=None):
        if D is None:
            D, _, s = self.at(t)
        k = self.k[i]
        amp = (s ** 2) * k ** 2
        flutter = amp * 0.04 * sum(math.sin(2 * math.pi * self.fl_f[i, m] * t + self.fl_p[i, m]) / (m + 1) for m in range(3))
        return dict(open=float(D[i] + flutter), curl=float(0.6 * D[i]), wave=0.028 * amp,
                    phase=2 * math.pi * self.wave_f[i] * t, edge=0.05 * amp,
                    edge_phase=2 * math.pi * 7.3 * t + self.fl_p[i, 0])


def fp_normals(fp):
    """Kopan yaprağın donmuş yerel şeklinin normalleri (gül uzayında)."""
    if getattr(fp, "_nrm", None) is None:
        from horror_rose import NA, NB
        fp._nrm = grid_normals((fp.local / ROSE_SCALE).reshape(NB, NA, 3)).reshape(-1, 3)
    return fp._nrm


class DetachedPetal:
    """Çarpmada gevşeyen dış yaprak: ikincil hareketin itişiyle tabanındaki menteşe etrafında dışa
    doğru açılmaya devam eder (soyulur), yatarak sıvının üstüne kapanır; sonra dalganın ittiği
    yönde yavaşça sürüklenip dönerek dalgalara biner. Zıplatma ya da ani itiş yoktur: kopma anındaki
    konum, dönüş ve açısal hız sürekli devam eder."""

    def __init__(self, idx, scene, t_d):
        rose, motion = scene.rose, scene.motion
        self.idx, self.t0 = idx, t_d
        b = float(scene.petal_bloom(t_d)[idx])
        D, DV, s = scene.dyn.at(t_d)
        flex = scene.dyn.flex(t_d, idx, D, s)
        local, nrm, _ = rose.petal(idx, b, flex=flex)
        R0 = motion.rotation(t_d)
        C0 = motion.position(t_d)
        base_l, axis_l = rose.hinge(idx, b)
        self.R0, self.C0 = R0, C0
        self.local = local.reshape(-1, 3) * ROSE_SCALE
        self.hinge_l = base_l * ROSE_SCALE
        self.axis = R0.apply(axis_l)
        p = rose.petals[idx]
        self.out = unit(R0.apply([math.sin(p.phi), 0.0, math.cos(p.phi)]) * np.array([1.0, 0.0, 1.0]))
        # yatarak kapanma açısı: yaprağın ağırlık merkezi yönü yataydan biraz aşağıya inene kadar
        cen = R0.apply(self.local.mean(0) - self.hinge_l)
        el = math.asin(np.clip(cen[1] / np.linalg.norm(cen), -1, 1))
        self.beta_flat = el + math.radians(8.0)
        # açılma: kopma anındaki açısal hızla başlar, yerçekimi ve sıvı onu düz yatırır
        dt = 1 / 600
        beta, bv = 0.0, float(DV[idx])
        ts, B = [], []
        t = t_d
        w = 2 * math.pi * 1.4
        while t < DURATION + 0.05:
            a = w * w * (self.beta_flat - beta) - 2 * 0.62 * w * bv
            bv += a * dt
            beta += bv * dt
            ts.append(t)
            B.append(beta)
            t += dt
        self.ts, self.B = np.array(ts), np.array(B)
        # yere yatma anı (dalga kaynağı) ve kayma başlangıcı
        i_flat = int(np.argmax(self.B >= 0.85 * self.beta_flat)) if (self.B >= 0.85 * self.beta_flat).any() else len(ts) - 1
        self.t_land = float(self.ts[i_flat])
        self.land_pos = self._pose(self.t_land, ripple=False)[0]
        self.rows = None

    def _pose(self, t, ripple=True):
        beta = float(np.interp(t, self.ts, self.B))
        Rh = Rot.from_rotvec(self.axis * beta)
        hinge_w = self.C0 + self.R0.apply(self.hinge_l)
        # yattıktan sonra dışa doğru sürüklenme ve yavaş dönüş
        tau = max(t - getattr(self, "t_land", t), 0.0)
        drift = self.out * 0.1 * 1.3 * (1 - math.exp(-tau / 1.3))
        spin = Rot.from_euler("y", 0.35 * 1.4 * (1 - math.exp(-tau / 1.4)))
        R = spin * Rh * self.R0
        rel = R.apply(self.local - self.hinge_l)
        verts = hinge_w + drift + rel
        # yüzme: en alt nokta sıvı yüzeyinin (dalga dahil) hemen üstünde kalır
        c = verts.mean(0)
        surf = ripple_height(self.rows, c[0], c[2], t) if (ripple and self.rows is not None) else 0.0
        lift = max(0.0, surf + 0.0015 - verts[:, 1].min()) * smooth(tau / 0.15 if tau > 0 else 0.0)
        return c + np.array([0.0, lift, 0.0]), R, hinge_w + drift + np.array([0.0, lift, 0.0])

    def vertices(self, t):
        c, R, hinge = self._pose(t)
        return hinge + R.apply(self.local - self.hinge_l), R


# ---------------------------------------------------------------- sahne

class Scene:
    def __init__(self, width=1920, height=1080, fps=60, seed=11):
        self.width, self.height, self.fps = width, height, fps
        self.duration = DURATION
        self.rng = np.random.default_rng(seed)
        self.rose = Rose()
        self.n = self.rose.n
        self.motion = RoseMotion()
        self._bud_geometry()
        self.drop_r = self.bud_r_eq * 0.97
        self.tip_end = MORPH_Y + self.bud_center[1] + self.drop_r * 1.2
        self._top_local = self.bud_top
        self._bloom_schedule()
        detach = self._pick_detach()
        self.dyn = PetalDynamics(self.rose, self.motion, T_SNAP - 0.3, DURATION + 0.05, detach=detach)
        self._petals(detach)
        self._droplets()
        self._ripples()
        for fp in self.falling:
            fp.rows = self.ripple_rows
        self._camera_tracks()
        self.renderer = None
        self._ao_key = None
        self._ao = None

    # ------------------------------------------------------------ hazırlık

    def _bud_geometry(self):
        P, _, _, _, _ = self.rose.build(0.0)
        P = P * ROSE_SCALE
        c = (P.max(0) + P.min(0)) / 2
        self.bud_center = c
        self.bud_radius = float(np.linalg.norm(P - c, axis=1).max())
        self.bud_r_eq = float(np.percentile(np.linalg.norm(P - c, axis=1), 85))
        self.bud_top = float(P[:, 1].max())
        # ipliğin koptuğu yükseklik: açık gülün iç yapraklarının tepesinin biraz üstü
        Po, _, _, I, _ = self.rose.build(1.0)
        self.snap_y = MORPH_Y + float((Po[I[:, 0] < 0.3][:, 1]).max()) * ROSE_SCALE + 0.035

    def _bloom_schedule(self):
        """Yapraklar üç dalga hâlinde (nabız gibi, sesle aynı vuruşta) dıştan içe, sarmal sırayla açılır."""
        n = self.n
        self.bloom_beats = (3.45, 4.05, 4.6)
        t0 = np.zeros(n)
        dur = np.zeros(n)
        order = list(range(n - 1, -1, -1))                    # dıştan içe
        groups = (order[:9], order[9:18], order[18:])
        for beat, g in zip(self.bloom_beats, groups):
            for j, i in enumerate(g):
                t0[i] = beat + j * 0.028
                dur[i] = 0.75 + 0.2 * (1 - self.rose.petals[i].k)
        self.bloom_t0, self.bloom_dur = t0, dur

    def _pick_detach(self):
        """Sıvıya önce değen (alçaktaki) tarafta, kameradan görünen iki dış yaprak."""
        R = self.motion.rotation(T_LAND)
        outer = [i for i, p in enumerate(self.rose.petals) if p.k > 0.8]
        low_side = -1.0 if self.motion._s(self.motion.bank, T_LAND) > 0 else 1.0     # ekranda sol / sağ

        def world_az(i):
            p = self.rose.petals[i]
            d = R.apply([math.sin(p.phi), 0.0, math.cos(p.phi)])
            return math.degrees(math.atan2(d[0], d[2]))

        def pick(target, exclude=()):
            cands = [i for i in outer if i not in exclude]
            return min(cands, key=lambda i: abs((world_az(i) - target + 180) % 360 - 180))

        a = pick(low_side * 62.0)
        b = pick(low_side * 118.0, (a,))
        return (a, b)

    def _petals(self, detach):
        """Kopan yapraklar: çarpmadan sonra en çok açıldıkları anda menteşeden ayrılırlar."""
        self.falling = []
        ts, D = self.dyn.ts, self.dyn.D
        for i, idx in enumerate(detach):
            # birinci yaprak ilk açılışta, ikincisi bir salınım daha tutunup ikinci açılışta kopar;
            # ayrılma, açılma hızını taşısın diye tepe noktasının %75'ine varıldığı anda olur
            j0 = int(np.searchsorted(ts, T_LAND + (0.0 if i == 0 else 0.3)))
            j1 = int(np.searchsorted(ts, T_LAND + (0.3 if i == 0 else 0.8)))
            jm = j0 + int(np.argmax(D[j0:j1, idx]))
            peak = D[jm, idx]
            jr = j0 + int(np.argmax(D[j0:jm + 1, idx] >= 0.75 * peak))
            self.falling.append(DetachedPetal(idx, self, float(ts[jr])))
        self.falling_idx = {fp.idx: fp for fp in self.falling}

    def _droplets(self):
        """Serbest kan damlacıkları: ipten kopanlar, düşen gülden damlayanlar ve taç sıçraması."""
        rng = self.rng
        drops = []
        # ipliğin ucundan karanlığa düşen iki damla
        for t0, r in ((T_DRIPS[0], 0.0085), (T_DRIPS[1], 0.011)):
            drops.append(dict(t0=t0, p0=np.array([0.0, 0.0, 0.0]), v0=np.array([0.0, -0.05, 0.0]), r=r,
                              src="tip"))
        # düşen gülün yaprak uçlarından damlayanlar (gülden hızlı düşer, sıvıya önce onlar değer)
        for t0 in (5.95, 6.55, 7.15, 7.65):
            ang = rng.uniform(0, 2 * math.pi)
            rad = rng.uniform(0.12, 0.2)
            drops.append(dict(t0=t0, p0=np.array([math.sin(ang) * rad, -0.03, math.cos(ang) * rad]),
                              v0=np.array([0.0, 0.0, 0.0]), r=rng.uniform(0.006, 0.009), src="rose"))
        # taç sıçraması (gülün sıvıya değdiği yerde)
        land = self.motion.position(T_LAND)
        for j in range(14):
            ang = j / 14 * 2 * math.pi + rng.uniform(-0.15, 0.15)
            rad = rng.uniform(0.2, 0.26)
            up = rng.uniform(0.55, 1.05)
            out = rng.uniform(0.15, 0.4)
            drops.append(dict(t0=T_LAND + 0.03 + rng.uniform(0, 0.04),
                              p0=np.array([land[0] + math.sin(ang) * rad, 0.004, land[2] + math.cos(ang) * rad]),
                              v0=np.array([math.sin(ang) * out, up, math.cos(ang) * out]),
                              r=rng.uniform(0.0035, 0.0075), src="crown"))
        for d in drops:
            if d["src"] == "rose":
                base = self.motion.position(d["t0"]) + self.motion.rotation(d["t0"]).apply(d["p0"] * 1.0)
                d["p0"] = base
                d["v0"] = self.motion.velocity_xy(d["t0"])
            elif d["src"] == "tip":
                c, r, st = self.drop_state(d["t0"])
                d["p0"] = np.array([c[0], c[1] - r * st * 0.9, c[2]])
            # sıvıya değme anı (sabit yerçekimi)
            y0, vy = d["p0"][1], d["v0"][1]
            disc = vy * vy + 2 * G * y0
            d["t_hit"] = d["t0"] + (vy + math.sqrt(max(disc, 0.0))) / G
        self.drops = drops

    def _ripples(self):
        """Zemindeki dalga kaynakları: x, z, t0, genlik | dalga boyu, hız, sönüm, 0."""
        rows = []
        for d in self.drops:
            if d["src"] == "tip":
                continue
            p = d["p0"] + d["v0"] * (d["t_hit"] - d["t0"])
            amp = 0.0006 if d["src"] == "crown" else 0.0013
            lam = 0.022 if d["src"] == "crown" else 0.034
            rows.append([p[0], p[2], d["t_hit"], amp, lam, 0.3, 0.9 if d["src"] == "crown" else 1.3, 0])
        land = self.motion.position(T_LAND)
        rest = self.motion.position(T_LAND + 0.3)
        rows.append([land[0], land[2], T_LAND, 0.0042, 0.07, 0.42, 2.2, 0])
        rows.append([rest[0], rest[2], T_LAND + 0.3, 0.0016, 0.05, 0.38, 1.6, 0])
        for fp in self.falling:
            if fp.t_land < DURATION:
                rows.append([fp.land_pos[0], fp.land_pos[2], fp.t_land, 0.0017, 0.045, 0.34, 1.6, 0])
        rows.sort(key=lambda r: r[2])
        self.ripple_rows = np.array(rows, "f4")

    def _camera_tracks(self):
        """Kamera hedefi gülü yaylarla takip eder: dikeyde tamamen, yatayda kısmen (salınım ekranda okunsun)."""
        dt = 1 / 600
        ts = np.arange(0, DURATION + 0.1, dt)
        follow_y = Spring(MORPH_Y + 0.06, 1.25, 0.95)
        follow_x = Spring(MORPH_X, 0.8, 0.9)
        ty = np.empty_like(ts)
        tx = np.empty_like(ts)
        for i, t in enumerate(ts):
            p = self.motion.position(t)
            goal = MORPH_Y + 0.08 - 0.06 * smooth(span(t, 2.2, 3.6)) if t < T_SNAP else p[1] + 0.035
            ty[i] = float(follow_y.step(goal, dt))
            k = 1.0 - 0.65 * smooth(span(t, T_SNAP, T_SNAP + 0.7)) + 0.5 * smooth(span(t, T_LAND, T_LAND + 1.1))
            tx[i] = float(follow_x.step(k * p[0], dt))
        self.cam_ty = Track(0.0, dt, ty)
        self.cam_tx = Track(0.0, dt, tx)

    def _tip_y(self, t):
        """İnen kan ipliğinin ucu: kadrajın üstünden ağır ağır iner, yavaşlayarak durur."""
        u = span(t, *T_OOZE)
        start, end = MORPH_Y + 0.75, self.tip_end
        return start + (end - start) * ease_out(u, 2.4)

    # ------------------------------------------------------------ zaman eğrileri

    def light_gain(self, t):
        if t < T_LIGHT:
            return 0.0
        g = 1.0
        for a, b, v in ((0.70, 0.745, 0.55), (0.745, 0.80, 0.02), (0.80, 0.83, 0.9), (0.83, 0.87, 0.3),
                        (T_FLICKER, T_FLICKER + 0.03, 0.35), (FLASHES[0][0], FLASHES[0][1], 0.02),
                        (T_FLICKER + 0.12, T_FLICKER + 0.15, 0.5),
                        (10.08, 10.12, 0.3), (10.22, 10.25, 0.15), (FLASHES[1][0], FLASHES[1][1], 0.0),
                        (10.5, 10.53, 0.3), (10.6, 10.62, 0.1)):
            if a <= t < b:
                g = v
        g *= 1 - smooth(span(t, 10.0, 10.72))
        g *= 1 - smooth(span(t, 10.72, 10.76))
        g *= 1 + 0.025 * math.sin(t * 37.0) * math.sin(t * 11.3)
        return max(g, 0.0)

    def camera(self, t):
        m = self.motion
        # mesafe, yükseklik açısı (+ yukarıdan bakış), yörünge açısı
        d = 1.26 - 0.12 * smooth(span(t, 0.9, 2.75)) + 0.2 * smoother(span(t, 3.1, 5.0)) \
            + 0.55 * smoother(span(t, T_SNAP, T_LAND)) - 0.17 * smooth(span(t, T_LAND, T_TILT[0] + 0.3))
        elev = 3.0 + 11.0 * smoother(span(t, 1.0, 4.2)) + 10.0 * smoother(span(t, T_SNAP + 0.3, T_LAND + 0.2))
        az = -7.0 + 13.0 * smooth(span(t, 0.0, T_SNAP)) + 5.0 * smooth(span(t, T_SNAP, T_TILT[0]))
        ty = self.cam_ty(t)
        target = np.array([self.cam_tx(t), ty, 0.0])
        e, a = math.radians(elev), math.radians(az)
        eye = target + d * np.array([math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e)])
        fwd = unit(target - eye)
        # kamera karanlığa, yukarı bakar
        u = smoother(span(t, *T_TILT)) ** 1.15
        if u > 0:
            pitch0 = math.asin(fwd[1])
            pitch = pitch0 + (math.radians(40.0) - pitch0) * u
            h = unit([fwd[0], 0.0, fwd[2]])
            fwd = np.array([h[0] * math.cos(pitch), math.sin(pitch), h[2] * math.cos(pitch)])
        # el kamerası, hafif eğik (dutch) açı, sıvıya değmede küçük sarsıntı
        hh = 0.0022 * np.array([math.sin(2 * math.pi * 0.7 * t + 0.3) + 0.4 * math.sin(2 * math.pi * 1.9 * t),
                                math.sin(2 * math.pi * 1.1 * t + 1.7), 0.0])
        k = t - T_LAND
        shake = 0.0045 * math.exp(-k / 0.1) * math.sin(k * 45.0) * smooth(k / 0.03) if 0 <= k < 0.6 else 0.0
        fwd = unit(fwd + hh + np.array([0.0, shake, 0.0]))
        roll = math.radians(1.3 * math.sin(0.23 * t + 0.5))
        right = unit(np.cross(fwd, [0.0, 1.0, 0.0]))
        up = unit(np.cross(right, fwd))
        up = up * math.cos(roll) + right * math.sin(roll)
        return dict(eye=eye, target=eye + fwd, up=up, fov=30.0)

    def lights(self, t):
        spot_dir = unit(SPOT_TARGET - SPOT_POS)
        light_vp = perspective(22.0, 1.0, 1.0, 8.0) @ look_at(SPOT_POS, SPOT_TARGET, (0.0, 0.0, -1.0))
        g = self.light_gain(t)
        back = 0.3 + 0.2 * smooth(span(t, T_SNAP + 1.0, T_LAND))
        return dict(spot_pos=SPOT_POS, spot_dir=spot_dir,
                    spot_cos=(math.cos(math.radians(8.0)), math.cos(math.radians(3.2))),
                    spot_col=(1.45, 1.32, 1.22), light_vp=light_vp,
                    back_dir=unit([-0.32, 0.36, -1.0]), back_col=(back, back * 0.9, back * 0.95),
                    amb=(0.02, 0.0015, 0.003), floor_glow=0.07 * smooth(span(t, T_LAND - 1.0, T_LAND)),
                    gain=g)

    # ------------------------------------------------------------ gül ağı

    def petal_bloom(self, t):
        """Yaprakların açılma oranı (açılma programı; ikincil hareket PetalDynamics'te)."""
        u = np.clip((t - self.bloom_t0) / self.bloom_dur, 0, 1)
        return np.array([ease_out_back(x, 1.2) for x in u])

    def petal_liquid(self, t):
        u = np.clip((t - self.bloom_t0) / self.bloom_dur, 0, 1)
        return 1.0 - 0.85 * np.array([smooth((x - 0.1) / 0.8) for x in u])

    def rose_visible(self, t):
        return t >= T_BUD

    def mesh(self, t):
        """Dünya uzayında gül köşeleri (n, 14) + üçgenler; ortam kapanması önbellekli."""
        bloom = self.petal_bloom(t)
        liquid = self.petal_liquid(t)
        wet = 1.0 - 0.35 * smooth(span(t, T_LAND, T_LAND + 2.0))
        grow = 0.72 + 0.28 * ease_out(span(t, T_BUD, T_BUD + 0.4), 2.0)
        S = ROSE_SCALE * grow
        R = self.motion.rotation(t)
        C = self.motion.position(t)
        rose = self.rose
        D, _, sp = self.dyn.at(t)
        dyn_on = t >= T_SNAP - 0.3
        locs, nrms, uvs = [], [], []
        for i in range(self.n):
            flex = self.dyn.flex(t, i, D, sp) if dyn_on else None
            pos, nrm, uv = rose.petal(i, float(bloom[i]), flex=flex)
            # sıvıdan biçimlenirken yüzeyde akan dalgalar
            lq = float(liquid[i])
            if lq > 0.02:
                vv = uv[..., 1:2]
                pos = pos + nrm * (0.012 * lq * np.sin(18.0 * vv - 9.0 * t + i) * vv)
            locs.append(pos.reshape(-1, 3))
            nrms.append(nrm.reshape(-1, 3))
            uvs.append(uv.reshape(-1, 2))
        nv = locs[0].shape[0]
        self._top_local = float(max(locs[i][:, 1].max() for i in range(6))) * S
        # ortam kapanması: gülün kendi uzayında, açılma durumu değiştikçe yeniden
        key = np.round(bloom, 2).tobytes()
        if key != self._ao_key:
            # ortam kapanması esnemesiz şekilden (ikincil hareket küçük; her karede yeniden hesaplanmaz)
            if dyn_on:
                base = [rose.petal(i, float(bloom[i])) for i in range(self.n)]
                bl = [b[0].reshape(-1, 3) for b in base]
                bn = [b[1].reshape(-1, 3) for b in base]
            else:
                bl, bn = locs, nrms
            self._ao = self._bake_ao(bl, bn)
            self._ao_key = key
        verts = np.zeros((self.n * nv, 14), "f4")
        for i in range(self.n):
            sl = slice(i * nv, (i + 1) * nv)
            p_loc = locs[i] * S
            n_loc = nrms[i]
            if i in self.falling_idx and t >= self.falling_idx[i].t0:
                fp = self.falling_idx[i]
                pw, Rp = fp.vertices(t)
                nw = Rp.apply(fp_normals(fp))
                sep = smooth(span(t, fp.t0, fp.t0 + 0.5))
                ao = self._ao[sl] * (1 - sep) + 0.92 * sep
            else:
                pw = C + R.apply(p_loc)
                nw = R.apply(n_loc)
                ao = self._ao[sl]
            verts[sl, 0:3] = pw
            verts[sl, 3:6] = nw
            verts[sl, 6:8] = uvs[i]
            verts[sl, 8] = rose.petals[i].k
            verts[sl, 9] = i
            verts[sl, 10:12] = ao
            verts[sl, 12] = liquid[i]
            verts[sl, 13] = wet
        return verts, rose.tri_all

    def _bake_ao(self, locs, nrms):
        nv = locs[0].shape[0]
        verts = np.zeros((self.n * nv, 14), "f4")
        verts[:, 0:3] = np.concatenate(locs)
        verts[:, 3:6] = np.concatenate(nrms)
        self.renderer.upload_mesh(verts, self.rose.tri_all)
        P = verts[:, 0:3]
        c = (P.max(0) + P.min(0)) / 2
        r = float(np.linalg.norm(P - c, axis=1).max()) * 1.02
        return self.renderer.bake_ao(c, r, offset=0.004)

    # ------------------------------------------------------------ sıvı

    def drop_state(self, t):
        """Asılı damla: (merkez, yarıçap, dikey uzama). Damla sonunda tomurcuğun içinde kaybolur."""
        r_final = self.drop_r
        r = 0.012 + (r_final - 0.012) * ease_out(span(t, T_OOZE[0] + 0.1, T_MORPH[0]), 1.8)
        if t >= T_BUD:
            r *= 1 - 0.72 * smooth(span(t, T_BUD + 0.12, T_BUD + 0.5))
        stretch = 1.0 + 0.2 * smooth(span(t, T_OOZE[1] - 0.3, T_MORPH[0])) - 0.2 * smooth(span(t, T_MORPH[0], T_BUD))
        cy = self._tip_y(t) - r * stretch
        if t >= T_MORPH[0]:
            cy = MORPH_Y + self.bud_center[1]
        x = self.motion.position(t)[0]
        return np.array([x, cy, 0.0]), r, stretch

    def liquid(self, t):
        """Raymarch edilen kan: iplik noktaları, damla ve damlacıklar."""
        caps, blobs = [], []
        drop = np.zeros(4)
        shape = np.zeros(4)
        top = None
        ridge = 0.0
        if T_OOZE[0] <= t < T_BUD + 0.5:
            c, r, stretch = self.drop_state(t)
            ridge = 0.3 * smooth(span(t, T_MORPH[0] + 0.05, T_BUD + 0.05))
            drop = np.array([*c, r])
            wob = 0.025 + 0.1 * smooth(span(t, T_MORPH[0], T_BUD)) + 0.03 * (1 - span(t, *T_OOZE))
            twist = 3.0 * smooth(span(t, T_MORPH[0], T_BUD + 0.45)) ** 2
            shape = np.array([stretch, wob, t * 7.0, twist])
            top = c[1] + r * stretch * 0.9
        if T_BUD <= t < T_SNAP:
            rose_top = self.motion.position(t)[1] + self._top_local
            w = smooth(span(t, T_BUD, T_BUD + 0.35))
            top = rose_top if top is None else top * (1 - w) + rose_top * w
        if T_OOZE[0] <= t < T_SNAP + 1.6:
            caps = self._thread(t, top)
        # serbest damlacıklar (sabit yerçekimi)
        for d in self.drops:
            if d["t0"] <= t < d["t_hit"]:
                tau = t - d["t0"]
                p = d["p0"] + d["v0"] * tau + np.array([0.0, -0.5 * G * tau * tau, 0.0])
                grow = smooth(tau / 0.06) if d["src"] != "crown" else 1.0
                blobs.append([*p, d["r"] * grow])
        # sınırlayıcı kutu
        pts = []
        for cp in caps:
            pts += [np.array(cp[:3]) - cp[3] - 0.03, np.array(cp[:3]) + cp[3] + 0.03]
        if drop[3] > 0:
            ext = drop[3] * 1.7 + 0.02
            pts += [drop[:3] - ext, drop[:3] + ext]
        for b in blobs:
            pts += [np.array(b[:3]) - b[3] - 0.01, np.array(b[:3]) + b[3] + 0.01]
        if not pts:
            return None
        pts = np.array(pts)
        return dict(caps=np.array(caps, "f4").reshape(-1, 4), blobs=np.array(blobs, "f4").reshape(-1, 4),
                    drop=tuple(float(x) for x in drop), drop_shape=tuple(float(x) for x in shape),
                    bmin=tuple(pts.min(0)), bmax=tuple(pts.max(0)), blend=0.022, ridge=ridge)

    def _thread(self, t, top):
        """Yapışkan kan ipliği: tepede kalın, uca doğru incelir; boncuklar aşağı akar; kopunca geri çekilir."""
        K = 14
        s = np.linspace(0.0, 1.0, K) ** 1.3        # alt uca doğru sıklaşan noktalar
        if t < T_SNAP:
            bottom = top
            neck = 0.0045 * (1 + 0.5 * smooth(span(t, T_BUD, T_BUD + 1.2))) * (1 - 0.75 * smooth(span(t, 4.8, T_SNAP)))
            neck = max(neck, 0.0012)
            recoil = None
        else:
            # kopma: üst parça yaylanarak geri çekilir, ucunda bir boncuk toplanır
            tau = t - T_SNAP
            rise = 0.32 * (1 - math.exp(-tau / 0.16)) + 0.035 * math.sin(tau * 19.0) * math.exp(-tau / 0.22)
            bottom = self.snap_y + rise
            neck = 0.0018 + 0.003 * math.exp(-tau / 0.2)
            recoil = tau
        ys = ANCHOR[1] + (bottom - ANCHOR[1]) * s
        r = 0.012 * (1 - s) ** 1.3 + neck
        beads = np.maximum(np.sin(2 * math.pi * (s * 2.6 - 0.8 * t)), 0.0) ** 2
        r = r * (1 + 0.28 * beads * (0.3 + s))
        if T_BUD <= t < T_SNAP:
            pump = np.maximum(np.sin(2 * math.pi * (s * 2.0 - 1.6 * t)), 0.0) ** 4
            r = r * (1 + 0.5 * pump * smooth(span(t, T_BUD, T_BUD + 0.4)) * (1 - smooth(span(t, 4.7, T_SNAP))))
        sway = 0.012 * np.sin(math.pi * s) * math.sin(2 * math.pi * 0.35 * t + 1.1) + \
            0.006 * np.sin(2 * math.pi * s) * math.sin(2 * math.pi * 0.8 * t)
        xs = ANCHOR[0] + sway + (self.motion.position(min(t, T_SNAP))[0] - ANCHOR[0]) * s ** 3
        zs = 0.5 * sway
        caps = [[xs[i], ys[i], zs[i], r[i]] for i in range(K)]
        if recoil is not None:
            caps[-1][3] = 0.002 + 0.0065 * (1 - math.exp(-recoil / 0.08))    # ucunda toplanan boncuk
        return caps

    # ------------------------------------------------------------ gözler ve yazı

    def eyes(self, t):
        """Kullanıcının çizdiği gözler: önce kapalı belirir, seğirir, sonra kapaklar açılır; göz bebekleri
        büyükten iğne ucuna büzülür, kamera sarsılır."""
        for a, b in FLASHES:
            if a <= t < b:
                return self._flash_eyes(t, a)
        if t < T_EYES_SHOW or t >= T_CUT:
            return None
        show = ease_out(span(t, T_EYES_SHOW, T_EYES_SHOW + 0.45), 2.0)
        reveal = 0.2 + 1.9 * ease_out(span(t, T_EYES_SHOW, T_EYES_SHOW + 0.5), 2.2)
        tau = t - T_EYES
        # açılmadan önce küçük bir seğirme (kapak aralanıp geri kapanır)
        tw = t - (T_EYES - 0.3)
        twitch = 0.1 * math.sin(math.pi * clamp01(tw / 0.12)) if 0 <= tw < 0.12 else 0.0
        lid_up = twitch + (ease_out_back(tau / 0.09, 1.8) if tau > 0 else 0.0)
        lid_lo = ease_out_back((tau - 0.02) / 0.13, 1.2) if tau > 0.02 else 0.0
        near_vis = smooth(span(tau, 0.02, 0.1))
        open_ = 1.0 + 0.07 * math.exp(-max(tau, 0) / 0.06) * (tau > 0) + 0.02 * math.sin(2 * math.pi * 9.0 * tau) * math.exp(-max(tau, 0) / 0.45) * (tau > 0)
        pupil = 0.8 + 1.5 * math.exp(-max(tau, 0) / 0.09) + 0.15 * (1 - smooth(max(tau, 0) / 0.7))
        pupil *= 1 + 0.07 * math.sin(tau * 31.0) * math.sin(tau * 7.3)
        rng = np.random.default_rng(int(max(tau, 0) * 3.2) + 5)
        sacc = rng.uniform(-1, 1, 2) * np.array([6.0, 3.5])
        look = sacc * smooth(span(tau, 0.25, 0.3)) + 1.2 * np.array([math.sin(tau * 53), math.sin(tau * 41)])
        if tau > 0:
            esc = span(t, *T_ESCALATE) ** 2.2                   # gözler giderken sarsıntı giderek şiddetlenir
            amp = 0.03 * math.exp(-tau / 0.32) + 0.0035 + 0.075 * esc
            fq = 1.0 + 0.8 * esc
            n1 = math.sin(tau * 71.0 * fq) * 0.6 + math.sin(tau * 113.0 * fq + 1.3) * 0.4
            n2 = math.sin(tau * 83.0 * fq + 0.7) * 0.6 + math.sin(tau * 131.0 * fq + 2.1) * 0.4
            shake = (amp * n1, amp * n2 * 0.8)
            rot = math.radians(1.6) * math.exp(-tau / 0.3) * math.sin(tau * 47.0) + math.radians(4.0) * esc * math.sin(tau * 61.0)
            zoom = 1.16 - 0.12 * ease_out(tau / 0.25) + 0.07 * smooth(span(tau, 0.2, T_CUT - T_EYES)) + 0.12 * esc
        else:
            # kapalıyken: çok yavaş yaklaşma ve hafif nefes
            k = t - T_EYES_SHOW
            shake = (0.0006 * math.sin(k * 5.1), 0.0008 * math.sin(k * 3.7))
            rot = 0.0
            zoom = 1.0 + 0.04 * smooth(span(t, T_EYES_SHOW, T_EYES))
        squint = smooth(span(t, T_CUT - 0.45, T_CUT - 0.05))
        glow = (1.25 + 0.05 * math.sin(tau * 29.0)) * (1 + 0.4 * math.exp(-max(tau, 0) / 0.06) * (tau > 0))
        return dict(u_open=float(open_), u_pupil=float(pupil), u_look=tuple(float(x) for x in look),
                    u_shake=tuple(float(x) for x in shake), u_rot=float(rot), u_zoom=float(zoom),
                    u_glow=float(glow), u_reveal=float(reveal), u_squint=float(squint),
                    u_lid_up=float(lid_up), u_lid_lo=float(lid_lo), u_show=float(show), u_near_vis=float(near_vis))

    def _flash_eyes(self, t, t0):
        """Bilinçaltı görüntü: ışık söndüğü 2 karede açık gözler karanlıktan belirip kaybolur."""
        k = (t - t0) / 0.035
        return dict(u_open=1.0, u_pupil=0.75, u_look=(0.0, 0.0), u_shake=(0.004 * math.sin(k * 9), 0.003),
                    u_rot=0.0, u_zoom=1.35 + 0.1 * k, u_glow=0.55 * (1 - 0.4 * k), u_reveal=2.2, u_squint=0.0,
                    u_lid_up=1.0, u_lid_lo=1.0, u_show=1.0, u_near_vis=1.0)

    def title(self, t):
        if t < T_TITLE:
            return None
        tau = t - T_TITLE
        reveal = ease_out(tau / 1.1, 2.0)
        fl = 1.0
        for a, b, v in ((0.0, 0.05, 1.6), (0.07, 0.1, 0.25), (0.16, 0.19, 0.5), (0.9, 0.93, 0.4)):
            if a <= tau < b:
                fl = v
        fl *= 1 + 0.03 * math.sin(tau * 43.0) * math.sin(tau * 17.0)
        glitch = 1.0 if (tau < 0.22 or 0.88 < tau < 0.95) else 0.0
        streak = 1.2 * math.exp(-tau / 0.35) + 0.1
        return dict(u_reveal=float(reveal), u_bright=float(fl), u_glitch=float(glitch), u_streak=float(streak))

    def post(self, t):
        k = t - T_EYES
        flash = 0.0
        if 0 <= k < 0.3:
            flash = 0.18 * math.exp(-k / 0.04)
        if 0 <= t - T_LAND < 0.3:
            flash += 0.06 * math.exp(-(t - T_LAND) / 0.08)
        blur = (0.0, 0.0)
        ca = 0.01
        if T_EYES <= t < T_CUT:
            e0 = self.eyes(t)
            e1 = self.eyes(min(t + 1 / self.fps, T_CUT - 1e-4))
            dx = (e1["u_shake"][0] - e0["u_shake"][0]) * self.height / self.width
            dy = (e1["u_shake"][1] - e0["u_shake"][1])
            blur = (dx * 0.8, dy * 0.8)
            ca = 0.012 + 0.09 * math.exp(-k / 0.25)
        if 0 <= t - T_TITLE < 0.3:
            ca += 0.05 * math.exp(-(t - T_TITLE) / 0.1)
        fade = 1.0 - smooth(span(t, *T_END_FADE))
        esc = span(t, *T_ESCALATE)
        if esc > 0 and t < T_CUT:
            ca += 0.16 * esc ** 1.5
            strobe = 1.0 if math.sin(2 * math.pi * 17.0 * t) > -0.2 else 0.35
            fade *= (1.0 - smooth((t - 12.55) / 0.4)) * (strobe if t > 12.6 else 1.0)
            flash += 0.25 * esc ** 3 * (0.5 + 0.5 * math.sin(2 * math.pi * 11.0 * t))
        if T_CUT <= t < T_TITLE:
            fade = 0.0
        eyes_on = T_EYES_SHOW <= t < T_CUT
        return dict(exposure=1.0, bloom=0.08 if eyes_on else 0.22, bloom_threshold=1.4 if eyes_on else 0.75,
                    ca=ca, blur=blur, grain=0.038,
                    vignette=0.3, flash=flash, fade=fade, bars=1.0)

    # ------------------------------------------------------------ kare

    def state(self, t):
        scene_on = T_LIGHT - 0.05 < t < T_DARK + 0.05
        st = dict(t=t, scene_on=scene_on, camera=self.camera(t), lights=self.lights(t),
                  ripples=self.ripple_rows, fog=0.03, refl_gain=1.0,
                  dust=dict(center=(0.12, 1.45, 0.08), extent=(1.3, 2.9, 1.3), amount=0.35, px=3.2),
                  eyes=self.eyes(t), title=self.title(t), post=self.post(t))
        if scene_on:
            st["mesh"] = self.mesh(t) if self.rose_visible(t) else None
            if not self.rose_visible(t):
                self.renderer.n_vertices = 0
            st["liquid"] = self.liquid(t)
        else:
            st["mesh"], st["liquid"] = None, None
        return st

    def render(self, t):
        if self.renderer is None:
            self._init_renderer()
        return self.renderer.render(self.state(t))

    def _init_renderer(self):
        from horror_gl import Renderer
        from horror_texture import palette, stroke_texture
        import horror_eyes as he
        self.renderer = Renderer(self.width, self.height)
        self.renderer.set_text(*title_masks(self.width, self.height))
        self.renderer.set_petal_texture(stroke_texture(), palette())
        aux, lids = he.eye_lids()
        self.renderer.set_eye_image(he.eye_image(), he.PUPILS, he.PUPIL_R, he.CENTER,
                                    he.ref_per_unit(self.width / self.height), aux, lids)

    # ------------------------------------------------------------ ses için olaylar

    def events(self):
        """Ses tasarımının görüntüyle aynı anda çalması için olaylar ve hareket eğrileri."""
        def drip_x(d):
            return float((d["p0"] + d["v0"] * (d["t_hit"] - d["t0"]))[0])
        drips = [(float(d["t_hit"]), drip_x(d)) for d in self.drops if d["src"] in ("tip", "rose")]
        crown = sorted((float(d["t_hit"]), drip_x(d)) for d in self.drops if d["src"] == "crown")
        # gülün hızı ve yatay konumu (süzülme hışırtıları, stereo konum)
        ts = np.arange(T_SNAP - 0.2, T_LAND + 1.0, 0.005)
        vel = np.array([np.linalg.norm(self.motion.velocity_xy(t)) for t in ts])
        xs = np.array([self.motion.position(t)[0] - self.cam_tx(t) for t in ts])
        bank = np.array([self.motion._s(self.motion.bank, t) for t in ts])
        # ışığın titremesi (vızıltı aynı anda kesilip gelsin)
        lt = np.arange(0.0, DURATION, 0.001)
        lg = np.array([self.light_gain(t) for t in lt])
        return dict(duration=DURATION, light_on=T_LIGHT, flicker=T_FLICKER, light_off=10.74,
                    light=(lt, lg), ooze=T_OOZE, drips_release=list(T_DRIPS), drip_hits=drips,
                    morph=T_MORPH, bud=T_BUD, bloom_beats=list(self.bloom_beats),
                    petal_opens=[float(x) for x in sorted(self.bloom_t0)], snap=T_SNAP, land=T_LAND,
                    land_x=float(self.motion.position(T_LAND)[0] - self.cam_tx(T_LAND)),
                    fall=(ts, vel, xs, bank), crown=crown,
                    petal_detach=[(fp.t0, float(fp.C0[0])) for fp in self.falling],
                    petal_land=[(fp.t_land, float(fp.land_pos[0])) for fp in self.falling],
                    tilt=T_TILT, dark=T_DARK, eyes_show=T_EYES_SHOW, twitch=T_EYES - 0.3, eyes=T_EYES,
                    flashes=[a for a, _ in FLASHES], escalate=T_ESCALATE,
                    cut=T_CUT, title=T_TITLE, end_fade=T_END_FADE)


def title_masks(width, height, text="COMING SOON"):
    """Cinzel yazı tipiyle keskin ve bulanık metin maskeleri (skia)."""
    import skia
    from pathlib import Path
    font_path = Path(__file__).parent / "fonts" / "Cinzel-SemiBold.ttf"
    size = height * 0.083
    font = skia.Font(skia.Typeface.MakeFromFile(str(font_path)), size)
    track = size * 0.2
    widths = font.getWidths(font.textToGlyphs(text))
    total = sum(widths) + track * (len(text) - 1)
    out = []
    for blur in (0.0, height * 0.012):
        surf = skia.Surface(width, height)
        c = surf.getCanvas()
        c.clear(skia.ColorBLACK)
        paint = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)
        if blur:
            paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
        x = (width - total) / 2
        y = height / 2 + size * 0.36
        for ch, w in zip(text, widths):
            c.drawString(ch, x, y, font, paint)
            x += w + track
        img = surf.makeImageSnapshot().toarray()
        out.append(img[..., 1].astype(np.float32) / 255.0)
    return out
