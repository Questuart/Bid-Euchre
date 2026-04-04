"""Issue closure verification tooling.

Enforces the tiered issue closure policy from
docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md § Tiered Issue Closure.

Three subcommands:

  list-pending    List open issues with ``needs-verification`` label.
  check-pr        Validate Fixes/Refs usage in a PR body against issue metadata.
  prove           Post verification evidence to an issue and close it.

Usage::

    uv run python scripts/internal/verify_issue_closure.py list-pending
    uv run python scripts/internal/verify_issue_closure.py check-pr 2350
    uv run python scripts/internal/verify_issue_closure.py prove 2306 \\
        --evidence "Verified in fleet run: <command> → <output>"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tier classification heuristics
# ---------------------------------------------------------------------------

# Signals that an issue is complex (Tier 2 — requires verified-close)
_TIER2_SIGNALS: list[tuple[str, str]] = [
    ("acceptance criteria", "Issue has explicit acceptance criteria section"),
    ("done when", "Issue defines 'done when' conditions"),
    ("verification", "Issue mentions verification requirements"),
    ("fleet", "Issue requires fleet/production verification"),
    ("production", "Issue requires production verification"),
    ("multiple prs", "Issue spans multiple PRs"),
    ("incremental", "Issue is being resolved incrementally"),
]

# Labels that indicate Tier 2
_TIER2_LABELS: set[str] = {
    "needs-verification",
    "needs-human",
    "infra-incident",
}


@dataclass
class IssueInfo:
    """Subset of GitHub issue metadata relevant to closure validation."""

    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    was_reopened: bool = False


@dataclass
class LinkageCheck:
    """Result of validating a single issue linkage in a PR."""

    issue_number: int
    keyword: str  # "Fixes" or "Refs"
    tier: int  # 1 or 2
    signals: list[str]  # reasons for tier classification
    ok: bool  # True if keyword matches tier
    message: str


# ---------------------------------------------------------------------------
# GitHub helpers (via gh CLI)
# ---------------------------------------------------------------------------


def _run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def _get_issue(number: int) -> IssueInfo:
    """Fetch issue metadata via gh CLI."""
    raw = _run_gh(
        [
            "issue",
            "view",
            str(number),
            "--json",
            "number,title,body,state,labels",
        ]
    )
    data = json.loads(raw)
    labels = [
        lbl["name"] if isinstance(lbl, dict) else lbl for lbl in data.get("labels", [])
    ]

    # Check timeline for reopen events
    was_reopened = False
    try:
        timeline_raw = _run_gh(
            [
                "api",
                f"repos/:owner/:repo/issues/{number}/timeline",
                "--jq",
                '[.[] | select(.event == "reopened")] | length',
            ]
        )
        was_reopened = timeline_raw.strip() not in ("", "0")
    except Exception:
        pass  # Timeline API may not be available; default to False

    return IssueInfo(
        number=data["number"],
        title=data.get("title", ""),
        body=data.get("body", "") or "",
        state=data.get("state", "UNKNOWN"),
        labels=labels,
        was_reopened=was_reopened,
    )


def _get_pr_body(pr_number: int) -> str:
    """Fetch PR body via gh CLI."""
    raw = _run_gh(["pr", "view", str(pr_number), "--json", "body"])
    data = json.loads(raw)
    return data.get("body", "") or ""


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


def classify_issue_tier(issue: IssueInfo) -> tuple[int, list[str]]:
    """Classify an issue as Tier 1 (auto-close OK) or Tier 2 (verified-close).

    Returns (tier, list_of_signals).
    """
    signals: list[str] = []
    body_lower = issue.body.lower()

    # Check for Tier 2 labels
    for label in issue.labels:
        if label in _TIER2_LABELS:
            signals.append(f"Label '{label}' indicates Tier 2")

    # Check for Tier 2 text signals
    for pattern, reason in _TIER2_SIGNALS:
        if pattern in body_lower:
            signals.append(reason)

    # Was previously reopened — strong Tier 2 signal
    if issue.was_reopened:
        signals.append("Issue was previously closed and reopened")

    # Body length heuristic: long issues usually have complex acceptance criteria
    if len(issue.body) > 1500:
        signals.append("Issue body is substantial (>1500 chars) — likely complex")

    tier = 2 if signals else 1
    return tier, signals


# ---------------------------------------------------------------------------
# PR linkage extraction
# ---------------------------------------------------------------------------

# Matches "Fixes #123", "Refs #123", "Closes #123" (case-insensitive)
_LINKAGE_RE = re.compile(
    r"\b(Fix(?:es)?|Close[sd]?|Resolve[sd]?|Refs?)\s+#(\d+)\b",
    re.IGNORECASE,
)

# Keywords that trigger auto-close on merge
_AUTO_CLOSE_KEYWORDS: set[str] = {
    "fix",
    "fixes",
    "close",
    "closes",
    "closed",
    "resolve",
    "resolves",
    "resolved",
}


def extract_linkages(pr_body: str) -> list[tuple[str, int]]:
    """Extract (keyword, issue_number) pairs from PR body."""
    results = []
    for match in _LINKAGE_RE.finditer(pr_body):
        keyword = match.group(1)
        number = int(match.group(2))
        results.append((keyword, number))
    return results


def is_auto_close_keyword(keyword: str) -> bool:
    """Return True if the keyword triggers auto-close on merge."""
    return keyword.lower() in _AUTO_CLOSE_KEYWORDS


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_list_pending(_args: argparse.Namespace) -> int:
    """List issues with needs-verification label."""
    raw = _run_gh(
        [
            "issue",
            "list",
            "--label",
            "needs-verification",
            "--state",
            "open",
            "--json",
            "number,title,labels",
            "--limit",
            "50",
        ]
    )
    issues = json.loads(raw)
    if not issues:
        print("No open issues with 'needs-verification' label.")
        return 0

    print(f"Found {len(issues)} issue(s) needing verification:\n")
    for issue in issues:
        labels_str = ", ".join(
            lbl["name"] if isinstance(lbl, dict) else lbl
            for lbl in issue.get("labels", [])
        )
        print(f"  #{issue['number']:>5}  {issue['title']}")
        print(f"         Labels: {labels_str}")
    return 0


def cmd_check_pr(args: argparse.Namespace) -> int:
    """Validate issue linkage in a PR body."""
    pr_number = args.pr_number
    pr_body = _get_pr_body(pr_number)
    linkages = extract_linkages(pr_body)

    if not linkages:
        print(f"PR #{pr_number}: No issue linkages found in PR body.")
        print("  Tip: Use 'Refs #N' or 'Fixes #N' in the Issue Linkage section.")
        return 0

    checks: list[LinkageCheck] = []
    has_problems = False

    for keyword, issue_number in linkages:
        auto_close = is_auto_close_keyword(keyword)

        try:
            issue = _get_issue(issue_number)
        except SystemExit:
            print(f"  Warning: Could not fetch issue #{issue_number}", file=sys.stderr)
            continue

        tier, signals = classify_issue_tier(issue)

        if auto_close and tier == 2:
            ok = False
            has_problems = True
            message = (
                f"'{keyword} #{issue_number}' will auto-close, but issue appears Tier 2. "
                f"Consider using 'Refs #{issue_number}' instead."
            )
        elif not auto_close and tier == 1:
            ok = True
            message = (
                f"'Refs #{issue_number}' is safe (Tier 1 issue). "
                f"'Fixes #{issue_number}' would also be acceptable."
            )
        elif auto_close and tier == 1:
            ok = True
            message = f"'{keyword} #{issue_number}' is appropriate for Tier 1 issue."
        else:
            # Refs + Tier 2 = correct
            ok = True
            message = f"'Refs #{issue_number}' is correct for Tier 2 issue."

        checks.append(
            LinkageCheck(
                issue_number=issue_number,
                keyword=keyword,
                tier=tier,
                signals=signals,
                ok=ok,
                message=message,
            )
        )

    # Print results
    print(f"PR #{pr_number} — Issue Linkage Check\n")
    for check in checks:
        status = "OK" if check.ok else "WARN"
        print(f"  [{status}] {check.message}")
        if check.signals:
            for signal in check.signals:
                print(f"         - {signal}")
        print()

    if has_problems:
        print(
            "Recommendation: Switch auto-close keywords to 'Refs #N' for "
            "Tier 2 issues, then verify and close manually after merge."
        )
        return 1

    print("All linkages look correct.")
    return 0


def cmd_prove(args: argparse.Namespace) -> int:
    """Post verification evidence and close an issue."""
    issue_number = args.issue_number
    evidence = args.evidence

    # Fetch issue to verify state
    issue = _get_issue(issue_number)

    if issue.state != "OPEN":
        print(f"Issue #{issue_number} is already {issue.state}. Nothing to do.")
        return 0

    # Build the verification comment
    comment_body = (
        "## Verification Evidence\n\n"
        f"{evidence}\n\n"
        "---\n"
        "*Closed via verified-close workflow "
        "(`scripts/internal/verify_issue_closure.py prove`).*"
    )

    if args.dry_run:
        print(f"DRY RUN — would post to #{issue_number}:\n")
        print(comment_body)
        print("\n(Would then close the issue)")
        return 0

    # Post the comment
    _run_gh(
        [
            "issue",
            "comment",
            str(issue_number),
            "--body",
            comment_body,
        ]
    )
    print(f"Posted verification evidence to #{issue_number}.")

    # Close the issue
    _run_gh(
        [
            "issue",
            "close",
            str(issue_number),
            "--reason",
            "completed",
        ]
    )
    print(f"Closed #{issue_number} with verification evidence.")

    # Remove needs-verification label if present
    if "needs-verification" in issue.labels:
        try:
            _run_gh(
                [
                    "issue",
                    "edit",
                    str(issue_number),
                    "--remove-label",
                    "needs-verification",
                ]
            )
            print("Removed 'needs-verification' label.")
        except Exception:
            pass  # Non-critical

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Issue closure verification tooling.",
        epilog=(
            "See docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md § Tiered Issue Closure "
            "and .claude/rules/deferred/55_issue_closure.md for policy details."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-pending
    subparsers.add_parser(
        "list-pending",
        help="List open issues with needs-verification label.",
    )

    # check-pr
    p_check = subparsers.add_parser(
        "check-pr",
        help="Validate Fixes/Refs usage in a PR body against issue metadata.",
    )
    p_check.add_argument("pr_number", type=int, help="PR number to validate.")

    # prove
    p_prove = subparsers.add_parser(
        "prove",
        help="Post verification evidence and close an issue.",
    )
    p_prove.add_argument("issue_number", type=int, help="Issue number to close.")
    p_prove.add_argument(
        "--evidence",
        required=True,
        help="Verification evidence text (proving command + output).",
    )
    p_prove.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be posted without actually posting.",
    )

    args = parser.parse_args()

    if args.command == "list-pending":
        return cmd_list_pending(args)
    elif args.command == "check-pr":
        return cmd_check_pr(args)
    elif args.command == "prove":
        return cmd_prove(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
