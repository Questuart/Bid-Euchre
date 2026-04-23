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
    _vc_is_trigger_path,
    _vc_surface_exists,
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
