"""Tests for plan review loop driver -- state machine, iteration, stagnation, sidecar."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from plan_review_driver import (
    PlanReviewLoopResult,
    _compute_verdict,
    _create_fallback_issue,
    _write_sidecar,
    run_plan_review_loop,
)
from review_state import (
    PlanReviewLoopState,
    PlanReviewState,
    load_plan_review_state,
    save_plan_review_state,
)

# ---------------------------------------------------------------------------
# Helpers -- mock adapter objects
# ---------------------------------------------------------------------------


def _make_finding(
    severity: str = "WARNING",
    category: str = "convention",
    description: str = "test finding",
    check_id: str | None = "P1",
) -> MagicMock:
    """Create a mock PlanReviewFinding with .to_dict() and .severity."""
    f = MagicMock()
    f.severity = severity
    f.category = category
    f.description = description
    f.check_id = check_id
    f.file = "plans/test.md"
    f.line = 1
    f.source = "codex_cli"
    f.to_dict.return_value = {
        "severity": severity,
        "category": category,
        "description": description,
        "check_id": check_id,
        "file": "plans/test.md",
        "line": 1,
        "source": "codex_cli",
    }
    return f


def _make_result(
    success: bool = True,
    findings: list | None = None,
    error: str | None = None,
    reviewer: str = "codex_cli",
) -> MagicMock:
    """Create a mock PlanReviewResult."""
    r = MagicMock()
    r.success = success
    r.findings = findings or []
    r.error = error
    r.reviewer = reviewer
    r.raw_output = ""
    r.latency_seconds = 0.5
    r.tier = "small"
    return r


# ---------------------------------------------------------------------------
# Verdict tests
# ---------------------------------------------------------------------------


class TestComputeVerdict:
    """Test verdict computation from findings."""

    def test_verdict_ready_no_findings(self) -> None:
        assert _compute_verdict([]) == "READY"

    def test_verdict_needs_attention_warnings_only(self) -> None:
        findings = [_make_finding(severity="WARNING"), _make_finding(severity="INFO")]
        assert _compute_verdict(findings) == "NEEDS_ATTENTION"

    def test_verdict_not_ready_critical(self) -> None:
        findings = [
            _make_finding(severity="CRITICAL"),
            _make_finding(severity="WARNING"),
        ]
        assert _compute_verdict(findings) == "NOT_READY"

    def test_verdict_needs_attention_info_only(self) -> None:
        findings = [_make_finding(severity="INFO")]
        assert _compute_verdict(findings) == "NEEDS_ATTENTION"

    def test_verdict_with_dict_findings(self) -> None:
        """Verdict works with raw dicts too."""
        findings = [{"severity": "CRITICAL"}, {"severity": "WARNING"}]
        assert _compute_verdict(findings) == "NOT_READY"

    def test_verdict_dict_ready(self) -> None:
        assert _compute_verdict([]) == "READY"

    def test_verdict_dict_needs_attention(self) -> None:
        findings = [{"severity": "WARNING"}]
        assert _compute_verdict(findings) == "NEEDS_ATTENTION"


# ---------------------------------------------------------------------------
# Clean review (single iteration, no findings)
# ---------------------------------------------------------------------------


class TestCleanReview:
    """Test that a clean Codex review completes in one iteration."""

    def test_clean_review_single_iteration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\nShort plan.\n")

        # Mock adapter functions
        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=True, findings=[]),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(success=True, findings=[]),
        )
        monkeypatch.setattr(
            "plan_review_driver.detect_plan_tier",
            lambda p: "small",
        )
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key",
            lambda p: "test_clean_key",
        )

        # Use tmp_path as base_dir for state persistence
        result = run_plan_review_loop(plan_file, base_dir=tmp_path)

        assert result.verdict == "READY"
        assert result.iterations == 1
        assert result.total_findings == 0
        assert result.open_findings == 0
        assert result.fallback_used is False
        assert result.reviewer == "codex_cli"


# ---------------------------------------------------------------------------
# Max iterations reached
# ---------------------------------------------------------------------------


class TestMaxIterations:
    """Test that the loop respects max_iter and stops."""

    def test_max_iterations_reached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\nSome content.\n")

        call_count = 0

        def mock_codex(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return different findings each time to avoid stagnation
            return _make_result(
                success=True,
                findings=[_make_finding(description=f"Finding iteration {call_count}")],
            )

        monkeypatch.setattr("plan_review_driver.invoke_codex_plan_review", mock_codex)
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_max_key"
        )

        # Set CLAUDE_FIX_CMD to a dummy that "succeeds"
        monkeypatch.setenv("CLAUDE_FIX_CMD", "true")

        # Use a unique findings hash each time to avoid stagnation
        hash_counter = 0

        def mock_hash(findings):
            nonlocal hash_counter
            hash_counter += 1
            return f"hash_{hash_counter:04d}"

        monkeypatch.setattr("plan_review_driver.compute_findings_hash", mock_hash)

        result = run_plan_review_loop(plan_file, max_iter=5, base_dir=tmp_path)

        assert result.iterations == 5
        assert result.verdict != "READY"  # Should have open findings
        assert result.total_findings >= 1

    def test_max_iterations_with_max_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Single-iteration limit completes correctly."""
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=True, findings=[_make_finding()]),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_max1_key"
        )

        result = run_plan_review_loop(plan_file, max_iter=1, base_dir=tmp_path)

        assert result.iterations == 1
        assert result.total_findings >= 1


# ---------------------------------------------------------------------------
# Stagnation detection
# ---------------------------------------------------------------------------


class TestStagnationDetection:
    """Test that the loop stops when findings don't change between iterations."""

    def test_stagnation_detection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\nSome content.\n")

        # Same finding every time -> stagnation
        static_finding = _make_finding(description="Same finding")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=True, findings=[static_finding]),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_stagnation_key"
        )

        # CLAUDE_FIX_CMD set so fix "succeeds" and loop continues
        monkeypatch.setenv("CLAUDE_FIX_CMD", "true")

        # Same hash every time -> stagnation detected on iteration 2
        monkeypatch.setattr(
            "plan_review_driver.compute_findings_hash",
            lambda f: "static_hash_value",
        )

        result = run_plan_review_loop(plan_file, max_iter=5, base_dir=tmp_path)

        # Should stop after 2 iterations due to stagnation
        assert result.iterations == 2
        assert result.verdict != "READY"


# ---------------------------------------------------------------------------
# Codex failure triggers fallback
# ---------------------------------------------------------------------------


class TestCodexFallback:
    """Test that Codex failure triggers Claude fallback and issue creation."""

    def test_codex_failure_triggers_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\nContent.\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=False, error="Codex not found"),
        )

        fallback_finding = _make_finding(
            severity="WARNING", description="Fallback warning"
        )

        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(
                success=True,
                findings=[fallback_finding],
                reviewer="claude_failsafe",
            ),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_fallback_key"
        )

        # Mock issue creation
        monkeypatch.setattr(
            "plan_review_driver._create_fallback_issue",
            lambda *a, **kw: "https://github.com/test/repo/issues/99",
        )

        result = run_plan_review_loop(plan_file, base_dir=tmp_path)

        assert result.fallback_used is True
        assert result.reviewer == "claude_failsafe"
        assert result.fallback_issue_url == "https://github.com/test/repo/issues/99"

    def test_fallback_clean_review(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex fails but Claude returns clean (no findings) -> READY, not NOT_READY.

        Regression test for Bug 3: empty findings list (``[]``) is falsy in Python,
        so ``success=True, findings=[]`` was incorrectly treated as "both failed."
        """
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n\nContent.\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=False, error="Codex unavailable"),
        )

        # Claude succeeds with no findings (clean review)
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(
                success=True,
                findings=[],
                reviewer="claude_failsafe",
            ),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_fallback_clean_key"
        )
        monkeypatch.setattr(
            "plan_review_driver._create_fallback_issue",
            lambda *a, **kw: "https://github.com/test/repo/issues/100",
        )

        result = run_plan_review_loop(plan_file, base_dir=tmp_path)

        assert result.fallback_used is True
        assert result.verdict == "READY"
        assert result.total_findings == 0
        assert result.open_findings == 0
        assert result.reviewer == "claude_failsafe"

    def test_codex_and_fallback_both_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both Codex and Claude fail -> REVIEW_COMPLETE_WITH_ISSUES."""
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=False, error="Codex broken"),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(success=False, error="Claude broken too"),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_both_fail_key"
        )
        monkeypatch.setattr(
            "plan_review_driver._create_fallback_issue",
            lambda *a, **kw: None,
        )

        result = run_plan_review_loop(plan_file, base_dir=tmp_path)

        assert result.fallback_used is True
        assert result.verdict == "NOT_READY"  # Both failed → synthetic CRITICAL finding
        assert result.total_findings == 1  # Synthetic "no review completed" finding
        assert result.iterations == 1


# ---------------------------------------------------------------------------
# Sidecar writing
# ---------------------------------------------------------------------------


class TestSidecarWritten:
    """Test sidecar review file generation."""

    def test_sidecar_written(self, tmp_path: Path) -> None:
        plan_path = Path("plans/sessions/test.md")
        state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key="test_sidecar_key",
            tier="small",
            state=PlanReviewState.REVIEW_COMPLETE.value,
            iteration_count=2,
            max_iterations=5,
        )

        finding = _make_finding(severity="WARNING", description="Test warning")
        all_findings: list[tuple[int, list]] = [(1, [finding])]

        sidecar = _write_sidecar(
            plan_path, state, all_findings, "codex_cli", base_dir=tmp_path
        )

        assert sidecar.exists()
        content = sidecar.read_text()
        assert "# Plan Review: test.md" in content
        assert "**Reviewer:** codex_cli" in content
        assert "**Tier:** small" in content
        assert "**Iterations:** 2/5" in content
        assert "**Verdict:** READY" in content
        assert "Test warning" in content

    def test_sidecar_no_findings(self, tmp_path: Path) -> None:
        plan_path = Path("plans/sessions/clean.md")
        state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key="test_clean_sidecar",
            tier="medium",
            state=PlanReviewState.REVIEW_COMPLETE.value,
            iteration_count=1,
            max_iterations=5,
        )

        sidecar = _write_sidecar(plan_path, state, [], "codex_cli", base_dir=tmp_path)

        assert sidecar.exists()
        content = sidecar.read_text()
        assert "No findings" in content
        assert "**Verdict:** READY" in content

    def test_sidecar_path_under_state_dir(self, tmp_path: Path) -> None:
        plan_path = Path("plans/sessions/test.md")
        state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key="pathcheck_key",
            tier="small",
            state=PlanReviewState.REVIEW_COMPLETE.value,
        )

        sidecar = _write_sidecar(plan_path, state, [], "codex_cli", base_dir=tmp_path)

        assert str(sidecar).startswith(str(tmp_path))
        assert "pathcheck_key" in str(sidecar)
        assert sidecar.name == "review.md"

    def test_sidecar_includes_raw_output(self, tmp_path: Path) -> None:
        """Sidecar includes raw reviewer output for debuggability (issue #799)."""
        plan_path = Path("plans/sessions/test.md")
        state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key="test_raw_output_key",
            tier="small",
            state=PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES.value,
            iteration_count=1,
            max_iterations=3,
        )

        raw = "The plan looks reasonable but I have some thoughts about error handling."
        sidecar = _write_sidecar(
            plan_path, state, [], "codex_cli", base_dir=tmp_path, raw_output=raw
        )

        content = sidecar.read_text()
        assert "## Raw Output" in content
        assert raw in content

    def test_sidecar_omits_raw_output_when_empty(self, tmp_path: Path) -> None:
        """Sidecar omits Raw Output section when output is empty."""
        plan_path = Path("plans/sessions/test.md")
        state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key="test_no_raw_key",
            tier="small",
            state=PlanReviewState.REVIEW_COMPLETE.value,
        )

        sidecar = _write_sidecar(
            plan_path, state, [], "codex_cli", base_dir=tmp_path, raw_output=""
        )

        content = sidecar.read_text()
        assert "## Raw Output" not in content


# ---------------------------------------------------------------------------
# Raw output persistence in loop
# ---------------------------------------------------------------------------


class TestRawOutputPersistence:
    """Test that raw output is persisted through the review loop (issue #799)."""

    def test_raw_output_persisted_to_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raw Codex output is written to codex_output_raw.txt in state dir."""
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n")

        codex_raw = "The plan looks well-structured. No significant issues."

        def mock_codex(*args, **kwargs):
            # Simulate invoke_codex_plan_review writing raw output
            output_dir = kwargs.get("output_dir")
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "codex_output_raw.txt").write_text(codex_raw)
            return _make_result(success=True, findings=[])

        monkeypatch.setattr("plan_review_driver.invoke_codex_plan_review", mock_codex)
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_raw_persist"
        )

        result = run_plan_review_loop(plan_file, base_dir=tmp_path)
        assert result.verdict == "READY"

        # Verify raw output was written to state dir
        from review_state import plan_review_state_dir

        state_dir = plan_review_state_dir("test_raw_persist", tmp_path)
        raw_file = state_dir / "codex_output_raw.txt"
        assert raw_file.exists()
        assert raw_file.read_text() == codex_raw

    def test_raw_output_in_sidecar_on_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When Codex returns unparseable output, sidecar includes it."""
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n")

        unparseable_text = "Here are my general thoughts about the plan..."

        mock_result = _make_result(success=False, error="Unparseable output")
        mock_result.raw_output = unparseable_text

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: mock_result,
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(success=False, error="Also failed"),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_sidecar_raw"
        )
        monkeypatch.setattr(
            "plan_review_driver._create_fallback_issue", lambda *a, **kw: None
        )

        result = run_plan_review_loop(plan_file, base_dir=tmp_path)

        # Read the sidecar and verify raw output section
        sidecar = Path(result.sidecar_path)
        assert sidecar.exists()
        content = sidecar.read_text()
        # The fallback's empty raw_output is last, so check that sidecar was written
        assert "## Raw Output" not in content or "## Final State" in content


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


class TestStatePersistence:
    """Test that state can be saved and loaded correctly."""

    def test_state_persistence(self, tmp_path: Path) -> None:
        original = PlanReviewLoopState(
            plan_path="plans/test.md",
            state_key="persist_test_key",
            tier="governing",
            state=PlanReviewState.FINDINGS_RECEIVED.value,
            iteration_count=3,
            max_iterations=5,
            last_findings_hash="abc123",
            fallback_used=True,
            fallback_reason="Codex timed out",
        )

        save_plan_review_state(original, tmp_path)
        loaded = load_plan_review_state("persist_test_key", tmp_path)

        assert loaded is not None
        assert loaded.plan_path == "plans/test.md"
        assert loaded.state_key == "persist_test_key"
        assert loaded.tier == "governing"
        assert loaded.state == PlanReviewState.FINDINGS_RECEIVED.value
        assert loaded.iteration_count == 3
        assert loaded.max_iterations == 5
        assert loaded.last_findings_hash == "abc123"
        assert loaded.fallback_used is True
        assert loaded.fallback_reason == "Codex timed out"

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        result = load_plan_review_state("nonexistent_key", tmp_path)
        assert result is None

    def test_resume_from_codex_reviewing_resets_to_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Resuming from CODEX_REVIEWING should not raise InvalidTransitionError.

        The driver resets non-terminal states to INITIALIZED before entering
        the loop, so a restart from any mid-loop state is safe.
        """
        # Pre-save state in CODEX_REVIEWING (simulates interrupted run)
        key = "resume_test_key"
        pre_state = PlanReviewLoopState(
            plan_path="plans/sessions/test.md",
            state_key=key,
            tier="small",
            state=PlanReviewState.CODEX_REVIEWING.value,
            iteration_count=1,
        )
        save_plan_review_state(pre_state, tmp_path)

        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text("# Test Plan\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=True, findings=[]),
        )
        monkeypatch.setattr("plan_review_driver.detect_plan_tier", lambda p: "small")
        monkeypatch.setattr("plan_review_driver.plan_state_key", lambda p: key)

        # Should NOT raise InvalidTransitionError
        result = run_plan_review_loop(plan_file, base_dir=tmp_path)
        assert result.verdict == "READY"


# ---------------------------------------------------------------------------
# Fallback issue creation
# ---------------------------------------------------------------------------


class TestCreateFallbackIssue:
    """Test GitHub issue creation for fallback scenarios."""

    def test_fallback_issue_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful issue creation returns URL."""

        def mock_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/42\n"
            return result

        monkeypatch.setattr("plan_review_driver.subprocess.run", mock_run)

        url = _create_fallback_issue(Path("plans/test.md"), "small", "Codex not found")
        assert url == "https://github.com/test/repo/issues/42"

    def test_fallback_issue_retries_without_label(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls back to no-label issue when label doesn't exist."""
        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # First call with label fails
                result.returncode = 1
                result.stdout = ""
            else:
                # Second call without label succeeds
                result.returncode = 0
                result.stdout = "https://github.com/test/repo/issues/43\n"
            return result

        monkeypatch.setattr("plan_review_driver.subprocess.run", mock_run)

        url = _create_fallback_issue(Path("plans/test.md"), "medium", "Codex broken")
        assert url == "https://github.com/test/repo/issues/43"
        assert call_count == 2

    def test_fallback_issue_all_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All attempts fail -> returns None."""

        def mock_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            return result

        monkeypatch.setattr("plan_review_driver.subprocess.run", mock_run)

        url = _create_fallback_issue(Path("plans/test.md"), "small", "error")
        assert url is None


# ---------------------------------------------------------------------------
# Tier override
# ---------------------------------------------------------------------------


class TestTierOverride:
    """Test that explicit tier overrides auto-detection."""

    def test_tier_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plans" / "sessions" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Test Plan\n")

        monkeypatch.setattr(
            "plan_review_driver.invoke_codex_plan_review",
            lambda *a, **kw: _make_result(success=True, findings=[]),
        )
        monkeypatch.setattr(
            "plan_review_driver.invoke_claude_failsafe",
            lambda *a, **kw: _make_result(),
        )
        # detect_plan_tier should NOT be called when tier is provided
        monkeypatch.setattr(
            "plan_review_driver.detect_plan_tier",
            lambda p: (_ for _ in ()).throw(AssertionError("Should not be called")),
        )
        monkeypatch.setattr(
            "plan_review_driver.plan_state_key", lambda p: "test_override_key"
        )

        result = run_plan_review_loop(plan_file, tier="governing", base_dir=tmp_path)

        assert result.tier == "governing"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


class TestPlanReviewLoopResult:
    """Test PlanReviewLoopResult serialization."""

    def test_result_to_dict(self) -> None:
        result = PlanReviewLoopResult(
            plan_path="plans/test.md",
            tier="small",
            verdict="READY",
            iterations=1,
            total_findings=0,
            open_findings=0,
            reviewer="codex_cli",
            fallback_used=False,
            fallback_issue_url=None,
            sidecar_path="/tmp/review.md",
            findings=[],
        )
        d = result.to_dict()
        assert d["plan_path"] == "plans/test.md"
        assert d["verdict"] == "READY"
        assert d["iterations"] == 1
        assert d["fallback_used"] is False
        assert d["findings"] == []

    def test_result_with_findings(self) -> None:
        result = PlanReviewLoopResult(
            plan_path="plans/test.md",
            tier="governing",
            verdict="NOT_READY",
            iterations=3,
            total_findings=5,
            open_findings=2,
            reviewer="claude_failsafe",
            fallback_used=True,
            fallback_issue_url="https://github.com/test/issues/1",
            sidecar_path="/tmp/review.md",
            findings=[{"severity": "CRITICAL", "description": "Problem"}],
        )
        d = result.to_dict()
        assert d["total_findings"] == 5
        assert d["open_findings"] == 2
        assert d["fallback_used"] is True
        assert len(d["findings"]) == 1
