# mitchozcom

The personal site of Misch Strotz: [www.mitchoz.com](https://www.mitchoz.com).

Plain HTML, CSS and one script. No framework, no build step.

## Run it locally

```bash
python -m http.server 5173 --bind 127.0.0.1
```

Then open http://localhost:5173.

## After changing the site

Rebuild the Markdown version for agents (`misch-strotz.md` and `llms.txt`):

```bash
python -I tools/build_md.py
```

Other scripts in `tools/`:

- `notes.mjs`: fills the tweet stories in `notes.json` from post links (`--refresh` updates likes).
- `import_essay.py <slug>`: imports an essay from the old site, then run `localize_assets.py`.
- `thumbs.py`: downloads and compresses the hover thumbnails.

## Deploy

The `Dockerfile` serves the site with nginx (config in `deploy/nginx.conf`). Coolify builds it on every push to `main`.

To try the container locally:

```bash
docker build -t mitchozcom . && docker run --rm -p 8080:80 mitchozcom
```
