# mitchozcom

The personal site of Misch Strotz: [www.mitchoz.com](https://www.mitchoz.com).

Plain HTML, CSS and one script. No framework, no build step.

## Run it locally

```bash
python -m http.server 5173 --bind 127.0.0.1
```

Then open http://localhost:5173.

## After changing the site

Rebuild what's generated from the pages:

```bash
python -I tools/render_lore.py && python -I tools/localize_x_images.py && python -I tools/format_dates.py && python -I tools/og_images.py && python -I tools/build_md.py && python -I tools/sitemap.py
```

- `render_lore.py`: writes the Lore stories from `notes.json` into `index.html`, with their images in `thumbs/lore/`.
- `localize_x_images.py`: copies images that essays load from X into `assets/x/`.
- `format_dates.py`: shows dates as 01 JUN 2025 (the ISO date stays in `datetime`).
- `og_images.py`: makes each essay's cover its share image (`assets/og/<slug>.jpg`, 1200×630).
- `build_md.py`: the Markdown version for agents (`misch-strotz.md` and `llms.txt`).
- `sitemap.py`: `sitemap.xml` for search engines.

Other scripts in `tools/`:

- `notes.mjs`: fills the Lore stories in `notes.json` from post links (`--refresh` updates likes).
- `import_essay.py <slug>`: imports an essay from the old site, then run `localize_assets.py` and the line above.
- `thumbs.py`: downloads and compresses the hover thumbnails.
- `press_kit.py`: rebuilds the press kit's previews and zip from `press/photos` and `press/logo`.
- `trace_logo.py`: redraws the logo as SVG and large PNGs from `assets/img/logo.png`.

## Deploy

The `Dockerfile` serves the site with nginx (config in `deploy/nginx.conf`). Coolify builds it on every push to `main`.

To try the container locally:

```bash
docker build -t mitchozcom . && docker run --rm -p 8080:80 mitchozcom
```
