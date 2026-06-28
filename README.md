# Spacerocks

Spacerocks is a static website for a personal meteorite and space-rock collection. It is intended to migrate the useful content and imagery from the old Google Site into a cleaner GitHub Pages site.

The public site uses section tabs for `Home`, `Shop`, `Collection`, `Adventures`, `Trust`, and `Contact` instead of presenting every section as one long scrolling page.

Target repo: `https://github.com/rayborg/spacerocks`

Expected public URL after GitHub Pages is enabled: `https://rayborg.github.io/spacerocks/`

## Site Sections

- `Shop`: generated inquiry listings from `inventory/shop/**`.
- `Collection`: specimen highlights and collection overview.
- `Expeditions`: field trips, hunting stories, and travel context.
- `Stories`: featured meteorite stories such as Aguas Zarcas, Santa Filomena, and the 190 g puzzle rock.

## Local Preview

Run the shop build when inventory changes, then serve the repository root so relative asset paths behave like they will on GitHub Pages:

```sh
python3 scripts/build_shop.py
```

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000/`.

For static edits, also run:

```sh
python3 -m py_compile scripts/build_shop.py
node --check app.js
git diff --check
```

## Shop Inventory Workflow

Each sellable item lives in its own folder:

```text
inventory/shop/<slug>/item.json
inventory/shop/<slug>/front.jpg
inventory/shop/<slug>/back.jpg
```

Minimal `item.json` fields are:

```json
{
  "title": "Aguas Zarcas slice 3.2 g",
  "name": "Aguas Zarcas",
  "weight_g": 3.2,
  "price_usd": null,
  "status": "inquiry",
  "description": "Short collector-facing description.",
  "type": "Carbonaceous chondrite fall",
  "classification": "CM2",
  "provenance": "Source, packet, or field notes.",
  "badges": ["Carbonaceous", "MetBull"],
  "image_order": ["front.jpg", "back.jpg"],
  "images": [],
  "featured": false,
  "metbull_lookup": true
}
```

Images can be uploaded into the item folder or listed explicitly in `images` as paths such as `assets/images/spacerock/source-puzzle-190g.png`. The static helper at `admin/new-listing.html` drafts JSON and folder names, but it cannot upload or commit files to GitHub because this is a static Pages site with no authenticated backend.

`scripts/build_shop.py` uses only Python stdlib. It writes `data/shop.json`, looks up exact Meteoritical Bulletin matches by `name`, caches successes and failures in `data/metbull-cache.json`, and keeps building with local fields if MetBull is unavailable.

GitHub Actions runs `.github/workflows/build-shop.yml` on relevant pushes, manually via `workflow_dispatch`, and every 10 minutes. The action commits changed `data/shop.json` and `data/metbull-cache.json` back with the GitHub Actions bot.

Before publishing inventory edits, run:

```sh
python3 scripts/build_shop.py
python3 -m py_compile scripts/build_shop.py
node --check app.js
git diff --check
```

## Structure

- `index.html` contains the page markup.
- `styles.css` contains the responsive visual design.
- `app.js` contains optional vanilla JavaScript enhancements.
- `inventory/shop/**/item.json` contains source shop listings and local item images.
- `scripts/build_shop.py` generates `data/shop.json` and `data/metbull-cache.json`.
- `admin/new-listing.html` is a static helper for drafting new listing JSON.
- `assets/images/spacerock/` contains local Spacerocks image assets and screenshot fallbacks from the old Google Site migration.
- `.nojekyll` tells GitHub Pages to serve the static files without Jekyll processing.
- `docs/session-memory.md` records migration context and open TODOs for future sessions.

Legacy Meteorite Meta Search scraper/data files may still exist in this worktree during migration. They are not required for the Spacerocks static website.

## Image Migration Notes

Old Google Sites image URLs using `lh3.googleusercontent.com/sitesv/...` returned HTTP 403 during direct download attempts. Use local screenshot fallbacks or user-provided originals instead of relying on those remote URLs.

## Deployment

1. Push the static site files to `https://github.com/rayborg/spacerocks`, normally on `main`.
2. In GitHub, open the repository settings and enable Pages.
3. Set the Pages source to deploy from the `main` branch and repository root.
4. Confirm the `Build Spacerocks shop` action is enabled so generated shop data refreshes after inventory pushes and on the 10-minute schedule.
5. Wait for Pages to publish, then verify `https://rayborg.github.io/spacerocks/`.

No package install or legacy scraper run is needed for deployment.
