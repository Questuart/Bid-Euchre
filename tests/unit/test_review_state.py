"""Tests for review_state.py — state schema, transitions, persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from review_state import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    ReviewLoopState,
    ReviewMode,
    ReviewState,
    compute_findings_hash,
    load_state,
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
        state.transition(ReviewState.APPLYING_FIXES)
        state.transition(ReviewState.RETESTING)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
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

    def test_review_failure_stops(self) -> None:
        state = ReviewLoopState(pr_number=1, branch="b")
        state.transition(ReviewState.PR_OPEN)
        state.transition(ReviewState.WAITING_FOR_CI)
        state.transition(ReviewState.WAITING_FOR_CODEX)
        state.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        assert state.is_terminal
