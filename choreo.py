"""İki karakterin koreografisi (GLITCH / Amazing Digital Circus açılışındaki
Pomni ve Caine hareketleri örnek alınarak).

Klasik animasyon prensipleriyle kurulur:
  * anahtar pozlar + ara geçişler: her eklem için zaman-değer anahtarları,
    aralar kübik eğriyle dolar; uç noktalarda teğet düzleşir (slow in / slow out),
    böylece kol savrulmanın ucunda yavaşlar, ortasında hızlanır;
  * overlap / follow-through: gövde hareketi başlatır, kafa, kollar ve bacaklar
    birkaç kare geriden gelir (her parçanın kendi gecikmesi var);
  * drag ve settle: kollar ve bacaklar sarkaç gibi davranır; karakter yukarı
    fırlarken geride (aşağıda) kalır, tepede durunca savrulup yerine oturur,
    düşerken yukarı kalkar. Bu, kök hareketin ivmesinden fiziksel olarak
    hesaplanır, yani pozlar arasındaki geçiş her zaman birbirini tutar;
  * arcs: kök yol düz bir çizgi değil, hafif yay çizer; asılı kalışta
    karakter tamamen durmaz (moving hold);
  * anticipation: düşüşten hemen önce küçük bir yükselip toplanma.

Fonksiyonlar karakterin sahneye girişinden beri geçen süreyi (tau) alır ve
(parça dönüşleri, kök dönüşü, kök konumu) döndürür.
"""
import math

import numpy as np

from rig import euler

PARTS = ("torso", "head", "right_arm", "left_arm", "right_leg", "left_leg")
# Karakter kameraya bakarken right_arm / right_leg ekranın SOL tarafındadır.
# Kol ve bacakta x+ öne (kameraya), gövdede x- öne eğilme, kafada x+ yukarı bakış.

# Overlap: gövde önden gider, diğerleri birkaç kare geriden izler (saniye)
DELAY = {"torso": 0.0, "head": 0.05, "right_arm": 0.035, "left_arm": 0.03,
         "right_leg": 0.055, "left_leg": 0.06}


class Curve:
    """Anahtarlardan geçen kübik eğri. Uçta (yerel tepe/çukur) teğet sıfırlanır,
    böylece değer anahtarı aşmaz ve orada yavaşlar (slow in / slow out)."""

    def __init__(self, keys):
        self.t = np.array([k[0] for k in keys], float)
        self.v = np.array([k[1] for k in keys], float)
        n = len(keys)
        self.m = np.zeros(n)
        for i in range(1, n - 1):
            a, b = self.v[i] - self.v[i - 1], self.v[i + 1] - self.v[i]
            if a * b <= 0:
                continue                                           # uç nokta: düz teğet
            m = (self.v[i + 1] - self.v[i - 1]) / (self.t[i + 1] - self.t[i - 1])
            # aşmayı önle (monoton kübik sınırı)
            lim = 3 * min(abs(a) / (self.t[i] - self.t[i - 1]), abs(b) / (self.t[i + 1] - self.t[i]))
            self.m[i] = math.copysign(min(abs(m), lim), m)

    def __call__(self, t):
        if t <= self.t[0]:
            return self.v[0]
        if t >= self.t[-1]:
            return self.v[-1]
        i = int(np.searchsorted(self.t, t) - 1)
        h = self.t[i + 1] - self.t[i]
        u = (t - self.t[i]) / h
        h00, h10 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u
        h01, h11 = -2 * u**3 + 3 * u**2, u**3 - u**2
        return h00 * self.v[i] + h10 * h * self.m[i] + h01 * self.v[i + 1] + h11 * h * self.m[i + 1]


class Track:
    """Bir parçanın (x, y, z) açı anahtarları."""

    def __init__(self, keys):
        self.curves = [Curve([(t, v[k]) for t, v in keys]) for k in range(3)]

    def __call__(self, t):
        return tuple(c(t) for c in self.curves)


def vertical(tau, rise, hang, top, bottom, drop, bob=0.0, bob_at=0.0):
    """Kökün yüksekliği: hızlı yükseliş ve küçük aşma, asılıyken yavaş süzülme,
    düşüşten önce küçük bir sıçrama (anticipation), sonra yerçekimiyle düşüş."""
    u = min(max(tau / rise, 0.0), 1.0)
    s = 1.6
    y = bottom + (top - bottom) * (1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2)
    hold = tau - rise
    if hold > 0:
        y += 0.15 * math.sin(math.pi * min(hold / hang, 1.0))
    if bob:
        b = (tau - bob_at) / (rise + hang - bob_at)
        if 0 < b < 1:
            y += bob * math.sin(math.pi * b) ** 2
    fall = tau - rise - hang
    if fall > 0:
        y -= drop * fall * fall
    return y


class Choreo:
    """Anahtar pozlar + sarkaç ikincil hareketi. Alt sınıflar anahtarları ve kök
    hareketini tanımlar."""
    end = 2.0
    keys = {}
    swing = ("right_arm", "left_arm", "right_leg", "left_leg")

    def __init__(self):
        self.keys = self._resolve_aims(self.keys)
        self.tracks = {p: Track(k) for p, k in self.keys.items()}
        self._simulate()

    def _resolve_aims(self, keys):
        """{"aim": yön} anahtarlarını omuz/kalça açısına çevirir. Yön dünya
        koordinatındadır (ekranın sağı -x, yukarı +y, kameraya doğru -z); açı,
        o andaki kök ve gövde duruşuna göre hesaplanır. Böylece kol, gövde nasıl
        dönmüş olursa olsun ekranda istenen yöne bakar (pozun okunurluğu)."""
        torso = Track(keys["torso"])
        out = {}
        for part, ks in keys.items():
            new, prev = [], None
            for t, v in ks:
                if isinstance(v, dict):
                    rx, ry, rz, _, _ = self.root(t)
                    parent = euler(x=rx, y=ry, z=rz) @ euler(*torso(t - DELAY["torso"]))
                    d = np.asarray(v["aim"], float)
                    loc = parent.T @ (d / np.linalg.norm(d))
                    z = math.asin(min(max(loc[0], -1.0), 1.0))
                    x = math.atan2(-loc[2], -loc[1])
                    if prev is not None:                  # en kısa yoldan dönsün
                        x += 2 * math.pi * round((prev[0] - x) / (2 * math.pi))
                    v = (x, v.get("twist", 0.0), z)
                new.append((t, v))
                prev = v
            out[part] = new
        return out

    # --- alt sınıfın dolduracağı kök hareketi
    def root(self, tau):
        raise NotImplementedError

    def height(self, tau):
        raise NotImplementedError

    def base_pose(self, tau):
        pose = {p: self.tracks[p](tau - DELAY[p]) for p in self.tracks}
        # kalça: gövde öne eğilince bacaklar büyük ölçüde aşağı sarkmaya devam eder
        lean = pose["torso"][0]
        for leg in ("right_leg", "left_leg"):
            x, y, z = pose[leg]
            pose[leg] = (x - 0.8 * lean, y, z)
        return pose

    def _simulate(self):
        """Kollar/bacaklar ve kafa için ikincil hareket: dikey ivmeye tepki veren
        sönümlü sarkaçlar. Önceden hesaplanır, sonra her kare için okunur."""
        dt = 1 / 600
        n = int(self.end / dt) + 2
        self.sim_t = np.arange(n) * dt
        ys = np.array([self.height(t) for t in self.sim_t])
        acc = np.gradient(np.gradient(ys, dt), dt)
        acc[:12] = acc[12]                                  # ekrana girmeden önceki ani başlangıç
        acc = 45 * np.tanh(acc / 45)                        # çok sert ivmeler yumuşak sınırlanır
        w0, zeta, gain = 2 * math.pi * 2.2, 0.32, 5.0       # doğal frekans, sönüm (hafif salınım: settle)
        self.sim = {}
        for part in self.swing:
            for axis in (0, 2):
                d = v = 0.0
                out = np.zeros(n)
                for i, t in enumerate(self.sim_t):
                    base = self.base_pose(t)[part][axis]
                    # yukarı ivme sarkacı aşağı (0'a) iter, düşüş yukarı (pi'ye) kaldırır
                    torque = -gain * acc[i] * math.sin(base + d) * (1.0 if axis == 0 else 0.6)
                    a = torque - w0 * w0 * d - 2 * zeta * w0 * v
                    v += a * dt
                    d += v * dt
                    out[i] = d
                self.sim[(part, axis)] = out
        # kafa: ivmeyle öne-arkaya küçük sallanma (follow-through)
        d = v = 0.0
        out = np.zeros(n)
        w1, z1 = 2 * math.pi * 3.0, 0.4
        for i in range(n):
            a = 0.012 * acc[i] - w1 * w1 * d - 2 * z1 * w1 * v
            v += a * dt
            d += v * dt
            out[i] = d
        self.sim[("head", 0)] = out

    def _sim(self, key, tau):
        return float(np.interp(tau, self.sim_t, self.sim[key])) if key in self.sim else 0.0

    def pose(self, tau):
        pose = self.base_pose(tau)
        out = {}
        for part, (x, y, z) in pose.items():
            out[part] = (x + self._sim((part, 0), tau), y, z + self._sim((part, 2), tau))
        return out

    def state(self, tau):
        pose = self.pose(tau)
        rx, ry, rz, px, pz = self.root(tau)
        mats = {p: euler(*a) for p, a in pose.items()}
        return mats, euler(x=rx, y=ry, z=rz), np.array([px, self.height(tau), pz])


class AndroeChoreo(Choreo):
    """1. karakter - Pomni gibi: aşağıdan fırlar, havada panikle kollarını
    değirmen gibi çevirir, bacakları boşlukta pedal çevirir; sonra düşer."""
    end = 1.7
    RISE, HANG = 0.28, 0.8

    keys = {
        # gövde öne (kameraya) eğik; kollara karşı hafifçe burulur (counteraction)
        "torso": [(0.0, (-0.05, 0.0, 0.0)), (0.3, (-0.25, -0.15, 0.05)), (0.45, (-0.4, -0.25, 0.0)),
                  (0.62, (-0.3, 0.05, -0.05)), (0.78, (-0.28, 0.25, 0.05)), (0.95, (-0.38, -0.1, 0.0)),
                  (1.08, (-0.25, 0.0, 0.0)), (1.4, (-0.05, 0.0, 0.0))],
        # kafa kalkık, kameraya bakar; gövde burulmasını kısmen geri alır
        "head": [(0.0, (0.3, 0.0, 0.0)), (0.3, (0.75, 0.1, 0.1)), (0.45, (0.9, 0.15, 0.0)),
                 (0.62, (0.8, -0.05, -0.1)), (0.78, (0.85, -0.15, 0.05)), (0.95, (0.9, 0.05, 0.05)),
                 (1.1, (0.65, 0.0, 0.0)), (1.4, (0.25, 0.0, 0.0))],
        # ekranın sağındaki kol: kameraya uzanır, önden aşağı iner, arkadan
        # tepeye dolaşıp yeniden öne gelir (geriye doğru değirmen)
        "left_arm": [(0.0, (-0.35, 0.0, -0.2)), (0.18, (0.2, 0.0, -0.25)), (0.34, (2.55, 0.0, -0.7)),
                     (0.45, (2.35, 0.0, -0.55)), (0.59, (0.6, 0.0, -0.2)), (0.68, (-0.6, 0.0, -0.45)),
                     (0.78, (-2.0, 0.0, -0.6)), (0.88, (-3.3, 0.0, -0.4)), (0.98, (-4.2, 0.0, -0.3)),
                     (1.08, (-4.5, 0.0, -0.35)), (1.4, (-3.5, 0.0, -0.8))],
        # ekranın solundaki kol: önce önde aşağıda, sonra arkaya-yukarı savrulur
        # ve kamçı gibi öne iner (diğer koldan farklı zamanlama: ikizlenme yok)
        "right_arm": [(0.0, (-0.3, 0.0, 0.2)), (0.2, (0.1, 0.0, 0.25)), (0.37, (0.95, 0.0, 0.3)),
                      (0.5, (0.45, 0.0, 0.35)), (0.63, (-1.1, 0.0, 0.5)), (0.74, (-2.5, 0.0, 0.7)),
                      (0.86, (-1.0, 0.0, 0.55)), (0.98, (0.8, 0.0, 0.35)),
                      (1.1, (1.0, 0.0, 0.3)), (1.4, (2.9, 0.0, 0.8))],
        # bacaklar boşlukta pedal çevirir (farklı fazlarda)
        "right_leg": [(0.0, (-0.1, 0.0, 0.08)), (0.3, (0.9, 0.0, 0.15)), (0.46, (-0.35, 0.0, 0.1)),
                      (0.62, (1.05, 0.0, 0.2)), (0.78, (-0.25, 0.0, 0.1)), (0.93, (0.95, 0.0, 0.2)),
                      (1.08, (0.1, 0.0, 0.1)), (1.4, (-0.3, 0.0, 0.25))],
        "left_leg": [(0.0, (-0.05, 0.0, -0.08)), (0.26, (-0.3, 0.0, -0.1)), (0.42, (1.0, 0.0, -0.18)),
                     (0.58, (-0.3, 0.0, -0.1)), (0.74, (1.0, 0.0, -0.2)), (0.89, (-0.2, 0.0, -0.1)),
                     (1.04, (0.85, 0.0, -0.15)), (1.4, (0.5, 0.0, -0.3))],
    }

    def __init__(self):
        # 3/4 dönük; tüm gövde öne ve ekranın soluna yatık (kafa sol üstte, ayaklar sağ altta)
        self.yaw = Curve([(0.0, -0.3), (0.4, -0.6), (0.75, -0.45), (1.08, -0.2), (1.5, 0.15)])
        self.tilt = Curve([(0.0, -0.05), (0.32, -0.3), (0.7, -0.24), (1.08, -0.28), (1.5, 0.35)])
        self.roll = Curve([(0.0, 0.0), (0.32, -0.36), (0.55, -0.26), (0.8, -0.38), (1.05, -0.24), (1.5, 0.15)])
        self.px = Curve([(0.0, 0.1), (0.3, 0.4), (1.08, 0.9), (1.6, 0.5)])
        self.pz = Curve([(0.0, 0.0), (0.3, -2.3), (0.7, -2.5), (1.08, -2.0), (1.6, -1.0)])
        super().__init__()

    def height(self, tau):
        return vertical(tau, self.RISE, self.HANG, top=1.55, bottom=-7.0, drop=17.0, bob=0.12, bob_at=0.9)

    def root(self, tau):
        return self.tilt(tau), self.yaw(tau), self.roll(tau), self.px(tau), self.pz(tau)


class OfficialChoreo(Choreo):
    """2. karakter - Caine gibi: dik ve toplu hâlde dönerek yükselir, dönüş
    yavaşlarken kollar ve bacaklar açılır; ayaktan uzanan ele kadar ekranı
    çapraz kesen tek bir çizgide asılı kalır (moving hold), sonra düşer."""
    end = 1.8
    RISE, HANG = 0.34, 0.88

    keys = {
        "torso": [(0.0, (0.0, 0.0, 0.0)), (0.3, (0.0, 0.0, 0.0)), (0.43, (-0.3, 0.1, 0.0)),
                  (0.55, (-0.2, 0.08, 0.0)), (0.85, (-0.24, 0.02, 0.03)), (1.12, (-0.2, -0.04, 0.0)),
                  (1.2, (-0.12, 0.0, 0.0)), (1.6, (0.0, 0.0, 0.0))],
        # kafa gövde çizgisine rağmen dik kalmaya ve kameraya bakmaya çalışır
        "head": [(0.0, (0.1, 0.0, 0.0)), (0.34, (0.25, 0.0, 0.0)), (0.47, (0.95, 0.05, -0.55)),
                 (0.6, (0.8, 0.0, -0.45)), (0.85, (0.85, -0.08, -0.5)), (1.12, (0.82, 0.05, -0.45)),
                 (1.6, (0.3, 0.0, 0.0))],
        # ekranın sağındaki kol gövde çizgisini sürdürerek yukarı-yana uzanır; asılıyken
        # yavaşça daha da açılır
        "left_arm": [(0.0, (0.0, 0.0, -0.08)), (0.3, (0.0, 0.0, -0.15)),
                     (0.43, {"aim": (-0.45, 0.88, 0.1)}), (0.54, {"aim": (-0.7, 0.7, 0.12)}),
                     (0.85, {"aim": (-0.6, 0.79, 0.12)}), (1.1, {"aim": (-0.55, 0.83, 0.1)}),
                     (1.18, {"aim": (-0.75, 0.62, 0.0)}), (1.5, (0.2, 0.0, -3.0))],
        # ekranın solundaki kol bükük, kalça hizasında (Caine'in bastonlu eli gibi)
        "right_arm": [(0.0, (0.0, 0.0, 0.08)), (0.3, (0.0, 0.0, 0.12)),
                      (0.45, {"aim": (0.7, -0.6, -0.4)}), (0.57, {"aim": (0.55, -0.75, -0.35)}),
                      (0.85, {"aim": (0.5, -0.78, -0.38)}), (1.1, {"aim": (0.55, -0.75, -0.35)}),
                      (1.18, {"aim": (0.6, -0.7, -0.3)}), (1.5, (2.8, 0.0, 0.6))],
        # bacaklar çizgiyi sol alta uzatır: biri dizden kırık gibi yana-öne, diğeri düz
        "right_leg": [(0.0, (0.0, 0.0, 0.0)), (0.3, (0.05, 0.0, 0.04)), (0.46, (0.75, 0.0, 0.8)),
                      (0.57, (0.6, 0.0, 0.65)), (0.85, (0.7, 0.0, 0.72)), (1.1, (0.62, 0.0, 0.68)),
                      (1.18, (0.45, 0.0, 0.45)), (1.5, (0.3, 0.0, 0.3))],
        "left_leg": [(0.0, (0.0, 0.0, 0.0)), (0.3, (0.0, 0.0, -0.03)), (0.46, (-0.35, 0.0, 0.15)),
                     (0.57, (-0.25, 0.0, 0.1)), (0.85, (-0.15, 0.0, 0.2)), (1.1, (-0.28, 0.0, 0.12)),
                     (1.18, (-0.1, 0.0, 0.05)), (1.5, (-0.5, 0.0, -0.3))],
    }

    def __init__(self):
        # çapraz çizgi (line of action): kafa sağ üste, ayaklar sol alta; hafif aşıp oturur
        self.roll = Curve([(0.0, 0.0), (0.28, 0.1), (0.43, 0.6), (0.54, 0.46), (0.85, 0.5), (1.15, 0.56), (1.6, -0.2)])
        self.tilt = Curve([(0.0, 0.0), (0.43, -0.12), (1.15, -0.08), (1.6, 0.5)])
        self.drift = Curve([(0.34, 0.2), (1.2, 0.32), (1.7, 1.4)])
        self.px = Curve([(0.0, -0.8), (0.34, 0.1), (1.2, 0.4), (1.7, 1.2)])
        # hızla kameraya yaklaşır, asılıyken yavaşça uzaklaşır (referanstaki boy değişimi)
        self.pz = Curve([(0.0, 1.0), (0.4, -3.6), (0.55, -3.4), (1.2, -2.5), (1.7, -1.2)])
        super().__init__()

    def height(self, tau):
        return vertical(tau, self.RISE, self.HANG, top=0.3, bottom=-8.0, drop=17.0, bob=0.14, bob_at=1.0)

    def root(self, tau):
        u = min(max(tau / self.RISE, 0.0), 1.0)
        spin = -2 * math.pi * (1 - u) ** 2                       # yükselirken bir tur, yavaşlayarak
        yaw = spin + (self.drift(tau) if tau > self.RISE else 0.2)
        return self.tilt(tau), yaw, self.roll(tau), self.px(tau), self.pz(tau)
