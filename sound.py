"""Androe Studio intro animasyonu - ses tasarımı.

Tüm sesler numpy ile sıfırdan sentezlenir, hazır ses dosyası kullanılmaz.
Zamanlamalar görsel sahneden gelir; her vuruş, kayış ve nota görüntüdeki
olayla aynı anda duyulur.

  ikon dönerek gelir   -> yaklaştıkça yükselen, dönüşle nabız atan "vuuum"
  ikon yerine oturur   -> derin vuruş, çatırtı, parlak çan
  ikon kayar           -> ikonun yönünde soldan sağa / sağdan sola "whoosh"
  harfler çıkar        -> her harfe bir nota (ANDROE yükselir, STUDIO alçalır)
  ikon durur           -> yumuşak "tok"
  logo oturur          -> çan, ışıltı, alt vuruş ve sıcak bir akor
"""
import wave

import numpy as np

SR = 48000
TAU = 2 * np.pi

NOTES = [523.25, 587.33, 659.26, 783.99, 880.00, 1046.50]  # Do5 Re5 Mi5 Sol5 La5 Do6
CHORD = [130.81, 196.00, 261.63, 293.66, 329.63, 392.00]   # Do majör (add9)


# ---------------------------------------------------------------- yardımcılar

def span(duration):
    return np.arange(int(duration * SR)) / SR


def peak(x):
    return x / (np.abs(x).max() + 1e-12)


def band(x, lo=None, hi=None, order=2):
    """Sıfır fazlı alçak/yüksek/band geçiren filtre (FFT ile)."""
    n = len(x)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    f = np.fft.rfftfreq(size, 1 / SR)
    gain = np.ones_like(f)
    if hi:
        gain /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        gain /= np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    return np.fft.irfft(np.fft.rfft(x, size) * gain, size)[:n]


def sweep_band(x, fc, q):
    """Merkez frekansı zamanla değişen band geçiren filtre (durum değişkenli filtre)."""
    g = np.tan(np.pi * np.clip(fc, 20, 0.45 * SR) / SR)
    k = 1 / q
    a1 = 1 / (1 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    out = np.empty(len(x))
    s1 = s2 = 0.0
    for i, (v0, b1, b2, b3) in enumerate(zip(x.tolist(), a1.tolist(), a2.tolist(), a3.tolist())):
        v3 = v0 - s2
        v1 = b1 * s1 + b2 * v3
        v2 = s2 + b2 * s1 + b3 * v3
        s1, s2 = 2 * v1 - s1, 2 * v2 - s2
        out[i] = v1
    return out * k


def glide(freq):
    """Değişen frekans dizisinden faz üretir."""
    return TAU * np.cumsum(freq) / SR


class Mixer:
    """Sesleri zamana yerleştirir; bir kısmını yankı (reverb) kanalına gönderir."""

    def __init__(self, duration):
        n = int(round(duration * SR))
        self.dry = np.zeros((n, 2))
        self.send = np.zeros((n, 2))

    def add(self, sig, t0, gain=1.0, pan=0.0, reverb=0.0):
        sig = np.asarray(sig, float) * gain
        if sig.ndim == 1:
            p = (np.clip(pan, -1, 1) + 1) * np.pi / 4       # sabit güçte stereo konum
            sig = np.stack([sig * np.cos(p), sig * np.sin(p)], -1)
        i0 = int(round(t0 * SR))
        a, b = max(i0, 0), min(i0 + len(sig), len(self.dry))
        if b > a:
            self.dry[a:b] += sig[a - i0:b - i0]
            self.send[a:b] += sig[a - i0:b - i0] * reverb


def reverb_ir(rng, length=2.2, rt60=1.5):
    """Yapay oda yankısı: tizleri daha çabuk sönen stereo gürültü kuyruğu."""
    t = span(length)
    ir = np.zeros((len(t), 2))
    for ch in range(2):
        noise = rng.standard_normal(len(t))
        ir[:, ch] = (band(noise, hi=900) * np.exp(-6.9 * t / rt60)
                     + band(noise, lo=900, hi=5000) * np.exp(-6.9 * t / (0.75 * rt60))
                     + 0.6 * band(noise, lo=5000) * np.exp(-6.9 * t / (0.35 * rt60)))
    ir *= np.clip(t / 0.004, 0, 1)[:, None]
    ir = np.vstack([np.zeros((int(0.018 * SR), 2)), ir])   # 18 ms ön gecikme
    return ir / np.sqrt((ir**2).sum(0).mean())


def convolve(x, ir):
    size = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    out = np.empty_like(x)
    for ch in range(2):
        y = np.fft.irfft(np.fft.rfft(x[:, ch], size) * np.fft.rfft(ir[:, ch], size), size)
        out[:, ch] = y[:len(x)]
    return out


# ---------------------------------------------------------------- ses efektleri

def spin_in(mx, t0, t1, spin_t, facing, rng):
    """İkon derinlikten dönerek gelirken: yaklaştıkça yükselen, dönüşle nabız atan hava sesi."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    near = (1 - (1 - u) ** 3) ** 2                        # yaklaşma (görüntüdeki gibi yavaşlayarak)
    pulse_ = 0.3 + 0.7 * np.interp(t0 + t, spin_t, facing) ** 2
    env = near * pulse_ * np.clip(t / 0.03, 0, 1) * np.clip((dur - t) / 0.01, 0, 1)
    fc = 350 * 7.5 ** near
    air = np.stack([sweep_band(rng.standard_normal(len(t)), fc, 1.4) for _ in range(2)], -1)
    mx.add(air / np.abs(air).max() * env[:, None], t0, gain=0.34, reverb=0.2)

    ph = glide(90 * 4 ** (u**1.6))
    tone = (np.sin(ph) + 0.35 * np.sin(2 * ph + 0.3) + 0.18 * np.sin(3 * ph)) * u**2.2
    mx.add(peak(tone) * np.clip((dur - t) / 0.01, 0, 1), t0, gain=0.12, reverb=0.1)


def impact(mx, t0, rng):
    """İkon yerine oturduğunda: derin vuruş, çatırtı, saçılan parçalar ve parlak çan."""
    t = span(2.0)
    env = (1 - np.exp(-t / 0.0015)) * np.exp(-t / 0.30)
    boom = np.tanh(1.8 * np.sin(glide(38 + 100 * np.exp(-t / 0.045))) * env) / np.tanh(1.8)
    noise = rng.standard_normal(len(t))
    punch = peak(band(noise, hi=900)) * np.exp(-t / 0.03)
    crack = peak(band(noise, lo=2500)) * np.exp(-t / 0.005)
    mx.add(0.9 * boom + 0.45 * punch + 0.3 * crack, t0, reverb=0.25)
    bell(mx, t0, 1046.5, gain=0.08, rng=rng)

    tt = span(0.06)
    for _ in range(30):
        dt = min(0.004 + rng.exponential(0.06), 0.35)
        f = rng.uniform(1900, 5200)
        tau = rng.uniform(0.004, 0.012)
        grain = (np.sin(TAU * f * tt + rng.uniform(0, TAU)) * np.exp(-tt / tau)
                 + 0.4 * np.sin(TAU * 2.63 * f * tt) * np.exp(-tt / (0.6 * tau)))
        amp = 0.1 * rng.uniform(0.35, 1) * np.exp(-dt / 0.15)
        mx.add(grain * amp, t0 + dt, pan=rng.uniform(-0.85, 0.85), reverb=0.2)


def bell(mx, t0, f0, gain, rng):
    t = span(2.6)
    tone = 0.5 * np.sin(TAU * f0 / 2 * t) * np.exp(-t / 1.8)
    for ratio, amp, decay in ((1.0, 1.0, 1.6), (2.0, 0.45, 1.1), (2.76, 0.3, 0.7),
                              (5.4, 0.16, 0.35), (8.93, 0.08, 0.18)):
        tone += amp * np.sin(TAU * f0 * ratio * t + rng.uniform(0, TAU)) * np.exp(-t / decay)
    mx.add(peak(tone) * (1 - np.exp(-t / 0.003)), t0, gain=gain, reverb=0.5)


def charge(mx, t0, t1, rng):
    """İkon ışığı içine çekerken: yükselen, sonunda kesilen parlak hışırtı ve ton."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = u**2 * np.clip((dur - t) / 0.01, 0, 1)
    air = np.stack([sweep_band(rng.standard_normal(len(t)), 800 * 10 ** u, 2.0) for _ in range(2)], -1)
    mx.add(air / np.abs(air).max() * env[:, None], t0, gain=0.16, reverb=0.3)
    ph = glide(220 * 4 ** u)
    tone = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * env
    mx.add(peak(tone), t0, gain=0.07, reverb=0.3)


def swoosh(mx, t0, t1, x0, x1, rng, gain=0.3):
    """İkon kayarken: hızına göre parlaklaşan, ikonla birlikte stereo alanda gezen hava sesi."""
    dur = t1 - t0
    t = span(dur + 0.1)
    u = np.clip(t / dur, 0, 1)
    speed = np.where(u < 0.5, 4 * u**2, 4 * (1 - u) ** 2)   # ease-in-out hız eğrisi (tepe 1)
    e = np.where(u < 0.5, 4 * u**3, 1 - (2 - 2 * u) ** 3 / 2)
    pan = np.clip(2 * (x0 + (x1 - x0) * e) - 1, -0.85, 0.85)
    air = [sweep_band(rng.standard_normal(len(t)), 500 + 2600 * speed, 1.1) for _ in range(2)]
    env = speed**1.3
    for ch, sig in enumerate(air):
        sig = sig / np.abs(sig).max() * env
        mx.add(sig, t0, gain=gain, pan=np.clip(pan + (0.25 if ch else -0.25), -1, 1), reverb=0.2)


def stop_thump(mx, t0, x, gain):
    """İkon durduğunda yumuşak, tok bir vuruş."""
    t = span(0.6)
    body = np.sin(glide(70 + 90 * np.exp(-t / 0.02))) * (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.12)
    click = np.sin(TAU * 2400 * t) * np.exp(-t / 0.004)
    mx.add(body + 0.25 * click, t0, gain=gain, pan=np.clip(2 * x - 1, -0.7, 0.7), reverb=0.15)


def letter_notes(mx, letters):
    """Her harf ikonun altından çıktığında bir nota: A-N-D-R-O-E / S-T-U-D-I-O = Do Re Mi Sol La Do."""
    t = span(0.9)
    for t0, i, x in letters:
        f = NOTES[i]
        tone = (np.sin(TAU * f * t) * np.exp(-t / 0.3)
                + 0.28 * np.sin(TAU * 2 * f * t) * np.exp(-t / 0.12)
                + 0.12 * np.sin(TAU * 3.01 * f * t) * np.exp(-t / 0.05))
        mx.add(tone * (1 - np.exp(-t / 0.002)), t0, gain=0.1, pan=np.clip(2 * x - 1, -0.8, 0.8),
               reverb=0.35)


def resolve(mx, t0, rng):
    """Logo son yerine oturunca: çan, ışıltı ve yumuşak alt vuruş."""
    bell(mx, t0, 1046.5, gain=0.13, rng=rng)
    t = span(0.9)
    env = np.sin(np.pi * np.clip(t / 0.6, 0, 1)) ** 1.5
    shimmer = peak(band(rng.standard_normal(len(t)), lo=5000, hi=12000)) * env
    mx.add(shimmer, t0, gain=0.05, reverb=0.4)
    tt = span(0.12)
    for _ in range(24):
        dt = rng.uniform(0, 0.6)
        spark = np.sin(TAU * rng.uniform(4500, 9000) * tt) * np.exp(-tt / rng.uniform(0.015, 0.04))
        mx.add(spark, t0 + dt, gain=0.022, pan=rng.uniform(-0.8, 0.8), reverb=0.5)
    t = span(1.2)
    thump = np.sin(glide(48 + 30 * np.exp(-t / 0.05))) * (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.35)
    mx.add(thump, t0, gain=0.4, reverb=0.1)


def pad(mx, t0, t_release, t_end, rng):
    """Logo oturduktan sonra çalan, parlak başlayıp yumuşayan geniş akor."""
    t = span(t_end - t0)
    rel = t_release - t0
    env = (0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.35, 0, 1)))
    env *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - rel) / (t_end - t_release), 0, 1))
    bright = 700 + 2200 * np.exp(-t / 0.5)
    out = np.zeros((len(t), 2))
    for f in CHORD:
        for cents, pan in ((-7, -0.6), (0, 0.0), (7, 0.6)):
            fd = f * 2 ** (cents / 1200)
            ratio = np.exp(-fd / bright)             # her üst harmonik biraz daha kısık
            amp = np.ones_like(t)
            voice = np.zeros_like(t)
            for h in range(1, int(7000 / fd) + 1):
                voice += amp / h * np.sin(TAU * fd * h * t + rng.uniform(0, TAU))
                amp = amp * ratio
            p = (pan + 1) * np.pi / 4
            out[:, 0] += voice * np.cos(p)
            out[:, 1] += voice * np.sin(p)
    sub = np.sin(TAU * 65.41 * t) + 0.25 * np.sin(TAU * 130.81 * t)
    out = out / np.abs(out).max() + 0.25 * sub[:, None]
    mx.add(out / np.abs(out).max() * env[:, None], t0, gain=0.17, reverb=0.25)


def glint(mx, t0):
    t = span(0.9)
    ting = (np.sin(TAU * 2637 * t) * np.exp(-t / 0.35)
            + 0.5 * np.sin(TAU * 3951 * t) * np.exp(-t / 0.22)) * (1 - np.exp(-t / 0.002))
    mx.add(ting, t0, gain=0.03, pan=0.2, reverb=0.5)


# ---------------------------------------------------------------- miks

def synthesize(events, seed=5):
    """Sahne olaylarından (scene.Scene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    mx = Mixer(events["duration"])
    out = events["out"]

    spin_in(mx, events["spin_in"][0], events["land"] - 0.01, *events["spin"], rng)
    impact(mx, events["land"], rng)
    for k, (a, b, x0, x1) in enumerate(events["moves"]):
        swoosh(mx, a, b, x0, x1, rng)
        if k < len(events["moves"]) - 1:
            stop_thump(mx, b, x1, gain=0.35)
    stop_thump(mx, events["moves"][-1][1], events["moves"][-1][3], gain=0.35)
    letter_notes(mx, events["letters"])
    charge(mx, events["exit"][0], events["final"] - 0.01, rng)
    for side in (0.2, 0.8):                     # kelimeler iki yandan ortaya süzülür
        swoosh(mx, *events["glide"], side, 0.5, rng, gain=0.12)
    resolve(mx, events["final"], rng)
    pad(mx, events["final"] - 0.03, out[0] + 0.05, out[1] + 0.08, rng)
    glint(mx, events["glint"][0] + 0.15)       # ışık dalgası yazıya değdiği an

    mix = mx.dry + 0.4 * convolve(mx.send, reverb_ir(rng))

    t = np.arange(len(mix)) / SR
    fade = np.clip(t / 0.003, 0, 1)
    fade *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - out[0] - 0.05) / (out[1] + 0.08 - out[0] - 0.05), 0, 1))
    mix *= fade[:, None]

    # Hafif doyurma ile sıkıştırıp tepe seviyeyi -1 dBFS'e getir
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)


def write_wav(path, audio):
    data = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
