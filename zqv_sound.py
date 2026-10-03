"""ZQV karanlık animasyonu - ses tasarımı.

sound.py araçlarıyla sıfırdan sentezlenir; zamanlamalar zqv_scene.ZQVScene.events() içinden gelir.

  tüm süre        -> alçak, hafif akortsuz drone (rüzgâr gibi nefes alır)
  0.5 -> 2.4      -> yavaş, uzak kalp atışı
  harfler yanar   -> elektrik vızıltısı, kıvılcım çıtırtısı, derin vuruş
  bozulma         -> dijital cızırtı ve bozuk bas
  harfler dağılır -> ters çan, yükselen hava, sonda sessizlik
"""
import numpy as np

from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span, sweep_band


def drone(mx, t0, t1, rng):
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = np.clip(t / 1.2, 0, 1) * np.clip((dur - t) / 0.9, 0, 1)
    sig = 0
    for f, a in ((55.0, 1.0), (55.45, 0.8), (82.4, 0.35), (110.9, 0.22), (164.5, 0.08)):
        sig = sig + a * np.sin(glide(f * (1 + 0.004 * np.sin(TAU * 0.13 * t))) + rng.uniform(0, TAU))
    wind = np.stack([sweep_band(rng.standard_normal(len(t)), 260 + 140 * np.sin(TAU * 0.21 * t + k), 1.6)
                     for k in range(2)], -1)
    mx.add(peak(sig) * env * (0.8 + 0.2 * np.sin(TAU * 0.3 * t)), t0, gain=0.30, reverb=0.3)
    mx.add(wind / np.abs(wind).max() * (env * (0.5 + 0.5 * np.sin(TAU * 0.17 * t)) ** 2)[:, None],
           t0, gain=0.10, reverb=0.5)


def heartbeat(mx, t0, gain):
    t = span(0.5)
    body = np.sin(glide(52 + 38 * np.exp(-t / 0.05))) * (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.11)
    mx.add(body, t0, gain=gain, reverb=0.25)


def buzz(mx, t0, dur, rng):
    """Bozuk ampul vızıltısı: 100 Hz'lik şebeke uğultusu ve çıtırdayan kapı."""
    t = span(dur)
    gate = (np.sin(TAU * 17 * t) * np.sin(TAU * 7.3 * t + 1) > -0.2).astype(float)
    hum = np.sin(TAU * 100 * t) + 0.5 * np.sin(TAU * 200 * t) + 0.3 * np.sin(TAU * 300 * t)
    hiss = peak(band(rng.standard_normal(len(t)), lo=3000, hi=9000))
    env = np.clip(t / 0.02, 0, 1) * np.exp(-t / (dur * 0.6))
    mx.add((hum * 0.5 + hiss * 0.35) * gate * env, t0, gain=0.09, pan=rng.uniform(-0.3, 0.3), reverb=0.3)


def crackle(mx, t0, rng, count=14, spread=0.5, gain=0.05):
    tt = span(0.03)
    for _ in range(count):
        dt = rng.uniform(0, spread)
        s = peak(band(rng.standard_normal(len(tt)), lo=2500)) * np.exp(-tt / rng.uniform(0.002, 0.006))
        mx.add(s, t0 + dt, gain=gain * rng.uniform(0.4, 1), pan=rng.uniform(-0.8, 0.8), reverb=0.3)


def thud(mx, t0, gain, rng):
    t = span(1.6)
    env = (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.35)
    boom = np.tanh(1.6 * np.sin(glide(34 + 70 * np.exp(-t / 0.06))) * env)
    punch = peak(band(rng.standard_normal(len(t)), hi=500)) * np.exp(-t / 0.05)
    mx.add(boom + 0.35 * punch, t0, gain=gain, reverb=0.4)


def glitch_burst(mx, t0, rng):
    t = span(0.16)
    env = np.exp(-t / 0.05)
    steps = np.floor(t * 90) % 5                           # bit-ezilmiş basamaklı ton
    tone = np.sign(np.sin(glide(70 + 40 * steps)))
    noise = np.round(peak(band(rng.standard_normal(len(t)), lo=1200)) * 6) / 6
    mx.add((0.5 * tone + 0.8 * noise) * env, t0, gain=0.16, pan=rng.uniform(-0.5, 0.5), reverb=0.2)


def dissolve_air(mx, t0, t1, rng):
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = np.sin(np.pi * u) ** 1.5
    air = np.stack([sweep_band(rng.standard_normal(len(t)), 250 * 6 ** u, 1.2) for _ in range(2)], -1)
    mx.add(air / np.abs(air).max() * env[:, None], t0, gain=0.26, reverb=0.5)
    ph = glide(110 * 2 ** (u * 1.4))
    mx.add(peak(np.sin(ph) + 0.4 * np.sin(2 * ph)) * env**2, t0, gain=0.08, reverb=0.5)


def synthesize(events, seed=13):
    rng = np.random.default_rng(seed)
    mx = Mixer(events["duration"])
    out = events["out"]
    dur = events["duration"]

    drone(mx, 0.0, dur, rng)
    for i, t in enumerate(np.arange(0.5, 2.5, 0.86)):
        heartbeat(mx, t, 0.5 * (0.6 + 0.4 * i / 2))
        heartbeat(mx, t + 0.22, 0.32 * (0.6 + 0.4 * i / 2))
    for t in events["letters"]:
        buzz(mx, t, 0.7, rng)
        crackle(mx, t, rng)
        thud(mx, t + 0.45, 0.3, rng)
    for t in events["glitch"]:
        glitch_burst(mx, t, rng)
    thud(mx, events["glitch"][0], 0.35, rng)
    dissolve_air(mx, events["dissolve"][0] - 0.1, out[1], rng)

    mix = mx.dry + 0.5 * convolve(mx.send, reverb_ir(rng, length=2.6, rt60=2.2))
    t = np.arange(len(mix)) / SR
    fade = np.clip(t / 0.4, 0, 1) * (0.5 + 0.5 * np.cos(np.pi * np.clip((t - out[0]) / (dur - out[0]), 0, 1)))
    mix *= fade[:, None]
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-2 / 20)).astype(np.float32)
