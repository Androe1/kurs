"""NexDev intro animasyonu - ses tasarımı.

Androe intro'sunun ses araçlarını (sound.py) kullanır; zamanlamalar
nexdev_scene.NexDevScene.events() içinden gelir.

  küpler belirir     -> tok blok sesi + yükselen nota (Do Re Mi Sol La)
  küpler dalgalanır  -> hafif ışıltı
  her küp dönüşü     -> Rubik küpü gibi plastik "klak"
  küpler toplanır    -> whoosh, ardından yükselen gerilim
  harfler çözülür    -> derin vuruş, çan, sıcak akor
"""
import numpy as np

from sound import (NOTES, SR, TAU, Mixer, band, bell, convolve, glide, glint, impact, pad, peak,
                   reverb_ir, span, sweep_band)


def block_pop(mx, t0, x, note):
    t = span(0.5)
    body = np.sin(glide(220 + 160 * np.exp(-t / 0.03))) * (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.06)
    click = np.sin(TAU * 3200 * t) * np.exp(-t / 0.003)
    tone = (np.sin(TAU * note * t) * np.exp(-t / 0.25) + 0.3 * np.sin(TAU * 2 * note * t) * np.exp(-t / 0.1))
    pan = float(np.clip(2 * x - 1, -0.8, 0.8))
    mx.add(body + 0.3 * click, t0, gain=0.4, pan=pan, reverb=0.15)
    mx.add(tone * (1 - np.exp(-t / 0.002)), t0, gain=0.09, pan=pan, reverb=0.35)


def cube_turn(mx, t0, t1, x, rng):
    """Rubik dönüşü: kısa hışırtı ve sonunda plastik bir klak."""
    pan = float(np.clip(2 * x - 1, -0.8, 0.8))
    dur = t1 - t0
    t = span(dur)
    swish = peak(band(rng.standard_normal(len(t)), lo=1500, hi=6000)) * np.sin(np.pi * t / dur) ** 2
    mx.add(swish, t0, gain=0.035, pan=pan, reverb=0.1)
    t = span(0.12)
    f = rng.uniform(1600, 2300)
    clack = (peak(band(rng.standard_normal(len(t)), lo=1500, hi=5000)) * np.exp(-t / 0.004)
             + 0.6 * np.sin(TAU * f * t) * np.exp(-t / 0.008)
             + 0.8 * np.sin(TAU * 260 * t) * np.exp(-t / 0.015))
    mx.add(clack, t1, gain=0.2 * rng.uniform(0.8, 1.0), pan=pan, reverb=0.12)


def sparkle(mx, t0, rng, count=18, spread=0.5, gain=0.02):
    tt = span(0.12)
    for _ in range(count):
        dt = rng.uniform(0, spread)
        s = np.sin(TAU * rng.uniform(4500, 9000) * tt) * np.exp(-tt / rng.uniform(0.015, 0.04))
        mx.add(s, t0 + dt, gain=gain, pan=rng.uniform(-0.8, 0.8), reverb=0.5)


def whoosh(mx, t0, t1, rng):
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    air = np.stack([sweep_band(rng.standard_normal(len(t)), 600 * 4**u, 1.0) for _ in range(2)], -1)
    mx.add(air / np.abs(air).max() * (np.sin(np.pi * u) ** 2)[:, None], t0, gain=0.22, reverb=0.25)


def riser(mx, t0, t1, rng):
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = u**2.2 * np.clip((dur - t) / 0.01, 0, 1)
    noise = np.stack([sweep_band(rng.standard_normal(len(t)), 300 * 20 ** (u**1.3), 1.5) for _ in range(2)], -1)
    mx.add(noise / np.abs(noise).max() * env[:, None], t0, gain=0.28, reverb=0.15)
    ph = glide(80 * 4 ** (u**1.8))
    tone = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.18 * np.sin(3 * ph)) * env
    mx.add(peak(tone), t0, gain=0.12, reverb=0.1)


def synthesize(events, seed=9):
    """Sahne olaylarından stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    mx = Mixer(events["duration"])
    out = events["out"]

    for t, x, i in events["pops"]:
        block_pop(mx, t, x, NOTES[i % len(NOTES)])
    for t0, t1, x in events["flips"]:
        cube_turn(mx, t0, t1, x, rng)
    sparkle(mx, events["wave"], rng)
    pad(mx, events["pops"][0][0], events["gather"][0], events["gather"][1], rng)   # sembollerin altında zemin
    whoosh(mx, *events["gather"], rng)
    riser(mx, events["gather"][1], events["snap"] - 0.01, rng)
    impact(mx, events["snap"], rng)
    bell(mx, events["snap"], 1046.5, gain=0.12, rng=rng)
    sparkle(mx, events["melt"][0], rng, count=24, spread=0.6, gain=0.022)
    pad(mx, events["snap"] - 0.03, out[0] + 0.05, out[1] + 0.08, rng)
    glint(mx, sum(events["glint"]) / 2)

    mix = mx.dry + 0.4 * convolve(mx.send, reverb_ir(rng))
    t = np.arange(len(mix)) / SR
    fade = np.clip(t / 0.003, 0, 1)
    fade *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - out[0] - 0.05) / (out[1] + 0.08 - out[0] - 0.05), 0, 1))
    mix *= fade[:, None]
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
