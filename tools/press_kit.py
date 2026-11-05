"""
Builds the press kit's previews and zip from the files in press/photos and press/logo.

    python -I tools/press_kit.py

press/photos/*.jpg      the photos as delivered by the photographer (published untouched)
press/previews/*.webp   small versions shown on the press page
press/misch-strotz-press-kit.zip   all photos, logos and a short README with credit and usage
"""
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PRESS = ROOT / "press"
PREVIEW_WIDTH = {"portrait": 640, "landscape": 960}

README = """Misch Strotz: press kit
https://www.mitchoz.com/press/

Free to use for articles, interviews, podcasts, and event or speaker announcements
featuring Misch Strotz.

Questions or higher resolutions: misch@msh.lu
"""

(PRESS / "previews").mkdir(exist_ok=True)
photos = sorted((PRESS / "photos").glob("*.jpg"))
for photo in photos:
    im = Image.open(photo)
    width = PREVIEW_WIDTH["portrait" if im.height > im.width else "landscape"]
    im = im.convert("RGB").resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out = PRESS / "previews" / (photo.stem + ".webp")
    im.save(out, "WEBP", quality=80, method=6)
    print(f"{out.relative_to(ROOT).as_posix()}  {im.size[0]}x{im.size[1]}  {out.stat().st_size // 1024} KB")

# Small square of the first portrait, shown next to the press kit on the homepage.
face = Image.open(PRESS / "photos" / "misch-strotz-01.jpg").convert("RGB").crop((290, 130, 1000, 840))
face.resize((240, 240), Image.LANCZOS).save(PRESS / "previews" / "misch-strotz-square.webp", "WEBP", quality=82, method=6)

zip_path = PRESS / "misch-strotz-press-kit.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("misch-strotz-press-kit/README.txt", README)
    for f in photos + sorted((PRESS / "logo").iterdir()):
        z.write(f, f"misch-strotz-press-kit/{f.parent.name}/{f.name}")
print(f"{zip_path.relative_to(ROOT).as_posix()}  {zip_path.stat().st_size // 1024} KB")
