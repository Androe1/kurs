"""SCP sinematiği - ses tasarımı (numpy ile sentez; hazır ses kullanılmaz).

Zamanlar Blender'ın yazdığı meta.json'dan gelir (blender/scp_cinematic.py):

  0 - 1 sn      sessizlik, sonda alçak bir emme (riser)
  her kesme     derin vuruş + metalik çarpma, uzun yankı; altta karanlık uğultu (drone)
  SECURE        kasa yığını kayarken hava sesi (whoosh), kasa kilidi "klak"ı
  CONTAIN       her zırhlı araç: dizel motor gürültüsü + palet/lastik hışırtısı,
                soldan sağa geçen stereo konum ve Doppler kayması
  PROTECT       harflerin altından geçerken whoosh, en sonda yankıyla sönen büyük vuruş
"""
import numpy as np

from glitch_sound import boom, crack, riser, thud, whoosh
from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span


def hit(mx, t0, rng, gain=1.0):
    """Kesme vuruşu: derin boom, metal çarpma ve kısa çatırtı."""
    boom(mx, t0, rng, gain=0.75 * gain)
    t = span(1.6)
    metal = sum(np.sin(TAU * f * t + rng.uniform(0, 6)) * np.exp(-t / d)
                for f, d in ((187, 0.5), (431, 0.35), (977, 0.2), (1720, 0.12)))
    mx.add(metal * (1 - np.exp(-t / 0.001)), t0, gain=0.07 * gain, reverb=0.6)
    crack(mx, t0, rng, gain=0.22 * gain)


def drone(mx, t0, t1, rng):
    dur = t1 - t0
    t = span(dur)
    env = np.clip(t / 0.4, 0, 1) * np.clip((dur - t) / 0.8, 0, 1)
    tone = (np.sin(TAU * 41.2 * t) + 0.5 * np.sin(TAU * 61.7 * t + 1) + 0.25 * np.sin(TAU * 82.4 * t)
            ) * (0.8 + 0.2 * np.sin(TAU * 0.3 * t))
    air = peak(band(rng.standard_normal(len(t)), lo=80, hi=400))
    mx.add((tone + 0.35 * air) * env, t0, gain=0.09, reverb=0.3)


def engine_pass(mx, t_mid, rng, dur=2.4, gain=0.5):
    """Önden geçen ağır araç: dizel uğultu + tekerlek gürültüsü, sol -> sağ, Doppler."""
    t = span(dur)
    u = (t - dur / 2) / 0.55                         # geçiş anına uzaklık (normalize)
    near = 1 / (1 + u ** 2)
    doppler = 1 + 0.06 * np.tanh(-u)
    f0 = 38 * doppler
    ph = glide(f0)
    body = sum(np.sign(np.sin(k * ph)) / k for k in (1, 2, 3, 5)) * 0.5
    rumble = band(body + 0.4 * rng.standard_normal(len(t)), hi=420)
    tires = band(rng.standard_normal(len(t)), lo=700, hi=4000)
    sig = peak(rumble) + 0.35 * peak(tires) * near
    sig *= near ** 0.8
    pan = np.tanh(u * 0.9)
    p = (pan + 1) * np.pi / 4
    st = np.stack([sig * np.cos(p), sig * np.sin(p)], -1)
    mx.add(st, t_mid - dur / 2, gain=gain, reverb=0.15)


def latch(mx, t0, rng):
    t = span(0.15)
    click = peak(band(rng.standard_normal(len(t)), lo=1500, hi=6000)) * np.exp(-t / 0.006)
    knock = np.sin(TAU * 180 * t) * np.exp(-t / 0.03)
    mx.add(click + 0.7 * knock, t0, gain=0.18, pan=0.3, reverb=0.25)


def synthesize(ev, seed=13):
    rng = np.random.default_rng(seed)
    dur = ev["end"] + 1.5
    mx = Mixer(dur)
    c1, c2, c3 = ev["cuts"]
    riser(mx, c1 - 0.7, c1, rng, f0=120, f1=1800, gain=0.12)
    drone(mx, c1, ev["end"] + 1.2, rng)
    for c in (c1, c2, c3):
        hit(mx, c, rng, gain=1.0 if c != c1 else 1.15)

    a, b = ev["crate_pass"]
    whoosh(mx, a, a + 0.75, rng, f0=300, f1=1400, pan0=0.6, pan1=-0.6, gain=0.2)
    latch(mx, a + 0.85, rng)
    thud(mx, a + 0.05, gain=0.12, pan=0.4)

    for t in ev["apc_pass"]:
        engine_pass(mx, t, rng)
    whoosh(mx, ev["apc_pass"][0] - 0.2, ev["apc_pass"][0] + 0.3, rng, f0=400, f1=2500, pan0=-0.7, pan1=0.7,
           gain=0.15)

    x = ev["through_text"]
    whoosh(mx, x - 0.45, x + 0.25, rng, f0=250, f1=3200, gain=0.24)
    hit(mx, ev["end"] - 0.25, rng, gain=0.8)

    wet = convolve(mx.send, reverb_ir(rng, length=3.0, rt60=2.4))
    out = mx.dry + 0.45 * wet
    fade = np.clip((dur - span(dur)) / 1.0, 0, 1)
    out *= fade[:, None]
    return (out / np.abs(out).max() * 10 ** (-1 / 20)).astype(np.float32)
