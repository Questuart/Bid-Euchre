#!/usr/bin/env python
"""Docs freshness gate: validate path references, image references, and script list completeness."""

import re
import sys
from pathlib import Path

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 8-byte PNG file signature
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def check_path_references(docs_dir: Path, repo_root: Path) -> list[str]:
    """Find markdown path references that don't resolve.

    Checks backtick paths containing a slash: `path/to/file.ext`

    Skips:
    - Archive/legacy directories (historical docs with known stale refs)
    - Paths relative to run directories (artifacts/, reports/, datasets/, etc.)
    - Paths under data/runs/ (gitignored generated outputs)
    - Wildcard patterns, Python module refs, URLs
    """
    errors = []
    backtick_re = re.compile(r"`([a-zA-Z0-9_./\-]+/[a-zA-Z0-9_.*\-]+)`")

    # Directories to skip entirely (historical docs with many stale refs)
    skip_dirs = {"archive", "legacy"}

    # Path prefixes that are relative to run directories, not repo root
    run_relative_prefixes = (
        "artifacts/",
        "reports/",
        "datasets/",
        "splits/",
        "logs/",
    )

    # src/bid_euchre/ submodule names — paths starting with these are
    # module-relative shorthand, not repo-root paths
    src_pkg_dir = repo_root / "src" / "bid_euchre"
    src_submodules: set[str] = set()
    if src_pkg_dir.is_dir():
        src_submodules = {
            d.name
            for d in src_pkg_dir.iterdir()
            if d.is_dir() and not d.name.startswith("__")
        }

    for md_file in sorted(docs_dir.rglob("*.md")):
        # Skip files in archive/legacy directories
        if any(part in skip_dirs for part in md_file.relative_to(docs_dir).parts):
            continue

        text = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(repo_root)

        for match in backtick_re.finditer(text):
            ref = match.group(1).strip()
            # Skip patterns with wildcards, Python module refs, URLs
            if "*" in ref or ref.startswith("http") or ref.startswith("<"):
                continue
            # Skip known non-path patterns
            if ref.startswith("random.") or ref.startswith("bid_euchre."):
                continue
            # Skip run-relative paths (not repo-root paths)
            if ref.startswith(run_relative_prefixes):
                continue
            # Skip data/runs/ paths (gitignored generated outputs)
            if ref.startswith("data/runs/"):
                continue
            # Skip src/bid_euchre/ submodule-relative shorthand paths
            first_segment = ref.split("/")[0]
            if first_segment in src_submodules:
                continue
            # Skip generic/template paths (e.g., _deprecated/README.md)
            if ref.startswith("_"):
                continue
            # Skip docs-relative schema paths (schemas/)
            if ref.startswith("schemas/"):
                continue
            # Skip paths that look like Python import paths (no extension, dots)
            if "." not in ref.split("/")[-1] and not ref.endswith("/"):
                # Could be a directory — check
                if not (repo_root / ref).exists() and not (repo_root / ref).is_dir():
                    continue  # Probably not a file path
            if not (repo_root / ref).exists():
                lineno = text[: match.start()].count("\n") + 1
                errors.append(f"{rel}:{lineno}: path not found: `{ref}`")
    return errors


def check_image_references(docs_dir: Path, repo_root: Path) -> list[str]:
    """Find markdown image references that don't resolve or are corrupt.

    Checks ``![alt](path)`` patterns in markdown files.

    For .png files: validates full PNG structure using PIL (if available),
    falling back to 8-byte signature check otherwise.

    Skips:
    - URLs (http:// / https://)
    - Archive/legacy directories
    """
    errors = []
    image_re = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    skip_dirs = {"archive", "legacy"}

    for md_file in sorted(docs_dir.rglob("*.md")):
        if any(part in skip_dirs for part in md_file.relative_to(docs_dir).parts):
            continue

        text = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(repo_root)

        for match in image_re.finditer(text):
            img_path = match.group(2).strip()

            # Skip URLs
            if img_path.startswith(("http://", "https://")):
                continue

            # Resolve relative to the markdown file's parent directory
            resolved = (md_file.parent / img_path).resolve()

            lineno = text[: match.start()].count("\n") + 1

            if not resolved.exists():
                errors.append(f"{rel}:{lineno}: image not found: `{img_path}`")
                continue

            # For .png files, validate structure
            if resolved.suffix.lower() == ".png":
                if HAS_PIL:
                    try:
                        with Image.open(resolved) as img:
                            img.verify()
                    except Exception as exc:
                        errors.append(
                            f"{rel}:{lineno}: invalid PNG: `{img_path}` ({exc})"
                        )
                else:
                    # Fallback: check 8-byte PNG signature
                    with open(resolved, "rb") as f:
                        sig = f.read(8)
                    if sig != _PNG_SIGNATURE:
                        errors.append(
                            f"{rel}:{lineno}: invalid PNG signature: `{img_path}`"
                        )

    return errors


def check_scripts_list_complete(arch_doc: Path, scripts_dir: Path) -> list[str]:
    """Verify ARCHITECTURE.md lists all non-internal, non-private scripts."""
    errors = []
    if not arch_doc.exists():
        return [f"ARCHITECTURE.md not found at {arch_doc}"]
    text = arch_doc.read_text(encoding="utf-8")
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        if py_file.name not in text:
            errors.append(f"ARCHITECTURE.md missing script: {py_file.name}")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    docs_dir = repo_root / "docs"
    scripts_dir = repo_root / "scripts"
    arch_doc = docs_dir / "01_core" / "ARCHITECTURE.md"

    all_errors: list[str] = []

    print("Checking path references in docs/...")
    path_errors = check_path_references(docs_dir, repo_root)
    all_errors.extend(path_errors)

    print("Checking image references in docs/...")
    image_errors = check_image_references(docs_dir, repo_root)
    all_errors.extend(image_errors)

    print("Checking script list completeness...")
    script_errors = check_scripts_list_complete(arch_doc, scripts_dir)
    all_errors.extend(script_errors)

    if all_errors:
        print(f"\nDocs freshness check FAILED ({len(all_errors)} issues):\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("Docs freshness check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
