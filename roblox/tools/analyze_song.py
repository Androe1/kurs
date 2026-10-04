#!/usr/bin/env python3
"""Şarkıyı analiz edip Roblox animasyon sisteminin okuyacağı SongMap.luau dosyasını üretir.

Kullanım:
    pip install librosa numpy scipy
    python roblox/tools/analyze_song.py fever_dream.mp3 \
        -o roblox/src/ReplicatedStorage/BandPerformance/Data/SongMap.luau

Bu bir kulak değil sinyal analizidir: tempo/ızgara, her 16'lık vuruştaki davul/gitar/bas
enerjisi, yarım ölçü başına akor kökü ve bölüm enerjisi çıkar. Vokal ayrıştırılamaz
(distorsiyonlu gitar duvarı perdeyi maskeliyor) - vokal sadece bölüm enerjisine bağlanır.
"""
import argparse
import json
import sys

import librosa
import numpy as np

SR = 22050
HOP = 128
FPS = SR / HOP
SLOTS = 16  # ölçü başına 16'lık
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def band_flux(S, fr, lo, hi):
    b = S[(fr >= lo) & (fr < hi)].sum(0)
    return np.maximum(0, np.diff(np.log1p(b), prepend=0))


def slot_max(env, pts, w=4):
    idx = np.clip((pts * FPS).astype(int), 0, len(env) - 1)
    return np.array([env[max(0, i - w): i + w + 1].max() for i in idx])


def quant(v, lo_q=40, hi_q=98):
    """Değerleri 0..9'a çevir: alt yüzdelik altı = 0 (vuruş yok)."""
    lo, hi = np.percentile(v, lo_q), np.percentile(v, hi_q)
    return np.clip(np.round((v - lo) / max(hi - lo, 1e-9) * 9), 0, 9).astype(int)


def detect_grid(y):
    """BPM ve ızgara ofsetini bul; ilk büyük (loudness) vuruşu birinci zaman olarak al."""
    H, P = librosa.effects.hpss(y)
    S = np.abs(librosa.stft(P, n_fft=1024, hop_length=HOP))
    fr = librosa.fft_frequencies(sr=SR, n_fft=1024)
    env = band_flux(S, fr, 40, 200) + band_flux(S, fr, 200, 600) + band_flux(S, fr, 2000, 8000)

    def score(T, o):
        pts = np.arange(o, len(env) / FPS - 0.1, T)
        idx = (pts * FPS).astype(int)
        return np.mean([env[max(0, i - 3): i + 4].max() for i in idx])

    best = max(((score(60 / b / 2, o), b, o)
                for b in np.arange(100, 200.01, 0.5)
                for o in np.arange(0, 60 / b / 2, 60 / b / 2 / 12)))
    bpm = best[1]
    # ince ayar
    fine = max(((score(60 / b / 2, o), b, o)
                for b in np.arange(bpm - 1, bpm + 1.01, 0.1)
                for o in np.arange(0, 60 / b / 2, 60 / b / 2 / 48)))
    bpm, off8 = fine[1], fine[2]
    beat = 60 / bpm
    # ilk büyük vuruş = ölçü başı (şarkıda 4 ölçülük introdan sonra tam grup giriyor)
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=HOP)[0]
    d = np.diff(np.convolve(rms, np.ones(8) / 8, "same"))
    drop = np.argmax(d[: int(12 * FPS)]) / FPS
    # drop'a en yakın 16'lık ızgara noktası, sonra geriye ölçü ölçü sar
    step = beat / 4
    g = off8 + np.round((drop - off8) / step) * step
    bar = beat * 4
    t0 = g - np.floor(g / bar) * bar  # ilk ölçü başı (0..bar)
    return bpm, t0, drop, H, P


def chord_roots(H, t0, bpm, nbar):
    """Yarım ölçü başına en olası akor kökü (majör/minör üçlü şablon eşleme)."""
    chroma = librosa.feature.chroma_cqt(y=H, sr=SR, hop_length=512, n_chroma=12, fmin=librosa.note_to_hz("C2"))
    ct = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=SR, hop_length=512)
    tmpl = []
    for r in range(12):
        for q, third in (("m", 3), ("M", 4)):
            v = np.zeros(12); v[r] = 1.0; v[(r + third) % 12] = 0.8; v[(r + 7) % 12] = 0.9
            tmpl.append((r, q, v / np.linalg.norm(v)))
    beat = 60 / bpm
    out = []
    for h in range(nbar * 2):
        a, b = t0 + h * 2 * beat, t0 + (h + 1) * 2 * beat
        c = chroma[:, (ct >= a) & (ct < b)].mean(1) if np.any((ct >= a) & (ct < b)) else np.zeros(12)
        if c.sum() < 1e-6:
            out.append((0, "m", 0.0)); continue
        c = c / np.linalg.norm(c)
        sc = [(float(c @ v), r, q) for r, q, v in tmpl]
        s, r, q = max(sc)
        out.append((r, q, s))
    return out


def bass_notes(y, t0, bpm, nbar):
    """Her vuruşta (1/4) baskın alçak nota (MIDI)."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, 200, "low", fs=SR, output="sos")
    low = sosfiltfilt(sos, y)
    f0, vf, _ = librosa.pyin(low, fmin=35, fmax=130, sr=SR, frame_length=4096, hop_length=512)
    ft = librosa.times_like(f0, sr=SR, hop_length=512)
    beat = 60 / bpm
    notes = []
    for k in range(nbar * 4):
        a, b = t0 + k * beat, t0 + (k + 1) * beat
        sel = (ft >= a) & (ft < b) & ~np.isnan(f0)
        notes.append(int(round(librosa.hz_to_midi(np.median(f0[sel])))) if sel.sum() >= 3 else 0)
    return notes


def sections(energy, brightness):
    """Ölçü bazlı özellikten bölüm sınırları (agglomerative) ve etiket."""
    feat = np.vstack([energy, brightness])
    feat = (feat - feat.mean(1, keepdims=True)) / (feat.std(1, keepdims=True) + 1e-9)
    # 4 ölçülük pencereye indir
    k = 4
    n = feat.shape[1] // k
    sm = feat[:, : n * k].reshape(2, n, k).mean(2)
    nseg = max(4, min(9, n // 3))
    b = librosa.segment.agglomerative(sm, nseg)
    starts = sorted(set([0] + [int(x) * k for x in b]))
    return starts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default="SongMap.luau")
    ap.add_argument("--json", help="isteğe bağlı: ham JSON de yaz")
    a = ap.parse_args()

    y, _ = librosa.load(a.audio, sr=SR, mono=True)
    dur = len(y) / SR
    bpm, t0, drop, H, P = detect_grid(y)
    beat = 60 / bpm
    bar = beat * 4
    nbar = int((dur - t0) / bar)
    step = beat / 4
    print(f"bpm={bpm:.2f} ilk ölçü başı={t0:.3f}s büyük vuruş={drop:.3f}s ölçü={nbar}", file=sys.stderr)

    S = np.abs(librosa.stft(P, n_fft=1024, hop_length=HOP))
    fr = librosa.fft_frequencies(sr=SR, n_fft=1024)
    pts = t0 + np.arange(nbar * SLOTS) * step
    kick = quant(slot_max(band_flux(S, fr, 40, 160), pts))
    snare = quant(slot_max(band_flux(S, fr, 200, 500), pts))
    hat = quant(slot_max(band_flux(S, fr, 6000, 11000), pts))
    # çarpma: sert yüksek frekans + sonrasındaki uzun sürme (0.35 sn içindeki ortalama)
    hi = S[(fr >= 4000) & (fr < 12000)].sum(0)
    hif = band_flux(S, fr, 4000, 12000)
    crash_raw = np.array([
        hif[max(0, int(t * FPS) - 4): int(t * FPS) + 5].max() *
        (hi[int(t * FPS) + int(0.12 * FPS): int(t * FPS) + int(0.4 * FPS)].mean() / (hi[max(0, int(t * FPS) - 8): int(t * FPS) + 1].mean() + 1e-6))
        if int(t * FPS) + int(0.4 * FPS) < len(hi) else 0.0
        for t in pts])
    crash = np.where(crash_raw > np.percentile(crash_raw, 96), quant(crash_raw, 96, 100), 0)
    # gitar atağı: harmonik katmanda 500-4000 Hz akış
    SH = np.abs(librosa.stft(H, n_fft=1024, hop_length=HOP))
    gtr = quant(slot_max(band_flux(SH, fr, 500, 4000), pts))

    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    cent = librosa.feature.spectral_centroid(y=y, sr=SR, hop_length=HOP)[0]
    energy, bright = [], []
    for i in range(nbar):
        s, e = int((t0 + i * bar) * FPS), int((t0 + (i + 1) * bar) * FPS)
        energy.append(float(rms[s:e].mean())); bright.append(float(cent[s:e].mean()))
    energy = np.array(energy); bright = np.array(bright)
    e01 = np.clip((energy - energy.min()) / (energy.max() - energy.min() + 1e-9), 0, 1)

    roots = chord_roots(H, t0, bpm, nbar)
    bass = bass_notes(y, t0, bpm, nbar)
    secs = sections(energy, bright)

    def lane(arr, i):
        return "".join(str(int(v)) if v else "." for v in arr[i * SLOTS:(i + 1) * SLOTS])

    L = []
    L.append("--!strict\n--[[ OTOMATİK ÜRETİLDİ: roblox/tools/analyze_song.py - elle düzenleme, aracı yeniden çalıştır.")
    L.append(f"     kaynak: {a.audio}  süre: {dur:.2f}s ]]")
    L.append("return {")
    L.append(f"\tbpm = {bpm:.3f},\n\tbeatsPerBar = 4,\n\tslotsPerBar = {SLOTS},")
    L.append(f"\tfirstBarTime = {t0:.4f}, -- ilk ölçü başı (sn)\n\tdropTime = {drop:.3f},\n\tduration = {dur:.3f},\n\tbars = {nbar},")
    L.append("\tsectionStarts = {" + ", ".join(str(s) for s in secs) + "}, -- ölçü indeksi (0 tabanlı)")
    L.append("\tenergy = {" + ", ".join(f"{v:.2f}" for v in e01) + "}, -- ölçü başına 0..1")
    L.append("\tbass = {" + ", ".join(str(n) for n in bass) + "}, -- vuruş başına MIDI (0=yok)")
    L.append("\tchords = {")
    for r, q, s in roots:
        L.append(f'\t\t{{{r}, "{q}", {s:.2f}}}, -- {NOTE[r]}{q}')
    L.append("\t}, -- yarım ölçü başına {kök pc, kalite, güven}")
    L.append("\tlanes = { -- ölçü başına 16 hane: 0-9 şiddet, '.' yok")
    for i in range(nbar):
        L.append(f'\t\t{{k="{lane(kick, i)}", s="{lane(snare, i)}", h="{lane(hat, i)}", c="{lane(crash, i)}", g="{lane(gtr, i)}"}},')
    L.append("\t},\n}")
    with open(a.out, "w") as f:
        f.write("\n".join(L) + "\n")
    if a.json:
        json.dump({"bpm": bpm, "t0": t0, "bars": nbar}, open(a.json, "w"))
    # özet
    print("bölüm başlangıçları (ölçü):", secs, file=sys.stderr)
    for i in range(min(nbar, 12)):
        print(f"{i:3d} K {lane(kick,i)} S {lane(snare,i)} H {lane(hat,i)} C {lane(crash,i)} G {lane(gtr,i)} e={e01[i]:.2f}", file=sys.stderr)


if __name__ == "__main__":
    main()
