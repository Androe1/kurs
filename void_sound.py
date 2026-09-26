"""Void Creations intro animasyonu - ses tasarımı.

Zemin referanstaki gibi vuruşsuz, sessizlikten kabaran koyu bir pad'dir; üzerine
ekrandaki her olayla aynı karede duyulan efektler gelir. Tüm sesler numpy ile
sentezlenir, hazır ses kullanılmaz. Zamanlar ve ekrandaki konumlar
void_scene.VoidScene.events()'ten gelir.

  ışık çizgileri gelir   -> geldiği yandan logoya doğru süzülen hava sesi
  bir kopya kapanır      -> camsı ince bir "tık"
  kopyalar birleşir      -> tonda (Si♭) yükselen gerilim
  logo yanıp söner       -> her flaşta kısa, cızırtılı bir elektrik çıtırtısı ve alçak vuruş
  logo dolar (2.2)       -> derin vuruş, çatırtı ve parıltı; bas tam güce çıkar
  harfler belirir        -> cepheyle soldan sağa giden hışırtı, her harfe ince bir nota
  silme (3.47)           -> soldan sağa hızlı hava sesi; akor Sol minöre döner, ses söner

Akorlar tamamen uyumludur: Si♭(add9) -> Sol minör(add9). Bas temiz bir alt sinüstür
(testere dişinin üst harmonikleri pad'deki notalarla yarım ton sürtüşmesin diye);
notalar, tıklar ve parıltılar da aynı tondadır (Si♭ majör pentatonik).
"""
import numpy as np

from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span, sweep_band

CHORD_1 = (174.61, 233.08, 293.66, 349.23, 523.25, 587.33)   # Fa3 Si♭3 Re4 Fa4 Do5 Re5 = Si♭(add9)
CHORD_2 = (196.00, 233.08, 293.66, 392.00, 440.00, 587.33)   # Sol3 Si♭3 Re4 Sol4 La4 Re5 = Solm(add9)
VOICE_DB = (-5, -3, -2, -4, -8, -7)                          # seslerin seviyeleri (iki akorda aynı sırada)
BASS = (58.27, 49.00)                                        # Si♭1 -> Sol1
# Si♭ majör pentatonik (Si♭ Do Re Fa Sol): harf başına bir nota, tıklar ve parıltılar
BELLS = (932.33, 1046.50, 1174.66, 1396.91, 1567.98, 1864.66, 2093.00, 2349.32, 2793.83, 3135.96,
         3729.31, 4186.01)
TICKS = (1396.91, 1864.66, 2093.00, 2349.32)

# Pad'in kabarması (saniye, dB): referanstaki müziğin seviye eğrisi
PAD_LEVEL = ((0.0, -70), (0.2, -45), (0.4, -33), (0.6, -24), (0.8, -18), (1.0, -15), (1.2, -12.5),
             (1.4, -10.5), (1.6, -8), (1.8, -5.5), (2.0, -3.5), (2.2, -2.5), (2.6, -1), (3.4, 0), (4.4, 0))
PAD_CUTOFF = ((0.0, 700), (0.4, 1100), (1.2, 2000), (2.2, 2800), (4.4, 2800))   # Hz


# ---------------------------------------------------------------- yardımcılar

def db(x):
    return 10 ** (np.asarray(x, float) / 20)


def envelope(t, table, smooth=0.03):
    """dB tablosundan genlik eğrisi; köşeler kısa bir ortalama ile yumuşatılır."""
    ts, vs = np.array(table, float).T
    env = db(np.interp(t, ts, vs))
    k = int(smooth * SR) | 1
    padded = np.concatenate([np.full(k // 2, env[0]), env, np.full(k // 2, env[-1])])
    return np.convolve(padded, np.ones(k) / k, mode="valid")


def panned(left, right, pan):
    """İki kanalı (ya da aynı sinyali) sabit güçte, zamanla değişebilen konuma yerleştirir."""
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([left * np.cos(p), right * np.sin(p)], -1)


def air(n, fc, q, rng):
    """İki kanallı (ilintisiz) band geçiren gürültü; merkez frekansı zamanla değişir."""
    return [sweep_band(rng.standard_normal(n), fc, q) for _ in range(2)]


def ducking(t, hits, depth, attack=0.004, release=0.12):
    """Vuruş anlarında kısılma kazancı: hits = [(başlangıç, süre)], her vuruşta depth kadar iner."""
    g = np.ones(len(t))
    for t0, hold in hits:
        x = t - t0
        shape = np.where(x < 0, 0.0, np.where(x < attack, x / attack,
                         np.where(x < attack + hold, 1.0, np.exp(-(x - attack - hold) / release))))
        g *= 1 - depth * shape
    return g


# ---------------------------------------------------------------- müzik yatağı

def saw_voice(t, f0, fc, rng, top=6000.0):
    """Yumuşak testere dişi (toplamalı): harmonikler 24 dB/oktav alçak geçirenden geçer."""
    out = np.zeros(len(t))
    for h in range(1, int(top / f0) + 1):
        gain = 1 / np.sqrt(1 + (f0 * h / fc) ** 8)
        out += gain / h * np.sin(TAU * f0 * h * t + rng.uniform(0, TAU))
    return out


def pad(t, change, rng):
    """Si♭(add9) -> Solm(add9): her nota üç hafif akort kaymış testere + sinüs gövdesi."""
    ts, fs = np.array(PAD_CUTOFF, float).T
    fc = np.exp(np.interp(t, ts, np.log(fs)))
    x = 0.5 - 0.5 * np.cos(np.pi * np.clip((t - change + 0.06) / 0.14, 0, 1))   # 0 -> 1 akor geçişi
    out = np.zeros((len(t), 2))
    for chord, weight in ((CHORD_1, 1 - x), (CHORD_2, x)):
        for f, level in zip(chord, VOICE_DB):
            for cents, pan_ in ((-6, -0.6), (0, 0.0), (6, 0.6)):
                v = saw_voice(t, f * 2 ** (cents / 1200), fc, rng) + 0.6 * np.sin(TAU * f * t + rng.uniform(0, TAU))
                out += db(level) * weight[:, None] * panned(v, v, pan_)
    return out / np.abs(out).max()


def bass(t, change):
    """Temiz alt bas: sinüs + oktavı + hafif doyurma (tek harmonikler akorun beşlisi ve üçlüsü)."""
    out = np.zeros(len(t))
    for f0, gate in ((BASS[0], np.clip((change + 0.03 - t) / 0.06, 0, 1)),
                     (BASS[1], np.clip((t - change) / 0.04, 0, 1))):
        out += (np.sin(TAU * f0 * t) + 0.3 * np.sin(TAU * 2 * f0 * t)) * gate
    out = np.tanh(1.4 * out) / np.tanh(1.4)
    return np.stack([out, out], -1)


# ---------------------------------------------------------------- efektler

def swish(mx, t0, arrive, pan0, rng, gain):
    """Işık çizgisi: geldiği yandan logoya doğru süzülen hava sesi; zirvesi logoya değdiği an."""
    rise = max(arrive - t0, 0.03)
    t = span(rise + 0.22)
    u = np.clip(t / rise, 0, 1)
    env = np.where(t < rise, u ** 2.2, np.exp(-(t - rise) / 0.06)) * np.clip((t[-1] - t) / 0.01, 0, 1)
    left, right = air(len(t), 900 * 4.5 ** u, 1.3, rng)
    sig = panned(left, right, 0.85 * pan0 * (1 - u))
    mx.add(sig / np.abs(sig).max() * env[:, None], t0, gain=gain, reverb=0.2)


def tick(mx, t0, f, pan, gain):
    """Bir kopyanın konturu kapandığında: camsı ince tık."""
    t = span(0.15)
    s = np.sin(TAU * f * t) * np.exp(-t / 0.02) + 0.35 * np.sin(TAU * 2.76 * f * t) * np.exp(-t / 0.007)
    mx.add(s * (1 - np.exp(-t / 0.0006)), t0, gain=gain, pan=pan, reverb=0.35)


def riser(mx, t0, t1, flashes, rng, gain):
    """Kopyalar birleşirken: tizleşen hava ve Si♭2'den Si♭4'e çıkan ton; logo dolarken kesilir.
    Logo her yanıp söndüğünde riser da kesilir: ses, flaşlarla aynı ritimde titrer."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = u ** 2.4 * np.clip((dur - t) / 0.004, 0, 1)
    env *= ducking(t0 + t, [(a, b - a) for a, b in flashes], 0.75, release=0.03)
    left, right = air(len(t), 350 * 18 ** (u ** 1.2), 1.6, rng)
    noise = panned(left, right, np.zeros(len(t)))
    mx.add(noise / np.abs(noise).max() * env[:, None], t0, gain=gain, reverb=0.2)
    ph = glide(116.54 * 4 ** (u ** 1.5))
    tone = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)) * env
    mx.add(peak(tone), t0, gain=0.45 * gain, reverb=0.25)


def zap(mx, t0, t1, strength, rng):
    """Logo yanıp söndüğünde: flaş süresince cızırtılı elektrik çıtırtısı ve alçak vuruş."""
    d = t1 - t0
    t = span(d + 0.15)
    gate = np.clip(t / 0.002, 0, 1) * np.clip((d + 0.012 - t) / 0.012, 0, 1)
    crackle = band(rng.standard_normal(len(t)), lo=2500, hi=11000)
    flutter = np.repeat(rng.uniform(0.2, 1.0, len(t) // 24 + 1), 24)[:len(t)]   # düzensiz titreşim
    buzz = np.sign(np.sin(TAU * 116.54 * t)) * 0.5 + np.sign(np.sin(TAU * 233.08 * t)) * 0.25
    buzz = band(buzz, hi=3000)
    thump = np.sin(glide(55 + 45 * np.exp(-t / 0.02))) * np.exp(-t / 0.07) * (1 - np.exp(-t / 0.001))
    s = 0.6 * peak(crackle) * flutter * gate + 0.3 * peak(buzz) * gate + 0.7 * thump
    mx.add(s, t0, gain=0.6 * strength, reverb=0.25)


def impact(mx, t0, rng):
    """Logo dolup yerine oturduğunda: derin vuruş, gövde, çatırtı ve tonda parıltı."""
    t = span(1.8)
    boom = np.tanh(2.0 * np.sin(glide(38 + 90 * np.exp(-t / 0.05))) * np.exp(-t / 0.5)) / np.tanh(2.0)
    boom *= 1 - np.exp(-t / 0.0015)
    noise = rng.standard_normal(len(t))
    body = peak(band(noise, hi=800)) * np.exp(-t / 0.035)
    crack = peak(band(noise, lo=3000)) * np.exp(-t / 0.006)
    mx.add(0.95 * boom + 0.4 * body + 0.3 * crack, t0, gain=0.95, reverb=0.25)
    shimmer = np.zeros(len(t))
    for f, amp, decay in ((932.33, 1.0, 1.2), (1396.91, 0.6, 0.9), (1864.66, 0.45, 0.7), (2349.32, 0.3, 0.5)):
        shimmer += amp * np.sin(TAU * f * t + rng.uniform(0, TAU)) * np.exp(-t / decay)
    mx.add(peak(shimmer) * (1 - np.exp(-t / 0.004)), t0, gain=0.07, reverb=0.55)


def follow(mx, samples, rng, gain, f_lo, f_hi, shape):
    """Ekranda hareket eden bir cepheyi izleyen hava sesi: konumu cepheyle soldan sağa kayar.
    shape(u) zarfıdır (u: 0 -> 1, sonunda 0 olmalı)."""
    ts, pans = np.array(samples, float).T
    t0, t1 = ts[0], ts[-1]
    t = span(t1 - t0)
    tt = t0 + t
    env = shape(t / (t1 - t0))
    left, right = air(len(t), f_lo + (f_hi - f_lo) * env, 1.2, rng)
    sig = panned(left, right, 0.9 * np.interp(tt, ts, pans))
    mx.add(sig / np.abs(sig).max() * env[:, None], t0, gain=gain, reverb=0.25)


def bell(mx, t0, f, pan, gain):
    """Harf belirince ince nota."""
    t = span(0.9)
    s = (np.sin(TAU * f * t) * np.exp(-t / 0.35) + 0.3 * np.sin(TAU * 2 * f * t) * np.exp(-t / 0.15)
         + 0.12 * np.sin(TAU * 3.01 * f * t) * np.exp(-t / 0.06))
    mx.add(s * (1 - np.exp(-t / 0.002)), t0, gain=gain, pan=pan, reverb=0.4)


def downer(mx, t0, gain):
    """Silme başlarken akor değişimini vurgulayan alçak, inen vuruş."""
    t = span(0.7)
    s = np.sin(glide(40 + 60 * np.exp(-t / 0.08))) * np.exp(-t / 0.25) * (1 - np.exp(-t / 0.003))
    mx.add(s, t0, gain=gain, reverb=0.2)


# ---------------------------------------------------------------- miks

def synthesize(events, seed=4):
    """Sahne olaylarından (void_scene.VoidScene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    duration = events["duration"]
    t = np.arange(int(round(duration * SR))) / SR
    turn, solid = events["turn"], events["solid"]
    wipe0, wipe1 = events["wipe"][0][0], events["wipe"][-1][0]

    # Müzik yatağı: pad referanstaki gibi kabarır; bas kopyalar birleşirken güçlenip logo dolunca tam güçte
    bass_level = ((0.0, -70), (0.4, -30), (turn[0], -20), (solid - 0.03, -7), (solid, 0), (duration, 0))
    bed = 0.45 * pad(t, wipe0, rng) * envelope(t, PAD_LEVEL)[:, None]
    bed += 0.34 * bass(t, wipe0) * envelope(t, bass_level)[:, None]
    wet = convolve(bed, reverb_ir(rng, length=3.0, rt60=2.4))
    bed += 0.35 * wet * np.abs(bed).max() / (np.abs(wet).max() + 1e-12)
    # yatak, flaşlarda ve logo dolduğunda kısa süre çekilir: vuruşlar öne çıkar
    hits = [(a, b - a) for a, b in events["flashes"]]
    bed *= (ducking(t, hits, 0.35) * ducking(t, [(solid, 0.02)], 0.55, release=0.35))[:, None]

    # Efektler: her biri görüntüdeki olayla aynı karede
    mx = Mixer(duration)
    for k, s in enumerate(events["snakes"]):
        swish(mx, s["t0"], s["arrive"], s["pan"], rng, gain=0.2)
        tick(mx, s["done"], TICKS[k % len(TICKS)], 0.15 * s["pan"], gain=0.07)
    riser(mx, turn[0], solid, events["flashes"], rng, gain=0.24)
    for k, (a, b) in enumerate(events["flashes"]):
        zap(mx, a, b, 0.75 + 0.07 * k, rng)
    impact(mx, solid, rng)
    follow(mx, events["reveal"], rng, gain=0.09, f_lo=1500, f_hi=5500,
           shape=lambda u: np.sin(np.pi * u) ** 1.2)
    for k, (tl, p) in enumerate(events["letters"]):
        bell(mx, tl, BELLS[k % len(BELLS)], 0.8 * p, gain=0.08)
    follow(mx, events["wipe"], rng, gain=0.3, f_lo=600, f_hi=5000,
           shape=lambda u: np.sin(np.pi * u) ** 1.5)
    downer(mx, wipe0, gain=0.35)
    sfx = mx.dry + 0.4 * convolve(mx.send, reverb_ir(rng, length=2.4, rt60=1.8))

    mix = bed + sfx
    fade_start = wipe1 + 0.02                # ekran kararınca söner
    fade = 0.5 + 0.5 * np.cos(np.pi * np.clip((t - fade_start) / (duration - fade_start), 0, 1))
    mix *= fade[:, None]

    # Hafif doyurma ile sıkıştırıp tepe seviyeyi -1 dBFS'e getir
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
