"""
Traces the logo (assets/img/logo.png, 207x50 px) into a sharp vector version for the press kit.

The logo is straight strokes of equal width: a lone slash, then two zigzags. Each stroke's left and right
edges are fitted as straight lines from the rows where all strokes are apart; neighbouring strokes meet
where their edges intersect. The result is checked against the original pixels before anything is written.

    python -I tools/trace_logo.py

Writes press/logo/misch-strotz-logo-{black,white}.svg and .png (2000 px wide, transparent).
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "press" / "logo"
src = Image.open(ROOT / "assets" / "img" / "logo.png").convert("RGBA")
W, H = src.size
alpha = src.getchannel("A")
A = alpha.load()


def runs(y):
    """Dark runs in row y as (left edge, right edge) with sub-pixel ends from partial coverage."""
    out, x = [], 0
    while x < W:
        if A[x, y] > 0:
            start = x
            while x < W and A[x, y] > 0:
                x += 1
            cov = [A[i, y] / 255 for i in range(start, x)]
            full = [i for i, c in enumerate(cov) if c > 0.99] or [max(range(len(cov)), key=cov.__getitem__)]
            left = start + full[0] - sum(cov[: full[0]])
            right = start + full[-1] + 1 + sum(cov[full[-1] + 1 :])
            if right - left > 1:
                out.append((left, right))
        else:
            x += 1
    return out


# Rows where every stroke stands apart.
rows = {y: runs(y) for y in range(H)}
count = max(len(r) for r in rows.values())
middle = [y for y, r in rows.items() if len(r) == count]
assert count == 11 and len(middle) > 15, (count, len(middle))


def fit(points):
    """Least-squares line x = a + b*y through (y, x) points."""
    n = len(points)
    my = sum(p[0] for p in points) / n
    mx = sum(p[1] for p in points) / n
    b = sum((y - my) * (x - mx) for y, x in points) / sum((y - my) ** 2 for y, _ in points)
    return (mx - b * my, b)


# Pixel row y covers [y, y+1]; sample edges at the row centre.
L = [fit([(y + 0.5, rows[y][i][0]) for y in middle]) for i in range(count)]
R = [fit([(y + 0.5, rows[y][i][1]) for y in middle]) for i in range(count)]

inked = [y for y in range(H) if any(A[x, y] > 0 for x in range(W))]
bottom = inked[-1] + 1
# The top row is only partly covered; measure how much of it the lone slash's flat top fills.
y0 = inked[0]
slash_ink = sum(A[x, y0] for x in range(int(L[0][0] + L[0][1] * y0) - 1, int(R[0][0] + R[0][1] * y0) + 2)) / 255
top = y0 + 1 - slash_ink / max(1e-6, (R[0][0] - L[0][0]) + (R[0][1] - L[0][1]) * y0)


def at(line, y):
    return line[0] + line[1] * y


def meet(p, q):
    """Where lines p and q cross, as (x, y)."""
    y = (q[0] - p[0]) / (p[1] - q[1])
    return (at(p, y), y)


def clip(vertex, p, q, y_limit, above):
    """A join beyond the logo's top/bottom becomes a flat cut along that line."""
    x, y = vertex
    if (above and y < y_limit) or (not above and y > y_limit):
        return [(at(p, y_limit), y_limit), (at(q, y_limit), y_limit)]
    return [vertex]


# Strokes 1 | 2-7 | 8-11 (a slash, then two zigzags); each zigzag starts with "/" at the bottom.
components = [[0], list(range(1, 7)), list(range(7, 11))]
polygons = []
for comp in components:
    side_a, side_b = [L[comp[0]]], [R[comp[0]]]
    for i in comp[1:]:
        side_a.append(R[i] if len(side_a) % 2 else L[i])
        side_b.append(L[i] if len(side_b) % 2 else R[i])
    a_pts, b_pts = [(at(side_a[0], bottom), bottom)], [(at(side_b[0], bottom), bottom)]
    for j in range(len(comp) - 1):
        joins_top = j % 2 == 0  # "/" then "\" meet at the top, "\" then "/" at the bottom
        for pts, side in ((a_pts, side_a), (b_pts, side_b)):
            v = meet(side[j], side[j + 1])
            pts += clip(v, side[j], side[j + 1], top if joins_top else bottom, above=joins_top)
    end = top if len(comp) % 2 else bottom
    a_pts.append((at(side_a[-1], end), end))
    b_pts.append((at(side_b[-1], end), end))
    polygons.append(a_pts + b_pts[::-1])

# ---------- Check the trace against the original ----------
SS = 8
check = Image.new("L", (W * SS, H * SS), 0)
draw = ImageDraw.Draw(check)
for poly in polygons:
    draw.polygon([(x * SS, y * SS) for x, y in poly], fill=255)
check = check.resize((W, H), Image.BOX)
C = check.load()
diff = sum(abs(C[x, y] - A[x, y]) for x in range(W) for y in range(H)) / 255
ink = sum(A[x, y] for x in range(W) for y in range(H)) / 255
print(f"trace differs from the original by {diff / ink:.1%} of the ink ({diff:.0f} of {ink:.0f} px)")
assert diff / ink < 0.06, "trace does not match the logo closely enough"

# ---------- Write SVG and PNG ----------
x0 = min(x for p in polygons for x, _ in p)
x1 = max(x for p in polygons for x, _ in p)
vw, vh = x1 - x0, bottom - top


def svg(color):
    paths = " ".join("M" + " L".join(f"{x - x0:.2f},{y - top:.2f}" for x, y in poly) + " Z" for poly in polygons)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw:.2f} {vh:.2f}" width="{vw * 4:.0f}" height="{vh * 4:.0f}">'
            f'<title>Misch Strotz</title><path fill="{color}" d="{paths}"/></svg>\n')


OUT.mkdir(parents=True, exist_ok=True)
for name, color in (("black", "#000000"), ("white", "#ffffff")):
    (OUT / f"misch-strotz-logo-{name}.svg").write_text(svg(color), encoding="utf-8", newline="\n")
    width = 2000
    scale = width / vw
    big = Image.new("L", (width * 2, round(vh * scale) * 2), 0)
    d = ImageDraw.Draw(big)
    for poly in polygons:
        d.polygon([((x - x0) * scale * 2, (y - top) * scale * 2) for x, y in poly], fill=255)
    mask = big.resize((width, round(vh * scale)), Image.LANCZOS)
    rgb = (0, 0, 0) if name == "black" else (255, 255, 255)
    png = Image.new("RGBA", mask.size, rgb + (0,))
    png.putalpha(mask)
    png.save(OUT / f"misch-strotz-logo-{name}.png", optimize=True)
    print(f"press/logo/misch-strotz-logo-{name}.svg/.png  ({width}x{mask.size[1]})")
