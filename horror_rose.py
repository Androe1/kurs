"""Korku teaser'ı - prosedürel 3B gül (yaprak yaprak).

Her yaprak parametrik bir yüzeydir:
  - orta çizgi: tabandan uca yükselir, açılma açısıyla dışa yatar, ucu geriye kıvrılır
  - enine kesit: ortası içe çukur, uca doğru kenarları dışa kıvrılır (gülün sivri görünen uçları)
Yapraklar altın açıyla (137.5°) dizilir: içtekiler dik ve birbirine sarılı (spiral merkez),
dıştakiler açık ve ucu kıvrık. `bloom` 0 iken yapraklar damla gibi yuvarlak bir tomurcukta
kapalıdır; 1 iken gül tamamen açıktır. Her yaprağın kendi açılma zamanı vardır.

Birim: gülün açık çapı ~1.0 (sahnede ölçeklenir). Yukarı ekseni +y.
"""
import math

import numpy as np

GOLDEN = math.radians(137.5)
N_PETALS = 26
NA, NB = 30, 40            # yaprak başına ızgara (enine x boyuna)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _smooth_int(x, e0):
    """∫_0^x smoothstep(e0, 1, x') dx' (kapalı form)."""
    x = np.asarray(x, float)
    t = np.clip((x - e0) / (1 - e0), 0.0, 1.0)
    inside = (1 - e0) * (t ** 3 - t ** 4 / 2)
    return np.where(x > 1, (1 - e0) * 0.5 + (x - 1), inside)


def lerp(a, b, t):
    return a + (b - a) * t


class Petal:
    """Tek yaprağın açık ve tomurcuk parametreleri."""

    def __init__(self, i, n, rng):
        k = i / (n - 1)                      # 0 = en iç, 1 = en dış
        self.i, self.k = i, k
        self.phi = i * GOLDEN + rng.normal(0, 0.06)
        j = lambda s: 1 + rng.normal(0, s)
        # boyut: iç yapraklar küçük, dışa doğru büyür
        self.L = (0.28 + 0.15 * k) * j(0.05)
        self.W = (0.11 + 0.12 * k) * j(0.06)
        # tabanın yeri: iç yapraklar merkezde, dıştakiler biraz aşağıda ve dışarıda
        self.r0 = 0.01 + 0.07 * k ** 1.3
        self.h0 = -0.01 - 0.10 * k ** 1.2
        # açık hâl
        self.alpha = math.radians(2 + 44 * k ** 2.0) * j(0.06)          # tabandaki açılma
        self.curl = math.radians(-35 + 45 * smoothstep(0.0, 0.25, k) + 82 * k ** 1.3) * j(0.1)  # uç: iç kapanık, dış geriye kıvrık
        self.cup = 1 / (0.04 + 0.36 * k ** 1.6)                          # içe çukurluk (1/yarıçap)
        self.roll = (2.5 + 17.0 * k ** 0.8) * j(0.12)                    # kenarın dışa kıvrılması
        self.twist = rng.normal(0, 0.12) * (0.3 + k)                     # hafif asimetri
        self.wave = rng.uniform(0, 2 * math.pi, 3)
        # tomurcuk / damla hâli: hepsi dik ve bir yumurtanın etrafına sarılı, uçları içe kapanık
        self.alpha_bud = math.radians(10 + 12 * k)
        self.curl_bud = -math.radians(55 + 30 * k)
        self.cup_bud = 1 / (0.03 + 0.10 * k)
        self.roll_bud = 0.0
        self.L_bud = self.L * (0.62 - 0.12 * k)
        self.W_bud = self.W * (0.85 - 0.15 * k)

    def params(self, b):
        """b: bu yaprağın açılma oranı (0 tomurcuk, 1 açık; hafif aşma olabilir)."""
        b = max(float(b), 0.0)
        return dict(
            L=lerp(self.L_bud, self.L, b), W=lerp(self.W_bud, self.W, b),
            alpha=lerp(self.alpha_bud, self.alpha, b), curl=lerp(self.curl_bud, self.curl, b),
            cup=math.exp(lerp(math.log(self.cup_bud), math.log(self.cup), b)),
            roll=lerp(self.roll_bud, self.roll, b ** 1.5), twist=self.twist * b,
            r0=lerp(0.6 * self.r0, self.r0, b), h0=lerp(0.3 * self.h0, self.h0, b))


def width_profile(v):
    """Yaprak yarı genişliği (W'nin oranı): dar taban, v≈0.7'de en geniş."""
    return 0.2 + 0.8 * np.sin(np.clip(v / 0.72, 0, 1) * np.pi / 2) ** 1.2


def top_profile(a):
    """Yaprağın yuvarlak üst kenarı: a sütunundaki en yüksek v."""
    return 1 - 0.3 * np.abs(a) ** 2.2


def petal_surface(p, prm, na=NA, nb=NB, flex=None):
    """(nb, na, 3) konumlar + (nb, na, 2) uv (a: enine -1..1, v: boyuna 0..1).

    flex (ikincil hareket, isteğe bağlı): {"open": taban açısına ek (rad), "curl": uç kıvrımına ek (rad),
    "wave": yüzeyde tabandan uca akan dalganın genliği, "phase": dalganın evresi,
    "edge": kenar titremesi genliği, "edge_phase": evresi}
    """
    L, W = prm["L"], prm["W"]
    if flex:
        prm = dict(prm, alpha=prm["alpha"] + flex.get("open", 0.0), curl=prm["curl"] + flex.get("curl", 0.0))
    a = np.linspace(-1, 1, na)
    b = np.linspace(0, 1, nb)
    A, B = np.meshgrid(a, b)
    V = B * top_profile(A)                       # her noktanın boyuna konumu
    sigma = A * W * width_profile(V)             # orta çizgiden kesit boyunca yay uzunluğu

    # orta çizgi: açılma açısı + uca doğru geriye kıvrılma
    vf = np.linspace(0, 1, 257)
    beta_f = prm["alpha"] + prm["curl"] * smoothstep(0.35, 1.0, vf) ** 1.6
    dv = L / (len(vf) - 1)
    mo = np.concatenate([[0], np.cumsum((np.sin(beta_f[1:]) + np.sin(beta_f[:-1])) / 2 * dv)])
    mu = np.concatenate([[0], np.cumsum((np.cos(beta_f[1:]) + np.cos(beta_f[:-1])) / 2 * dv)])
    out_m = np.interp(V, vf, mo)
    up_m = np.interp(V, vf, mu)
    beta = np.interp(V, vf, beta_f)

    # enine kesit: θ(σ) = cup·σ - roll·∫smoothstep  (kenarlar uca doğru dışa kıvrılır)
    K = 24
    s = np.abs(sigma)[..., None] * np.linspace(0, 1, K)[None, None, :]
    roll_v = prm["roll"] * smoothstep(0.25, 0.9, V)[..., None]
    cup_v = prm["cup"] * (0.55 + 0.45 * smoothstep(0.0, 0.5, V))[..., None]
    theta = cup_v * s - roll_v * W * _smooth_int(s / W, 0.45)
    ds = np.abs(sigma)[..., None] / (K - 1)
    X = np.sign(sigma) * np.trapezoid(np.cos(theta), dx=1, axis=-1) * ds[..., 0]
    Z = -np.trapezoid(np.sin(theta), dx=1, axis=-1) * ds[..., 0]

    # kenarlarda hafif dalga (doğal düzensizlik)
    wv = p.wave
    Z = Z + 0.006 * W / 0.2 * np.abs(A) ** 2 * V * (np.sin(7 * A + wv[0]) + 0.6 * np.sin(13 * A + wv[1]))
    if flex:
        # rüzgarda titreme: tabandan uca akan eğilme dalgası + kenarların çırpınması
        Z = Z + flex.get("wave", 0.0) * L * V ** 2 * np.sin(2 * np.pi * 1.3 * V - flex.get("phase", 0.0))
        Z = Z + flex.get("edge", 0.0) * W * np.abs(A) ** 2 * V * np.sin(5.0 * A + flex.get("edge_phase", 0.0))

    # hafif burulma: kesit orta çizgi etrafında döner
    tw = prm["twist"] * V
    Xr = X * np.cos(tw) - Z * np.sin(tw)
    Zr = X * np.sin(tw) + Z * np.cos(tw)

    # yerel çerçeve: e_t (teğet), e_r (dışa), up; kesitin normali n = (cos β, -sin β)
    radial = prm["r0"] + out_m + Zr * np.cos(beta)
    height = prm["h0"] + up_m - Zr * np.sin(beta)
    tang = Xr
    phi = p.phi
    x = tang * math.cos(phi) + radial * math.sin(phi)
    z = -tang * math.sin(phi) + radial * math.cos(phi)
    pos = np.stack([x, height, z], -1)
    uv = np.stack([A, V], -1)
    return pos, uv


def grid_normals(pos):
    """Izgara yüzeyinin normali: ∂P/∂a × ∂P/∂v (yaprağın dış/sırt yüzüne doğru; üçgen sarımıyla aynı)."""
    da = np.gradient(pos, axis=1)
    db = np.gradient(pos, axis=0)
    n = np.cross(da, db)
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def grid_indices(nb=NB, na=NA):
    idx = np.arange(nb * na).reshape(nb, na)
    q = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    return np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]]).astype("i4")


class Rose:
    """Gülün tüm yaprakları. `build(bloom)` -> köşe dizileri."""

    def __init__(self, n=N_PETALS, seed=7):
        rng = np.random.default_rng(seed)
        self.petals = [Petal(i, n, rng) for i in range(n)]
        self.n = n
        self.tri = grid_indices()
        self.tri_all = np.concatenate([self.tri + j * NA * NB for j in range(n)])

    def petal(self, i, b, flex=None):
        p = self.petals[i]
        pos, uv = petal_surface(p, p.params(b), flex=flex)
        return pos, grid_normals(pos), uv

    def hinge(self, i, b):
        """Yaprağın tabanı (gül uzayında) ve menteşe ekseni (teğet yön)."""
        p = self.petals[i]
        prm = p.params(b)
        base = np.array([prm["r0"] * np.sin(p.phi), prm["h0"], prm["r0"] * np.cos(p.phi)])
        axis = np.array([np.cos(p.phi), 0.0, -np.sin(p.phi)])
        return base, axis

    def build(self, bloom):
        """bloom: skaler ya da yaprak başına dizi. (pos, nrm, uv, info) düz diziler + üçgenler."""
        bloom = np.broadcast_to(np.asarray(bloom, float), (self.n,))
        P, N, U, I = [], [], [], []
        for i, p in enumerate(self.petals):
            pos, nrm, uv = self.petal(i, float(bloom[i]))
            P.append(pos.reshape(-1, 3))
            N.append(nrm.reshape(-1, 3))
            U.append(uv.reshape(-1, 2))
            I.append(np.tile([p.k, i], (pos.shape[0] * pos.shape[1], 1)))
        return (np.concatenate(P).astype("f4"), np.concatenate(N).astype("f4"),
                np.concatenate(U).astype("f4"), np.concatenate(I).astype("f4"), self.tri_all)
