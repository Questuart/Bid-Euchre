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
        # Report-relative paths used in generated report bundles
        "tables/",
        "full_chart_suite/",
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
            # Skip absolute paths (machine-specific, not repo-relative)
            if ref.startswith("/"):
                continue
            # Skip known non-path patterns
            if ref.startswith("random.") or ref.startswith("bid_euchre."):
                continue
            # Skip run-relative paths (not repo-root paths)
            if ref.startswith(run_relative_prefixes):
                continue
            # Skip data/runs/, data/artifacts/, and data/events/ paths
            # (gitignored generated outputs — runtime artifacts)
            if ref.startswith(("data/runs/", "data/artifacts/", "data/events/")):
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


def check_internal_scripts_listed(
    arch_doc: Path, internal_scripts_dir: Path
) -> list[str]:
    """Verify ARCHITECTURE.md lists all non-private scripts in scripts/internal/.

    Checks by full path (``scripts/internal/{name}``) to avoid false positives
    from deprecation wrappers at ``scripts/`` that share the same basename.
    """
    errors = []
    if not arch_doc.exists():
        return [f"ARCHITECTURE.md not found at {arch_doc}"]
    if not internal_scripts_dir.is_dir():
        return []
    text = arch_doc.read_text(encoding="utf-8")
    for py_file in sorted(internal_scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        expected_token = f"scripts/internal/{py_file.name}"
        if expected_token not in text:
            errors.append(f"ARCHITECTURE.md missing internal script: {expected_token}")
    return errors


def check_no_duplicate_headings(doc_path: Path) -> list[str]:
    """Flag duplicate ``## `` (H2) headings within a single markdown doc.

    Only checks H2 — duplicate H3 under different H2 parents is valid.
    Reports both line numbers for each duplicate.
    """
    errors = []
    if not doc_path.exists():
        return []
    text = doc_path.read_text(encoding="utf-8")
    heading_re = re.compile(r"^## (.+)$", re.MULTILINE)
    seen: dict[str, int] = {}
    for match in heading_re.finditer(text):
        heading = match.group(1).strip()
        lineno = text[: match.start()].count("\n") + 1
        if heading in seen:
            errors.append(
                f"{doc_path.name}:{lineno}: duplicate H2 '## {heading}' "
                f"(first at line {seen[heading]})"
            )
        else:
            seen[heading] = lineno
    return errors


def check_command_contracts(docs_dir: Path, repo_root: Path) -> list[str]:
    """Scan bash/sh/untagged fenced code blocks for command contract violations.

    Checks:
    1. ``run_experiment.py`` without ``--seed`` or ``--allow-nondeterministic``
    2. ``pip install -r requirements.txt`` (stale install method)

    Only scans ``bash``, ``sh``, or untagged (no language) fenced blocks.
    Skips mermaid, yaml, python, json, etc. to prevent false positives.
    Skips template commands containing ``<placeholder>`` angle brackets.
    Follows backslash continuations for multi-line commands.
    Skips archive/legacy directories.
    """
    errors = []
    skip_dirs = {"archive", "legacy"}
    # Languages we consider "shell-like" (check commands in these blocks)
    shell_langs = {"bash", "sh", ""}
    fence_open_re = re.compile(r"^```(\w*)\s*$")
    # Match run_experiment.py only when used as a command (preceded by python
    # or at the start of a command line with PYTHONPATH=), not file tree listings
    run_exp_re = re.compile(r"python\s+\S*run_experiment\.py")
    seed_re = re.compile(r"--seed\b|--allow-nondeterministic\b")
    template_re = re.compile(r"<\w+")
    requirements_re = re.compile(r"pip install\s+-r\s+requirements\.txt")

    for md_file in sorted(docs_dir.rglob("*.md")):
        if any(part in skip_dirs for part in md_file.relative_to(docs_dir).parts):
            continue
        text = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(repo_root)
        lines = text.splitlines()

        # Parse fenced blocks with a simple state machine
        in_block = False
        block_lang = ""
        block_lines: list[tuple[int, str]] = []  # (lineno, text)

        for lineno_0, line in enumerate(lines):
            lineno = lineno_0 + 1
            stripped = line.strip()

            if not in_block:
                m = fence_open_re.match(stripped)
                if m:
                    in_block = True
                    block_lang = m.group(1)
                    block_lines = []
                continue

            # Inside a block — check for closing fence
            if stripped == "```":
                # Block closed — check if it was a shell-like block
                if block_lang in shell_langs:
                    _check_block_commands(
                        block_lines,
                        rel,
                        errors,
                        run_exp_re,
                        seed_re,
                        template_re,
                        requirements_re,
                    )
                in_block = False
                continue

            block_lines.append((lineno, line))

    return errors


def _check_block_commands(
    block_lines: list[tuple[int, str]],
    rel: Path,
    errors: list[str],
    run_exp_re: re.Pattern,
    seed_re: re.Pattern,
    template_re: re.Pattern,
    requirements_re: re.Pattern,
) -> None:
    """Check a single shell code block for command contract violations."""
    for idx, (lineno, line) in enumerate(block_lines):
        if run_exp_re.search(line):
            if template_re.search(line):
                continue
            # Collect continuation lines
            cmd_parts = [line]
            j = idx + 1
            while j < len(block_lines) and cmd_parts[-1].rstrip().endswith("\\"):
                cmd_parts.append(block_lines[j][1])
                j += 1
            full_cmd = " ".join(cmd_parts)
            if not seed_re.search(full_cmd):
                errors.append(
                    f"{rel}:{lineno}: run_experiment.py without "
                    f"--seed or --allow-nondeterministic"
                )

        if requirements_re.search(line):
            errors.append(
                f"{rel}:{lineno}: stale 'pip install -r requirements.txt' "
                f"(use 'uv sync' or 'pip install -e \".[dev]\"')"
            )


def check_active_governing_plans(claude_md: Path, repo_root: Path) -> list[str]:
    """Verify the Active Governing Plans table in CLAUDE.md.

    Checks:
    1. Every initiative path in the table points to a file that exists on disk.
    2. No duplicate initiative names (each initiative listed at most once).
    """
    errors = []
    if not claude_md.exists():
        return [f"CLAUDE.md not found at {claude_md}"]

    text = claude_md.read_text(encoding="utf-8")

    # Find the "Active Governing Plans" section and parse the table
    section_re = re.compile(r"^## Active Governing Plans\s*\n", re.MULTILINE)
    match = section_re.search(text)
    if not match:
        return ["CLAUDE.md: missing '## Active Governing Plans' section"]

    # Parse table rows after the header: | Initiative | Governing Plan | Status |
    # Skip the header row and separator row, then extract data rows
    table_re = re.compile(r"^\| ([^|]+)\| `([^`]+)` \| (\w+) \|$", re.MULTILINE)
    initiatives_seen: dict[str, int] = {}
    section_text = text[match.start() :]
    # Stop at the next H2 or end of file
    next_h2 = re.search(r"\n## ", section_text[1:])
    if next_h2:
        section_text = section_text[: next_h2.start() + 1]

    row_count = 0
    for row_match in table_re.finditer(section_text):
        initiative = row_match.group(1).strip()
        plan_path = row_match.group(2).strip()

        # Skip header/separator rows
        if initiative.startswith("-") or initiative == "Initiative":
            continue

        row_count += 1
        line_offset = (
            text[: match.start()].count("\n")
            + section_text[: row_match.start()].count("\n")
            + 1
        )

        # Check for duplicate initiative names
        if initiative in initiatives_seen:
            errors.append(
                f"CLAUDE.md:{line_offset}: duplicate initiative "
                f"'{initiative}' (first at line {initiatives_seen[initiative]})"
            )
        else:
            initiatives_seen[initiative] = line_offset

        # Check that the governing plan file exists
        if not (repo_root / plan_path).exists():
            errors.append(
                f"CLAUDE.md:{line_offset}: governing plan not found: `{plan_path}`"
            )

    if row_count == 0:
        errors.append("CLAUDE.md: Active Governing Plans table has no entries")

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

    print("Checking internal script list completeness...")
    internal_errors = check_internal_scripts_listed(arch_doc, scripts_dir / "internal")
    all_errors.extend(internal_errors)

    print("Checking for duplicate headings...")
    heading_errors = check_no_duplicate_headings(arch_doc)
    all_errors.extend(heading_errors)

    print("Checking command contracts in docs/...")
    contract_errors = check_command_contracts(docs_dir, repo_root)
    all_errors.extend(contract_errors)

    print("Checking active governing plans...")
    claude_md = repo_root / "CLAUDE.md"
    plan_errors = check_active_governing_plans(claude_md, repo_root)
    all_errors.extend(plan_errors)

    if all_errors:
        print(f"\nDocs freshness check FAILED ({len(all_errors)} issues):\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("Docs freshness check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
