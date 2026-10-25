# Contributing to Better Aiko

Thanks for helping. Icon requests, fixes to names and tags, and new icons are all welcome.

## Requesting an icon

Open an issue with the **Icon request** template. Say what the icon is for and, if you can, link a similar icon from another set so the metaphor is clear.

## Adding or changing an icon

1. Set up the build tools once (Python 3.10+ and Node 18+):

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements-dev.txt
   ```

2. Add `icons-src/<name>.svg`. Copy a similar source and keep its root attributes. The rules:
   - 20×20 grid, stroke width 1.33, round caps and joins, corner radius 2.5.
   - Keep strokes within about 2.5–17.5 so the icon matches upstream's optical size.
   - Reuse an upstream outline with `<use href="#id"/>` when the icon shares a shape (file, folder, cloud, message…).
   - Badges (plus, check, lock, x, search, arrows) sit in the 12.5–17.5 corner. Leave a gap with `class="cut"`.
   - Set `data-category` (UI, AI, Developer, Files, Social, Media, System, Business) and `data-tags`.
3. Build, then check:

   ```sh
   .venv/bin/python scripts/build-icons.py
   .venv/bin/python scripts/build-icons.py --check
   node --test tests/svg-export.test.cjs
   ```

   The first build adds a `data-id` to the source. Commit the source, `assets/icons.svg` and `index.html` together.
4. Look at the icon next to upstream ones at 20 px, in light and dark, by running `start.command` or `python3 -m http.server 8794`. If it stands out, redraw it.

## Pull requests

- Keep each PR to one change (a few related icons, or one fix).
- Use conventional commit prefixes (`feat:`, `fix:`, `docs:`), as upstream does.
- CI must pass.

By contributing you agree that your work is licensed under the MIT licence in [LICENSE](LICENSE), and you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
