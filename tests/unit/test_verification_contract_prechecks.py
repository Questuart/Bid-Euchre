"""Unit tests for V1–V6 verification-contract prechecks (Pattern 10).

Covers the ``check_verification_contract`` function wired into
``check_diff`` in ``scripts/internal/deterministic_prechecks.py``.

Pattern 10 — see ``plans/steward_platform/governing_plan.md`` §10.9 and
``plans/steward_platform/verification_contract/shaping.md`` §3.3–§3.4.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from deterministic_prechecks import (  # noqa: E402
    _should_run_path_existence_check,
    _vc_is_trigger_path,
    _vc_surface_exists,
    check_diff,
    check_verification_contract,
)

# ---------------------------------------------------------------------------
# Trigger-path detection (§3.3)
# ---------------------------------------------------------------------------


def test_trigger_path_src() -> None:
    assert _vc_is_trigger_path("src/bid_euchre/foo.py")
    assert _vc_is_trigger_path("src/bid_euchre/ops/events.py")


def test_trigger_path_scripts_internal() -> None:
    assert _vc_is_trigger_path("scripts/internal/verify_map_coverage.py")


def test_trigger_path_claude_hooks() -> None:
    assert _vc_is_trigger_path(".claude/hooks/post-merge-notify.sh")


def test_trigger_path_claude_skills() -> None:
    assert _vc_is_trigger_path(".claude/skills/run-canary/SKILL.md")


def test_trigger_path_plans_template() -> None:
    assert _vc_is_trigger_path("plans/_templates/sub_plan.md")


def test_trigger_path_governing_plan() -> None:
    assert _vc_is_trigger_path("plans/steward_platform/governing_plan.md")


def test_trigger_path_plan_md_add_section() -> None:
    assert _vc_is_trigger_path(
        "plans/steward_platform/verification_contract/sub_plan.md"
    )


def test_trigger_path_adrs() -> None:
    assert _vc_is_trigger_path(
        "plans/steward_platform/adrs/005_official_code_review_plugin.md"
    )
    assert _vc_is_trigger_path("knowledge/adr/010_memory_service.md")


def test_trigger_path_settings_and_prompt_policy() -> None:
    assert _vc_is_trigger_path(".claude/settings.json")
    assert _vc_is_trigger_path(".claude/rules/prompt_policy/author.md")


def test_non_trigger_paths() -> None:
    assert not _vc_is_trigger_path("README.md")
    assert not _vc_is_trigger_path("docs/01_core/RULES.md")
    assert not _vc_is_trigger_path("tests/unit/test_x.py")
    assert not _vc_is_trigger_path("data/runs/run_123/foo.json")


# ---------------------------------------------------------------------------
# Surface-existence (V3 helper)
# ---------------------------------------------------------------------------


def test_surface_exists_for_real_path(tmp_path: Path) -> None:
    p = tmp_path / "tests" / "unit" / "test_foo.py"
    p.parent.mkdir(parents=True)
    p.write_text("# fixture\n")
    assert _vc_surface_exists("tests/unit/test_foo.py", tmp_path)
    # path::node form strips the node suffix for existence check
    assert _vc_surface_exists("tests/unit/test_foo.py::test_bar", tmp_path)


def test_surface_missing_path_fails(tmp_path: Path) -> None:
    assert not _vc_surface_exists("tests/unit/nope.py", tmp_path)


def test_surface_non_path_keyword_accepted(tmp_path: Path) -> None:
    # Command-form surfaces don't need a path; Pattern 10 is lenient-form.
    assert _vc_surface_exists("make check-gated", tmp_path)
    assert _vc_surface_exists("uv run python foo.py", tmp_path)
    assert _vc_surface_exists("canary-dashboard", tmp_path)


def test_surface_empty_fails(tmp_path: Path) -> None:
    assert not _vc_surface_exists("", tmp_path)
    assert not _vc_surface_exists("   ", tmp_path)


# ---------------------------------------------------------------------------
# V2 — BLOCK when footer + PR-body are both missing
# ---------------------------------------------------------------------------


def test_v2_blocks_when_no_footer_and_no_pr_body(tmp_path: Path) -> None:
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=["feat: add foo\n\nSome body text."],
        pr_body="## Summary\nAdds foo.\n",
    )
    v2 = [f for f in findings if f.check_id == "V2"]
    assert v2, "expected V2 BLOCK finding"
    assert all(f.severity == "P0" for f in v2)


def test_v2_silent_with_commit_footer(tmp_path: Path) -> None:
    p = tmp_path / "tests" / "unit" / "test_foo.py"
    p.parent.mkdir(parents=True)
    p.write_text("# fixture\n")
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=["feat: add foo\n\nVerification: tests/unit/test_foo.py\n"],
        pr_body="## Summary\n",
    )
    assert not any(f.check_id == "V2" for f in findings)


def test_v2_silent_with_pr_body_section(tmp_path: Path) -> None:
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=["feat: add foo\n"],
        pr_body=(
            "## Summary\n\n## Verification Performed\n\n"
            "`tests/unit/test_foo.py` passes.\n"
        ),
    )
    assert not any(f.check_id == "V2" for f in findings)


def test_v2_footer_accepted_on_any_commit_in_range(tmp_path: Path) -> None:
    """Per §13.2 risk #3: footer on ANY commit satisfies V2."""
    p = tmp_path / "tests" / "unit" / "test_foo.py"
    p.parent.mkdir(parents=True)
    p.write_text("# fixture\n")
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=[
            "feat: add foo\n",  # no footer on introducing commit
            "chore: address review\n\nVerification: tests/unit/test_foo.py\n",
        ],
        pr_body="## Summary\n",
    )
    assert not any(f.check_id == "V2" for f in findings)


def test_v2_fallback_warn_when_no_commit_messages(tmp_path: Path) -> None:
    """No commit_messages supplied → WARN, not BLOCK."""
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed, tmp_path, commit_messages=None, pr_body=None
    )
    v2 = [f for f in findings if f.check_id == "V2"]
    assert v2
    assert all(f.severity == "P2" for f in v2)


# ---------------------------------------------------------------------------
# V3 — surface must exist (strict-existence)
# ---------------------------------------------------------------------------


def test_v3_blocks_when_named_surface_missing(tmp_path: Path) -> None:
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=["feat: add foo\n\nVerification: tests/unit/nope.py\n"],
    )
    v3 = [f for f in findings if f.check_id == "V3"]
    assert v3
    assert all(f.severity == "P0" for f in v3)


def test_v3_silent_when_surface_exists(tmp_path: Path) -> None:
    p = tmp_path / "tests" / "unit" / "test_foo.py"
    p.parent.mkdir(parents=True)
    p.write_text("# fixture\n")
    findings = check_verification_contract(
        ["src/bid_euchre/foo.py"],
        tmp_path,
        commit_messages=["feat: add foo\n\nVerification: tests/unit/test_foo.py\n"],
    )
    assert not any(f.check_id == "V3" for f in findings)


# ---------------------------------------------------------------------------
# V5 — INFO-ish: PR-body section present, no commit footer
# ---------------------------------------------------------------------------


def test_v5_info_when_pr_body_only(tmp_path: Path) -> None:
    changed = ["src/bid_euchre/foo.py"]
    findings = check_verification_contract(
        changed,
        tmp_path,
        commit_messages=["feat: add foo\n"],  # no footer
        pr_body=(
            "## Summary\n\n## Verification Performed\n\n"
            "`tests/unit/test_foo.py` passes.\n"
        ),
    )
    v5 = [f for f in findings if f.check_id == "V5"]
    assert v5
    # V5 is recorded with WARN severity (P2) but described as INFO per §3.4.
    assert all(f.severity == "P2" for f in v5)


# ---------------------------------------------------------------------------
# V4 — WARN: hook change names "operator review" as surface
# ---------------------------------------------------------------------------


def test_v4_warns_on_hook_operator_review(tmp_path: Path) -> None:
    findings = check_verification_contract(
        [".claude/hooks/new-hook.sh"],
        tmp_path,
        commit_messages=["feat: add new hook\n\nVerification: operator review\n"],
    )
    v4 = [f for f in findings if f.check_id == "V4"]
    assert v4
    assert all(f.severity == "P2" for f in v4)


def test_v4_silent_when_hook_has_rollback_test(tmp_path: Path) -> None:
    findings = check_verification_contract(
        [".claude/hooks/new-hook.sh"],
        tmp_path,
        commit_messages=[
            "feat: add new hook\n\nVerification: operator review + rollback test in tests/integration/\n"
        ],
    )
    assert not any(f.check_id == "V4" for f in findings)


# ---------------------------------------------------------------------------
# V6 — WARN: plan file changed but map.md has no row for its §N.M sections
# ---------------------------------------------------------------------------


def test_v6_warns_when_map_has_no_row_for_plan_sections(tmp_path: Path) -> None:
    plan_path = tmp_path / "plans" / "some_plan.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("## §5.3 Primitive X\n\n### Work\n- ship `src/foo.py`\n")
    # Create empty map.md — no rows.
    map_path = (
        tmp_path / "plans" / "steward_platform" / "verification_contract" / "map.md"
    )
    map_path.parent.mkdir(parents=True)
    map_path.write_text("# map\n")
    findings = check_verification_contract(
        ["plans/some_plan.md"],
        tmp_path,
        commit_messages=["docs: update plan\n\nVerification: plans/some_plan.md\n"],
    )
    v6 = [f for f in findings if f.check_id == "V6"]
    assert v6
    assert all(f.severity == "P2" for f in v6)


def test_v6_silent_when_map_has_matching_row(tmp_path: Path) -> None:
    plan_path = tmp_path / "plans" / "some_plan.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("## §5.3 Primitive X\n\n### Work\n- ship `src/foo.py`\n")
    map_path = (
        tmp_path / "plans" / "steward_platform" / "verification_contract" / "map.md"
    )
    map_path.parent.mkdir(parents=True)
    map_path.write_text(
        "| Deliverable | Class | Surface | Owner | Acceptance |\n"
        "|---|---|---|---|---|\n"
        "| §5.3 src/foo.py | new module | tests/unit/test_foo.py | author | pytest |\n"
    )
    findings = check_verification_contract(
        ["plans/some_plan.md"],
        tmp_path,
        commit_messages=["docs: update plan\n\nVerification: plans/some_plan.md\n"],
    )
    assert not any(f.check_id == "V6" for f in findings)


# ---------------------------------------------------------------------------
# No-trigger: completely non-triggering changes emit nothing.
# ---------------------------------------------------------------------------


def test_no_triggers_emits_no_findings(tmp_path: Path) -> None:
    findings = check_verification_contract(
        ["docs/01_core/RULES.md", "README.md"],
        tmp_path,
        commit_messages=["docs: fix typo\n"],
        pr_body="",
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Path-existence check exclusion (issue #2761)
#
# Governance plan markdown PRs triggered 20–130 false-positive findings
# from the plan-audit path-existence check treating prose path mentions
# (e.g. ``task_queue.py`` inside a sentence) as asserted repo-root paths.
# The exclusion skips the check when the diff touches only plans/**/*.md
# while mixed/code diffs still run it.
# ---------------------------------------------------------------------------


def test_gate_plans_markdown_only_returns_false() -> None:
    """All-plan-markdown diffs skip the path-existence check."""
    assert not _should_run_path_existence_check(
        [
            "plans/steward_platform/governing_plan.md",
            "plans/steward_platform/draft7_review_analyst-d.md",
            "plans/sessions/2026-04-23_foo.md",
        ]
    )


def test_gate_mixed_pr_returns_true() -> None:
    """Plan markdown + any non-plan file → run the check."""
    assert _should_run_path_existence_check(
        ["plans/steward_platform/governing_plan.md", "src/bid_euchre/foo.py"]
    )


def test_gate_code_only_returns_true() -> None:
    """Pure code diffs still run the check."""
    assert _should_run_path_existence_check(
        ["src/bid_euchre/core/rules.py", "tests/unit/test_rules.py"]
    )


def test_gate_plans_non_markdown_returns_true() -> None:
    """plans/**/*.yaml or plans/**/*.json still run the check."""
    assert _should_run_path_existence_check(["plans/browser_game/config.yaml"])


def test_gate_non_plans_markdown_returns_true() -> None:
    """docs/ or README markdown still run the check."""
    assert _should_run_path_existence_check(["README.md", "docs/01_core/RULES.md"])


def test_gate_empty_diff_returns_true() -> None:
    """Empty diff → run the check (safe default)."""
    assert _should_run_path_existence_check([])


def test_plan_markdown_only_pr_skips_path_check(tmp_path: Path) -> None:
    """Plans-only PR produces the PX skip marker and zero path-existence findings."""
    plan = tmp_path / "plans" / "foo.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        "# Plan\n\n"
        "See `scripts/internal/missing_script.py` for implementation.\n"
        "Edit `src/bid_euchre/nonexistent_module.py` and update `ops/dashboard.py`.\n"
    )
    findings = check_diff(
        changed_files=["plans/foo.md"],
        mode="plan-audit",
        repo_root=tmp_path,
        commit_messages=["docs: plan\n\nVerification: plans/foo.md\n"],
        pr_body="## Summary\n",
    )
    px_markers = [f for f in findings if f.check_id == "PX"]
    assert len(px_markers) == 1, f"expected 1 PX marker, got {len(px_markers)}"
    assert px_markers[0].severity == "P2"
    assert "plans/**/*.md" in px_markers[0].message
    path_findings = [
        f for f in findings if f.message.startswith("Referenced path does not exist")
    ]
    assert (
        path_findings == []
    ), f"expected 0 path-existence findings on plans-only PR, got {len(path_findings)}"


def test_mixed_pr_runs_path_check(tmp_path: Path) -> None:
    """Mixed plans + code PR runs the path-existence check and emits findings."""
    plan = tmp_path / "plans" / "foo.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n\nReferences `tests/unit/nope.py` which is missing.\n")
    code = tmp_path / "src" / "bid_euchre" / "bar.py"
    code.parent.mkdir(parents=True)
    code.write_text("# stub\n")
    findings = check_diff(
        changed_files=["plans/foo.md", "src/bid_euchre/bar.py"],
        mode="plan-audit",
        repo_root=tmp_path,
        commit_messages=["feat: bar\n\nVerification: tests/unit/test_bar.py\n"],
        pr_body="## Summary\n",
    )
    # No PX skip marker when the gate says run.
    assert not any(f.check_id == "PX" for f in findings)
    # Path-existence check did run — flags the missing tests/unit/nope.py.
    path_findings = [
        f for f in findings if f.message.startswith("Referenced path does not exist")
    ]
    assert path_findings, "expected path-existence findings on mixed PR"


def test_code_only_pr_runs_path_check(tmp_path: Path) -> None:
    """Code-only PR in plan-audit mode — gate is True (check would run)."""
    # No plans/*.md in the diff, so `_check_plan_paths` loops find nothing
    # to audit regardless; the important guarantee is that the gate doesn't
    # short-circuit and emit a skip marker.
    code = tmp_path / "src" / "bid_euchre" / "bar.py"
    code.parent.mkdir(parents=True)
    code.write_text("# stub\n")
    findings = check_diff(
        changed_files=["src/bid_euchre/bar.py"],
        mode="plan-audit",
        repo_root=tmp_path,
        commit_messages=["feat: bar\n\nVerification: tests/unit/test_bar.py\n"],
        pr_body="## Summary\n",
    )
    assert not any(f.check_id == "PX" for f in findings)


def test_plan_markdown_prose_references_not_flagged_after_exclusion() -> None:
    """Golden fixture: plans/steward_platform/draft7_review_analyst-d.md

    Before #2761 fix: the file triggered 132 path-existence findings from
    prose references.  After the exclusion: zero path-existence findings
    (plus one PX skip marker).  Regression-locks the fix against future
    code paths that might re-enable the check on plans-only diffs.
    """
    fixture = Path("plans/steward_platform/draft7_review_analyst-d.md")
    if not fixture.exists():  # pragma: no cover — guards local/CI symmetry
        import pytest

        pytest.skip(f"golden fixture not present: {fixture}")
    findings = check_diff(
        changed_files=[str(fixture)],
        mode="plan-audit",
        repo_root=Path("."),
        commit_messages=[f"docs: review\n\nVerification: {fixture}\n"],
        pr_body="## Summary\n",
    )
    path_findings = [
        f for f in findings if f.message.startswith("Referenced path does not exist")
    ]
    assert path_findings == [], (
        f"golden fixture regression: expected 0 path-existence findings "
        f"after #2761 exclusion, got {len(path_findings)}"
    )
    px_markers = [f for f in findings if f.check_id == "PX"]
    assert len(px_markers) == 1, f"expected exactly 1 PX marker, got {len(px_markers)}"
