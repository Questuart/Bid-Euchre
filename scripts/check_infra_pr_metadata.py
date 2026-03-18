#!/usr/bin/env python3
"""Check whether PRs touching infra paths include infra-incident metadata.

Usage (CI):
  python scripts/check_infra_pr_metadata.py --pr-body "$PR_BODY" --changed-files file1 file2 ...

Usage (local, reads git diff):
  python scripts/check_infra_pr_metadata.py --pr-body "$PR_BODY" --base origin/main --head HEAD

Exit codes:
  0 — check passed or not applicable
  1 — advisory warning (missing metadata for infra-touching PR)

Phase 3a: advisory output only (GitHub Actions warning annotations).
Phase 3b: will hard-fail for PRs explicitly marked as infra-incident work.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# Infrastructure path prefixes — kept in sync with scripts/lint_repo.py
INFRA_PATH_PREFIXES = (
    ".github/workflows/",
    ".claude/hooks/",
    "scripts/internal/",
)

INFRA_EXACT_FILES = frozenset({"Makefile"})

# Extensions that are documentation-only under infra paths
INFRA_DOC_EXTENSIONS = frozenset({".md", ".txt", ".rst"})

# Section header pattern in PR body
INFRA_INCIDENT_HEADER = re.compile(
    r"^##\s+Infra\s+Incident", re.MULTILINE | re.IGNORECASE
)

# Minimal field patterns inside the section.
# Use [^\S\n]* (horizontal whitespace only) to prevent matching across lines.
INFRA_FIELD_PATTERNS = {
    "Issue": re.compile(r"^\s*-\s*Issue:[^\S\n]*\S", re.MULTILINE),
    "Regression test": re.compile(r"^\s*-\s*Regression test:[^\S\n]*\S", re.MULTILINE),
}


def is_infra_path(path: str) -> bool:
    """Return True if *path* is an infrastructure file (non-doc)."""
    if path in INFRA_EXACT_FILES:
        return True
    for prefix in INFRA_PATH_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            # Exempt documentation-only files
            ext = path[path.rfind(".") :].lower() if "." in path else ""
            if ext in INFRA_DOC_EXTENSIONS:
                return False
            return True
    return False


def get_changed_files_from_git(base: str, head: str) -> list[str]:
    """Return changed files between base..head, excluding deletions."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=d", f"{base}..{head}"],
        text=True,
    ).strip()
    if not out:
        return []
    return out.splitlines()


def has_infra_incident_section(pr_body: str) -> bool:
    """Return True if the PR body contains an ## Infra Incident header."""
    return bool(INFRA_INCIDENT_HEADER.search(pr_body))


def check_infra_fields(pr_body: str) -> list[str]:
    """Return list of missing field names in the Infra Incident section."""
    missing = []
    for name, pattern in INFRA_FIELD_PATTERNS.items():
        if not pattern.search(pr_body):
            missing.append(name)
    return missing


def check(pr_body: str, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Run the infra PR metadata check.

    Returns (has_infra_changes, warnings).
    """
    infra_files = [f for f in changed_files if is_infra_path(f)]

    if not infra_files:
        return False, []

    warnings: list[str] = []

    if not has_infra_incident_section(pr_body):
        warnings.append(
            f"PR touches {len(infra_files)} infra file(s) but has no "
            f"'## Infra Incident' section. Consider filling it if this "
            f"fixes an infra breakage."
        )
    else:
        missing = check_infra_fields(pr_body)
        if missing:
            warnings.append(
                f"'## Infra Incident' section is present but missing: "
                f"{', '.join(missing)}"
            )

    return True, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pr-body",
        required=True,
        help="Full text of the PR description body",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--changed-files",
        nargs="*",
        default=None,
        help="Explicit list of changed file paths",
    )
    group.add_argument(
        "--base",
        default=None,
        help="Git base ref (e.g., origin/main). Used with --head.",
    )
    ap.add_argument(
        "--head",
        default="HEAD",
        help="Git head ref (default: HEAD). Used with --base.",
    )

    args = ap.parse_args()

    if args.changed_files is not None:
        changed = args.changed_files
    elif args.base is not None:
        changed = get_changed_files_from_git(args.base, args.head)
    else:
        ap.error("Provide either --changed-files or --base")
        return 1  # unreachable

    has_infra, warnings = check(args.pr_body, changed)

    if not has_infra:
        print("No infra files changed — skipping metadata check.")
        return 0

    if warnings:
        for w in warnings:
            # GitHub Actions annotation format
            print(f"::warning::{w}")
        # Phase 3a: advisory only — return 0
        return 0

    print("Infra metadata check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
