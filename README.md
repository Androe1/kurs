# Androe Studio - Intro Animasyonu

Simsiyah ekran, beyaz yazı: Roblox oyun stüdyosu **Androe Studio** için
5 saniyelik, ses efektli logo intro'su. Görüntü de ses de tamamen kodla
üretilir; hazır video, görsel ya da ses dosyası kullanılmaz.

Hazır video: [`output/androe_studio_intro.mp4`](output/androe_studio_intro.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo)

## Akış

| Saniye      | Görüntü                                                                  | Ses                                  |
|-------------|--------------------------------------------------------------------------|--------------------------------------|
| 0.1 - 0.7   | Beyaz, 3B eğik kare ikon derinlikten dönerek gelir ve ortaya oturur      | yaklaştıkça yükselen "vuuum", vuruş  |
| 0.85 - 1.3  | İkon sağa yuvarlanır, arkasından ANDROE çıkar                            | whoosh + her harfe yükselen nota     |
| 1.6 - 2.1   | İkon sola döner: ANDROE'yi yutar, arkasından STUDIO çıkar                | whoosh + alçalan notalar             |
| 2.3 - 2.8   | İkon yeniden sağa gider, STUDIO'yu iter, solundan ANDROE çıkar           | whoosh + notalar                     |
| 2.9 - 3.3   | İkon ışığı içine çeker (yazılar gümüşe söner), ince bir ışık çizgisine dönüşüp bir noktaya çöker; kelimeler süzülerek birleşir | yükselen gerilim, iki yandan whoosh |
| 3.3 - 3.95  | Işık noktasından iki yana yayılan dalgalar yazıyı bembeyaz yapar         | çan, ışıltı, sıcak akor              |
| 3.95 - 4.9  | Ekranda yalnızca "ANDROE STUDIO" kalır, sonra yumuşakça kararır          | ses söner                            |

## Çalıştırma

```bash
pip install -r requirements.txt
python intro.py
```

Video `output/androe_studio_intro.mp4` olarak yazılır. Diğer seçenekler:

```bash
python intro.py --width 3840 --height 2160 -o output/androe_studio_intro_4k.mp4   # 4K
python intro.py --still 3.0                                                     # tek kareyi PNG kaydet
```

Linux'ta `skia-python` için `libegl1` paketi gerekebilir (`sudo apt install libegl1`).

## Dosyalar

- `intro.py` - kareleri ve sesi üretip ffmpeg ile MP4'e dönüştürür
- `scene.py` - görsel sahne: 3B ikon, yazıların ikonun arkasından çıkışı, efektler
- `sound.py` - ses tasarımı: tüm efektler numpy ile sentezlenir
- `fonts/` - Montserrat yazı tipi (SIL Open Font License, bkz. `fonts/OFL.txt`)

## Düzenleme

- Zamanlama: `scene.py` başındaki `T_IN`, `T_MOVES`, `T_EXIT`, `T_GLIDE`, `T_SHINE`, `T_OUT` (ses de bunlara göre kendini ayarlar)
- İkon: `ICON_TILT` (eğiklik), `ICON_HOLE` (delik), `ICON_DEPTH` (kalınlık), `ICON_BIG` / `ICON_SMALL` (boyut)
- Yazı boyutu ve aralıklar: `FONT_SIZE`, `TRACK`, `GAP`
- Notalar ve akor: `sound.py` içindeki `NOTES` ve `CHORD`

---

# NexDev - Intro Animasyonu (7 saniye)

Hazır video: [`output/nexdev_intro.mp4`](output/nexdev_intro.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo). Logoya sadık: Inter Black, tek satır
"NexDev", Nex beyaz, Dev sarı (#FFCC69). Ekranda logodan başka yazı yok.

| Saniye      | Görüntü                                                                        | Ses                                   |
|-------------|--------------------------------------------------------------------------------|---------------------------------------|
| 0.2 - 0.8   | Beş 3B küp takla atarak belirir; yüzlerinde build, VFX, SFX, modelleme, script sembolleri | blok "tok" sesleri + yükselen notalar |
| 2.0         | Küpler dalga hâlinde sağa sola döner                                           | ışıltı, hafif akor zemini             |
| 2.85 - 4.6  | Rubik küpü gibi sağa, sola, ileri, geri dönerek sıralanır, N e x D e v çözülür | plastik "klak"lar, whoosh, gerilim    |
| 4.6 - 5.4   | Kıvılcımlar saçılır; küpler erir, harfler "NexDev" logosuna toplanır          | derin vuruş, çan, akor                |
| 5.6 - 6.9   | Logonun üzerinden ışık geçer, video siyah biter                                | ses söner                             |

```bash
python nexdev.py                  # output/nexdev_intro.mp4
python nexdev.py --still 4.0      # tek kareyi PNG kaydet
```

- `nexdev.py` - videoyu üretir
- `nexdev_scene.py` - küpler, yüz dokuları (semboller ve harfler), Rubik dönüşleri, logo
- `nexdev_sound.py` - NexDev ses tasarımı (sound.py'deki araçları kullanır)
Efektler: zeminde silik yansıma, küp kenarlarında ince ışık, ortada süzülen toz parçacıkları,
belirişte genişleyen sarı kare halkalar, çözülme anında yatay ışık çizgisi, kıvılcımlar ve sıcak
parlama, logonun arkasında nefes alan sarı hale ve üzerinden geçen ışık. Parlama yalnızca harflerin
etrafına hale ekler; harflerin içi her zaman logodaki renktir (Nex #FFFFFF, Dev #FFCC69).

- `fonts/Inter-Black.ttf` - Inter yazı tipi (SIL Open Font License, bkz. `fonts/Inter-LICENSE.txt`)

---

# Androe Studio - Karakterli Intro (10 saniye, GLITCH Productions'tan ilham)

Hazır video: [`output/androe_glitch_intro.mp4`](output/androe_glitch_intro.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo). Sağ altta "Inspired by Glitch Productions"
yazar; rengi her pikselde altındaki zeminin tersidir.

| Saniye       | Görüntü                                                                                  | Ses                                                  |
|--------------|------------------------------------------------------------------------------------------|------------------------------------------------------|
| 0.35 - 3.05  | A N D R O E harfleri eğik panellerle, dönerek gelir (beyaz / siyah / gri)                  | her harfte tok vuruş + yükselen dijital nota        |
| 3.05 - 3.45  | Glitch geçişi: şeritler kayar, beyaza patlar                                             | kırpık dijital cızırtı, beyaz patlama               |
| 3.58 - 4.28  | androe (siyah-beyaz-gri) Pomni gibi sağ alttan trambolinden fırlamış gibi yükselir, vuruş pozuna aşıp oturur, gövdesi yatay havada süzülürken kollarını yüzer gibi çırpar, toplanıp kameraya doğru düşer | whoosh'lar, swish'ler, düşüş sesi |
| 4.28 - 5.10  | androeofficial (siyah-beyaz-altın) Caine gibi şeridin arkasından kendi sağına dönerek yükselir, çapraz vuruş pozuna aşıp oturur, geriye yaslı süzülür, dönmeye devam ederek düşer | gerilen ton, derin vuruş + altın akor, ışıltı |
| 5.28 - 5.68  | Altın / siyah / beyaz paneller ekranı süpürür                                            | soldan sağa hava sesleri                            |
| 5.68 - 10.0  | Siyahta beyaz "ANDROE STUDIO" glitch ile kurulur, yavaşça yaklaşır, iki kez ışık geçer   | bas vuruşu, dijital tıklar, sıcak akor, çın sesleri |

```bash
pip install bpy==4.2.0 scipy            # Blender Python modülü (karakterler için)
python blender/fit_keyposes.py          # anahtar pozları çöz (keyposes.json)
python blender/animate.py --char 1      # karakter dizilerini render et (renders/char1, char2)
python blender/animate.py --char 2
python blender/alpha_pass.py renders/char1 renders/char2
python glitch_intro.py                  # output/androe_glitch_intro.mp4
python glitch_intro.py --still 4.6      # tek kareyi PNG kaydet
```

- `glitch_intro.py` - videoyu üretir
- `glitch_scene.py` - sahne: harfler, glitch, karakter sahneleri, panel süpürmesi, logo, ters renkli yazı
- `blender/` - karakter katmanları Blender'da (bpy, headless) üretilir:
  - `r15_rig.py` - R15 .obj'yi parçalarından tanır, Motor6D düzeninde 19 kemiklik iskelet kurar
    (HumanoidRootPart, LowerTorso, UpperTorso, Head, kol/bacak zincirleri, 3 kemiklik pelerin);
    başlık/taç Head'e, pelerin UpperTorso'daki zincire bağlanır; normaller dışa düzeltilir,
    yinelenen yüzler temizlenir, malzemeler iki yüzlüdür
  - `fit_keyposes.py` + `posefit.py` - vuruş ve hold pozları referans karelerdeki eklem
    noktalarından en küçük karelerle çözülür (eklem sınırlı, kameradan bakınca noktalara oturur)
  - `animate.py` - trambolin fiziği: kök yörüngesi, poz eğrileri (PCHIP, lead & follow),
    hıza tepki veren kol/bacak sürüklemesi, yerçekimli pelerin, Pomni'nin çırpınan kolları,
    Caine'in dönüşü, hacmi koruyan squash & stretch, 22 mm kamera (yaklaşma, el kamerası,
    vuruş sarsıntısı); EEVEE ile gerçek motion blur'lu şeffaf PNG dizisi + meta.json
  - `alpha_pass.py` - ayrı silüet (alpha) katmanı
- `rig.py`, `choreo.py` - önceki R6 sürümü (Blender dizileri yoksa sahne bunlarla çizer)
- `glitch_sound.py` - ses tasarımı (numpy ile sentez; hazır ses kullanılmaz)
- `characters/` - Roblox Studio'dan dışa aktarılan R6 karakterler (androe, androeofficial)
- `output/taslak/` - onay için storyboard, hareket önizlemesi ve referansla senkron karşılaştırma

Linux'ta sunucuda çalıştırmak için `libegl1` gerekir (ekran kartı gerekmez, llvmpipe ile çalışır).

---

# QUEEN (LiSA) - Fan Yapımı Lyric Video (1 dakika, 2B)

Şarkının ilk dakikası için patlamalı, geçişli, kamera sarsıntılı 2B lyric video.
Ana yazılar kanji, altında küçük romaji; her karakter söylendiği an renk değiştirip zıplar,
romaji soldan sağa dolar. Sağ altta sürekli "LiSA — QUEEN" ve videonun fan yapımı olduğunu,
şarkının haklarının sahiplerine ait olduğunu belirten not durur.

Çıktı: `output/queen_lyric_video.mp4` (1920x1080, 60 fps, H.264 + AAC, 61 sn).
**Şarkı ve sözler telifli olduğu için repoya eklenmez** (`input/` ve bu video `.gitignore`'da);
video kullanıcıya doğrudan gönderilir.

| Saniye       | Görüntü                                                                                           |
|--------------|---------------------------------------------------------------------------------------------------|
| 0.0 - 0.5    | CRT açılışı, ilk vuruşta patlama                                                                  |
| 0.5 - 12.4   | Kırmızı/yeşil ikiye bölünmüş ekran, uyarı bandı, tram noktaları, trafik lambaları; lamba tabelası hece hece yanar, kanji damga gibi iner, köşe etiketleri, lambalı şeritler |
| 12.4 - 14.07 | Durak: ekran kararır, 12.77 kırmızı ve 13.32 yeşil dev flaş + patlama, hız çizgileri merkeze çöker |
| **14.07**    | **Dev patlama**: beyaz flaş, iki karelik ters renk, şok dalgaları, kırıklar, kromatik sapma       |
| 14.07 - 20.7 | Sözsüz fırtına bölümü: yağmur, bulutlar, şimşekler; ANDROE harfleri vuruşlarla düşer, STUDIO açılır; 17.44'te şimşekle taçlı QUEEN başlığı, 19.11'de LiSA |
| 20.7 - 27.7  | Pençe çizikleri ve yükselen kalpler; yumuşak parıltılardan keskin altın yıldızlara geçiş          |
| 27.7 - 34.4  | Ekranı yarıp geçen damgalar (hız çizgileri, akan oklar), uçuşan kurdeleler ve tüyler, dalgalar    |
| 34.4 - 48.09 | Kalp/çarpı zikzak ekran + mühür damgası; girdap ve HP çubuğu; soru işaretleri, şimşek, doğru cevap halkası + konfeti; açan çiçekler, kamera içeri girer |
| **48.09**    | **Nakarat patlaması**                                                                             |
| 48.09 - 54.86| Gece göğü, bulutlar ikiye yarılır, dev ay; dans halkaları ve notalar                              |
| **54.86**    | **Dev patlama** (60 saniyedeki en güçlü zil vuruşu)                                               |
| 54.86 - 60.09| Konser sahnesi: hareketli ışık huzmeleri, lazerler, ses halkaları; son uzun notada yazı ve kamera giderek daha çok titrer |
| 60.09 - 61.0 | Final patlaması (görüntü + `sound.impact` sesi), siyahta ANDROE STUDIO                            |

Sahne geçişleri: çapraz bıçak, panjur ve şerit perdeler (0.3 sn), büyük anlarda beyaz flaş.
Her vuruşta kamera sarsılır (güce göre 5-42 px, dönmeli), yazılar harf harf titrer.

## Senkron

Zamanlama `queen_timing.py`'dedir, şarkı analiz edilerek çıkarılmıştır:
vuruş ızgarası librosa `beat_track` ile (~141 BPM), vokal stereo merkez kanal + armonik
ayrıştırma ve Melodia perde takibiyle bulundu; her söz parçasının başlangıcı vokal girişine
(±0.04 sn) oturtuldu. Patlama anları yüksek frekans (zil) sıçramaları ve bölüm geçişleridir.
Bir satır kayık gelirse yalnızca `LINES` içindeki saniyeyi değiştirmek yeterlidir.

## Çalıştırma

`input/` klasörüne kendi dosyalarını koy:

- `input/queen.mp3` - şarkı (tam sürüm; ilk 61 saniyesi kullanılır)
- `input/queen_sozler.txt` - 0:00-1:00 sözleri, `LINES` sırasıyla, her satır
  `kanji parçaları " / " ile | romaji parçaları " / " ile` (parça sayısı `LINES` ile aynı)

```bash
pip install -r requirements.txt
python queen.py                      # output/queen_lyric_video.mp4 (tüm çekirdeklerle paralel)
python queen.py --still 14.2         # tek kare PNG
python queen.py --preview            # 960x540, 30 fps hızlı önizleme
python queen.py --sheet 0 61 48      # 48 karelik kontak baskı
```

## Dosyalar

- `queen.py` - sözleri yükler, kareleri paralel render eder, şarkıyı keser, final sesini ekler, MP4 yazar
- `queen_timing.py` - vuruşlar, söz parçalarının zamanları, patlama anları, sahneler (söz metni içermez)
- `queen_scene.py` - yazı motoru (kanji + romaji, giriş/çıkış, renk dolumu), özel parçalar, kamera, patlamalar, geçişler
- `queen_bg.py` - sahne arka planları (sinyal, fırtına, ay, konser ışıkları vb.)
- `queen_fx.py` - 2B şekiller ve efektler (patlama, şok dalgası, şimşek, kırıklar, hız çizgileri, desenler)
- `fonts/` - Dela Gothic One, RocknRoll One, Reggae One, Anton, Black Ops One, Bungee (SIL OFL, bkz. `fonts/QUEEN-FONTS.txt`)
