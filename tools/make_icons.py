"""
Makes the site's icons and share image from the white logo, on black.

    python -I tools/make_icons.py

  favicon.ico          16, 32 and 48 px, for browser tabs
  favicon-32.png       32 px
  apple-touch-icon.png 180 px, for phone home screens
  og-image.png         1200 x 630, the preview shown when a page is shared (logo small, centered)
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "img" / "logo-white.png"
BLACK = (0, 0, 0, 255)


def trimmed_logo():
    logo = Image.open(LOGO).convert("RGBA")
    return logo.crop(logo.getbbox())  # drop the transparent margin around the mark


def on_black(size, logo_width):
    """A black canvas of `size` with the logo scaled to `logo_width` and centered."""
    logo = trimmed_logo()
    scale = logo_width / logo.width
    mark = logo.resize((round(logo.width * scale), max(1, round(logo.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", size, BLACK)
    canvas.alpha_composite(mark, ((size[0] - mark.width) // 2, (size[1] - mark.height) // 2))
    return canvas


def icon(px):
    # The mark is wide and low, so it fills most of the width to stay legible at tab size.
    return on_black((px, px), round(px * 0.84))


if __name__ == "__main__":
    on_black((1200, 630), 240).convert("RGB").save(ROOT / "og-image.png", optimize=True)
    icon(180).convert("RGB").save(ROOT / "apple-touch-icon.png", optimize=True)
    icon(32).convert("RGB").save(ROOT / "favicon-32.png", optimize=True)
    icon(48).save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for name in ("og-image.png", "apple-touch-icon.png", "favicon-32.png", "favicon.ico"):
        print(f"{name:22} {(ROOT / name).stat().st_size / 1024:.1f} KB")
