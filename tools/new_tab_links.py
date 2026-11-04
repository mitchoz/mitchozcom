"""
Adds target="_blank" rel="noopener" to every <a href> that doesn't set a target,
so links open in a new tab even in browsers that ignore <base target>.

    python -I tools/new_tab_links.py index.html whywelovewhatwecreate/index.html
"""
import re
import sys
from pathlib import Path

LINK = re.compile(r"<a (?![^>]*\btarget=)([^>]*\bhref=)")


def new_tab(html):
    return LINK.sub(r'<a target="_blank" rel="noopener" \1', html)


if __name__ == "__main__":
    for name in sys.argv[1:]:
        path = Path(name)
        before = path.read_text(encoding="utf-8")
        after = new_tab(before)
        path.write_text(after, encoding="utf-8", newline="")
        print(f"{name}: {len(LINK.findall(before))} links updated")
