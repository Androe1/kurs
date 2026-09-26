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

# Void Creations - Intro (4.4 saniye)

Hazır video: [`output/void_creations_intro.mp4`](output/void_creations_intro.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo). Referans videonun ilk 4 saniyesindeki animasyon;
ekranda logo ve yazıdan başka hiçbir şey yok. V logosu VOID'in V'sidir: **[V]OID CREATIONS**.

| Saniye       | Görüntü                                                                                          | Ses                                          |
|--------------|--------------------------------------------------------------------------------------------------|----------------------------------------------|
| 0.36 - 1.2   | Perspektifte teknik çizim zemini belirir (daireler, taralı bantlar, işaretler, kılavuz çizgiler); ekran dışından gelen ışık çizgileri köşelerde dönerek V logosunun 3B'de üst üste dizili beş kopyasını çizer | sessizlikten kabaran koyu pad (Si♭maj7♯11) |
| 1.48 - 2.17  | Kamera logoya döner, kopyalar tek logoda birleşir; öndeki kopya hızlanan aralıklarla dolu beyaz yanıp söner, zemin kararır | Si♭ bası güçlenerek girer |
| 2.2 - 2.8    | Logo dolar, küçülüp sola kayarak VOID'in V'si olur; OID CREATIONS önce ince kontur, ardından eğik bir dolgu cephesiyle soldan sağa belirir | akor tam güçte, bas nefes alır |
| 3.47 - 3.73  | Logonun eğimiyle (18.3°) aynı açıda bir silme her şeyi soldan sağa siler                          | bas Sol'e iner                               |
| 3.73 - 4.4   | siyah                                                                                            | ses söner                                    |

```bash
python void_creations.py                 # output/void_creations_intro.mp4
python void_creations.py --still 1.3     # tek kareyi PNG kaydet
```

- `void_creations.py` - videoyu üretir
- `void_scene.py` - sahne: perspektifteki zemin, ışık çizgileri (trim path), 3B kopya yığını,
  birleşme ve yanıp sönme, yazının kontur + dolgu açılışı, eğik silme. V logosu vektör olarak
  (`LOGO`, iki dörtgen) tanımlı; köşeler logo görselinin kenarlarına alt piksel doğrulukla oturtuldu
- `void_sound.py` - ses tasarımı (numpy ile sentez; hazır ses kullanılmaz). Akorlar ve seviye
  eğrileri referansın spektrumundan ölçüldü
- `fonts/Figtree-Black.ttf` - Figtree değişken yazı tipinden üretilmiş Black (900) örneği (SIL Open
  Font License, bkz. `fonts/Figtree-LICENSE.txt`); kerning çiftleri (A-T, V-O) fontun GPOS tablosundan
- `output/taslak/void_storyboard.png` - bitmiş videodan 12 anahtar kare

Düzenleme: zamanlama `void_scene.py` başındaki `T_*`, `FLASHES`, `COLLAPSE`; yığın `STACK_*`, `TILT`,
`SPIN`; yazı `TEXT`, `CAP`, `KERN`; ses akorları ve seviye eğrileri `void_sound.py` başında.
`output/taslak/void_karsilastirma.mp4`: üstte referans, altta bizim; önce referansın sesiyle, sonra bizimkiyle.
