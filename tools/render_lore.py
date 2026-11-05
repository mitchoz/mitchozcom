"""
Writes the Lore stories from notes.json into index.html, so search engines, link previews and agents
see them without running JavaScript. Each post's image is copied into thumbs/lore/ (no loading from X).

    python -I tools/render_lore.py

Run it after changing notes.json (e.g. after node tools/notes.mjs). The markup matches what the page
used to build in the browser: one row per story, follow-ups indented under it.
"""
import html
import io
import json
import re
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
THUMBS = ROOT / "thumbs" / "lore"
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
A = 'target="_blank" rel="noopener"'
START = '<ol class="entries" id="notes-list">'
END = "<!-- /lore -->"


def esc(s):
    return html.escape(s, quote=True)


def one_line(s):
    return re.sub(r"\s*\n+\s*", " ", s)


def day(iso):
    y, m, d = iso[:10].split("-")
    return f'<time datetime="{iso[:10]}">{d} {MONTHS[int(m) - 1]} {y}</time>'


def stats(p):
    return "Only visible on X" if p.get("hidden") else f"{p['likes']:,} likes · {p['replies']:,} replies"


def link(p):
    text = one_line(p["text"]) if p.get("text") else "Age-restricted post on X" if p.get("hidden") else "Video" if p.get("video") else "Image"
    return f'<a {A} href="{esc(p["url"])}">{esc(text)}</a>'


def quote(p, story_urls):
    q = p.get("quote")
    if not q or q["url"] in story_urls:
        return ""  # quoting a post of the same story repeats what's already on screen
    return f'<p>Quoting <a {A} href="{esc(q["url"])}">{esc(one_line(q["text"]) if q.get("text") else "a post")}</a></p>'


def thumb(p):
    """Local hover image for a post (its video frame or first photo); "" for text-only posts."""
    src = p.get("video") or (p.get("photos") or [None])[0]
    if not src:
        return ""
    out = THUMBS / f"{p['id']}.webp"
    if not out.exists():
        url = f"{src}?name=small" if "/media/" in src else src
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width > 560:
            im = im.resize((560, round(im.height * 560 / im.width)), Image.LANCZOS)
        THUMBS.mkdir(parents=True, exist_ok=True)
        im.save(out, "WEBP", quality=80, method=6)
        print(f"  thumbs/lore/{out.name} ({out.stat().st_size // 1024} KB)")
    return out.relative_to(ROOT).as_posix()


def story_html(posts, indent):
    first, *follow = posts
    urls = {p["url"] for p in posts}
    rows = [f'<li class="story" data-thumb="{thumb(first)}">{day(first["date"])}<div>',
            link(first) + quote(first, urls) + f"<p>{stats(first)}</p>"]
    if follow:
        rows.append('<ol class="story-posts">' + "".join(
            f'<li data-thumb="{thumb(p)}">{link(p)}{quote(p, urls)}<p>{day(p["date"])} · {stats(p)}</p></li>' for p in follow
        ) + "</ol>")
    rows.append("</div></li>")
    return indent + "".join(rows)


stories = json.loads((ROOT / "notes.json").read_text(encoding="utf-8-sig"))["stories"]
shown = []
for s in stories:
    posts = sorted((p for p in s["posts"] if isinstance(p, dict) and p.get("date")), key=lambda p: p["date"])
    if posts:
        shown.append(posts)  # links the notes script hasn't filled in yet are skipped
shown.sort(key=lambda ps: ps[0]["date"], reverse=True)

page_path = ROOT / "index.html"
page = page_path.read_text(encoding="utf-8")
m = re.search(re.escape(START) + r"(.*?)(?:" + re.escape(END) + r")?\s*</ol>(?=\s*</section>)", page, re.S)
assert m, "Lore list not found in index.html"
indent = "        "
body = "\n".join(story_html(ps, indent) for ps in shown)
new = f"{START}\n        <!-- Built by tools/render_lore.py from notes.json; edit those, not this. -->\n{body}\n        {END}\n      </ol>"
page = page[: m.start()] + new + page[m.end():]
page_path.write_text(page, encoding="utf-8", newline="")
print(f"index.html: {len(shown)} stories, {sum(len(ps) for ps in shown)} posts")
