#!/usr/bin/env python3
"""Audit analysis for the automated review pipeline.

Queries GitHub-native artifacts (merged PRs, commit statuses,
follow-up issues, labels) to report on review pipeline health.

Usage:
    uv run python scripts/internal/audit_analysis.py
    uv run python scripts/internal/audit_analysis.py --limit 50
    uv run python scripts/internal/audit_analysis.py --format json
    uv run python scripts/internal/audit_analysis.py --since 2026-03-01
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime

REPO = "Questuart/Bid-Euchre"
REVIEW_CONTEXT = "reviewing-changes"
FOLLOW_UP_LABEL = "follow-up"
FIX_LABEL_PREFIX = "fix:"


def gh_api(endpoint: str, paginate: bool = False) -> list | dict:
    """Call the GitHub API via gh CLI."""
    cmd = ["gh", "api", endpoint]
    if paginate:
        cmd.append("--paginate")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_merged_prs(limit: int, since: str | None = None) -> list[dict]:
    """Fetch merged PRs from the repo."""
    query = f"repo:{REPO} is:pr is:merged"
    if since:
        query += f" merged:>={since}"
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        REPO,
        "--state",
        "merged",
        "--limit",
        str(limit),
        "--json",
        "number,title,mergedAt,labels,url",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    prs = json.loads(result.stdout)
    if since:
        prs = [pr for pr in prs if pr.get("mergedAt", "") >= since]
    return prs


def get_review_status(pr: dict) -> str | None:
    """Get the reviewing-changes commit status for a PR's merge commit."""
    number = pr["number"]
    try:
        pr_detail = gh_api(f"/repos/{REPO}/pulls/{number}")
        merge_sha = pr_detail.get("merge_commit_sha")
        if not merge_sha:
            return None
        statuses = gh_api(f"/repos/{REPO}/commits/{merge_sha}/statuses")
        for status in statuses:
            if status.get("context") == REVIEW_CONTEXT:
                return status["state"]
    except (subprocess.CalledProcessError, KeyError):
        pass
    return None


def get_follow_up_issues() -> list[dict]:
    """Fetch all issues with the follow-up label."""
    cmd = [
        "gh",
        "issue",
        "list",
        "--repo",
        REPO,
        "--label",
        FOLLOW_UP_LABEL,
        "--state",
        "all",
        "--limit",
        "200",
        "--json",
        "number,title,labels,state,url",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_corrective_prs() -> list[dict]:
    """Find PRs with the follow-up label (corrective PRs)."""
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        REPO,
        "--state",
        "all",
        "--label",
        FOLLOW_UP_LABEL,
        "--limit",
        "200",
        "--json",
        "number,title,state,labels,url,body",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def extract_source_pr(title: str) -> int | None:
    """Extract the source PR number from a follow-up issue title.

    Expected format: 'fix(<category>): follow-up for PR #NNN'
    """
    import re

    match = re.search(r"PR #(\d+)", title)
    return int(match.group(1)) if match else None


def extract_referenced_issues(text: str) -> set[int]:
    """Extract issue/PR numbers referenced in text.

    Looks for patterns like 'Fixes #NNN', 'Closes #NNN', 'Resolves #NNN',
    or plain '#NNN' references.
    """
    import re

    return {int(m) for m in re.findall(r"#(\d+)", text)}


def build_audit_trail(
    merged_prs: list[dict],
    follow_up_issues: list[dict],
    corrective_prs: list[dict],
) -> dict[int, dict]:
    """Build per-PR audit trail linking PRs to follow-ups and correctives."""
    trail: dict[int, dict] = {}

    for pr in merged_prs:
        trail[pr["number"]] = {
            "title": pr["title"],
            "merged_at": pr.get("mergedAt", ""),
            "url": pr["url"],
            "follow_up_issues": [],
            "corrective_prs": [],
        }

    # Link follow-up issues to source PRs
    for issue in follow_up_issues:
        source = extract_source_pr(issue["title"])
        if source and source in trail:
            trail[source]["follow_up_issues"].append(
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "labels": [l["name"] for l in issue.get("labels", [])],
                    "url": issue["url"],
                }
            )

    # Build follow-up issue number → source PR mapping
    followup_to_source: dict[int, int] = {}
    for issue in follow_up_issues:
        source = extract_source_pr(issue["title"])
        if source:
            followup_to_source[issue["number"]] = source

    # Link corrective PRs to source PRs via:
    # 1. Title regex (PR #NNN in corrective PR title)
    # 2. Body references to follow-up issues (#NNN → source PR)
    for pr in corrective_prs:
        source = extract_source_pr(pr["title"])
        if not source:
            # Check if the PR body references any follow-up issues
            refs = extract_referenced_issues(pr.get("body", ""))
            for ref in refs:
                if ref in followup_to_source:
                    source = followup_to_source[ref]
                    break
        if source and source in trail:
            trail[source]["corrective_prs"].append(
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "url": pr["url"],
                }
            )

    return trail


def compute_stats(
    merged_prs: list[dict],
    audit_trail: dict[int, dict],
) -> dict:
    """Compute summary statistics scoped to the analyzed PR set.

    All counts are derived from the audit trail (which only links
    issues/PRs to the analyzed merged PRs), not from repo-wide totals.
    """
    total = len(merged_prs)
    prs_with_followups = sum(1 for t in audit_trail.values() if t["follow_up_issues"])
    prs_with_correctives = sum(1 for t in audit_trail.values() if t["corrective_prs"])

    # Collect only issues/PRs linked to the analyzed set
    linked_issues = [
        issue for t in audit_trail.values() for issue in t["follow_up_issues"]
    ]
    linked_correctives = [
        pr for t in audit_trail.values() for pr in t["corrective_prs"]
    ]

    # Category breakdown from linked follow-up issue labels
    categories: Counter[str] = Counter()
    for issue in linked_issues:
        for label_name in issue.get("labels", []):
            if isinstance(label_name, str) and label_name.startswith(FIX_LABEL_PREFIX):
                categories[label_name] += 1

    # Follow-up issue states (scoped)
    issue_states: Counter[str] = Counter()
    for issue in linked_issues:
        issue_states[issue["state"]] += 1

    return {
        "merged_pr_count": total,
        "follow_up_issue_count": len(linked_issues),
        "corrective_pr_count": len(linked_correctives),
        "prs_with_followups": prs_with_followups,
        "prs_with_correctives": prs_with_correctives,
        "follow_up_rate": prs_with_followups / total if total else 0,
        "corrective_rate": prs_with_correctives / total if total else 0,
        "categories": dict(categories.most_common()),
        "issue_states": dict(issue_states),
    }


def format_markdown(stats: dict, audit_trail: dict[int, dict]) -> str:
    """Format the report as markdown."""
    lines = []
    lines.append("# Review Pipeline Audit Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    lines.append("\n## Summary")
    lines.append(f"- Merged PRs analyzed: **{stats['merged_pr_count']}**")
    lines.append(f"- Follow-up issues: **{stats['follow_up_issue_count']}**")
    lines.append(f"- Corrective PRs: **{stats['corrective_pr_count']}**")
    lines.append(
        f"- Follow-up rate: **{stats['follow_up_rate']:.0%}** "
        f"({stats['prs_with_followups']}/{stats['merged_pr_count']} PRs)"
    )
    lines.append(
        f"- Corrective rate: **{stats['corrective_rate']:.0%}** "
        f"({stats['prs_with_correctives']}/{stats['merged_pr_count']} PRs)"
    )

    if stats["categories"]:
        lines.append("\n## Follow-up Categories")
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        for cat, count in stats["categories"].items():
            lines.append(f"| `{cat}` | {count} |")

    if stats["issue_states"]:
        lines.append("\n## Follow-up Issue Status")
        lines.append("| State | Count |")
        lines.append("|-------|-------|")
        for state, count in stats["issue_states"].items():
            lines.append(f"| {state} | {count} |")

    # Per-PR audit trail (only PRs with follow-ups)
    prs_with_trail = {
        k: v
        for k, v in audit_trail.items()
        if v["follow_up_issues"] or v["corrective_prs"]
    }
    if prs_with_trail:
        lines.append("\n## Per-PR Audit Trail")
        for pr_num in sorted(prs_with_trail.keys(), reverse=True):
            entry = prs_with_trail[pr_num]
            lines.append(f"\n### PR #{pr_num} — {entry['title']}")
            if entry["follow_up_issues"]:
                lines.append("**Follow-up issues:**")
                for issue in entry["follow_up_issues"]:
                    labels = ", ".join(f"`{l}`" for l in issue["labels"])
                    lines.append(
                        f"- #{issue['number']} ({issue['state']}) "
                        f"{issue['title']} [{labels}]"
                    )
            if entry["corrective_prs"]:
                lines.append("**Corrective PRs:**")
                for pr in entry["corrective_prs"]:
                    lines.append(f"- #{pr['number']} ({pr['state']}) {pr['title']}")
    else:
        lines.append("\n## Per-PR Audit Trail")
        lines.append("No PRs with follow-up issues or corrective PRs found.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit analysis for the automated review pipeline"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Number of merged PRs to analyze (default: 30)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only include PRs merged on or after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    # Gather data
    merged_prs = get_merged_prs(args.limit, args.since)
    follow_up_issues = get_follow_up_issues()
    corrective_prs = get_corrective_prs()
    audit_trail = build_audit_trail(merged_prs, follow_up_issues, corrective_prs)
    stats = compute_stats(merged_prs, audit_trail)

    if args.format == "json":
        output = {
            "stats": stats,
            "audit_trail": {
                str(k): v
                for k, v in audit_trail.items()
                if v["follow_up_issues"] or v["corrective_prs"]
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_markdown(stats, audit_trail))


if __name__ == "__main__":
    main()
