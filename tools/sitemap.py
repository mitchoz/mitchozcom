"""
Writes sitemap.xml: the homepage, the press kit and every essay, each with the date its page last changed.

    python -I tools/sitemap.py

Run it after adding or changing a page (search engines read it via robots.txt).
"""
import subprocess
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.mitchoz.com/"


def last_changed(path):
    """The page's last commit date, or today if it has uncommitted changes or none yet."""
    rel = path.relative_to(ROOT).as_posix()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    stamp = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return date.today().isoformat() if dirty or not stamp else stamp


pages = [ROOT / "index.html"] + sorted(p for p in ROOT.glob("*/index.html"))
urls = []
for page in pages:
    loc = SITE if page.parent == ROOT else f"{SITE}{page.parent.name}/"
    urls.append(f"  <url><loc>{loc}</loc><lastmod>{last_changed(page)}</lastmod></url>")

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
(ROOT / "sitemap.xml").write_text(xml, encoding="utf-8", newline="\n")
print(f"sitemap.xml: {len(urls)} pages")
