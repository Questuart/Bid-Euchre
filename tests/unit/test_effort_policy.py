"""Unit tests for `bid_euchre.ops.effort_policy` and `.claude/rules/effort_policy.md`.

Covers:
- `effort_for(archetype, task_type)` returns the expected tier for known pairs.
- `effort_for` raises `ValueError` on `n/a` pairings.
- `effort_for` raises `ValueError` on unknown archetype / task_type.
- `effort_for` is pure (no I/O; stateless across calls).
- `POLICY_TABLE` and the markdown table in `.claude/rules/effort_policy.md`
  are 1:1 identical (drift guard per shaping §7.4).
- `max` is in `VALID_EFFORT_HINTS` per §7.5 enum extension.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bid_euchre.ops.effort_policy import (
    POLICY_TABLE,
    POLICY_VERSION,
    VALID_TIERS,
    effort_for,
)

# --- Repo-root discovery ---------------------------------------------------


def _repo_root() -> Path:
    """Walk up from this file until we find the repo's `.claude/` dir."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude").is_dir() and (parent / "src" / "bid_euchre").is_dir():
            return parent
    raise RuntimeError(f"could not find repo root from {here}")


EFFORT_POLICY_MD = _repo_root() / ".claude" / "rules" / "effort_policy.md"


# --- effort_for() correctness ---------------------------------------------


class TestEffortFor:
    """Verify the resolver returns the right tier for each (archetype, task_type)."""

    def test_author_implementation_xhigh(self) -> None:
        """Shaping §7.4 example: author + implementation = xhigh."""
        assert effort_for("author", "implementation") == "xhigh"

    def test_analyst_investigation_max(self) -> None:
        """Analyst investigation is the one `max` default (hardest shaping)."""
        assert effort_for("analyst", "investigation") == "max"

    def test_ops_docs_lower(self) -> None:
        """Ops is lower-tier across its non-n/a columns."""
        assert effort_for("ops", "docs") == "lower"

    def test_flex_any_task_type(self) -> None:
        """Flex is the union-row — accepts every task type."""
        assert effort_for("flex", "investigation") == "xhigh"
        assert effort_for("flex", "implementation") == "xhigh"
        assert effort_for("flex", "refactor") == "xhigh"
        assert effort_for("flex", "fix") == "xhigh"
        assert effort_for("flex", "docs") == "lower"

    def test_returns_string_from_valid_tiers(self) -> None:
        """Every non-n/a cell must be one of the declared tier literals."""
        for archetype, row in POLICY_TABLE.items():
            for task_type, tier in row.items():
                assert tier in VALID_TIERS, (
                    f"POLICY_TABLE[{archetype!r}][{task_type!r}] = {tier!r} "
                    f"not in VALID_TIERS={VALID_TIERS!r}"
                )


class TestEffortForRaises:
    """Verify `effort_for` raises on `n/a` cells and unknown inputs."""

    def test_author_investigation_raises_na(self) -> None:
        """Authors do not do investigation work — `n/a` cell raises."""
        with pytest.raises(ValueError, match="n/a"):
            effort_for("author", "investigation")

    def test_orchestrator_implementation_raises_na(self) -> None:
        """Orchestrator does not do implementation — `n/a` cell raises."""
        with pytest.raises(ValueError, match="n/a"):
            effort_for("orchestrator", "implementation")

    def test_review_fix_raises_na(self) -> None:
        """Review lane does not ship fixes — `n/a` cell raises."""
        with pytest.raises(ValueError, match="n/a"):
            effort_for("review", "fix")

    def test_unknown_archetype_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown archetype"):
            effort_for("wizard", "investigation")

    def test_unknown_task_type_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown task_type"):
            effort_for("author", "ponder")


class TestEffortForPurity:
    """Verify `effort_for` is pure: no state, no I/O, no side effects."""

    def test_repeated_calls_return_same_result(self) -> None:
        for _ in range(5):
            assert effort_for("author", "fix") == "xhigh"
            assert effort_for("ops", "investigation") == "lower"

    def test_table_not_mutated_by_calls(self) -> None:
        """Calling `effort_for` must not mutate `POLICY_TABLE`."""
        before = {k: dict(v) for k, v in POLICY_TABLE.items()}
        effort_for("flex", "implementation")
        effort_for("analyst", "docs")
        with pytest.raises(ValueError):
            effort_for("author", "investigation")
        after = {k: dict(v) for k, v in POLICY_TABLE.items()}
        assert before == after


# --- Markdown table drift guard --------------------------------------------

_TABLE_HEADER_RE = re.compile(
    r"^\|\s*Archetype\s*\|\s*task_type=investigation\s*\|"
    r"\s*task_type=implementation\s*\|\s*task_type=refactor\s*\|"
    r"\s*task_type=fix\s*\|\s*task_type=docs\s*\|",
)


def _parse_markdown_table(text: str) -> dict[str, dict[str, str]]:
    """Parse the 7-row × 5-col policy table from the markdown file.

    Returns a dict shaped like `POLICY_TABLE`. Skips the header and
    separator rows; stops at the first non-pipe line after the table body.
    """
    lines = text.splitlines()
    # Locate the header row.
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if _TABLE_HEADER_RE.match(line):
            header_idx = i
            break
    assert (
        header_idx is not None
    ), f"policy table header not found in {EFFORT_POLICY_MD}"
    # Data rows start 2 lines after the header (skip separator `|---|...`).
    data_start = header_idx + 2
    result: dict[str, dict[str, str]] = {}
    task_types = ("investigation", "implementation", "refactor", "fix", "docs")
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 6:
            continue
        archetype = cells[0]
        row = {task_types[i]: cells[i + 1] for i in range(5)}
        result[archetype] = row
    return result


class TestMarkdownDriftGuard:
    """Verify `.claude/rules/effort_policy.md` table matches `POLICY_TABLE` 1:1."""

    def test_markdown_file_exists(self) -> None:
        assert (
            EFFORT_POLICY_MD.is_file()
        ), f"expected effort policy at {EFFORT_POLICY_MD}"

    def test_markdown_version_matches(self) -> None:
        text = EFFORT_POLICY_MD.read_text()
        # Version appears as a backticked token under `## Version`.
        assert (
            f"`{POLICY_VERSION}`" in text
        ), f"POLICY_VERSION={POLICY_VERSION!r} not cited in {EFFORT_POLICY_MD}"

    def test_markdown_table_matches_policy_table(self) -> None:
        text = EFFORT_POLICY_MD.read_text()
        parsed = _parse_markdown_table(text)
        assert parsed == POLICY_TABLE, (
            "POLICY_TABLE in effort_policy.py drifted from the markdown "
            "table. Update both files together."
        )

    def test_markdown_table_has_all_archetypes(self) -> None:
        text = EFFORT_POLICY_MD.read_text()
        parsed = _parse_markdown_table(text)
        assert set(parsed.keys()) == set(POLICY_TABLE.keys())
        # Exactly 7 rows — shaping §7 specifies the 7-archetype matrix.
        assert len(parsed) == 7


# --- Enum extension (§7.5) -------------------------------------------------


class TestEnumExtension:
    """Verify `max` was added to `VALID_EFFORT_HINTS` per shaping §7.5."""

    def test_max_in_valid_effort_hints(self) -> None:
        from bid_euchre.ops.task_queue import VALID_EFFORT_HINTS

        assert "max" in VALID_EFFORT_HINTS

    def test_all_original_values_preserved(self) -> None:
        """Existing enum values must still be accepted (backward compat)."""
        from bid_euchre.ops.task_queue import VALID_EFFORT_HINTS

        assert {"low", "medium", "high"}.issubset(VALID_EFFORT_HINTS)
