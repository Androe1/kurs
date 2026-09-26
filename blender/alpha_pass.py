"""Render edilen RGBA karelerden ayrı silüet (alpha) katmanını yazar: NNN_alpha.png (beyaz = karakter).

    python blender/alpha_pass.py renders/char1 renders/char2
"""
import sys
from pathlib import Path

import numpy as np
import skia

for folder in sys.argv[1:]:
    for f in sorted(Path(folder).glob("[0-9][0-9][0-9].png")):
        a = skia.Image.open(str(f)).toarray(colorType=skia.kRGBA_8888_ColorType)[..., 3]
        out = np.dstack([a, a, a, np.full_like(a, 255)])
        skia.Image.fromarray(np.ascontiguousarray(out), colorType=skia.kRGBA_8888_ColorType).save(
            str(f.with_name(f.stem + "_alpha.png")), skia.kPNG)
    print(folder, "tamam")
