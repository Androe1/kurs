# BandPerformance - Roblox R15 canlı grup performans sistemi

4 R15 karakterin (gitar, bas, bateri, vokal) **bu şarkıya** (`fever_dream.mp3`) kilitli, katmanlı ve fizik hissi veren bir
müzik performansı oynamasını sağlar. "Tek bir döngü + el ileri geri" değildir: her vuruşun, her akor değişiminin
bir karşılığı vardır; hareket kalçadan kafaya/ele **kinetik zincir** olarak yayılır; eller enstrümana **IK ile gerçekten temas** eder.

> **Doğrulama durumu (dürüstçe):** Bu kod Roblox Studio'da çalıştırılmadı (bu ortamda Studio yok). Çekirdek, gerçek bir
> Luau VM'inde (WASM) R15'e yakın sahte bir rig üzerinde **tüm şarkı boyunca** simüle edilip ölçüldü (aşağıda "Test ve doğrulama").
> Studio'ya özgü kısımlar (Instance üretimi, RunService, Sound, Motor6D'nin kendi rig'inizdeki gerçek C0/C1 değerleri)
> ilk çalıştırmada kontrol edilmelidir; "İlk çalıştırma kontrol listesi"ne bakın.

## Şarkı analizi (animasyonun dayandığı veri)

`tools/analyze_song.py` şarkıyı ölçüp `Data/SongMap.luau` üretir (üretilmiş hali depoda):

| | |
|---|---|
| Tempo / ölçü | **160 BPM**, 4/4, 114 ölçü (2:52). Izgara 16'lık (0.09375 sn), ilk ölçü başı 0.391 sn |
| Yapı | 4 ölçülük intro (kısık, filtreli build) -> **6.4 sn büyük giriş** -> verse/nakarat blokları -> 1:48'den outro |
| Harmoni | 4 akorluk döngü **E♭ - Cm - Gm - B♭** (her akor 1 ölçü), 4 ölçülük tekrar |
| Davul | 16'lık başına kick/snare/hat/crash enerjisi (backbeat 2 ve 4, nakaratta ride, bölüm başı crash, ölçü sonu fill) |
| Gitar | 8'lik aşağı-yukarı ızgara, atak enerjisi, güçlü vuruşlar, cümle sonu boşlukları |
| Bas | Vuruş başına alçak nota (MIDI), akor köküne yakınlaştırılmış, kick'e kilitli plucklar |

**Sınırlar:** Ölçüm sinyal analizidir, kulak değil. Distorsiyonlu gitar duvarı davul transkripsiyonunu gürültülü yapar
(ölçüm + stil önceliği birleştirilir) ve **vokal ayrıştırılamadı**: vokalist fraz yapısı ölçü stilinden (verse = 3 ölçü şarkı + 1 nefes,
nakarat sürekli) gelir. Gerçek fraz zamanlarını biliyorsan `Score.barStyles[bar].vocalOn` dizisini doldurman yeterli.

## Mimari

```
src/ReplicatedStorage/BandPerformance/
  init.luau              Band orkestratörü (new/update/seek/getMetrics, registerRole, discover, zaman kaynakları)
  Config.luau            Rol profilleri (ağır/hafif, sallanma, kafa...), yay parametreleri, eklem sınırları
  Data/SongMap.luau      analyze_song.py çıktısı
  Music/Clock.luau       Müzik saati (Sound / sunucu saati / elle) + drift düzeltme
  Music/Score.luau       SongMap -> olaylar: davul, strum ızgarası, akor/perde, bas plucklar, bölümler, ölçü varyasyonları
  Rig/R15Rig.luau        Motor6D bağlama, kendi FK'sı (dönüşüm yalnızca Motor6D.Transform)
  Rig/TwoBoneIK.luau     Analitik 2 kemik IK + anatomik menteşe (twist) + ön kol roll'ü + soft uzama
  Rig/RigPrep.luau       HRP anchored, Animate kapalı, vb. (idempotent)
  Layers/Pose.luau       Katman karışımı (ağırlıklı dönüş/kayma/el-ayak hedefi biriktirici)
  Layers/Base.luau       TEMEL: nefes, duruş, ayak planı, dengelenme, ayak vuruşu
  Layers/Groove.luau     İKİNCİL: ritme bağlı kinetik zincir, ağırlık transferi, kafa (counter-rotation)
  Layers/Strum.luau      Sağ el vuruş eğrisi (Hermite, hız sürekli, ses anı = ip düzlemi)
  Layers/Follow.luau     Gövdeye bağlı nesnenin follow-through'u (gitar, bas)
  Layers/Interaction.luau ETKİLEŞİM: IK + FK karışımı, bilek sınırı gevşetme (temas noktası kaymaz)
  Performers/Performer   Karakter beyni: durum makinesi, yaylar, olay imleçleri, kare akışı
  Performers/PerformerState  Idle/Ready/Playing/Accent/Transition/Recovery/Outro (ağırlıklı, snap yok)
  Performers/Stringed    Gitar + bas (aynı iskelet, farklı karakter)   Guitarist / Bassist
  Performers/Drummer     Bateri (çubuk ucu yayları, pedal ayakları)    DrumKit (set yerleşimi)
  Performers/Vocalist    Vokal: el mikrofonu + sol el jestleri (4. karakter / modülerlik örneği)
  Props/PropBuilder      Prosedürel gitar/bas/bateri seti/mikrofon + kendi modelini kullanma (adopt)
  CameraRig.luau         10 kamera planı + müziğe göre otomatik yönetmen
src/ServerScriptService/BandServer.server.luau        sunucu: karakterleri hazırla, ortak başlangıç zamanı
src/StarterPlayer/StarterPlayerScripts/BandClient.client.luau   istemci: animasyonu üret, sesi senkronla, kamera
tools/analyze_song.py    şarkı -> SongMap
tests/                   Luau VM'inde çalışan testler + önizleme araçları
```

**Sunucu / istemci ayrımı:** Motor6D.Transform ve prop CFrame'leri replike olmaz; bu yüzden animasyonu her istemci aynı
sunucu saatinden (`workspace:GetServerTimeNow() - BandStartServerTime`) **yerelde** üretir. Ağ trafiği yok, herkes aynı karede
aynı vuruşu görür. Sunucu yalnızca karakterleri hazırlar ve başlangıç zamanını yazar. Ses her istemcide yerel çalınır ve saate çekilir.

**Neden `AnimationTrack` / `IKControl` değil?** Yaratıcı kontrol ve test edilebilirlik için: hedef pozlar önceden çekilmiş bir
klipten değil müzik olaylarından (strum zamanı, akor, davul vuruşu) üretiliyor; temas noktaları dünya uzayında her kare çözülmeli;
dirsek/diz menteşe eksenini anatomik tutmak ve erişilemeyen hedefte yumuşak uzamak istiyoruz. `IKControl` bunları kare başına
deterministik ve kuvvetle test edilebilir biçimde vermez. Katmanlı karışım (`Pose`) AnimationTrack'in öncelik/ağırlık
mantığını kendi içinde yapar. İstersen Idle gibi önceden çekilmiş bir `AnimationTrack`'i düşük öncelikle çalıştırıp
`Transform`'u `Pose.rot` ile `Lerp`leyebilirsin (`Performer.update` içindeki `rig:apply` noktası).

## Kurulum

1. **Rojo ile:** `rojo serve` (veya `rojo build -o Band.rbxlx`). Yapı `default.project.json`'da.
   **Elle:** `BandPerformance` klasörünü `ReplicatedStorage`'a, `BandServer`'ı `ServerScriptService`'e,
   `BandClient`'ı `StarterPlayerScripts`'e koy (aynı isimlerle).
2. Karakterleri `workspace.Band` klasörüne koy (yoksa workspace'te aranır). Her modelde ya **`BandRole` attribute'u**
   (`Guitar`/`Bass`/`Drums`/`Vocal`) ya da şu adlardan biri olmalı: `Gitarist, Basgitar, Baterist, Vokalist`.
   Karakter **R15 Motor6D rig'i** olmalı (HumanoidRootPart, LowerTorso, UpperTorso, Head, kollar/bacaklar). Rig'in C0/C1'ine dokunulmaz.
3. Karakterleri sahneye yerleştir ve **bakacakları yöne** döndür (sistem karakteri çevirmez; `autoFacing` isteğe bağlı).
   Gitar/bas gövdeye askılıdır; **bateri için kendi HRP'sini oturma noktasının üstüne koy** (kalça tabureye otomatik alçalır,
   set kendi önünde `-Z` yönünde kurulur). Vokalist mikrofonu elinde tutar.
4. Şarkıyı yükle, `workspace` attribute'una `BandSongId = "rbxassetid://..."` yaz (ya da `workspace`/`SoundService` içine `BandSong` adında Sound koy).
5. Play. Sunucu 3 sn sonra şarkıyı başlatır, bitince tekrar eder (`BandLoop`).

Prop'lar (gitar, bas, davul seti, mikrofon) prosedürel üretilir. Kendi modelini kullanmak için modeli karakterin içine
`Guitar_Prop` / `Bass_Prop` / `Vocal_Prop` adıyla koy (PrimaryPart = enstrüman çerçevesi: gövde merkezi, **+X başlığa, +Z yüzeyden dışarı, +Y üst kenar**).

### Faydalı attribute'lar (workspace)
`BandSongId`, `BandLoop`, `BandLeadIn`, `BandDebug` (true: 5 sn'de bir temas hatası özeti), `BandCamera`
(`auto` ya da `front, threeQuarterFront, side, threeQuarterBack, handsCloseUp, guitarSide, bassSide, drummerSide, lowAngle, elevated`).

## Sessiz kayıt modu (telifli şarkıyı yüklemeden video)

Şarkıyı Roblox'a yüklemene gerek yok. `BandSongId` boş bırak, `workspace` attribute'una `BandRecord = true` yaz:
1. Play'e bas; 6 sn geri sayım (6..1) gelir, şarkı zamanı 0'da ekran **bir an beyaz flaşlar**.
2. Ekran kaydını (OBS / Roblox Recorder) başlatıp animasyonu kaydet (şarkı 2:52, döngü kapalı).
3. Video editöründe mp3'ü, sesteki ilk vuruşu videodaki beyaz flaşın karesine hizalayarak koy
   (şarkıda ilk ölçü başı 0.39 sn, büyük giriş 6.4 sn'dedir: kolay hizalama noktası).
Kamera için `BandCamera = auto` (müziğe göre otomatik kesme) ya da tek bir plan adı yaz.

## Animasyon felsefesi - istekler nerede karşılanıyor

| İstek | Nerede |
|---|---|
| Kinetik zincir: hareket -> ağırlık -> gövde -> omuz -> kol -> dirsek -> bilek -> el | `Stringed._strumEvents` / `Drummer.prepare`: her vuruş **gecikmeli darbe zinciri** (el 0 ms, omuz +18, göğüs +35, kalça +50, kafa +65). Hepsi ayrı kütleli yay (`Util/Spring`), bu yüzden lead&follow/overlap kendiliğinden oluşur |
| Bilek ana kaynak, dirsek yardımcı | `Strum.eval` + `Stringed.contact`: uç, bilek etrafında yay çizer; bilek pivotu vuruş yönünde 1/4 oranında kayar (dirsek). İP düzlemini kesme anı **tam** ses anı (testle doğrulanır) |
| Kol açılarını kilitleme, spine'ı tek parça yapma | Üç segment (pelvis/Waist/Neck) ayrı yaylar; omuz klavikula kayması (`Pose.addShoulder`); dirsek `elbowOpen` yayı |
| Anticipation / overshoot / settle | `Spring.impulseForPeak` (ilk tepe genliği ayarlanabilir), ağırlık transferinde zıt yönde ön hamle, perde değişiminde sol el 0.07-0.11 sn **önceden** harekete başlar |
| Ağırlık, teleport yok | Ayaklar IK ile yere sabit; kalça kayınca bacaklar uyum sağlar; yüksüz ayağın topuğu kalkar ve ritimde vurur (`Layers/Base`) |
| El enstrümandan ayrılmaz | `Interaction.solve`: bilek açısı sınırı aşılırsa **yönelim gevşer, temas noktası kaymaz** (`solveRelaxed`). Çubuk ucu vuruşta yüzeye < 0.1 stud (testle ölçülür) |
| Gitar | Strum eğrisi: aşağı/yukarı, accent, mute, ghost (sessiz ama el durmaz), cümle sonu boşluğu; sol el akor (perde) değişiminde kayar ve boyundan hafifçe kalkar; gitar gövdeye askılı + follow-through (`Layers/Follow`); öne eğilme/geri yaslanma cümle bazlı; ağırlık aktarımı |
| Bas (gitardan farklı) | Daha ağır yaylar, daha az/güçlü hareket, parmak pluck (dalış + yana kayma, dönüşümlü parmak), tel değişince el konumu, **sustain'de gövde/el sakinleşir** (`perf.calm`), güçlü notada kalça+gövde+omuz vurgusu, kick'e kilitli |
| Bateri | Kalça tabureye oturur; çubuk ucu iki vuruş arası **asimetrik yay** (hızlı geri tepme, ivmelenen düşüş); sağ ayak kick pedalı (topuk kalkar, ayak ucu basar), sol ayak hi-hat pedalı (2 ve 4'te chick); crash'te büyük zincir; tom fill'de gövde set boyunca yön değiştirir; el ataması **fiziksel uygulanabilirlik** (hız/mesafe) kontrollü |
| 4. karakter | Vokalist: el mikrofonu fraz öncesi kalkar + hazırlık nefesi, sol el jest kütüphanesi. Yeni rol için `BandPerformance.registerRole(rol, factory)` |
| Mikro hareketler | Nefes, omuz, baş selamı, ayak vuruşu, kalça kayması, dengelenme; hepsi müziğe/enerjiye bağlı; rastgelelik yalnız `Util/Rng` (deterministik hash) |
| Loop hissi yok | Durum makinesi (Idle/Ready/Playing/Accent/Transition/Recovery/Outro) + **4 ölçülük döngü varyasyonu**: normal / güçlü vurgu + daha çok çökme / baş hareketi / duruş değişimi, %±8 deterministik oynama, cümle sonu "pose hold" |
| Katmanlı karışım | Base -> Performance(enstrüman) -> Accent(darbe zinciri) -> Secondary(Groove) -> Interaction; her katman `Pose`'a **ağırlıkla** katkı yapar, rig'e doğrudan yazmaz. Durum ağırlıkları yayla yumuşatılır |
| Çok açılı doğruluk | Hareket 3B IK'dan gelir (kamera yönüne bağımlı değil); `CameraRig` 10 plan; test önizlemesi front/side/3/4/top |
| Camera-facing yok | Her karakter kendi performans yönünde; kafa gövdeyi birebir izlemez (bakış `gaze` ayrı yay, perde değişiminde boyuna bakar) |
| 12 prensip | Anticipation, Follow-through, Overlapping, Slow in/out (`Ease`, Hermite), Arcs (strum/çubuk yayları), Timing/Spacing (SongMap ızgarası), Secondary action, Exaggeration (vuruş darbe genlikleri), Staging (kamera), Squash&stretch: R15 rijit parçalar olduğu için ölçek yok; yerine **kalça çökmesi + overshoot** |

### Bilinen sınırlar
- R15 elleri parmak eklemi içermez: "parmak düzeltme" yalnızca bilek/el yönelimi ve temas ofseti olarak yapılır.
- Squash & stretch ölçekle değil kalça/gövde çökmesiyle verilir (Motor6D `Transform` ölçek taşıyamaz).
- Vokal ve davul transkripsiyonu yaklaşıktır (yukarıya bak).
- Props prosedürel/yer tutucudur; kendi mesh'lerini `*_Prop` ile bağlayabilirsin.
- Karakter ölçekleri varsayılan R15'e yakın varsayılır; uzunluklar rig'in kemik uzunluklarından (reach) ölçeklenir, ama çok farklı oranlarda (Rthro) sahne yerleşimi/enstrüman konumları `Stringed.SPECS` ve `DrumKit.PIECES` ile ayarlanmalıdır.

## İlk çalıştırma kontrol listesi
1. `workspace.BandDebug = true` yap; çıktıda `elHata` değerleri ~0.00x olmalı. Büyükse ilgili enstrüman konumunu (`Stringed.SPECS.*.strapPos/neckDir`, `DrumKit.PIECES`) rig'ine göre ayarla.
2. Karakter hiç oynamıyorsa: modelde `HumanoidRootPart` anchored ve diğer parçalar unanchored mı (`RigPrep` yapar), `Animate` scripti kapalı mı?
3. Sesle kayma varsa `Config.VISUAL_LEAD` (+ görsel erken) ile oyna. Ses ve görüntü aynı sunucu saatine bağlıdır.
4. Roblox eksen kuralı: karakter `-Z`'ye bakar, `+X` karakterin sağıdır; tüm yönler buna göre.

## Test ve doğrulama

```bash
cd roblox && npm install
node tests/run.mjs            # tüm testler (Luau VM, WASM) - ~3 dk
node tests/run.mjs 06         # tek test dosyası (önek)
node tests/lint.mjs           # statik analiz (Roblox tipleri tanımsız olduğundan tip gürültüsü içerir)
```

Testlerin kapsadığı ölçümler (60 fps, **tüm 172 sn**, 4 karakter):
- yay: kapalı form, 30/60/240 fps'de aynı sonuç, `impulseForPeak` tepe genliği
- IK: hedefe ulaşma (FK ile çapraz doğrulama), dirsek/diz menteşe ekseni, erişilemeyen hedefte soft uzama
- Strum: ses anı tam ip düzleminde, yön eğri hızıyla uyumlu, konum sürekli
- Her karakter: dirsek 0..155°, diz < 145°, **hiçbir eklem tek karede 28°'den fazla dönmez**, el temas hatası < 0.2 stud (ölçülen max ~0.09),
  erişilemeyen kare < %2, ardışık 4 ölçülük döngüler birbirine benzemez (bağıl uzaklık 0.25-0.36)
- Bateri: çubuk ucunun vuruş anında davul yüzeyine uzaklığı (ort ~0.02, max ~0.1 stud), 5 davul/zil için kol uzanımı
- Durum geçişleri (Idle->Ready->Playing->Outro->Idle), seek, LOD dönüşü: snap yok
- 30 fps ile 60 fps aynı müzik anında farklı pozlar üretmez (< 0.06 stud fark)

Görsel kontrol (çok açılı iskelet önizlemesi):
```bash
ROLE=Drums T0=6.1 T1=6.6 STEP=1 LOG_FILE=/tmp/drums.log node tests/run.mjs 90
python3 tests/preview.py /tmp/drums.log drums.png --frames 0,6,12,18 --views front,threeq,side,top
```
`docs/preview/` içinde örnekler var (crash anı, strum, bas pluck, vokal).

Performans: WASM yorumlayıcıda 4 karakter + prop ≈ 7.5 ms/kare; Roblox'un yerel Luau VM'i belirgin biçimde hızlıdır.
Uzak performer'lar için LOD var (`cullDistance`, `getCameraPosition`).

## Şarkıyı yeniden analiz etmek / başka şarkı

```bash
pip install librosa numpy scipy
python tools/analyze_song.py fever_dream.mp3 -o src/ReplicatedStorage/BandPerformance/Data/SongMap.luau
```
Tempo ızgarasını, ölçü başını (şarkıdaki ilk büyük vuruştan), akor köklerini ve 16'lık başına davul/gitar enerjisini yeniden çıkarır.
Başka bir şarkıyla animasyon istenirse yalnızca bu dosya değişir.
