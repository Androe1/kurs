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
| 1.0 - 3.6  | Madalyon dönerek yukarıdan iner, aynadaki ikizi aşağıdan yükselir; aynaya yaklaşınca ışık parlar |
| 3.6 - 5.3  | Hafif yan duruşla süzülür, arka yüzdeki küre nabız gibi parlar |
| 5.3 - 6.5  | Yarım tur: üstte karanlık yüz, altta aydınlık yüz görünür |
| 7.2 - 8.4  | Yarım tur daha, ilk duruşa döner |
| 8.7 - 11   | "BİR MADALYONUN" üstte, "İKİ YÜZÜ" altta belirir |

## Çalıştırma

```bash
cd madalyon
npm install
npm run build      # src.html + Cinzel yazı tipi -> madalyon.html
npm run render     # -> ../output/madalyonun_iki_yuzu.mp4
node render.js out.png --still 4.5,6.9   # tek kareler
```

`madalyon.html` tarayıcıda doğrudan açılıp canlı da izlenebilir (döngüde oynar).

## Dosyalar

- `src.html` - sahne: madalyon geometrisi, kodla çizilen yüz dokuları, ışıklar, zaman çizelgesi (`renderAt`)
- `build.py` - yazı tiplerini gömerek `madalyon.html` üretir
- `render.js` - başsız Chromium ile kare kare çizer, ffmpeg ile MP4 yapar
