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

# SCP Sinematiği (7 saniye, Blender)

Referans: SCP: Roleplay videosunun 00:25-00:32 arası (siyah ekran + üç plan).
Karakter yok; silah kasaları ve M4A1'ler, zırhlı araç konvoyu, sisli göknar ormanı, tesis kapısı.

| Saniye    | Plan    | Görüntü                                                                     | Ses                                  |
|-----------|---------|-----------------------------------------------------------------------------|--------------------------------------|
| 0 - 1     | –       | siyah, siyahtan yumuşak açılış                                              | emme + ters yankı kabarması          |
| 1 - 3     | SECURE  | sisli ormanda kasa deposu; ön plandaki kasa yığını kayarken yazı arkasından belirir; odak kasalardan yazıya kayar; kasaya dayalı M4A1'ler, asılı lamba, havada toz | trailer darbesi, kayan whoosh, metal tıngırtı, lamba vızıltısı, telsiz |
| 3 - 5     | CONTAIN | alçak kamera, gece orman yolu; tepe lambası dönen 8x8 zırhlı araç kameranın dibinden geçip yazıyı bir an örter (odak araca kayar), ikinci araç yazının arkasındaki şeritten geçer; ön planda otlar | braam + darbe, dizel motorlar (ateşleme sırası, Doppler, sol->sağ; uzak araç kısık/boğuk), lastik/çakıl |
| 5 - 7     | PROTECT | kamera harflerin altından geçip tesis kapısına ilerler; odak yazıdan ambleme kayar; çit, bariyer, kule, kamyonlar | darbe, harf whoosh'u, uzak siren, sonda büyük darbe |

Planlar arası 0.33 sn çapraz geçiş: her plan kesmenin iki yanına 10 kare taşacak şekilde ayrı
render edilir ve ffmpeg `xfade` ile birleşir; kamera ve araçlar geçiş boyunca hareketini sürdürür.

```bash
python3.11 -m pip install bpy==4.2.0 scipy        # Blender Python modülü (Python 3.11)
pip install -r requirements.txt                   # numpy, scipy, imageio-ffmpeg (ses + birleştirme)
python assets/fetch_polyhaven.py                  # Poly Haven modelleri (CC0) + göknar .blend
python3.11 blender/bake_trees.py                  # göknarları impostor görüntülerine pişir (bir kez)
python3.11 blender/render_chunks.py --preview --step 2   # önizleme kareleri (640x360)
python scp_intro.py --preview                     # output/taslak/scp_onizleme.mp4
python3.11 blender/render_chunks.py               # final kareler (1920x1080), kaldığı yerden sürer
python scp_intro.py                               # output/scp_cinematic.mp4
python3.11 blender/scp_cinematic.py --preview --still 72,232,405   # tek tek kareler
```

- `blender/scp_cinematic.py` - sahne, ışık, sis, kamera, odak kaydırma, toz/bokeh, render (headless bpy)
- `blender/vehicles.py` - prosedürel 8x8 zırhlı araç ve 6x6 askerî kamyon (gerçek ölçüler, kamuflaj + çamur)
- `blender/bake_trees.py` - Poly Haven fir_tree_01'in üç ağacını çapraz düzlemli impostora pişirir
- `blender/render_chunks.py` - planları küçük gruplar halinde ayrı işlemlerde render eder (bellek)
- `scp_sound.py` - ses tasarımı: dizel motor + Doppler'li geçiş, trailer darbeleri, braam, ortam,
  ducking, kompresör/limiter (numpy + scipy ile sentez; zamanlar `meta.json`'dan)
- `scp_intro.py` - siyah giriş, çapraz geçişler, kararma, vinyet, film greni, ses -> MP4
- `assets/models/` - dış modeller (bkz. `assets/models/README.md`, `CREDITS.md`); M4A1: Lolik123654
  (Sketchfab, CC BY 4.0) - videoyu paylaşırken açıklamaya yazılmalı
