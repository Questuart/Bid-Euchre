#!/usr/bin/env python
"""Verify no files are dropped during stacked-PR squash merges.

When squash-merging a stacked PR, Git collapses all intermediate commits into
a single commit. Files added by intermediate PRs that are not in the final
squash diff are silently dropped. This tool detects those dropped files.

Usage — pre-merge check (before squash-merging the bottom PR):

    uv run python scripts/internal/verify_squash_merge.py \\
        --bottom-pr 1898 --stack-prs 1896 1897

Usage — post-merge audit (compare merge commit against stack):

    uv run python scripts/internal/verify_squash_merge.py \\
        --merge-sha abc123 --stack-prs 1896 1897

Exit codes:
    0 — all files accounted for (or no discrepancies)
    1 — dropped files detected
    2 — usage error or gh CLI failure

See issue #1908 for background.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def get_pr_files(pr_number: int) -> set[str]:
    """Get set of files changed in a PR via ``gh pr diff --name-only``.

    Raises:
        RuntimeError: If the ``gh`` CLI call fails.
    """
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number), "--name-only"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to get PR #{pr_number} changed files: {result.stderr.strip()}"
        )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def get_merge_commit_files(sha: str) -> set[str]:
    """Get set of files in a merge commit via ``git diff-tree``.

    Raises:
        RuntimeError: If the ``git`` command fails.
    """
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", sha],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to get files for commit {sha}: {result.stderr.strip()}"
        )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def get_pr_file_statuses(pr_number: int) -> dict[str, str]:
    """Get file paths with their change status (added/modified/removed/renamed).

    Uses ``gh pr diff`` raw output to parse file statuses from diff headers.

    Raises:
        RuntimeError: If the ``gh`` CLI call fails.
    """
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "files"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to get PR #{pr_number} file statuses: {result.stderr.strip()}"
        )
    data = json.loads(result.stdout)
    files = data.get("files", [])
    # gh returns [{path, additions, deletions}] — no explicit status field.
    # Fall back to name-only for the path set; status isn't critical for
    # the drop detection algorithm.
    return {f["path"]: "changed" for f in files}


def verify_stack(
    bottom_files: set[str],
    stack_files_by_pr: dict[int, set[str]],
) -> list[dict[str, object]]:
    """Compare bottom PR files against the union of stack PR files.

    Returns a list of dropped-file records, each with:
        - ``file``: the file path
        - ``source_prs``: list of PR numbers that introduced the file

    Files present in stack PRs but absent from the bottom PR are "dropped".
    """
    union_stack = set()
    file_sources: dict[str, list[int]] = {}
    for pr_num, files in stack_files_by_pr.items():
        union_stack |= files
        for f in files:
            file_sources.setdefault(f, []).append(pr_num)

    dropped = sorted(union_stack - bottom_files)
    return [{"file": f, "source_prs": sorted(file_sources.get(f, []))} for f in dropped]


def format_report(
    dropped: list[dict[str, object]],
    bottom_label: str,
    stack_prs: list[int],
    bottom_count: int,
    stack_union_count: int,
) -> str:
    """Format a human-readable report of verification results."""
    lines: list[str] = []

    lines.append(f"Squash merge verification for {bottom_label}")
    lines.append(f"  Stack PRs: {', '.join(f'#{p}' for p in stack_prs)}")
    lines.append(f"  Bottom PR files: {bottom_count}")
    lines.append(f"  Stack union files: {stack_union_count}")
    lines.append("")

    if not dropped:
        lines.append("✅ All stack files accounted for — no dropped files.")
    else:
        lines.append(f"❌ {len(dropped)} file(s) potentially dropped:")
        lines.append("")
        for entry in dropped:
            sources = ", ".join(f"#{p}" for p in entry["source_prs"])  # type: ignore[union-attr]
            lines.append(f"  - {entry['file']}  (from {sources})")
        lines.append("")
        lines.append(
            "These files were changed in stack PRs but are NOT in the bottom PR's diff."
        )
        lines.append("If squash-merged, these changes will be silently dropped.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the verification tool."""
    parser = argparse.ArgumentParser(
        description="Verify stacked-PR squash merges don't drop files.",
        epilog="See issue #1908 for background.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--bottom-pr",
        type=int,
        help="PR number of the bottom of the stack (the one being merged into main).",
    )
    group.add_argument(
        "--merge-sha",
        type=str,
        help="SHA of an already-merged squash commit (for post-hoc audit).",
    )
    parser.add_argument(
        "--stack-prs",
        type=int,
        nargs="+",
        required=True,
        help="PR numbers of the intermediate/upper stack PRs.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON instead of human-readable text.",
    )

    args = parser.parse_args(argv)

    # Collect bottom files
    bottom_label: str
    try:
        if args.bottom_pr:
            bottom_files = get_pr_files(args.bottom_pr)
            bottom_label = f"PR #{args.bottom_pr}"
        else:
            bottom_files = get_merge_commit_files(args.merge_sha)
            bottom_label = f"commit {args.merge_sha[:12]}"
    except RuntimeError as exc:
        print(f"Error getting bottom files: {exc}", file=sys.stderr)
        return 2

    # Collect stack files
    stack_files_by_pr: dict[int, set[str]] = {}
    for pr_num in args.stack_prs:
        try:
            stack_files_by_pr[pr_num] = get_pr_files(pr_num)
        except RuntimeError as exc:
            print(f"Error getting PR #{pr_num} files: {exc}", file=sys.stderr)
            return 2

    # Verify
    dropped = verify_stack(bottom_files, stack_files_by_pr)

    # Output
    if args.json_output:
        result = {
            "bottom": args.bottom_pr or args.merge_sha,
            "stack_prs": args.stack_prs,
            "bottom_file_count": len(bottom_files),
            "stack_union_file_count": len(set().union(*stack_files_by_pr.values())),
            "dropped_count": len(dropped),
            "dropped": dropped,
            "ok": len(dropped) == 0,
        }
        print(json.dumps(result, indent=2))
    else:
        stack_union = set().union(*stack_files_by_pr.values())
        report = format_report(
            dropped,
            bottom_label,
            args.stack_prs,
            len(bottom_files),
            len(stack_union),
        )
        print(report)

    return 0 if not dropped else 1


if __name__ == "__main__":
    sys.exit(main())
