#!/usr/bin/env python3
"""Portability audit script for the ops package.

Scans ``src/bid_euchre/ops/`` for project-specific coupling patterns and
produces a structured report.  Used to track portability progress over time
as the ops package is decoupled from Bid-Euchre-specific assumptions.

Usage::

    uv run python scripts/internal/audit_portability.py          # human-readable
    uv run python scripts/internal/audit_portability.py --json    # machine-readable
    uv run python scripts/internal/audit_portability.py --threshold 300  # fail if above

Exit codes:
    0 — audit complete (and under threshold, if specified)
    1 — coupling count exceeds threshold
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Coupling pattern definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CouplingPattern:
    """A grep-style pattern that detects project-specific coupling."""

    name: str
    regex: str
    severity: str  # hard-block | soft-coupling | cosmetic
    description: str
    #: If True, matches in comments/docstrings are cosmetic (downgraded).
    downgrade_in_comments: bool = True
    #: If True, matches inside ``adapters/`` are excluded (they are expected).
    exclude_adapter: bool = False
    #: If True, Python import lines are excluded (package name is structural).
    exclude_imports: bool = False


#: Ordered list of coupling patterns to scan for.
PATTERNS: list[CouplingPattern] = [
    # -- Hard-block: string literals that embed the project name -----------
    CouplingPattern(
        name="worktree-name-literal",
        regex=r"""["']Bid-Euchre-steward-[^"']*["']""",
        severity="hard-block",
        description=(
            "Hard-coded worktree directory names (e.g., "
            '"Bid-Euchre-steward-author").  Must be read from adapter config.'
        ),
    ),
    CouplingPattern(
        name="project-name-literal",
        regex=r"""["']Bid-Euchre["']""",
        severity="hard-block",
        description=(
            "Hard-coded project name string.  Should come from adapter config "
            "or environment."
        ),
    ),
    CouplingPattern(
        name="repo-slug-literal",
        regex=r"Questuart/Bid-Euchre",
        severity="hard-block",
        description="Hard-coded GitHub repo slug.",
    ),
    CouplingPattern(
        name="steward-prefix-regex",
        regex=r"Bid-Euchre-steward-",
        severity="hard-block",
        description=(
            "Regex or string operations that assume the "
            '"Bid-Euchre-steward-" prefix for worktree directories.'
        ),
        downgrade_in_comments=True,
    ),
    # -- Soft-coupling: patterns that assume project conventions -----------
    CouplingPattern(
        name="tmux-session-default",
        regex=r'["\']steward["\']',
        severity="soft-coupling",
        description=(
            'Default tmux session name "steward".  Should be configurable '
            "via adapter config."
        ),
    ),
    CouplingPattern(
        name="branch-prefix-codex-steward",
        regex=r"codex/steward-",
        severity="soft-coupling",
        description=(
            "Branch prefix assumption (codex/steward-).  Cosmetic in "
            "display helpers, but blocks reuse if hard-coded in logic."
        ),
    ),
    CouplingPattern(
        name="review-context-name",
        regex=r"reviewing-changes",
        severity="soft-coupling",
        description=(
            "GitHub status context name.  Should be configurable or "
            "read from adapter config."
        ),
    ),
    CouplingPattern(
        name="recovery-template-paths",
        regex=r"Bid-Euchre-steward-review",
        severity="soft-coupling",
        description=(
            "Hard-coded worktree paths in recovery templates.  "
            "Should be derived from adapter config."
        ),
    ),
    CouplingPattern(
        name="lane-name-in-code",
        regex=r'"(author-[a-d]|brws-author-[a-d]|analyst-[a-d]|flex-[a-d]|review|ops)"',
        severity="soft-coupling",
        description=(
            "Specific lane identifiers outside of the adapter config module.  "
            "The adapter layer should be the sole source of these."
        ),
        exclude_adapter=True,
    ),
    # -- Cosmetic: references that are informational / non-blocking --------
    CouplingPattern(
        name="docstring-bid-euchre",
        regex=r"[Bb]id.[Ee]uchre",
        severity="cosmetic",
        description=(
            "References to 'Bid Euchre' in docstrings and comments.  "
            "Informational — no runtime impact."
        ),
        downgrade_in_comments=False,  # Already cosmetic
        exclude_imports=True,
    ),
    CouplingPattern(
        name="runtime-dir-claude",
        regex=r"\.claude/runtime",
        severity="cosmetic",
        description=(
            "Claude Code runtime directory convention.  This is a platform "
            "convention (Claude Code), not project-specific."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    """A single coupling occurrence."""

    file: str
    line_number: int
    line_text: str
    pattern_name: str
    severity: str
    in_comment: bool = False


@dataclass
class AuditReport:
    """Aggregate audit results."""

    hits: list[Hit] = field(default_factory=list)
    files_scanned: int = 0
    lines_scanned: int = 0

    @property
    def total(self) -> int:
        return len(self.hits)

    def by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {"hard-block": 0, "soft-coupling": 0, "cosmetic": 0}
        for h in self.hits:
            counts[h.severity] = counts.get(h.severity, 0) + 1
        return counts

    def by_file(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for h in self.hits:
            counts[h.file] = counts.get(h.file, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def by_pattern(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for h in self.hits:
            counts[h.pattern_name] = counts.get(h.pattern_name, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _is_comment_line(line: str) -> bool:
    """Heuristic: line is a Python comment or docstring continuation."""
    stripped = line.lstrip()
    return (
        stripped.startswith("#")
        or stripped.startswith('"""')
        or stripped.startswith("'''")
    )


def _is_in_docstring_context(lines: list[str], idx: int) -> bool:
    """Rough heuristic to detect if a line is inside a docstring."""
    # Count triple-quote occurrences before this line
    count = 0
    for i in range(idx):
        count += lines[i].count('"""') + lines[i].count("'''")
    # Odd count means we're inside a docstring
    return count % 2 == 1


def _is_adapter_file(filepath: Path) -> bool:
    """Check if a file is inside the adapters/ package."""
    return "adapters" in filepath.parts


def scan_file(
    filepath: Path,
    patterns: list[CouplingPattern],
    *,
    rel_to: Path | None = None,
) -> list[Hit]:
    """Scan a single file for coupling patterns."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    lines = text.splitlines()
    hits: list[Hit] = []

    if rel_to is not None:
        try:
            rel_path = str(filepath.relative_to(rel_to))
        except ValueError:
            rel_path = str(filepath)
    else:
        rel_path = str(filepath)

    is_adapter = _is_adapter_file(filepath)

    for pattern in patterns:
        # Skip patterns that should not match in adapter files
        if pattern.exclude_adapter and is_adapter:
            continue

        compiled = re.compile(pattern.regex)
        for i, line in enumerate(lines, start=1):
            if compiled.search(line):
                # Skip Python import lines when requested
                if pattern.exclude_imports:
                    stripped = line.lstrip()
                    if stripped.startswith(("from ", "import ")):
                        continue
                in_comment = _is_comment_line(line) or _is_in_docstring_context(
                    lines, i - 1
                )
                severity = pattern.severity
                if (
                    in_comment
                    and pattern.downgrade_in_comments
                    and severity != "cosmetic"
                ):
                    severity = "cosmetic"

                hits.append(
                    Hit(
                        file=rel_path,
                        line_number=i,
                        line_text=line.rstrip(),
                        pattern_name=pattern.name,
                        severity=severity,
                        in_comment=in_comment,
                    )
                )

    return hits


def run_audit(ops_dir: Path) -> AuditReport:
    """Run the full portability audit on the ops package."""
    report = AuditReport()

    py_files = sorted(ops_dir.rglob("*.py"))
    # Exclude __pycache__
    py_files = [f for f in py_files if "__pycache__" not in str(f)]

    report.files_scanned = len(py_files)

    # Resolve relative path base: parent of ops/ (i.e., src/bid_euchre/)
    rel_base = ops_dir.parent

    for filepath in py_files:
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
            report.lines_scanned += len(lines)
        except (OSError, UnicodeDecodeError):
            continue

        file_hits = scan_file(filepath, PATTERNS, rel_to=rel_base)
        report.hits.extend(file_hits)

    return report


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_human(report: AuditReport) -> str:
    """Format report for human reading."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  Ops Portability Audit Report")
    lines.append("=" * 70)
    lines.append("")
    sev = report.by_severity()
    non_cosmetic = sev.get("hard-block", 0) + sev.get("soft-coupling", 0)
    lines.append(f"Files scanned:  {report.files_scanned}")
    lines.append(f"Lines scanned:  {report.lines_scanned}")
    lines.append(f"Total coupling: {report.total}")
    lines.append(f"  Non-cosmetic: {non_cosmetic}  (hard-block + soft-coupling)")
    lines.append("")

    # By severity (reuse sev computed above)
    lines.append("By Severity:")
    for s in ("hard-block", "soft-coupling", "cosmetic"):
        count = sev.get(s, 0)
        marker = "🔴" if s == "hard-block" else ("🟡" if s == "soft-coupling" else "⚪")
        lines.append(f"  {marker} {s:20s} {count:4d}")
    lines.append("")

    # By pattern
    lines.append("By Pattern:")
    for name, count in report.by_pattern().items():
        lines.append(f"  {name:40s} {count:4d}")
    lines.append("")

    # By file (top 15)
    lines.append("By File (top 15):")
    for filepath, count in list(report.by_file().items())[:15]:
        lines.append(f"  {filepath:50s} {count:4d}")
    lines.append("")

    # Non-cosmetic hits detail
    non_cosmetic = [h for h in report.hits if h.severity != "cosmetic"]
    if non_cosmetic:
        lines.append("-" * 70)
        lines.append(f"Non-Cosmetic Hits ({len(non_cosmetic)}):")
        lines.append("-" * 70)
        for h in non_cosmetic:
            lines.append(f"  [{h.severity}] {h.file}:{h.line_number}")
            lines.append(f"    pattern: {h.pattern_name}")
            lines.append(f"    {h.line_text.strip()[:100]}")
            lines.append("")

    return "\n".join(lines)


def format_json(report: AuditReport) -> str:
    """Format report as JSON."""
    sev = report.by_severity()
    non_cosmetic = sev.get("hard-block", 0) + sev.get("soft-coupling", 0)
    return json.dumps(
        {
            "files_scanned": report.files_scanned,
            "lines_scanned": report.lines_scanned,
            "total_coupling": report.total,
            "non_cosmetic_coupling": non_cosmetic,
            "by_severity": sev,
            "by_pattern": report.by_pattern(),
            "by_file": report.by_file(),
            "hits": [
                {
                    "file": h.file,
                    "line": h.line_number,
                    "pattern": h.pattern_name,
                    "severity": h.severity,
                    "in_comment": h.in_comment,
                }
                for h in report.hits
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _find_ops_dir() -> Path:
    """Locate the ops package directory relative to repo root."""
    # Try relative to script location first
    script_dir = Path(__file__).resolve().parent
    # scripts/internal/audit_portability.py -> repo root
    repo_root = script_dir.parent.parent
    ops_dir = repo_root / "src" / "bid_euchre" / "ops"
    if ops_dir.is_dir():
        return ops_dir

    # Try CWD
    cwd_ops = Path.cwd() / "src" / "bid_euchre" / "ops"
    if cwd_ops.is_dir():
        return cwd_ops

    print(
        f"ERROR: Cannot find ops directory (tried {ops_dir} and {cwd_ops})",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit ops package for project-specific coupling",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Fail (exit 1) if total coupling count exceeds this value",
    )
    parser.add_argument(
        "--non-cosmetic-threshold",
        type=int,
        default=None,
        help="Fail (exit 1) if non-cosmetic (hard-block + soft-coupling) count exceeds this",
    )
    parser.add_argument(
        "--ops-dir",
        type=Path,
        default=None,
        help="Path to the ops package directory (auto-detected if omitted)",
    )
    args = parser.parse_args()

    ops_dir = args.ops_dir or _find_ops_dir()
    report = run_audit(ops_dir)

    if args.json:
        print(format_json(report))
    else:
        print(format_human(report))

    if args.threshold is not None and report.total > args.threshold:
        print(
            f"\nFAIL: coupling count ({report.total}) exceeds threshold ({args.threshold})",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.non_cosmetic_threshold is not None:
        sev = report.by_severity()
        non_cosmetic = sev.get("hard-block", 0) + sev.get("soft-coupling", 0)
        if non_cosmetic > args.non_cosmetic_threshold:
            print(
                f"\nFAIL: non-cosmetic coupling ({non_cosmetic}) exceeds "
                f"threshold ({args.non_cosmetic_threshold})",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
