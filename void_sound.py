"""Void Creations intro animasyonu - dijital ses tasarımı.

Yumuşak pad yok: tüm sesler net, keskin ve dijitaldir. Bant sınırlı kare dalga
bipler, FM "ping"ler, bit derinliği düşürülmüş (bitcrush) glitch'ler, basamaklı
(yarım ton yarım ton) yükselen dizi ve sıkı alt vuruşlar; zarflar milisaniye
hassasiyetinde, yankı çok kısa. Ton Si♭ minör pentatonik (Si♭ Re♭ Mi♭ Fa La♭).
Tüm sesler numpy ile sentezlenir; zamanlar ve ekrandaki konumlar
void_scene.VoidScene.events()'ten gelir, her ses görüntüdeki olayla aynı karede başlar.

  zemin belirir (0.36)   -> "sistem açılıyor": alçak tık ve iki kısa bip
  ışık çizgileri gelir   -> geldiği yandan dijital lazer: aşağı süzülen metalik ton
  bir kopya kapanır      -> kare dalga onay biplerinden yükselen bir dizi
  arka planda            -> hesaplama gibi rastgele tiz veri bipleri, alçak elektrik uğultusu
  kopyalar birleşir      -> hızlanan basamaklı kare dalga dizisi + ezik gürültü riser
  logo yanıp söner       -> flaş süresince keskin kesilmiş glitch patlaması
  logo dolar (2.2)       -> sıkı dijital vuruş, ezik şaklama ve FM ping
  harfler belirir        -> her harfe dijital "yazma" tıkı, cepheyi izleyen tarayıcı sesi
  silme (3.47)           -> soldan sağa ezik süpürme, "kapanma" (ton aşağı çöker), son tık
"""
import numpy as np

from sound import SR, TAU, Mixer, band, convolve, glide, peak, reverb_ir, span


def note(name_octave):
    """Nota adı -> frekans (La4 = 440 Hz). Örn. 'Bb5', 'Db7'."""
    names = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
    name, octave = name_octave[:-1], int(name_octave[-1])
    return 440.0 * 2 ** ((names[name] + 12 * (octave + 1) - 69) / 12)




LOCK_NOTES = [note(n) for n in ("Bb5", "Db6", "Eb6", "F6", "Ab6", "Bb6", "Db7", "Eb7", "F7", "Ab7")]
CHATTER = [note(n) for n in ("Bb6", "Db7", "Eb7", "F7", "Ab7", "Bb7", "Db8", "Eb8")]
ARP = [note(n) for n in ("Bb3", "Db4", "Eb4", "F4", "Ab4", "Bb4", "Db5", "Eb5", "F5", "Ab5",
                         "Bb5", "Db6", "Eb6", "F6", "Ab6", "Bb6")]
TYPE_NOTES = [note(n) for n in ("F7", "Ab7", "Bb7", "Db8")]
HUM = note("Bb1")


# ---------------------------------------------------------------- dijital yapı taşları

def square(phase, fmax, top=12000.0):
    """Bant sınırlı kare dalga (tek harmonikler): net ama aliasing'siz."""
    out = np.zeros_like(phase)
    for k in range(1, max(int(top / fmax), 1) + 1, 2):
        out += np.sin(k * phase) / k
    return out * (4 / np.pi)


def crush(x, bits):
    """Bit derinliğini düşürür: dijital, basamaklı genlik."""
    q = 2 ** (bits - 1)
    return np.round(x * q) / q


def hold(x, k):
    """Örnekleme hızını düşürür (her k örnekte bir değer): dijital pürüz."""
    return np.repeat(x[::k], k)[:len(x)]


def gate(t, attack, length, release=0.0015):
    """Keskin kapı: attack ile açılır, length boyunca tam, release ile kapanır (saniye)."""
    return np.clip(t / attack, 0, 1) * np.clip((length - t) / release, 0, 1)


def pluck(t, attack, decay):
    """Keskin başlayıp üstel sönen zarf."""
    return np.clip(t / attack, 0, 1) * np.exp(-t / decay)


def panned(sig, pan):
    """Sabit güçte stereo konum (pan sabit ya da zamanla değişen dizi)."""
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([sig * np.cos(p), sig * np.sin(p)], -1)


# ---------------------------------------------------------------- sesler

def boot(mx, t0):
    """Zemin belirirken: alçak tık ve iki kısa kare dalga bip ("sistem açılıyor")."""
    t = span(0.3)
    thump = np.sin(glide(50 + 70 * np.exp(-t / 0.012))) * pluck(t, 0.0005, 0.04)
    mx.add(thump, t0, gain=0.5, reverb=0.05)
    for dt, f in ((0.0, note("Bb5")), (0.07, note("F6"))):
        tb = span(0.05)
        blip = square(TAU * f * tb, f) * gate(tb, 0.0005, 0.038)
        mx.add(blip, t0 + dt, gain=0.075, reverb=0.1)


def laser(mx, t0, arrive, pan0, rng, gain):
    """Işık çizgisi: geldiği yandan logoya doğru aşağı süzülen metalik FM tonu; logoya değince tık."""
    dur = max(arrive - t0, 0.04)
    t = span(dur)
    u = t / dur
    f = 4200 * (1400 / 4200) ** u                           # 4.2 kHz -> 1.4 kHz
    ph = glide(f)
    fm = np.sin(ph + 1.8 * np.sin(2.5 * ph))                # metalik (FM)
    tone = crush(fm, 6) * np.clip(t / 0.002, 0, 1) * (0.35 + 0.65 * u) * np.clip((dur - t) / 0.003, 0, 1)
    mx.add(panned(tone, 0.85 * pan0 * (1 - u)), t0, gain=gain, reverb=0.08)
    tc = span(0.03)
    click = band(rng.standard_normal(len(tc)), lo=2000) * pluck(tc, 0.0003, 0.004)
    mx.add(peak(click), arrive, gain=0.5 * gain, reverb=0.05)


def lock(mx, t0, f, pan):
    """Bir kopyanın konturu kapandı: kısa kare dalga onay bipi."""
    t = span(0.06)
    blip = square(TAU * f * t, f) * gate(t, 0.0005, 0.03, 0.004) * np.exp(-t / 0.05)
    mx.add(blip, t0, gain=0.07, pan=pan, reverb=0.12)


def chatter(mx, t0, t1, rng):
    """Arka planda hesaplama gibi rastgele tiz veri bipleri; sıklığı giderek artar."""
    t = t0
    while True:
        u = (t - t0) / (t1 - t0)
        t += rng.exponential(1 / (7 + 45 * u ** 2))
        if t >= t1:
            break
        f = CHATTER[rng.integers(len(CHATTER))]
        d = rng.uniform(0.006, 0.016)
        tb = span(d + 0.002)
        blip = np.sin(TAU * f * tb) * gate(tb, 0.0005, d, 0.001)
        mx.add(blip, t, gain=rng.uniform(0.012, 0.03), pan=rng.uniform(-0.85, 0.85), reverb=0.1)


def hum(t, t_in, t_rise, solid, wipe0, wipe1):
    """Alçak dijital uğultu (Si♭1 sinüs + ezik kare); silmede tonu aşağı çökerek kapanır."""
    f = np.full(len(t), HUM)
    u = np.clip((t - wipe0) / (wipe1 - wipe0), 0, 1)
    f *= 2 ** (-2.2 * u ** 1.5)                               # kapanma: ~2 oktav aşağı
    ph = glide(f)
    sq = hold(crush(square(2 * ph, 2 * HUM, top=900), 6), 6)
    sig = np.sin(ph) + 0.22 * sq
    level = np.interp(t, [0, t_in, t_in + 0.25, t_rise, solid, wipe0, wipe1, wipe1 + 0.08],
                      [0, 0, 0.35, 0.4, 1.0, 1.0, 0.6, 0.0])
    return sig * level


def stepped_riser(mx, t0, t1, flashes, rng):
    """Kopyalar birleşirken: hızlanan basamaklı kare dalga dizisi ve ezik gürültü; logo dolunca kesilir.
    Logo her yanıp söndüğünde dizi susar: flaşlarla aynı ritimde kesilir."""
    dur = t1 - t0
    # adımlar giderek kısalır: pentatonik dizide Si♭3'ten Si♭6'ya
    n = len(ARP)
    w = np.linspace(1.0, 0.25, n)
    edges = t0 + dur * np.concatenate([[0], np.cumsum(w) / w.sum()])
    t = span(dur)
    tt = t0 + t
    f = np.array(ARP)[np.clip(np.searchsorted(edges, tt, side="right") - 1, 0, n - 1)]
    ph = glide(f)
    tone = square(ph, max(ARP), top=9000)
    # her adımın başında keskin vurgu
    step_start = edges[np.clip(np.searchsorted(edges, tt, side="right") - 1, 0, n - 1)]
    accent = 0.55 + 0.45 * np.exp(-(tt - step_start) / 0.02)
    u = t / dur
    env = (0.25 + 0.75 * u ** 1.5) * accent * np.clip((dur - t) / 0.002, 0, 1)
    duck = np.ones(len(t))
    for a, b in flashes:
        duck *= 1 - ((tt >= a) & (tt < b + 0.004))
    mx.add(tone * env * duck, t0, gain=0.09, reverb=0.08)
    noise = hold(crush(rng.standard_normal(len(t)), 4), 3)
    noise = peak(band(noise, lo=500, hi=2500)) * (1 - u) + peak(band(noise, lo=2500, hi=12000)) * u   # tizleşir
    noise_env = u ** 2.2 * duck * np.clip((dur - t) / 0.002, 0, 1)
    mx.add(noise * noise_env, t0, gain=0.12, reverb=0.05)


def glitch(mx, t0, t1, k, rng):
    """Logo yanıp söndüğünde: flaş süresince keskin kesilmiş glitch patlaması."""
    d = t1 - t0
    t = span(d + 0.03)
    g = gate(t, 0.0005, d, 0.002)
    noise = hold(crush(rng.standard_normal(len(t)), 3), rng.integers(2, 6))
    f = (note("Bb6"), note("F6"))[k % 2]
    tone = square(TAU * f * t, f, top=10000)
    thump = np.sin(glide(55 + 90 * np.exp(-t / 0.008))) * pluck(t, 0.0005, 0.03)
    s = (0.55 * peak(band(noise, lo=1200)) + 0.3 * tone) * g + 0.6 * thump
    mx.add(s, t0, gain=0.34 + 0.03 * k, reverb=0.06)


def impact(mx, t0, rng):
    """Logo dolup yerine oturduğunda: sıkı dijital vuruş, ezik şaklama ve FM ping."""
    t = span(1.2)
    kick = np.tanh(3.0 * np.sin(glide(45 + 130 * np.exp(-t / 0.028))) * pluck(t, 0.0005, 0.2)) / np.tanh(3.0)
    snap = hold(crush(rng.standard_normal(len(t)), 4), 2)
    snap = peak(band(snap, lo=1500)) * pluck(t, 0.0003, 0.02)
    mx.add(0.95 * kick + 0.5 * snap, t0, gain=0.95, reverb=0.08)
    fc, fm = note("Bb5"), note("Bb5") * 3.5
    index = 6.0 * np.exp(-t / 0.08)
    ping = np.sin(TAU * fc * t + index * np.sin(TAU * fm * t)) * pluck(t, 0.0005, 0.45)
    mx.add(ping, t0, gain=0.12, reverb=0.25)


def type_tick(mx, t0, pan, rng):
    """Harf belirince: dijital "yazma" tıkı (kısa kare bip + tık)."""
    t = span(0.03)
    f = TYPE_NOTES[rng.integers(len(TYPE_NOTES))]
    blip = square(TAU * f * t, f) * gate(t, 0.0004, 0.012, 0.004)
    click = band(rng.standard_normal(len(t)), lo=3000) * pluck(t, 0.0002, 0.0025)
    mx.add(0.6 * blip + 0.5 * peak(click), t0, gain=0.2, pan=pan, reverb=0.08)


def scanner(mx, samples, rng):
    """Yazının üzerinden geçen cepheyi izleyen dijital tarayıcı: 60 Hz'de titreyen dar bant ses."""
    ts, pans = np.array(samples, float).T
    dur = ts[-1] - ts[0]
    t = span(dur)
    tt = ts[0] + t
    u = t / dur
    carrier = crush(np.sin(TAU * 3729.31 * t), 5)            # Si♭7
    chop = (np.sin(TAU * 60 * t) > 0).astype(float)          # dijital titreşim
    env = np.sin(np.pi * u) ** 0.8 * (0.4 + 0.6 * chop)
    mx.add(panned(carrier * env, 0.9 * np.interp(tt, ts, pans)), ts[0], gain=0.035, reverb=0.05)


def swipe(mx, samples, rng):
    """Silme: soldan sağa giden ezik gürültü süpürmesi; cephe hızlandıkça tizleşir."""
    ts, pans = np.array(samples, float).T
    dur = ts[-1] - ts[0]
    t = span(dur)
    tt = ts[0] + t
    u = t / dur
    speed = np.sin(np.pi * u) ** 1.5
    noise = hold(crush(rng.standard_normal(len(t)), 4), 2)
    lo_band = band(noise, lo=400, hi=2500)
    hi_band = band(noise, lo=2500, hi=12000)
    sig = (peak(lo_band) * (1 - speed) + peak(hi_band) * speed) * speed
    mx.add(panned(sig, 0.9 * np.interp(tt, ts, pans)), ts[0], gain=0.3, reverb=0.06)


def shutdown(mx, t0, t_end, rng):
    """Silme başlarken aşağı çöken kare dalga, sonunda (ekran kararınca) kesin bir tık."""
    dur = t_end - t0
    t = span(dur)
    u = t / dur
    f = note("Bb4") * 2 ** (-3 * u ** 1.3)
    tone = crush(square(glide(f), note("Bb4"), top=6000), 5) * (1 - u) ** 0.5
    mx.add(tone * np.clip(t / 0.001, 0, 1), t0, gain=0.07, reverb=0.08)
    tc = span(0.25)
    end = (np.sin(glide(45 + 80 * np.exp(-tc / 0.01))) * pluck(tc, 0.0005, 0.06)
           + 0.4 * peak(band(rng.standard_normal(len(tc)), lo=2500)) * pluck(tc, 0.0003, 0.003))
    mx.add(end, t_end, gain=0.45, reverb=0.1)


# ---------------------------------------------------------------- miks

def synthesize(events, seed=4):
    """Sahne olaylarından (void_scene.VoidScene.events) stereo ses üretir: (örnek, 2) float32."""
    rng = np.random.default_rng(seed)
    duration = events["duration"]
    t = np.arange(int(round(duration * SR))) / SR
    turn, solid = events["turn"], events["solid"]
    wipe0, wipe1 = events["wipe"][0][0], events["wipe"][-1][0]
    mx = Mixer(duration)

    boot(mx, events["boot"])
    done = sorted(events["snakes"], key=lambda s: s["done"])
    for s in events["snakes"]:
        laser(mx, s["t0"], s["arrive"], s["pan"], rng, gain=0.12)
    for k, s in enumerate(done):
        lock(mx, s["done"], LOCK_NOTES[k % len(LOCK_NOTES)], 0.2 * s["pan"])
    chatter(mx, events["boot"] + 0.08, solid, rng)
    stepped_riser(mx, turn[0], solid, events["flashes"], rng)
    for k, (a, b) in enumerate(events["flashes"]):
        glitch(mx, a, b, k, rng)
    impact(mx, solid, rng)
    for tl, p in events["letters"]:
        type_tick(mx, tl, 0.8 * p, rng)
    scanner(mx, events["reveal"], rng)
    swipe(mx, events["wipe"], rng)
    shutdown(mx, wipe0, wipe1, rng)

    base = hum(t, events["boot"], turn[0], solid, wipe0, wipe1)
    mix = mx.dry + 0.11 * np.stack([base, base], -1)
    mix += 0.3 * convolve(mx.send, reverb_ir(rng, length=0.8, rt60=0.45))   # çok kısa oda: net kalsın

    # Tepe seviyeyi -1 dBFS'e getir (sert olmayan, hafif bir sınırlayıcıyla)
    mix = np.tanh(1.15 * mix / np.abs(mix).max()) / np.tanh(1.15)
    return (mix * 10 ** (-1 / 20)).astype(np.float32)
