# Aiko Agent Guide

Aiko is a static icon browser. `index.html` contains the UI and export logic; it loads SVG symbols from `assets/icons.svg`. There is no package build step.

## Editing and Verification

- Preserve each symbol's `viewBox`, fill, stroke, and related SVG attributes when copying or exporting it. Outline and solid icons use different rendering attributes; do not force one shape onto both.
- Run `node --test tests/svg-export.test.cjs` after export changes. The tests exercise `getSvgCode` from `index.html`.
- Serve the repository over HTTP for browser checks so the sprite fetch works. Verify search, color selection, SVG copying, and SVG/PNG downloads for both an outline and a solid icon when changing those flows.
- Keep icon metadata in `index.html` aligned with the symbol identifiers in `assets/icons.svg`.

## Adding Icons

- New icons are drawn as stroked 20x20 sources in `icons-src/<name>.svg` (stroke width 1.33, round caps and joins, centrelines mostly within 2.5–17.5, corner radius 2.5). `scripts/build-icons.py` expands them into single filled paths, compacts them with svgo, and inserts the symbol (sorted by id) and its metadata line. Never hand-edit those generated entries.
- In a source, `<use href="#id"/>` reuses an upstream glyph, `class="cut"` removes an area (add `stroke-width` to cut a gap around a stroke), and `class="fill"` adds a solid shape. Badges sit in the 12.5–17.5 corner, as in upstream's file-add and folder-add.
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`. Build with `.venv/bin/python scripts/build-icons.py`; CI runs it with `--check`, which also fails on unnamed, unsorted or duplicate icons.
