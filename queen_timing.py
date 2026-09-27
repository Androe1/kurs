"""QUEEN (LiSA) fan yapımı lyric video - zamanlama verisi (saniye, şarkının başından).

Şarkının 0:00-1:00 bölümü analiz edilerek çıkarıldı:
  - vuruş ızgarası: librosa beat_track (~141 BPM, ilk vuruş 0.488 sn)
  - vokal: stereo merkez kanal + armonik ayrıştırma, Melodia perde takibi;
    her parçanın başlangıcı vokal girişine (±0.04 sn) oturtuldu
  - patlama anları: yüksek frekans (zil) sıçramaları ve bölüm geçişleri

Sözlerin kendisi burada yok. Kullanıcının verdiği metin input/queen_sozler.txt
dosyasından okunur; oradaki parçalar LINES içindeki parçalarla sırayla eşleşir.

Parça türleri:
  rog      "(Red or Green?)" arka vokali: kırmızı/yeşil lamba tabelası
  main     büyük kanji, altında küçük romaji
  yeah     köşeye yapışan "Yeah" etiketi
  ratatta  hece hece damgalanan kısa satır
  light    "Red Light?" / "Green Light?" (lambası yanan şerit)
  chase    ekranı yarıp geçen "Chase me!" damgası
  moon     nakarattaki "Moonlight"
  tonight  nakarattaki dev "Tonight" patlaması
"""

DURATION = 61.0              # video uzunluğu
FINAL_HIT = 60.093           # son uzun notanın bittiği ölçü başı: final patlaması
AUDIO_FADE = (60.10, 60.42)  # şarkı burada kısılır; yerine final patlamasının sesi (sound.impact) yankılanır

# librosa beat_track ile bulunan vuruşlar (0-61 sn); her 4'ün ilki ölçü başı
BEATS = [
    0.488, 0.929, 1.37, 1.788, 2.229, 2.647, 3.065, 3.483, 3.901, 4.319, 4.737, 5.132, 5.55, 5.991,
    6.432, 6.85, 7.268, 7.686, 8.127, 8.568, 8.986, 9.404, 9.822, 10.263, 10.704, 11.122, 11.564,
    11.981, 12.376, 12.771, 13.189, 13.63, 14.071, 14.489, 14.884, 15.302, 15.72, 16.161, 16.579,
    17.02, 17.438, 17.856, 18.274, 18.692, 19.11, 19.505, 19.9, 20.317, 20.735, 21.13, 21.525,
    21.943, 22.361, 22.802, 23.22, 23.661, 24.079, 24.52, 24.938, 25.379, 25.797, 26.215, 26.657,
    27.074, 27.492, 27.934, 28.375, 28.793, 29.234, 29.652, 30.07, 30.511, 30.929, 31.37, 31.788,
    32.229, 32.647, 33.088, 33.506, 33.948, 34.366, 34.807, 35.225, 35.666, 36.084, 36.525,
    36.943, 37.384, 37.802, 38.243, 38.661, 39.079, 39.497, 39.938, 40.356, 40.774, 41.215,
    41.657, 42.098, 42.516, 42.957, 43.375, 43.793, 44.234, 44.652, 45.07, 45.511, 45.952, 46.37,
    46.788, 47.229, 47.647, 48.089, 48.506, 48.948, 49.366, 49.784, 50.225, 50.643, 51.084,
    51.525, 51.943, 52.384, 52.802, 53.243, 53.661, 54.079, 54.52, 54.938, 55.356, 55.798,
    56.216, 56.657, 57.075, 57.516, 57.934, 58.375, 58.793, 59.234, 59.652, 60.093, 60.511, 60.952,
]
BARS = BEATS[::4]

# Her satır: parçalar (tür, vokal başı, vokal sonu) ve yazının ekrandan çıktığı an (end).
LINES = [
    # 0.5-14 sn: dört "Red or Green?" satırı, her biri 2 ölçü
    dict(end=4.10, parts=[("rog", 0.49, 1.70), ("main", 1.76, 3.72), ("yeah", 3.88, 4.10)]),
    dict(end=7.24, parts=[("rog", 4.12, 5.10), ("ratatta", 5.15, 5.80), ("light", 5.90, 6.30),
                          ("light", 6.47, 7.24)]),
    dict(end=10.98, parts=[("rog", 7.27, 8.78), ("main", 8.82, 9.66), ("main", 9.71, 10.38),
                           ("yeah", 10.75, 10.98)]),
    dict(end=14.07, parts=[("rog", 11.00, 12.10), ("ratatta", 12.13, 12.62), ("light", 12.76, 13.15),
                           ("light", 13.32, 13.97)]),
    # 14.07-21 sn: sözsüz fırtına bölümü (ANDROE STUDIO)
    # 21-34 sn: verse
    dict(end=24.50, parts=[("main", 21.14, 22.65), ("main", 22.69, 24.42)]),
    dict(end=27.72, parts=[("main", 24.55, 26.08), ("main", 26.11, 27.65)]),
    dict(end=29.17, parts=[("chase", 28.38, 28.70), ("chase", 28.80, 29.12)]),
    dict(end=31.58, parts=[("main", 29.20, 30.45), ("main", 30.68, 31.58)]),
    dict(end=34.62, parts=[("main", 31.62, 32.35), ("main", 32.41, 34.25)]),
    # 35-48 sn: nakarat öncesi
    dict(end=37.50, parts=[("main", 34.95, 35.93), ("main", 36.06, 37.40)]),
    dict(end=40.98, parts=[("main", 37.54, 38.16), ("main", 38.37, 40.72)]),
    dict(end=44.56, parts=[("main", 41.07, 41.65), ("main", 41.82, 43.00), ("main", 43.06, 44.40)]),
    dict(end=48.03, parts=[("main", 44.62, 45.85), ("main", 45.92, 47.85)]),
    # 48.1-60.1 sn: nakarat (son uzun nota 60.09'da biter)
    dict(end=51.45, parts=[("moon", 48.06, 48.40), ("main", 48.42, 50.22), ("main", 50.40, 51.36)]),
    dict(end=54.74, parts=[("main", 51.49, 52.83), ("main", 52.96, 54.60)]),
    dict(end=FINAL_HIT, parts=[("tonight", 54.78, 55.25), ("main", 55.27, 57.60), ("main", 57.72, FINAL_HIT)]),
]

# Patlama / sarsıntı anları: (zaman, güç 1-4, tür)
#   1 küçük vuruş, 2 orta, 3 büyük (flaş + sarsıntı), 4 dev (beyaz patlama, ters renk, şok dalgası)
HITS = [
    (0.488, 3, "start"),
    (7.268, 2, "bass"),                         # bas ve davul girer
    (12.771, 3, "red"), (13.32, 3, "green"),    # durak vuruşları: Red Light? / Green Light?
    (14.071, 4, "drop"),                        # fırtına bölümü patlaması
    (15.72, 2, "bolt"), (17.438, 3, "bolt"), (19.11, 2, "bolt"),
    (20.735, 2, "whip"),
    (21.41, 1, "scratch"), (22.13, 1, "scratch"), (23.93, 2, "scratch"),
    (24.65, 1, "glare"), (25.40, 2, "glare"), (25.95, 1, "glare"), (26.11, 2, "glare"),
    (27.492, 1, "bar"), (28.375, 3, "chase"), (28.80, 3, "chase"), (29.234, 2, "bar"),
    (34.366, 2, "bar"), (36.06, 3, "seal"), (38.37, 1, "bar"),
    (41.215, 2, "bar"), (43.06, 3, "correct"), (44.652, 2, "bar"), (46.37, 1, "bar"), (47.23, 1, "bar"),
    (48.089, 4, "chorus"),
    (48.42, 2, "clouds"), (50.40, 2, "moon"), (51.49, 1, "bar"), (52.96, 1, "bar"),
    (54.86, 4, "tonight"),
    (56.657, 2, "bar"), (58.375, 2, "bar"),
    (FINAL_HIT, 4, "final"),
]

# Sahneler: (başlangıç, ad)
SCENES = [
    (0.0, "boot"),
    (0.488, "signal"),
    (14.071, "storm"),
    (20.735, "scar"),
    (24.52, "glare"),
    (27.72, "chase"),
    (29.19, "robe"),
    (31.60, "yura"),
    (34.366, "lovehate"),
    (37.50, "swallow"),
    (40.98, "answer"),
    (44.56, "bloom"),
    (48.089, "moon"),
    (54.86, "tonight"),
    (FINAL_HIT, "end"),
]
