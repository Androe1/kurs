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

# Korku Oyunu Teaser'ı (15 saniye)

Hazır video: [`output/horror_teaser.mp4`](output/horror_teaser.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo). 3B sahne, çizim / boyama görünümüyle render edilir:
mürekkep konturları, bantlı boya gölgelendirme, Kuwahara boya filtresi, fırça dokusu.
Görüntü de ses de kodla üretilir; tek hazır görsel, oyunun göz çizimidir (`assets/seytani_gozler.png`).

| Saniye       | Görüntü                                                                                          | Ses                                                        |
|--------------|--------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 0.0 - 0.7    | Zifiri karanlık                                                                                  | kısık oda uğultusu, derinden bas                           |
| 0.7          | Tepede spot ışık titreyerek yanar, huzmede toz süzülür                                           | ağır şalter "klank"ı, titremeyle kesilen lamba vızıltısı   |
| 0.95 - 2.75  | Kan yukarıdan ağır ağır iner, ucunda damla şişer; iki damla karanlığa düşer                      | yapışkan gurultu; damlalar çok aşağıdan yankılanır         |
| 2.75 - 5.05  | Damla titreyip döner, yüzeyinde sarmal sırtlar belirir; yapraklar sıvıdan çıkar ve üç vuruşta dıştan içe açılarak gül olur | tersten yükselen nefes, ıslak çıtırtılar, fısıltılar; her açılma vuruşu kalp atışı + yaylı darbesi |
| 5.25         | İplik kopar, üst parça yaylanarak geri çekilir                                                   | çıt + esnek geri sekme                                     |
| 5.25 - 8.35  | Gül düşen yaprak fiziğiyle sağa sola yatarak süzülür, kamera yayla takip eder; üstünden kan damlar | gülün hızıyla açılan, onunla sağa sola gezen hışırtı, hızlanan kalp |
| 8.35         | Gül kan birikintisine değer: halka halka dalga, taç sıçraması; iki yaprak kopup savrulur ve sıvıya iner | BRAAM, alt frekans patlaması, sıçrama, halkaların parıltısı |
| 9.85 - 10.95 | Işık titreyip söner, kamera yukarı, karanlığa bakar                                              | yükselen gerilim, hızlanan kalp, ölü sessizlik             |
| 11.15 - 11.75 | Karanlıktan kapalı şeytani gözler belirir, bir kez seğirir                                      | derin hırıltı, içe çekilen nefes, ıslak tık                |
| 11.75 - 12.95 | Kapaklar açılır; göz bebekleri büyükten iğne ucuna büzülür, kamera sarsılır; sonda gözler kısılır | dev vuruş: uyumsuz akor kümesi, metal çığlık, alt patlama |
| 13.15 - 15.0 | "COMING SOON" ortadan dışa yanarak belirir, titrer, söner                                        | derin vuruş, metalik çınlama, karanlık uğultu              |

```bash
pip install -r requirements.txt
python horror_teaser.py                     # output/horror_teaser.mp4 (1080p60, ~30 dk)
python horror_teaser.py --width 960 --height 540 --fps 30 -o output/taslak/horror_teaser_onizleme.mp4
python horror_teaser.py --still 8.6         # tek kareyi PNG kaydet
python horror_teaser.py --storyboard        # anahtar anlardan film şeridi
```

- `horror_teaser.py` - videoyu üretir (kareleri render eder, sesi sentezler, ffmpeg ile birleştirir)
- `horror_scene.py` - zaman çizelgesi, fizik, kamera, ışık; sıvı, damlacıklar, dalga kaynakları, gözler, yazı
  - gülün düşüşü: Andersen–Pesavento–Wang yarı-durağan düz levha modeli (kaldırma / sirkülasyon,
    yöne bağlı sürükleme, eklenen kütle, dönme sönümü) + çiçeğin ağır tabanından gelen safra torku;
    sağa sola süzülme kendiliğinden oluşur. Zaman ölçeği g ile ayarlanır (inişin anı sabit kalsın).
    Sıvıya değince temas kuvveti kademeli devreye girer; yatay hız söner, eğim burulma yayıyla düzelir.
  - kopan yapraklar: yöne bağlı sürükleme ve yana itişle sallanarak düşer, sıvıda yüzer
  - hareket `.claude/skills/character-physics/scripts/check_motion.py` ile doğrulandı (hız sıçraması
    ve ters sarsıntı yok)
- `horror_rose.py` - prosedürel gül: 26 yaprak, orta çizgi + enine kesit integrali, altın açı dizilimi,
  tomurcuk (damla) -> açık gül geçişi
- `horror_eyes.py` - göz çizimi: göz bebekleri silinir (animasyonlu çizilir), kapak sınırları çizimden çıkarılır
- `horror_gl.py` - moderngl render hattı: gölge haritası, 48 yönden ortam kapanması, zemin yansıması,
  hacimsel ışık, G-buffer, bloom, ton eşleme
- `shaders/` - GLSL: gül yaprağı, kan sıvısı (raymarch), dalgalanan kan zemini, ışık huzmesi, toz,
  çizim görünümü (kontur + Kuwahara), gözler, yazı, son işlem
- `horror_sound.py` - ses tasarımı (numpy ile sentez)
- `fonts/Cinzel-*.ttf` - Cinzel yazı tipi (SIL Open Font License, bkz. `fonts/Cinzel-OFL.txt`)

Linux sunucuda `libegl1` gerekir (ekran kartı gerekmez, Mesa llvmpipe ile çalışır).
