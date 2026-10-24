# Dış modeller (SCP sinematiği)

`blender/scp_cinematic.py` bu klasöre bakar. Dosya adı aşağıdaki addan başlıyorsa
(`.glb` / `.gltf` / `.fbx` / `.obj` / `.blend`) blok model yerine o kullanılır.
Ölçek, taban ve merkez otomatik ayarlanır.

| Dosya adı      | Ne                                         | Hedef ölçü    | Nerede          |
|----------------|--------------------------------------------|---------------|-----------------|
| `crate.*`      | Kapalı askerî silah kasası                 | 1.25 m uzunluk | SECURE          |
| `crate_open.*` | Kapağı açık kasa (içi boş; tüfekler eklenir)| 1.25 m        | SECURE          |
| `ammo.*`       | Mühimmat kutusu                            | 0.30 m        | SECURE          |
| `rifle.*`      | Tüfek (namlu ileri)                        | 0.95 m        | açık kasanın içi |
| `apc.*`        | Zırhlı personel taşıyıcı / zırhlı araç     | 7.0 m         | CONTAIN (x2)    |
| `truck.*`      | Askerî kamyon                              | 7.5 m         | PROTECT (park)  |
| `pine.*`       | Çam ağacı                                  | yükseklik ölçeklenir | her planda |

Lisans: CC0 veya CC-BY modeller (CC-BY ise yazarını `CREDITS.md`'ye yaz).
İyi kaynaklar: Poly Haven (CC0), Sketchfab (filtre: Downloadable + CC), Quaternius / Kenney (CC0).

## Yön düzeltme

Kural: **ön (namlu / aracın burnu) +X, yukarı +Z**. Model başka yöne bakıyorsa
`models.json` ile döndür (derece) ya da ölçeği değiştir:

```json
{
  "apc":   {"rot": [0, 0, 90]},
  "rifle": {"rot": [0, 0, 180], "scale": 1.0},
  "truck": {"file": "military_truck_v2.glb", "rot": [0, 0, -90]}
}
```

Dış modellerde farlar aracın burnuna (x = uzunluk/2, z = 1.3 m) otomatik yerleştirilir.
