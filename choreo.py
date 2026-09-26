"""İki karakterin koreografisi (GLITCH / Amazing Digital Circus açılışındaki
Pomni ve Caine hareketleri örnek alınarak, R6 rig'ine uyarlanmış).

Referans video kare kare (30 fps) incelenip zamanlama birebir alındı:
  Pomni  5.10 fırlar, 5.27 kol kameraya uzanır (tepe), 5.30-5.33 kol aşağı
         süpürür, 5.37-5.40 havada çömelip kısa durur, 5.43 dönüp kolunu arkaya
         kurar, 5.47-5.50 kısa durur, 5.53 kamçı gibi savurur, 5.60-5.70 kollar
         açılıp yukarı kalkarken çöker ve kameraya yaklaşarak düşer (5.77).
  Caine  5.90 sırtı dönük, toplu dönerek yükselir, 6.03-6.07 dizlerini karnına
         çekip yay gibi kurulur, 6.10-6.13 patlar (kollar açılır, bacak kameraya
         fırlar), 6.17 aşar, 6.20-6.23 çapraz pozuna oturur, 6.27-6.50 geri
         çekilerek asılı kalır, 6.53 toplanır, 6.57-6.63 kollar yukarıda düşer.

Hareket "pozdan poza yumuşak geçiş" değil, fiziksel bir eylem olarak kurulur:
  * her geçişin kendi hız eğrisi var (spacing): hazırlıkta yavaş, eylemde çok
    hızlı, tepede kısa okunur duruş, sonra kontrollü yavaşlama;
  * anticipation: büyük hareketten önce ters yönde sıkışma (squash, dizler
    gövdeye, kollar içe); ardından uzama (stretch) ile boşalma;
  * lead & follow: kök/kalça önce, sonra gövde, omuz, kol, en son kafa gelir
    (DELAY); uzanan kol gibi hareketi başlatan parça anahtarlarda öne alınır;
  * counteraction: kol bir yöne savrulurken gövde ters yöne burulur, kafa
    gövdenin eğimini dengeler;
  * overshoot & settle: patlamadan sonra hedefi hafifçe aşıp geri oturur;
    ikincil parçalar (kollar, bacaklar) ivmeye tepkiyle birkaç kare geç oturur;
  * R6 hileleri (Roblox'ta Motor6D konumunu key'lemek gibi): kol omuzdan uzar,
    dizler gövdeye çekilir, tüm beden squash & stretch yapar.

Fonksiyonlar karakterin bölümü başladığından beri geçen süreyi (tau) alır.
"""
import math

import numpy as np

from rig import euler

# Karakter kameraya bakarken right_arm / right_leg ekranın SOL tarafındadır.
# Kol ve bacakta x+ öne (kameraya), gövdede x- öne eğilme, kafada x+ yukarı bakış.
# right_arm z+ / left_arm z- kolu yana-yukarı açar. Kaydırmalar gövde uzayında:
# +x karakterin sağı (right_arm tarafı), +y yukarı, -z ileri (kameraya).
# Kökte y+ ekranın sağına döner, z+ kafayı ekranın sağına yatırır.

# Lead & follow: kök hareketi başlatır, gövde 1 kare, kollar ~2, bacaklar ~2,
# kafa ~3 kare geriden gelir.
DELAY = {"torso": 0.012, "right_arm": 0.025, "left_arm": 0.025,
         "right_leg": 0.03, "left_leg": 0.03, "head": 0.045}

# Geçiş hız eğrileri (spacing). Anahtardaki mod, o anahtardan SONRAKİ geçişe uygulanır.
EASE = {
    "auto": None,                                    # komşulara göre yumuşak kübik (breakdown)
    "lin": lambda u: u,
    "in": lambda u: u * u,                           # yavaş başla, hızlanarak bitir (eyleme giriş, düşüş)
    "out": lambda u: 1 - (1 - u) ** 2,               # hızlı başla, yavaşlayarak otur
    "snap": lambda u: 1 - (1 - u) ** 4,              # patlayıcı: ilk karelerde yolun çoğu alınır
    "io": lambda u: u * u * (3 - 2 * u),             # yavaş-hızlı-yavaş (moving hold, geri çekilme)
    "hold": lambda u: 0.0,                           # sabit (kısa okunur duruş)
}


class Curve:
    """Anahtarlardan geçen eğri; her aralık kendi hız eğrisiyle (spacing) ilerler.
    "auto" aralıklarda uçlarda teğet düzleşen monoton kübik kullanılır, böylece
    değer anahtarı istemsizce aşmaz; aşma istenen yerde ayrı anahtarla verilir."""

    def __init__(self, keys):
        self.t = np.array([k[0] for k in keys], float)
        self.v = np.array([k[1] for k in keys], float)
        self.mode = [k[2] if len(k) > 2 else "auto" for k in keys]
        n = len(keys)
        self.m = np.zeros(n)
        for i in range(1, n - 1):
            a, b = self.v[i] - self.v[i - 1], self.v[i + 1] - self.v[i]
            if a * b <= 0:
                continue
            m = (self.v[i + 1] - self.v[i - 1]) / (self.t[i + 1] - self.t[i - 1])
            lim = 3 * min(abs(a) / (self.t[i] - self.t[i - 1]), abs(b) / (self.t[i + 1] - self.t[i]))
            self.m[i] = math.copysign(min(abs(m), lim), m)

    def __call__(self, t):
        if t <= self.t[0]:
            return self.v[0]
        if t >= self.t[-1]:
            return self.v[-1]
        i = int(np.searchsorted(self.t, t, side="right") - 1)
        h = self.t[i + 1] - self.t[i]
        u = (t - self.t[i]) / h
        ease = EASE[self.mode[i]]
        if ease is not None:
            return self.v[i] + (self.v[i + 1] - self.v[i]) * ease(u)
        h00, h10 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u
        h01, h11 = -2 * u**3 + 3 * u**2, u**3 - u**2
        return h00 * self.v[i] + h10 * h * self.m[i] + h01 * self.v[i + 1] + h11 * h * self.m[i + 1]


class Track:
    """Bir parçanın dönüş (x, y, z) ve kaydırma (ox, oy, oz) anahtarları.
    Anahtar: (t, değer) ya da (t, değer, mod); değer 3'lü (yalnız dönüş) ya da 6'lı."""

    def __init__(self, keys):
        rows = []
        for k in keys:
            v = tuple(k[1]) + (0.0,) * (6 - len(k[1]))
            rows.append((k[0], v) + tuple(k[2:]))
        self.curves = [Curve([(r[0], r[1][c]) + r[2:] for r in rows]) for c in range(6)]

    def __call__(self, t):
        return tuple(c(t) for c in self.curves)


class Choreo:
    """Anahtar pozlar + kök hareketi + ivmeye tepki veren ikincil hareket."""
    end = 1.0
    keys = {}
    root_keys = {}                  # "x","y","z" konum; "rx","ry","rz" dönüş; "sy" squash
    swing = ("right_arm", "left_arm", "right_leg", "left_leg")
    drag_gain = 2.2

    def __init__(self):
        self.root_curves = {k: Curve(v) for k, v in self.root_keys.items()}
        self.keys = self._resolve_aims(self.keys)
        self.tracks = {p: Track(k) for p, k in self.keys.items()}
        self._simulate()

    def _root(self, name, tau, default=0.0):
        c = self.root_curves.get(name)
        return c(tau) if c else default

    def root(self, tau):
        return tuple(self._root(n, tau) for n in ("rx", "ry", "rz", "x", "z"))

    def height(self, tau):
        return self._root("y", tau)

    def _resolve_aims(self, keys):
        """{"aim": yön} anahtarlarını omuz/kalça açısına çevirir. Yön dünya
        koordinatındadır (ekranın sağı -x, yukarı +y, kameraya doğru -z); açı o
        andaki kök ve gövde duruşundan hesaplanır, böylece gövde nasıl dönmüş
        olursa olsun kol ekranda istenen yöne bakar (pozun okunurluğu)."""
        torso = Track(keys["torso"])
        out = {}
        for part, ks in keys.items():
            new, prev = [], None
            for k in ks:
                t, v = k[0], k[1]
                if isinstance(v, dict):
                    rx, ry, rz, _, _ = self.root(t)
                    parent = euler(x=rx, y=ry, z=rz) @ euler(*torso(t - DELAY["torso"])[:3])
                    d = np.asarray(v["aim"], float)
                    loc = parent.T @ (d / np.linalg.norm(d))
                    z = math.asin(min(max(loc[0], -1.0), 1.0))
                    x = math.atan2(-loc[2], -loc[1])
                    if prev is not None:                  # en kısa yoldan dönsün
                        x += 2 * math.pi * round((prev[0] - x) / (2 * math.pi))
                    v = (x, 0.0, z) + tuple(v.get("off", (0.0, 0.0, 0.0)))
                new.append((t, v) + tuple(k[2:]))
                prev = v
            out[part] = new
        return out

    def base_pose(self, tau):
        return {p: self.tracks[p](tau - DELAY[p]) for p in self.tracks}

    def _simulate(self):
        """Overlap: kollar ve bacaklar kök ivmesine sönümlü sarkaç gibi tepki
        verir (hızlı yön değişiminde geride kalır, durunca birkaç kare geç
        oturur). Etkisi bilerek küçük tutulur; ana hareket anahtarlardadır."""
        dt = 1 / 600
        n = int(self.end / dt) + 2
        self.sim_t = np.arange(n) * dt
        ys = np.array([self.height(t) for t in self.sim_t])
        acc = np.gradient(np.gradient(ys, dt), dt)
        acc = 40 * np.tanh(acc / 40)
        w0, zeta = 2 * math.pi * 3.0, 0.45
        self.sim = {}
        bases = [self.base_pose(t) for t in self.sim_t]
        for part in self.swing:
            for axis in (0, 2):
                d = v = 0.0
                out = np.zeros(n)
                for i in range(n):
                    base = bases[i][part][axis]
                    torque = -self.drag_gain * acc[i] * math.sin(base + d) * (1.0 if axis == 0 else 0.6)
                    a = torque - w0 * w0 * d - 2 * zeta * w0 * v
                    v += a * dt
                    d += v * dt
                    out[i] = d
                self.sim[(part, axis)] = out

    def pose(self, tau):
        out = {}
        for part, v in self.base_pose(tau).items():
            x, y, z = v[:3]
            if (part, 0) in self.sim:
                x += float(np.interp(tau, self.sim_t, self.sim[(part, 0)]))
                z += float(np.interp(tau, self.sim_t, self.sim[(part, 2)]))
            out[part] = (x, y, z) + tuple(v[3:])
        return out

    def state(self, tau):
        """(parça dönüş+kaydırmaları, kök dönüşü, kök konumu, squash ölçeği)."""
        pose = self.pose(tau)
        rx, ry, rz, px, pz = self.root(tau)
        mats = {p: (euler(*a[:3]), a[3:]) for p, a in pose.items()}
        sy = self._root("sy", tau, 1.0)
        squash = (1 / math.sqrt(sy), sy, 1 / math.sqrt(sy))       # hacim korunur
        return mats, euler(x=rx, y=ry, z=rz), np.array([px, self.height(tau), pz]), squash


class AndroeChoreo(Choreo):
    """1. karakter - Pomni: fırlar, kolu kameraya uzanır, süpürür, havada çömelir,
    dönüp kolunu kurar ve kamçılar, sonra kollar yukarıda çöküp düşer.
    tau = referans saniyesi - 5.02."""
    end = 1.0

    root_keys = {
        # yükseliş: çok hızlı, tepede küçük aşma; asılıyken yavaş çökme; sonra hızlanan düşüş
        "y": [(0.05, -7.5, "out"), (0.13, -1.2, "out"), (0.17, 0.8, "out"), (0.213, 1.45, "out"),
              (0.247, 1.25, "io"), (0.313, 1.1), (0.38, 0.95, "io"), (0.48, 1.0),
              (0.58, 0.8, "in"), (0.647, 0.35, "in"), (0.70, -0.2, "in"), (0.75, -1.4, "in"),
              (0.8, -4.0, "in"), (0.86, -9.0)],
        "x": [(0.06, 0.1), (0.25, 0.45), (0.45, 0.25), (0.58, 0.3), (0.78, 0.05)],
        # sonunda kameraya yaklaşarak düşer (referansta Pomni büyür)
        "z": [(0.05, -0.6), (0.21, -3.3), (0.55, -3.5, "in"), (0.7, -5.4, "in"), (0.8, -8.8)],
        "ry": [(0.06, -0.25), (0.25, -0.35), (0.38, -0.3), (0.413, -0.62, "hold"), (0.405, -0.62),
               (0.48, -0.55), (0.53, -0.3), (0.62, -0.2), (0.8, -0.1)],
        # gövde çizgisi: sola yatık (kafa sol üstte), kamçıda doğrulur
        "rz": [(0.06, -0.1), (0.21, -0.3), (0.3, -0.22), (0.38, -0.12), (0.413, -0.42, "io"),
               (0.48, -0.35), (0.53, -0.08), (0.6, 0.02), (0.8, 0.1)],
        "rx": [(0.06, 0.0), (0.3, -0.15), (0.4, -0.25), (0.6, -0.08), (0.8, 0.2)],
        # squash & stretch: fırlarken uzar, tepede sıkışır, çömelmede basılır, düşerken uzar
        "sy": [(0.06, 1.16, "out"), (0.18, 1.04), (0.213, 0.94, "out"), (0.26, 1.0), (0.347, 0.93),
               (0.38, 0.94), (0.413, 1.06, "out"), (0.45, 1.0), (0.6, 1.0, "in"), (0.72, 1.12)],
    }

    keys = {
        "torso": [(0.06, (0.0, 0.0, 0.0)), (0.2, (-0.15, -0.2, 0.0)), (0.247, (-0.2, -0.28, 0.0)),
                  (0.28, (-0.3, -0.15, 0.0), "in"), (0.313, (-0.55, 0.18, 0.0), "out"),
                  (0.347, (-0.65, 0.2, 0.0)), (0.38, (-0.62, 0.15, 0.0), "snap"),
                  (0.413, (-0.5, 0.35, 0.05)), (0.447, (-0.48, 0.4, 0.0)), (0.48, (-0.5, 0.42, 0.0), "in"),
                  (0.51, (-0.4, -0.25, 0.0), "out"), (0.547, (-0.35, -0.35, 0.0)),
                  (0.58, (-0.15, -0.1, 0.0)), (0.66, (-0.05, 0.0, 0.0)), (0.8, (0.05, 0.0, 0.0))],
        # kafa en son gelir, gövdenin eğimini dengeleyip kameraya bakar
        "head": [(0.06, (0.2, 0.0, 0.0)), (0.2, (0.45, 0.15, 0.1)), (0.26, (0.6, 0.2, 0.1)),
                 (0.313, (0.7, -0.1, 0.0)), (0.38, (0.8, -0.15, 0.05)), (0.413, (0.25, -0.3, -0.15)),
                 (0.48, (0.35, -0.3, -0.1), "in"), (0.53, (0.6, 0.2, 0.05)), (0.6, (0.55, 0.05, 0.0)),
                 (0.7, (0.35, 0.0, 0.0)), (0.8, (0.2, 0.0, 0.0))],
        # ekranın sağındaki kol: hareketi o başlatır, kameraya uzanır (omuzdan uzayarak),
        # süpürür, çömelmede aşağıda kalır, sonra açılıp yukarı kalkar. Yönler ekran
        # düzleminde verilir (aim): sağ -x, yukarı +y, kameraya -z.
        "left_arm": [(0.06, (0.4, 0.0, -0.15)),
                     (0.147, {"aim": (-0.4, 0.5, -0.75), "off": (0.0, 0.0, -0.1)}),
                     (0.18, {"aim": (-0.5, 0.7, -0.5), "off": (-0.05, 0.1, -0.3)}),
                     (0.213, {"aim": (-0.55, 0.75, -0.35), "off": (-0.1, 0.15, -0.45)}),
                     (0.247, {"aim": (-0.6, 0.75, -0.3), "off": (-0.12, 0.15, -0.5)}, "in"),
                     (0.28, {"aim": (-0.85, 0.1, -0.5), "off": (-0.05, 0.05, -0.25)}, "out"),
                     (0.313, {"aim": (-0.45, -0.75, -0.45)}), (0.347, {"aim": (-0.4, -0.8, -0.45)}),
                     (0.38, {"aim": (-0.35, -0.85, -0.4)}, "snap"), (0.413, {"aim": (-0.2, -0.95, 0.1)}),
                     (0.48, {"aim": (-0.3, -0.9, 0.0)}), (0.547, {"aim": (-0.8, -0.5, 0.0)}),
                     (0.58, {"aim": (-1.0, 0.0, 0.0)}), (0.613, {"aim": (-0.85, 0.5, 0.0)}),
                     (0.647, {"aim": (-0.6, 0.8, 0.0)}), (0.7, {"aim": (-0.35, 0.93, 0.0)}),
                     (0.8, {"aim": (-0.2, 0.97, 0.0)})],
        # ekranın solundaki kol: önce aşağıda, dönüşte arkaya-yukarı kurulur (hazırlık),
        # kamçı gibi öne-aşağı iner ve gövdenin önünden öteye geçip oturur (follow-through)
        "right_arm": [(0.06, (-0.1, 0.0, 0.15)), (0.2, {"aim": (0.35, -0.9, -0.2)}),
                      (0.28, {"aim": (0.3, -0.9, -0.3)}), (0.313, {"aim": (0.2, -0.85, -0.5)}),
                      (0.347, {"aim": (0.25, -0.85, -0.45)}), (0.38, {"aim": (0.3, -0.85, -0.4)}, "in"),
                      (0.405, {"aim": (0.95, -0.25, -0.1), "off": (0.08, 0.0, 0.0)}, "out"),
                      (0.44, {"aim": (0.65, 0.6, 0.45), "off": (0.1, 0.1, 0.0)}),
                      (0.447, {"aim": (0.6, 0.7, 0.4), "off": (0.12, 0.12, 0.05)}),
                      (0.48, {"aim": (0.55, 0.75, 0.35), "off": (0.12, 0.12, 0.05)}, "in"),
                      (0.503, {"aim": (0.45, 0.45, -0.75), "off": (0.05, 0.05, -0.1)}),
                      (0.527, {"aim": (0.1, -0.6, -0.8), "off": (0.0, 0.0, -0.2)}, "out"),
                      (0.56, {"aim": (-0.2, -0.9, -0.4)}), (0.58, {"aim": (0.8, -0.6, 0.0)}),
                      (0.613, {"aim": (0.95, -0.1, 0.0)}), (0.647, {"aim": (0.85, 0.5, 0.0)}),
                      (0.7, {"aim": (0.4, 0.9, 0.0)}), (0.8, {"aim": (0.2, 0.97, 0.0)})],
        # bacaklar: havada adım, çömelmede dizler gövdeye çekilir (R6 hilesi), kamçıda yer değiştirir
        "right_leg": [(0.06, (-0.2, 0.0, 0.05, 0.0, -0.1, 0.0)), (0.18, (0.4, 0.0, 0.08)),
                      (0.247, (0.7, 0.0, 0.1)), (0.313, (0.8, 0.0, 0.1, 0.0, 0.3, 0.0)),
                      (0.347, (1.25, 0.0, 0.15, 0.0, 0.75, -0.2)), (0.38, (1.2, 0.0, 0.15, 0.0, 0.7, -0.2), "out"),
                      (0.43, (-0.5, 0.0, 0.1)), (0.48, (-0.6, 0.0, 0.12), "in"), (0.53, (0.2, 0.0, 0.1)),
                      (0.58, (-0.3, 0.0, 0.1)), (0.7, (-0.1, 0.0, 0.2)), (0.8, (0.2, 0.0, 0.25))],
        "left_leg": [(0.06, (-0.2, 0.0, -0.05, 0.0, -0.1, 0.0)), (0.18, (-0.3, 0.0, -0.08)),
                     (0.247, (-0.5, 0.0, -0.1)), (0.313, (0.4, 0.0, -0.1, 0.0, 0.3, 0.0)),
                     (0.347, (0.9, 0.0, -0.15, 0.0, 0.7, -0.2)), (0.38, (0.85, 0.0, -0.15, 0.0, 0.65, -0.2), "out"),
                     (0.43, (0.8, 0.0, -0.1)), (0.48, (0.85, 0.0, -0.12), "in"), (0.53, (-0.2, 0.0, -0.1)),
                     (0.58, (0.6, 0.0, -0.1)), (0.7, (0.3, 0.0, -0.2)), (0.8, (0.1, 0.0, -0.25))],
    }


class OfficialChoreo(Choreo):
    """2. karakter - Caine: sırtı dönük dönerek yükselir, yay gibi kurulur,
    patlayarak açılır, çapraz dramatik pozda geri çekilerek asılı kalır, düşer.
    tau = referans saniyesi - 5.85."""
    end = 1.0
    drag_gain = 1.8

    root_keys = {
        "y": [(0.03, -7.8, "out"), (0.117, -2.2, "out"), (0.183, 0.4, "out"), (0.25, 1.45, "out"),
              (0.3, 1.65), (0.35, 1.55, "io"), (0.65, 1.72, "io"), (0.683, 1.85, "in"),
              (0.717, 1.2, "in"), (0.75, -0.4, "in"), (0.8, -3.4, "in"), (0.86, -8.5)],
        "x": [(0.03, 0.0), (0.2, 0.5), (0.3, 0.85), (0.65, 0.95), (0.86, 1.1)],
        # patlamada kameraya en çok yaklaşır, sonra yavaşça geri çekilir
        "z": [(0.03, -1.0, "out"), (0.25, -5.8, "out"), (0.317, -7.3), (0.4, -6.9, "io"), (0.65, -5.9),
              (0.86, -4.8)],
        # sırtı dönük başlar: bir buçuk tur değil, yarım turdan kameraya döner (yavaşlayarak)
        "ry": [(0.03, -math.pi - 0.6, "out"), (0.117, -2.6, "out"), (0.183, -1.2, "out"),
               (0.25, -0.1, "out"), (0.3, 0.18), (0.65, 0.3), (0.72, 0.1, "in"), (0.86, 1.2)],
        # çapraz çizgi: patlamada aşar, sonra oturur; düşüşte dikleşir
        "rz": [(0.03, 0.2), (0.183, 0.15), (0.25, 0.3, "snap"), (0.317, 0.68, "out"), (0.37, 0.5),
               (0.65, 0.56), (0.683, 0.5, "in"), (0.75, 0.0), (0.86, -0.2)],
        "rx": [(0.03, 0.0), (0.183, 0.1), (0.25, -0.05), (0.317, -0.18), (0.65, -0.1), (0.75, 0.3),
               (0.86, 0.5)],
        # yükselişte uzar, kurulurken basılır, patlamada uzar, oturunca normal; düşüşte uzar
        "sy": [(0.03, 1.15), (0.15, 1.05), (0.217, 0.87, "snap"), (0.283, 1.1, "out"), (0.35, 0.98),
               (0.4, 1.0), (0.683, 0.95, "in"), (0.75, 1.1), (0.8, 1.14)],
    }

    keys = {
        # kurulmada gövde öne kıvrılır, patlamada göğüs açılır, sonra kameraya eğilir
        "torso": [(0.03, (-0.1, 0.0, 0.0)), (0.15, (-0.15, 0.0, 0.0)), (0.217, (-0.38, 0.0, 0.0), "snap"),
                  (0.283, (0.1, 0.1, 0.0), "out"), (0.35, (-0.25, 0.08, 0.0)), (0.5, (-0.22, 0.04, 0.02)),
                  (0.65, (-0.2, -0.03, 0.0)), (0.683, (-0.3, 0.0, 0.0), "in"), (0.75, (0.05, 0.0, 0.0)),
                  (0.86, (0.1, 0.0, 0.0))],
        "head": [(0.03, (0.0, 0.0, 0.0)), (0.183, (-0.15, 0.0, 0.0)), (0.217, (-0.3, 0.0, 0.0), "snap"),
                 (0.283, (0.55, 0.1, -0.2), "out"), (0.35, (0.9, 0.05, -0.5)), (0.5, (0.85, -0.05, -0.45)),
                 (0.65, (0.88, 0.05, -0.48)), (0.72, (0.5, 0.0, -0.1)), (0.86, (0.2, 0.0, 0.0))],
        # ekranın sağındaki kol: kurulmada göğse çekilir, patlamada omuzdan uzayarak
        # yana fırlar, sonra gövde çizgisini sürdürerek sağ üste oturur
        "left_arm": [(0.03, (0.1, 0.0, -0.05, 0.2, 0.0, 0.0)), (0.15, (0.4, 0.0, 0.1, 0.25, 0.0, 0.0)),
                     (0.217, (1.0, 0.0, 0.45, 0.3, 0.05, -0.1), "snap"),
                     (0.283, {"aim": (-0.9, 0.35, -0.25), "off": (-0.35, 0.1, 0.0)}, "out"),
                     (0.35, {"aim": (-0.5, 0.86, 0.1), "off": (-0.15, 0.05, 0.0)}),
                     (0.5, {"aim": (-0.58, 0.8, 0.12), "off": (-0.1, 0.0, 0.0)}),
                     (0.65, {"aim": (-0.55, 0.83, 0.1), "off": (-0.1, 0.0, 0.0)}),
                     (0.683, {"aim": (-0.7, 0.65, 0.0)}, "in"), (0.75, {"aim": (-0.3, 0.95, 0.05)}),
                     (0.86, {"aim": (-0.15, 0.98, 0.05)})],
        # ekranın solundaki kol (bastonlu el): kurulmada göğse, patlamada yana, sonra kalçada
        "right_arm": [(0.03, (0.1, 0.0, 0.05, -0.2, 0.0, 0.0)), (0.15, (0.4, 0.0, -0.1, -0.25, 0.0, 0.0)),
                      (0.217, (1.0, 0.0, -0.45, -0.3, 0.05, -0.1), "snap"),
                      (0.283, {"aim": (0.9, 0.3, -0.3), "off": (0.3, 0.1, 0.0)}, "out"),
                      (0.35, {"aim": (0.62, -0.62, -0.45)}), (0.5, {"aim": (0.55, -0.72, -0.4)}),
                      (0.65, {"aim": (0.55, -0.72, -0.4)}), (0.683, {"aim": (0.7, -0.4, -0.3)}, "in"),
                      (0.705, {"aim": (0.95, 0.2, -0.1)}), (0.75, {"aim": (0.4, 0.9, 0.05)}), (0.86, {"aim": (0.2, 0.97, 0.05)})],
        # bacaklar: yükselişte bitişik, kurulmada dizler gövdeye çekilir (R6 hilesi),
        # patlamada biri kameraya fırlar, diğeri çizgiyi geriye uzatır
        "right_leg": [(0.03, (0.0, 0.0, 0.0, -0.1, 0.0, 0.0)), (0.15, (0.4, 0.0, 0.0, -0.05, 0.15, 0.0)),
                      (0.217, (1.3, 0.0, 0.1, 0.0, 0.55, -0.15), "snap"),
                      (0.283, (1.6, 0.0, 0.5, 0.05, -0.1, -0.25), "out"), (0.35, (1.05, 0.0, 0.7)),
                      (0.5, (0.95, 0.0, 0.72)), (0.65, (1.05, 0.0, 0.68)), (0.683, (0.8, 0.0, 0.4), "in"),
                      (0.75, (0.1, 0.0, 0.15)), (0.86, (-0.2, 0.0, 0.2))],
        "left_leg": [(0.03, (0.0, 0.0, 0.0, 0.1, 0.0, 0.0)), (0.15, (0.2, 0.0, 0.0, 0.05, 0.1, 0.0)),
                     (0.217, (0.9, 0.0, -0.1, 0.0, 0.45, -0.1), "snap"),
                     (0.283, (-0.6, 0.0, 0.1, 0.0, -0.05, 0.1), "out"), (0.35, (-0.3, 0.0, 0.15)),
                     (0.5, (-0.1, 0.0, 0.2)), (0.65, (0.15, 0.0, 0.22)), (0.683, (0.1, 0.0, 0.1), "in"),
                     (0.75, (-0.2, 0.0, -0.1)), (0.86, (-0.4, 0.0, -0.25))],
    }
