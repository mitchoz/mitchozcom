"""
Builds the agent-friendly versions of the site from index.html and notes.json:

  misch-strotz.md   everything on the site in one Markdown file
  llms.txt          a short index for AI agents (llmstxt.org), pointing to the file above and the essays

    python -I tools/build_md.py

Run it after changing the site, so both stay in sync with the page.
"""
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.mitchoz.com/"
page = (ROOT / "index.html").read_text(encoding="utf-8")


def text(fragment):
    """Visible text of an HTML fragment, on one line."""
    flat = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())
    return re.sub(r" ([.,;:!?)])", r"\1", flat)


def section(sid):
    m = re.search(rf'<section id="{sid}">(.*?)</section>', page, re.S)
    return m.group(1) if m else ""


def items(fragment):
    """The top-level <li> elements of a list, with any nested lists kept inside them."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"<(/?)li\b[^>]*>", fragment):
        if not m.group(1):
            if depth == 0:
                start = m.end()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                out.append(fragment[start:m.start()])
    return out


def entry(li):
    """(date, title, absolute url, description) of one <li>."""
    # Agents get the ISO date from the datetime attribute; the page shows "01 JUN 2025".
    when = re.search(r'<time(?: datetime="([^"]*)")?[^>]*>(.*?)</time>', li, re.S)
    link = re.search(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
    if not link:
        return None
    paras = [text(p) for p in re.findall(r"<p>(.*?)</p>", li, re.S)]
    desc = " ".join(paras)
    if when and desc.startswith(text(when.group(2))):  # a follow-up's "22 MAY 2026 · ..." line
        desc = desc[len(text(when.group(2))):].lstrip(" ·")
    return ((when.group(1) or text(when.group(2))) if when else "", text(link.group(2)), urljoin(SITE, html.unescape(link.group(1))), desc)


def entries(fragment):
    """(date, title, url, description, follow-ups) for each row; follow-ups are the row's nested links."""
    rows = []
    for li in items(fragment):
        nested = re.search(r'<ol class="story-posts">(.*)</ol>', li, re.S)
        main = entry(li[: nested.start()] if nested else li)
        if main:
            rows.append((*main, [e for e in map(entry, items(nested.group(1))) if e] if nested else []))
    return rows


def bullet(when, title, url, desc, subs=()):
    line = f"- {when} · [{title}]({url})" + (f": {desc}" if desc else "")
    return "\n".join([line] + ["  " + bullet(*s) for s in subs])


def lists_with_headings(fragment):
    """Splits a section with several <h2> lists (e.g. Main projects / Side quests)."""
    parts = re.split(r"<h2>(.*?)</h2>", fragment)
    return [(text(parts[i]), entries(parts[i + 1])) for i in range(1, len(parts), 2)]


# ---------- Masthead ----------
masthead = re.search(r'<header class="masthead">(.*?)</header>', page, re.S).group(1)
bio = text(re.search(r"<h1>.*?</h1>\s*<p>(.*?)</p>", masthead, re.S).group(1))
links = [(text(t), html.unescape(h)) for h, t in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.search(r'<p class="links">(.*?)</p>', masthead, re.S).group(1))]

out = [
    "# Misch Strotz",
    "",
    f"> {bio}",
    "",
    f"Website: {SITE}  ",
    f"Press kit (photos, logo, bio): {SITE}press/  ",
    "Elsewhere: " + " · ".join(f"[{t}]({h})" for t, h in links),
    "",
    f"_This file mirrors {SITE} for AI agents and other readers. Updated {date.today().isoformat()}._",
    "",
]

# ---------- Lists ----------
def heading(sid):
    """The section's heading as shown on the page, so renames carry over."""
    return text(re.search(r"<h2>(.*?)</h2>", section(sid), re.S).group(1))


for sid in ("writing", "talks", "press"):
    out += [f"## {heading(sid)}","", *[bullet(*row) for row in entries(section(sid))], ""]

# ---------- Lore (from notes.json: stories told on X, each starting with how it started) ----------
stories = json.loads((ROOT / "notes.json").read_text(encoding="utf-8-sig"))["stories"]
stories = sorted((s for s in stories if s["posts"] and isinstance(s["posts"][0], dict)), key=lambda s: s["posts"][0]["date"], reverse=True)


def post_line(p, indent=""):
    label = " ".join((p.get("text") or ("Video" if p.get("video") else "Image")).split())
    stats = "only visible on X" if p.get("hidden") else f"{p['likes']:,} likes"
    return f"{indent}- {p['date'][:10]} · [{label}]({p['url']}) ({stats})"


out += [f"## {heading('lore')}", "", "Stories told on X, newest first. Indented posts followed the first one.", ""]
for s in stories:
    posts = [p for p in s["posts"] if isinstance(p, dict)]
    out.append(post_line(posts[0]))
    out += [post_line(p, "  ") for p in posts[1:]]
out.append("")

# ---------- Terms ----------
out += ["## Terms", "", "Concepts coined by Misch Strotz.", ""]
for li in re.findall(r"<li id=[^>]*>(.*?)</li>", section("terms"), re.S):
    year = text(re.search(r"<time>(.*?)</time>", li).group(1))
    tag, name = re.search(r'<a ([^>]*class="term-name"[^>]*)>(.*?)</a>', li, re.S).groups()
    name_href = html.unescape(re.search(r'href="([^"]+)"', tag).group(1))
    definition = text(re.search(r'<span class="term-def">(.*?)</span>', li, re.S).group(1))
    source = text(re.search(r'<span class="term-src">(.*?)</span>', li, re.S).group(1))
    out.append(f"- **[{text(name)}]({urljoin(SITE, name_href)})** ({year}): {definition} {source}")
out.append("")

# ---------- Projects ----------
for heading, rows in lists_with_headings(section("work")):
    out += [f"## {heading}", "", *[bullet(*row) for row in rows], ""]

out += ["## Contact", "", "misch@msh.lu", ""]
(ROOT / "misch-strotz.md").write_text("\n".join(out), encoding="utf-8-sig", newline="\n")

# ---------- llms.txt ----------
essays = [row for row in entries(section("writing")) if row[2].startswith(SITE)]
llms = [
    "# Misch Strotz",
    "",
    f"> {bio}",
    "",
    "Personal site with essays, talks, press, lore (stories told on X), coined terms and projects.",
    "",
    "## Profile",
    "",
    f"- [Misch Strotz (Markdown)]({SITE}misch-strotz.md): everything on the site in one file",
    f"- [Press kit]({SITE}press/): photos, logo, bio and name spellings, free to use for editorial coverage",
    "",
    "## Essays",
    "",
    *[f"- [{title}]({url}): {desc}" for _, title, url, desc, _ in essays],
    "",
]
(ROOT / "llms.txt").write_text("\n".join(llms), encoding="utf-8-sig", newline="\n")

print(f"misch-strotz.md: {len(out)} lines, {sum(1 for l in out if l.startswith('- ') or l.startswith('  - '))} entries")
print(f"llms.txt: {len(essays)} essays")
