"""
Puts the ASCII logo (tools/ascii_logo.txt) as a comment right after <!doctype html> in each page,
replacing an earlier copy. Visitors only see it with "View source".

    python -I tools/add_ascii.py index.html */index.html
"""
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = (ROOT / "tools" / "ascii_logo.txt").read_text(encoding="utf-8").rstrip()
COMMENT = f"<!--{ART}\n-->"
OLD = re.compile(r"\n<!--\n {7}/ {5}/\\.*?-->", re.S)  # an earlier copy, to replace


def add(html):
    html = OLD.sub("", html)
    return re.sub(r"^(<!doctype html>)", lambda m: m.group(1) + "\n" + COMMENT, html, count=1, flags=re.I)


if __name__ == "__main__":
    for name in (p for arg in sys.argv[1:] for p in glob.glob(arg)):
        path = Path(name)
        path.write_text(add(path.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        print("added to", name)
