"""Void Creations intro animasyonu - ses tasarımı.

Referans videonun sesi vuruşsuz bir müzik yatağıdır: sessizlikten kabaran
koyu, sinematik bir pad. Aynı karakter burada numpy ile sıfırdan sentezlenir,
hazır ses kullanılmaz. Akorlar ve seviye eğrileri referansın spektrumundan
çıkarıldı (Si♭ bas üzerinde La-Re-Mi üst sesleri = Si♭maj7(#11), sonra Sol bas).

  0.0 - 1.7   üst sesler sessizlikten kabarır; filtre açıldıkça parlaklaşır
              (ışık çizgileri logonun kopyalarını çizer)
  1.55 - 2.25 Si♭ bası güçlenerek girer: kopyalar tek logoda birleşirken
  2.25 - 3.47 akor tam güçte; bas yavaşça nefes alır (yazı belirir)
  3.47        silmeyle birlikte bas Sol'e iner, üst sesler kalır
  3.75 - 4.4  ekran kararınca ses söner
"""
import numpy as np

from sound import SR, TAU, band, convolve, reverb_ir

UPPER = ((220.00, -3.5), (293.66, -2.3), (440.00, 0.0), (587.33, -7.0), (659.26, -15.0))  # La3 Re4 La4 Re5 Mi5, dB
BASS = (58.27, 49.00)    # Si♭1 -> Sol1

# Seviye eğrileri (saniye, dB): referansın bant enerjilerinden
PAD_LEVEL = ((0.0, -70), (0.2, -45), (0.4, -33), (0.6, -24), (0.8, -18), (1.0, -15.3), (1.2, -12),
             (1.4, -10.6), (1.6, -7.7), (1.8, -5.2), (2.0, -3.4), (2.2, -2.5), (2.5, -1), (3.0, 0),
             (3.4, 1.5), (4.4, 1.5))
BASS_LEVEL = ((0.0, -70), (0.2, -35), (0.4, -24), (0.6, -20), (0.8, -15.5), (1.0, -14), (1.3, -13),
              (1.5, -11.5), (1.6, -8.6), (1.8, -1.7), (2.0, 2.1), (2.2, 4.0), (2.4, 2.4), (2.6, -1.5),
              (2.8, -5.0), (3.0, 2.0), (3.2, 5.0), (3.4, -1.0), (3.6, 4.5), (3.8, 6.5), (4.4, 6.5))
PAD_CUTOFF = ((0.0, 900), (0.3, 1400), (1.0, 2600), (2.0, 3400), (3.0, 3800), (4.4, 3800))  # Hz


def db(x):
    return 10 ** (np.asarray(x) / 20)


def envelope(t, table, smooth=0.04):
    """dB tablosundan doğrusal genlik eğrisi; köşeler kısa bir ortalama ile yumuşatılır."""
    ts, vs = np.array(table, float).T
    env = db(np.interp(t, ts, vs))
    k = int(smooth * SR) | 1
    pad = k // 2
    padded = np.concatenate([np.full(pad, env[0]), env, np.full(pad, env[-1])])
    return np.convolve(padded, np.ones(k) / k, mode="valid")


def voice(t, f0, fc, rng, top=8000.0, drift=0.0012):
    """Filtreli testere dişi (toplamalı sentez): her harmonik, o anki kesim
    frekansındaki alçak geçiren filtre kazancıyla (12 dB/oktav) çarpılır."""
    wobble = 1 + drift * np.sin(TAU * rng.uniform(0.15, 0.35) * t + rng.uniform(0, TAU))
    phase = TAU * np.cumsum(f0 * wobble) / SR
    out = np.zeros(len(t))
    for h in range(1, int(top / f0) + 1):
        gain = 1 / np.sqrt(1 + (f0 * h / fc) ** 4)
        out += gain / h * np.sin(h * phase + rng.uniform(0, TAU))
    return out


def stereo(sig, pan):
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([sig * np.cos(p), sig * np.sin(p)], -1)


def upper_pad(t, rng):
    """Üst sesler: her nota beş akort kaymış ses (supersaw); tizlerde harmonikler
    birbirine karışıp referanstaki gibi yoğun bir doku olur."""
    ts, fs = np.array(PAD_CUTOFF, float).T
    fc = np.exp(np.interp(t, ts, np.log(fs)))
    out = np.zeros((len(t), 2))
    for f, level in UPPER:
        for cents, pan in ((-18, -0.9), (-9, -0.45), (0, 0.0), (9, 0.45), (18, 0.9)):
            out += db(level) * stereo(voice(t, f * 2 ** (cents / 1200), fc, rng), pan)
    return out / np.abs(out).max()


def bass(t, change, rng):
    """Si♭1'den Sol1'e: iki testere (hafif akort kayık) ve temeli güçlendiren sinüs."""
    out = np.zeros((len(t), 2))
    for f0, (a, b) in ((BASS[0], (0.0, change)), (BASS[1], (change, t[-1] + 1))):
        attack = np.clip((t - a) / 0.03, 0, 1) if a > 0 else 1.0   # ilk notanın girişini seviye eğrisi yapar
        gate = attack * np.clip((b - t) / 0.06, 0, 1)
        fc = np.full(len(t), 650.0)
        for cents, pan in ((-5, -0.3), (5, 0.3)):
            out += 0.5 * stereo(voice(t, f0 * 2 ** (cents / 1200), fc, rng, top=2500) * gate, pan)
        sub = np.sin(TAU * f0 * t) * gate
        out += 0.9 * sub[:, None] * np.sqrt(0.5)
    return out / np.abs(out).max()


def air(t, rng):
    """Tizlerdeki hafif hava dokusu: yavaşça dalgalanan filtreli gürültü."""
    noise = np.stack([band(rng.standard_normal(len(t)), lo=1800, hi=7000) for _ in range(2)], -1)
    move = 0.75 + 0.25 * np.sin(TAU * 0.45 * t + 1.3)
    return noise / np.abs(noise).max() * move[:, None]


def synthesize(events, seed=4):
    """Sahne olaylarından (void_scene.VoidScene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    duration = events["duration"]
    t = np.arange(int(round(duration * SR))) / SR
    change = events["wipe"][0]               # akor değişimi silmeyle birlikte

    pad_env = envelope(t, PAD_LEVEL)
    mix = upper_pad(t, rng) * pad_env[:, None]
    mix += 0.27 * bass(t, change, rng) * envelope(t, BASS_LEVEL)[:, None]
    mix += 0.04 * air(t, rng) * pad_env[:, None]

    wet = convolve(mix, reverb_ir(rng, length=3.2, rt60=2.6))
    mix = mix + 0.45 * wet * (np.abs(mix).max() / (np.abs(wet).max() + 1e-12))

    fade_start = events["wipe"][1] + 0.02    # ekran kararınca söner
    fade = 0.5 + 0.5 * np.cos(np.pi * np.clip((t - fade_start) / (duration - fade_start), 0, 1))
    mix *= fade[:, None]

    # Hafif doyurma ile sıkıştırıp tepe seviyeyi -1 dBFS'e getir
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
