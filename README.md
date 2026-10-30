# walchinsky.com

Personal site for [walchinsky.com](https://walchinsky.com/), built with [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

GitHub Pages publishes the root of `main`. Page source lives in `docs/`. `scripts/sync_site.py` builds the site and copies the generated files to the repository root so the existing Pages setup serves them. The file `.generated-files.txt` lists those generated paths.

## Preview

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdocs serve
```

Open http://127.0.0.1:8000.

## Publish a content change

Edit Markdown in `docs/`, then rebuild the files Pages serves:

```bash
python scripts/sync_site.py
```

Commit both the Markdown and the updated generated files. Continuous integration runs `python scripts/sync_site.py --check` and fails if the root is out of date.
