"""
Imports an essay from the old mitchoz.com into the new site.

    python -I tools/import_essay.py whywelovewhatwecreate

Reads https://www.mitchoz.com/<slug>, keeps the text and links exactly as written,
and writes <slug>/index.html in the new layout:
  - X embeds become static post cards (text, images, date, likes) built from X's public
    embed data, without X's tracking script
  - YouTube embeds become privacy-enhanced (youtube-nocookie) players
  - passages listed in ANCHORS get an id, so the homepage's Terms can link straight to them
  - passages listed in SKIP are left out

Images and audio still point at the old site after importing; copy them into the new site with
    python -I tools/localize_assets.py <slug>/index.html
"""
import html
import json
import re
import sys
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://www.mitchoz.com/"

# id -> words from the passage that defines a term (the first passage containing them gets the id)
ANCHORS = {
    "whywelovewhatwecreate": {
        "early-curve": "Whenever a new, more powerful AI tool comes along, I observe",
        "identity-economy": "AI is not erasing reality",
        "mirror-rejection-effect": "I call this form of cognitive dissonance the Mirror Rejection Effect",
    },
    "infiniteinformationloops": {
        "a-priori-fake": "is a condition in which one must assume that all media is potentially fake",
        "synthographic-object": "Without a Story, a Synthographic Object has only one property",
        "infinite-information-loop": "This scenario is what I call the Infinite Information Loop",
    },
}

# for pages that don't show their date
DATES = {
    "letzai": "September 1st 2023",
}

# start of passages to leave out of the new page
SKIP = {
    "whywelovewhatwecreate": [
        "(Note: It's not my intention to put every man and every woman in the same basket",
    ],
}

VOID = {"br", "img", "hr", "meta", "link", "input", "source"}
INLINE_KEEP = {"a": "a", "strong": "strong", "b": "strong", "em": "em", "i": "em", "br": "br"}


# ---------- Minimal DOM ----------
class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or {}), parent, []

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def find(self, pred):
        for c in self.children:
            if isinstance(c, Node):
                if pred(c):
                    return c
                hit = c.find(pred)
                if hit:
                    return hit
        return None

    def elements(self):
        return [c for c in self.children if isinstance(c, Node)]


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("#root")

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


# ---------- Inline HTML ----------
def inline(node):
    out = []
    for c in node.children:
        if isinstance(c, str):
            out.append(html.escape(re.sub(r"\s+", " ", c), quote=False))
            continue
        tag = INLINE_KEEP.get(c.tag)
        if tag == "br":
            out.append("<br>")
        elif tag == "a":
            out.append(f'<a href="{html.escape(c.attrs.get("href", ""))}">{inline(c)}</a>')
        elif tag:
            out.append(f"<{tag}>{inline(c)}</{tag}>")
        else:
            out.append(inline(c))
    return "".join(out).strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def is_caption(node):
    # Captions are italic divs, or small-print divs (the date uses the same class but is read first).
    return node.tag == "div" and ("italic" in (node.attrs.get("style") or "") or "smallfont" in node.classes())


def absolute(src):
    return src if src.startswith("http") else SOURCE + src.lstrip("/")


# ---------- Blocks ----------
def blocks_of(article):
    """Flattens the old layout into a list of (kind, data) blocks."""
    def flatten(el):
        # The collapsible AI summaries and float-clearing divs carry no essay text.
        if el.tag == "div" and ({"summary", "clearfix"} & set(el.classes())):
            return []
        # Chapters and plain wrapper divs (e.g. a centered div around an embed) are unwrapped.
        unwrap = "wrapchapter" in el.classes() or (el.tag == "div" and not el.classes() and not is_caption(el))
        return [x for c in el.elements() for x in flatten(c)] if unwrap else [el]

    items = [x for el in article.elements() for x in flatten(el)]

    blocks, meta = [], {}
    for i, el in enumerate(items):
        nxt = next((n for n in items[i + 1:i + 4] if is_caption(n)), None)
        if el.tag == "h1":
            meta["title"] = el.text().strip()
        elif el.tag == "p" and "title" in meta and "dek" not in meta:
            meta["dek"] = el.text().strip()
        elif "smallfont" in el.classes() and "date" not in meta:
            meta["date"] = el.text().strip()
        elif el.tag == "img" and "txtimg" in el.classes() and "cover" not in meta and not blocks:
            meta["cover"] = absolute(el.attrs["src"])
        elif el.tag == "h3":
            blocks.append(("h2", el.text().strip()))
        elif el.tag == "p":
            # Images wrapped in a paragraph become figures; the text (if any) stays a paragraph.
            for im in (n for n in iter_nodes(el) if n.tag == "img"):
                blocks.append(("figure", (absolute(im.attrs["src"]), im.attrs.get("alt", ""), "")))
            # Some pages separate paragraphs with blank lines (<br><br>) inside one <p>.
            for part in re.split(r"(?:<br>\s*){2,}", inline(el)):
                part = re.sub(r"^(?:<br>\s*)+|(?:\s*<br>)+$", "", part.strip())
                if part:
                    blocks.append(("p", part))
        elif is_caption(el) and not any(
                n.tag in ("img", "iframe") and absolute(n.attrs.get("src", "")) != meta.get("cover")
                for n in items[max(0, i - 3):i]):
            # Caption-styled lines that don't sit under an image or video are part of the text.
            blocks.append(("p", inline(el)))
        elif el.tag == "h4":
            blocks.append(("key", inline(el)))
        elif el.tag == "img" and "p33" in el.classes():
            # Images shown three in a row become one gallery.
            if blocks and blocks[-1][0] == "gallery":
                blocks[-1][1].append(absolute(el.attrs["src"]))
            else:
                blocks.append(("gallery", [absolute(el.attrs["src"])]))
        elif el.tag == "img":
            blocks.append(("figure", (absolute(el.attrs["src"]), el.attrs.get("alt", ""), inline(nxt) if nxt else "")))
        elif el.tag == "audio":
            src = el.attrs.get("src") or next((s.attrs.get("src") for s in iter_nodes(el) if s.tag == "source"), None)
            if src:
                blocks.append(("audio", absolute(src)))
        elif el.tag == "blockquote" and "instagram-media" in el.classes():
            link = el.attrs.get("data-instgrm-permalink") or next(
                (a.attrs["href"] for a in iter_nodes(el) if a.tag == "a" and "instagram.com" in a.attrs.get("href", "")), None)
            if link:
                blocks.append(("instagram", link.split("?")[0]))
        elif el.tag == "iframe" and "youtube" in el.attrs.get("src", ""):
            vid = re.search(r"embed/([\w-]+)", el.attrs["src"]).group(1)
            blocks.append(("video", (vid, inline(nxt) if nxt else "Video")))
        elif el.tag == "blockquote" and "twitter-tweet" in el.classes():
            link = [a for a in iter_nodes(el) if a.tag == "a" and "/status/" in a.attrs.get("href", "")][-1]
            pid = re.search(r"status/(\d+)", link.attrs["href"]).group(1)
            p = el.find(lambda n: n.tag == "p")
            text = re.sub(r"\s*(pic\.twitter\.com/\S+|https://t\.co/\S+)", "", p.text()).strip() if p else ""
            blocks.append(("post", (pid, text)))
    return meta, blocks


def iter_nodes(node):
    for c in node.children:
        if isinstance(c, Node):
            yield c
            yield from iter_nodes(c)


# ---------- Rendering ----------
def fetch_post(pid):
    """Post data from X's public embed endpoint (it doesn't check the token). None if X hides it."""
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={pid}&lang=en&token=0"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        j = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        print(f"  post {pid}: {e}")
        return None
    return j if j.get("id_str") else None


def post_text(j):
    """Text with attached-media links dropped and other t.co links expanded."""
    text = j.get("text", "")
    for m in j.get("entities", {}).get("media", []):
        text = text.replace(m["url"], "")
    for u in j.get("entities", {}).get("urls", []):
        text = text.replace(u["url"], u["expanded_url"])
    # X sends text HTML-escaped; decode so linkify() doesn't escape it twice.
    return html.unescape(text.strip())


def linkify(text):
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', escaped)
    return escaped.replace("\n", "<br>")


def render_post(pid, fallback_text):
    j = fetch_post(pid)
    url = f"https://x.com/mitch0z/status/{pid}"
    if not j:
        # X hides some posts from embeds; fall back to the text quoted on the old page.
        return (f'<figure class="embed post"><blockquote cite="{url}"><p>{linkify(fallback_text)}</p></blockquote>'
                f'<figcaption><a href="{url}">View on X</a></figcaption></figure>')

    user = j.get("user", {})
    d = datetime.strptime(j["created_at"][:10], "%Y-%m-%d")
    date = f"{d:%b} {d.day}, {d.year}"
    text = post_text(j)
    parts = [f'<p class="post-author"><strong>{html.escape(user.get("name", ""))}</strong> '
             f'<span class="meta">@{html.escape(user.get("screen_name", ""))}</span></p>']
    if text:
        parts.append(f'<p class="post-text">{linkify(text)}</p>')
    q = j.get("quoted_tweet")
    if q and post_text(q):
        parts.append(f'<p class="post-quote">Quoting @{html.escape(q.get("user", {}).get("screen_name", ""))}: '
                     f'{linkify(post_text(q))}</p>')

    video = next((m for m in j.get("mediaDetails", []) if m.get("type") != "photo"), None)
    if video:
        parts.append(f'<a class="post-media n-1 is-video" href="{url}" aria-label="Play video on X">'
                     f'<img src="{html.escape(video["media_url_https"])}" alt="" loading="lazy"><span class="play">▶</span></a>')
    elif j.get("photos"):
        photos = j["photos"][:4]
        imgs = "".join(f'<img src="{html.escape(p["url"])}?name=small" alt="" loading="lazy">' for p in photos)
        parts.append(f'<a class="post-media n-{len(photos)}" href="{url}" aria-label="Open images on X">{imgs}</a>')

    likes = j.get("favorite_count", 0)
    return (f'<figure class="embed post"><blockquote cite="{url}">{"".join(parts)}</blockquote>'
            f'<figcaption><a href="{url}">{date}</a> · {likes:,} likes · View on X</figcaption></figure>')


def render(slug, meta, blocks):
    anchors = ANCHORS.get(slug, {})
    skip = SKIP.get(slug, [])
    plain = lambda content: re.sub(r"<[^>]+>", "", html.unescape(content))

    used = set()

    def anchor_for(content):
        aid = next((a for a, words in anchors.items() if a not in used and words in plain(content)), None)
        if aid:
            used.add(aid)
        return aid

    body = []
    for kind, data in blocks:
        if kind == "h2":
            body.append(f'<h2 id="{slugify(data)}">{html.escape(data)}</h2>')
        elif kind in ("p", "key"):
            if any(plain(data).startswith(s) for s in skip):
                continue
            aid = anchor_for(data)
            attrs = (' class="key"' if kind == "key" else "") + (f' id="{aid}"' if aid else "")
            body.append(f"<p{attrs}>{data}</p>")
        elif kind == "figure":
            src, alt, cap = data
            cap_html = f"<figcaption>{cap}</figcaption>" if cap else ""
            body.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy">{cap_html}</figure>')
        elif kind == "video":
            vid, cap = data
            body.append(
                f'<figure class="embed video"><div class="frame">'
                f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{html.escape(plain(cap))}" loading="lazy" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>'
                f'<figcaption>{cap}</figcaption></figure>')
        elif kind == "post":
            body.append(render_post(*data))
        elif kind == "gallery":
            imgs = "".join(f'<img src="{html.escape(s)}" alt="" loading="lazy">' for s in data)
            body.append(f'<figure class="gallery n-{len(data)}">{imgs}</figure>')
        elif kind == "audio":
            body.append(f'<figure class="embed audio"><audio controls preload="none" src="{html.escape(data)}"></audio>'
                        f'<figcaption>Listen to this article</figcaption></figure>')
        elif kind == "instagram":
            body.append(f'<p class="embed-link"><a href="{html.escape(data)}">View this post on Instagram</a></p>')

    # Old pages write dates as "December 11th 2025", "September 1st, 2023" or "January 16, 2025".
    plain_date = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", meta["date"]).replace(",", "")
    date_iso = datetime.strptime(" ".join(plain_date.split()), "%B %d %Y").date().isoformat()
    title, dek = meta["title"], meta.get("dek", "")
    ld = {
        "@context": "https://schema.org", "@type": "Article", "headline": title, "description": dek,
        "datePublished": date_iso, "image": meta.get("cover"), "url": f"https://www.mitchoz.com/{slug}/",
        "author": {"@type": "Person", "name": "Misch Strotz", "url": "https://www.mitchoz.com/"},
    }
    cover = f'<figure class="cover"><img src="{html.escape(meta["cover"])}" alt=""></figure>' if meta.get("cover") else ""
    nl = "\n      "
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · Misch Strotz</title>
  <meta name="description" content="{html.escape(dek)}">
  <link rel="canonical" href="https://www.mitchoz.com/{slug}/">
  <link rel="icon" href="../favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="32x32" href="../favicon-32.png">
  <link rel="apple-touch-icon" href="../apple-touch-icon.png">
  <meta name="theme-color" content="#000000">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Misch Strotz">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(dek)}">
  <meta property="og:url" content="https://www.mitchoz.com/{slug}/">
  <meta property="og:image" content="https://www.mitchoz.com/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="The Misch Strotz logo on black">
  <meta property="article:published_time" content="{date_iso}">
  <meta property="article:author" content="Misch Strotz">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:site" content="@mitch0z">
  <meta name="twitter:creator" content="@mitch0z">
  <link rel="preload" href="../assets/fonts/source-serif-4-latin-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="../styles.css">
  <script>
    // Hold the text back for a moment so app.js can scramble it in; skipped with reduced motion, never longer than 1 s.
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {{
      document.documentElement.classList.add("scramble-wait");
      setTimeout(() => document.documentElement.classList.remove("scramble-wait"), 1000);
    }}
  </script>
  <base target="_blank">
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
  <main class="essay">
    <nav class="crumb"><a href="../"><img class="logo logo--ink" src="../assets/img/logo.png" alt="Misch Strotz" width="207" height="50"><img class="logo logo--paper" src="../assets/img/logo-white.png" alt="Misch Strotz" width="207" height="50"></a></nav>
    <header>
      <h1>{html.escape(title)}</h1>
      <p class="dek">{html.escape(dek)}</p>
      <p class="meta"><time datetime="{date_iso}">{date_iso[8:10]} {"JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()[int(date_iso[5:7]) - 1]} {date_iso[:4]}</time></p>
    </header>
    {cover}
    <article>
      {nl.join(body)}
    </article>
    <p class="support">If you liked this article, you can <a href="https://buymeacoffee.com/mitch0z">buy me a coffee</a> or <a href="https://x.com/mitch0z">follow me on X</a>.</p>
    <footer><a href="../">Misch Strotz</a> · © 2026</footer>
  </main>

  <div class="preview" id="preview" hidden></div>
  <script src="../app.js"></script>
</body>
</html>
"""


def main(slug):
    req = urllib.request.Request(SOURCE + slug, headers={"User-Agent": "Mozilla/5.0"})
    source = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    tb = TreeBuilder()
    tb.feed(source)
    # Some pages split the article into several wraparticle blocks; read them all, in order.
    parts = [n for n in iter_nodes(tb.root) if "wraparticle" in n.classes()]
    if not parts:
        sys.exit("No article found on the page.")
    article = Node("#article")
    article.children = [c for part in parts for c in part.children]
    meta, blocks = blocks_of(article)
    meta.setdefault("date", DATES.get(slug))

    out = ROOT / slug / "index.html"
    out.parent.mkdir(exist_ok=True)
    # Every link opens in a new tab (same rule as tools/new_tab_links.py; -I can't import it).
    page = re.sub(r"<a (?![^>]*\btarget=)([^>]*\bhref=)", r'<a target="_blank" rel="noopener" \1', render(slug, meta, blocks))
    # The ASCII logo for people who view the source (same as tools/add_ascii.py does for other pages).
    art = (ROOT / "tools" / "ascii_logo.txt").read_text(encoding="utf-8").rstrip()
    page = page.replace("<!doctype html>", f"<!doctype html>\n<!--{art}\n-->", 1)
    out.write_text(page, encoding="utf-8")

    counts = {}
    for kind, _ in blocks:
        counts[kind] = counts.get(kind, 0) + 1
    found = [a for a in ANCHORS.get(slug, {}) if f'id="{a}"' in out.read_text(encoding="utf-8")]
    print(f"{out.relative_to(ROOT)}: {meta.get('title')!r}, {meta.get('date')}")
    print("  blocks:", counts)
    print("  anchors:", found, "of", list(ANCHORS.get(slug, {})))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "whywelovewhatwecreate")
