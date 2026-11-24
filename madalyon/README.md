# Bir Madalyonun İki Yüzü

11 saniyelik 3B madalyon animasyonu. Ekranın ortasında yatay bir ayna var:
üstte aydınlık dünya ve madalyonun **ön yüzü** (altın güneş, ortasında karanlık bir tutulma),
altta karanlık dünya ve aynada madalyonun **arka yüzü** (gece hilali, kucağında parlayan bir küre).
Aydınlığın içinde karanlık, karanlığın içinde aydınlık.

Hazır video: [`../output/madalyonun_iki_yuzu.mp4`](../output/madalyonun_iki_yuzu.mp4) (1920x1080, 60 fps, H.264, sessiz)

| Saniye     | Olay |
|------------|------|
| 0.25 - 1.5 | Karanlıkta ortadan iki yana ayna çizgisi çizilir |
| 0.9 - 3.0  | Üst yarı aydınlanır, alt yarıda yıldızlar belirir |
| 1.1 - 2.1  | Madalyon dönerek serbest düşer (yerçekimi), aynadaki ikizi aşağıdan yükselir |
| ~2.5       | Aynanın alanı onu yay gibi yakalar; aynaya en yakın anda ışık patlar, kamera hafifçe sarsılır |
| 2.5 - 5.3  | Dönüş sürtünmeyle söner, yalpa (presesyon) sönümlenir; madalyon nefes alır gibi süzülür |
| 5.3 / 7.35 | Yay sürüşlü yarım turlar: hafif aşıp oturur, dönerken yükselir, eylemsizlikle yana yatar |
| 8.7 - 11   | "BİR MADALYONUN" üstte, "İKİ YÜZÜ" altta belirir |

## Fizik

- **Düşüş:** `y = y0 - ½gt²`, sonra sönümlü yay (ω=7, ζ=0.65) ile süzülme yüksekliğine oturur.
- **Dönüş:** açısal konum `REST - Θ·e^(-kτ)`; hız üstel söner, hızla orantılı presesyon yalpası eşlik eder.
- **Çevirmeler:** hedef açıya basamak yanıtlı yay (ω=4.4, ζ=0.62); açısal hız kaldırma, açısal ivme yatma üretir.
- Her şey zamanın saf fonksiyonu: herhangi bir kare tek başına yeniden üretilebilir.

## Işık ve görüntü

- Aydınlık dünya: gezen sıcak anahtar ışık, arkadan sıcak kontur, soğuk dolgu, stüdyo ortam yansımaları.
- Karanlık dünya: arkadan iki soğuk ay konturu, zayıf ay anahtarı, kürenin kendi sıcak nokta ışığı.
- HDR (half-float) çizim → bloom → 8 alt-kare birikimi (180° obtüratörle gerçek hareket bulanıklığı + Halton
  titreşimli kenar yumuşatma) → film ton eşlemesi, vinyet, çok hafif renk sapması ve film greni.

## Çalıştırma

```bash
cd madalyon
npm install
npm run build      # src.html + Cinzel yazı tipi -> madalyon.html
npm run render     # -> ../output/madalyonun_iki_yuzu.mp4  (--sub 8: alt-kare sayısı)
node render.js out.png --still 4.5,6.9   # tek kareler
```

`madalyon.html` tarayıcıda doğrudan açılıp canlı da izlenebilir (döngüde oynar).

## Dosyalar

- `src.html` - sahne: madalyon geometrisi, kodla çizilen yüz dokuları, ışıklar, zaman çizelgesi (`renderAt`)
- `build.py` - yazı tiplerini gömerek `madalyon.html` üretir
- `render.js` - başsız Chromium ile kare kare çizer, ffmpeg ile MP4 yapar
