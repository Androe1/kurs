"""Androe Studio karakterli intro - ses tasarımı (enerjik, ritmik).

Tamamen numpy ile sentezlenir; hazır ses ya da örnek kullanılmaz ve GLITCH
açılışının müziğini taklit etmez. Her şey harflerin vuruşuna kilitli bir tempo
ızgarasında çalar (BEAT = 0.45 s = 133 BPM, La minör):

  harfler (0.35-3.05)   dört vuruşlu davul (kick), 2. ve 4. vuruşta clap, sekizlik hi-hat,
                        offbeat bas, her harfte yükselen dijital nota + panel whoosh'u;
                        son bar trampet rulosu ve yükseliş
  glitch (3.05-3.45)    son 16'lığın kekeleyerek tekrarı (stutter), bitcrush, beyaza patlama
  karakterler           tam groove: 16'lık bas, açık hi-hat, arpej, kick'e göre "pompalayan"
                        (sidechain) akor; karakter sesleri animasyon karelerine bağlı: fırlama
                        whoosh'u, vuruşta patlama + akor vuruşu, çırpınmalarda swish, düşüş
  panel süpürmesi       trampet rulosu + yükseliş, logodan hemen önce kısa sessizlik
  logo                  büyük vuruş + akor, yarım tempo groove, sıcak akor zemini, çın sesleri;
                        sonda yankı kuyruğuyla söner
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


# ---------------------------------------------------------------- ritim bölümü

CHORDS = {  # La minör: kök (bas) ve akor notaları
    "Am": (55.0, [220.0, 261.63, 329.63, 440.0]),
    "F": (43.65, [174.61, 220.0, 261.63, 349.23]),
    "C": (65.41, [196.0, 261.63, 329.63, 392.0]),
    "G": (49.0, [196.0, 246.94, 293.66, 392.0]),
}
PROG = ["Am", "F", "C", "G"]


def hat(mx, t0, rng, open_=False, gain=0.06, pan=0.25):
    t = span(0.25 if open_ else 0.06)
    n = rng.standard_normal(len(t))
    env = np.exp(-t / (0.09 if open_ else 0.014))
    mx.add(peak(band(n, lo=7500)) * env, t0, gain=gain, pan=pan, reverb=0.05)


def clap(mx, t0, rng, gain=0.28):
    """Üç hızlı patlamadan oluşan el çırpma + gövde."""
    t = span(0.3)
    n = rng.standard_normal(len(t))
    env = sum(np.exp(-np.clip(t - d, 0, None) / 0.006) * (t >= d) for d in (0.0, 0.011, 0.022))
    env = env + 0.8 * np.exp(-np.clip(t - 0.03, 0, None) / 0.07) * (t >= 0.03)
    mx.add(peak(band(n, lo=900, hi=6000)) * env, t0, gain=gain, pan=0.0, reverb=0.25)


def snare(mx, t0, rng, gain=0.2):
    t = span(0.22)
    n = rng.standard_normal(len(t))
    body = np.sin(glide(190 * (1 + 0.4 * np.exp(-t / 0.01)))) * np.exp(-t / 0.05)
    mx.add(0.6 * body + peak(band(n, lo=1500, hi=9000)) * np.exp(-t / 0.07), t0, gain=gain, reverb=0.2)


def bass_note(mx, t0, f, dur, gain=0.22):
    """Kare/testere karışımı bas; filtre her notada açılıp kapanır (plak gibi 'pluck')."""
    t = span(dur)
    out = np.zeros_like(t)
    cutoff = 250 + 1600 * np.exp(-t / 0.05)
    for h in range(1, 24):
        amp = (1 / h) * (1.0 if h % 2 else 0.45)
        out += amp * np.sin(TAU * f * h * t) / np.sqrt(1 + (f * h / cutoff) ** 4)
    env = (1 - np.exp(-t / 0.003)) * np.clip((dur - t) / 0.01, 0, 1) * np.exp(-t / (dur * 1.2))
    mx.add(np.tanh(1.5 * peak(out)) * env, t0, gain=gain, reverb=0.02)


def pluck(mx, t0, f, gain=0.05, pan=0.0):
    """Arpej için kısa, parlak testere 'pluck'."""
    t = span(0.22)
    cutoff = 800 + 5000 * np.exp(-t / 0.03)
    out = sum((1 / h) * np.sin(TAU * f * h * t) / np.sqrt(1 + (f * h / cutoff) ** 4) for h in range(1, 14))
    mx.add(peak(out) * (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.08), t0, gain=gain, pan=pan, reverb=0.35)


def chord_bed(mx, t0, dur, notes, rng, gain=0.07):
    """Sürekli akor (sidechain ile kick'e göre pompalanacak)."""
    t = span(dur)
    out = np.zeros((len(t), 2))
    for f in notes:
        for cents, pan in ((-10, -0.6), (10, 0.6)):
            fd = f * 2 ** (cents / 1200)
            saw = sum(np.sin(TAU * fd * h * t + rng.uniform(0, TAU)) / h * np.exp(-h * fd / 2500) for h in range(1, 10))
            p = (pan + 1) * np.pi / 4
            out[:, 0] += saw * np.cos(p)
            out[:, 1] += saw * np.sin(p)
    env = np.clip(t / 0.02, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    mx.add(out / np.abs(out).max() * env[:, None], t0, gain=gain, reverb=0.3)


def sidechain(x, kicks, depth=0.75, release=0.16):
    """Kick anlarında sesi kısıp geri açar (pompalama)."""
    t = np.arange(len(x)) / SR
    g = np.ones(len(x))
    for k in kicks:
        m = (t >= k) & (t < k + 4 * release)
        g[m] = np.minimum(g[m], 1 - depth * np.exp(-(t[m] - k) / release))
    return x * g[:, None]


def synthesize(ev, seed=21):
    """Sahne olaylarından (GlitchScene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    dur = ev["duration"]
    drums, music, sfx = Mixer(dur), Mixer(dur), Mixer(dur)
    B, T0 = ev["beat"], ev["t0"]
    beat = lambda n: T0 + n * B
    g0, g1 = ev["glitch"]
    logo, (s0, s1) = ev["logo"], ev["sweep"]
    n_glitch = round((g0 - T0) / B)            # 6: glitch vuruşu
    n_logo = (logo - T0) / B
    kicks = []

    # ---------- davul ızgarası
    n = 0
    while beat(n) < ev["out"][0]:
        t = beat(n)
        in_glitch = g0 - 0.01 <= t < g1
        pre_logo = s1 - 0.06 <= t < logo
        if not in_glitch and not pre_logo:
            half_time = t >= logo + 0.3
            if not half_time or n % 2 == 0:
                kick(drums, t, gain=0.55 if t < logo else 0.45)
                kicks.append(t)
            if n % 2 == 1 and t < logo + 2 * B:
                clap(drums, t, rng, gain=0.22)
            elif n % 4 == 2 and half_time:
                clap(drums, t, rng, gain=0.16)
            # hi-hat: harflerde sekizlik, karakterlerde 16'lık + açık offbeat
            chars = g1 <= t < s1
            for k in (range(4) if chars else range(2)):
                tt = t + k * B / (4 if chars else 2)
                if half_time and k % 2:
                    continue
                hat(drums, tt, rng, open_=(chars and k == 2), gain=0.05 if k else 0.035,
                    pan=0.3 if k % 2 else -0.2)
        n += 1

    # son harf barında ve süpürmede trampet rulosu (hızlanan)
    for a, b in ((beat(n_glitch - 1), g0), (s0, s1 - 0.06)):
        t, step = a, B / 2
        while t < b - 0.02:
            snare(drums, t, rng, gain=0.07 + 0.12 * (t - a) / (b - a))
            t += step
            step = max(step * 0.8, B / 8)

    # ---------- bas, akor, arpej (bar = 4 vuruş)
    n = 0
    while beat(n) < ev["out"][0] + 0.2:
        t = beat(n)
        if g0 - 0.01 <= t < g1 or s1 - 0.06 <= t < logo:
            n += 1
            continue
        chord = PROG[(n // 4) % 4] if t >= g1 else "Am"
        root, notes = CHORDS[chord]
        chars = g1 <= t < s1
        if t < logo:
            if chars:                                           # 16'lık sürüş basanı
                for k, mult in enumerate((1, 1, 2, 1)):
                    bass_note(music, t + k * B / 4, root * mult, B / 4 * 0.9, gain=0.2)
            else:                                               # offbeat bas
                bass_note(music, t + B / 2, root * 2, B / 2 * 0.8, gain=0.2)
            if n % 4 == 0 and chars:
                chord_bed(music, t, 4 * B, notes, rng, gain=0.06)
            if chars:                                           # arpej
                for k in range(4):
                    pluck(music, t + k * B / 4, notes[(n * 4 + k) % len(notes)] * 2, gain=0.035,
                          pan=-0.4 + 0.8 * (k % 2))
        else:                                                   # logo: yarım tempo, yumuşak
            if n % 2 == 0:
                bass_note(music, t, CHORDS["Am"][0], B * 1.6, gain=0.16)
            pluck(music, t, CHORDS["Am"][1][n % 4] * 4, gain=0.02, pan=0.3 if n % 2 else -0.3)
        n += 1

    # ---------- harfler: panel whoosh + dijital nota + küçük yankı notası
    for i, t0 in enumerate(ev["letters"]):
        pan = -0.3 if i % 2 else 0.3
        whoosh(sfx, t0 - 0.07, t0 + 0.08, rng, f0=500, f1=2600, gain=0.14)
        blip(sfx, t0, LETTER_NOTES[i], gain=0.12, pan=pan)
        blip(sfx, t0 + B / 2, LETTER_NOTES[i] * 2, gain=0.04, pan=-pan, length=0.15)
    riser(sfx, ev["zoom"][0], g0, rng, f0=400, f1=7000, gain=0.2)

    # ---------- glitch geçişi
    glitch_burst(sfx, g0, g1, rng, gain=0.22)
    white_burst(sfx, g1 - 0.02, rng, gain=0.45)

    # ---------- 1. karakter
    a, b = ev["c1_rise"]
    whoosh(sfx, a - 0.03, b, rng, f0=300, f1=3200, pan0=0.4, pan1=0.0, gain=0.34)
    boom(sfx, ev["c1_hit"], rng, gain=0.35)
    chord_stab(sfx, ev["c1_hit"], CHORDS["Am"][1], rng, gain=0.13, length=0.6)
    for k, t in enumerate(ev["c1_flaps"]):
        swish(sfx, t, rng, dur=0.1, fc=2200 + 300 * k, gain=0.14, pan=-0.3 if k % 2 else 0.3)
    thud(sfx, ev["c1_antic"], gain=0.2)
    fall_whoosh(sfx, *ev["c1_fall"], rng, gain=0.26)
    zap(sfx, ev["cut"], rng, gain=0.16)

    # ---------- 2. karakter
    a, b = ev["c2_rise"]
    whoosh(sfx, a, b, rng, f0=280, f1=2800, pan0=-0.5, pan1=0.5, gain=0.32)
    tension(sfx, b - 0.12, b - 0.005, gain=0.1)
    boom(sfx, ev["c2_hit"], rng, gain=0.55)
    chord_stab(sfx, ev["c2_hit"], GOLD_CHORD, rng, gain=0.18)
    sparkle(sfx, ev["c2_hit"] + 0.05, rng, count=24, spread=0.45, gain=0.02)
    thud(sfx, ev["c2_antic"], gain=0.2, pan=0.15)
    fall_whoosh(sfx, *ev["c2_fall"], rng, pan=0.15, gain=0.26)

    # ---------- süpürme ve logo
    for k in range(4):
        t = s0 + k * 0.2 * (s1 - s0) / 1.6
        whoosh(sfx, t, t + 0.2, rng, f0=600, f1=2600, pan0=-0.7, pan1=0.7, gain=0.18)
    riser(sfx, s0 - 0.2, logo - 0.06, rng, f0=500, f1=6000, gain=0.16)
    boom(sfx, logo, rng, gain=0.6)
    chord_stab(sfx, logo, LOGO_CHORD[2:], rng, gain=0.16, length=1.4)
    for k, t0 in enumerate(ev["logo_letters"]):
        tick(sfx, t0, rng, gain=0.06, pan=-0.6 + 1.2 * k / max(len(ev["logo_letters"]) - 1, 1))
    warm_pad(music, logo + 0.05, ev["out"][0], ev["out"][1] + 0.05, LOGO_CHORD, rng, gain=0.13)
    bell(sfx, ev["logo_letters"][-1] + 0.22, 880.0, gain=0.06, rng=rng)
    for k, t in enumerate(ev["shines"]):
        ting(sfx, t + 0.3, gain=0.035 if k == 0 else 0.025, pan=-0.2 + 0.4 * k)
        sparkle(sfx, t + 0.2, rng, count=10, spread=0.3, gain=0.012)
    for t in ev["flickers"]:
        tick(sfx, t, rng, gain=0.03, pan=rng.uniform(-0.5, 0.5))

    # ---------- miks: müzik kick'e göre pompalanır; glitch'te son 16'lık kekeler
    mus = sidechain(music.dry, kicks) + 0.3 * convolve(sidechain(music.send, kicks), reverb_ir(rng, 1.4, 1.0))
    drm = drums.dry + 0.25 * convolve(drums.send, reverb_ir(rng, 1.0, 0.7))
    bed = mus + drm
    i0, i1 = int(g0 * SR), int(g1 * SR)
    seg = bed[int((g0 - B / 4) * SR):i0].copy()
    reps = []
    L = len(seg)
    while sum(len(r) for r in reps) < i1 - i0:
        m = max(int(L * (0.5 ** (len(reps) // 3))), 400)         # tekrar boyu giderek kısalır
        reps.append(seg[:m] * np.linspace(1, 0.6, m)[:, None])
    stut = np.vstack(reps)[: i1 - i0]
    bed[i0:i1] = bitcrush(stut.ravel(), 3, 6).reshape(stut.shape) * 0.8
    fx = sfx.dry + 0.35 * convolve(sfx.send, reverb_ir(rng, length=1.8, rt60=1.2))
    mix = 0.9 * bed + fx
    t = np.arange(len(mix)) / SR
    out = ev["out"]
    fade = np.clip(t / 0.003, 0, 1)
    fade *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - out[0]) / (out[1] + 0.04 - out[0]), 0, 1))
    mix *= fade[:, None]
    mix = np.tanh(1.6 * mix / np.abs(mix).max()) / np.tanh(1.6)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
