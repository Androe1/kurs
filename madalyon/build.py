"""src.html içindeki yazı tipi yer tutucularını base64 Cinzel ile doldurup madalyon.html üretir."""
import base64, pathlib, sys
here = pathlib.Path(__file__).parent
fontdir = pathlib.Path(sys.argv[1])  # @fontsource/cinzel/files
src = (here / "src.html").read_text(encoding="utf-8")
for key, name in {"EXT600": "latin-ext-600", "LAT600": "latin-600", "EXT400": "latin-ext-400", "LAT400": "latin-400"}.items():
    b = base64.b64encode((fontdir / f"cinzel-{name}-normal.woff2").read_bytes()).decode()
    src = src.replace("{{%s}}" % key, b)
(here / "madalyon.html").write_text(src, encoding="utf-8")
print("madalyon.html", len(src))
