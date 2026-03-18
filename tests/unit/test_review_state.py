"""Tests for review_state.py — state schema, transitions, persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from review_state import (
    REVIEW_STATUS_MAP,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    NormalizedFinding,
    ReviewLoopState,
    ReviewMode,
    ReviewState,
    compute_findings_hash,
    load_state,
    review_status_to_github,
    save_state,
)


class TestReviewState:
    """Test ReviewState enum and transition rules."""

    def test_all_states_have_transition_entry(self) -> None:
        """Every state must appear as a key in VALID_TRANSITIONS."""
        for state in ReviewState:
            assert state in VALID_TRANSITIONS, f"{state} missing from VALID_TRANSITIONS"

    def test_terminal_states_have_no_outgoing(self) -> None:
        """Terminal states must have empty transition lists."""
        for state in TERMINAL_STATES:
            assert (
                VALID_TRANSITIONS[state] == []
            ), f"Terminal state {state} has outgoing transitions"

    def test_terminal_states_are_correct(self) -> None:
        expected = {
            ReviewState.MERGED,
            ReviewState.STOPPED_MAX_ITERATIONS,
            ReviewState.STOPPED_NO_PROGRESS,
            ReviewState.STOPPED_CI_FAILURE,
            ReviewState.STOPPED_REVIEW_FAILURE,
        }
        assert TERMINAL_STATES == expected

    def test_non_terminal_states_have_outgoing(self) -> None:
        """Non-terminal states must have at least one outgoing transition."""
        for state in ReviewState:
            if state not in TERMINAL_STATES:
                assert (
                    len(VALID_TRANSITIONS[state]) > 0
                ), f"Non-terminal state {state} has no outgoing transitions"

    def test_transition_targets_are_valid_states(self) -> None:
        """All transition targets must be valid ReviewState values."""
        for source, targets in VALID_TRANSITIONS.items():
            for target in targets:
                assert isinstance(
                    target, ReviewState
                ), f"Invalid target {target} from {source}"


class TestReviewLoopState:
    """Test ReviewLoopState dataclass."""

    def test_initialization(self) -> None:
        state = ReviewLoopState(pr_number=42, branch="test-branch")
        assert state.pr_number == 42
        assert state.branch == "test-branch"
        assert state.current_state == ReviewState.INITIALIZED
        assert state.mode == ReviewMode.STANDARD.value
        assert state.iteration_count == 0
        assert state.max_iterations == 5
        assert not state.is_terminal

    def test_valid_transition(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        assert state.current_state == ReviewState.PR_OPEN
        assert not state.is_terminal

    def test_invalid_transition_raises(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        # INITIALIZED can only go to PR_OPEN
        with pytest.raises(InvalidTransitionError):
            state.transition(ReviewState.READY_TO_MERGE)

    def test_transition_from_terminal_raises(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.state = ReviewState.MERGED.value
        with pytest.raises(InvalidTransitionError, match="terminal"):
            state.transition(ReviewState.PR_OPEN)

    def test_global_stop_transitions(self) -> None:
        """Any non-terminal state can transition to global stop states."""
        state = ReviewLoopState(pr_number=1, branch="b")
        state.state = ReviewState.WAITING_FOR_CI.value
        # STOPPED_MAX_ITERATIONS is a global target
        state.transition(ReviewState.STOPPED_MAX_ITERATIONS)
        assert state.is_terminal

    def test_is_terminal(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.state = ReviewState.STOPPED_NO_PROGRESS.value
        assert state.is_terminal

    def test_updated_at_changes_on_transition(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        original = state.updated_at
        state.transition(ReviewState.PR_OPEN)
        assert state.updated_at >= original


class TestSerialization:
    """Test state serialization round-trip."""

    def test_to_dict_from_dict_roundtrip(self) -> None:
        original = ReviewLoopState(
            pr_number=42,
            branch="feature-branch",
            mode=ReviewMode.REPORT_AUDIT.value,
            iteration_count=3,
            last_findings_hash="abc123",
            last_head_sha="deadbeef",
            stop_reason="test stop",
        )
        d = original.to_dict()
        restored = ReviewLoopState.from_dict(d)

        assert restored.pr_number == original.pr_number
        assert restored.branch == original.branch
        assert restored.mode == original.mode
        assert restored.iteration_count == original.iteration_count
        assert restored.last_findings_hash == original.last_findings_hash
        assert restored.last_head_sha == original.last_head_sha
        assert restored.stop_reason == original.stop_reason

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = {"pr_number": 1, "branch": "b", "unknown_key": "ignored"}
        state = ReviewLoopState.from_dict(d)
        assert state.pr_number == 1

    def test_json_roundtrip(self) -> None:
        original = ReviewLoopState(pr_number=99, branch="test")
        json_str = json.dumps(original.to_dict())
        restored = ReviewLoopState.from_dict(json.loads(json_str))
        assert restored.pr_number == 99


class TestPersistence:
    """Test load/save to disk."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        original = ReviewLoopState(pr_number=42, branch="test-branch")
        original.transition(ReviewState.PR_OPEN)

        save_state(original, tmp_path)
        loaded = load_state(42, tmp_path)

        assert loaded is not None
        assert loaded.pr_number == 42
        assert loaded.current_state == ReviewState.PR_OPEN

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        result = load_state(999, tmp_path)
        assert result is None

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        state = ReviewLoopState(pr_number=7, branch="b")
        path = save_state(state, tmp_path)
        assert path.exists()
        assert path.parent.name == "pr_7"

    def test_idempotent_save(self, tmp_path: Path) -> None:
        """Saving the same state twice produces the same file."""
        state = ReviewLoopState(pr_number=1, branch="b")
        save_state(state, tmp_path)
        save_state(state, tmp_path)
        loaded = load_state(1, tmp_path)
        assert loaded is not None
        assert loaded.pr_number == 1


class TestFindingsHash:
    """Test deterministic findings hashing."""

    def test_same_findings_same_hash(self) -> None:
        findings = [
            {"file": "a.py", "line": 1, "message": "issue"},
            {"file": "b.py", "line": 2, "message": "other"},
        ]
        h1 = compute_findings_hash(findings)
        h2 = compute_findings_hash(findings)
        assert h1 == h2

    def test_order_independent(self) -> None:
        findings_a = [
            {"file": "b.py", "line": 2, "message": "other"},
            {"file": "a.py", "line": 1, "message": "issue"},
        ]
        findings_b = [
            {"file": "a.py", "line": 1, "message": "issue"},
            {"file": "b.py", "line": 2, "message": "other"},
        ]
        assert compute_findings_hash(findings_a) == compute_findings_hash(findings_b)

    def test_different_findings_different_hash(self) -> None:
        h1 = compute_findings_hash([{"file": "a.py", "line": 1, "message": "x"}])
        h2 = compute_findings_hash([{"file": "a.py", "line": 1, "message": "y"}])
        assert h1 != h2

    def test_empty_findings(self) -> None:
        h = compute_findings_hash([])
        assert isinstance(h, str)
        assert len(h) == 16


class TestTransitionChains:
    """Test complete state transition chains (happy path + error paths)."""

    def test_happy_path_chain(self) -> None:
        """Full happy path: initialized → ... → ready_to_merge → merged."""
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
        state.transition(ReviewState.SCORING_FINDINGS)
        state.transition(ReviewState.READY_TO_MERGE)
        assert state.current_state == ReviewState.READY_TO_MERGE
        assert not state.is_terminal  # Can still transition to MERGED
        state.transition(ReviewState.MERGED)
        assert state.is_terminal

    def test_fix_loop_chain(self) -> None:
        """Fix loop: ... → applying_fixes → retesting → waiting_for_ci → ..."""
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
        state.transition(ReviewState.SCORING_FINDINGS)
        state.transition(ReviewState.APPLYING_FIXES)
        state.transition(ReviewState.RETESTING)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
        state.transition(ReviewState.SCORING_FINDINGS)
        state.transition(ReviewState.READY_TO_MERGE)
        assert state.current_state == ReviewState.READY_TO_MERGE
        state.transition(ReviewState.MERGED)
        assert state.is_terminal

    def test_ci_failure_stops(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.STOPPED_CI_FAILURE)
        assert state.is_terminal
        assert state.current_state == ReviewState.STOPPED_CI_FAILURE

    def test_pr_open_to_stopped_ci_failure(self) -> None:
        """Regression: pr_open must allow direct transition to stopped_ci_failure.

        The review driver transitions pr_open → stopped_ci_failure when
        deterministic prechecks find blocking issues before CI starts.
        """
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.STOPPED_CI_FAILURE)
        assert state.is_terminal
        assert state.current_state == ReviewState.STOPPED_CI_FAILURE

    def test_review_failure_stops(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
        state.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        assert state.is_terminal


class TestSHAIdempotency:
    """Test SHA-based idempotency in load_state()."""

    def test_load_without_head_sha_works_as_before(self, tmp_path: Path) -> None:
        """Backward compat: load_state without head_sha always returns state."""
        state = ReviewLoopState(pr_number=42, branch="b", initial_head_sha="abc1234")
        save_state(state, tmp_path)
        loaded = load_state(42, tmp_path)
        assert loaded is not None
        assert loaded.initial_head_sha == "abc1234"

    def test_load_with_matching_head_sha_returns_state(self, tmp_path: Path) -> None:
        """If head_sha matches initial_head_sha, state is valid."""
        state = ReviewLoopState(
            pr_number=42,
            branch="b",
            initial_head_sha="abc1234567890",
            current_head_sha="abc1234567890",
        )
        save_state(state, tmp_path)
        loaded = load_state(42, tmp_path, head_sha="abc1234567890")
        assert loaded is not None

    def test_load_with_mismatched_head_sha_returns_none(self, tmp_path: Path) -> None:
        """If head_sha doesn't match initial or current, state is stale."""
        state = ReviewLoopState(
            pr_number=42,
            branch="b",
            initial_head_sha="abc1234567890",
            current_head_sha="abc1234567890",
        )
        save_state(state, tmp_path)
        loaded = load_state(42, tmp_path, head_sha="deadbeef12345")
        assert loaded is None

    def test_load_with_autofix_sha_returns_state(self, tmp_path: Path) -> None:
        """If head_sha matches current_head_sha (auto-fix), state is valid."""
        state = ReviewLoopState(
            pr_number=42,
            branch="b",
            initial_head_sha="abc1234567890",
            current_head_sha="deadbeef12345",  # auto-fix pushed new SHA
        )
        save_state(state, tmp_path)
        # head_sha matches current (auto-fix SHA), not initial
        loaded = load_state(42, tmp_path, head_sha="deadbeef12345")
        assert loaded is not None

    def test_load_no_initial_sha_ignores_check(self, tmp_path: Path) -> None:
        """If state has no initial_head_sha, SHA check is skipped."""
        state = ReviewLoopState(pr_number=42, branch="b")
        assert state.initial_head_sha is None
        save_state(state, tmp_path)
        loaded = load_state(42, tmp_path, head_sha="anything")
        assert loaded is not None

    def test_sha_fields_roundtrip(self) -> None:
        """New SHA fields survive serialization round-trip."""
        state = ReviewLoopState(
            pr_number=1,
            branch="b",
            initial_head_sha="abc1234567890",
            current_head_sha="def4567890123",
            run_id="pr_1_abc1234",
        )
        d = state.to_dict()
        restored = ReviewLoopState.from_dict(d)
        assert restored.initial_head_sha == "abc1234567890"
        assert restored.current_head_sha == "def4567890123"
        assert restored.run_id == "pr_1_abc1234"


class TestNormalizedFinding:
    """Test the NormalizedFinding dataclass."""

    def test_creation(self) -> None:
        finding = NormalizedFinding(
            severity="P1",
            file="src/foo.py",
            line=42,
            category="correctness",
            check_id="C1",
            message="test issue",
            source="deterministic_precheck",
        )
        assert finding.severity == "P1"
        assert finding.file == "src/foo.py"
        assert finding.line == 42
        assert finding.source == "deterministic_precheck"
        assert finding.rationale is None

    def test_to_dict(self) -> None:
        finding = NormalizedFinding(
            severity="P2",
            file="tests/test.py",
            line=10,
            category="convention",
            check_id=None,
            message="convention issue",
            source="codex_cli",
            rationale="style concern",
        )
        d = finding.to_dict()
        assert d["severity"] == "P2"
        assert d["source"] == "codex_cli"
        assert d["rationale"] == "style concern"
        assert d["check_id"] is None

    def test_from_dict(self) -> None:
        data = {
            "severity": "P0",
            "file": "core.py",
            "line": 1,
            "category": "process",
            "check_id": "X3",
            "message": "merge conflict",
            "source": "deterministic_precheck",
        }
        finding = NormalizedFinding.from_dict(data)
        assert finding.severity == "P0"
        assert finding.check_id == "X3"

    def test_from_dict_maps_raw_source(self) -> None:
        """Finding/CodexFinding use raw_source, should be mapped to source."""
        data = {
            "severity": "P1",
            "file": "x.py",
            "line": 5,
            "category": "correctness",
            "check_id": "C1",
            "message": "unseeded",
            "raw_source": "codex_cli",
        }
        finding = NormalizedFinding.from_dict(data)
        assert finding.source == "codex_cli"

    def test_from_dict_ignores_unknown_keys(self) -> None:
        data = {
            "severity": "P2",
            "file": "x.py",
            "line": 1,
            "category": "convention",
            "check_id": None,
            "message": "test",
            "source": "test",
            "unknown_field": "ignored",
        }
        finding = NormalizedFinding.from_dict(data)
        assert finding.message == "test"


class TestReviewStatusMap:
    """Test the review status mapping."""

    def test_all_statuses_mapped(self) -> None:
        expected_keys = {"pending", "in_progress", "fail", "warn", "ready", "degraded"}
        assert set(REVIEW_STATUS_MAP.keys()) == expected_keys

    def test_degraded_maps_to_success(self) -> None:
        assert review_status_to_github("degraded") == "success"

    def test_pending_maps_to_pending(self) -> None:
        assert review_status_to_github("pending") == "pending"

    def test_in_progress_maps_to_pending(self) -> None:
        assert review_status_to_github("in_progress") == "pending"

    def test_fail_maps_to_failure(self) -> None:
        assert review_status_to_github("fail") == "failure"

    def test_warn_maps_to_success(self) -> None:
        assert review_status_to_github("warn") == "success"

    def test_ready_maps_to_success(self) -> None:
        assert review_status_to_github("ready") == "success"

    def test_unknown_defaults_to_pending(self) -> None:
        assert review_status_to_github("unknown_status") == "pending"

    def test_github_api_state_values(self) -> None:
        """All mapped values must be valid GitHub API states."""
        valid_github_states = {"pending", "success", "failure", "error"}
        for value in REVIEW_STATUS_MAP.values():
            assert value in valid_github_states
