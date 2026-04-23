#!/usr/bin/env python3
"""Agent-readability lint for steward-platform plan/artifact health.

This is the shared lint harness for two draft-8 §10.9 patterns:

* **Pattern 9 — Load-bearing-ownership lint.** Every *load-bearing* item
  (cross-linked, referenced-from-multiple-places, gate-input) must have a
  named owner in its originating primitive.  Rule set: ``check
  load-bearing-ownership`` *(scaffold only in Packet 2b; rule set lands in
  a follow-up).*

* **Pattern 10 — Verification surface per deliverable.** Every plan/sub-plan
  ``§N.M`` Work bullet or Readiness bullet must be backed by a row in its
  plan's ``## Verification Plan`` section OR in the canonical
  ``plans/steward_platform/verification_contract/map.md``.  Rule set:
  ``check verification-contract``.

**Shared-module dependency (§13.2 risk #2 of verification_contract/shaping.md):**
both rule sets consume the same plan-walker core and the same row-parser
primitives.  Breaking or regressing the plan-walker *silently degrades both
Pattern 9 and Pattern 10 enforcement at once.*  Tests for either rule set
therefore live alongside shared-core tests in
``tests/unit/test_agent_readability_lint.py`` and the plan-walker must be
treated as a single-owner component even though it is exercised by two
distinct rule sets.

Usage
-----
::

    uv run python scripts/internal/agent_readability_lint.py \\
        check verification-contract [PATH ...]

    uv run python scripts/internal/agent_readability_lint.py \\
        check load-bearing-ownership [PATH ...]  # Pattern 9 scaffold

If no ``PATH`` is provided, the lint walks ``plans/`` from the repository
root.

Exit codes
----------
* ``0`` — lint passes (no findings, or only INFO findings)
* ``1`` — invocation error (unknown sub-command, bad path, malformed CLI)
* ``2`` — lint findings present (BLOCK or WARN severity)

Severity semantics follow ``.claude/rules/deferred/60_review_gate.md``:
BLOCK fails the precheck; WARN is reported but non-fatal under
``--warnings-ok``; INFO is recorded in the report only.

Pattern 10 — see ``plans/steward_platform/governing_plan.md`` §10.9 and
``plans/steward_platform/verification_contract/shaping.md`` §3.2(iii).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Severity model (aligned with 60_review_gate.md)
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


@dataclass
class Finding:
    severity: Severity
    rule_id: str
    path: Path
    line: int
    message: str

    def format_line(self) -> str:
        return f"{self.severity.value} [{self.rule_id}] {self.path}:{self.line}: {self.message}"


# ---------------------------------------------------------------------------
# Plan-walker core (shared by Pattern 9 and Pattern 10 rule sets)
# ---------------------------------------------------------------------------

# A §N.M section heading, e.g. `## §5.3`, `### §5.3 Work`, `## 5.3`.  We
# accept both the section-sigil form (§5.3) and the plain-number form
# (5.3 Work) to keep the walker lenient-form per Pattern 10.
SECTION_HEADING_RE = re.compile(
    r"^(?P<hashes>#{1,6})\s+(?:§\s*)?(?P<num>\d+(?:\.\d+)+)\b", re.MULTILINE
)

# A "Work bullet" or "Readiness bullet": a markdown list item under a
# `Work`/`Readiness`/`Deliverables` heading.  We detect the containing
# heading via the walker, then treat every `- ` list item under it as a
# candidate deliverable.
WORK_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:§\s*\d+(?:\.\d+)+\s+)?(Work|Readiness|Deliverables)\b",
    re.IGNORECASE | re.MULTILINE,
)

# A deliverable row in a `## Verification Plan` table.  Columns:
# Deliverable | Class | Verification surface | Owner | Acceptance.
VERIFICATION_ROW_RE = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)

VERIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s+Verification\s+Plan\b", re.IGNORECASE | re.MULTILINE
)


@dataclass
class DeliverableBullet:
    """A `Work`/`Readiness` bullet found in a plan §N.M section."""

    path: Path
    section_num: str
    bullet_text: str
    line: int


@dataclass
class VerificationRow:
    """A row under a `## Verification Plan` section."""

    path: Path
    deliverable: str
    class_: str
    surface: str
    owner: str
    acceptance: str
    line: int


@dataclass
class PlanWalk:
    deliverables: list[DeliverableBullet] = field(default_factory=list)
    verification_rows: list[VerificationRow] = field(default_factory=list)
    plans_walked: list[Path] = field(default_factory=list)


def walk_plans(roots: list[Path]) -> PlanWalk:
    """Walk plan-like markdown files rooted at the given paths.

    A "plan-like" file is any ``*.md`` under ``plans/``, ``plans/_templates``,
    ``plans/sessions``, or ``.claude/skills``.  For Packet 2b we scope the
    walker to ``plans/`` because that is where Pattern 10's contract lives;
    skills are sub-walked only when a caller explicitly includes them.
    """
    walk = PlanWalk()
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".md":
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            # Skip archival drafts — they are historical snapshots, not live
            # plans subject to Pattern 10 enforcement.
            if "_archive" in p.parts or "archive" in p.parts:
                continue
            files.append(p)

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        walk.plans_walked.append(path)
        _walk_file(path, text, walk)
    return walk


def _walk_file(path: Path, text: str, walk: PlanWalk) -> None:
    lines = text.splitlines()

    # Find all Work/Readiness/Deliverables headings and collect their bullets.
    work_headings = list(WORK_HEADING_RE.finditer(text))
    # Map each work heading to its §N.M number by searching backward for the
    # most recent numbered-section heading.
    for m in work_headings:
        heading_line_idx = text[: m.start()].count("\n")
        section_num = _nearest_section_num(lines, heading_line_idx)
        if section_num is None:
            continue
        # Collect bullets until next heading of equal or higher level.
        heading_level = len(m.group(0).split()[0])
        bullets = _collect_bullets_under_heading(lines, heading_line_idx, heading_level)
        for bullet_line_idx, bullet_text in bullets:
            walk.deliverables.append(
                DeliverableBullet(
                    path=path,
                    section_num=section_num,
                    bullet_text=bullet_text,
                    line=bullet_line_idx + 1,
                )
            )

    # Find the `## Verification Plan` section (0 or 1 per file) and parse
    # its table rows.
    vp_match = VERIFICATION_HEADING_RE.search(text)
    if vp_match is not None:
        vp_line_idx = text[: vp_match.start()].count("\n")
        vp_level = len(vp_match.group(0).split()[0])
        rows = _collect_verification_rows(path, lines, vp_line_idx, vp_level)
        walk.verification_rows.extend(rows)


def _nearest_section_num(lines: list[str], idx: int) -> str | None:
    """Walk backward from `idx` looking for the nearest ``§N.M`` heading."""
    for i in range(idx, -1, -1):
        m = SECTION_HEADING_RE.match(lines[i])
        if m:
            return m.group("num")
    return None


def _collect_bullets_under_heading(
    lines: list[str], heading_idx: int, heading_level: int
) -> list[tuple[int, str]]:
    """Return ``[(line_idx, bullet_text), ...]`` for list items that fall
    under the heading at ``heading_idx`` until the next heading of equal or
    higher level."""
    bullets: list[tuple[int, str]] = []
    i = heading_idx + 1
    while i < len(lines):
        line = lines[i]
        heading_m = re.match(r"^(#{1,6})\s+", line)
        if heading_m and len(heading_m.group(1)) <= heading_level:
            break
        bullet_m = re.match(r"^\s*[-*]\s+(.*\S)", line)
        if bullet_m:
            bullets.append((i, bullet_m.group(1).strip()))
        i += 1
    return bullets


def _collect_verification_rows(
    path: Path, lines: list[str], heading_idx: int, heading_level: int
) -> list[VerificationRow]:
    rows: list[VerificationRow] = []
    i = heading_idx + 1
    # Skip preamble (non-table content) until we hit a table.
    while i < len(lines):
        line = lines[i]
        heading_m = re.match(r"^(#{1,6})\s+", line)
        if heading_m and len(heading_m.group(1)) <= heading_level:
            break
        if line.startswith("|"):
            # Parse this table block.
            while i < len(lines) and lines[i].startswith("|"):
                table_line = lines[i]
                # Skip separator rows and header rows.
                if re.match(r"^\|[\s\-:|]+\|\s*$", table_line):
                    i += 1
                    continue
                m = VERIFICATION_ROW_RE.match(table_line)
                if m:
                    deliverable, class_, surface, owner, acceptance = (
                        g.strip() for g in m.groups()
                    )
                    # Skip obvious header rows.
                    lower = deliverable.lower()
                    if lower in {"deliverable", "deliverable (§n.m)", "item"}:
                        i += 1
                        continue
                    # Skip the illustrative "(row per …)" template placeholder.
                    if deliverable.startswith("(") and deliverable.endswith(")"):
                        i += 1
                        continue
                    rows.append(
                        VerificationRow(
                            path=path,
                            deliverable=deliverable,
                            class_=class_,
                            surface=surface,
                            owner=owner,
                            acceptance=acceptance,
                            line=i + 1,
                        )
                    )
                i += 1
            continue
        i += 1
    return rows


# ---------------------------------------------------------------------------
# Pattern 10: check verification-contract
# ---------------------------------------------------------------------------


# Tokens in the `surface` column that mean "not a real surface yet".
_SURFACE_PLACEHOLDER_TOKENS = ("TBD", "TODO", "FIXME", "XXX")


def _surface_is_placeholder(surface: str) -> bool:
    upper = surface.upper()
    return any(tok in upper for tok in _SURFACE_PLACEHOLDER_TOKENS)


def _surface_is_present(surface: str) -> bool:
    s = surface.strip()
    return bool(s) and s not in {"—", "-"}


def _load_global_map(repo_root: Path) -> set[str]:
    """Load deliverables from the canonical verification-contract map.

    Returns a set of deliverable-strings covered by the global map.  Used
    by ``check verification-contract`` to allow plans to satisfy Pattern 10
    either via their own ``## Verification Plan`` or via a row in the
    global map (per §6.1 of verification_contract/shaping.md worked
    example).
    """
    map_path = (
        repo_root / "plans" / "steward_platform" / "verification_contract" / "map.md"
    )
    if not map_path.exists():
        return set()
    try:
        text = map_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    deliverables: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        m = VERIFICATION_ROW_RE.match(line)
        if not m:
            continue
        deliverable = m.group(1).strip()
        if deliverable.lower() in {"deliverable", "deliverable (§n.m)", "item"}:
            continue
        if re.match(r"^\|[\s\-:|]+\|?$", line):
            continue
        if deliverable.startswith("(") and deliverable.endswith(")"):
            continue
        if not deliverable:
            continue
        deliverables.add(deliverable)
    return deliverables


def check_verification_contract(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Return all Pattern 10 findings across the given plan roots."""
    walk = walk_plans(roots)
    global_map = _load_global_map(repo_root)
    findings: list[Finding] = []

    # Rule VC1 — Verification Plan rows must carry a non-placeholder surface.
    for row in walk.verification_rows:
        if not _surface_is_present(row.surface):
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="VC1",
                    path=row.path,
                    line=row.line,
                    message=(
                        f"Verification Plan row for {row.deliverable!r} has "
                        f"no surface (column is empty or '—'). Pattern 10 "
                        f"requires a concrete surface."
                    ),
                )
            )
            continue
        if _surface_is_placeholder(row.surface):
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="VC2",
                    path=row.path,
                    line=row.line,
                    message=(
                        f"Verification Plan row for {row.deliverable!r} "
                        f"carries placeholder surface {row.surface!r}. "
                        f"Pattern 10 requires strict-existence; replace "
                        f"TBD/TODO/FIXME/XXX with a real surface before "
                        f"merge."
                    ),
                )
            )

    # Rule VC3 — every Work/Readiness bullet in a plan should be covered
    # by a row either in the same plan's Verification Plan section OR in
    # the global `verification_contract/map.md`.
    #
    # We keep this check WARN (not BLOCK) because the walker is
    # intentionally lenient-form and can false-positive on narrative
    # bullets that are not themselves deliverables.  Review-driver V1/V6
    # promote the plan-change cases to BLOCK at PR time (see shaping
    # §3.4); this periodic lint is the run-against-existing surface.
    #
    # Files that contain their own `## Verification Plan` section opt
    # into covering-via-own-section; files without one opt into
    # covering-via-global-map (or are expected to have no Work/Readiness
    # bullets).
    per_file_rows: dict[Path, list[VerificationRow]] = {}
    for row in walk.verification_rows:
        per_file_rows.setdefault(row.path, []).append(row)

    for bullet in walk.deliverables:
        if _bullet_covered(bullet, per_file_rows.get(bullet.path, []), global_map):
            continue
        findings.append(
            Finding(
                severity=Severity.WARN,
                rule_id="VC3",
                path=bullet.path,
                line=bullet.line,
                message=(
                    f"§{bullet.section_num} bullet {_truncate(bullet.bullet_text, 60)!r} "
                    f"is not covered by a Verification Plan row in this file "
                    f"or by a row in plans/steward_platform/verification_contract/map.md. "
                    f"Pattern 10: add a row naming the verification surface."
                ),
            )
        )

    return findings


def _bullet_covered(
    bullet: DeliverableBullet,
    local_rows: list[VerificationRow],
    global_map: set[str],
) -> bool:
    # Heuristic match: a row covers a bullet if the bullet's section
    # number appears in the row's `Deliverable` column OR a token of the
    # bullet text appears in the `Deliverable` column.  This is
    # deliberately lenient-form per Pattern 10.
    section_needle = f"§{bullet.section_num}"
    raw_needle = bullet.section_num
    bullet_tokens = _bullet_keywords(bullet.bullet_text)
    for row in local_rows:
        d = row.deliverable
        if (
            section_needle in d
            or d.startswith(raw_needle)
            or f" {raw_needle}" in f" {d}"
        ):
            return True
        for tok in bullet_tokens:
            if tok and tok in d:
                return True
    for deliverable in global_map:
        if section_needle in deliverable or deliverable.startswith(raw_needle):
            return True
        for tok in bullet_tokens:
            if tok and tok in deliverable:
                return True
    return False


def _bullet_keywords(text: str) -> list[str]:
    """Extract stable keywords from a bullet text for lenient matching.

    We take backtick-quoted code spans and path-like tokens as the stable
    keywords.  Natural-language prose is ignored.
    """
    keywords: list[str] = []
    for m in re.finditer(r"`([^`]+)`", text):
        keywords.append(m.group(1).strip())
    for m in re.finditer(
        r"[A-Za-z_./][A-Za-z0-9_./\-]*\.(py|md|json|yaml|yml|sh)", text
    ):
        keywords.append(m.group(0))
    return keywords


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Pattern 9 scaffold: check load-bearing-ownership
# ---------------------------------------------------------------------------


def check_load_bearing_ownership(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Scaffold for Pattern 9 enforcement.

    The Pattern 9 rule set is enumerated in draft 8 §10.9 and folded into
    this harness per the shared-module decision in §13.2 risk #2 of
    verification_contract/shaping.md.  The concrete rule set lands in a
    follow-up PR; Packet 2b ships the scaffold and ensures the sub-command
    is available so downstream callers have a stable interface.
    """
    # Intentionally no findings in the scaffold version.  Tests assert the
    # sub-command exits 0 over a known-clean tree.
    _ = roots
    _ = repo_root
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_findings(findings: list[Finding], stream) -> None:  # type: ignore[no-untyped-def]
    for f in findings:
        print(f.format_line(), file=stream)


def _exit_code_for_findings(findings: list[Finding], warnings_ok: bool) -> int:
    blocks = [f for f in findings if f.severity == Severity.BLOCK]
    warns = [f for f in findings if f.severity == Severity.WARN]
    if blocks:
        return 2
    if warns and not warnings_ok:
        return 2
    return 0


def _default_roots(repo_root: Path) -> list[Path]:
    return [repo_root / "plans"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent_readability_lint",
        description=(
            "Agent-readability lint for steward-platform plan health "
            "(Pattern 9 + Pattern 10)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: inferred from script path)",
    )
    parser.add_argument(
        "--warnings-ok",
        action="store_true",
        help="Exit 0 even if WARN findings are present (BLOCK still exits 2).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run a named rule set")
    check_sub = check.add_subparsers(dest="rule_set", required=True)

    vc = check_sub.add_parser(
        "verification-contract",
        help="Pattern 10 — verify surface-per-deliverable contract",
    )
    vc.add_argument("paths", nargs="*", type=Path, help="Plan paths to walk")

    lbo = check_sub.add_parser(
        "load-bearing-ownership",
        help="Pattern 9 — verify load-bearing items have named owners",
    )
    lbo.add_argument("paths", nargs="*", type=Path, help="Plan paths to walk")

    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    paths: list[Path] = list(args.paths) or _default_roots(repo_root)

    # Validate paths exist to avoid silent empty walks.
    for p in paths:
        if not p.exists():
            print(f"ERROR: path not found: {p}", file=sys.stderr)
            return 1

    if args.rule_set == "verification-contract":
        findings = check_verification_contract(paths, repo_root)
    elif args.rule_set == "load-bearing-ownership":
        findings = check_load_bearing_ownership(paths, repo_root)
    else:  # pragma: no cover - argparse enforces
        print(f"ERROR: unknown rule set: {args.rule_set}", file=sys.stderr)
        return 1

    if findings:
        _print_findings(findings, sys.stdout)
    else:
        print("agent_readability_lint: 0 findings")

    return _exit_code_for_findings(findings, args.warnings_ok)


if __name__ == "__main__":
    sys.exit(main())
