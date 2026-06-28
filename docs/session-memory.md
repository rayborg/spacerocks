# Session Memory

Last updated: 2026-06-27

## Project Context

- Project is now the static Spacerocks website, replacing the old Meteorite Meta Search dashboard memory.
- Target repo: `https://github.com/rayborg/spacerocks`.
- Target GitHub Pages URL after deployment: `https://rayborg.github.io/spacerocks/`.
- The target repo is public and was empty when checked on 2026-06-27.
- Current worktree remote still points to `https://github.com/rayborg/meteorite-meta-search.git`; update or add a remote before pushing to Spacerocks.
- Current branch is `opencode/eager-pixel`.
- Current task allows edits to the static site, shop inventory source, generated shop data/cache, admin helper, build script, docs, and new build workflow.
- User requested committing and pushing the completed site to `https://github.com/rayborg/spacerocks`; use an orphan `main` publish so legacy `meteorite-meta-search` history is not pushed.

## User Goals

- Build a new low-maintenance static website for Spacerocks.
- Migrate the useful content and imagery from the old Google Site into a cleaner, modern, GitHub Pages-hosted site.
- Present Spacerocks as a personal meteorite/space-rock collection, inquiry shop, and story site, not as a seller-inventory scraper.
- Keep the public site static: HTML, CSS, optional vanilla JavaScript, generated JSON, and a Python stdlib shop builder run locally or by GitHub Actions.
- Make the shop easy to update by uploading an `inventory/shop/<slug>/item.json` file plus images in the same folder.
- Enrich shop listings from the Meteoritical Bulletin Database by exact meteorite `name`, with cached successes and failures.
- Use strong specimen and expedition imagery, concise captions, and approachable science/storytelling copy.
- Preserve the old Google Site material as source content, but do not keep the old Google Sites visual design or fragile image URLs as production dependencies.

## Planned Site Sections

- `Collection`: overview of the collection, specimen highlights, display-gallery feel, and short educational captions.
- `Expeditions`: field trips, hunting stories, travel context, and documentary-style imagery.
- `Stories`: featured meteorite stories such as Aguas Zarcas, Aguas Zarcas hammer material, Santa Filomena parts, and the 190 g puzzle rock.

## Reference-Site Research Notes

Distilled from subagent reference-site research:

- Collector and museum-style sites work best when they lead with photography and a clear identity statement before metadata-heavy details.
- Meteorite dealer sites tend to over-index on catalog tables; Spacerocks should avoid that and feel more like a curated collection/gallery.
- Science and museum references are strongest for plain-language explanation, provenance, classification snippets, and fall/find context.
- Expedition and field-report references work best as cards or story blocks with date/place/context, not as long undifferentiated text.
- The recommended visual direction is dark, space-forward, high-contrast, and image-led, but with restrained effects so the meteorites and stories stay primary.
- Mobile layout matters: stack sections, keep image cards readable, and avoid horizontal table/dashboard patterns from the old project.
- Accessibility basics: semantic sections, descriptive headings, useful image alt text, keyboard-friendly navigation, and adequate contrast.

## Old Google Site Content And Images

- Treat the old Google Site as the source of content and image references for migration.
- Old content themes identified for reuse: collection overview, expeditions, Aguas Zarcas, Aguas Zarcas hammer material, Santa Filomena multi-part story, and the 190 g puzzle rock.
- Direct Google Sites image downloads from `lh3.googleusercontent.com/sitesv/...` are blocked with HTTP 403, so production work should not depend on those URLs.
- Do not try to bypass the 403. Use user-provided originals when available, or use screenshot-derived local fallbacks until originals can be supplied.
- Screenshot fallback images currently exist under `assets/images/spacerock/` and are untracked in this worktree:
- `assets/images/spacerock/source-collection.png`
- `assets/images/spacerock/source-expeditions.png`
- `assets/images/spacerock/source-aguas-zarcas.png`
- `assets/images/spacerock/source-aguas-zarcas-hammer.png`
- `assets/images/spacerock/source-santa-filomena.png`
- `assets/images/spacerock/source-santa-filomena-part-2.png`
- `assets/images/spacerock/source-santa-filomena-part-3.png`
- `assets/images/spacerock/source-puzzle-190g.png`
- These fallback images are PNG screenshots at 1440 x 1200.
- Use the screenshots as migration aids or temporary page imagery, then replace with original/cropped/optimized images if the user supplies better assets.

## Asset Download Blocker

- Blocker: old Google Sites `lh3`/`sitesv` image URLs return HTTP 403 on direct download.
- Decision: do not scrape, mirror, or escalate around the blocked URLs.
- Fallback: use browser screenshots of the old pages/images as temporary local assets.
- Follow-up: ask the user for original image files or a public export if higher-quality final imagery is needed.

## Implementation Decisions

- The new site should be a static GitHub Pages site served directly from the repository root.
- Primary files should remain `index.html`, `styles.css`, `app.js`, generated `data/shop.json`, and local media under `assets/` or item folders.
- No package manager, bundler, framework, or legacy scraper is needed for the Spacerocks site.
- `scripts/build_shop.py` uses only Python stdlib and reads `inventory/shop/**/item.json` to generate `data/shop.json`.
- `data/metbull-cache.json` stores MetBull lookup results keyed by exact official `name`; failures are cached to avoid hammering MetBull on 10-minute schedules.
- `admin/new-listing.html` is a static helper that drafts JSON and folder names. It cannot upload or commit to GitHub without auth/backend.
- `.github/workflows/build-shop.yml` runs on relevant pushes, manual dispatch, and every 10 minutes, then commits only generated shop JSON/cache if they changed.
- Keep copy hand-authored and section-based rather than data-driven.
- Use relative asset paths so the site works at the GitHub Pages project URL `/spacerocks/`.
- Prefer local assets over remote Google Sites URLs for reliability.
- Keep `.nojekyll` so GitHub Pages serves static assets without Jekyll processing surprises.
- The old `data/listings.json`, `data/metbull_names.json`, `scraper/`, and scraper workflows are legacy Meteorite Meta Search leftovers and are not part of the desired Spacerocks shop build.
- If cleanup is requested later, remove legacy scraper/data/workflow content in a dedicated pass after confirming no files are still needed.

## Validation Instructions

Run from the repo root before publishing code changes:

```sh
git status --short
python3 scripts/build_shop.py
python3 -m py_compile scripts/build_shop.py
node --check app.js
git diff --check
python3 -m http.server 8000
```

Then preview `http://localhost:8000/` on desktop and mobile widths.

Do not run `node --check admin/new-listing.html`; it is HTML. If legacy Python scraper files remain untouched, Python scraper validation is not required for Spacerocks-only static-site changes.

## Push And Deployment Instructions

- Commit and push after validation unless a blocker appears.
- Before a future publish, inspect `git status --short`, `git diff`, and `git log --oneline -10`.
- Stage only intended Spacerocks files.
- Make sure no old Meteorite Meta Search generated data or accidental screenshots are staged unless intentionally part of the new site.
- For the final orphan branch publish, stage only intended Spacerocks files and do not delete legacy scraper/data/workflow files unless explicitly requested.
- Point a remote at `https://github.com/rayborg/spacerocks` before pushing. Either update `origin` or add a separate `spacerocks` remote.
- Push the intended branch to the target repo, usually `main`.
- In GitHub, enable Pages from the `main` branch and repository root. Enable the `Build Spacerocks shop` workflow for generated inventory refresh.
- After Pages publishes, verify `https://rayborg.github.io/spacerocks/`.

## Open TODOs

- Decide whether to keep, archive, or delete legacy Meteorite Meta Search files in a separate confirmed cleanup pass after the orphan Spacerocks publish.
- Convert screenshot fallbacks into final web assets, or replace them with original images from the user.
- Write final copy for Collection, Expeditions, and Stories sections.
- Add image alt text and captions for every migrated image.
- Add more real sale listings under `inventory/shop/**` as inventory becomes available.
- Enable GitHub Pages after the first push to the target repo.

## Warnings For Future Agents

- Only edit files the user has granted ownership for in the current task.
- Do not edit `index.html`, `styles.css`, `app.js`, data files, or assets unless explicitly allowed.
- Do not attempt to bypass old Google Sites image 403 responses.
- Do not commit or push when the user says not to commit.
- Use `apply_patch` for manual edits.
- Keep the new site static and simple; the listing helper must not claim direct GitHub uploads without auth/backend.
