"""Unit tests for I10 idempotency-checklist precheck (Primitive H.0).

Covers the ``check_idempotency_checklist`` function wired into
``check_diff`` in ``scripts/internal/deterministic_prechecks.py``.

Severity: WARN (P2) in Phase 0; rows 1–4 tighten to BLOCK in Phase 1 per
`plans/steward_platform/8_primitive_H/shaping.md` §5.5.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from deterministic_prechecks import (  # noqa: E402
    _i10_matches,
    _i10_pr_body_has_idempotency_section,
    check_idempotency_checklist,
)

# ---------------------------------------------------------------------------
# Row-matching (surfaces from §Rows table in idempotency_checklist.md)
# ---------------------------------------------------------------------------


def test_row1_message_bus() -> None:
    matches = _i10_matches("src/bid_euchre/ops/message_bus.py")
    assert (1, "message send") in matches


def test_row2_task_queue() -> None:
    matches = _i10_matches("src/bid_euchre/ops/task_queue.py")
    assert (2, "task status update") in matches


def test_row3_events() -> None:
    matches = _i10_matches("src/bid_euchre/ops/events.py")
    assert (3, "event emission") in matches


def test_row4_state_files_runtime_json() -> None:
    matches = _i10_matches(".claude/runtime/canary_state/dogfood_v1.json")
    assert any(r[0] == 4 for r in matches)


def test_row4_state_files_memory_md() -> None:
    matches = _i10_matches("MEMORY.md")
    assert any(r[0] == 4 for r in matches)


def test_row4_state_files_index_md() -> None:
    matches = _i10_matches("knowledge/INDEX.md")
    assert any(r[0] == 4 for r in matches)


def test_row5_hooks() -> None:
    matches = _i10_matches(".claude/hooks/material-platform-change-canary.sh")
    assert any(r[0] == 5 for r in matches)


def test_row6_loops() -> None:
    matches = _i10_matches(".claude/runtime/loops/orchestrator.json")
    # Both row 4 (state file write) and row 6 (cron/loop registration) match
    # — by surface overlap the idempotency audit requires both considerations.
    row_ids = {r[0] for r in matches}
    assert 6 in row_ids


def test_row7_kb_promotion() -> None:
    matches = _i10_matches("knowledge/_promoted/adr-010.md")
    assert any(r[0] == 7 for r in matches)


def test_no_match_for_unrelated_path() -> None:
    assert _i10_matches("src/bid_euchre/core/rules.py") == []
    assert _i10_matches("tests/unit/test_foo.py") == []
    assert _i10_matches("docs/01_core/RULES.md") == []


# ---------------------------------------------------------------------------
# PR-body section detection
# ---------------------------------------------------------------------------


def test_pr_body_has_idempotency_heading() -> None:
    assert _i10_pr_body_has_idempotency_section(
        "## Summary\n\n...\n\n## Idempotency\n\nrow 3 handled via dedup key"
    )


def test_pr_body_has_idempotency_at_level_3() -> None:
    assert _i10_pr_body_has_idempotency_section("### Idempotency\n...")


def test_pr_body_missing_idempotency() -> None:
    assert not _i10_pr_body_has_idempotency_section(
        "## Summary\n...\n## Verification Performed\n..."
    )


def test_pr_body_none_returns_false() -> None:
    assert not _i10_pr_body_has_idempotency_section(None)


def test_pr_body_empty_returns_false() -> None:
    assert not _i10_pr_body_has_idempotency_section("")


# ---------------------------------------------------------------------------
# End-to-end: check_idempotency_checklist
# ---------------------------------------------------------------------------


def test_no_trigger_no_findings() -> None:
    findings = check_idempotency_checklist(
        ["src/bid_euchre/core/rules.py", "tests/unit/test_foo.py"],
        pr_body="## Summary\n...",
    )
    assert findings == []


def test_trigger_with_section_no_findings() -> None:
    findings = check_idempotency_checklist(
        ["src/bid_euchre/ops/events.py"],
        pr_body="## Summary\n...\n## Idempotency\n\nrow 3 handled\n",
    )
    assert findings == []


def test_trigger_without_section_emits_warn() -> None:
    findings = check_idempotency_checklist(
        ["src/bid_euchre/ops/events.py"],
        pr_body="## Summary\n...",
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "P2"  # WARN
    assert f.check_id == "I10"
    assert f.file == "src/bid_euchre/ops/events.py"
    assert "row 3" in f.message.lower()


def test_trigger_without_pr_body_emits_warn() -> None:
    findings = check_idempotency_checklist(
        [".claude/hooks/some-hook.sh"],
        pr_body=None,
    )
    assert len(findings) == 1
    assert findings[0].severity == "P2"
    assert findings[0].check_id == "I10"


def test_multiple_triggers_deduped_by_path_row() -> None:
    findings = check_idempotency_checklist(
        [
            "src/bid_euchre/ops/events.py",
            "src/bid_euchre/ops/task_queue.py",
            ".claude/hooks/a.sh",
            ".claude/hooks/b.sh",
        ],
        pr_body="## Summary\n...",
    )
    # 4 distinct (path, row) pairs
    check_ids = {(f.file, f.check_id) for f in findings}
    assert len(check_ids) == 4
    for f in findings:
        assert f.check_id == "I10"
        assert f.severity == "P2"


def test_severity_never_p0() -> None:
    """Phase 0 is WARN-only. Phase 1 kickoff separately promotes rows 1-4."""
    findings = check_idempotency_checklist(
        [
            "src/bid_euchre/ops/message_bus.py",
            "src/bid_euchre/ops/task_queue.py",
            "src/bid_euchre/ops/events.py",
            ".claude/runtime/state.json",
        ],
        pr_body=None,
    )
    for f in findings:
        assert f.severity == "P2", (
            f"Phase 0 I10 severity must be P2/WARN (got {f.severity}). "
            "Phase 1 kickoff promotes rows 1-4 to P0/BLOCK — that change "
            "must be a separate commit/PR."
        )
