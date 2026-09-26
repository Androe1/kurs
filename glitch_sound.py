"""Androe Studio karakterli intro - ses tasarımı.

Tamamen numpy ile sentezlenir; hazır ses ya da örnek kullanılmaz ve GLITCH
açılışındaki müziği / sesleri taklit etmez. Karakteri elektronik ve dijitaldir:

  harfler          -> her harfte tok vuruş + parlak dijital "blip" (La minör pentatonik
                      yükselen dizi), panel süpürmesine kısa hava sesi
  son harf büyür   -> yükselen gerilim
  glitch geçişi    -> kırpılmış (bitcrush) dijital cızırtı, rastgele cıvıltılar, beyaz patlama
  1. karakter      -> fırlarken yükselen whoosh, kol hareketlerine kısa swish'ler,
                      çömelmede yumuşak tok ses, kamçıda şaklama, düşüşte alçalan whoosh
  sahne geçişi     -> kısa dijital "zap"
  2. karakter      -> dönerek yükselen stereo whoosh, kurulurken gerilen ton,
                      patlamada derin vuruş + altın akor vuruşu + ışıltı, düşüşte whoosh
  panel süpürmesi  -> soldan sağa geçen hava sesleri, logoya çıkan yükseliş
  logo             -> her harfte dijital tık, bas vuruşu, sıcak akor zemini,
                      ışık geçişlerinde çın sesi, ara titremelerde küçük glitch'ler
"""
import numpy as np

from sound import SR, TAU, Mixer, band, bell, convolve, glide, peak, reverb_ir, span, sweep_band

# La minör pentatonik, harflerde yükselen dizi (A4 C5 D5 E5 G5 A5)
LETTER_NOTES = [440.0, 523.25, 587.33, 659.26, 783.99, 880.0]
# Altın akor (patlama) ve logo akoru: Fa majör 9 (sıcak, açık)
GOLD_CHORD = [174.61, 261.63, 329.63, 392.0, 523.25]
LOGO_CHORD = [87.31, 130.81, 174.61, 220.0, 261.63, 329.63, 392.0]


def kick(mx, t0, gain=0.6, pitch=1.0):
    t = span(0.5)
    body = np.sin(glide(pitch * (45 + 120 * np.exp(-t / 0.035)))) * (1 - np.exp(-t / 0.0015)) * np.exp(-t / 0.16)
    click = np.sin(TAU * 3000 * t) * np.exp(-t / 0.003)
    mx.add(np.tanh(1.6 * body) + 0.2 * click, t0, gain=gain, reverb=0.08)


def snap(mx, t0, rng, gain=0.25, pan=0.0):
    """Parmak şıklatması / clap arası kuru, parlak vuruş."""
    t = span(0.25)
    n = rng.standard_normal(len(t))
    env = np.exp(-t / 0.035) * (1 + 0.6 * np.exp(-((t - 0.012) / 0.003) ** 2))
    mx.add(peak(band(n, lo=1200, hi=7000)) * env, t0, gain=gain, pan=pan, reverb=0.3)


def blip(mx, t0, f, gain=0.12, pan=0.0, length=0.35):
    """Kare dalgaya yakın, hafif bükülen dijital ton."""
    t = span(length)
    ph = glide(f * (1 + 0.03 * np.exp(-t / 0.02)))
    sq = np.tanh(3 * np.sin(ph)) + 0.25 * np.sin(2 * ph)
    env = (1 - np.exp(-t / 0.002)) * np.exp(-t / (length * 0.35))
    mx.add(peak(band(sq, hi=6000)) * env, t0, gain=gain, pan=pan, reverb=0.3)


def whoosh(mx, t0, t1, rng, f0=500, f1=3000, pan0=0.0, pan1=0.0, gain=0.25, q=1.2):
    """Hareketin hızına göre parlaklaşan hava sesi; frekans ve stereo konum hareketle kayar."""
    dur = t1 - t0
    t = span(dur + 0.08)
    u = np.clip(t / dur, 0, 1)
    env = np.sin(np.pi * u) ** 1.5 * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    fc = f0 * (f1 / f0) ** u
    for side in (-1, 1):
        sig = sweep_band(rng.standard_normal(len(t)), fc * (1 + 0.06 * side), q)
        pan = np.clip(pan0 + (pan1 - pan0) * u.mean() + 0.3 * side, -1, 1)
        mx.add(sig / (np.abs(sig).max() + 1e-9) * env, t0, gain=gain * 0.7, pan=float(pan), reverb=0.2)


def swish(mx, t0, rng, dur=0.08, fc=2500, gain=0.15, pan=0.0):
    """Kol savrulması: çok kısa, keskin hava sesi."""
    whoosh(mx, t0, t0 + dur, rng, f0=fc * 0.6, f1=fc * 1.4, pan0=pan, pan1=pan, gain=gain, q=1.6)


def crack(mx, t0, rng, gain=0.3, pan=0.0):
    """Kamçı şaklaması: çok kısa parlak patlama + yüksek frekanslı çatlak."""
    t = span(0.2)
    n = rng.standard_normal(len(t))
    sig = peak(band(n, lo=2500)) * np.exp(-t / 0.006) + 0.5 * peak(band(n, lo=600, hi=3000)) * np.exp(-t / 0.02)
    mx.add(sig, t0, gain=gain, pan=pan, reverb=0.35)


def thud(mx, t0, gain=0.3, pan=0.0):
    """Yumuşak, tok toplanma sesi (havada çömelme)."""
    t = span(0.35)
    body = np.sin(glide(90 + 60 * np.exp(-t / 0.03))) * (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.08)
    mx.add(body, t0, gain=gain, pan=pan, reverb=0.15)


def riser(mx, t0, t1, rng, f0=300, f1=6000, gain=0.2):
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = u ** 2 * np.clip((dur - t) / 0.01, 0, 1)
    air = np.stack([sweep_band(rng.standard_normal(len(t)), f0 * (f1 / f0) ** (u ** 1.3), 1.5) for _ in range(2)], -1)
    mx.add(air / np.abs(air).max() * env[:, None], t0, gain=gain, reverb=0.2)
    ph = glide(110 * 4 ** (u ** 1.6))
    mx.add(peak(np.sin(ph) + 0.3 * np.sin(2 * ph)) * env, t0, gain=gain * 0.45, reverb=0.15)


def fall_whoosh(mx, t0, t1, rng, pan=0.0, gain=0.24):
    """Düşüş: hızlanan, perdesi alçalan hava sesi ve kayan ton."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    env = u ** 0.7 * np.clip((dur - t) / 0.04, 0, 1)
    air = sweep_band(rng.standard_normal(len(t)), 2600 * (0.25 ** u), 1.3)
    mx.add(air / np.abs(air).max() * env, t0, gain=gain, pan=pan, reverb=0.25)
    ph = glide(700 * 0.3 ** u)
    mx.add(np.sin(ph) * env * 0.5, t0, gain=gain * 0.3, pan=pan, reverb=0.3)


def bitcrush(x, hold, bits):
    """Örnek tutma (düşük örnekleme) ve bit azaltma: dijital bozulma dokusu."""
    idx = (np.arange(len(x)) // hold) * hold
    y = x[np.minimum(idx, len(x) - 1)]
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


def glitch_burst(mx, t0, t1, rng, gain=0.28):
    """Glitch geçişi: yoğunlaşan kırpık dijital cızırtı, rastgele cıvıltılar, kekemelik."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    noise = rng.standard_normal(len(t))
    crushed = bitcrush(band(noise, lo=300, hi=9000) / 3, hold=24, bits=4)
    gate = (rng.random(int(dur * 40) + 1) < 0.4 + 0.5 * np.linspace(0, 1, int(dur * 40) + 1)).astype(float)
    gate = np.repeat(gate, int(SR / 40))[:len(t)]
    gate = np.pad(gate, (0, len(t) - len(gate)))
    mx.add(np.clip(crushed, -1, 1) * gate * u ** 0.8, t0, gain=gain * 0.8, pan=0.0, reverb=0.1)
    for _ in range(18):
        s = t0 + rng.uniform(0, dur)
        tt = span(rng.uniform(0.015, 0.05))
        f = rng.uniform(300, 2500)
        chirp = np.tanh(4 * np.sin(glide(f * (1 + rng.uniform(-0.6, 1.5) * tt / tt[-1]))))
        mx.add(bitcrush(chirp, 8, 3), s, gain=gain * 0.35, pan=rng.uniform(-0.8, 0.8), reverb=0.1)


def white_burst(mx, t0, rng, gain=0.4):
    """Beyaza patlama: açılan parlak hava + derin vuruş."""
    t = span(0.6)
    n = rng.standard_normal(len(t))
    mx.add(peak(band(n, lo=3000)) * np.exp(-t / 0.12) * (1 - np.exp(-t / 0.004)), t0, gain=gain * 0.35, reverb=0.4)
    kick(mx, t0, gain=gain, pitch=0.9)


def zap(mx, t0, rng, gain=0.18):
    """Sahne kesmesinde kısa dijital zap: hızla alçalan ton + kırpık gürültü."""
    t = span(0.12)
    ph = glide(2400 * np.exp(-t / 0.03) + 200)
    sig = np.tanh(3 * np.sin(ph)) * np.exp(-t / 0.05)
    sig += 0.4 * bitcrush(rng.standard_normal(len(t)) * np.exp(-t / 0.02), 16, 3)
    mx.add(sig, t0, gain=gain, reverb=0.15)


def chord_stab(mx, t0, chord, rng, gain=0.2, length=0.9):
    """Detune'lu testere akor vuruşu; filtresi hızla kapanır (parlak -> yumuşak)."""
    t = span(length)
    out = np.zeros((len(t), 2))
    for f in chord:
        for cents, pan in ((-9, -0.5), (0, 0.0), (9, 0.5)):
            fd = f * 2 ** (cents / 1200)
            saw = np.zeros_like(t)
            for h in range(1, int(5000 / fd) + 1):
                saw += np.sin(TAU * fd * h * t + rng.uniform(0, TAU)) / h * np.exp(-h * fd / (500 + 4000 * np.exp(-t / 0.08)))
            p = (pan + 1) * np.pi / 4
            out[:, 0] += saw * np.cos(p)
            out[:, 1] += saw * np.sin(p)
    env = (1 - np.exp(-t / 0.003)) * np.exp(-t / (length * 0.35))
    mx.add(out / np.abs(out).max() * env[:, None], t0, gain=gain, reverb=0.35)


def sparkle(mx, t0, rng, count=20, spread=0.4, gain=0.02):
    tt = span(0.12)
    for _ in range(count):
        s = np.sin(TAU * rng.uniform(4500, 9500) * tt) * np.exp(-tt / rng.uniform(0.015, 0.04))
        mx.add(s, t0 + rng.uniform(0, spread), gain=gain, pan=rng.uniform(-0.85, 0.85), reverb=0.5)


def boom(mx, t0, rng, gain=0.7):
    """Patlama: derin alt vuruş, gövde ve kısa çatırtı."""
    t = span(1.4)
    env = (1 - np.exp(-t / 0.0015)) * np.exp(-t / 0.28)
    low = np.tanh(1.8 * np.sin(glide(36 + 110 * np.exp(-t / 0.05))) * env) / np.tanh(1.8)
    n = rng.standard_normal(len(t))
    mx.add(0.9 * low + 0.35 * peak(band(n, hi=1200)) * np.exp(-t / 0.035)
           + 0.25 * peak(band(n, lo=3000)) * np.exp(-t / 0.006), t0, gain=gain, reverb=0.25)


def tension(mx, t0, t1, gain=0.12):
    """Kurulma: kısa sürede gerilerek yükselen ton (yay gibi)."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    ph = glide(180 * 3 ** (u ** 2))
    sig = (np.tanh(2 * np.sin(ph)) + 0.4 * np.sin(2.01 * ph)) * u ** 1.5 * np.clip((dur - t) / 0.006, 0, 1)
    mx.add(sig, t0, gain=gain, reverb=0.15)


def tick(mx, t0, rng, gain=0.08, pan=0.0):
    """Logo harfi belirirken küçük dijital tık."""
    t = span(0.05)
    f = rng.uniform(1800, 3200)
    sig = bitcrush(np.sin(TAU * f * t) * np.exp(-t / 0.012), 6, 3)
    mx.add(sig, t0, gain=gain, pan=pan, reverb=0.25)


def warm_pad(mx, t0, t_release, t_end, chord, rng, gain=0.16):
    """Logonun altındaki sıcak akor: yavaş açılır, sonda yumuşakça söner."""
    t = span(t_end - t0)
    rel = t_release - t0
    env = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.5, 0, 1))
    env *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - rel) / (t_end - t_release), 0, 1))
    bright = 600 + 1800 * np.exp(-t / 0.8)
    out = np.zeros((len(t), 2))
    for f in chord:
        for cents, pan in ((-6, -0.7), (0, 0.0), (6, 0.7)):
            fd = f * 2 ** (cents / 1200)
            ratio = np.exp(-fd / bright)
            amp = np.ones_like(t)
            voice = np.zeros_like(t)
            for h in range(1, int(6000 / fd) + 1):
                voice += amp / h * np.sin(TAU * fd * h * t + rng.uniform(0, TAU))
                amp = amp * ratio
            # yavaş vibrato benzeri genlik dalgalanması (canlılık)
            voice *= 1 + 0.08 * np.sin(TAU * rng.uniform(0.2, 0.5) * t + rng.uniform(0, TAU))
            p = (pan + 1) * np.pi / 4
            out[:, 0] += voice * np.cos(p)
            out[:, 1] += voice * np.sin(p)
    mx.add(out / np.abs(out).max() * env[:, None], t0, gain=gain, reverb=0.3)


def ting(mx, t0, gain=0.035, pan=0.2):
    t = span(1.0)
    s = (np.sin(TAU * 2637 * t) * np.exp(-t / 0.4) + 0.5 * np.sin(TAU * 3520 * t) * np.exp(-t / 0.25)) * (1 - np.exp(-t / 0.002))
    mx.add(s, t0, gain=gain, pan=pan, reverb=0.5)


def synthesize(ev, seed=21):
    """Sahne olaylarından (GlitchScene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    mx = Mixer(ev["duration"])

    # --- harfler: her vuruşta panel süpürmesi + tok vuruş + yükselen blip
    for i, t0 in enumerate(ev["letters"]):
        pan = -0.3 if i % 2 else 0.3
        whoosh(mx, t0 - 0.05, t0 + 0.1, rng, f0=400, f1=2200, pan0=0, pan1=0, gain=0.12)
        kick(mx, t0, gain=0.5)
        snap(mx, t0 + 0.005, rng, gain=0.12, pan=pan)
        blip(mx, t0, LETTER_NOTES[i], gain=0.1, pan=pan)
        blip(mx, t0 + 0.11, LETTER_NOTES[i] * 2, gain=0.035, pan=-pan, length=0.18)   # küçük yankı notası
    # hafif ritim zemini: vuruşların arasında kısa hi-hat
    for t0 in ev["letters"]:
        for k in (0.5,):
            tt = span(0.05)
            mx.add(peak(band(rng.standard_normal(len(tt)), lo=7000)) * np.exp(-tt / 0.012),
                   t0 + k * 0.45, gain=0.05, pan=0.2, reverb=0.1)
    riser(mx, ev["zoom"][0], ev["glitch"][1], rng, f0=400, f1=7000, gain=0.2)

    # --- glitch geçişi ve beyaza patlama
    glitch_burst(mx, *ev["glitch"], rng)
    white_burst(mx, ev["glitch"][1] - 0.02, rng)

    # --- 1. karakter (sol-orta)
    p1 = -0.15
    whoosh(mx, *ev["c1_rise"], rng, f0=350, f1=2800, pan0=p1, pan1=p1, gain=0.3)
    swish(mx, ev["c1_reach"], rng, dur=0.06, fc=3200, gain=0.12, pan=0.3)
    swish(mx, ev["c1_swipe"][0], rng, dur=ev["c1_swipe"][1] - ev["c1_swipe"][0], fc=2000, gain=0.2, pan=0.35)
    thud(mx, ev["c1_tuck"], gain=0.28, pan=p1)
    swish(mx, ev["c1_windup"][0], rng, dur=ev["c1_windup"][1] - ev["c1_windup"][0], fc=2600, gain=0.14, pan=-0.4)
    swish(mx, ev["c1_whip"][0], rng, dur=0.05, fc=3500, gain=0.18, pan=-0.2)
    crack(mx, ev["c1_whip"][0] + 0.045, rng, gain=0.22, pan=0.0)
    fall_whoosh(mx, *ev["c1_fall"], rng, pan=p1, gain=0.26)

    zap(mx, ev["cut"], rng)

    # --- 2. karakter (orta-sağ)
    p2 = 0.15
    whoosh(mx, *ev["c2_rise"], rng, f0=300, f1=2400, pan0=-0.5, pan1=0.5, gain=0.3)
    tension(mx, *ev["c2_coil"], gain=0.1)
    boom(mx, ev["c2_burst"], rng, gain=0.6)
    chord_stab(mx, ev["c2_burst"], GOLD_CHORD, rng, gain=0.2)
    snap(mx, ev["c2_burst"] + 0.004, rng, gain=0.2, pan=0.0)
    sparkle(mx, ev["c2_burst"] + 0.05, rng, count=26, spread=0.5, gain=0.02)
    t = span(ev["c2_hold"][1] - ev["c2_hold"][0])      # asılı kalışta hafif ışıltılı hava
    hold = peak(band(rng.standard_normal(len(t)), lo=5000, hi=11000)) * np.sin(np.pi * t / t[-1]) ** 2
    mx.add(hold, ev["c2_hold"][0], gain=0.03, pan=p2, reverb=0.4)
    fall_whoosh(mx, *ev["c2_fall"], rng, pan=p2, gain=0.26)

    # --- panel süpürmesi: soldan sağa hava sesleri ve logoya yükseliş
    a, b = ev["sweep"]
    for k in range(4):
        s0 = a + k * 0.2 * (b - a) / 1.6
        whoosh(mx, s0, s0 + 0.2, rng, f0=600, f1=2600, pan0=-0.7, pan1=0.7, gain=0.2)
    riser(mx, a, ev["logo"], rng, f0=500, f1=5000, gain=0.12)

    # --- logo
    logo = ev["logo"]
    boom(mx, logo + 0.1, rng, gain=0.5)
    for k, t0 in enumerate(ev["logo_letters"]):
        tick(mx, t0, rng, gain=0.07, pan=-0.6 + 1.2 * k / max(len(ev["logo_letters"]) - 1, 1))
    chord_stab(mx, ev["logo_letters"][-1] + 0.2, LOGO_CHORD[2:], rng, gain=0.12, length=1.2)
    warm_pad(mx, logo + 0.1, ev["out"][0], ev["out"][1] + 0.05, LOGO_CHORD, rng)
    bell(mx, ev["logo_letters"][-1] + 0.22, 880.0, gain=0.06, rng=rng)
    for k, s0 in enumerate(ev["shines"]):
        ting(mx, s0 + 0.3, gain=0.035 if k == 0 else 0.025, pan=-0.2 + 0.4 * k)
        sparkle(mx, s0 + 0.2, rng, count=10, spread=0.3, gain=0.012)
    for s0 in ev["flickers"]:
        tick(mx, s0, rng, gain=0.035, pan=rng.uniform(-0.5, 0.5))

    mix = mx.dry + 0.35 * convolve(mx.send, reverb_ir(rng, length=1.8, rt60=1.2))
    t = np.arange(len(mix)) / SR
    out = ev["out"]
    fade = np.clip(t / 0.003, 0, 1)
    fade *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - out[0]) / (out[1] + 0.04 - out[0]), 0, 1))
    mix *= fade[:, None]
    mix = np.tanh(1.4 * mix / np.abs(mix).max()) / np.tanh(1.4)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
