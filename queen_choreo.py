"""QUEEN lyric video - üç dansçının koreografisi ve fizik "bake"i.

Katmanlar (character-physics skill'indeki sırayla):
  1. Anahtar pozlar: el/ayak hedefleri (IK) ve gövde açıları; her figür şarkının vuruşuna,
     sözüne ya da patlama anına bağlı (queen_timing.BEATS / LINES / HITS).
  2. Kök yörüngesi: zıplamalar balistik (sabit yerçekimi, tepede duraksama yok), kalkış ve iniş hız sürekli.
  3. Kemikler kütleli yaylardan geçer: gövde sert, eller/ayaklar gevşek -> kendiliğinden overlap.
  4. Zıplarken hava sürüklemesi: eller yükselirken geride kalır, düşerken havalanır.
  5. Saç zincirleri ve etek kaburgaları dünya uzayında Verlet + şekil yayı + çarpışma.

Figürler (hepsi özgün, idol dansı): lamba gibi işaret etme, adım-dokun, alkış, hece hece
tepinme, "kırmızı ışık"ta donma, süper zıplama, pırıltı elleri, keskin pozlar, kovalamaca
koşusu (iki dansçı yer değiştirir), uzanıp yakalama, dönüş, dalga gibi salınım, kalp eller,
X kollar, düşünme, fikir, kollarla ○ (doğru cevap), çiçek açma, bulutları yarma, yüz
çerçeveleme, idol dalgası, projektör süpürmesi, gökyüzüne uzanma ve final kraliçe pozu.
"""
import math
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / ".claude/skills/character-physics/scripts"))
from physics import Spring  # noqa: E402

from queen_dancers import HEAD_C, HEAD_S, JOINT_NAMES, SKIRT_NODES, Dancer, solve_skeleton  # noqa: E402
from queen_timing import BEATS, DURATION, FINAL_HIT  # noqa: E402

FPS = 60
NAMES = ("aka", "kin", "midori")
AVG_BEAT = (BEATS[-1] - BEATS[0]) / (len(BEATS) - 1)
G = 13.0                                   # çizgi film yerçekimi (birim/s², karakter boyu 1.6)
HIDE = (14.46, 20.55)                      # fırtına bölümünde sahnede yoklar


def beat_at(t):
    """(vuruş no, vuruş içindeki kesir 0-1, vuruş süresi)."""
    if t < BEATS[0]:
        f = (t - BEATS[0]) / AVG_BEAT
        return int(math.floor(f)), f - math.floor(f), AVG_BEAT
    i = bisect_right(BEATS, t) - 1
    if i >= len(BEATS) - 1:
        f = (t - BEATS[-1]) / AVG_BEAT
        k = int(math.floor(f))
        return len(BEATS) - 1 + k, f - k, AVG_BEAT
    d = BEATS[i + 1] - BEATS[i]
    return i, (t - BEATS[i]) / d, d


def beat_time(i):
    if i < len(BEATS):
        return BEATS[max(i, 0)]
    return BEATS[-1] + (i - len(BEATS) + 1) * AVG_BEAT


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def win(t, a, b, fade=0.12):
    """a-b aralığında 1, kenarlarda yumuşak geçiş."""
    return smooth((t - a + fade) / fade) * smooth((b + fade - t) / fade)


def pulse(t, t0, width=0.18):
    """t0'da tepe yapan kısa vuruş zarfı (0-1)."""
    x = (t - t0) / width
    return math.exp(-x * x * 4) if -1 < x < 2 else 0.0


# ---------------------------------------------------------------- anahtar el pozları (sol el; sağ için x ters)

HANDS = {
    "rest": ((0.17, -0.28, 0.05), (0.3, -0.2, -1.0)),
    "hip": ((0.13, -0.19, 0.03), (1.0, 0.0, -0.6)),
    "up": ((0.15, 0.51, 0.04), (1.0, 0.0, 0.0)),
    "v": ((0.33, 0.44, 0.07), (0.0, 0.0, -1.0)),
    "point": ((0.38, 0.4, 0.13), (0.0, -1.0, -1.0)),
    "out": ((0.53, 0.1, 0.03), (0.0, 0.0, -1.0)),
    "fwd": ((0.12, 0.1, 0.4), (1.0, -0.5, 0.0)),
    "clap": ((0.015, 0.03, 0.26), (1.0, -0.6, -0.2)),
    "open": ((0.3, 0.05, 0.2), (0.4, -1.0, -0.3)),
    "chest": ((0.035, 0.05, 0.13), (1.0, -1.0, 0.0)),
    "face": ((0.12, 0.27, 0.14), (1.0, -1.0, 0.0)),
    "heart": ((0.02, 0.4, 0.08), (1.0, 0.3, 0.2)),
    "maru": ((0.012, 0.45, 0.0), (1.0, 0.4, 0.0)),
    "cross": ((-0.1, 0.05, 0.2), (1.0, -0.4, 0.0)),
    "wide": ((0.46, -0.05, 0.15), (0.0, -1.0, -0.5)),
    "shrug": ((0.3, -0.02, 0.16), (0.3, -1.0, 0.0)),
    "chin": ((0.0, 0.2, 0.16), (1.0, -1.2, 0.0)),
    "fist": ((0.18, 0.4, 0.14), (1.0, -0.3, -0.3)),
    "fist_low": ((0.16, -0.12, 0.16), (0.4, -1.0, -0.4)),
    "run_f": ((0.14, -0.04, 0.2), (0.2, -1.0, -0.5)),
    "run_b": ((0.15, -0.2, -0.12), (0.2, -1.0, 0.3)),
    "jazz": ((0.27, 0.26, 0.12), (1.0, -1.0, 0.0)),
    "sky": ((0.25, 0.48, 0.2), (0.0, 0.0, -1.0)),
    "beckon": ((0.1, 0.18, 0.34), (1.0, -1.0, 0.0)),
    "angle_up": ((0.3, 0.36, 0.02), (0.0, -1.0, -1.0)),
    "angle_down": ((0.36, -0.2, 0.05), (0.0, 1.0, -1.0)),
}


def hand(name, side, pull=0.0):
    p, e = HANDS[name]
    s = 1 if side == "l" else -1
    return np.array([p[0] * s, p[1], p[2] + pull]), np.array([e[0] * s, e[1], e[2]])


def mix_pose(a, b, w):
    if w <= 0:
        return a
    if w >= 1:
        return b
    out = {}
    for k in a:
        out[k] = a[k] + (b[k] - a[k]) * w if k in b else a[k]
    return out


# ---------------------------------------------------------------- formasyon

def formation(i, t):
    """Dansçının sahnedeki yeri (x, z) ve bakış yönü (yaw)."""
    base = ((-1.0, 0.0), (0.0, 0.25), (1.0, 0.0))[i]
    x, z = base
    yaw = (8.0, 0.0, -8.0)[i]
    if i != 1:
        # "Chase me": iki yan dansçı arkadan koşarak yer değiştirir (28.3 - 29.15)
        u = smooth((t - 28.3) / 0.85)
        x = base[0] + (-2 * base[0]) * u
        lane = -0.45 if i == 0 else -0.75
        z = lane * math.sin(math.pi * u) if 28.3 < t < 29.15 else 0.0
        if 28.2 < t < 29.25:
            run_dir = 1 if i == 0 else -1
            yaw = 90 * run_dir * win(t, 28.32, 29.05, 0.12) + yaw * (1 - win(t, 28.32, 29.05, 0.12))
        if t >= 29.15:
            yaw = -yaw
        # finalde merkeze yaklaşır
        k = smooth((t - 57.6) / 1.2)
        x = x * (1 - 0.2 * k)
    else:
        z += 0.1 * smooth((t - 57.6) / 1.2)
    return x, z, yaw


# ---------------------------------------------------------------- figürler

def base_pose(i, t):
    """Her figürün altında çalışan groove: vuruşta dizler bükülür, ağırlık iki vuruşta bir yana geçer."""
    b, f, d = beat_at(t)
    x, z, yaw = formation(i, t)
    energy = 0.6 if t < 7.268 else (0.4 if 36.0 < t < 41.2 else 1.0)
    depth = 0.018 * energy
    bounce = -depth * (0.5 + 0.5 * math.cos(2 * math.pi * f)) - 0.02
    side = math.sin(math.pi * (b + f) + i * 0.7)
    hl, el = hand("rest", "l")
    hr, er = hand("rest", "r")
    swing = 0.03 * math.sin(math.pi * (b + f))
    hl = hl + np.array([0.0, 0.0, swing])
    hr = hr + np.array([0.0, 0.0, -swing])
    return dict(
        root=np.array([x, 0.0, z]), yaw=np.array([yaw]), bounce=np.array([bounce]),
        pelvis=np.array([2.0, 4.0 * side * energy, 3.0 * side * energy]),
        spine=np.array([0.0, 0.0, -1.5 * side]), chest=np.array([2.0, -3.0 * side * energy, -2.0 * side]),
        neck=np.array([3.0 * math.cos(2 * math.pi * f) * energy, 0.0, 0.0]), head=np.array([0.0, 0.0, 3.0 * side]),
        hand_l=hl, elbow_l=el, hand_r=hr, elbow_r=er,
        foot_l=np.array([0.1, 0.06, 0.0]), foot_r=np.array([-0.1, 0.06, 0.0]),
        knee_l=np.array([0.2, 0.0, 1.0]), knee_r=np.array([-0.2, 0.0, 1.0]))


def set_hands(p, left, right, pull=0.0):
    p["hand_l"], p["elbow_l"] = hand(left, "l", pull)
    p["hand_r"], p["elbow_r"] = hand(right, "r", pull)


def lean(p, forward=0.0, side=0.0, turn=0.0, look=(0.0, 0.0, 0.0)):
    p["pelvis"] = p["pelvis"] + np.array([forward * 0.3, turn * 0.3, side * 0.4])
    p["chest"] = p["chest"] + np.array([forward * 0.7, turn * 0.7, side * 0.6])
    p["head"] = p["head"] + np.array(look)


def step_touch(p, t, width=0.13, arms=True):
    b, f, d = beat_at(t)
    s = 1 if b % 2 == 0 else -1                           # hangi ayak adım atıyor
    lift = 0.07 * math.sin(math.pi * min(f / 0.5, 1.0)) if f < 0.5 else 0.0
    move = smooth(f / 0.45)
    out = width * (1 if s > 0 else -1)
    # adım atan ayak dışarı çıkar, diğeri yanına dokunur
    if s > 0:
        p["foot_l"] = np.array([0.1 + width * move, 0.06, 0.0])
        p["foot_r"] = np.array([-0.06 + width * move, 0.06 + lift, 0.02])
    else:
        p["foot_r"] = np.array([-0.1 - width * move, 0.06, 0.0])
        p["foot_l"] = np.array([0.06 - width * move, 0.06 + lift, 0.02])
    shift = out * (0.5 * move)
    p["root"] = p["root"] + np.array([shift * 0.6, 0.0, 0.0])
    p["foot_l"] = p["foot_l"] - np.array([shift * 0.6, 0.0, 0.0])
    p["foot_r"] = p["foot_r"] - np.array([shift * 0.6, 0.0, 0.0])
    p["pelvis"] = p["pelvis"] + np.array([0.0, 0.0, 5.0 * s])
    if arms:
        sw = math.sin(math.pi * (b + f))
        p["hand_l"] = p["hand_l"] + np.array([0.02, 0.06 * max(sw, 0), 0.08 * sw])
        p["hand_r"] = p["hand_r"] + np.array([-0.02, 0.06 * max(-sw, 0), -0.08 * sw])


def stomp(p, t, times):
    """Hecelerde tepinme: ayak kalkar, vuruşta yere iner, gövde çöker."""
    for k, tk in enumerate(times):
        dt = t - tk
        s = "l" if k % 2 == 0 else "r"
        if -0.14 < dt < 0.0:
            u = (dt + 0.14) / 0.14
            key = f"foot_{s}"
            p[key] = p[key] + np.array([0.0, 0.1 * math.sin(math.pi * u), 0.03])
        if 0.0 <= dt < 0.25:
            p["bounce"] = p["bounce"] - 0.045 * math.exp(-dt / 0.07)


def hermite(u, p0, v0, p1, v1, dur):
    """Konum ve hızı (birim/s) iki uçta verilen kübik geçiş; u 0-1, dur saniye."""
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * v0 * dur
            + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * v1 * dur)


# Zıplamalar: kalkış, iniş, yükseklik. Hepsinde çömelme -> dizlerle itiş (hız sürekli) ->
# balistik uçuş -> dizlerle karşılayan iniş -> toparlanma.
JUMPS = [(10.70, 10.99, 0.16), (48.10, 48.50, 0.34), (54.79, 55.14, 0.20)]
SUPER = (14.071, 9.0)                                     # 14.07: ekranın üstünden çıkış
FALL = (20.40, 21.14)                                     # yukarıdan serbest düşüş, 21.14'te iniş
CROUCH, PUSH, ABSORB, RECOVER = 0.22, 0.12, 0.13, 0.32


def _takeoff(t, t_off, v0, depth):
    """Kalkış öncesi pelvis: çömelme, sonra kalkış anında v0 hızına ulaşan itiş."""
    a = t_off - PUSH - CROUCH
    if a <= t < t_off - PUSH:
        return -depth * smooth((t - a) / CROUCH)
    if t_off - PUSH <= t < t_off:
        return hermite((t - (t_off - PUSH)) / PUSH, -depth, 0.0, 0.0, v0, PUSH)
    return None


def _landing(t, t_land, v_land, depth):
    """İniş: pelvis düşüş hızıyla aşağı devam eder, dizler bükülerek durdurur, sonra toparlanır."""
    if t_land <= t < t_land + ABSORB:
        return hermite((t - t_land) / ABSORB, 0.0, -v_land, -depth, 0.0, ABSORB)
    if t_land + ABSORB <= t < t_land + ABSORB + RECOVER:
        return -depth * (1 - smooth((t - t_land - ABSORB) / RECOVER))
    return None


def vertical(t):
    """(kök yüksekliği, pelvis ek inişi) - kalkışta ve inişte hız süreklidir."""
    for t_off, t_land, h in JUMPS:
        T = t_land - t_off
        g = 8 * h / (T * T)
        v0 = g * T / 2
        pre = _takeoff(t, t_off, v0, 0.11)
        if pre is not None:
            return 0.0, pre
        if t_off <= t < t_land:
            dt = t - t_off
            return v0 * dt - 0.5 * g * dt * dt, 0.0
        post = _landing(t, t_land, v0, 0.1)
        if post is not None:
            return 0.0, post
    t_off, v0 = SUPER
    pre = _takeoff(t, t_off, v0, 0.16)
    if pre is not None:
        return 0.0, pre
    if t_off <= t < HIDE[0] + 0.05:
        dt = t - t_off
        return v0 * dt - 0.5 * G * dt * dt, 0.0
    t0, t_land = FALL
    if t0 <= t < t_land:
        h0 = 0.5 * G * (t_land - t0) ** 2
        return h0 - 0.5 * G * (t - t0) ** 2, 0.0
    post = _landing(t, t_land, G * (t_land - t0), 0.17)
    if post is not None:
        return 0.0, post
    return 0.0, 0.0


# Figür zaman çizelgesi: (başlangıç, bitiş, fonksiyon) - fonksiyon(p, t, i) pozu değiştirir
def fig_point(p, t, i, t_red=None, t_green=None):
    # A (ekranın solu) sağ koluyla sola, M (ekranın sağı) sol koluyla sağa işaret eder
    if i == 0 and t_red is not None:
        w = smooth((t - t_red + 0.1) / 0.12)
        a, e = hand("point", "r")
        p["hand_r"] = p["hand_r"] + (a - p["hand_r"]) * w
        p["elbow_r"] = e
        hl, el = hand("hip", "l")
        p["hand_l"], p["elbow_l"] = hl, el
        lean(p, side=-4 * w, look=(-4 * w, -18 * w, -6 * w))
    if i == 2 and t_green is not None:
        w = smooth((t - t_green + 0.1) / 0.12)
        a, e = hand("point", "l")
        p["hand_l"] = p["hand_l"] + (a - p["hand_l"]) * w
        p["elbow_l"] = e
        hr, er = hand("hip", "r")
        p["hand_r"], p["elbow_r"] = hr, er
        lean(p, side=4 * w, look=(-4 * w, 18 * w, 6 * w))
    if i == 1:
        set_hands(p, "hip", "hip")
        lean(p, forward=-3)


def fig_clap(p, t, beats):
    b, f, d = beat_at(t)
    close = max(pulse(t, tb, 0.16) for tb in beats) if beats else 0.0
    ol, _ = hand("open", "l")
    orr, _ = hand("open", "r")
    cl, el = hand("clap", "l")
    cr, er = hand("clap", "r")
    p["hand_l"] = ol + (cl - ol) * close
    p["hand_r"] = orr + (cr - orr) * close
    p["elbow_l"], p["elbow_r"] = el, er


def fig_freeze(p, t, i, t0, variant):
    """'Red Light?': herkes olduğu yerde donar (her dansçı farklı pozda)."""
    poses = (
        ("out", "up", dict(side=-6, look=(0, -10, -8)), (0.0, 0.14)),
        ("v", "v", dict(forward=-4, look=(-8, 0, 0)), (0.0, 0.0)),
        ("fwd", "hip", dict(side=6, look=(0, 12, 6)), (0.12, 0.0)),
    )
    if variant:
        poses = poses[::-1]
    l, r, ln, lift = poses[i]
    set_hands(p, l, r)
    lean(p, **ln)
    p["foot_l"] = p["foot_l"] + np.array([0.0, lift[0], 0.05 * (lift[0] > 0)])
    p["foot_r"] = p["foot_r"] + np.array([0.0, lift[1], 0.05 * (lift[1] > 0)])
    p["bounce"] = np.array([-0.035])
    for k in ("pelvis", "chest", "neck"):
        p[k] = p[k] * 0.3


def fig_crouch(p, t, t0, t1):
    u = smooth((t - t0) / (t1 - t0))
    set_hands(p, "rest", "rest")
    p["hand_l"] = p["hand_l"] + np.array([0.0, -0.05, -0.1]) * u
    p["hand_r"] = p["hand_r"] + np.array([0.0, -0.05, -0.1]) * u
    lean(p, forward=18 * u, look=(10 * u, 0, 0))


def fig_air(p, t, arms="v"):
    set_hands(p, arms, arms)
    p["foot_l"] = p["foot_l"] + np.array([0.02, 0.1, -0.03])
    p["foot_r"] = p["foot_r"] + np.array([-0.02, 0.06, 0.04])
    lean(p, forward=-6, look=(-10, 0, 0))


def fig_land(p, t, t_land):
    dt = t - t_land
    if 0 <= dt < 0.45:
        lean(p, forward=14 * math.exp(-dt / 0.15))


def fig_run(p, t, i):
    b, f, d = beat_at(t)
    ph = (b + f) * 2 * math.pi                           # sekizlik koşu: vuruşta iki adım
    for s, sg in (("l", 1), ("r", -1)):
        up = max(0.0, math.sin(ph + (0 if s == "l" else math.pi)))
        p[f"foot_{s}"] = np.array([0.08 * sg, 0.06 + 0.16 * up, 0.08 * up])
        key = "run_f" if math.sin(ph + (math.pi if s == "l" else 0)) > 0 else "run_b"
        a, e = hand(key, s)
        p[f"hand_{s}"], p[f"elbow_{s}"] = a, e
    p["bounce"] = p["bounce"] - 0.02 + 0.02 * abs(math.sin(ph))
    lean(p, forward=10)


def fig_beckon(p, t, times):
    set_hands(p, "hip", "beckon")
    curl = max(pulse(t, tk, 0.2) for tk in times)
    p["hand_r"] = p["hand_r"] + np.array([0.0, 0.06 * curl, -0.12 * curl])
    lean(p, forward=4, look=(0, 0, -8))


def fig_reach(p, t, t0, t_grab):
    u = smooth((t - t0) / 0.3)
    g = smooth((t - t_grab) / 0.25)
    fl, el = hand("fwd", "l")
    fr, er = hand("fwd", "r")
    cl, _ = hand("chest", "l")
    cr, _ = hand("chest", "r")
    p["hand_l"] = p["hand_l"] + (fl - p["hand_l"]) * u
    p["hand_r"] = p["hand_r"] + (fr - p["hand_r"]) * u
    p["hand_l"] = p["hand_l"] + (cl - p["hand_l"]) * g
    p["hand_r"] = p["hand_r"] + (cr - p["hand_r"]) * g
    p["elbow_l"], p["elbow_r"] = el, er
    lean(p, forward=14 * u * (1 - g) - 4 * g)


def fig_spin(p, t, t0, t1):
    u = smooth((t - t0) / (t1 - t0))
    p["yaw"] = p["yaw"] + 360 * u * (1 if t0 % 2 < 1 else -1)
    w = math.sin(math.pi * u)
    set_hands(p, "out", "out")
    p["hand_l"] = p["hand_l"] + np.array([-0.2, -0.1, 0.0]) * (1 - w)
    p["hand_r"] = p["hand_r"] + np.array([0.2, -0.1, 0.0]) * (1 - w)
    p["foot_l"] = p["foot_l"] * 0.6
    p["foot_r"] = p["foot_r"] * 0.6 + np.array([0.0, 0.05 * w, 0.0])
    lean(p, look=(-6 * w, 0, 0))


def fig_sway(p, t, i, half=True, circles=False):
    b, f, d = beat_at(t)
    period = 4 if half else 2
    ph = ((b + f) / period) * 2 * math.pi
    s = math.sin(ph)
    set_hands(p, "angle_up", "angle_up")
    p["hand_l"] = np.array([0.18 + 0.2 * s, 0.3 + 0.12 * math.cos(ph), 0.12])
    p["hand_r"] = np.array([-0.18 + 0.2 * s, 0.3 - 0.12 * math.cos(ph), 0.12])
    if circles:
        p["hand_l"] = np.array([0.12 + 0.12 * math.cos(ph), 0.42 + 0.08 * math.sin(ph), 0.08])
        p["hand_r"] = np.array([-0.12 + 0.12 * math.cos(ph), 0.42 - 0.08 * math.sin(ph), 0.08])
    p["elbow_l"] = np.array([1.0, -0.5, -0.4])
    p["elbow_r"] = np.array([-1.0, -0.5, -0.4])
    p["root"] = p["root"] + np.array([0.06 * s, 0.0, 0.0])
    p["foot_l"] = p["foot_l"] - np.array([0.06 * s, 0.0, 0.0])
    p["foot_r"] = p["foot_r"] - np.array([0.06 * s, 0.0, 0.0])
    lean(p, side=8 * s, look=(0, 0, 10 * s))


def fig_jazz(p, t):
    set_hands(p, "jazz", "jazz")
    tw = math.sin(t * 38)
    p["hand_l"] = p["hand_l"] + np.array([0.02 * tw, 0.02 * math.sin(t * 29), 0.0])
    p["hand_r"] = p["hand_r"] + np.array([-0.02 * tw, 0.02 * math.cos(t * 31), 0.0])
    step_touch(p, t, 0.08, arms=False)


def fig_sharp(p, t, i, beats):
    """Keskin, köşeli pozlar: her vuruşta bir poz (vogue gibi)."""
    k = 0
    for j, tb in enumerate(beats):
        if t >= tb - 0.06:
            k = j + 1
    table = [("hip", "hip"), ("angle_up", "angle_down"), ("angle_down", "angle_up"), ("up", "hip"), ("v", "v")]
    l, r = table[k % len(table)]
    if i == 2:
        l, r = r, l
    set_hands(p, l, r)
    s = 1 if k % 2 else -1
    lean(p, side=7 * s, turn=10 * s, look=(0, -12 * s, 6 * s))
    p["pelvis"] = p["pelvis"] + np.array([0.0, 0.0, 8 * s])


def fig_heart_cross_wide(p, t, t_heart, t_cross, t_wide):
    if t < t_cross - 0.05:
        set_hands(p, "heart", "heart")
        lean(p, side=5, look=(-4, 0, 8))
    elif t < t_wide - 0.05:
        set_hands(p, "cross", "cross")
        p["hand_r"] = p["hand_r"] + np.array([0.0, 0.03, 0.02])
        lean(p, forward=6, look=(6, 0, 0))
    else:
        set_hands(p, "wide", "wide")
        lean(p, forward=-6, look=(-6, 0, 0))
    stomp(p, t, [t_wide])


def fig_shrug_roll(p, t, i, t_shrug):
    if t < t_shrug + 0.7:
        set_hands(p, "shrug", "shrug")
        lean(p, look=(0, 0, 10))
    else:
        fig_sway(p, t, i, half=False, circles=True)


def fig_think_idea_maru(p, t, i, t_think, t_idea, t_maru):
    if t < t_idea - 0.05:
        p["hand_r"], p["elbow_r"] = hand("chin", "r")
        p["hand_l"], p["elbow_l"] = hand("cross", "l")
        p["hand_l"] = p["hand_l"] + np.array([0.02, -0.08, 0.0])
        lean(p, side=-3, look=(4, -8, -14))
    elif t < t_maru - 0.05:
        p["hand_r"], p["elbow_r"] = hand("up", "r")
        p["hand_l"], p["elbow_l"] = hand("hip", "l")
        lean(p, side=6, look=(-8, 0, 6))
    else:
        set_hands(p, "maru", "maru")
        lean(p, forward=-3, look=(-4, 0, 0))


def fig_pump(p, t, i):
    b, f, d = beat_at(t)
    s = "l" if b % 2 == 0 else "r"
    o = "r" if s == "l" else "l"
    up = pulse(t, beat_time(b), 0.2)
    a, e = hand("fist", s)
    lo, eo = hand("fist_low", s)
    p[f"hand_{s}"] = lo + (a - lo) * (0.4 + 0.6 * up)
    p[f"elbow_{s}"] = e
    p[f"hand_{o}"], p[f"elbow_{o}"] = hand("fist_low", o)
    step_touch(p, t, 0.12, arms=False)


def fig_bloom(p, t, t0):
    u = smooth((t - t0) / 0.45)
    cl, el = hand("chest", "l")
    cr, er = hand("chest", "r")
    vl, _ = hand("v", "l")
    vr, _ = hand("v", "r")
    p["hand_l"] = cl + (vl - cl) * u
    p["hand_r"] = cr + (vr - cr) * u
    p["elbow_l"], p["elbow_r"] = el, er
    lean(p, forward=-8 * u, look=(-10 * u, 0, 0))


def fig_part_clouds(p, t, starts):
    k = max((j for j, s in enumerate(starts) if t >= s - 0.05), default=0)
    u = smooth((t - starts[k]) / 0.55)
    cl, el = hand("clap", "l")
    cr, er = hand("clap", "r")
    ol, _ = hand("out", "l")
    orr, _ = hand("out", "r")
    lift = np.array([0.0, 0.12, 0.05])
    p["hand_l"] = cl + lift + (ol - cl - lift) * u
    p["hand_r"] = cr + lift + (orr - cr - lift) * u
    p["elbow_l"], p["elbow_r"] = el, er
    lean(p, forward=-4 * u, look=(-6, 0, 0))


def fig_peek(p, t, t0, t_open):
    if t < t_open:
        set_hands(p, "face", "face")
        lean(p, forward=6, look=(4, 0, 10))
    else:
        u = smooth((t - t_open) / 0.3)
        fl, el = hand("face", "l")
        fr, er = hand("face", "r")
        vl, _ = hand("v", "l")
        vr, _ = hand("v", "r")
        p["hand_l"], p["hand_r"] = fl + (vl - fl) * u, fr + (vr - fr) * u
        p["elbow_l"], p["elbow_r"] = el, er
        lean(p, forward=-6 * u, look=(-8 * u, 0, 0))


def fig_idol(p, t, i):
    b, f, d = beat_at(t)
    s = 1 if b % 2 == 0 else -1
    up = smooth(f / 0.35)
    a_up, e_up = hand("v", "l" if s > 0 else "r")
    a_dn, e_dn = hand("fist_low", "r" if s > 0 else "l")
    if s > 0:
        p["hand_l"], p["elbow_l"] = a_up * up + hand("fist_low", "l")[0] * (1 - up), e_up
        p["hand_r"], p["elbow_r"] = a_dn, e_dn
    else:
        p["hand_r"], p["elbow_r"] = a_up * up + hand("fist_low", "r")[0] * (1 - up), e_up
        p["hand_l"], p["elbow_l"] = a_dn, e_dn
    step_touch(p, t, 0.15, arms=False)
    lean(p, side=5 * s, look=(0, 8 * s, 5 * s))


def fig_wave_up(p, t, i):
    b, f, d = beat_at(t)
    ph = (b + f) * math.pi
    set_hands(p, "v", "v")
    sw = math.sin(ph)
    p["hand_l"] = p["hand_l"] + np.array([0.12 * sw, -0.04 * abs(sw), 0.0])
    p["hand_r"] = p["hand_r"] + np.array([0.12 * sw, -0.04 * abs(sw), 0.0])
    lean(p, side=6 * sw, look=(0, 0, 8 * sw))


def fig_spotlight(p, t, i):
    b, f, d = beat_at(t)
    ph = (b + f) / 4 * 2 * math.pi
    s = math.sin(ph + i)
    p["hand_r"] = np.array([-0.12 + 0.28 * s, 0.5, 0.12])
    p["elbow_r"] = np.array([0.0, 0.0, -1.0])
    p["hand_l"], p["elbow_l"] = hand("hip", "l")
    lean(p, side=6 * s, look=(-14, 12 * s, 0))


def fig_sky(p, t, i, t0):
    u = smooth((t - t0) / 0.5)
    set_hands(p, "sky", "sky")
    k = smooth((t - 58.4) / (FINAL_HIT - 58.4))
    trem = 0.006 + 0.02 * k
    p["hand_l"] = p["hand_l"] + np.array([trem * math.sin(t * 61), trem * math.sin(t * 47), 0.0])
    p["hand_r"] = p["hand_r"] + np.array([trem * math.sin(t * 57), trem * math.sin(t * 53), 0.0])
    p["foot_l"] = p["foot_l"] + np.array([0.0, 0.0, 0.0])
    p["bounce"] = p["bounce"] + 0.02 * u
    lean(p, forward=-12 * u, look=(-18 * u, 0, 0))


def fig_final(p, t, i):
    if i == 1:
        p["hand_r"], p["elbow_r"] = hand("up", "r")
        p["hand_l"], p["elbow_l"] = hand("hip", "l")
        lean(p, forward=-4, side=4, look=(-4, 0, 8))
    else:
        inner = "l" if i == 0 else "r"                    # merkeze bakan kol
        outer = "r" if i == 0 else "l"
        a, e = hand("point", inner)
        p[f"hand_{inner}"], p[f"elbow_{inner}"] = a, e
        p[f"hand_{outer}"], p[f"elbow_{outer}"] = hand("v", outer)
        s = 1 if i == 0 else -1
        lean(p, side=-8 * s, turn=-14 * s, look=(-6, -18 * s, -6 * s))
        p["foot_l" if i == 0 else "foot_r"] = p["foot_l" if i == 0 else "foot_r"] + np.array([0.08 * s, 0.0, 0.1])


def choreography(i):
    """Dansçının figür listesi: (başlangıç, bitiş, fonksiyon)."""
    red_green = [(0.488, 1.76, 0.49, 0.93), (4.12, 5.13, 4.5, 4.12), (7.27, 8.8, 7.27, 7.7), (11.0, 12.13, 11.0, 11.4)]
    F = []
    for a, b, tr, tg in red_green:
        F.append((a, b, lambda p, t, i, tr=tr, tg=tg: fig_point(p, t, i, tr, tg)))
    F += [
        (1.76, 3.84, lambda p, t, i: step_touch(p, t, 0.12)),
        (3.84, 4.12, lambda p, t, i: set_hands(p, "fist" if i != 1 else "v", "hip" if i != 1 else "v")),
        (4.12, 5.13, lambda p, t, i: fig_clap(p, t, [4.319, 4.737]) if i == 1 else None),
        (5.13, 5.86, lambda p, t, i: (set_hands(p, "fist_low", "fist_low"), stomp(p, t, [5.15, 5.34, 5.55]))),
        (5.86, 6.44, lambda p, t, i: fig_freeze(p, t, i, 5.9, False)),
        (6.44, 7.27, lambda p, t, i: step_touch(p, t, 0.14)),
        (7.27, 8.8, lambda p, t, i: fig_clap(p, t, [7.686, 8.568]) if i == 1 else step_touch(p, t, 0.14)),
        (8.8, 9.68, lambda p, t, i: (set_hands(p, "fist_low", "fist_low"), stomp(p, t, [8.82, 9.05, 9.25, 9.45]))),
        (9.68, 10.6, lambda p, t, i: (set_hands(p, "cross", "cross") if t < 9.72 else set_hands(p, "v", "v"),
                                      lean(p, forward=-5, look=(-8, 0, 0)))),
        (10.6, 11.0, lambda p, t, i: fig_air(p, t) if t > 10.7 else fig_crouch(p, t, 10.6, 10.7)),
        (12.13, 12.7, lambda p, t, i: (set_hands(p, "fist_low", "fist_low"), stomp(p, t, [12.18, 12.376, 12.57]))),
        (12.7, 13.28, lambda p, t, i: fig_freeze(p, t, i, 12.771, False)),
        (13.28, 13.66, lambda p, t, i: fig_freeze(p, t, i, 13.32, True)),
        (13.66, 14.071, lambda p, t, i: fig_crouch(p, t, 13.66, 14.05)),
        (14.071, 14.6, lambda p, t, i: fig_air(p, t, "up")),
        (20.4, 21.3, lambda p, t, i: fig_air(p, t, "v") if t < 21.14 else (set_hands(p, "open", "open"),
                                                                          fig_land(p, t, 21.14))),
        (21.3, 23.6, lambda p, t, i: fig_sway(p, t, i, half=True)),
        (23.6, 24.5, lambda p, t, i: (set_hands(p, "chest", "chest"), lean(p, look=(4, 0, 10)))),
        (24.5, 26.1, lambda p, t, i: fig_jazz(p, t)),
        (26.1, 27.72, lambda p, t, i: fig_sharp(p, t, i, [26.11, 26.215, 26.657, 27.074, 27.492])),
        (27.72, 29.2, lambda p, t, i: fig_beckon(p, t, [28.38, 28.8]) if i == 1 else fig_run(p, t, i)),
        (29.2, 30.62, lambda p, t, i: fig_reach(p, t, 29.2, 30.05)),
        (30.62, 31.5, lambda p, t, i: fig_spin(p, t, 30.68 + 0.08 * i, 31.35 + 0.08 * i)),
        (31.5, 34.6, lambda p, t, i: fig_sway(p, t, i, half=True)),
        (34.6, 37.5, lambda p, t, i: fig_heart_cross_wide(p, t, 34.95, 35.42, 36.06)),
        (37.5, 41.0, lambda p, t, i: fig_shrug_roll(p, t, i, 37.54)),
        (41.0, 44.56, lambda p, t, i: fig_think_idea_maru(p, t, i, 41.07, 41.82, 43.06)),
        (44.56, 45.9, lambda p, t, i: fig_pump(p, t, i)),
        (45.9, 46.8, lambda p, t, i: fig_bloom(p, t, 45.92)),
        (46.8, 47.66, lambda p, t, i: fig_spin(p, t, 46.8 + 0.2 * i, 47.25 + 0.2 * i)),
        (47.66, 48.1, lambda p, t, i: fig_crouch(p, t, 47.66, 48.06)),
        (48.1, 48.5, lambda p, t, i: fig_air(p, t)),
        (48.5, 50.35, lambda p, t, i: fig_part_clouds(p, t, [48.5, 49.36])),
        (50.35, 51.45, lambda p, t, i: fig_peek(p, t, 50.4, 50.95)),
        (51.45, 52.95, lambda p, t, i: fig_idol(p, t, i)),
        (52.95, 54.7, lambda p, t, i: fig_wave_up(p, t, i)),
        (54.7, 55.2, lambda p, t, i: fig_air(p, t, "v")),
        (55.2, 57.65, lambda p, t, i: fig_spotlight(p, t, i)),
        (57.65, FINAL_HIT - 0.06, lambda p, t, i: fig_sky(p, t, i, 57.72)),
        (FINAL_HIT - 0.06, DURATION + 1, lambda p, t, i: fig_final(p, t, i)),
    ]
    F.sort(key=lambda s: s[0])
    return F


def target_pose(i, t, figs):
    """Figürleri üst üste uygular; figür sınırlarında 0.12 sn'lik geçişle karıştırır."""
    p = base_pose(i, t)
    for a, b, fn in figs:
        if a - 0.12 <= t <= b + 0.12:
            q = {k: np.array(v, float) for k, v in p.items()}
            fn(q, t, i)
            p = mix_pose(p, q, win(t, a, b, 0.12))
    return p


# ---------------------------------------------------------------- yüz ifadeleri

def face_at(i, t):
    blink_period = (3.1, 3.7, 2.9)[i]
    ph = (t + i * 1.3) % blink_period
    blink = ph < 0.11
    if 34.95 <= t < 35.4 or 43.06 <= t < 44.4 or 50.4 <= t < 50.95:
        return 3                                         # ^^
    if (i == 0 and 12.771 <= t < 13.2) or (i == 2 and 13.32 <= t < 13.66) or (i == 1 and t >= FINAL_HIT):
        return 4                                         # göz kırpma
    if blink:
        return 1
    if 48.06 <= t < FINAL_HIT or 3.84 <= t < 4.12 or 10.7 <= t < 11.0 or 28.3 <= t < 29.2 or 14.0 <= t < 14.6:
        return 2                                         # açık ağız
    return 0


# ---------------------------------------------------------------- fizik bake

SPRINGS = {  # (Hz, sönüm): gövde sert, eller/ayaklar gevşek
    "root": (5.0, 0.8), "yaw": (6.0, 0.8), "bounce": (9.0, 0.75),
    "pelvis": (8.0, 0.8), "spine": (7.5, 0.75), "chest": (7.0, 0.7), "neck": (6.0, 0.6), "head": (5.0, 0.5),
    "hand_l": (6.5, 0.55), "hand_r": (6.5, 0.55), "elbow_l": (5.0, 0.7), "elbow_r": (5.0, 0.7),
    "foot_l": (12.0, 0.85), "foot_r": (12.0, 0.85), "knee_l": (6.0, 0.8), "knee_r": (6.0, 0.8),
}


def capsule_push(P, a, b, r):
    """P (n,3) noktalarını a-b kapsülünün (yarıçap r) dışına iter."""
    ab = b - a
    tt = np.clip(((P - a) @ ab) / (ab @ ab + 1e-12), 0, 1)
    c = a + tt[:, None] * ab
    d = P - c
    dist = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    inside = dist < r
    return np.where(inside, c + d / dist * r, P)


def bake(dancers, t0=-0.3, t1=DURATION, fps=FPS, sub=4):
    """Tüm karelerin iskeletini, saç zincirlerini ve etek düğümlerini hesaplar."""
    n_frames = int(round(t1 * fps))
    warm = int(round(-t0 * fps))
    out = []
    for i, d in enumerate(dancers):
        figs = choreography(i)
        springs = None
        R_all = np.zeros((n_frames, len(JOINT_NAMES), 3, 3), np.float32)
        P_all = np.zeros((n_frames, len(JOINT_NAMES), 3), np.float32)
        faces = np.zeros(n_frames, np.int8)
        vis = np.zeros(n_frames, bool)
        chains_state = None
        chain_out = [np.zeros((n_frames, ch["nodes"], 3), np.float32) for ch in d.chains]
        skirt_out = np.zeros((n_frames, len(d.skirt[0]), SKIRT_NODES, 3), np.float32)
        dt = 1.0 / fps
        prev_y = 0.0
        for fr in range(-warm, n_frames):
            t = fr / fps
            tp = target_pose(i, t, figs)
            y, dip = vertical(t)
            if springs is None:
                springs = {k: Spring(v, *SPRINGS[k]) for k, v in tp.items()}
            pose = {k: springs[k].step(v, dt) for k, v in tp.items()}
            pose = {k: np.array(v) for k, v in pose.items()}
            # zıplarken hava sürüklemesi: eller yükselişte geride, düşüşte havada
            vyy = (y - prev_y) * fps
            prev_y = y
            drag = 0.05 * math.tanh(vyy / 3.0)
            pose["hand_l"] = pose["hand_l"] + np.array([0.0, -drag, 0.0])
            pose["hand_r"] = pose["hand_r"] + np.array([0.0, -drag, 0.0])
            pose["root"] = pose["root"] + np.array([0.0, y, 0.0])
            pose["foot_l"] = pose["foot_l"] + np.array([0.0, y, 0.0])
            pose["foot_r"] = pose["foot_r"] + np.array([0.0, y, 0.0])
            sk = dict(root=pose["root"], yaw=float(pose["yaw"][0]), bounce=float(pose["bounce"][0]) + dip)
            for k in ("pelvis", "spine", "chest", "neck", "head"):
                sk[k] = tuple(pose[k])
            for k in ("hand_l", "hand_r", "elbow_l", "elbow_r", "foot_l", "foot_r", "knee_l", "knee_r"):
                sk[k] = pose[k]
            Rw, Pw = solve_skeleton(sk)
            # saç zincirleri ve etek: dünya uzayında PBD
            if chains_state is None:
                chains_state = make_sims(d, Rw, Pw)
            hair_pts, skirt_pts = step_sims(d, chains_state, Rw, Pw, dt, sub)
            if fr >= 0:
                for k, name in enumerate(JOINT_NAMES):
                    R_all[fr, k] = Rw[name]
                    P_all[fr, k] = Pw[name]
                for k, pts in enumerate(hair_pts):
                    chain_out[k][fr] = pts
                skirt_out[fr] = skirt_pts
                faces[fr] = face_at(i, t)
                vis[fr] = t >= 0.47 and not (HIDE[0] <= t < HIDE[1])
        out.append(dict(R=R_all, P=P_all, chains=chain_out, skirt=skirt_out, face=faces, vis=vis))
    return out


def _colliders(Rw, Pw):
    head_c = Pw["head"] + Rw["head"] @ (HEAD_C * HEAD_S)
    torso_a = Pw["pelvis"] + Rw["pelvis"] @ np.array([0.0, 0.05, -0.01])
    torso_b = Pw["chest"] + Rw["chest"] @ np.array([0.0, 0.1, -0.01])
    return head_c, (torso_a, torso_b)


class ChainSim:
    """Saç zincirleri / etek kaburgaları için PBD (position based dynamics), zincirler üzerinde vektörel.

    Her alt adım: hız + yerçekimi -> tahmin; kök noktası kafa/bele kilitli (alt adımlarda
    ara değerlenir); yumuşak şekil yayı (saç modelini korur); mesafe kısıtları (uzamaz);
    çarpışma (kafa küresi, gövde/bacak kapsülleri); hız = düzeltilmiş konum farkı.
    """

    def __init__(self, n_nodes, seg, stiff, anchors, dirs, damp=0.985, iters=3):
        self.n = np.asarray(n_nodes)
        self.nm = int(self.n.max())
        self.seg = np.asarray(seg, float)
        self.stiff = np.asarray(stiff, float)
        self.mask = (np.arange(self.nm)[None, :] < self.n[:, None]).astype(float)
        k = np.arange(self.nm)[None, :, None]
        self.x = anchors[:, None, :] + dirs[:, None, :] * self.seg[:, None, None] * k
        self.v = np.zeros_like(self.x)
        self.prev_anchor = anchors.copy()
        self.damp, self.iters = damp, iters

    def step(self, anchors, dirs, dt, sub, push):
        h = dt / sub
        g = np.array([0.0, -9.8, 0.0])
        a0 = self.prev_anchor
        for s in range(sub):
            a = a0 + (anchors - a0) * (s + 1) / sub
            self.v = (self.v + g * h) * self.damp
            p = self.x + self.v * h
            p[:, 0] = a
            for j in range(1, self.nm):                   # şekil yayı: kökten uca, uca doğru gevşer
                w = self.stiff * (1.0 - 0.6 * j / self.n) * self.mask[:, j]
                tgt = p[:, j - 1] + dirs * self.seg[:, None]
                p[:, j] += (tgt - p[:, j]) * w[:, None]
            for _ in range(self.iters):
                for j in range(1, self.nm):               # mesafe kısıtları (kök sabit)
                    d = p[:, j] - p[:, j - 1]
                    L = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
                    corr = (L - self.seg[:, None]) / L * d * self.mask[:, j:j + 1]
                    if j == 1:
                        p[:, 1] -= corr
                    else:
                        p[:, j - 1] += corr * 0.5
                        p[:, j] -= corr * 0.5
                p[:, 1:] = push(p[:, 1:])
            self.v = (p - self.x) / h
            self.x = p
        self.prev_anchor = anchors.copy()
        return self.x


def make_sims(d, Rw, Pw):
    chains = d.chains
    anchors = np.array([Pw["head"] + Rw["head"] @ ch["anchor"] * HEAD_S for ch in chains])
    dirs = np.array([Rw["head"] @ ch["rest"] for ch in chains])
    hair = ChainSim([ch["nodes"] for ch in chains], [ch["length"] / (ch["nodes"] - 1) for ch in chains],
                    [ch["stiff"] * 3.0 for ch in chains], anchors, dirs, damp=0.975)
    A, D, length = _skirt_frame(d, Rw, Pw)
    skirt = ChainSim([SKIRT_NODES] * len(A), [length / (SKIRT_NODES - 1)] * len(A), [0.35] * len(A), A, D,
                     damp=0.96)
    return hair, skirt


def _skirt_frame(d, Rw, Pw):
    anchors, dirs, length = d.skirt
    return Pw["pelvis"] + anchors @ Rw["pelvis"].T, dirs @ Rw["pelvis"].T, length


def step_sims(d, sims, Rw, Pw, dt, sub):
    hair, skirt = sims
    head_c, (ta, tb) = _colliders(Rw, Pw)
    rr = 0.155 * HEAD_S

    def push_hair(P):
        shp = P.shape
        Q = P.reshape(-1, 3)
        dv = Q - head_c
        dist = np.linalg.norm(dv, axis=1, keepdims=True) + 1e-9
        Q = np.where(dist < rr, head_c + dv / dist * rr, Q)
        Q = capsule_push(Q, ta, tb, 0.13)
        return Q.reshape(shp)

    thighs = [(Pw[f"hip_{s}"], Pw[f"hip_{s}"] + (Pw[f"knee_{s}"] - Pw[f"hip_{s}"]) * 0.8) for s in ("l", "r")]

    def push_skirt(P):
        shp = P.shape
        Q = P.reshape(-1, 3)
        for a, b in thighs:
            Q = capsule_push(Q, a, b, 0.075)
        return Q.reshape(shp)

    anchors = np.array([Pw["head"] + Rw["head"] @ ch["anchor"] * HEAD_S for ch in d.chains])
    dirs = np.array([Rw["head"] @ ch["rest"] for ch in d.chains])
    hx = hair.step(anchors, dirs, dt, sub, push_hair)
    A, D, _ = _skirt_frame(d, Rw, Pw)
    sx = skirt.step(A, D, dt, sub, push_skirt)
    return [hx[k, :ch["nodes"]].copy() for k, ch in enumerate(d.chains)], sx.copy()


def save_bake(path, dancers=None):
    dancers = dancers or [Dancer(n) for n in NAMES]
    data = bake(dancers)
    arrays = {}
    for i, dd in enumerate(data):
        arrays[f"R{i}"] = dd["R"]
        arrays[f"P{i}"] = dd["P"]
        arrays[f"skirt{i}"] = dd["skirt"]
        arrays[f"face{i}"] = dd["face"]
        arrays[f"vis{i}"] = dd["vis"]
        for k, c in enumerate(dd["chains"]):
            arrays[f"chain{i}_{k}"] = c
    np.savez(path, **arrays)
    return path


def load_bake(path):
    z = np.load(path)
    out = []
    for i in range(3):
        chains = []
        k = 0
        while f"chain{i}_{k}" in z:
            chains.append(z[f"chain{i}_{k}"])
            k += 1
        out.append(dict(R=z[f"R{i}"], P=z[f"P{i}"], skirt=z[f"skirt{i}"], face=z[f"face{i}"], vis=z[f"vis{i}"],
                        chains=chains))
    return out
