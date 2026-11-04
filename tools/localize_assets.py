"""
Copies files the pages load from the old mitchoz.com (anything under /public/) into assets/,
and points the pages at the copies, so nothing breaks when the new site replaces the old one.

    python -I tools/localize_assets.py index.html */index.html

Large JPEG/PNG images (over 300 KB) are resized to at most 1600px wide and saved as WebP;
GIFs (they may be animated), small images and audio are copied as they are.
Run it again after importing an essay; files already copied are reused.
"""
import glob
import io
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SITE = "https://www.mitchoz.com/"
OLD = re.compile(r"https?://(?:www\.)?mitchoz\.com/public/([^\"'\s)<>]+)")
BIG = 300 * 1024
MAX_WIDTH = 1600

copied = {}  # old URL -> path relative to ROOT


def fetch(url):
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/?&=%#+,;@!$'()*~"), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read()


def localize(url, rest):
    if url in copied:
        return copied[url]
    rel = Path("assets") / urllib.parse.unquote(rest.split("?")[0])
    suffix = rel.suffix.lower()
    webp = rel.with_suffix(".webp")
    for existing in (rel, webp):
        if (ROOT / existing).exists():
            copied[url] = existing
            return existing
    data = fetch(url)
    target = rel
    if suffix in (".jpg", ".jpeg", ".png") and len(data) > BIG:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
        if img.width > MAX_WIDTH:
            img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=82, method=6)
        data, target = buf.getvalue(), webp
    (ROOT / target).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / target).write_bytes(data)
    print(f"  {rest[:70]:72} -> {target.as_posix()} ({len(data) // 1024} KB)")
    copied[url] = target
    return target


def process(page):
    text = page.read_text(encoding="utf-8")
    here = page.parent

    # In attributes (src, href): a path relative to the page, so the site works from any folder.
    def attr(m):
        target = localize(m.group(2), m.group(3))
        return f'{m.group(1)}"{Path(os.path.relpath(ROOT / target, here)).as_posix()}"'

    text = re.sub(r'((?:src|href|data-thumb)=)"(' + OLD.pattern + r')"', attr, text)
    # Anywhere else (e.g. structured data for search engines): the absolute address on the new site.
    text = OLD.sub(lambda m: SITE + localize(m.group(0), m.group(1)).as_posix(), text)
    page.write_text(text, encoding="utf-8", newline="")


if __name__ == "__main__":
    pages = [Path(p) for arg in sys.argv[1:] for p in glob.glob(arg)]
    for page in pages:
        print(page.as_posix())
        process(page.resolve())
    total = sum((ROOT / p).stat().st_size for p in set(copied.values()))
    print(f"{len(set(copied.values()))} files in assets/, {total // 1024} KB")
