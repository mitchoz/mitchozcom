"""
Gives every essay its cover as share image (og:image), so a shared link shows the article, not the site logo.

    python -I tools/og_images.py

For each essay folder (a page with <figure class="cover">), writes assets/og/<slug>.jpg at 1200x630
(the size X, LinkedIn, Facebook and messengers expect; JPG because not all of them show WebP) and points the
page's og:image, its size and alt text at it. Run it again after importing an essay or changing a cover.
"""
import html
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.mitchoz.com/"
W, H = 1200, 630
OUT = ROOT / "assets" / "og"


def crop_to_share(im):
    """Fill 1200x630; when cropping height, keep a bit more of the top, where faces and titles usually are."""
    im = im.convert("RGB")
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left = (im.width - W) // 2
    top = round((im.height - H) * 0.35)
    return im.crop((left, top, left + W, top + H))


OUT.mkdir(parents=True, exist_ok=True)
for page in sorted(ROOT.glob("*/index.html")):
    s = page.read_text(encoding="utf-8")
    cover = re.search(r'<figure class="cover"><img src="([^"]+)"', s)
    if not cover:
        continue
    slug = page.parent.name
    src = (page.parent / html.unescape(cover.group(1))).resolve()
    out = OUT / f"{slug}.jpg"
    crop_to_share(Image.open(src)).save(out, "JPEG", quality=85, optimize=True, progressive=True)
    title = html.unescape(re.search(r'<meta property="og:title" content="([^"]*)"', s).group(1))
    url = f"{SITE}assets/og/{slug}.jpg"
    s = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{url}\2", s)
    s = re.sub(r'(<meta property="og:image:width" content=")[^"]*(")', rf"\g<1>{W}\2", s)
    s = re.sub(r'(<meta property="og:image:height" content=")[^"]*(")', rf"\g<1>{H}\2", s)
    s = re.sub(r'(<meta property="og:image:alt" content=")[^"]*(")', lambda m: m.group(1) + html.escape(f"Cover of {title}") + m.group(2), s)
    page.write_text(s, encoding="utf-8", newline="")
    print(f"{slug}: {out.relative_to(ROOT).as_posix()} ({out.stat().st_size // 1024} KB)")
