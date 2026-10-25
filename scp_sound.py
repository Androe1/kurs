"""SCP sinematiği - ses tasarımı (numpy + scipy ile sentez; hazır ses/örnek kullanılmaz).

Bir SFX sanatçısının katmanlama mantığıyla, her ses fiziksel kaynağından modellenir; saf sinüs
yerine katmanlı, süzülmüş kaynaklar kullanılır:

  zaman çizgisi  0.4 açılış vuruşu | 3.6 sert kesme | 6.8 siyaha karartma | 9.2 logo (en büyük vuruş)
                 vuruşlar görüntüdeki kesmelerle aynı örnekte; her sahnenin sesi kendi aralığında
                 kalır (kesmede 6-30 ms'lik yumuşak kapanış, vuruş altında), yalnızca vuruşların
                 yankısı geçişe taşar.
  depo           oda tonu (bina gövdesi gürlemesi, havalandırma hışırtısı), lamba balastı vızıltısı
                 (süzülmüş darbe dizisi), kapıdan giren rüzgâr, sub-bass vuruşları
  yol            dizel motor: 6 silindirin ateşleme darbeleri, egzoz rezonansı (tarak filtre),
                 formantlar, tıkırtı, turbo; 8 lastikten yuvarlanma ve çakıl çatırtısı,
                 ekipman tıngırtıları. Kaynak kameranın önünden geçen yörüngede hareket eder:
                 Doppler (değişken gecikme), 1/r, hava soğurması, yerden yansıma, ITD/ILD
                 (yaklaşım: TrafficSoundSim, EURASIP 2024). Gece rüzgârı.
  tesis          uzak "whoop" alarm kornası (harmonikli, rezonanslı, doygun; mesafe ve yankı),
                 trafo vızıltısı, rüzgâr; logoya doğru hızlanan sub vuruşları ve ters yankı
  darbe          trailer "hit" katmanları: gürültü geçişi, gövde (perdesi düşen), sub drop, koyu
                 metal çınlama, enkaz gürlemesi, braam, uzun yankı (son vuruşta >2 sn doğal sönüm)
  temizlik       her parçaya 6 ms giriş / 8 ms çıkış yumuşatması (tık yok)
  mastering      bus kompresörü, ITU-R BS.1770-4 ölçümüyle -14 LUFS'e kazanç, 4x aşırı örneklemeli
                 ileri bakışlı true-peak limiter (-1.5 dBTP; AAC kodlaması sonrası < -1 dBTP),
                 sonda 0.5 sn kararma

Zamanlar ve sahne geometrisi Blender'ın yazdığı meta.json'dan gelir (blender/scp_cinematic.py).
"""
import numpy as np
from scipy import ndimage, signal

SR = 48000
TAU = 2 * np.pi
C_SOUND = 343.0

# Varsayılan sahne geometrisi (meta.json'da yoksa; blender/scp_cinematic.py, shot_contain): kamera
# yol kenarında, araçlar y=-5.9 şeridinde 8 m/s ile +x yönünde geçer; merkez x=0'dan geçerken apc_pass.
VEH_SPEED, VEH_Y, LISTENER, RIGHT = 8.0, -5.9, np.array([0.0, -10.4, 0.75]), np.array([0.17, 0.985, 0.0])
TARGET_LUFS, TP_CEIL_DB = -14.0, -1.5
DECLICK_IN, DECLICK_OUT = 0.006, 0.008


# ---------------------------------------------------------------- temel araçlar

def tt(dur):
    return np.arange(int(round(dur * SR))) / SR


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, min(f, SR / 2 - 200), "low", fs=SR, output="sos"), x, axis=0)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR / 2 - 200)], "band", fs=SR, output="sos"), x, axis=0)


def peak_eq(x, f0, gain_db, q=1.0):
    """RBJ peaking EQ."""
    a = 10 ** (gain_db / 40)
    w = TAU * f0 / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * a, -2 * np.cos(w), 1 - al * a]
    aa = [1 + al / a, -2 * np.cos(w), 1 - al / a]
    return signal.lfilter(b, aa, x, axis=0)


def fades(n, fi, fo):
    t = np.arange(n) / SR
    return np.clip(t / fi, 0, 1) * np.clip((n / SR - t) / fo, 0, 1)


def norm(x):
    m = np.max(np.abs(x))
    return x / m if m > 0 else x


def sat(x, drive=2.0):
    return np.tanh(drive * x) / np.tanh(drive)


def pink(n, rng):
    """Voss-McCartney yerine spektral şekillendirme: 1/f gücü."""
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    k = np.arange(len(f))
    k[0] = 1
    return norm(np.fft.irfft(f / np.sqrt(k), n))


def brown(n, rng):
    return norm(hp(np.cumsum(rng.standard_normal(n)), 15))


def env_exp(t, attack, decay):
    return (1 - np.exp(-t / max(attack, 1e-5))) * np.exp(-t / decay)


def stereo(mono, pan=0.0, width=0.0, rng=None):
    """Sabit güç kaydırma; pan dizi de olabilir. width>0: kanallar arası hafif dekorelasyon."""
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    st = np.stack([mono * np.cos(p), mono * np.sin(p)], -1)
    if width > 0:
        d = int(0.00031 * SR)  # 0.3 ms Haas
        st[:, 1] = (1 - width) * st[:, 1] + width * np.concatenate([np.zeros(d), st[:-d, 1]])
    return st


def stft_sweep(x, centers, width_oct, gains=None):
    """Zamanla kayan bant geçiren (whoosh): STFT karelerinde log-frekansta Gauss pencere."""
    nper, hop = 2048, 256
    f, t, Z = signal.stft(x, SR, nperseg=nper, noverlap=nper - hop)
    tc = np.interp(t, np.linspace(0, t[-1], len(centers)), centers)
    lf = np.log2(np.maximum(f, 20))[:, None]
    mask = np.exp(-0.5 * ((lf - np.log2(tc)[None, :]) / width_oct) ** 2)
    if gains is not None:
        mask *= np.interp(t, np.linspace(0, t[-1], len(gains)), gains)[None, :]
    _, y = signal.istft(Z * mask, SR, nperseg=nper, noverlap=nper - hop)
    return y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))


def make_ir(rng, length=3.5, rt60_lo=2.6, rt60_hi=1.1, predelay=0.02, early=()):
    """Stereo yapay yankı: frekansa bağlı sönümlü gürültü + erken yansımalar (ağaç hattı)."""
    t = tt(length)
    ir = np.zeros((len(t), 2))
    for ch in range(2):
        n = rng.standard_normal(len(t))
        lo = lp(n, 500) * np.exp(-6.9 * t / rt60_lo)
        mid = bp(n, 500, 4000) * np.exp(-6.9 * t / ((rt60_lo + rt60_hi) / 2))
        hi = hp(n, 4000) * np.exp(-6.9 * t / rt60_hi) * 0.6
        ir[:, ch] = (lo + mid + hi) * np.clip(t / 0.03, 0, 1)
        for d, g in early:
            i = int((d + rng.uniform(-0.004, 0.004)) * SR)
            if i < len(t):
                ir[i, ch] += g * rng.choice([-1, 1]) * 8
    ir = np.vstack([np.zeros((int(predelay * SR), 2)), ir])
    return ir / np.sqrt((ir ** 2).sum(0).mean())


def convolve(x, ir):
    return np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], -1)


def declick(x, fi=DECLICK_IN, fo=DECLICK_OUT):
    """Baş ve sona yükseltilmiş kosinüs yumuşatma: parça hiçbir zaman sıfır olmayan örnekle
    başlamaz ya da bitmez (dalga biçimi süreksizliği = tık)."""
    x = np.array(x, float)
    n = len(x)
    a, b = min(int(fi * SR), n // 2), min(int(fo * SR), n // 2)
    g = np.ones(n)
    if a:
        g[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if b:
        g[n - b:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(1, b + 1) / b)
    return x * (g[:, None] if x.ndim == 2 else g)


class Mix:
    """Zamana yerleştirme + iki yankı göndermesi (oda: kısa, salon: uzun trailer yankısı).
    Her parça eklenirken yumuşatılır; t_end verilirse parça o anda (sahne sınırı) kapanır."""

    def __init__(self, dur):
        n = int(dur * SR)
        self.dry = np.zeros((n, 2))
        self.room = np.zeros((n, 2))
        self.hall = np.zeros((n, 2))

    def add(self, sig, t0, gain=1.0, pan=0.0, room=0.0, hall=0.0, width=0.0, t_end=None, fo=DECLICK_OUT):
        sig = np.asarray(sig, float) * gain
        if sig.ndim == 1:
            sig = stereo(sig, pan, width)
        if t_end is not None:
            sig = sig[:max(int(round((t_end - t0) * SR)), 0)]
        if len(sig) < 2:
            return
        sig = declick(sig, DECLICK_IN, fo)
        i0 = int(round(t0 * SR))
        a, b = max(i0, 0), min(i0 + len(sig), len(self.dry))
        if b <= a:
            return
        seg = sig[a - i0:b - i0]
        self.dry[a:b] += seg
        self.room[a:b] += seg * room
        self.hall[a:b] += seg * hall

    def add_scene(self, sig, t0, t1, gain=1.0, pan=0.0, width=0.0, ir=None, wet=0.0, fo=0.012):
        """Sahne sesi: yankısı yerelde eklenir ve sahne aralığında [t0, t1) kesilir; böylece
        hiçbir sahne öğesi sonraki sahneye taşmaz. Kapanış (fo) kesmedeki vuruşun altında kalır."""
        sig = np.asarray(sig, float)
        if sig.ndim == 1:
            sig = stereo(sig, pan, width)
        if ir is not None and wet > 0:
            sig = sig + wet * convolve(sig, ir)
        self.add(sig, t0, gain, t_end=t1, fo=fo)


# ---------------------------------------------------------------- dinamik işlemciler

def compress(x, thresh_db=-18, ratio=3.0, attack=0.01, release=0.15, knee=6.0, makeup_db=0.0):
    """RMS algılayıcılı stereo bağlı kompresör."""
    det = np.mean(x ** 2, axis=1)
    a = np.exp(-1 / (SR * 0.005))
    rms = np.sqrt(signal.lfilter([1 - a], [1, -a], det) + 1e-12)
    lvl = 20 * np.log10(rms)
    over = lvl - thresh_db
    gr = np.where(over <= -knee / 2, 0,
                  np.where(over >= knee / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    # saldırı/bırakma: hızlı yükselen, yavaş düşen kazanç azaltma
    aa, ar = np.exp(-1 / (SR * attack)), np.exp(-1 / (SR * release))
    sm_fast = signal.lfilter([1 - aa], [1, -aa], gr)
    sm_slow = signal.lfilter([1 - ar], [1, -ar], gr)
    g = np.maximum(sm_fast, sm_slow)
    return x * (10 ** ((makeup_db - g) / 20))[:, None]


def limit(x, ceiling_db=-1.0, lookahead=0.004, release=0.08):
    ceil = 10 ** (ceiling_db / 20)
    pk = np.max(np.abs(x), axis=1)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    la = int(lookahead * SR)
    need = ndimage.minimum_filter1d(need, size=2 * la + 1, origin=0)
    a = np.exp(-1 / (SR * release))
    g = 1 - signal.lfilter([1 - a], [1, -a], 1 - need)
    g = np.minimum(g, need)
    return x * g[:, None]


# BS.1770-4 K ağırlıklandırma, 48 kHz katsayıları (ön süzgeç raf + RLB yüksek geçiren)
K_B1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
K_A1 = [1.0, -1.69065929318241, 0.73248077421585]
K_B2 = [1.0, -2.0, 1.0]
K_A2 = [1.0, -1.99004745483398, 0.99007225036621]


def lufs(x):
    """Bütünleşik yükseklik (ITU-R BS.1770-4): 400 ms bloklar %75 örtüşmeli, -70 LUFS mutlak ve
    -10 LU göreli kapı."""
    y = signal.lfilter(K_B2, K_A2, signal.lfilter(K_B1, K_A1, x, axis=0), axis=0)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    p = np.cumsum(np.concatenate([[0.0], (y ** 2).sum(1)]))
    starts = np.arange(0, len(y) - blk + 1, hop)
    z = (p[starts + blk] - p[starts]) / blk
    lk = -0.691 + 10 * np.log10(z + 1e-15)
    g = z[lk > -70]
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g = z[(lk > -70) & (lk > rel)]
    return -0.691 + 10 * np.log10(g.mean())


def true_peak_db(x, os=4):
    up = signal.resample_poly(x, os, 1, axis=0)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def tp_limit(x, ceiling_db=TP_CEIL_DB, os=4, lookahead=0.003, release=0.08):
    """True-peak limiter: tepe algısı 4x aşırı örneklenmiş sinyalde (örnekler arası tepeler),
    ileri bakışlı kayan minimum + kutu ortalama saldırı (kazanç tepeye zamanında iner, basamaksız),
    tek kutuplu bırakma."""
    ceil = 10 ** (ceiling_db / 20)
    up = signal.resample_poly(x, os, 1, axis=0)
    pk = np.abs(up).max(1)[:len(x) * os].reshape(len(x), os).max(1)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    L = max(int(lookahead * SR), 1)
    m = ndimage.minimum_filter1d(need, size=L + 1, origin=-(L // 2))       # need[i .. i+L] minimumu
    s_att = ndimage.uniform_filter1d(m, size=L + 1, origin=L // 2)           # m[i-L .. i] ortalaması
    s_att = np.minimum(s_att, need)
    a = np.exp(-1 / (SR * release))
    rel = 1 - signal.lfilter([1 - a], [1, -a], 1 - s_att)
    g = np.minimum(s_att, rel)
    return x * g[:, None]


def master(x, target=TARGET_LUFS, ceiling_db=TP_CEIL_DB):
    """Hedef yüksekliğe kazanç + true-peak sınırlama; limiter yüksekliği biraz düşürdüğü için
    birkaç turda yakınsar."""
    y = x
    for _ in range(6):
        y = tp_limit(y * 10 ** ((target - lufs(y)) / 20), ceiling_db)
        if abs(lufs(y) - target) < 0.05:
            break
    return y


# ---------------------------------------------------------------- ses kaynakları

def transient(rng, dur=0.08, lo=900, hi=9000):
    """Vuruşun önü: süzülmüş gürültü patlaması, 1.5 ms yükselişli (anlık tık yok)."""
    t = tt(dur)
    n = bp(rng.standard_normal(len(t)), lo, hi) * env_exp(t, 0.0015, 0.009)
    body = lp(rng.standard_normal(len(t)), 900) * env_exp(t, 0.002, 0.02)
    return norm(n + 0.6 * norm(body))


def boom(dur=2.4, f_hi=110, f_lo=38, fall=0.09, decay=0.55):
    t = tt(dur)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / fall)
    ph = TAU * np.cumsum(f) / SR
    return sat(np.sin(ph) * env_exp(t, 0.002, decay), 2.5)


def sub_drop(dur=2.2, f0=62, f1=27):
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.5)
    return np.sin(TAU * np.cumsum(f) / SR) * env_exp(t, 0.01, 0.9)


def metal(rng, dur=2.5, base=180.0, bright=1.0, decay=1.6):
    """Modal sentez: çelik levha/kasa çınlaması (inharmonik kısmi tonlar)."""
    t = tt(dur)
    ratios = np.array([1.0, 2.32, 4.25, 6.63, 9.38, 12.6, 16.1, 20.3, 25.0])
    x = np.zeros(len(t))
    for i, r in enumerate(ratios):
        f = base * r * rng.uniform(0.985, 1.015)
        if f > 15000:
            break
        a = (0.9 ** i) * (bright ** i) * rng.uniform(0.6, 1.0)
        d = decay / (1 + 0.45 * i)
        x += a * np.sin(TAU * f * t + rng.uniform(0, TAU)) * np.exp(-t / d) * (1 + 0.05 * np.sin(TAU * rng.uniform(2, 6) * t))
    exc = bp(rng.standard_normal(len(t)), 800, 7000) * np.exp(-t / 0.004)
    return norm(x * (1 - np.exp(-t / 0.0007)) + 0.3 * exc)


def rubble(rng, dur=2.0):
    t = tt(dur)
    return norm(lp(brown(len(t), rng), 220) * env_exp(t, 0.02, 0.6))


def impact(mx, t0, rng, size=1.0, metal_base=150.0, pan=0.0, metal_amt=1.0):
    """Trailer darbesi: geçiş + gövde + sub + metal + gürleme; ayrı yankı göndermeleri."""
    mx.add(transient(rng), t0, 0.5 * size, pan, room=0.3, hall=0.4, width=0.5)
    mx.add(boom(f_hi=105 * rng.uniform(0.95, 1.05)), t0, 0.85 * size, 0.0, hall=0.35)
    mx.add(sub_drop(), t0, 0.55 * size, 0.0)
    if metal_amt > 0:  # koyu, kısa çınlama (uzun süren yüksek "bip" tonu yok)
        m = metal(rng, 1.2, metal_base, 0.75, 0.6)
        mx.add(lp(m, 2800), t0, 0.12 * size * metal_amt, pan - 0.25, hall=0.9, width=0.6)
        m2 = metal(rng, 1.0, metal_base * 1.37, 0.75, 0.4)
        mx.add(lp(m2, 2400), t0 + 0.004, 0.07 * size * metal_amt, pan + 0.3, hall=0.9)
    mx.add(rubble(rng), t0 + 0.01, 0.3 * size, 0.0, hall=0.5, width=0.8)


def reverse_swell(mx, t_hit, rng, ir, dur=0.9, gain=0.35):
    """Ters yankı kabarması: gürültü patlaması yankıdan geçirilip ters çevrilir, vuruşta biter."""
    t = tt(0.25)
    src = bp(rng.standard_normal(len(t)), 300, 9000) * np.exp(-t / 0.05)
    wet = np.stack([signal.fftconvolve(src, ir[:, c]) for c in range(2)], -1)
    on = int(np.argmax(np.abs(wet).max(1) > 0.2 * np.abs(wet).max()))  # yankının ön gecikmesi atlanır:
    m = int(dur * SR)                                                   # ters kabarma vuruşa kadar dolu
    wet = wet[on:on + m]
    sw = wet[::-1] * np.linspace(0, 1, len(wet))[:, None] ** 1.5
    mx.add(norm(sw), t_hit - len(sw) / SR, gain, fo=0.002)


def whoosh(rng, dur, f0, f1, f_peak=None, width=0.55, curve=None):
    t = tt(dur)
    n = pink(len(t), rng) + 0.3 * rng.standard_normal(len(t))
    k = 64
    u = np.linspace(0, 1, k)
    fp = f_peak or np.sqrt(f0 * f1)
    centers = np.where(u < 0.6, f0 * (fp / f0) ** (u / 0.6), fp * (f1 / fp) ** ((u - 0.6) / 0.4))
    g = curve if curve is not None else np.sin(np.pi * u ** 0.8) ** 2
    return norm(stft_sweep(n, centers, width, g))


def braam(rng, dur=2.2, f=36.7, bright=1.0):
    """Alçak pirinç benzeri 'braam': dedüne testere yığını, açılıp kapanan filtre, satürasyon."""
    t = tt(dur)
    fc = 150 + (1300 * bright) * np.clip(t / 0.25, 0, 1) * np.exp(-np.maximum(t - 0.3, 0) / 0.9)
    x = np.zeros(len(t))
    for ratio, amp in ((1, 1.0), (2, 0.8), (1.5, 0.45), (4, 0.25)):
        for det in (-0.12, 0.0, 0.11):
            f0 = f * ratio * (1 + det * 0.01)
            ph0 = rng.uniform(0, TAU)
            for k in range(1, 48):
                fk = f0 * k
                if fk > 9000:
                    break
                resp = 1 / np.sqrt(1 + (fk / fc) ** 4)
                x += amp * resp / k * np.sin(TAU * fk * t + k * ph0)
    e = np.clip(t / 0.06, 0, 1) * np.exp(-np.maximum(t - 0.4, 0) / 0.7)
    return norm(sat(norm(x) * e * 1.6, 2.2))


def diesel(rng, dur, rpm, cyl=6, load=0.8):
    """Dizel motor kaynağı: ateşleme darbeleri + egzoz rezonansı + tıkırtı + turbo."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rpm_t = rpm * (1 + 0.012 * np.sin(TAU * 0.7 * t + rng.uniform(0, 6)) + 0.006 * rng.standard_normal(n).cumsum() / np.sqrt(n))
    cycles = np.cumsum(rpm_t / 60 / 2) / SR * cyl  # 4 zamanlı: 2 turda her silindir bir kez
    idx = np.nonzero(np.diff(np.floor(cycles)) > 0)[0]
    imbalance = 1 + 0.18 * rng.standard_normal(cyl)
    pulses = np.zeros(n)
    knocks = np.zeros(n)
    for k, i in enumerate(idx):
        j = i + int(rng.normal(0, 0.00018) * SR)
        if 0 <= j < n:
            a = imbalance[k % cyl] * (1 + 0.08 * rng.standard_normal())
            pulses[j] += a
            knocks[j] += a * rng.uniform(0.6, 1.0)
    pt = tt(0.012)
    shape = (1 - np.exp(-pt / 0.0007)) * np.exp(-pt / 0.0035)
    gas = signal.fftconvolve(pulses, shape)[:n]
    # egzoz borusu (tarak, ~2.9 m) + susturucu + formantlar
    d = int(2 * 2.9 / C_SOUND * SR)
    ex = signal.lfilter([1.0], np.r_[1.0, np.zeros(d - 1), -0.55], gas)
    ex = lp(ex, 1700)
    body = peak_eq(peak_eq(peak_eq(peak_eq(ex, 95, 5, 1.2), 230, 4, 1.5), 520, 5, 1.6), 1100, 4, 1.4)
    rumble = lp(brown(n, rng), 120) * (0.6 + 0.4 * lp(gas, 30) / (np.max(np.abs(gas)) + 1e-9))
    clatter = bp(signal.fftconvolve(knocks, rng.standard_normal(int(0.002 * SR)) * np.exp(-tt(0.002) / 0.0006))[:n],
                 1800, 7000)
    turbo = bp(rng.standard_normal(n), 2900, 3400, 2) * (0.5 + 0.5 * np.sin(TAU * 0.3 * t))  # dar bant ıslık
    intake = bp(rng.standard_normal(n), 900, 2600)
    mix = (norm(body) * 1.0 + norm(rumble) * 0.45 * load + norm(clatter) * 0.4 + norm(turbo) * 0.04
           + norm(intake) * 0.07)
    return sat(norm(mix) * 1.2, 1.6)


def tires_gravel(rng, dur, speed=14.0):
    """Lastik yuvarlanma gürültüsü (~800 Hz tepe) + çakıl çatırtısı (Poisson taneleri) + yol gümbürtüsü."""
    n = int(dur * SR)
    roll = peak_eq(bp(pink(n, rng), 250, 3500), 850, 6, 0.9)
    rate = 900 * speed / 14
    imp = np.zeros(n)
    k = rng.poisson(rate * dur)
    imp[rng.integers(0, n, k)] = rng.uniform(0.2, 1.0, k) * rng.choice([-1, 1], k)
    crunch = bp(imp, 1200, 6500) + 0.6 * bp(imp, 500, 1500)
    thump = lp(brown(n, rng), 80)
    return norm(norm(roll) * 0.7 + norm(crunch) * 0.55 + norm(thump) * 0.5)


def rattles(rng, dur, count=7):
    """Ekipman/süspansiyon tıngırtıları: kısa metal darbeler ve alçak tok sesler."""
    n = int(dur * SR)
    x = np.zeros(n)
    for _ in range(count):
        i = int(rng.uniform(0.15, 0.85) * n)
        m = metal(rng, 0.25, rng.uniform(400, 1400), 0.8, 0.07) * rng.uniform(0.3, 0.8)
        x[i:i + len(m)] += m[: n - i]
        th = boom(0.2, 140, 70, 0.02, 0.05) * rng.uniform(0.3, 0.7)
        j = int(rng.uniform(0.1, 0.9) * n)
        x[j:j + len(th)] += th[: n - j]
    return x


def pass_by(src, t_mid, x_mid, speed, y, z, t_start, listener=LISTENER, right=RIGHT):
    """Hareketli kaynağı dinleyiciye taşır: Doppler (değişken gecikme), 1/r, hava soğurması,
    yerden yansıma ve kulaklar arası zaman/seviye farkıyla stereo. right: kameranın sağ yönü
    (yatay birim vektör); sol-sağ konum kaynağın bu yöndeki bileşeninden gelir."""
    n = len(src)
    t = t_start + np.arange(n) / SR
    right = np.asarray(right, float)[:2] / np.linalg.norm(np.asarray(right, float)[:2])

    def path(z_src):
        x = x_mid + speed * (t - t_mid)
        d = np.stack([x - listener[0], np.full(n, y - listener[1]), np.full(n, z_src - listener[2])], -1)
        return d, np.linalg.norm(d, axis=1)

    out = np.zeros((n, 2))
    idx = np.arange(n)
    dry_lp = lp(src, 2200, 2)
    for z_src, refl in ((z, 1.0), (-z, 0.45)):  # direkt + yerden yansıma (zemine göre görüntü kaynak)
        d, r = path(z_src)
        az = np.clip((d[:, 0] * right[0] + d[:, 1] * right[1]) / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6),
                     -1, 1)  # sağ-sol
        g = refl * 5.0 / np.maximum(r, 2.0)
        air = np.clip((r - 6) / 40, 0, 1)  # uzakta tizler kaybolur
        for ch, side in ((0, -1), (1, 1)):
            itd = 0.00033 * az * side  # yakın kulağa erken varış
            delay = r / C_SOUND - itd
            pos = idx - delay * SR
            s = (1 - air) * np.interp(pos, idx, src) + air * np.interp(pos, idx, dry_lp)
            ild = 0.5 + 0.5 * side * az * 0.85
            out[:, ch] += s * g * np.sqrt(np.clip(ild, 0.05, 1))
    return out


def wind(rng, dur, gust_rate=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    gust = 0.55 + 0.45 * lp(rng.standard_normal(n), gust_rate * 4) * 40
    gust = np.clip(gust, 0.15, 1.3)
    low = lp(pink(n, rng), 450)
    whistle = stft_sweep(rng.standard_normal(n), 700 + 500 * np.interp(np.linspace(0, 1, 32), np.linspace(0, 1, n),
                                                                      gust), 0.35)
    l = norm(low * gust + 0.15 * whistle)
    r = norm(lp(pink(n, rng), 450) * gust[::-1] + 0.15 * whistle[::-1])
    return np.stack([l, r], -1) * np.clip(t / 0.3, 0, 1)[:, None]


def drone(rng, dur):
    """Gerilim yatağı (saf sinüs yok): D1-A1 kümesinde dedüne bant sınırlı testereler, yavaşça
    açılıp kapanan alçak geçiren süzgeç, süzülmüş pembe gürültü nefesi, altta ince sub katmanı."""
    t = tt(dur)
    x = np.zeros(len(t))
    for f, amp in ((36.7, 1.0), (36.92, 0.9), (55.0, 0.55), (55.3, 0.45), (73.4, 0.25)):
        ph0 = rng.uniform(0, TAU)
        for k in range(1, int(900 / f)):
            x += amp / k * np.sin(TAU * f * k * t + k * ph0)
    cut = 170 + 90 * (0.5 - 0.5 * np.cos(TAU * t / 5.3))
    # zamanla değişen süzgeç: kısa bloklarda kesim frekansı güncellenir (yumuşak geçişli)
    y = np.zeros_like(x)
    blk = int(0.05 * SR)
    win = np.hanning(2 * blk)
    for i in range(0, len(x) - blk, blk):
        seg = x[max(i - blk // 2, 0):i + 2 * blk - blk // 2]
        f_seg = lp(seg, cut[min(i + blk, len(cut) - 1)], 4)
        a = max(i - blk // 2, 0)
        w = win[:len(f_seg)]
        y[a:a + len(f_seg)] += f_seg * w
    breath = bp(pink(len(t), rng), 70, 420) * (0.6 + 0.4 * np.sin(TAU * t / 3.7 + 1.0))
    sub = np.sin(TAU * 36.7 * t) * 0.25
    return norm(norm(y) + 0.35 * norm(breath) + sub)


def room_tone(rng, dur):
    """Depo oda tonu: bina gövdesinin alçak gürlemesi, havalandırma hışırtısı (süzülmüş gürültü)."""
    n = int(dur * SR)
    rumble = lp(brown(n, rng), 130, 4)
    vent = peak_eq(bp(pink(n, rng), 160, 1800), 420, 4, 1.4)
    flutter = 0.85 + 0.15 * lp(rng.standard_normal(n), 3) * 60
    return norm(norm(rumble) * 0.9 + norm(vent) * 0.35 * np.clip(flutter, 0.6, 1.2))


def mains_buzz(rng, dur, f=50.0, hiss=0.25):
    """Lamba balastı / trafo vızıltısı: şebekenin iki katında sönümlü darbe dizisi (zengin
    harmonikler, saf sinüs değil), rezonanslı bant süzgeci, tepe anlarında ark hışırtısı."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = (2 * f * t + 0.03 * np.cumsum(rng.standard_normal(n)) / SR) % 1.0
    pulse = np.exp(-ph / 0.07)
    x = bp(pulse - pulse.mean(), 90, 2400)
    x = peak_eq(peak_eq(x, 2 * f, 5, 2.0), 6 * f, 3, 2.0)
    arc = bp(rng.standard_normal(n), 2500, 7000) * (pulse > 0.75)
    flick = 1 - 0.25 * (lp(rng.standard_normal(n), 6) * 30 > 0.9)
    return norm((norm(x) + hiss * norm(arc)) * flick)


def sub_pulse(rng, dur=1.2, f0=70.0, f1=38.0, decay=0.32):
    """Sub-bass vuruşu: perdesi düşen gövde + alçak geçirilmiş gürültü tokluğu, hafif doygun."""
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.06)
    body = np.sin(TAU * np.cumsum(f) / SR) * env_exp(t, 0.004, decay)
    thud = lp(rng.standard_normal(len(t)), 180, 4) * env_exp(t, 0.003, 0.05)
    return norm(lp(sat(body + 0.5 * norm(thud), 1.8), 220))


def klaxon(rng, dur, period=1.15, on=0.9, f_lo=360.0, f_hi=780.0, phase=0.35):
    """Tesis alarmı ("whoop" kornası): her periyotta yükselen perde; kare dalgaya yakın harmonikler,
    korna rezonansları (tepe EQ), doygunluk. Mesafe ve yankı çağıran tarafta eklenir."""
    t = tt(dur)
    u = ((t / period) + phase) % 1.0
    f = f_lo + (f_hi - f_lo) * np.clip(u / on, 0, 1) ** 0.6
    ph = TAU * np.cumsum(f) / SR
    x = sum(np.sin(k * ph) / k * (1.0 if k % 2 else 0.3) for k in range(1, 14))
    gate = lp((u < on).astype(float), 40, 2)
    horn = sat(norm(x) * gate * 1.4, 2.4)
    horn = peak_eq(peak_eq(bp(horn, 280, 4200), 1150, 5, 1.3), 2400, 3, 1.5)
    wobble = 1 + 0.04 * np.sin(TAU * 5.5 * t)
    return norm(horn * wobble)


# ---------------------------------------------------------------- sahne

def synthesize(ev, seed=13):
    """meta.json olaylarından 12 sn'lik stereo miks (48 kHz, float32)."""
    rng = np.random.default_rng(seed)
    end = ev["end"]
    c1, c2, c3 = ev["cuts"]          # 3.6 sert kesme, 6.8 karartma, 9.2 logo
    t_open = 0.4                     # siyahtan açılışın tamamlandığı an
    dur = end + 0.5
    mx = Mix(dur)
    ir_hall = make_ir(rng, 4.0, 3.2, 1.3, 0.03, early=((0.09, 0.4), (0.17, 0.3), (0.29, 0.2)))
    ir_room = make_ir(rng, 1.6, 1.2, 0.5, 0.012, early=((0.035, 0.5), (0.061, 0.35), (0.11, 0.25)))
    ir_shed = make_ir(rng, 1.4, 1.1, 0.45, 0.008, early=((0.021, 0.5), (0.034, 0.4), (0.052, 0.3)))
    ir_yard = make_ir(rng, 3.0, 2.4, 0.9, 0.06, early=((0.12, 0.5), (0.21, 0.35), (0.33, 0.25)))
    hits = (t_open, c1, c2, c3)

    # Ducking: her vuruşta yatak ~6 dB çekilip yavaşça geri gelir (vuruşlar temiz vursun)
    tl = np.arange(int(dur * SR)) / SR
    duck = np.ones_like(tl)
    for c in hits:
        d = np.clip((tl - c) / 0.012, 0, 1) * np.exp(-np.maximum(tl - c, 0) / 0.6)
        duck *= 1 - 0.5 * d

    def ducked(sig, t0):
        i0 = int(round(t0 * SR))
        g = duck[max(i0, 0):max(i0, 0) + len(sig)]
        g = np.pad(g, (0, len(sig) - len(g)), constant_values=1.0)
        return sig * (g[:, None] if np.ndim(sig) == 2 else g)

    # --- gerilim yatağı: tüm video boyunca, logoda söner (müzik katmanı; sahne sesi değil)
    dr = drone(rng, 11.6)
    e = np.clip(tt(11.6) / 0.35, 0, 1) * np.clip((10.9 - tt(11.6)) / 1.6, 0, 1) ** 1.5
    mx.add(ducked(hp(dr, 28) * e, 0.0), 0.0, 0.16, width=0.6, hall=0.15)

    # --- DEPO (0 - 3.6): oda tonu, lamba balastı, kapıdan rüzgâr, sub-bass vuruşları
    mx.add_scene(ducked(room_tone(rng, c1), 0.0), 0.0, c1, 0.085, width=0.7, ir=ir_shed, wet=0.3)
    bz = mains_buzz(rng, c1, 50, 0.2)
    mx.add_scene(bz, 0.0, c1, 0.018, 0.25, ir=ir_shed, wet=0.5)
    w = wind(rng, c1)
    mx.add_scene(lp(w, 900), 0.0, c1, 0.05, ir=ir_shed, wet=0.4)
    for tp, g in ((1.55, 0.32), (2.55, 0.36)):
        mx.add(sub_pulse(rng), tp, g, hall=0.1, t_end=c1)

    # --- YOL (3.6 - 6.8): iki zırhlı araç (motor + lastik + tıngırtı), Doppler'li geçiş, rüzgâr
    lst = np.array(ev.get("listener", LISTENER), float)
    right = np.array(ev.get("listener_right", RIGHT), float)
    speed = ev.get("apc_speed", VEH_SPEED)
    wr = wind(rng, c2 - c1)
    mx.add_scene(ducked(wr, c1), c1, c2, 0.075, ir=ir_room, wet=0.2)
    for i, t_mid in enumerate(ev["apc_pass"]):
        n_dur = c2 - c1
        eng = diesel(rng, n_dur, 1500 + 160 * i)
        tyr = tires_gravel(rng, n_dur, speed)
        rat = rattles(rng, n_dur, 5)
        src = eng * 0.9 + tyr * 0.5 + rat * 0.3
        lane_y = ev.get("apc_lanes", [VEH_Y, VEH_Y])[i]
        st = pass_by(src, t_mid, 0.0, speed, lane_y, 1.1, c1, listener=lst, right=right)
        mx.add_scene(st, c1, c2, 0.62, ir=ir_room, wet=0.25)
        # geçişin dibinde hava kütlesi: kısa, alçak whoosh, sağa doğru
        ws = whoosh(rng, 0.7, 150, 600, 400, 0.6)
        mx.add(stereo(ws, np.linspace(0.1, 0.95, len(ws))), t_mid - 0.4, 0.22, room=0.1, t_end=c2)

    # --- TESİS (6.8 - 9.2): uzak alarm kornası, trafo vızıltısı, rüzgâr
    al = klaxon(rng, c3 - c2 + 0.2)
    al = lp(al, 2600)
    mx.add_scene(ducked(stereo(al, -0.25, 0.6), c2), c2, c3, 0.11, ir=ir_yard, wet=1.6)
    mx.add_scene(mains_buzz(rng, c3 - c2, 60, 0.1), c2, c3, 0.02, 0.15, ir=ir_yard, wet=0.3)
    mx.add_scene(ducked(wind(rng, c3 - c2), c2), c2, c3, 0.06, ir=ir_yard, wet=0.2)
    for tp, g in ((8.15, 0.24), (8.55, 0.3), (8.8, 0.34), (8.98, 0.38)):  # logoya doğru hızlanan nabız
        mx.add(sub_pulse(rng, 0.6, 75, 40, 0.18), tp, g, t_end=c3)

    # --- yazı aksanları: kelime belirirken yumuşak, alçak "fısıltı" (kelime başına aynı)
    for tw in ev.get("words", (0.9, 4.0, 7.0)):
        sw = whoosh(rng, 0.5, 2600, 700, 1500, 0.5, np.sin(np.pi * np.linspace(0, 1, 64) ** 0.6) ** 2)
        mx.add(sw, tw - 0.05, 0.05, 0.0, room=0.3, width=0.7)

    # --- vuruşlar: açılış, iki kesme, logo (en büyük); öncesinde ters yankı kabarması
    swell = {t_open: (0.38, 0.22), c1: (0.85, 0.3), c2: (0.85, 0.3), c3: (0.95, 0.38)}
    for c, size, mb, ma in ((t_open, 0.75, 120, 0.0), (c1, 0.95, 115, 0.8), (c2, 0.92, 105, 0.8), (c3, 1.35, 95, 1.0)):
        d_sw, g_sw = swell[c]
        reverse_swell(mx, c, rng, ir_hall, d_sw, g_sw)
        impact(mx, c, rng, size, mb, metal_amt=ma)
    mx.add(braam(rng, 2.0, 36.7, 0.9), c1, 0.3, hall=0.35, width=0.5)
    mx.add(braam(rng, 1.8, 41.2, 0.8), c2, 0.24, hall=0.4, width=0.5)
    mx.add(braam(rng, 2.6, 36.7, 1.1), c3, 0.42, hall=0.55, width=0.5)
    mx.add(sub_drop(2.8, 58, 24), c3, 0.45)
    ws = whoosh(rng, 0.9, 150, 4000, 2500, 0.6, np.linspace(0, 1, 64) ** 2.2)  # logoya emme
    mx.add(ws, c3 - 0.9, 0.2, room=0.2, width=0.6)

    # --- yankılar, ses eşitleme, mastering
    wet = convolve(mx.room, ir_room) * 0.45 + convolve(mx.hall, ir_hall) * 0.6
    mixd = mx.dry + wet
    mixd = hp(mixd, 22, 2)                       # DC/infra
    mixd = peak_eq(mixd, 250, -2.0, 0.8)         # çamur temizliği
    mixd = peak_eq(mixd, 3500, 1.5, 0.9)         # netlik
    mixd = mixd + 0.1 * hp(mixd, 7000, 2)        # hava (yüksek raf)
    mixd = norm(mixd) * 0.5
    mixd = compress(mixd, -20, 2.2, 0.015, 0.22, makeup_db=0.0)
    mixd = sat(mixd, 1.05)
    n = int(end * SR)
    mixd = mixd[:n]
    fo = int(0.5 * SR)                            # son 0.5 sn: yumuşak kararma (aniden kesilmez)
    g = np.ones(n)
    g[n - fo:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(1, fo + 1) / fo)
    mixd = declick(mixd * g[:, None], DECLICK_IN, 0.0)
    out = master(mixd)
    return out.astype(np.float32)


def report(x):
    """Ölçüm özeti: bütünleşik yükseklik, true peak, son 0.5 sn ve tail seviyeleri."""
    seg = lambda a, b: 20 * np.log10(np.sqrt(np.mean(x[int(a * SR):int(b * SR)] ** 2)) + 1e-12)
    return {"lufs": round(lufs(x), 2), "true_peak_dbtp": round(true_peak_db(x), 2),
            "rms_9.2-10.0": round(seg(9.2, 10.0), 1), "rms_10.7-11.5": round(seg(10.7, 11.5), 1),
            "rms_11.9-12.0": round(seg(11.9, 12.0), 1), "last_sample": float(np.abs(x[-1]).max())}


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from sound import write_wav
    meta = json.loads(Path(sys.argv[1]).read_text())
    audio = synthesize(meta)
    write_wav(sys.argv[2], audio)
    print("yazıldı", sys.argv[2], audio.shape, report(audio))
