"""
Copies images the essays load from X (pbs.twimg.com, in embedded posts) into assets/x/ and points the pages
at the copies, so readers' browsers don't contact X and the images survive if X changes its links.

    python -I tools/localize_x_images.py

Run it after importing an essay that embeds posts. Lore images are handled by tools/render_lore.py.
"""
import io
import os
import re
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "x"
PBS = re.compile(r'https://pbs\.twimg\.com/[^"\'\s)<>]+')

for page in sorted(p for p in ROOT.glob("*/index.html")):
    s = page.read_text(encoding="utf-8")
    found = sorted(set(PBS.findall(s)))
    if not found:
        continue
    for url in found:
        name = re.sub(r"\.\w+$", "", url.split("?")[0].rstrip("/").split("/")[-1]) + ".webp"
        out = OUT / name
        if not out.exists():
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            im = Image.open(io.BytesIO(data)).convert("RGB")
            if im.width > 1080:
                im = im.resize((1080, round(im.height * 1080 / im.width)), Image.LANCZOS)
            OUT.mkdir(parents=True, exist_ok=True)
            im.save(out, "WEBP", quality=82, method=6)
        s = s.replace(url, Path(os.path.relpath(out, page.parent)).as_posix())
    page.write_text(s, encoding="utf-8", newline="")
    print(f"{page.relative_to(ROOT).as_posix()}: {len(found)} images now in assets/x/")
