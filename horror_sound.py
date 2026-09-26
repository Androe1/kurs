"""Korku teaser'ı - ses tasarımı. Tamamı numpy ile sentezlenir; hazır ses ya da örnek kullanılmaz.

Her ses görüntüdeki olayla aynı anda çalar (zamanlar horror_scene.Scene.events'ten gelir):

  0.00-0.70   karanlık: çok kısık oda uğultusu, derinden gelen bas
  0.70        spot ışık yanar: ağır şalter "klank"ı; lamba vızıltısı titremeyle birlikte kesilip gelir
  0.95-2.35   kan ağır ağır iner: yapışkan sıvının gerilmesi, gurultular
  1.55/2.55   damla kopar; ~0.7 sn sonra çok aşağıdan yankılı "tık" (derinlik hissi)
  2.75-5.05   dönüşüm: tersten yükselen nefes, ıslak çıtırtılar, fısıltılar; yapraklar üç vuruşta
              açılır: her biri kalp atışı gibi (gümm-güm) + ıslak yırtılma + uyumsuz yaylı darbesi
  5.25        iplik kopar: keskin çıt + esnek geri sekme
  5.25-8.35   süzülme: gülün hızına göre hışırdayan, gülle birlikte sağa sola gezen hava; kalp
              atışı hızlanır; gülden kopan damlalar kana düşer
  8.35        gül kana değer: derin BRAAM, alt frekans patlaması, sıçrama, taç damlacıkları,
              yayılan halkaların ürpertici parıltısı; kopan yapraklar ve inişleri
  9.30        ışık titrer (elektrik cızırtısı)
  9.85-10.95  kamera yukarı bakar: yükselen gerilim, hızlanan kalp, ışık söner
  10.95       kesme: ölü sessizlik
  11.15       kapalı gözler belirir: derin hırıltı, içe çekilen nefes
  11.45       seğirme: ıslak tık
  11.75       gözler açılır: dev vuruş (uyumsuz akor kümesi, metal çığlık, alt patlama, ıslak kapak)
  12.95       kesme: sessizlik
  13.15       COMING SOON: derin vuruş, metalik çınlama, karanlık uğultu; sonda söner
"""
import numpy as np

from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span, sweep_band


# ---------------------------------------------------------------- yardımcılar

def env_ad(t, attack, decay):
    return (1 - np.exp(-t / max(attack, 1e-4))) * np.exp(-t / decay)


def fade(t, t0, t1):
    return np.clip((t - t0) / max(t1 - t0, 1e-6), 0, 1)


def additive(freq, dur, bright, t_bright=None, n_max=60, rng=None, jitter=0.0):
    """Testere benzeri ton: harmonikler 1/k, parlaklık (Hz) üstündekiler söner; parlaklık zamanla değişebilir.
    freq: sabit ya da zaman dizisi (Hz)."""
    t = span(dur)
    f = np.broadcast_to(np.asarray(freq, float), t.shape)
    if jitter and rng is not None:
        f = f * (1 + jitter * band(rng.standard_normal(len(t)), hi=6))
    ph = glide(f)
    br = np.broadcast_to(np.asarray(bright if t_bright is None else t_bright, float), t.shape)
    out = np.zeros(len(t))
    f0 = float(np.mean(f))
    for k in range(1, n_max + 1):
        if k * f0 > 0.45 * SR:
            break
        amp = np.exp(-k * f / br) / k
        out += amp * np.sin(k * ph + (rng.uniform(0, TAU) if rng is not None else 0.0))
    return out


def bowed(f, dur, rng, bright=2500.0, vib=0.004, voices=3, cents=7.0):
    """Yaylı çalgı: birkaç hafif akort farklı ses, vibrato ve yay hışırtısı."""
    t = span(dur)
    out = np.zeros(len(t))
    for v in range(voices):
        det = 2 ** ((v - (voices - 1) / 2) * cents / 1200)
        fv = f * det * (1 + vib * np.sin(TAU * rng.uniform(4.8, 5.8) * t + rng.uniform(0, TAU)))
        out += additive(fv, dur, bright, n_max=40, rng=rng)
    bow = band(rng.standard_normal(len(t)), lo=f * 2, hi=min(f * 12, 9000)) * 0.08
    return out / voices + bow


def pan_const(sig, pan):
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([sig * np.cos(p), sig * np.sin(p)], -1)


def pan_dynamic(sig, pan):
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([sig * np.cos(p), sig * np.sin(p)], -1)


def at(curve_t, curve_v, t):
    return np.interp(t, curve_t, curve_v)


# ---------------------------------------------------------------- ses öğeleri

def room_tone(mx, dur, rng, cuts):
    """Karanlık odanın çok kısık uğultusu (kesmelerde susar)."""
    t = span(dur)
    low = peak(band(rng.standard_normal(len(t)), lo=35, hi=320))
    air = peak(band(rng.standard_normal(len(t)), lo=1800, hi=6500))
    g = fade(t, 0.0, 0.6)
    for a, b in cuts:
        g = g * (1 - ((t >= a) & (t < b)))
    sig = (0.55 * low + 0.12 * air) * g
    mx.add(np.stack([sig, np.roll(sig, 2400)], -1), 0.0, gain=0.035)


def sub_drone(mx, t0, t1, rng, swells):
    """Derinden bas: iki yakın sesin vuruşan titreşimi, yavaş nefes alan filtre."""
    dur = t1 - t0
    t = span(dur)
    a = np.sin(TAU * 36.7 * t) + 0.8 * np.sin(TAU * 38.9 * t + 1.0)
    body = additive(55.0, dur, 160 + 90 * np.sin(TAU * 0.13 * t) ** 2, n_max=8, rng=rng)
    body += additive(58.27, dur, 150, n_max=8, rng=rng)
    env = fade(t, 0.0, 1.2) * np.clip((dur - t) / 0.02, 0, 1)
    lvl = np.full_like(t, 0.55)
    for c, w, g in swells:
        lvl += g * np.exp(-((t0 + t - c) / w) ** 2)
    sig = (0.7 * a + 0.45 * peak(body)) * env * lvl
    mx.add(np.stack([sig, sig], -1), t0, gain=0.17, reverb=0.05)


def clunk(mx, t0, rng, gain=0.5):
    """Ağır şalter / projektör açılması: metalik tık, gövde vuruşu, kısa çınlama."""
    t = span(1.2)
    n = rng.standard_normal(len(t))
    click = peak(band(n, lo=900, hi=4500)) * np.exp(-t / 0.012)
    thump = np.sin(glide(70 + 60 * np.exp(-t / 0.03))) * env_ad(t, 0.002, 0.12)
    ring = sum(np.sin(TAU * f * t + rng.uniform(0, TAU)) * np.exp(-t / d) * a
               for f, d, a in ((1210, 0.25, 1.0), (2870, 0.14, 0.6), (4310, 0.08, 0.35)))
    mx.add(0.8 * click + 1.0 * thump + 0.12 * ring, t0, gain=gain, reverb=0.35)


def lamp_buzz(mx, light, rng, gain=0.05):
    """Lamba vızıltısı: 50 Hz ve harmonikleri + yüksek cızırtı; ışığın titremesiyle kesilip gelir."""
    lt, lg = light
    dur = lt[-1]
    t = span(dur)
    g = np.interp(t, lt, lg)
    hum = sum(np.sin(TAU * 50 * k * t) / k ** 0.7 for k in range(1, 12))
    saw = additive(100.0, dur, 4000, n_max=40, rng=rng)
    fizz = band(saw, lo=1800, hi=5000)
    sig = (0.6 * peak(hum) + 0.4 * peak(fizz)) * np.clip(g, 0, 1.2)
    # ışık hızla değişirken elektrik çıtırtıları
    dg = np.abs(np.gradient(g)) * SR
    crack = rng.standard_normal(len(t)) * np.clip(dg / 40.0, 0, 1)
    sig += 0.8 * band(crack, lo=1500, hi=9000)
    mx.add(np.stack([sig, sig * 0.9], -1), 0.0, gain=gain, reverb=0.15)


def ooze(mx, t0, t1, rng, gain=0.09):
    """Yapışkan kanın gerilerek inmesi: rezonanslı gurultu, ıslak kabarcıklar, gerilme tonu."""
    dur = t1 - t0
    t = span(dur)
    fc = 180 + 140 * (0.5 + 0.5 * np.sin(TAU * 0.7 * t + 1.3)) + 80 * band(rng.standard_normal(len(t)), hi=3)
    creak = sweep_band(rng.standard_normal(len(t)), fc, 6.0)
    env = fade(t, 0.0, 0.3) * np.clip((dur - t) / 0.5, 0, 1)
    mx.add(peak(creak) * env, t0, gain=gain, pan=-0.1, reverb=0.2)
    tone = np.sin(glide(88 + 6 * np.sin(TAU * 0.9 * t))) * env * 0.5
    mx.add(tone, t0, gain=gain * 0.6, reverb=0.1)
    tb = span(0.08)
    for _ in range(7):
        dt = rng.uniform(0.1, dur - 0.2)
        f0 = rng.uniform(120, 220)
        blob = np.sin(glide(f0 * (1 + 0.5 * (tb / 0.08) ** 0.6))) * env_ad(tb, 0.004, 0.025)
        blob = band(blob + 0.3 * rng.standard_normal(len(tb)) * np.exp(-tb / 0.01), hi=1200)
        mx.add(blob, t0 + dt, gain=gain * 0.6, pan=rng.uniform(-0.3, 0.3), reverb=0.25)


def plink(freq, dur=0.5, rise=1.8, decay=0.07):
    """Damla sesi: rezonans frekansı hızla yükselen kısa sinüs (kabarcık) + tık."""
    t = span(dur)
    s = np.sin(glide(freq * (1 + (rise - 1) * (1 - np.exp(-t / 0.018))))) * env_ad(t, 0.0015, decay)
    s += 0.25 * np.sin(TAU * 4 * freq * t) * np.exp(-t / 0.004)
    return s


def far_drip(mx, t0, x, rng, cave_ir, gain=0.22):
    """Çok aşağıda, karanlığa düşen damla: boğuk, mağara gibi uzun yankılı."""
    s = band(plink(rng.uniform(650, 900), dur=0.6, rise=1.6, decay=0.09), hi=2500)
    pad = np.concatenate([s, np.zeros(len(cave_ir))])
    st = np.stack([pad, pad], -1)
    sig = 0.25 * st + 1.4 * convolve(st, cave_ir)
    p = (np.clip(x * 1.5, -0.7, 0.7) + 1) * np.pi / 4
    mx.add(sig * np.array([np.cos(p), np.sin(p)]), t0, gain=gain)


def near_drip(mx, t0, x, rng, gain=0.2, big=1.0):
    s = plink(rng.uniform(900, 1400) / big, dur=0.5, rise=1.9, decay=0.06 * big)
    mx.add(s, t0, gain=gain, pan=np.clip(x * 1.6, -0.8, 0.8), reverb=0.4)


def tick(mx, t0, rng, gain=0.1, pan=0.0):
    t = span(0.05)
    s = band(rng.standard_normal(len(t)), lo=2500, hi=9000) * np.exp(-t / 0.004)
    mx.add(peak(s), t0, gain=gain, pan=pan, reverb=0.3)


def reverse_swell(mx, t0, t1, rng, gain=0.3, lo=300, hi=6000):
    """Tersten yükselen nefes / zil: sona doğru hızla büyüyüp aniden biter."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    n = np.stack([band(rng.standard_normal(len(t)), lo=lo, hi=hi) for _ in range(2)], -1)
    env = (np.exp(4.0 * u) - 1) / (np.e ** 4 - 1)
    bellish = sum(np.sin(TAU * f * t) * a for f, a in ((523.3, 1.0), (1107.0, 0.5), (1661.0, 0.3)))
    sig = n / np.abs(n).max() * env[:, None] + 0.35 * (bellish * env ** 2)[:, None] / 1.8
    sig *= np.clip((dur - t) / 0.004, 0, 1)[:, None]
    mx.add(sig, t0, gain=gain, reverb=0.4)


def wet_crackle(mx, t0, rng, gain=0.12, n=14, spread=0.18, pan=0.0):
    """Islak çıtırtı: dokunun yırtılması / yaprağın sıvıdan ayrılması."""
    tt = span(0.03)
    for _ in range(n):
        dt = rng.exponential(spread / 3)
        f = rng.uniform(800, 4200)
        g = band(rng.standard_normal(len(tt)), lo=f * 0.6, hi=f * 1.5) * np.exp(-tt / rng.uniform(0.002, 0.008))
        mx.add(peak(g) * rng.uniform(0.3, 1.0), t0 + min(dt, spread * 2), gain=gain,
               pan=np.clip(pan + rng.uniform(-0.4, 0.4), -1, 1), reverb=0.25)


def squelch(mx, t0, rng, gain=0.25, dur=0.25, pan=0.0):
    """Islak, yapışkan ses: rezonansı hızla kayan gürültü (göz kapağı / sıvıdan biçimlenme)."""
    t = span(dur)
    fc = 500 * np.exp(1.6 * np.sin(np.pi * t / dur)) * (1 + 0.3 * np.sin(TAU * 23 * t))
    s = sweep_band(rng.standard_normal(len(t)), fc, 5.0)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    mx.add(peak(s) * env, t0, gain=gain, pan=pan, reverb=0.2)


def whispers(mx, t0, t1, rng, gain=0.06):
    """Hece gibi kesik kesik fısıltılar (formant süzgeçli gürültü), iki yanda gezinir, bol yankılı."""
    formants = ((700, 1200), (400, 2200), (300, 900), (600, 1000), (500, 1800))
    t_cur = t0
    side = -1
    while t_cur < t1 - 0.2:
        d = rng.uniform(0.12, 0.3)
        t = span(d)
        n = rng.standard_normal(len(t))
        f1, f2 = formants[rng.integers(len(formants))]
        s = band(n, lo=f1 * 0.8, hi=f1 * 1.25) + 0.7 * band(n, lo=f2 * 0.85, hi=f2 * 1.2) + 0.3 * band(n, lo=3500, hi=7000)
        env = np.sin(np.pi * t / d) ** 1.5 * (0.6 + 0.4 * np.sin(TAU * rng.uniform(5, 9) * t))
        mx.add(peak(s) * env, t_cur, gain=gain * rng.uniform(0.5, 1.0), pan=side * rng.uniform(0.4, 0.9), reverb=0.7)
        side = -side
        t_cur += d + rng.uniform(0.02, 0.18)


def heartbeat(mx, t0, gain=0.5, pitch=1.0):
    """Kalp atışı: gümm-güm (iki boğuk vuruş)."""
    t = span(0.6)
    lub = np.sin(glide(pitch * (48 + 30 * np.exp(-t / 0.03)))) * env_ad(t, 0.004, 0.09)
    t2 = np.clip(t - 0.17, 0, None)
    dub = np.sin(glide(pitch * (60 + 28 * np.exp(-t2 / 0.025)))) * env_ad(t2, 0.004, 0.07) * (t >= 0.17)
    s = np.tanh(1.8 * (lub + 0.75 * dub))
    mx.add(s, t0, gain=gain, reverb=0.08)


def string_cluster(mx, t0, dur, notes, rng, gain=0.12, attack=0.8, release=0.4, bright=2200.0, pan_spread=0.6,
                   crescendo=True, tremolo=0.0):
    """Uyumsuz yaylı küme: yavaş girer, (istenirse) giderek büyür, titreyebilir."""
    t = span(dur)
    for i, f in enumerate(notes):
        s = bowed(f, dur, rng, bright=bright)
        env = fade(t, 0, attack) * np.clip((dur - t) / release, 0, 1)
        if crescendo:
            env *= 0.35 + 0.65 * (t / dur) ** 1.6
        if tremolo:
            env *= 0.6 + 0.4 * np.sin(TAU * tremolo * t + rng.uniform(0, TAU)) ** 2
        pan = (i / max(len(notes) - 1, 1) - 0.5) * 2 * pan_spread
        mx.add(peak(s) * env, t0, gain=gain / len(notes) ** 0.5, pan=pan, reverb=0.45)


def string_stab(mx, t0, notes, rng, gain=0.25, dur=0.9):
    """Kısa, sert yaylı darbe (sforzando)."""
    t = span(dur)
    for i, f in enumerate(notes):
        s = bowed(f, dur, rng, bright=3500)
        env = env_ad(t, 0.006, 0.25) + 0.25 * np.exp(-t / 0.6)
        mx.add(np.tanh(1.5 * peak(s)) * env, t0, gain=gain / len(notes) ** 0.5,
               pan=(i / max(len(notes) - 1, 1) - 0.5) * 1.2, reverb=0.4)


def snap_thread(mx, t0, rng, gain=0.35):
    """İplik kopar: keskin çıt + geri sekmenin esnek 'tıwww'u + küçük ıslak şap."""
    t = span(0.5)
    crack = band(rng.standard_normal(len(t)), lo=2000, hi=10000) * np.exp(-t / 0.003)
    twang = np.sin(glide(950 * np.exp(-t / 0.08) + 220)) * env_ad(t, 0.001, 0.12) * (1 + 0.3 * np.sin(TAU * 38 * t))
    mx.add(0.9 * peak(crack) + 0.45 * twang, t0, gain=gain, reverb=0.35)
    squelch(mx, t0 + 0.02, rng, gain=gain * 0.4, dur=0.12)


def flutter_air(mx, fall, rng, gain=0.26):
    """Süzülen gülün havası: hızına göre açılan, gülle birlikte sağa sola gezen hışırtı."""
    ts, vel, xs, bank = fall
    t0, t1 = ts[0], ts[-1]
    t = span(t1 - t0)
    v = np.interp(t0 + t, ts, vel)
    x = np.interp(t0 + t, ts, xs)
    b = np.interp(t0 + t, ts, bank)
    vn = v / max(vel.max(), 1e-6)
    # dönüş noktalarında (yatış açısı en büyükken) kısa "hışşt"lar
    fc = 350 + 1500 * vn ** 1.3 + 500 * np.abs(np.gradient(b) * SR)
    left = sweep_band(rng.standard_normal(len(t)), fc, 1.4)
    right = sweep_band(rng.standard_normal(len(t)), fc * 1.07, 1.4)
    amp = vn ** 1.6
    pan = np.clip(x * 2.2, -0.9, 0.9)
    p = (pan + 1) * np.pi / 4
    sig = np.stack([left / np.abs(left).max() * np.cos(p), right / np.abs(right).max() * np.sin(p)], -1)
    sig *= amp[:, None] * np.clip((t1 - t0 - t) / 0.3, 0, 1)[:, None]
    mx.add(sig, t0, gain=gain, reverb=0.25)


def braam(mx, t0, rng, gain=0.55, dur=3.2, root=55.0):
    """Sinema fragmanı 'BRAAM'ı: akort farklı testere kümesi, parlaklığı hızla kapanan süzgeç, bozulma."""
    t = span(dur)
    bright = 180 + 2600 * np.exp(-t / 0.35)
    out = np.zeros(len(t))
    for f in (root, root * 1.498, root * 2.0, root * 2.0 * 1.012, root * 0.5):
        out += additive(f * (1 - 0.01 * np.exp(-t / 0.2)), dur, bright, n_max=70, rng=rng, jitter=0.002)
    env = env_ad(t, 0.012, 1.3)
    sig = np.tanh(2.2 * peak(out) * env)
    mx.add(np.stack([sig, np.roll(sig, 31)], -1), t0, gain=gain, reverb=0.45)


def sub_boom(mx, t0, gain=0.7, f0=62.0, f1=27.0, dur=1.6):
    t = span(dur)
    s = np.sin(glide(f1 + (f0 - f1) * np.exp(-t / 0.25))) * env_ad(t, 0.004, 0.55)
    mx.add(np.tanh(1.4 * s), t0, gain=gain, reverb=0.1)


def splash(mx, t0, x, rng, gain=0.4):
    """Sıvıya düşüş: gürültü patlaması + kabarcık cıvıltıları."""
    t = span(0.8)
    burst = band(rng.standard_normal(len(t)), lo=400, hi=5000) * env_ad(t, 0.002, 0.07)
    mx.add(peak(burst), t0, gain=gain, pan=np.clip(x * 1.4, -0.7, 0.7), reverb=0.35)
    for _ in range(12):
        dt = rng.uniform(0.0, 0.35)
        s = plink(rng.uniform(500, 1600), dur=0.3, rise=1.9, decay=rng.uniform(0.02, 0.05))
        mx.add(s, t0 + dt, gain=gain * 0.35 * rng.uniform(0.4, 1), pan=np.clip(x * 1.4 + rng.uniform(-0.4, 0.4), -1, 1),
               reverb=0.35)


def ripple_shimmer(mx, t0, dur, rng, gain=0.07):
    """Yayılan halkaların ürpertici parıltısı: aşağı kayan titrek yüksek tonlar."""
    t = span(dur)
    out = np.zeros((len(t), 2))
    for i, f in enumerate((2093.0, 2489.0, 2960.0, 3520.0, 4186.0)):
        s = np.sin(glide(f * (1 - 0.12 * t / dur) * (1 + 0.004 * np.sin(TAU * 6 * t + i)))) \
            * (0.5 + 0.5 * np.sin(TAU * (3 + i) * t + i)) * np.exp(-t / (dur * 0.35)) * fade(t, 0, 0.05)
        out += pan_const(s, (i - 2) * 0.35)
    mx.add(out / 5, t0, gain=gain, reverb=0.7)


def riser(mx, t0, t1, rng, gain=0.3):
    """Kamera yukarı bakarken yükselen gerilim: yukarı kayan uyumsuz tonlar + gürültü süpürmesi; keskin biter."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    out = np.zeros(len(t))
    for f in (220.0, 233.1, 311.1, 329.6):
        out += np.sin(glide(f * 2 ** (1.6 * u ** 1.4)) + np.sin(TAU * 7 * t) * 0.3)
    noise = sweep_band(rng.standard_normal(len(t)), 400 * 12 ** u, 2.0)
    env = u ** 2.2 * np.clip((dur - t) / 0.004, 0, 1)
    sig = (0.6 * peak(out) + 0.5 * peak(noise)) * env
    mx.add(np.stack([sig, np.roll(sig, 17)], -1), t0, gain=gain, reverb=0.25)


def growl(mx, t0, dur, rng, gain=0.2):
    """Karanlıkta derin, boğazdan gelen hırıltı: düzensiz alt frekans darbeleri, formant süzgeci."""
    t = span(dur)
    wob = band(rng.standard_normal(len(t)), hi=4)
    f = 42 + 8 * wob / (np.abs(wob).max() + 1e-9)
    ph = glide(f)
    pulses = np.maximum(np.sin(ph), 0) ** 8
    src = pulses + 0.15 * rng.standard_normal(len(t)) * pulses
    s = band(src, lo=60, hi=700) + 0.6 * band(src, lo=900, hi=1400)
    env = fade(t, 0, 0.5) * np.clip((dur - t) / 0.08, 0, 1)
    mx.add(peak(s) * env, t0, gain=gain, reverb=0.35)


def breath_in(mx, t0, dur, rng, gain=0.12):
    t = span(dur)
    s = band(rng.standard_normal(len(t)), lo=500, hi=3000) + 0.4 * band(rng.standard_normal(len(t)), lo=3000, hi=7000)
    env = (t / dur) ** 1.5 * np.clip((dur - t) / 0.05, 0, 1)
    mx.add(np.stack([peak(s) * env, peak(np.roll(s, 99)) * env], -1), t0, gain=gain, reverb=0.4)


def screech(mx, t0, rng, gain=0.3, dur=1.4):
    """Metal çığlık: uyumsuz kısmilerin aşağı kayması ve titremesi."""
    t = span(dur)
    out = np.zeros(len(t))
    for r, a in ((1.0, 1.0), (1.414, 0.7), (2.23, 0.5), (2.97, 0.35), (4.1, 0.2)):
        f = 1650 * r * (1 - 0.35 * (1 - np.exp(-t / 0.4))) * (1 + 0.012 * np.sin(TAU * 13 * t))
        out += a * np.sin(glide(f) + rng.uniform(0, TAU))
    env = env_ad(t, 0.01, 0.45) * (0.7 + 0.3 * np.sin(TAU * 17 * t))
    s = np.tanh(1.6 * out / 2.8) * env
    mx.add(np.stack([s, np.roll(s, 41)], -1), t0, gain=gain, reverb=0.5)


def eyes_stinger(mx, t0, rng):
    """Gözler açılınca: dev vuruş katmanları."""
    cluster = [130.8, 138.6, 185.0, 196.0, 261.6, 277.2, 370.0, 392.0, 523.3, 554.4]
    string_stab(mx, t0, cluster, rng, gain=0.5, dur=1.8)
    screech(mx, t0 + 0.01, rng, gain=0.24)
    sub_boom(mx, t0, gain=0.8, f0=70, f1=24, dur=2.2)
    braam(mx, t0, rng, gain=0.35, dur=2.4, root=43.65)
    t = span(0.4)
    burst = band(rng.standard_normal(len(t)), lo=300, hi=9000) * env_ad(t, 0.001, 0.05)
    mx.add(np.stack([peak(burst), peak(np.roll(burst, 7))], -1), t0, gain=0.35, reverb=0.5)
    squelch(mx, t0 - 0.01, rng, gain=0.3, dur=0.18)


def rumble(mx, t0, dur, rng, gain=0.25):
    """Sarsıntı gürlemesi: alçak gürültü, zamanla söner."""
    t = span(dur)
    s = band(rng.standard_normal(len(t)), lo=25, hi=160)
    env = np.exp(-t / (dur * 0.45)) * np.clip((dur - t) / 0.02, 0, 1)
    mx.add(np.stack([peak(s) * env, peak(np.roll(s, 500)) * env], -1), t0, gain=gain, reverb=0.1)


def title_hit(mx, t0, rng):
    """COMING SOON: derin vuruş, metalik çınlama ve karanlık uğultu."""
    sub_boom(mx, t0, gain=0.75, f0=58, f1=26, dur=2.4)
    braam(mx, t0, rng, gain=0.3, dur=2.6, root=41.2)
    t = span(4.0)
    ring = sum(a * np.sin(TAU * f * t + rng.uniform(0, TAU)) * np.exp(-t / d)
               for f, a, d in ((196.0, 1.0, 2.2), (311.1, 0.6, 1.6), (466.2, 0.45, 1.2),
                               (740.0, 0.3, 0.8), (1175.0, 0.2, 0.5), (1864.0, 0.1, 0.3)))
    mx.add(np.stack([ring, np.roll(ring, 60)], -1) / 2.6, t0, gain=0.16, reverb=0.7)
    t = span(1.9)
    drone = additive(55.0, 1.9, 300, n_max=12, rng=rng) + additive(82.41, 1.9, 280, n_max=10, rng=rng)
    env = fade(t, 0, 0.1) * np.clip((1.9 - t) / 0.6, 0, 1)
    mx.add(peak(drone) * env, t0, gain=0.14, reverb=0.3)


def title_flicker(mx, t0, dur, rng, gain=0.1):
    """Yazı titrerken elektrik cızırtısı."""
    t = span(dur)
    s = band(rng.standard_normal(len(t)), lo=1200, hi=7000) * (rng.random(len(t)) < 0.3)
    buzz = np.sign(np.sin(TAU * 100 * t)) * 0.3
    env = (np.sin(TAU * 24 * t) > 0) * np.clip((dur - t) / 0.02, 0, 1)
    mx.add((0.7 * s + buzz) * env, t0, gain=gain, reverb=0.2)


# ---------------------------------------------------------------- miks

def synthesize(ev, seed=13):
    """Sahne olaylarından stereo ses: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    dur = ev["duration"]
    mx = Mixer(dur)
    cave_ir = reverb_ir(np.random.default_rng(seed + 1), length=3.2, rt60=3.0) * 0.35

    land, eyes, cut, title = ev["land"], ev["eyes"], ev["cut"], ev["title"]
    dark = ev["dark"]

    # zemin
    room_tone(mx, dur, rng, cuts=[(dark, ev["eyes_show"]), (cut, title)])
    sub_drone(mx, 0.15, dark, rng, swells=[(4.0, 1.2, 0.35), (7.6, 1.0, 0.4), (10.4, 0.5, 0.5)])

    # ışık
    clunk(mx, ev["light_on"], rng, gain=0.5)
    lamp_buzz(mx, ev["light"], rng, gain=0.03)
    tick(mx, ev["flicker"], rng, gain=0.12, pan=0.3)
    tick(mx, ev["flicker"] + 0.09, rng, gain=0.09, pan=0.25)
    clunk(mx, ev["light_off"], rng, gain=0.3)

    # kan iner, damlalar
    ooze(mx, ev["ooze"][0], ev["ooze"][1] + 0.4, rng)
    for tr in ev["drips_release"]:
        tick(mx, tr, rng, gain=0.06)
    for th, x in ev["drip_hits"]:
        if th < ev["snap"]:
            far_drip(mx, th, x, rng, cave_ir)
        else:
            near_drip(mx, th, x, rng, gain=0.18)

    # dönüşüm
    reverse_swell(mx, ev["morph"][0] - 0.45, ev["bud"], rng, gain=0.28)
    squelch(mx, ev["bud"], rng, gain=0.3, dur=0.35)
    wet_crackle(mx, ev["bud"], rng, gain=0.1, n=20, spread=0.3)
    whispers(mx, ev["morph"][0], ev["snap"], rng, gain=0.05)
    for to in ev["petal_opens"]:
        wet_crackle(mx, to, rng, gain=0.05, n=4, spread=0.06, pan=rng.uniform(-0.5, 0.5))
    stab_notes = [[164.8, 174.6, 246.9], [155.6, 164.8, 233.1, 246.9], [146.8, 155.6, 220.0, 233.1, 311.1]]
    for i, tb in enumerate(ev["bloom_beats"]):
        heartbeat(mx, tb - 0.02, gain=0.55 + 0.1 * i)
        wet_crackle(mx, tb, rng, gain=0.14, n=12, spread=0.15)
        string_stab(mx, tb, stab_notes[i], rng, gain=0.16 + 0.05 * i, dur=0.7)
    string_cluster(mx, ev["morph"][0] - 0.2, ev["snap"] - ev["morph"][0] + 0.25,
                   [164.8, 174.6, 246.9, 261.6], rng, gain=0.07, attack=1.2, release=0.05, bright=1800)

    # kopma ve süzülme
    snap_thread(mx, ev["snap"], rng)
    flutter_air(mx, ev["fall"], rng)
    string_cluster(mx, ev["snap"] + 0.1, land - ev["snap"] - 0.1, [659.3, 698.5, 987.8], rng, gain=0.05,
                   attack=0.6, release=0.03, bright=4000, tremolo=6.5)
    string_cluster(mx, ev["snap"], land - ev["snap"], [65.41, 69.3], rng, gain=0.06, attack=0.5,
                   release=0.03, bright=600)
    for tb in (5.75, 6.55, 7.25, 7.8):
        heartbeat(mx, tb, gain=0.45)

    # iniş
    lx = ev["land_x"]
    braam(mx, land, rng, gain=0.55)
    sub_boom(mx, land, gain=0.75)
    splash(mx, land, lx, rng, gain=0.42)
    for tc, x in ev["crown"]:
        near_drip(mx, tc, x, rng, gain=0.06, big=0.8)
    ripple_shimmer(mx, land + 0.05, 2.2, rng)
    for td, x in ev["petal_detach"]:
        t = span(0.25)
        flap = band(rng.standard_normal(len(t)), lo=600, hi=3000) * np.sin(np.pi * t / 0.25) ** 2
        mx.add(peak(flap), td, gain=0.06, pan=np.clip(x * 1.6, -0.8, 0.8), reverb=0.3)
    for tl, x in ev["petal_land"]:
        near_drip(mx, tl, x, rng, gain=0.12, big=1.6)

    # kamera yukarı, karanlık
    riser(mx, ev["tilt"][0], dark, rng, gain=0.32)
    for tb in (9.95, 10.3, 10.57, 10.78):
        heartbeat(mx, tb, gain=0.5, pitch=1.05)
    string_cluster(mx, ev["tilt"][0], dark - ev["tilt"][0], [440.0, 466.2, 622.3, 659.3], rng, gain=0.09,
                   attack=0.5, release=0.004, bright=5000, tremolo=11.0)

    # gözler
    growl(mx, ev["eyes_show"], eyes - ev["eyes_show"] + 0.2, rng, gain=0.22)
    breath_in(mx, ev["eyes_show"] + 0.1, eyes - ev["eyes_show"] - 0.1, rng, gain=0.12)
    squelch(mx, ev["twitch"] + 0.02, rng, gain=0.12, dur=0.1)
    eyes_stinger(mx, eyes, rng)
    rumble(mx, eyes, cut - eyes, rng, gain=0.28)
    string_cluster(mx, eyes + 0.15, cut - eyes - 0.15, [1046.5, 1108.7, 1480.0], rng, gain=0.06,
                   attack=0.3, release=0.004, bright=6000, tremolo=14.0, crescendo=False)
    reverse_swell(mx, cut - 0.35, cut, rng, gain=0.18, lo=200, hi=3000)

    # başlık
    title_hit(mx, title, rng)
    title_flicker(mx, title, 0.22, rng)
    title_flicker(mx, title + 0.88, 0.07, rng)

    mix = mx.dry + 0.35 * convolve(mx.send, reverb_ir(rng, length=3.0, rt60=2.6))

    # kesmeler: ölü sessizlik (yankı da kesilir), sonda sönme
    t = np.arange(len(mix)) / SR
    g = np.ones(len(t))
    for a, b in ((dark, ev["eyes_show"]), (cut, title)):
        g *= 1 - (np.clip((t - a) / 0.012, 0, 1) * np.clip((b - 0.004 - t) / 0.004, 0, 1))
    e0, e1 = ev["end_fade"]
    g *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - e0) / (e1 - e0), 0, 1))
    g *= np.clip(t / 0.01, 0, 1)
    mix *= g[:, None]

    mix = np.tanh(1.25 * mix / np.abs(mix).max()) / np.tanh(1.25)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
