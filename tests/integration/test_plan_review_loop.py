"""Integration tests for plan review loop -- end-to-end with mocked Codex CLI.

Tests the full loop including real tier detection, real state key computation,
and real state persistence. Codex CLI invocation is mocked at the adapter
boundary since it requires a live git repo with a temp index.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts/internal to path
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from codex_plan_review_adapter import (
    PlanReviewFinding,
    PlanReviewResult,
    detect_plan_tier,
    plan_state_key,
)
from plan_review_driver import run_plan_review_loop
from review_state import load_plan_review_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clean_result(tier: str = "small") -> PlanReviewResult:
    """Create a clean (no findings) PlanReviewResult."""
    return PlanReviewResult(
        success=True,
        findings=[],
        tier=tier,
        reviewer="codex_cli",
        raw_output="No issues found.",
        latency_seconds=0.1,
    )


def _make_findings_result(
    findings: list[PlanReviewFinding], tier: str = "small"
) -> PlanReviewResult:
    """Create a PlanReviewResult with findings."""
    return PlanReviewResult(
        success=True,
        findings=findings,
        tier=tier,
        reviewer="codex_cli",
        raw_output="[P1] test:1 -- finding",
        latency_seconds=0.1,
    )


def _make_failed_result(
    error: str = "Codex not found", tier: str = "small"
) -> PlanReviewResult:
    """Create a failed PlanReviewResult."""
    return PlanReviewResult(
        success=False,
        findings=[],
        tier=tier,
        reviewer="codex_cli",
        raw_output="",
        latency_seconds=0.1,
        error=error,
    )


def _make_finding(
    severity: str = "WARNING",
    description: str = "test finding",
    check_id: str = "P1",
) -> PlanReviewFinding:
    """Create a PlanReviewFinding."""
    return PlanReviewFinding(
        severity=severity,
        category="convention",
        file="plans/test.md",
        line=1,
        description=description,
        check_id=check_id,
        source="codex_cli",
    )


def _make_sample_plan(
    plan_path: Path,
    *,
    lines: int = 30,
    files_ref: int = 2,
    research: bool = False,
    tier_override: str | None = None,
) -> Path:
    """Create a sample plan file with controllable properties.

    Args:
        plan_path: Full path where the plan should be written.
        lines: Approximate number of lines in the plan.
        files_ref: Number of backtick-quoted file references to include.
        research: If True, add research signals (## Hypotheses).
        tier_override: If set, add a frontmatter tier override comment.

    Returns:
        Path to the created plan file.
    """
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []

    if tier_override:
        parts.append(f"<!-- review-tier: {tier_override} -->")

    parts.append("# Test Plan")
    parts.append("")
    parts.append("## Goal")
    parts.append("Test the plan review system.")
    parts.append("")

    if research:
        parts.append("## Hypotheses")
        parts.append("")
        parts.append("H1: Model capacity matters more than label quality.")
        parts.append("")

    # Add file references
    if files_ref > 0:
        parts.append("## Files")
        for i in range(files_ref):
            parts.append(f"- `src/module_{i}.py`")
        parts.append("")

    parts.append("## Steps")
    parts.append("")
    parts.append("1. Implement the feature.")
    parts.append("2. Run tests.")
    parts.append("")

    # Pad to reach desired line count
    current_lines = len(parts)
    if lines > current_lines:
        parts.append("## Details")
        parts.append("")
        for i in range(lines - current_lines - 2):
            parts.append(f"Detail line {i + 1}.")

    content = "\n".join(parts) + "\n"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


# ---------------------------------------------------------------------------
# Tier detection integration
# ---------------------------------------------------------------------------


class TestTierDetectionIntegration:
    """Integration tests for tier detection with realistic plan structures."""

    def test_small_plan_detected(self, tmp_path: Path) -> None:
        """Short session plan -> small tier."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md", lines=30)
        assert detect_plan_tier(plan) == "small"

    def test_medium_plan_detected(self, tmp_path: Path) -> None:
        """100-line plan with 5 file refs -> medium tier."""
        plan = _make_sample_plan(
            tmp_path / "plans" / "sessions" / "test.md",
            lines=100,
            files_ref=5,
        )
        assert detect_plan_tier(plan) == "medium"

    def test_governing_override(self, tmp_path: Path) -> None:
        """Frontmatter override -> governing regardless of content."""
        plan = _make_sample_plan(
            tmp_path / "plans" / "sessions" / "test.md",
            lines=20,
            tier_override="governing",
        )
        assert detect_plan_tier(plan) == "governing"

    def test_large_tooling_stays_medium(self, tmp_path: Path) -> None:
        """350-line plan without research signals -> medium (not governing)."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md", lines=350)
        assert detect_plan_tier(plan) == "medium"

    def test_large_research_escalates(self, tmp_path: Path) -> None:
        """350-line plan with ## Hypotheses -> governing."""
        plan = _make_sample_plan(
            tmp_path / "plans" / "sessions" / "test.md",
            lines=350,
            research=True,
        )
        assert detect_plan_tier(plan) == "governing"

    def test_initiative_path_governing(self, tmp_path: Path) -> None:
        """plans/arc_d_v2/foo.md -> governing."""
        plan = _make_sample_plan(tmp_path / "plans" / "arc_d_v2" / "test.md", lines=30)
        assert detect_plan_tier(plan) == "governing"


# ---------------------------------------------------------------------------
# Plan review loop integration -- real tier detection + real state
# ---------------------------------------------------------------------------


class TestPlanReviewLoopIntegration:
    """Integration tests for the full plan review loop.

    These use real tier detection and state persistence, mocking only the
    Codex CLI invocation boundary (invoke_codex_plan_review).
    """

    def test_clean_review_completes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clean Codex review -> READY in 1 iteration."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_clean_result(),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state")

        assert result.verdict == "READY"
        assert result.iterations == 1
        assert result.total_findings == 0

    def test_findings_trigger_stop_without_fix_cmd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex finds issues but no CLAUDE_FIX_CMD -> stops after 1 iteration."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md")
        finding = _make_finding(description="Missing seed in command")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_findings_result([finding]),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )
        # Ensure CLAUDE_FIX_CMD is not set
        monkeypatch.delenv("CLAUDE_FIX_CMD", raising=False)

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state", max_iter=5)

        assert result.verdict in ("NEEDS_ATTENTION", "NOT_READY")
        assert result.iterations == 1
        assert result.total_findings >= 1

    def test_codex_failure_triggers_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex CLI failure -> Claude fallback used."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_failed_result("Codex not found"),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )
        # Mock the fallback issue creation to avoid subprocess calls
        monkeypatch.setattr(
            "plan_review_driver._create_fallback_issue",
            lambda *a, **kw: "https://github.com/test/repo/issues/99",
        )

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state")

        assert result.fallback_used is True
        assert result.reviewer == "claude_failsafe"
        assert result.fallback_issue_url == "https://github.com/test/repo/issues/99"

    def test_sidecar_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Review sidecar file is written to state dir."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_clean_result(),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state")

        assert result.sidecar_path is not None
        sidecar = Path(result.sidecar_path)
        assert sidecar.exists()
        content = sidecar.read_text()
        assert "# Plan Review:" in content
        assert "READY" in content

    def test_state_persisted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is saved to disk after loop completes."""
        plan = _make_sample_plan(tmp_path / "plans" / "sessions" / "test.md")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_clean_result(),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )

        run_plan_review_loop(plan, base_dir=tmp_path / "state")

        key = plan_state_key(plan)
        state = load_plan_review_state(key, base=tmp_path / "state")
        assert state is not None
        assert state.current_state.value in (
            "review_complete",
            "review_complete_with_issues",
        )

    def test_tier_auto_detected_for_medium(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """100-line plan -> medium tier is auto-detected and used."""
        plan = _make_sample_plan(
            tmp_path / "plans" / "sessions" / "test.md",
            lines=100,
            files_ref=5,
        )

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_clean_result("medium"),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state")

        assert result.tier == "medium"
        assert result.verdict == "READY"

    def test_tier_auto_detected_for_governing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Initiative-path plan -> governing tier is auto-detected."""
        plan = _make_sample_plan(tmp_path / "plans" / "arc_d_v2" / "test.md", lines=30)

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_clean_result("governing"),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_clean_result(),
        )

        result = run_plan_review_loop(plan, base_dir=tmp_path / "state")

        assert result.tier == "governing"
        assert result.verdict == "READY"


# ---------------------------------------------------------------------------
# State key collision
# ---------------------------------------------------------------------------


class TestStateKeyCollision:
    """Test that state keys are unique across different plan paths."""

    def test_different_initiatives_different_keys(self, tmp_path: Path) -> None:
        """Same basename in different dirs -> different state keys."""
        p1 = tmp_path / "plans" / "arc_d_v2" / "amendments.md"
        p2 = tmp_path / "plans" / "browser_game" / "amendments.md"
        p1.parent.mkdir(parents=True)
        p2.parent.mkdir(parents=True)
        p1.write_text("# Amendments A")
        p2.write_text("# Amendments B")
        assert plan_state_key(p1) != plan_state_key(p2)


# --- Failure Scenario Tests ---

from unittest.mock import patch


class TestBothReviewersFail:
    """Test behavior when both Codex and Claude failsafe fail."""

    @patch("plan_review_driver._create_fallback_issue", return_value=None)
    @patch(
        "plan_review_driver.invoke_claude_failsafe",
        return_value=PlanReviewResult(
            success=False,
            findings=[],
            tier="small",
            reviewer="claude_failsafe",
            raw_output="",
            latency_seconds=1.0,
            error="No command available",
        ),
    )
    @patch(
        "plan_review_driver.invoke_codex_plan_review",
        return_value=PlanReviewResult(
            success=False,
            findings=[],
            tier="small",
            reviewer="codex_cli",
            raw_output="",
            latency_seconds=300.0,
            error="Timeout after 600s",
        ),
    )
    def test_synthetic_critical_injected(
        self, mock_codex, mock_claude, mock_issue, tmp_path: Path
    ) -> None:
        """When both fail, a synthetic CRITICAL finding is injected."""
        plan = tmp_path / "test.md"
        plan.write_text("<!-- review-tier: small -->\n# Plan\n")
        result = run_plan_review_loop(plan, base_dir=tmp_path)
        assert result.verdict == "NOT_READY"
        assert result.total_findings == 1
        finding = result.findings[0]
        sev = finding.severity if hasattr(finding, "severity") else finding["severity"]
        desc = (
            finding.description
            if hasattr(finding, "description")
            else finding["description"]
        )
        assert sev == "CRITICAL"
        assert "both Codex CLI and Claude fallback failed" in desc

    @patch("plan_review_driver._create_fallback_issue", return_value=None)
    @patch(
        "plan_review_driver.invoke_claude_failsafe",
        return_value=PlanReviewResult(
            success=False,
            findings=[],
            tier="small",
            reviewer="claude_failsafe",
            raw_output="",
            latency_seconds=1.0,
            error="Timed out",
        ),
    )
    @patch(
        "plan_review_driver.invoke_codex_plan_review",
        return_value=PlanReviewResult(
            success=False,
            findings=[],
            tier="small",
            reviewer="codex_cli",
            raw_output="",
            latency_seconds=600.0,
            error="Timeout after 600s",
        ),
    )
    def test_state_records_stop_reason(
        self, mock_codex, mock_claude, mock_issue, tmp_path: Path
    ) -> None:
        """State file records correct stop reason when both fail."""
        plan = tmp_path / "test.md"
        plan.write_text("<!-- review-tier: small -->\n# Plan\n")
        run_plan_review_loop(plan, base_dir=tmp_path)
        state = load_plan_review_state(plan_state_key(plan), tmp_path)
        assert state is not None
        assert (
            "both unavailable" in state.stop_reason.lower()
            or "fallback" in state.stop_reason.lower()
        )


class TestUnparseableOutput:
    """Test behavior when Codex returns unparseable output."""

    @patch("plan_review_driver._create_fallback_issue", return_value=None)
    @patch(
        "plan_review_driver.invoke_claude_failsafe",
        return_value=PlanReviewResult(
            success=True,
            findings=[
                PlanReviewFinding(
                    severity="INFO",
                    category="convention",
                    file="test.md",
                    line=1,
                    description="Fallback found an issue",
                    check_id=None,
                ),
            ],
            tier="small",
            reviewer="claude_failsafe",
            raw_output="[{}]",
            latency_seconds=5.0,
        ),
    )
    @patch(
        "plan_review_driver.invoke_codex_plan_review",
        return_value=PlanReviewResult(
            success=False,
            findings=[],
            tier="small",
            reviewer="codex_cli",
            raw_output="gibberish output",
            latency_seconds=100.0,
            error="Unparseable output: no findings matched",
        ),
    )
    def test_fallback_findings_used(
        self, mock_codex, mock_claude, mock_issue, tmp_path: Path
    ) -> None:
        """When Codex fails with unparseable output, Claude failsafe findings are used."""
        plan = tmp_path / "test.md"
        plan.write_text("<!-- review-tier: small -->\n# Plan\n")
        result = run_plan_review_loop(plan, base_dir=tmp_path)
        assert result.fallback_used is True
        assert result.total_findings == 1
        finding = result.findings[0]
        desc = (
            finding.description
            if hasattr(finding, "description")
            else finding["description"]
        )
        assert desc == "Fallback found an issue"
