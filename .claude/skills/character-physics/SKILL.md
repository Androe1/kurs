---
name: character-physics
description: Karakter animasyonuna gerçek fizik (yerçekimi, momentum, havada kalma, kütleli yaylar, hava sürüklemesi, pelerin, squash & stretch, kamera) ekleme ve hareket kalitesini ölçerek doğrulama yöntemi. Bir karakter zıplıyor, fırlıyor, havada süzülüyor, düşüyor, savruluyor ya da "pozu değişen video gibi", "yerçekimi yok", "momentum yok", "robot gibi", "kayıyor/donuyor" gibi şikâyetler varsa; Roblox R6/R15, Blender (bpy), Unity veya kendi render'ında karakter/obje animasyonu yapılacaksa bunu kullan. Referans videodaki hareketi taklit ederken de kullan.
---

# Karakter fiziği (Androe Studio intro'sundan çıkarılan yöntem)

Bu skill, "sadece poz değişen" animasyonu gerçek bir fiziksel harekete çeviren katmanı ve
bunu doğrulamanın yolunu anlatır. Kod `scripts/physics.py` içinde (motordan bağımsız numpy),
kontrol aracı `scripts/check_motion.py`. Kullanılmış tam örnek: depo kökündeki
`blender/animate.py` (Blender, R15, iki karakter).

## Temel ders: poz ≠ hareket

Kullanıcı ilk sürümleri "yerçekimi yok, fizik yok, momentum yok, sadece pozu değişmiş video"
diye reddetti. Ölçünce sebep netti (göğsün kare başı dikey hızı, piksel):

```
fiziksiz:  -162 -152 -139 ... -35 | +11 +15 -10 +13 ... ~0 (24 kare) ... -64 -105 | +171 +367
fizikli :   -72  -65  -59 ... -18  -9  0  2  4  5  7  8  9 10 12 ... +90 +96
```

Fiziksiz sürümde karakter görünmez tavana çarpıyor (hız bir karede sıçrıyor), yarım saniye
yerçekimsiz asılı kalıyor, düşmeden önce yukarı zıplıyor. Fizikli sürümde hız **her karede
aynı miktarda** değişiyor. Göz bunu "ağırlık" olarak okur. Anahtar pozlar ne kadar iyi olursa
olsun, kök yörüngesi fiziksel değilse animasyon ölü görünür.

## Katmanlar (sırasıyla uygula)

1. **Anahtar pozlar** (ne yapıyor): vuruş ve hold pozları. Referans taklit ediliyorsa açıları
   tahmin etme; referans karelerinde eklem noktalarını ızgara ile oku ve pozu en küçük karelerle
   çöz (`blender/posefit.py`, `blender/fit_keyposes.py`). Taraflara dikkat: karakterin kendi
   sağı kameraya bakarken ekranın solundadır.
2. **Kök yörüngesi = serbest uçuş** (`Ballistic`): sabit yerçekimi + sabit yatay momentum.
   - `Ballistic.through(pa, fa, pb, fb)` iki anahtar konumdan geçen yolu verir; tepe anını
     fizik belirler. Tepe anını pencerenin ortasına almak istersen `Ballistic(apex_frame, ...)`.
   - `hang=(0.6, 7)`: yerçekimi tepe çevresinde %60 azalır → trambolin / çizgi film "havada
     kalma". Hız yine süreklidir. Gerçekçi fizikte `hang=(0, 1)`.
   - Yerçekimi ölçeği: karakter boyuna göre seç. Bu projede karakter 6 stud, g = 150 stud/s²
     (gerçeğin ~4.5 katı; kısa pencerede ekrandan çıkabilmesi için çizgi film yerçekimi).
   - **Asla**: tepede duraksatma, "toplanma" için kökü yukarı zıplatma, vuruş anında kökü
     durdurma. Bunlar tam olarak reddedilen şeylerdi.
3. **Kök dönüşü = açısal momentum**: vuruş→hold arasındaki açısal hız öncesinde ve sonrasında
   üstel sönerek sürer; sonuç `RotSpring` (6 Hz, 0.8) ile yumuşatılır. Sürekli dönüş isteniyorsa
   (ör. "havada kendi sağına dönüyor") sabit açısal hız ekle. Çok uzun süren momentum takla
   attırır; sönümü kısa tut (≈5 kare).
4. **Kemikler = kütleli yaylar** (`Spring`/`RotSpring`): kemik hedef poza yayla gider;
   hızlanır, hafifçe aşar, geç oturur. `BONE_SPRING_DEFAULTS`: gövde sert (7-8 Hz), el/ayak
   gevşek (4 Hz). Farklı frekanslar lead & follow ve overlap'ı **kendiliğinden** üretir;
   ayrıca kare gecikmesi eklemeye gerek kalmaz. Yayları ilk kareden önce ~12 kare ısıt
   (ilk karede sıçrama olmasın).
5. **Hava sürüklemesi**: dikey hızı yayla süz (4 Hz, 0.55), `drag_angle` ile uzuvları dünya
   uzayında yerçekimi yönüne döndür: yükselirken kollar/bacaklar aşağıda kalır, tepede
   serbestleşir, düşerken yukarı kalkar. Alt uzuv yarım açıyla ve ekstra gecikmeyle.
   Çok güçlü sürükleme vuruş pozunu okunmaz yapar: en fazla ~32°, yay frekansı ≥ 4 Hz.
6. **Pelerin / kumaş**: gövdeye göre değil dünyaya göre hesapla. Karakter yatayken gövdeye göre
   sarkan pelerin kafanın üstünü kaplar (bu projede oldu). Hedef yön = gövde boyunca ayaklara
   doğru + biraz sırt + biraz yerçekimi; düşerken sırta doğru havalanır. Zincirin her halkası
   biraz daha gecikmeli.
7. **Karaktere özgü hareket**: hedef poza eklenir, sonra yaylardan geçer (ör. Pomni'nin yüzer
   gibi çırpan kolları: gövdenin yan ekseni çevresinde 3 Hz, kollar ters fazda).
8. **Squash & stretch**: hızdan türet (`squash_from_speed`), hacmi koru, en fazla %10-12.
   Elle konan "toplanma squash"ı kök fiziğiyle çelişiyorsa koyma.
9. **Kamera**: karakteri yayla hafif takip eden tilt (kök yüksekliğinin ~%25'i, 2 Hz),
   `handheld` ile 0.3-0.5° titreme, vuruşta `camera_shake` (0.6°, 3-4 kare). Sarsıntı büyükse
   ekrandaki hız eğrisinde çentik yapar.

## Doğrulama (her seferinde, render'dan önce)

1. Ucuz önizleme al (Blender'da Workbench 640x360, saniyeler sürer). Pahalı final render'ı
   (EEVEE + motion blur, 1080p ~20 s/kare) önizleme onaylanmadan başlatma.
2. Her karede ekran konumunu yaz (ör. `meta.json` içinde göğüs noktası) ve ölç:

   ```bash
   python .claude/skills/character-physics/scripts/check_motion.py renders/char1/meta.json chest
   ```

   Üç hatayı raporlar: **hız sıçraması** (duvara çarpma), **yerçekimsiz donma** (hız küçük ve
   değişmiyor), **ters sarsıntı**. Hepsi "yok" olmalı. Beklenen imza: hız negatiften
   pozitife düzgünce geçer, tepe civarında küçük ama sürekli değişir.
3. Kareleri film şeridi olarak incele (her 2-3 karede bir) ve referansla yan yana koy.
   Sadece anahtar karelere bakmak yetmez; sorunlar geçişlerde.

## Sık hatalar (bu projede yaşandı)

- Anahtar pozlar arası yumuşak interpolasyon = "pozu değişen video". Fizik katmanı şart.
- Pozları açı tahmin ederek kurmak: 3B açı → 2B görünüş kafada çevrilemez; kemik eksen
  işaretlerini önce test render'ıyla doğrula, pozu noktalardan çöz.
- Uzuv yön eşlemesinde oranlar farklıysa konum yerine **ekrandaki yön + oransal boy** eşle;
  yoksa çözücü uzvu kameraya dik uzatıp "noktaya" çevirir.
- Derinlik belirsizliği: "bu ayak arkada", "göğüs yere bakıyor" gibi kuralları çözücüye ek
  terim olarak ver; karakter kameraya fazla yaklaşıyorsa kök derinliğini sabitle.
- Blender: `cam.matrix_world` sahne güncellenmeden eskidir; `matrix_basis` kullan veya
  `view_layer.update()` çağır. `pb.head/tail` armature uzayındadır, dünyaya çevirmeyi unutma.
- Uzun render'ı beklerken `pgrep -f "desen"` kullanan bekleme döngüsü kendi komut satırını da
  eşleştirir ve sonsuza kadar bekler (bir saat kaybettirdi). PID ile bekle ya da render'ı ve
  sonraki adımları tek komut zincirinde çalıştır.
- Hızlı ekran geçişlerinde (panel süpürmesi) alt-kare örnek sayısını artır (8-10), yoksa
  basamaklı hayalet görüntü olur; şerit çizim sırası: önce geniş koyu, sonra dar renkli.

## Başka projede kullanma

```python
import sys; sys.path.insert(0, ".claude/skills/character-physics/scripts")
from physics import Ballistic, Spring, RotSpring, drag_angle, squash_from_speed, BONE_SPRING_DEFAULTS

traj = Ballistic.through(hit_pos, 10, hold_pos, 25, gravity=150, fps=60, hang=(0.6, 7))
drag = Spring(0.0, *BONE_SPRING_DEFAULTS["drag"])
for f in range(n):
    pos = traj(f)
    d = drag.step(traj.vz(f), 1 / 60)
    limb_angle = drag_angle(d)              # uzvu dünyada aşağı (+) / yukarı (-) döndür
    scale = squash_from_speed(traj.vz(f))
    # kemikler: RotSpring(ref, start, *BONE_SPRING_DEFAULTS["upper_arm"]).step(hedef, 1/60)
```

Roblox'ta aynı değerler her kare `Motor6D.Transform` / kök `CFrame`'e yazılabilir; Blender'da
her kareye keyframe (Bezier) olarak basılır. Fizik hesaplanıp "bake" edilir, motorun kendi
interpolasyonuna bırakılmaz.
