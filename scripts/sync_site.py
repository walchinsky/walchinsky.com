#!/usr/bin/env python3
"""Build the MkDocs site and copy it to the repository root.

GitHub Pages for walchinsky.com serves the root of the main branch.
Markdown stays in docs/. Generated paths are recorded in
.generated-files.txt so a later build can remove stale pages.
"""

from __future__ import annotations

import argparse
import filecmp
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".generated-files.txt"
SITEMAP = "sitemap.xml"
SITEMAP_GZ = "sitemap.xml.gz"

# Source and project files. Never delete or overwrite these.
PROTECTED = {
    ".generated-files.txt",
    ".git",
    ".github",
    ".gitignore",
    "CNAME",
    "README.md",
    "docs",
    "mkdocs.yml",
    "requirements.txt",
    "scripts",
}

HREF_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
LASTMOD_RE = re.compile(r"\n[ \t]*<lastmod>[^<]*</lastmod>")


def build_site(dest: Path) -> None:
    env = os.environ.copy()
    # Material prints an end-of-life notice that is not a build failure.
    env.setdefault("NO_MKDOCS_2_WARNING", "1")
    subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(dest)],
        cwd=ROOT,
        check=True,
        env=env,
    )


def normalize(site: Path) -> None:
    """Make the artifact deterministic and safe for legacy GitHub Pages.

    Pages runs Jekyll unless .nojekyll is present. Jekyll would skip
    underscore paths and might rewrite the static site.
    """
    (site / ".nojekyll").write_bytes(b"")
    sitemap = site / SITEMAP
    if not sitemap.is_file():
        return
    text = LASTMOD_RE.sub("", sitemap.read_text(encoding="utf-8"))
    if not text.endswith("\n"):
        text += "\n"
    sitemap.write_text(text, encoding="utf-8")
    gz_path = site / SITEMAP_GZ
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_path.open("wb"), mtime=0) as handle:
        handle.write(text.encode("utf-8"))


def generated_files(site: Path) -> list[str]:
    files: list[str] = []
    for path in site.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(site).as_posix()
        if is_protected(rel):
            continue
        files.append(rel)
    return sorted(files)


def read_manifest() -> list[str]:
    if not MANIFEST.is_file():
        return []
    return [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_protected(rel: str) -> bool:
    top = rel.split("/", 1)[0]
    return rel in PROTECTED or top in PROTECTED


def check_links(site: Path) -> None:
    errors: list[str] = []
    site_root = site.resolve()
    for html in site.rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        for match in HREF_RE.finditer(text):
            url = match.group(1).strip()
            if not url or url.startswith(("#", "mailto:", "data:", "javascript:", "http://", "https://", "//")):
                continue
            path = url.split("#", 1)[0]
            if not path:
                continue
            if path.startswith("/"):
                target = (site / path.lstrip("/")).resolve()
            else:
                target = (html.parent / path).resolve()
            try:
                target.relative_to(site_root)
            except ValueError:
                errors.append(f"{html.relative_to(site)} escapes site: {url}")
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"{html.relative_to(site)} -> {url}")
    if errors:
        print("Broken local links:")
        for error in errors:
            print(f"  {error}")
        raise SystemExit(1)


def diff_against_root(site: Path, files: list[str]) -> int:
    problems = False
    for rel in files:
        src = site / rel
        dst = ROOT / rel
        if not dst.is_file():
            print(f"missing: {rel}")
            problems = True
        elif not filecmp.cmp(src, dst, shallow=False):
            print(f"differs: {rel}")
            problems = True
    for rel in sorted(set(read_manifest()) - set(files)):
        print(f"stale: {rel}")
        problems = True
    if read_manifest() != files:
        print("manifest does not match the build")
        problems = True
    if problems:
        return 1
    print(f"Generated site matches the repository root ({len(files)} files).")
    return 0


def remove_stale(previous: list[str], current: set[str]) -> None:
    for rel in previous:
        if rel in current or is_protected(rel):
            continue
        path = ROOT / rel
        if path.is_file():
            path.unlink()
    parents = { (ROOT / rel).parent for rel in previous if not is_protected(rel) }
    for parent in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        while parent != ROOT:
            if is_protected(parent.relative_to(ROOT).as_posix()):
                break
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def publish(site: Path, files: list[str]) -> None:
    blocked = [rel for rel in files if is_protected(rel)]
    if blocked:
        raise SystemExit("Refusing to overwrite protected paths: " + ", ".join(blocked))
    remove_stale(read_manifest(), set(files))
    for rel in files:
        destination = ROOT / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site / rel, destination)
    MANIFEST.write_text("\n".join(files) + "\n", encoding="utf-8")
    print(f"Published {len(files)} files to the repository root.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed site differs from a fresh build.",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mkdocs-site-") as tmp:
        site = Path(tmp)
        build_site(site)
        normalize(site)
        check_links(site)
        files = generated_files(site)
        if args.check:
            return diff_against_root(site, files)
        publish(site, files)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
