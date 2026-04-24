#!/usr/bin/env python3
"""Agent-Readability Scorecard runner.

Per Primitive C shaping §4.2 (``plans/steward_platform/3_primitive_C/shaping.md``)
and ADR 001 §D3 (``knowledge/adr/001-platform-pattern-reset.md``).

Evaluates the 10 canonical scorecard items against the live repository
and enforces the ≥7/10 floor set by ADR 001. Sub-plans may *tighten*
the floor (8/10 or 9/10) via ``--floor N`` but may not *loosen* it: any
value below 7 is rejected with an explicit citation to ADR 001.

This runner is deliberately side-effect free in ``--stdout`` mode so
it can be invoked during preflight gates without write permissions on
``knowledge/``.

**Exit codes:**

* ``0`` — score ≥ floor (pass)
* ``1`` — invocation / I/O error
* ``2`` — score < floor (fail) or ``--floor`` below ADR 001 minimum

**Usage:**

.. code-block:: bash

    # Print machine-parseable report to stdout (no file write).
    uv run python scripts/internal/agent_readability_score.py --stdout

    # Rewrite knowledge/agent_readability_scorecard.md.
    uv run python scripts/internal/agent_readability_score.py --write

    # Tighten the floor for a sub-plan.
    uv run python scripts/internal/agent_readability_score.py --stdout --floor 8
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ADR_FLOOR = 7
ADR_CITATION = "ADR 001 (knowledge/adr/001-platform-pattern-reset.md §D3)"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemResult:
    """One scorecard item's evaluation result.

    ``number`` is the 1-based position in the canonical §4.2 table;
    ``slug`` is the machine-readable key used in the stdout report.
    """

    number: int
    slug: str
    title: str
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# Item implementations (10 items, §4.2 table order)
# ---------------------------------------------------------------------------


def _item_1_claude_md_line_count(repo_root: Path) -> ItemResult:
    """Item 1 — ``CLAUDE.md`` ≤ 200 lines."""
    target = repo_root / "CLAUDE.md"
    if not target.exists():
        return ItemResult(
            1,
            "claude_md_line_count",
            "CLAUDE.md ≤ 200 lines",
            False,
            "FAIL: CLAUDE.md not found at repo root",
        )
    lines = target.read_text(encoding="utf-8").splitlines()
    passed = len(lines) <= 200
    detail = f"{len(lines)} lines; limit 200"
    return ItemResult(
        1, "claude_md_line_count", "CLAUDE.md ≤ 200 lines", passed, detail
    )


def _count_h1_outside_fences(text: str) -> int:
    r"""Count ``# Heading`` lines, ignoring fenced code blocks.

    Comments inside ``\`\`\`bash`` blocks that begin with ``# `` are not
    Markdown H1 headings — they are shell comments. Without this filter,
    any CLAUDE.md with bash examples that include comments like
    ``# Run experiment`` is incorrectly counted as having extra H1s.
    """
    in_fence = False
    count = 0
    fence_re = re.compile(r"^\s*```")
    h1_re = re.compile(r"^# [^#]")
    for line in text.splitlines():
        if fence_re.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if h1_re.match(line):
            count += 1
    return count


def _item_2_canonical_entry(repo_root: Path) -> ItemResult:
    """Item 2 — single canonical entry point for new sessions.

    Pass if CLAUDE.md has exactly one top-level ``# `` heading (outside
    fenced code blocks) AND at least one of {CLAUDE.md,
    .claude/CLAUDE.md} carries a recognizable entry-point marker
    (``## Project Overview`` heading).
    """
    claude_md = repo_root / "CLAUDE.md"
    dotclaude_md = repo_root / ".claude" / "CLAUDE.md"
    if not claude_md.exists():
        return ItemResult(
            2,
            "canonical_entry",
            "Single canonical entry point",
            False,
            "FAIL: CLAUDE.md not found",
        )
    text = claude_md.read_text(encoding="utf-8")
    h1_count = _count_h1_outside_fences(text)
    has_marker = False
    for candidate in (claude_md, dotclaude_md):
        if candidate.exists() and "## Project Overview" in candidate.read_text(
            encoding="utf-8"
        ):
            has_marker = True
            break
    passed = h1_count == 1 and has_marker
    detail = (
        f"H1 count={h1_count}; Project-Overview marker={'yes' if has_marker else 'no'}"
    )
    return ItemResult(
        2, "canonical_entry", "Single canonical entry point", passed, detail
    )


_GOVERNING_PLAN_RE = re.compile(r"plans/[a-z_]+/governing_plan\.md")


def _item_3_governing_plan_findable(repo_root: Path) -> ItemResult:
    """Item 3 — active governing plan findable in ≤2 hops from repo root.

    Pass if ``CLAUDE.md`` and/or ``MEMORY.md`` together carry at least
    one literal reference to ``plans/<initiative>/governing_plan.md``.
    """
    matches: list[str] = []
    for name in ("CLAUDE.md", "MEMORY.md"):
        target = repo_root / name
        if not target.exists():
            continue
        for match in _GOVERNING_PLAN_RE.finditer(target.read_text(encoding="utf-8")):
            matches.append(f"{name}:{match.group(0)}")
    passed = len(matches) >= 1
    if passed:
        detail = f"{len(matches)} reference(s): {matches[0]}" + (
            f" (+{len(matches) - 1} more)" if len(matches) > 1 else ""
        )
    else:
        detail = "no plans/<initiative>/governing_plan.md reference found in CLAUDE.md or MEMORY.md"
    return ItemResult(
        3,
        "governing_plan_findable",
        "Governing plan findable in ≤2 hops",
        passed,
        detail,
    )


def _item_4_skills_discoverable(repo_root: Path) -> ItemResult:
    """Item 4 — all skills discoverable from ``.claude/skills/``.

    Pass if every ``.claude/skills/*/SKILL.md`` has ``name:`` and
    ``description:`` frontmatter fields AND no ``SKILL.md`` lives
    outside ``.claude/skills/``.
    """
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.is_dir():
        return ItemResult(
            4,
            "skills_discoverable",
            "Skills discoverable",
            False,
            "FAIL: .claude/skills/ not found",
        )
    skill_files = list(skills_dir.glob("*/SKILL.md"))
    missing_fields: list[str] = []
    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        # Frontmatter is bounded by leading and closing `---` lines.
        if not text.lstrip().startswith("---"):
            missing_fields.append(
                f"{skill_file.relative_to(repo_root)}: no frontmatter"
            )
            continue
        frontmatter_end = text.find("---", text.find("---") + 3)
        frontmatter = text[:frontmatter_end] if frontmatter_end != -1 else text
        has_name = bool(re.search(r"^name:\s*\S", frontmatter, re.MULTILINE))
        has_desc = bool(re.search(r"^description:\s*\S", frontmatter, re.MULTILINE))
        if not has_name or not has_desc:
            missing_fields.append(
                f"{skill_file.relative_to(repo_root)}: missing "
                + (
                    " ".join(
                        f
                        for f, ok in [("name", has_name), ("description", has_desc)]
                        if not ok
                    )
                )
            )
    # Count any SKILL.md living outside .claude/skills/ (should be none).
    outside_skills: list[str] = []
    for stray in repo_root.rglob("SKILL.md"):
        try:
            stray.resolve().relative_to(skills_dir.resolve())
        except ValueError:
            # Exclude virtualenv caches and other non-source artifacts.
            rel = stray.relative_to(repo_root)
            parts = rel.parts
            if parts and parts[0] in {".venv", ".git", "node_modules", "__pycache__"}:
                continue
            outside_skills.append(str(rel))
    passed = not missing_fields and not outside_skills
    orphan_note = (
        ""
        if not outside_skills
        else f"; {len(outside_skills)} SKILL.md outside .claude/skills/"
    )
    if passed:
        detail = f"{len(skill_files)} skills; 0 orphans"
    else:
        fragments = []
        if missing_fields:
            fragments.append(f"{len(missing_fields)} frontmatter issue(s)")
        if outside_skills:
            fragments.append(f"{len(outside_skills)} stray SKILL.md")
        detail = f"{len(skill_files)} skills; " + ", ".join(fragments) + orphan_note
    return ItemResult(4, "skills_discoverable", "Skills discoverable", passed, detail)


_LANE_POOL_PATTERNS: dict[str, re.Pattern[str]] = {
    "platform": re.compile(r"Bid-Euchre-steward-author(-[a-d])?\b"),
    "browser": re.compile(r"Bid-Euchre-steward-brws-author-[a-d]\b"),
    "analyst": re.compile(r"Bid-Euchre-steward-analyst(-[b-d])?\b"),
    "flex": re.compile(r"Bid-Euchre-steward-flex-[a-d]\b"),
    "control": re.compile(r"Bid-Euchre-steward-(review|ops)\b"),
}


def _item_5_lane_registry_authoritative(repo_root: Path) -> ItemResult:
    """Item 5 — lane registry is authoritative, not inferred.

    Pass if ``.claude/rules/75_worktree_protection.md`` exists AND
    enumerates ≥1 lane per pool (platform / browser / analyst / flex /
    control).
    """
    target = repo_root / ".claude" / "rules" / "75_worktree_protection.md"
    if not target.exists():
        return ItemResult(
            5,
            "lane_registry_authoritative",
            "Lane registry authoritative",
            False,
            "FAIL: .claude/rules/75_worktree_protection.md missing",
        )
    text = target.read_text(encoding="utf-8")
    covered: list[str] = []
    missing: list[str] = []
    for pool, pattern in _LANE_POOL_PATTERNS.items():
        if pattern.search(text):
            covered.append(pool)
        else:
            missing.append(pool)
    passed = not missing
    if passed:
        detail = f"pools covered: {', '.join(covered)}"
    else:
        detail = (
            f"pools missing: {', '.join(missing)}; "
            f"pools covered: {', '.join(covered) if covered else '(none)'}"
        )
    return ItemResult(
        5,
        "lane_registry_authoritative",
        "Lane registry authoritative",
        passed,
        detail,
    )


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _item_6_memory_indexes(repo_root: Path) -> ItemResult:
    """Item 6 — ``MEMORY.md`` indexes rather than recaps.

    Pass if ratio of markdown ``[link](path)`` references to non-blank
    lines in ``MEMORY.md`` exceeds 0.10. A missing ``MEMORY.md`` FAILS
    loudly (the item is a signal that the file is present *and*
    index-shaped).
    """
    target = repo_root / "MEMORY.md"
    if not target.exists():
        return ItemResult(
            6,
            "memory_indexes",
            "MEMORY.md indexes rather than recaps",
            False,
            "FAIL: MEMORY.md not found",
        )
    text = target.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ItemResult(
            6,
            "memory_indexes",
            "MEMORY.md indexes rather than recaps",
            False,
            "FAIL: MEMORY.md is empty",
        )
    link_count = len(_MARKDOWN_LINK_RE.findall(text))
    ratio = link_count / len(lines)
    passed = ratio > 0.10
    detail = (
        f"link-ratio={ratio:.3f} ({link_count} links / {len(lines)} non-blank lines); "
        f"threshold 0.10"
    )
    return ItemResult(
        6,
        "memory_indexes",
        "MEMORY.md indexes rather than recaps",
        passed,
        detail,
    )


_ADR_FILE_STEM_RE = re.compile(r"^([0-9]+|[A-Z][0-9]+)-")
_ADR_INDEX_ROW_RE = re.compile(
    r"^\|\s*\*?\*?([0-9]+|[A-Z][0-9]+)\*?\*?\s*\|",
    re.MULTILINE,
)


def _item_7_adr_index_current(repo_root: Path) -> ItemResult:
    """Item 7 — ADR index current.

    Pass if every ADR file on disk (``knowledge/adr/<N>-*.md`` or
    ``knowledge/adr/<LetterN>-*.md``) has a matching index row in
    ``knowledge/adr/README.md``. Seeded entries are tracked in the index
    even if the promoted file has not yet landed, so index-count ≥
    disk-count is the correct inequality.
    """
    adr_dir = repo_root / "knowledge" / "adr"
    readme = adr_dir / "README.md"
    if not readme.exists():
        return ItemResult(
            7,
            "adr_index_current",
            "ADR index current",
            False,
            "FAIL: knowledge/adr/README.md missing",
        )
    on_disk: list[str] = []
    for entry in sorted(adr_dir.glob("*.md")):
        if entry.name == "README.md":
            continue
        m = _ADR_FILE_STEM_RE.match(entry.name)
        if m:
            on_disk.append(m.group(1))
    index_ids = set(_ADR_INDEX_ROW_RE.findall(readme.read_text(encoding="utf-8")))
    missing = [aid for aid in on_disk if aid not in index_ids]
    passed = not missing
    if passed:
        detail = (
            f"{len(on_disk)} ADR file(s) on disk; "
            f"{len(index_ids)} ID(s) indexed in README"
        )
    else:
        detail = f"{len(missing)} ADR file(s) missing from README index: " + ", ".join(
            missing
        )
    return ItemResult(7, "adr_index_current", "ADR index current", passed, detail)


def _item_8_kb_index_current(repo_root: Path) -> ItemResult:
    """Item 8 — KB ``INDEX.md`` current.

    Pass if ``kb_index.py --check`` exits 0 (stdout-equivalent to
    committed INDEX).
    """
    script = repo_root / "scripts" / "internal" / "kb_index.py"
    if not script.exists():
        return ItemResult(
            8,
            "kb_index_current",
            "KB INDEX current",
            False,
            "FAIL: scripts/internal/kb_index.py missing",
        )
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(repo_root), "--check"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ItemResult(
            8,
            "kb_index_current",
            "KB INDEX current",
            False,
            f"FAIL: kb_index.py invocation error: {exc}",
        )
    passed = proc.returncode == 0
    if passed:
        detail = "kb_index.py --check exit 0 (INDEX up to date)"
    else:
        detail = (
            f"kb_index.py --check exit {proc.returncode}: "
            + (proc.stderr.strip().splitlines() or ["(no stderr)"])[0]
        )
    return ItemResult(8, "kb_index_current", "KB INDEX current", passed, detail)


def _item_9_no_orphan_refs(repo_root: Path) -> ItemResult:
    """Item 9 — no orphan references in plans.

    Pass if ``agent_readability_lint.py check load-bearing-ownership
    plans/`` exits 0 (no BLOCK findings). WARN-only exits are treated
    as pass — the scorecard is tracking *blocker-grade* orphans only.
    """
    script = repo_root / "scripts" / "internal" / "agent_readability_lint.py"
    if not script.exists():
        return ItemResult(
            9,
            "no_orphan_refs",
            "No orphan references in plans",
            False,
            "FAIL: agent_readability_lint.py missing",
        )
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--repo-root",
                str(repo_root),
                "--warnings-ok",
                "check",
                "load-bearing-ownership",
                "plans/",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ItemResult(
            9,
            "no_orphan_refs",
            "No orphan references in plans",
            False,
            f"FAIL: lint invocation error: {exc}",
        )
    passed = proc.returncode == 0
    if passed:
        detail = "lint check load-bearing-ownership exit 0 (no BLOCK findings)"
    else:
        # Extract the first BLOCK line from stdout, if any.
        first_block = next(
            (line for line in proc.stdout.splitlines() if "BLOCK" in line),
            proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else "",
        )
        detail = f"lint exit {proc.returncode}: {first_block}"
    return ItemResult(
        9, "no_orphan_refs", "No orphan references in plans", passed, detail
    )


def _item_10_rules_grep_discoverable(repo_root: Path) -> ItemResult:
    """Item 10 — rule files grep-discoverable.

    Pass if every ``.claude/rules/**/*.md`` is referenced (by path)
    from ``CLAUDE.md``, ``.claude/CLAUDE.md``, or another rule file.
    """
    rules_dir = repo_root / ".claude" / "rules"
    if not rules_dir.is_dir():
        return ItemResult(
            10,
            "rules_grep_discoverable",
            "Rule files grep-discoverable",
            False,
            "FAIL: .claude/rules/ missing",
        )
    rule_files = sorted(p for p in rules_dir.rglob("*.md") if p.is_file())
    if not rule_files:
        return ItemResult(
            10,
            "rules_grep_discoverable",
            "Rule files grep-discoverable",
            False,
            "FAIL: no rule files found under .claude/rules/",
        )
    # Assemble the corpus: CLAUDE.md + .claude/CLAUDE.md + every rule file.
    corpus_parts: list[str] = []
    for extra in (repo_root / "CLAUDE.md", repo_root / ".claude" / "CLAUDE.md"):
        if extra.exists():
            corpus_parts.append(extra.read_text(encoding="utf-8"))
    for rule_file in rule_files:
        corpus_parts.append(rule_file.read_text(encoding="utf-8"))
    corpus = "\n".join(corpus_parts)
    orphans: list[str] = []
    for rule_file in rule_files:
        rel = rule_file.relative_to(repo_root).as_posix()
        # A rule is discoverable if its relative path (or its basename)
        # appears anywhere in the corpus. Basename-only is acceptable
        # because rule cross-references sometimes use e.g. the filename
        # in running prose.
        basename = rule_file.name
        if rel not in corpus and basename not in corpus:
            orphans.append(rel)
    passed = not orphans
    if passed:
        detail = f"{len(rule_files)} rule file(s); 0 orphan(s)"
    else:
        detail = (
            f"{len(orphans)} orphan rule file(s): "
            + ", ".join(orphans[:3])
            + (f" (+{len(orphans) - 3} more)" if len(orphans) > 3 else "")
        )
    return ItemResult(
        10,
        "rules_grep_discoverable",
        "Rule files grep-discoverable",
        passed,
        detail,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


ITEM_FUNCTIONS = (
    _item_1_claude_md_line_count,
    _item_2_canonical_entry,
    _item_3_governing_plan_findable,
    _item_4_skills_discoverable,
    _item_5_lane_registry_authoritative,
    _item_6_memory_indexes,
    _item_7_adr_index_current,
    _item_8_kb_index_current,
    _item_9_no_orphan_refs,
    _item_10_rules_grep_discoverable,
)


def score(repo_root: Path) -> list[ItemResult]:
    """Run every scorecard item against ``repo_root`` in numeric order."""
    return [fn(repo_root) for fn in ITEM_FUNCTIONS]


def _render_stdout(results: list[ItemResult]) -> str:
    total = sum(1 for r in results if r.passed)
    lines = [f"agent_readability_score: {total}/{len(results)}"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"item_{r.number}_{r.slug}: {status} ({r.detail})")
    return "\n".join(lines) + "\n"


def _render_file(results: list[ItemResult], floor: int, now: datetime) -> str:
    total = sum(1 for r in results if r.passed)
    rows = []
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        rows.append(f"| {r.number} | {r.title} | {status} | {r.detail} |")
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")
    # The floor header is the ADR-mandated minimum; invocation floor
    # (which may be ≥ ADR floor for a sub-plan tightening) is shown
    # separately in the run log.
    invocation_note = "" if floor == ADR_FLOOR else f" (invoked with --floor {floor})"
    return (
        "# Agent-Readability Scorecard\n\n"
        f"**Floor (per ADR 001):** ≥{ADR_FLOOR}/10\n"
        f"**Current score:** {total}/{len(results)} (last run {date_str}){invocation_note}\n"
        "**Phase 0 baseline:** <recorded at Phase 0 Readiness>\n"
        "**Phase 1 end score:** <recorded at Phase 1 end; must ≥ Phase 0 baseline>\n\n"
        "## Items\n\n"
        "| # | Item | Status | Detail |\n"
        "|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        "## Run log\n\n"
        f"- {now.strftime('%Y-%m-%d')}: {total}/10"
        f" — scorecard runner v0 — lane-automated — post-Phase-0-scaffold"
        f" — floor {floor}/10\n"
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent_readability_score",
        description=(
            "Agent-readability scorecard runner (Primitive C shaping §4.2). "
            f"Enforces ≥{ADR_FLOOR}/10 floor per {ADR_CITATION}."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: inferred from script path).",
    )
    parser.add_argument(
        "--floor",
        type=int,
        default=ADR_FLOOR,
        help=f"Minimum passing score; must be ≥{ADR_FLOOR} ({ADR_CITATION}).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="Overwrite knowledge/agent_readability_scorecard.md with today's score.",
    )
    mode.add_argument(
        "--stdout",
        action="store_true",
        help="Print machine-parseable scorecard to stdout (default).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.floor < ADR_FLOOR:
        print(
            f"error: --floor {args.floor} < {ADR_FLOOR}; the floor set by {ADR_CITATION} "
            "may not be loosened by script invocation.",
            file=sys.stderr,
        )
        return 2
    repo_root = args.repo_root.resolve()
    results = score(repo_root)
    total = sum(1 for r in results if r.passed)
    rendered = _render_stdout(results)
    if args.write:
        out = repo_root / "knowledge" / "agent_readability_scorecard.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _render_file(results, args.floor, datetime.now(tz=timezone.utc)),
            encoding="utf-8",
        )
        sys.stdout.write(rendered)
    else:
        sys.stdout.write(rendered)
    if total < args.floor:
        print(
            f"score {total}/{len(results)} < floor {args.floor} ({ADR_CITATION})",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
