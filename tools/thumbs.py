"""
Makes small local thumbnails for the project list.

    python -I tools/thumbs.py

For every project in index.html whose data-thumb is still a remote URL, downloads the
image, resizes it to 560px wide (2x the 280px it is shown at), saves it as
thumbs/<project>.webp and points data-thumb at that file. Sources are kept in
thumbs/sources.json. To add a project, give its <li> a remote data-thumb and run this again.
"""
import html
import io
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
OUT = ROOT / "thumbs"
WIDTH = 560
QUALITY = 72

ROW = re.compile(r'<li data-thumb="(https?://[^"]+)">(\s*<time[^>]*>[^<]*</time>\s*<div>\s*<a [^>]*href="[^"]*"[^>]*>([^<]+)</a>)')


def slugify(name):
    # Fold accents first (Gëlle -> Gelle) so they don't turn into dashes.
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    # Capped so long article headlines still make sensible filenames.
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:60].rstrip("-")


def fetch(url):
    # Percent-encode characters like © that urllib can't send as-is; leave existing escapes alone.
    url = urllib.parse.quote(url, safe=":/?&=%#+,;@!$'()*~")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def to_webp(data):
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
    if img.width > WIDTH:
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=QUALITY, method=6)
    return buf.getvalue(), img.size


def main():
    page = INDEX.read_text(encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    manifest_path = OUT / "sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    total_in = total_out = 0

    def replace(m):
        nonlocal total_in, total_out
        url, rest, name = html.unescape(m.group(1)), m.group(2), html.unescape(m.group(3))
        slug = slugify(name)
        try:
            data = fetch(url)
            webp, (w, h) = to_webp(data)
        except Exception as e:  # leave the remote URL in place and report
            print(f"  FAILED {name}: {e}")
            return m.group(0)
        (OUT / f"{slug}.webp").write_bytes(webp)
        manifest[slug] = url
        total_in += len(data)
        total_out += len(webp)
        print(f"  {name:20} {len(data) // 1024:>5} KB -> {len(webp) // 1024:>3} KB  ({w}x{h})")
        return f'<li data-thumb="thumbs/{slug}.webp">{rest}'

    page = ROW.sub(replace, page)
    INDEX.write_text(page, encoding="utf-8", newline="")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if total_in:
        print(f"Total: {total_in // 1024} KB -> {total_out // 1024} KB")
    else:
        print("No remote thumbnails left to process.")


if __name__ == "__main__":
    main()
