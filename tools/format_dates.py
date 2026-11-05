"""
Shows dates as "01 JUN 2025" (or "JUN 2025") instead of 2025-06-01, which reads differently in the US and Europe.
The ISO date stays in the datetime attribute for search engines and tools.

    python -I tools/format_dates.py

Rewrites every <time> in the site's pages whose text is an ISO date; run it again after importing an essay.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
TIME = re.compile(r'<time(?: datetime="[^"]*")?>(\d{4})-(\d{2})(?:-(\d{2}))?</time>')


def label(year, month, day=None):
    return f"{day} {MONTHS[int(month) - 1]} {year}" if day else f"{MONTHS[int(month) - 1]} {year}"


def human(m):
    year, month, day = m.groups()
    iso = f"{year}-{month}" + (f"-{day}" if day else "")
    return f'<time datetime="{iso}">{label(year, month, day)}</time>'


if __name__ == "__main__":
    pages = [p for p in ROOT.rglob("*.html") if "tools" not in p.parts]
    for page in pages:
        s = page.read_text(encoding="utf-8")
        new, n = TIME.subn(human, s)
        if n:
            page.write_text(new, encoding="utf-8", newline="")
            print(f"{page.relative_to(ROOT).as_posix()}: {n} dates")
