# Androe Studio - Intro Animasyonu

Simsiyah ekran, beyaz yazı: Roblox oyun stüdyosu **Androe Studio** için
5 saniyelik, ses efektli logo intro'su. Görüntü de ses de tamamen kodla
üretilir; hazır video, görsel ya da ses dosyası kullanılmaz.

Hazır video: [`output/androe_studio_intro.mp4`](output/androe_studio_intro.mp4)
(1920x1080, 60 fps, H.264 + AAC stereo)

## Akış

| Saniye    | Görüntü                                                        | Ses                                      |
|-----------|----------------------------------------------------------------|------------------------------------------|
| 0.2       | Beyaz bir yapı bloğu (üstü çıkıntılı küp) belirir              | yumuşak "pop"                            |
| 0.6 - 0.9 | Küp dönerek sıkışır ve parlar                                  | yükselen enerji sesi                     |
| 0.9       | Küp yüzlerce küçük bloğa ayrılarak patlar                      | derin bas vuruş, çatırtı                 |
| 1.3 - 2.1 | Bloklar uçup ANDROE harflerini soldan sağa, alttan üste kurar  | tıkırtılar + her harfte yükselen bir nota |
| 2.1 - 2.5 | Işık taraması blok harfleri pürüzsüz yazıya çevirir            | parlak çan, ışıltı, sıcak bir akor       |
| 2.4 - 3.0 | Altında STUDIO açılır                                          | hafif hava sesi                          |
| 4.3 - 4.9 | Logo yumuşakça kararır, video siyah biter                      | ses söner                                |

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
- `scene.py` - görsel sahne: küp, patlama, blok harfler, ışık taraması, yazı
- `sound.py` - ses tasarımı: tüm efektler numpy ile sentezlenir
- `fonts/` - Montserrat yazı tipi (SIL Open Font License, bkz. `fonts/OFL.txt`)

## Düzenleme

- Zamanlama: `scene.py` başındaki `T_...` sabitleri (ses de bunlara göre kendini ayarlar)
- Yazılar: `WORD` ve `SUB`
- Blok boyutu: `CELL` (küçüldükçe harfler daha çok bloktan oluşur)
- Notalar ve akor: `sound.py` içindeki `NOTES` ve `CHORD`
