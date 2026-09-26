"""Korku teaser'ı - ses tasarımı. Tamamı numpy ile sentezlenir; hazır ses ya da örnek kullanılmaz.

Palet karanlık ve boğuktur (korku fragmanı dili): uğuldayan rüzgar, derin drone, içeriden duyulan
kalp atışı, mağarada yankılanan ağır damlalar, ters yankılı fısıltılar, hırıltı, alçak geçiren
süzgeçten geçmiş ağır vuruşlar (sub drop + braam). Tiz, tonal, "şirin" ses yoktur: damla
"bloop"u, zil, çınlama, parıltı kullanılmaz. Gerilimi sürekli yüksek ses değil dinamik kontrast
taşır: büyük vuruşlardan önce kesme ve ölü sessizlik; atmosfer yatağı vuruşların altında kısılır.

Telefon hoparlörü 150 Hz altını çalamaz; bu yüzden alt frekanslı her vuruş hafifçe doyurulur
(harmonikleri 100-400 Hz'e taşınır) ki kulaklıksız da duyulsun.

Her ses görüntüdeki olayla aynı anda çalar (zamanlar horror_scene.Scene.events'ten gelir):

  0.00        karanlık: uzaktan esen boğuk rüzgar, derinden uğultu, tek kalp atışı
  0.70        spot ışık: büyük boş bir salonda yankılanan ağır "tuum"; titremeyle kesilen alçak vızıltı
  0.95-2.75   kan iner: yapışkan, alçak gıcırtılar; damlalar aşağıda, karanlıkta derinden yankılanır
  2.75-5.05   dönüşüm: içe çekilen ters yankı, ters çevrilmiş fısıltılar, ıslak et sesleri; üç açılma
              vuruşu boğuk kalp atışı gibi; koyu, uyumsuz çello kümesi büyür
  5.05-5.25   iplik gerilir (sıklaşan gıcırtı), kopar: boğuk "tok"
  5.25-8.35   süzülme: gülün hızıyla açılan, onunla sağa sola gezen rüzgar; kalp hızlanır
  8.35        kana değme: derin boğuk patlama + karanlık braam + ağır sıçrama, yayılan dalganın uğultusu
  9.35/10.38  gözlerin bilinçaltı göründüğü karelerde ters fısıltı ve elektrik çatırtısı
  9.85-10.95  kamera yukarı: karanlık yükselen gerilim, hızlanan kalp -> keskin kesme, ölü sessizlik
  11.15       kapalı gözler: hırıltı, yavaş nefes, gözlere doğru kabaran ters yankı
  11.75       gözler açılır: sub drop, bozulmuş braam, alçak metal sürtünmesi, boğuk çığlık dokusu
  12.3-12.95  sarsıntı büyür: kükreyen gürültü, gürleme, hızlanan kalp -> kesme, sessizlik
  13.15       COMING SOON: en büyük vuruş, uzun karanlık kuyruk, rüzgar geri gelir; son bir kalp atışı
"""
import numpy as np
from scipy.ndimage import maximum_filter1d

from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span, sweep_band


# ---------------------------------------------------------------- yardımcılar

def env_ad(t, attack, decay):
    return (1 - np.exp(-t / max(attack, 1e-4))) * np.exp(-t / decay)


def fade(t, t0, t1):
    return np.clip((t - t0) / max(t1 - t0, 1e-6), 0, 1)


def tail(t, dur, release):
    """Sonda kısa kapanış (kesik 'tık' olmasın)."""
    return np.clip((dur - t) / release, 0, 1)


def lowpass(x, hi, order=2):
    return band(x, hi=hi, order=order)


def slow_noise(n, rate, rng):
    """Yavaşça gezinen rastgele eğri (0..1): esinti, süzgeç gezinmesi."""
    x = band(rng.standard_normal(n), hi=rate, order=4)
    return (x - x.min()) / (np.ptp(x) + 1e-12)


def pan(sig, p):
    """Sabit güçte stereo konum; p sabit ya da zaman dizisi (-1 sol, +1 sağ)."""
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([sig * np.cos(a), sig * np.sin(a)], -1)


def wide(sig, delay=0.0):
    """Mono sesi sağ kanalı hafif geciktirerek iki kanala yay."""
    d = int(delay * SR)
    right = np.concatenate([np.zeros(d), sig[:len(sig) - d]]) if d else sig
    return np.stack([sig, right], -1)


def additive(freq, dur, bright, n_max=40, rng=None):
    """Testere benzeri ton: harmonikler 1/k, 'bright' (Hz) üstündekiler söner. freq/bright dizi olabilir."""
    t = span(dur)
    f = np.broadcast_to(np.asarray(freq, float), t.shape)
    ph = glide(f)
    br = np.broadcast_to(np.asarray(bright, float), t.shape)
    out = np.zeros(len(t))
    f_top = float(np.max(f))
    for k in range(1, n_max + 1):
        if k * f_top > 0.45 * SR:
            break
        out += np.exp(-k * f / br) / k * np.sin(k * ph + (rng.uniform(0, TAU) if rng is not None else 0.0))
    return out


def reverse_reverb(src, ir, dry=0.5):
    """Sesi yankıla ve ters çevir: yankı sesten önce kabarır (korku sinemasının 'ters yankı'sı)."""
    pad = np.concatenate([src, np.zeros(len(ir))])
    st = np.stack([pad, pad], -1)
    return (dry * st + convolve(st, ir))[::-1]


def stick_slip(n, rate, rng):
    """Düzensiz tık dizisi (gıcırtı, yapışkan esneme kaynağı); rate: anlık tık sıklığı (Hz)."""
    ph = np.cumsum(rate * (0.55 + 0.9 * slow_noise(n, 9.0, rng)) / SR)
    ticks = np.diff(np.floor(ph), prepend=0.0) > 0
    return ticks * rng.uniform(0.3, 1.0, n)


def thump(dur, f_hi, f_lo, sweep, decay):
    """Perdesi hızla düşen alçak vuruş (kalp, darbe gövdesi)."""
    t = span(dur)
    return np.sin(glide(f_lo + (f_hi - f_lo) * np.exp(-t / sweep))) * env_ad(t, 0.003, decay)


# ---------------------------------------------------------------- atmosfer (yatak)

def dark_wind(mx, dur, rng, level, gain=0.2):
    """Boğuk rüzgar: esintiyle gezinen geniş bantlı gövde, esinti tepesinde uluyan dar bantlar
    (aralarında triton), altta gürleme. level: (zamanlar, seviyeler)."""
    t = span(dur)
    n = len(t)
    lv = np.interp(t, *level)
    gust_all = slow_noise(n, 0.3, rng)
    out = np.zeros((n, 2))
    for ch in range(2):
        gust = 0.75 * gust_all + 0.25 * slow_noise(n, 0.55, rng)
        fc = 150 + 380 * gust + 70 * slow_noise(n, 1.6, rng)
        body = lowpass(sweep_band(rng.standard_normal(n), fc, 1.2), 1000)
        hf = 230 + 260 * slow_noise(n, 0.13, rng) + 140 * gust
        howl = sweep_band(rng.standard_normal(n), hf, 10.0) + 0.6 * sweep_band(rng.standard_normal(n), hf * 1.41, 12.0)
        howl_env = np.clip(gust * 1.6 - 0.55, 0, 1) ** 1.5
        rumble = lowpass(rng.standard_normal(n), 75)
        sig = (1.0 * peak(body) * (0.25 + 0.75 * gust ** 1.6) + 0.6 * peak(howl) * howl_env
               + 0.22 * peak(rumble) * (0.4 + 0.6 * gust))
        out[:, ch] = sig * lv
    mx.add(out, 0.0, gain=gain, reverb=0.2)


def deep_drone(mx, t0, t1, rng, swells, gain=0.16):
    """Derinden uğultu: vuruşan iki alçak ses ve çok yavaş nefes alan boğuk testereler."""
    dur = t1 - t0
    t = span(dur)
    beat = np.sin(TAU * 36.7 * t) + 0.8 * np.sin(TAU * 38.9 * t + 1.0)
    br = 200 + 120 * np.sin(TAU * 0.11 * t) ** 2
    body = additive(55.0, dur, br, n_max=14, rng=rng) + additive(58.27, dur, br * 0.9, n_max=14, rng=rng)
    lvl = np.full_like(t, 0.5)
    for c, w, g in swells:
        lvl += g * np.exp(-((t0 + t - c) / w) ** 2)
    sig = (0.3 * beat / 1.8 + 0.7 * peak(body)) * fade(t, 0, 1.5) * tail(t, dur, 0.02) * lvl
    mx.add(wide(sig, 0.011), t0, gain=gain, reverb=0.08)


def bowed_dark(f, dur, rng, bright=850.0, voices=3, cents=9.0):
    """Koyu yaylı (çello / kontrbas): yavaş vibrato, boğuk harmonikler, hafif yay hışırtısı."""
    t = span(dur)
    out = np.zeros(len(t))
    for v in range(voices):
        det = 2 ** ((v - (voices - 1) / 2) * cents / 1200)
        fv = f * det * (1 + 0.005 * np.sin(TAU * rng.uniform(4.2, 5.4) * t + rng.uniform(0, TAU)))
        out += additive(fv, dur, bright, n_max=30, rng=rng)
    bow = band(rng.standard_normal(len(t)), lo=f * 1.5, hi=min(f * 8, 2000)) * 0.05
    return out / voices + bow


def cello_cluster(mx, t0, dur, notes, rng, gain=0.1, attack=1.0, release=0.1, bright=600.0, crescendo=True,
                  tremolo=0.0, spread=0.6):
    """Uyumsuz, koyu yaylı küme (yarım ses + triton): yavaş girer, büyür, istenirse titrer."""
    t = span(dur)
    for i, f in enumerate(notes):
        s = bowed_dark(f, dur, rng, bright=bright)
        env = fade(t, 0, attack) * tail(t, dur, release)
        if crescendo:
            env = env * (0.3 + 0.7 * (t / dur) ** 1.8)
        if tremolo:
            env = env * (0.55 + 0.45 * np.sin(TAU * tremolo * t + rng.uniform(0, TAU)) ** 2)
        p = (i / max(len(notes) - 1, 1) - 0.5) * 2 * spread
        mx.add(pan(peak(s) * env, p), t0, gain=gain / len(notes) ** 0.5, reverb=0.45)


def low_hum(mx, light, gain=0.03):
    """Lambanın alçak vızıltısı (yalnızca 50/100/150 Hz); ışık titredikçe kesilir."""
    lt, lg = light
    t = span(lt[-1])
    g = np.clip(np.interp(t, lt, lg), 0, 1.2)
    hum = np.sin(TAU * 50 * t) + 0.6 * np.sin(TAU * 100 * t) + 0.25 * np.sin(TAU * 150 * t)
    mx.add(wide(hum * g), 0.0, gain=gain, reverb=0.1)


# ---------------------------------------------------------------- olay sesleri

def heart(mx, t0, gain=0.5, rate=1.0, rng=None):
    """İçeriden duyulan boğuk kalp atışı (gümm-güm): alçak vuruş + kapakçığın boğuk 'tok'u."""
    rng = rng or np.random.default_rng(int(t0 * 1000))
    n = int(0.8 * SR)
    t = span(0.8)
    knock = peak(band(rng.standard_normal(n), lo=80, hi=500)) * env_ad(t, 0.001, 0.035)
    lub = thump(0.8, 130, 52, 0.025, 0.09) + 1.0 * knock
    dub = thump(0.8, 115, 60, 0.02, 0.07) + 0.7 * knock
    d = int(0.17 / rate * SR)
    s = lub + 0.72 * np.concatenate([np.zeros(d), dub[:n - d]])
    mx.add(wide(lowpass(np.tanh(2.6 * s), 600)), t0, gain=gain, reverb=0.04)


def thoom(mx, t0, rng, gain=0.5, f0=60.0, f1=30.0, decay=0.5, knock=450):
    """Büyük boş bir salonda ağır, boğuk darbe."""
    dur = max(decay * 5, 1.5)
    t = span(dur)
    body = np.sin(glide(f1 + (f0 - f1) * np.exp(-t / 0.12))) * env_ad(t, 0.004, decay)
    drum = np.sin(glide(2.3 * f0 * (1 + 0.4 * np.exp(-t / 0.02)))) * env_ad(t, 0.002, 0.1 + decay * 0.15)
    hit = lowpass(rng.standard_normal(len(t)), knock) * env_ad(t, 0.002, 0.05)
    s = np.tanh(1.8 * (0.8 * body + 0.6 * drum + 1.1 * peak(hit)))
    mx.add(wide(s, 0.0005), t0, gain=gain, reverb=0.55)


def slam(mx, t0, rng, gain=0.4, f=140.0):
    """Büyük bir salonda ağır kapı çarpması gibi boğuk darbe: alçak geçiren gürültü patlaması + gövde rezonansı.
    Vuruşun telefonda da duyulan (100-600 Hz) gövdesi budur."""
    t = span(1.2)
    burst = lowpass(rng.standard_normal(len(t)), 1500) * env_ad(t, 0.001, 0.07)
    body = sweep_band(rng.standard_normal(len(t)), f + 0.6 * f * np.exp(-t / 0.05), 5.0) * env_ad(t, 0.002, 0.25)
    s = np.tanh(2.0 * (0.8 * peak(burst) + 0.7 * peak(body)))
    mx.add(wide(s, 0.0007), t0, gain=gain, reverb=0.6)


def crackle(mx, t0, dur, rng, gain=0.1, density=0.004, hi=2500):
    """Boğuk elektrik çatırtısı."""
    t = span(dur)
    s = rng.standard_normal(len(t)) * (rng.random(len(t)) < density)
    s = band(s, lo=180, hi=hi) * tail(t, dur, 0.01)
    mx.add(wide(peak(s), 0.0007), t0, gain=gain, reverb=0.25)


def deep_drip(mx, t0, x, rng, cave_ir, gain=0.25):
    """Aşağıda, karanlıkta kana düşen ağır damla: boğuk 'tok', uzak duvarlardan yankılar, mağara."""
    t = span(0.4)
    f = rng.uniform(140, 190) * (1 + 0.6 * np.exp(-t / 0.01))
    s = np.sin(glide(f)) * env_ad(t, 0.0008, 0.05)
    s += 0.6 * peak(lowpass(rng.standard_normal(len(t)), 900)) * env_ad(t, 0.0005, 0.008)
    s = np.tanh(1.4 * s)
    n = len(s)
    echo = np.zeros(n + int(0.9 * SR))
    echo[:n] += s
    for dt, a, lp in ((0.23, 0.35, 700), (0.51, 0.2, 500), (0.83, 0.1, 350)):
        i = int(dt * SR)
        echo[i:i + n] += a * lowpass(s, lp)
    pad = np.concatenate([echo, np.zeros(len(cave_ir))])
    st = np.stack([pad, pad], -1)
    sig = 0.35 * st + 1.5 * convolve(st, cave_ir)
    mx.add(sig * pan(np.ones(1), np.clip(x * 1.4, -0.7, 0.7))[0], t0, gain=gain)


def near_tap(mx, t0, x, rng, gain=0.1):
    """Yakında kana düşen küçük damla / yaprak: yumuşak, boğuk dokunuş."""
    t = span(0.3)
    s = 0.7 * peak(lowpass(rng.standard_normal(len(t)), 1100)) * env_ad(t, 0.0008, 0.015)
    s += 0.5 * np.sin(glide(rng.uniform(110, 160) * (1 + 0.4 * np.exp(-t / 0.01)))) * env_ad(t, 0.002, 0.05)
    mx.add(pan(s, np.clip(x * 1.5, -0.8, 0.8)), t0, gain=gain, reverb=0.4)


def ooze_creak(mx, t0, t1, rng, gain=0.1):
    """Yapışkan kanın inmesi: alçak rezonanslı gıcırtı (tık dizisi) + ıslak esneme."""
    dur = t1 - t0
    t = span(dur)
    n = len(t)
    ticks = stick_slip(n, 22 + 30 * slow_noise(n, 0.8, rng), rng)
    creak = sweep_band(ticks, 110 + 130 * slow_noise(n, 1.1, rng), 7.0)
    stretch = lowpass(sweep_band(rng.standard_normal(n), 240 + 200 * slow_noise(n, 0.9, rng), 3.0), 800)
    env = fade(t, 0, 0.5) * tail(t, dur, 0.5)
    sig = lowpass(0.8 * peak(creak) + 0.4 * peak(stretch), 1200) * env
    mx.add(wide(sig, 0.0009), t0, gain=gain, reverb=0.3)


def swell(mx, t_end, rng, ir, gain=0.3, lo=80, hi=1200, burst=0.08):
    """Ters yankı: kısa gürültü darbesinin yankısı ters çevrilir, t_end'e kabararak gelir, aniden kesilir."""
    t = span(burst)
    src = band(rng.standard_normal(len(t)), lo=lo, hi=hi) * np.exp(-t / (burst / 3))
    rev = reverse_reverb(peak(src), ir, dry=0.3)
    mx.add(rev / np.abs(rev).max(), t_end - len(rev) / SR, gain=gain)


def ghost_whispers(mx, t0, t1, rng, ir, gain=0.07):
    """Ters çevrilmiş, ters yankılı, boğuk fısıltılar; iki yanda gezinir."""
    formants = ((650, 1100), (420, 1900), (330, 850), (560, 950), (480, 1600))
    t_cur = t0
    side = -1
    while t_cur < t1 - 0.25:
        d = rng.uniform(0.15, 0.32)
        t = span(d)
        noise = rng.standard_normal(len(t))
        f1, f2 = formants[rng.integers(len(formants))]
        s = band(noise, lo=f1 * 0.8, hi=f1 * 1.25) + 0.6 * band(noise, lo=f2 * 0.85, hi=f2 * 1.2)
        s = lowpass(s, 2500) * np.sin(np.pi * t / d) ** 1.5 * (0.6 + 0.4 * np.sin(TAU * rng.uniform(5, 9) * t))
        rev = reverse_reverb(peak(s), ir, dry=0.6)
        rev = rev / np.abs(rev).max()
        mx.add(rev * pan(np.ones(1), side * rng.uniform(0.3, 0.85))[0], t_cur + d - len(rev) / SR,
               gain=gain * rng.uniform(0.6, 1.0))
        side = -side
        t_cur += d + rng.uniform(0.05, 0.22)


def flesh(mx, t0, rng, gain=0.2, dur=0.3, p=0.0):
    """Islak et / yırtılma: rezonansı kayan, alçak geçiren süzgeçli gürültü."""
    t = span(dur)
    fc = 220 * np.exp(1.2 * np.sin(np.pi * t / dur)) * (1 + 0.25 * np.sin(TAU * 19 * t))
    s = lowpass(sweep_band(rng.standard_normal(len(t)), fc, 4.0), 1300)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6
    mx.add(pan(peak(s) * env, p), t0, gain=gain, reverb=0.25)


def tendon(mx, t0, t1, rng, gain=0.15):
    """İplik gerilir: sıklaşan ve yükselen gıcırtı; kopma anında kesilir."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    ticks = stick_slip(len(t), 18 + 90 * u ** 1.5, rng)
    s = sweep_band(ticks, 120 + 260 * u ** 1.5, 8.0)
    s = lowpass(peak(s), 1400) * u ** 1.2 * tail(t, dur, 0.003)
    mx.add(wide(s, 0.0006), t0, gain=gain, reverb=0.25)


def glide_wind(mx, fall, rng, gain=0.3):
    """Süzülen gülün havası: hızıyla açılan, gülle birlikte sağa sola gezen boğuk rüzgar."""
    ts, vel, xs, bank = fall
    t0, t1 = ts[0], ts[-1]
    t = span(t1 - t0)
    v = np.interp(t0 + t, ts, vel)
    x = np.interp(t0 + t, ts, xs)
    vn = v / max(vel.max(), 1e-6)
    fc = 220 + 650 * vn ** 1.3
    left = lowpass(sweep_band(rng.standard_normal(len(t)), fc, 1.3), 1400)
    right = lowpass(sweep_band(rng.standard_normal(len(t)), fc * 1.06, 1.3), 1400)
    a = (np.clip(x * 2.0, -0.9, 0.9) + 1) * np.pi / 4
    sig = np.stack([left / np.abs(left).max() * np.cos(a), right / np.abs(right).max() * np.sin(a)], -1)
    sig *= (vn ** 1.5 * tail(t, t1 - t0, 0.3))[:, None]
    mx.add(sig, t0, gain=gain, reverb=0.3)


def dark_braam(mx, t0, rng, gain=0.5, dur=3.2, root=55.0, cutoff=650.0):
    """Karanlık braam: akort farklı testere kümesi, süzgeci kapanır, bozulur, uzun kuyruk."""
    t = span(dur)
    bright = 140 + cutoff * np.exp(-t / 0.6)
    out = np.zeros(len(t))
    for f in (root, root * 1.498, root * 2.0, root * 2.0 * 1.013, root * 2.997):
        out += additive(f * (1 - 0.012 * np.exp(-t / 0.25)), dur, bright, n_max=40, rng=rng)
    sig = lowpass(np.tanh(2.6 * peak(out) * env_ad(t, 0.02, 1.4)), 1500)
    mx.add(wide(sig, 0.0006), t0, gain=gain, reverb=0.5)


def dark_stab(mx, t0, notes, rng, gain=0.4, dur=2.2):
    """Sert girişli, doyurulmuş koyu yaylı küme (fragman 'hit'inin telefonda da duyulan orta gövdesi)."""
    t = span(dur)
    out = np.zeros(len(t))
    for f in notes:
        out += peak(bowed_dark(f, dur, rng, bright=1100))
    env = env_ad(t, 0.005, 0.3) + 0.3 * env_ad(t, 0.05, 1.1)
    sig = lowpass(np.tanh(2.2 * out / len(notes) ** 0.5 * env), 2000)
    mx.add(wide(sig, 0.0011), t0, gain=gain, reverb=0.5)


def sub_drop(mx, t0, gain=0.7, f0=64.0, f1=24.0, dur=2.0):
    """Alt frekans düşüşü; hafif doyurma telefonda da duyulsun diye harmonik ekler."""
    t = span(dur)
    s = np.sin(glide(f1 + (f0 - f1) * np.exp(-t / 0.3))) * env_ad(t, 0.004, dur * 0.35)
    mx.add(wide(np.tanh(1.6 * s)), t0, gain=gain, reverb=0.08)


def heavy_splash(mx, t0, x, rng, gain=0.35):
    """Ağır, boğuk sıçrama: alçak geçiren gürültü patlaması + koyu sıvının kabarması."""
    t = span(0.9)
    burst = lowpass(rng.standard_normal(len(t)), 1400) * env_ad(t, 0.002, 0.09)
    gloop = lowpass(sweep_band(rng.standard_normal(len(t)), 180 + 260 * np.exp(-t / 0.2), 5.0), 900) \
        * env_ad(t, 0.01, 0.25)
    mx.add(pan(0.8 * peak(burst) + 0.6 * peak(gloop), np.clip(x * 1.3, -0.7, 0.7)), t0, gain=gain, reverb=0.4)


def wave_whoom(mx, t0, rng, gain=0.25, dur=2.4):
    """Yayılan dalga: aşağı kayan alçak rezonans + yavaşlayan alçak nabız."""
    t = span(dur)
    s = peak(sweep_band(rng.standard_normal(len(t)), 80 + 260 * np.exp(-t / 0.5), 6.0)) * env_ad(t, 0.03, dur * 0.35)
    puls = np.sin(TAU * 48 * t) * (0.5 + 0.5 * np.sin(TAU * (3.0 - 1.4 * t / dur) * t)) \
        * np.exp(-t / (dur * 0.35)) * fade(t, 0, 0.05)
    mx.add(wide(0.7 * s + 0.5 * puls, 0.013), t0, gain=gain, reverb=0.3)


def dark_riser(mx, t0, t1, rng, gain=0.35):
    """Karanlık yükselen gerilim: bir oktav yükselen alçak küme + açılan gürültü; keskin biter."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    tone = np.zeros(len(t))
    for f in (55.0, 58.3, 82.4, 87.3):
        tone += additive(f * 2 ** (u ** 1.5), dur, 200 + 900 * u ** 2, n_max=16, rng=rng)
    noise = lowpass(sweep_band(rng.standard_normal(len(t)), 150 * 7 ** u, 1.8), 2500)
    env = u ** 2.4 * tail(t, dur, 0.004)
    mx.add(wide((0.6 * peak(tone) + 0.6 * peak(noise)) * env, 0.0004), t0, gain=gain, reverb=0.2)


def demon_growl(mx, t0, dur, rng, gain=0.22):
    """Perdesi düşük, boğazdan gelen hırıltı: düzensiz alt frekans darbeleri, formant süzgeci."""
    t = span(dur)
    wob = band(rng.standard_normal(len(t)), hi=4)
    pulses = np.maximum(np.sin(glide(34 + 7 * wob / (np.abs(wob).max() + 1e-9))), 0) ** 8
    src = pulses + 0.2 * rng.standard_normal(len(t)) * pulses
    s = band(src, lo=50, hi=500) + 0.5 * band(src, lo=550, hi=950)
    env = fade(t, 0, 0.6) * tail(t, dur, 0.08)
    mx.add(wide(lowpass(peak(s), 1100) * env, 0.0003), t0, gain=gain, reverb=0.35)


def slow_breath(mx, t0, dur, rng, gain=0.12):
    """Karanlıkta yavaş, derin nefes (içe çekiş)."""
    t = span(dur)
    s = lowpass(band(rng.standard_normal(len(t)), lo=300, hi=2400), 1800)
    env = (t / dur) ** 1.4 * tail(t, dur, 0.06)
    mx.add(wide(peak(s) * env, 0.002), t0, gain=gain, reverb=0.45)


def metal_scrape(mx, t0, rng, gain=0.2, dur=1.6):
    """Alçak metal sürtünmesi: rezonanslı gürültünün aşağı kayması (boğuk, tiz değil)."""
    t = span(dur)
    out = np.zeros(len(t))
    for f, q in ((330, 18), (540, 22), (870, 26)):
        fc = f * (1 - 0.3 * (1 - np.exp(-t / 0.6))) * (1 + 0.01 * np.sin(TAU * 9 * t))
        out += sweep_band(rng.standard_normal(len(t)), fc, q)
    mx.add(wide(lowpass(peak(out), 1500) * env_ad(t, 0.02, 0.6), 0.0009), t0, gain=gain, reverb=0.5)


def low_scream(mx, t0, rng, gain=0.2, dur=1.2):
    """Boğuk çığlık dokusu: formantları aşağı kayan, perdesi düşürülmüş nefesli gürültü."""
    t = span(dur)
    noise = rng.standard_normal(len(t))
    s = sweep_band(noise, 620 * (1 - 0.35 * t / dur), 6.0) + 0.6 * sweep_band(noise, 1150 * (1 - 0.3 * t / dur), 7.0)
    mx.add(wide(lowpass(peak(s), 1600) * env_ad(t, 0.03, 0.5), 0.0012), t0, gain=gain, reverb=0.55)


def roar(mx, t0, t1, rng, gain=0.35):
    """Gözler giderken büyüyen kükreme: kesim frekansı ve şiddeti artan gürültü + gürleme; keskin biter."""
    dur = t1 - t0
    t = span(dur)
    u = t / dur
    fc = 180 * 6 ** u
    left = lowpass(sweep_band(rng.standard_normal(len(t)), fc, 0.9), 2200)
    right = lowpass(sweep_band(rng.standard_normal(len(t)), fc * 1.05, 0.9), 2200)
    rum = peak(lowpass(rng.standard_normal(len(t)), 90)) * (0.4 + 0.6 * u)
    end = tail(t, dur, 0.004)
    sig = (np.stack([peak(left), peak(right)], -1) * (u ** 1.6)[:, None] + 0.5 * rum[:, None]) * end[:, None]
    mx.add(sig, t0, gain=gain, reverb=0.15)


def whisper_blip(mx, t_end, rng, ir, gain=0.2):
    """Bilinçaltı görüntüde ters fısıltı: kabarır ve karenin bittiği anda kesilir."""
    d = 0.18
    t = span(d)
    s = lowpass(band(rng.standard_normal(len(t)), lo=400, hi=2600), 2200) * np.sin(np.pi * t / d)
    rev = reverse_reverb(peak(s), ir, dry=0.8)
    mx.add(rev / np.abs(rev).max(), t_end - len(rev) / SR, gain=gain)


# ---------------------------------------------------------------- miks

def synthesize(ev, seed=13):
    """Sahne olaylarından stereo ses: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    dur = ev["duration"]
    fx = Mixer(dur)      # olay sesleri
    bed = Mixer(dur)     # atmosfer yatağı: vuruşların altında kısılır
    hall = reverb_ir(np.random.default_rng(seed + 2), length=3.4, rt60=3.0)
    cave = reverb_ir(np.random.default_rng(seed + 1), length=3.4, rt60=3.4) * 0.35
    long_ir = reverb_ir(np.random.default_rng(seed + 3), length=2.6, rt60=2.4)
    short_ir = reverb_ir(np.random.default_rng(seed + 4), length=0.6, rt60=0.7)

    land, eyes, cut, title = ev["land"], ev["eyes"], ev["cut"], ev["title"]
    dark, show = ev["dark"], ev["eyes_show"]
    e0, _ = ev["escalate"]
    snap, morph0 = ev["snap"], ev["morph"][0]

    # ------------------------------------------------ atmosfer yatağı
    lt = [0.0, 0.5, 2.7, 5.0, snap + 0.05, 8.2, land + 0.3, 9.8, dark - 0.05, dark, dark + 0.001,
          show, show + 0.6, eyes, cut - 0.01, cut, title + 0.3, title + 1.2, dur]
    lv = [0.0, 0.4, 0.5, 0.62, 0.5, 0.75, 0.55, 0.6, 1.0, 1.0, 0.0,
          0.0, 0.22, 0.25, 0.3, 0.0, 0.0, 0.35, 0.25]
    dark_wind(bed, dur, rng, (np.array(lt), np.array(lv)), gain=1.7)
    deep_drone(bed, 0.2, dark, rng, swells=[(4.4, 1.2, 0.35), (8.0, 1.0, 0.45), (10.6, 0.5, 0.6)], gain=0.396)
    low_hum(bed, ev["light"], gain=0.02)
    cello_cluster(bed, morph0 - 0.3, snap - morph0 + 0.3, [65.41, 69.3, 92.5, 98.0], rng,
                  gain=0.336, attack=1.4, release=0.05, bright=800)
    cello_cluster(bed, snap, land - snap, [49.0, 51.9, 73.4], rng, gain=0.28, attack=0.6, release=0.02, bright=650)
    cello_cluster(bed, ev["tilt"][0], dark - ev["tilt"][0], [73.4, 77.8, 103.8, 110.0], rng, gain=0.336,
                  attack=0.5, release=0.004, bright=1000, tremolo=9.0)

    # ------------------------------------------------ karanlık, ışık
    heart(fx, 0.35, gain=0.14)
    thoom(fx, ev["light_on"], rng, gain=0.4, f0=70, f1=34, decay=0.35, knock=500)
    slam(fx, ev["light_on"], rng, gain=0.3, f=160)
    crackle(fx, ev["light_on"] + 0.02, 0.14, rng, gain=0.56)
    crackle(fx, ev["flicker"], 0.2, rng, gain=0.7)
    thoom(fx, ev["light_off"], rng, gain=0.22, f0=60, f1=30, decay=0.25, knock=400)

    # ------------------------------------------------ kan iner, damlalar aşağıda yankılanır
    ooze_creak(fx, ev["ooze"][0], morph0 + 0.2, rng, gain=0.384)
    for th, x in ev["drip_hits"]:
        if th < snap:
            deep_drip(fx, th, x, rng, cave, gain=1.26)
        else:
            near_tap(fx, th, x, rng, gain=0.38)

    # ------------------------------------------------ dönüşüm
    swell(fx, ev["bud"], rng, long_ir, gain=0.9, lo=70, hi=900)
    flesh(fx, ev["bud"], rng, gain=0.644, dur=0.45)
    ghost_whispers(fx, morph0 + 0.1, snap - 0.1, rng, short_ir, gain=0.5)
    for i, tb in enumerate(ev["bloom_beats"]):
        heart(fx, tb - 0.03, gain=0.24 + 0.04 * i)
        flesh(fx, tb, rng, gain=0.32 + 0.07 * i, dur=0.35, p=rng.uniform(-0.4, 0.4))

    # ------------------------------------------------ gerilme, kopma, süzülme
    tendon(fx, snap - 0.55, snap, rng, gain=0.416)
    thoom(fx, snap, rng, gain=0.2, f0=130, f1=65, decay=0.08, knock=900)
    glide_wind(fx, ev["fall"], rng, gain=0.96)
    for tb, g in ((5.75, 0.16), (6.45, 0.175), (7.1, 0.19), (7.62, 0.2), (8.02, 0.215)):
        heart(fx, tb, gain=g)

    # ------------------------------------------------ kana değme
    lx = ev["land_x"]
    sub_drop(fx, land, gain=0.297)
    dark_braam(fx, land, rng, gain=0.5)
    thoom(fx, land, rng, gain=0.38, f0=80, f1=32, decay=0.6)
    heavy_splash(fx, land, lx, rng, gain=1.0)
    wave_whoom(fx, land + 0.05, rng, gain=0.924)
    for tc, x in ev["crown"]:
        near_tap(fx, tc, x, rng, gain=0.133)
    for td, x in ev["petal_detach"]:
        flesh(fx, td - 0.04, rng, gain=0.161, dur=0.3, p=np.clip(x * 1.5, -0.8, 0.8))
    for tl, x in ev["petal_land"]:
        near_tap(fx, tl, x, rng, gain=0.38)

    # ------------------------------------------------ bilinçaltı gözler
    for tf in ev["flashes"]:
        whisper_blip(fx, tf + 0.04, rng, short_ir, gain=0.672)
        crackle(fx, tf - 0.01, 0.08, rng, gain=0.98)
        thoom(fx, tf, rng, gain=0.12, f0=90, f1=45, decay=0.06, knock=300)

    # ------------------------------------------------ kamera yukarı, karanlık
    dark_riser(fx, ev["tilt"][0], dark, rng, gain=0.96)
    for tb, g in ((9.95, 0.19), (10.3, 0.21), (10.56, 0.225), (10.76, 0.245)):
        heart(fx, tb, gain=g, rate=1.2)

    # ------------------------------------------------ gözler
    demon_growl(fx, show, eyes - show + 0.25, rng, gain=0.456)
    slow_breath(fx, show + 0.1, eyes - show - 0.15, rng, gain=0.648)
    swell(fx, eyes, rng, short_ir, gain=0.75, lo=90, hi=1400, burst=0.05)
    flesh(fx, ev["twitch"] + 0.02, rng, gain=0.184, dur=0.12)
    sub_drop(fx, eyes, gain=0.317, f0=72, f1=26, dur=2.2)
    dark_braam(fx, eyes, rng, gain=0.542, dur=2.6, root=43.65, cutoff=800)
    slam(fx, eyes, rng, gain=0.3, f=120)
    metal_scrape(fx, eyes + 0.01, rng, gain=1.36)
    low_scream(fx, eyes, rng, gain=1.52)
    flesh(fx, eyes - 0.01, rng, gain=0.46, dur=0.18)
    roar(fx, e0, cut, rng, gain=1.5)
    for i, tb in enumerate(np.arange(e0 + 0.05, cut - 0.05, 0.14)):
        heart(fx, tb, gain=0.18 + 0.02 * i, rate=1.5)

    # ------------------------------------------------ başlık: en büyük vuruş, sonra son bir kalp atışı
    swell(fx, title, rng, short_ir, gain=0.45, lo=60, hi=600, burst=0.03)
    sub_drop(fx, title, gain=0.26, f0=58, f1=26, dur=2.6)
    dark_braam(fx, title, rng, gain=0.645, dur=3.4, root=41.2, cutoff=1500)
    slam(fx, title, rng, gain=0.45, f=110)
    slam(fx, title, rng, gain=0.75, f=260)
    dark_stab(fx, title, [110.0, 164.8, 220.0, 233.1, 329.6], rng, gain=0.62)
    thoom(fx, title, rng, gain=0.36, f0=70, f1=28, decay=0.8)
    crackle(fx, title, 0.2, rng, gain=0.56)
    heart(fx, 14.15, gain=0.14)

    # ------------------------------------------------ yatağı vuruşların altında kıs (sidechain)
    hits = np.abs(fx.dry).max(1)
    hits = lowpass(maximum_filter1d(hits, int(0.04 * SR)), 6)
    duck = 1 - 0.6 * np.clip(hits / (np.percentile(hits, 99.5) + 1e-9), 0, 1)
    dry = fx.dry + bed.dry * duck[:, None]
    send = fx.send + bed.send * duck[:, None]
    mix = dry + 0.4 * convolve(send, hall)

    # kesmeler: ölü sessizlik (yankı da kesilir), sonda sönme
    t = np.arange(len(mix)) / SR
    g = np.ones(len(t))
    for a, b in ((dark, show), (cut, title - 0.1)):
        g *= 1 - (np.clip((t - a) / 0.012, 0, 1) * np.clip((b - 0.004 - t) / 0.004, 0, 1))
    e0, e1 = ev["end_fade"]
    g *= 0.5 + 0.5 * np.cos(np.pi * np.clip((t - e0) / (e1 - e0), 0, 1))
    g *= np.clip(t / 0.01, 0, 1)
    mix *= g[:, None]

    # duyulmayan en alt bölgeyi (<30 Hz) ve tizleri yumuşakça kıs (boğuk genel karakter),
    # hafif doyurarak tepeyi -1 dBFS'e getir
    mix = np.stack([band(mix[:, ch], lo=30, hi=7000, order=1) for ch in range(2)], -1)
    mix = np.tanh(1.3 * mix / np.abs(mix).max()) / np.tanh(1.3)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
