#!/usr/bin/env python3
"""Verify Pattern 10 verification-contract map coverage.

Walks a ``map.md`` file (default
``plans/steward_platform/verification_contract/map.md``) and computes:

  coverage = rows_with_valid_surface / rows_total

Fails (exit 2) if coverage is below the threshold (default 0.90) or if
any row has a placeholder / stub surface (``TBD`` / ``TODO`` / ``FIXME``
/ ``XXX``). Prints a per-row report to stdout.

Usage::

    uv run python scripts/internal/verify_map_coverage.py [map_path] [--threshold N] [--allow-under-coverage]

Exit codes:
    0 — coverage meets threshold and no placeholder surfaces
    1 — invocation error (bad path, malformed args)
    2 — coverage below threshold or placeholder surfaces present
        (override with --allow-under-coverage; exit still 2 but
        informational message)

Pattern 10 — Verification surface per deliverable. See
``plans/steward_platform/governing_plan.md`` §10.9.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Tokens that fail the strict-existence check for a verification surface.
PLACEHOLDER_TOKENS = ("TBD", "TODO", "FIXME", "XXX")

# Row pattern: any pipe-delimited table row with ≥5 columns (Deliverable,
# Class, Surface, Owner, Acceptance). Header and separator rows are
# filtered out in the walker.
ROW_RE = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)
HEADER_HINT_RE = re.compile(r"^\|\s*(Deliverable|Item|#|\s*-+\s*)", re.IGNORECASE)
SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|\s*$")


@dataclass
class MapRow:
    """One parsed row from the coverage map."""

    deliverable: str
    class_: str
    surface: str
    owner: str
    acceptance: str
    line_number: int

    @property
    def has_placeholder(self) -> bool:
        # Only the surface column is strict-enforced per Pattern 10.
        # Deliverable/acceptance can have free-form text that happens to
        # contain TODO-like strings (e.g., "plan tracks TODO items").
        upper = self.surface.upper()
        return any(token in upper for token in PLACEHOLDER_TOKENS)

    @property
    def has_surface(self) -> bool:
        stripped = self.surface.strip()
        return bool(stripped) and stripped != "—" and stripped != "-"


@dataclass
class CoverageReport:
    rows_total: int
    rows_with_surface: int
    rows_with_placeholder: int
    placeholder_rows: list[MapRow]
    no_surface_rows: list[MapRow]

    @property
    def coverage(self) -> float:
        if self.rows_total == 0:
            return 0.0
        return self.rows_with_surface / self.rows_total


def parse_map(path: Path) -> list[MapRow]:
    """Extract deliverable rows from a map.md file.

    Heuristics:
      - Skip lines that do not match a 5-column pipe-delimited pattern.
      - Skip header rows (first column is a known header keyword or the
        row is the separator ``| --- | --- | ...``).
    """
    rows: list[MapRow] = []
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")
    for i, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if SEPARATOR_RE.match(line):
            continue
        if HEADER_HINT_RE.match(line):
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        deliverable, class_, surface, owner, acceptance = (
            g.strip() for g in m.groups()
        )
        # Skip the illustrative "(row per …)" placeholder rows.
        if deliverable.startswith("(") and deliverable.endswith(")"):
            continue
        rows.append(
            MapRow(
                deliverable=deliverable,
                class_=class_,
                surface=surface,
                owner=owner,
                acceptance=acceptance,
                line_number=i,
            )
        )
    return rows


def compute_coverage(rows: list[MapRow]) -> CoverageReport:
    placeholder_rows = [r for r in rows if r.has_placeholder]
    no_surface_rows = [r for r in rows if not r.has_surface]
    rows_with_surface = sum(1 for r in rows if r.has_surface and not r.has_placeholder)
    return CoverageReport(
        rows_total=len(rows),
        rows_with_surface=rows_with_surface,
        rows_with_placeholder=len(placeholder_rows),
        placeholder_rows=placeholder_rows,
        no_surface_rows=no_surface_rows,
    )


def format_report(report: CoverageReport, threshold: float) -> str:
    lines = [
        "Verification-Contract Map Coverage Report",
        "==========================================",
        f"Total rows:            {report.rows_total}",
        f"Rows with surface:     {report.rows_with_surface}",
        f"Rows with placeholder: {report.rows_with_placeholder}",
        f"Coverage:              {report.coverage:.2%}",
        f"Threshold:             {threshold:.2%}",
        "",
    ]
    if report.placeholder_rows:
        lines.append("Placeholder surfaces (BLOCK):")
        for r in report.placeholder_rows:
            lines.append(
                f"  L{r.line_number}: {r.deliverable!r} — surface={r.surface!r}"
            )
    if report.no_surface_rows:
        lines.append("Rows missing a surface:")
        for r in report.no_surface_rows:
            lines.append(f"  L{r.line_number}: {r.deliverable!r}")
    if not report.placeholder_rows and not report.no_surface_rows:
        lines.append("All rows carry a concrete verification surface.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    description = (__doc__ or "Verify Pattern 10 map coverage.").strip().splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "map_path",
        nargs="?",
        default="plans/steward_platform/verification_contract/map.md",
        type=Path,
        help="Path to map.md",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        help="Coverage ratio required (default 0.90)",
    )
    parser.add_argument(
        "--allow-under-coverage",
        action="store_true",
        help="Emit report but do not exit non-zero on under-coverage "
        "(operator override; usage is logged to review_log.md as a "
        "one-off, per sub_plan.md §Rollback).",
    )
    args = parser.parse_args(argv)

    try:
        rows = parse_map(args.map_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = compute_coverage(rows)
    print(format_report(report, args.threshold))

    failed = (report.coverage < args.threshold) or bool(report.placeholder_rows)
    if failed and not args.allow_under_coverage:
        return 2
    if failed and args.allow_under_coverage:
        print(
            "\nNOTE: --allow-under-coverage set; would have failed "
            "(exit 2) without override.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
