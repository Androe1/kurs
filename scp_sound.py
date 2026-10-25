"""SCP sinematiği - ses tasarımı (numpy + scipy ile sentez; hazır ses/örnek kullanılmaz).

Bir SFX sanatçısının katmanlama mantığıyla, her ses fiziksel kaynağından modellenir:

  araç geçişi   dizel motor: 6 silindirin ateşleme sırasına göre yanma darbeleri (silindir
                dengesizliği + zamanlama titreşimi -> "gurlama"), egzoz borusu rezonansı (tarak
                filtre) ve formantlar, dizel tıkırtısı, turbo ıslığı; 8 lastikten yuvarlanma ve
                çakıl çatırtısı, süspansiyon/ekipman tıngırtıları. Kaynak bir yörüngede hareket
                eder: değişken gecikme hattıyla Doppler, 1/r zayıflama, uzaklıkla hava soğurması,
                yerden yansıma (görüntü kaynak), kulaklar arası zaman/seviye farkı
                (yaklaşım: TrafficSoundSim, EURASIP 2024; motor: darbe dizisi + rezonatör).
  darbe         trailer "hit" katmanları: geçiş anı (gürültü patlaması + tık), gövde (perdesi
                düşen sinüs, satürasyon), sub drop, modal metal çınlama, enkaz gürlemesi, uzun yankı
  geçiş         her kesmeden önce ters yankı kabarması + whoosh (STFT'de kayan bant), braam
  ortam         gece rüzgârı (esintili), lamba vızıltısı, tesis trafosu, uzak siren, telsiz,
                gerilim yatağı (yavaş vuruşan alçak küme + cam gibi yüksek ton)
  mastering     bus kompresörü, yumuşak satürasyon, ileri bakışlı limiter (-1 dBFS)

Zamanlar Blender'ın yazdığı meta.json'dan gelir (blender/scp_cinematic.py).
"""
import numpy as np
from scipy import ndimage, signal

SR = 48000
TAU = 2 * np.pi
C_SOUND = 343.0

# Sahneyle aynı geometri (blender/scp_cinematic.py, shot_contain): kamera (0,-10,0.9), araçlar
# y=-4.5'te 14 m/s ile soldan sağa geçer; araç merkezi x=0.6'dan geçerken apc_pass anıdır.
VEH_SPEED, VEH_Y, VEH_X_MID, LISTENER = 14.0, -4.5, 0.6, np.array([0.0, -10.0, 0.9])


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


class Mix:
    """Zamana yerleştirme + iki yankı göndermesi (orman: kısa/orta, büyük: uzun trailer yankısı)."""

    def __init__(self, dur):
        n = int(dur * SR)
        self.dry = np.zeros((n, 2))
        self.room = np.zeros((n, 2))
        self.hall = np.zeros((n, 2))

    def add(self, sig, t0, gain=1.0, pan=0.0, room=0.0, hall=0.0, width=0.0):
        sig = np.asarray(sig, float) * gain
        if sig.ndim == 1:
            sig = stereo(sig, pan, width)
        i0 = int(round(t0 * SR))
        a, b = max(i0, 0), min(i0 + len(sig), len(self.dry))
        if b <= a:
            return
        seg = sig[a - i0:b - i0]
        self.dry[a:b] += seg
        self.room[a:b] += seg * room
        self.hall[a:b] += seg * hall


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


# ---------------------------------------------------------------- ses kaynakları

def transient(rng, dur=0.06, lo=1800, hi=9000):
    t = tt(dur)
    n = bp(rng.standard_normal(len(t)), lo, hi) * np.exp(-t / 0.006)
    click = np.sin(TAU * 3200 * t) * np.exp(-t / 0.0015)
    return norm(n + 0.5 * click)


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


def impact(mx, t0, rng, size=1.0, metal_base=150.0, pan=0.0):
    """Trailer darbesi: geçiş + gövde + sub + metal + gürleme; ayrı yankı göndermeleri."""
    mx.add(transient(rng), t0, 0.5 * size, pan, room=0.3, hall=0.4, width=0.5)
    mx.add(boom(f_hi=105 * rng.uniform(0.95, 1.05)), t0, 0.85 * size, 0.0, hall=0.35)
    mx.add(sub_drop(), t0, 0.55 * size, 0.0)
    m = metal(rng, base=metal_base)
    mx.add(m, t0, 0.22 * size, pan - 0.25, hall=0.9, width=0.6)
    mx.add(metal(rng, base=metal_base * 1.37, decay=1.0), t0 + 0.004, 0.14 * size, pan + 0.3, hall=0.9)
    mx.add(rubble(rng), t0 + 0.01, 0.3 * size, 0.0, hall=0.5, width=0.8)


def reverse_swell(mx, t_hit, rng, ir, dur=0.9, gain=0.35):
    """Ters yankı kabarması: gürültü patlaması yankıdan geçirilip ters çevrilir, vuruşta biter."""
    t = tt(0.25)
    src = bp(rng.standard_normal(len(t)), 300, 9000) * np.exp(-t / 0.05)
    m = int(dur * SR)
    wet = np.stack([signal.fftconvolve(src, ir[:m, c])[:m] for c in range(2)], -1)
    sw = wet[::-1] * np.linspace(0, 1, len(wet))[:, None] ** 1.5
    mx.add(norm(sw), t_hit - dur, gain)


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
    turbo_f = 3100 * rpm_t / rpm
    turbo = np.sin(TAU * np.cumsum(turbo_f) / SR) * (0.5 + 0.5 * np.sin(TAU * 0.3 * t))
    intake = bp(rng.standard_normal(n), 900, 2600)
    mix = (norm(body) * 1.0 + norm(rumble) * 0.45 * load + norm(clatter) * 0.4 + turbo * 0.03 + norm(intake) * 0.07)
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


def pass_by(src, t_mid, x_mid, speed, y, z, t_start, listener=LISTENER):
    """Hareketli kaynağı dinleyiciye taşır: Doppler (değişken gecikme), 1/r, hava soğurması,
    yerden yansıma ve kulaklar arası zaman/seviye farkıyla stereo."""
    n = len(src)
    t = t_start + np.arange(n) / SR

    def path(z_src):
        x = x_mid + speed * (t - t_mid)
        d = np.stack([x - listener[0], np.full(n, y - listener[1]), np.full(n, z_src - listener[2])], -1)
        return d, np.linalg.norm(d, axis=1)

    out = np.zeros((n, 2))
    idx = np.arange(n)
    dry_lp = lp(src, 2200, 2)
    for z_src, refl in ((z, 1.0), (-z, 0.45)):  # direkt + yerden yansıma (zemine göre görüntü kaynak)
        d, r = path(z_src)
        az = np.clip(d[:, 0] / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6), -1, 1)  # sağ-sol
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


def hum(rng, dur, f=50.0, buzz=0.25):
    """Trafo/lamba vızıltısı: şebeke frekansının çift harmonikleri + kesik vızıltı."""
    t = tt(dur)
    x = sum(a * np.sin(TAU * f * k * t + rng.uniform(0, 6)) for k, a in ((2, 1.0), (4, 0.4), (6, 0.25), (8, 0.12)))
    saw = bp(np.sign(np.sin(TAU * 2 * f * t)), 300, 3000) * buzz
    flick = 1 - 0.3 * (lp(rng.standard_normal(len(t)), 8) * 30 > 0.9)
    return norm((x + saw) * flick)


def siren(rng, dur, f_lo=520, f_hi=760, period=2.4):
    t = tt(dur)
    f = f_lo + (f_hi - f_lo) * (0.5 - 0.5 * np.cos(TAU * t / period))
    ph = TAU * np.cumsum(f) / SR
    x = sum(np.sin(k * ph) / k for k in range(1, 7))
    return norm(lp(x, 1800))


def radio(rng, dur=0.6):
    """Telsiz: açılış tıkı, bant sınırlı parazit, kısa bip, kapanış 'kşş'."""
    t = tt(dur)
    n = len(t)
    noise = bp(rng.standard_normal(n), 400, 3200) * (0.4 + 0.6 * (lp(rng.standard_normal(n), 25) * 25 > 0))
    beep = np.sin(TAU * 1450 * t) * ((t > 0.05) & (t < 0.13))
    env = np.clip(t / 0.005, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    click = np.zeros(n)
    click[:60] = np.hanning(60)
    return norm(sat((noise * 0.6 + beep * 0.5) * env + click, 3.0))


def drone(rng, dur):
    """Gerilim yatağı: D1-A1-D2 kümesi yavaş vuruşlarla, üstte cam gibi yüksek ton."""
    t = tt(dur)
    low = sum(np.sin(TAU * f * t + rng.uniform(0, 6)) * a for f, a in
              ((36.7, 1.0), (36.95, 0.8), (55.0, 0.5), (73.4, 0.35), (110.2, 0.15)))
    air = bp(pink(len(t), rng), 120, 900) * 0.25
    glass = sum(np.sin(TAU * f * t + rng.uniform(0, 6)) * np.sin(TAU * r * t) ** 2 for f, r in
                ((1318.5, 0.11), (1975.5, 0.07), (2637.0, 0.05))) * 0.06
    return norm(low + air + glass)


# ---------------------------------------------------------------- sahne

def synthesize(ev, seed=13):
    rng = np.random.default_rng(seed)
    end = ev["end"]
    dur = end + 2.5
    mx = Mix(dur)
    c1, c2, c3 = ev["cuts"]
    ir_hall = make_ir(rng, 4.0, 3.2, 1.3, 0.03, early=((0.09, 0.4), (0.17, 0.3), (0.29, 0.2)))
    ir_room = make_ir(rng, 1.6, 1.2, 0.5, 0.012, early=((0.035, 0.5), (0.061, 0.35), (0.11, 0.25)))

    # Ducking: her darbede ortam/yatak ~6 dB çekilip yavaşça geri gelir (darbeler temiz vursun).
    tl = np.arange(int(dur * SR)) / SR
    duck = np.ones_like(tl)
    for c in (c1, c2, c3, end - 0.62):
        d = np.clip((tl - (c - 0.04)) / 0.04, 0, 1) * np.exp(-np.maximum(tl - c, 0) / 0.6)
        duck *= 1 - 0.5 * d

    def ducked(sig, t0):
        i0 = int(round(t0 * SR))
        g = duck[max(i0, 0):max(i0, 0) + len(sig)]
        g = np.pad(g, (0, len(sig) - len(g)), constant_values=1.0)
        return sig * (g[:, None] if np.ndim(sig) == 2 else g)

    # --- gerilim yatağı ve ortam
    dr = drone(rng, end - c1 + 1.5)
    e = np.clip(tt(len(dr) / SR) / 0.8, 0, 1) * np.clip((len(dr) / SR - tt(len(dr) / SR)) / 1.4, 0, 1)
    mx.add(ducked(hp(dr, 30) * e, c1 - 0.2), c1 - 0.2, 0.1, width=0.6, hall=0.2)
    w = wind(rng, end - c1 + 1.0)
    mx.add(ducked(w, c1 - 0.3), c1 - 0.3, 0.07, room=0.1)
    # SECURE: lamba vızıltısı ve uzak telsiz
    hm = hum(rng, c2 - c1 + 0.3, 50, 0.35)
    mx.add(ducked(hm * fades(len(hm), 0.1, 0.3), c1), c1, 0.025, 0.25, room=0.3)
    mx.add(radio(rng, 0.55), c1 + 1.15, 0.05, -0.55, room=0.6)
    # PROTECT: tesis trafosu, uzak siren
    mx.add(hum(rng, end - c3 + 1.0, 60, 0.15), c3 - 0.15, 0.03, 0.1, room=0.4)
    s = siren(rng, end - c3 + 1.5)
    mx.add(ducked(lp(s, 1100) * np.clip(tt(len(s) / SR) / 0.6, 0, 1), c3 - 0.1), c3 - 0.1, 0.05, -0.3, hall=1.0,
           width=0.5)

    # --- açılış: siyah ekranda emme, 1. darbe
    mx.add(whoosh(rng, 0.9, 120, 2500, 1800, 0.6, np.linspace(0, 1, 64) ** 2.5), c1 - 0.9, 0.35, room=0.2)
    reverse_swell(mx, c1, rng, ir_hall, 0.8, 0.28)
    impact(mx, c1, rng, 1.0, 140)

    # --- SECURE: kasa yığını önden kayar (sağdan sola), metal tıngırtılar, başlık parıltısı
    p0, p1 = ev["crate_pass"]
    wsh = whoosh(rng, 0.75, 200, 900, 1400, 0.5)
    mx.add(stereo(wsh, np.linspace(0.8, -0.8, len(wsh))), p0 + 0.02, 0.4, room=0.2)
    for dt_, base in ((0.18, 620), (0.41, 910), (0.66, 480)):
        mx.add(metal(rng, 0.6, base, 0.85, 0.25), p0 + dt_, 0.06, rng.uniform(-0.5, 0.5), room=0.5)
    mx.add(boom(0.5, 160, 90, 0.03, 0.12), p0 + 0.08, 0.18, 0.3, room=0.4)  # ahşap tok
    sh = whoosh(rng, 0.6, 3000, 9000, 7000, 0.4, np.linspace(1, 0, 64) ** 2)
    mx.add(sh, p1 - 0.05, 0.08, 0.0, hall=0.6, width=0.8)

    # --- geçiş 1 -> 2 (CONTAIN): ters kabarma + braam + darbe
    reverse_swell(mx, c2, rng, ir_hall, 0.9, 0.3)
    mx.add(braam(rng, 2.0, 36.7), c2, 0.32, hall=0.35, width=0.5)
    impact(mx, c2, rng, 0.95, 120)

    # --- araç konvoyu: motor + lastik + tıngırtı, Doppler'li geçiş (önceden duyulur: J-cut)
    for i, t_mid in enumerate(ev["apc_pass"]):
        t_start = c2 - 0.9
        n_dur = end - t_start
        eng = diesel(rng, n_dur, 1650 + 140 * i)
        tyr = tires_gravel(rng, n_dur)
        rat = rattles(rng, n_dur, 6)
        src = eng * 0.9 + tyr * 0.55 + rat * 0.35
        st = pass_by(src, t_mid, VEH_X_MID, VEH_SPEED, VEH_Y - 0.15 * i, 1.1, t_start)
        fade = np.clip((tt(n_dur) - 0.3) / 0.6, 0, 1) * np.clip((c3 + 0.6 - (t_start + tt(n_dur))) / 0.5, 0, 1)
        mx.add(st * fade[:, None], t_start, 0.75, room=0.25)
        # geçişin dibinde hava kütlesi: kısa, alçak whoosh
        ws = whoosh(rng, 0.7, 150, 600, 400, 0.6)
        mx.add(stereo(ws, np.linspace(-0.9, 0.9, len(ws))), t_mid - 0.35, 0.25, room=0.15)

    # --- geçiş 2 -> 3 (PROTECT)
    reverse_swell(mx, c3, rng, ir_hall, 0.9, 0.3)
    impact(mx, c3, rng, 0.9, 165)
    mx.add(braam(rng, 1.8, 41.2, 0.8), c3, 0.22, hall=0.4, width=0.5)

    # --- harflerin altından geçiş: yakın, hızlı, iki yana açılan whoosh
    x = ev["through_text"]
    for side in (-1, 1):
        ws = whoosh(rng, 0.8, 250, 5000, 3500, 0.45)
        mx.add(stereo(ws, np.linspace(0, 0.85 * side, len(ws))), x - 0.5, 0.3, room=0.15)
    # --- kapanış: büyük darbe + braam, kararmayla birlikte söner
    t_end = end - 0.62
    reverse_swell(mx, t_end, rng, ir_hall, 1.0, 0.35)
    impact(mx, t_end, rng, 1.25, 110)
    mx.add(braam(rng, 2.4, 36.7, 1.1), t_end, 0.38, hall=0.5, width=0.5)

    # --- yankılar, ses eşitleme, mastering
    wet = convolve(mx.room, ir_room) * 0.45 + convolve(mx.hall, ir_hall) * 0.6
    mixd = mx.dry + wet
    mixd = hp(mixd, 22, 2)                       # DC/infra
    mixd = peak_eq(mixd, 250, -2.0, 0.8)         # çamur temizliği
    mixd = peak_eq(mixd, 3500, 1.5, 0.9)         # netlik
    mixd = mixd + 0.12 * hp(mixd, 7000, 2)       # hava (yüksek raf)
    mixd = norm(mixd) * 0.9                       # tepe -1 dB civarı; aradaki sessizlik korunur
    mixd = compress(mixd, -14, 2.0, 0.02, 0.25, makeup_db=1.0)
    mixd = sat(mixd, 1.05)
    out = limit(mixd, -1.0)
    return out.astype(np.float32)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from sound import write_wav
    meta = json.loads(Path(sys.argv[1]).read_text())
    audio = synthesize(meta)
    write_wav(sys.argv[2], audio)
    print("yazıldı", sys.argv[2], audio.shape)
