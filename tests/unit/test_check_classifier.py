"""Tests for the three-category check classifier in ops/__init__.py."""

from __future__ import annotations

import sys
from pathlib import Path

from bid_euchre.ops import (
    ADVISORY_CONTEXTS,
    DEFAULT_REVIEW_CONTEXTS,
    NON_CI_CONTEXTS,
    REVIEW_GATE_CONTEXTS,
    classify_check,
)


class TestClassifyCheck:
    """Tests for classify_check()."""

    def test_reviewing_changes_is_review_gate(self) -> None:
        assert classify_check("reviewing-changes") == "review_gate"

    def test_claude_review_is_advisory(self) -> None:
        assert classify_check("claude-review") == "advisory"

    def test_tests_is_ci(self) -> None:
        assert classify_check("tests") == "ci"

    def test_lint_is_ci(self) -> None:
        assert classify_check("lint") == "ci"

    def test_unknown_name_defaults_to_ci(self) -> None:
        """Unknown check names must default to 'ci' (conservative)."""
        assert classify_check("some-random-check") == "ci"

    def test_empty_name_is_ci(self) -> None:
        assert classify_check("") == "ci"


class TestConstants:
    """Tests for the check classification constants."""

    def test_review_gate_contains_reviewing_changes(self) -> None:
        assert "reviewing-changes" in REVIEW_GATE_CONTEXTS

    def test_advisory_contains_claude_review(self) -> None:
        assert "claude-review" in ADVISORY_CONTEXTS

    def test_non_ci_is_union(self) -> None:
        """NON_CI_CONTEXTS is the union of review gate + advisory."""
        expected = set(REVIEW_GATE_CONTEXTS) | set(ADVISORY_CONTEXTS)
        assert set(NON_CI_CONTEXTS) == expected

    def test_review_gate_is_alias_for_default(self) -> None:
        """REVIEW_GATE_CONTEXTS == DEFAULT_REVIEW_CONTEXTS (backward compat)."""
        assert REVIEW_GATE_CONTEXTS == DEFAULT_REVIEW_CONTEXTS

    def test_no_overlap_between_review_gate_and_advisory(self) -> None:
        """Review gate and advisory must be disjoint categories."""
        overlap = set(REVIEW_GATE_CONTEXTS) & set(ADVISORY_CONTEXTS)
        assert overlap == set(), f"Unexpected overlap: {overlap}"


class TestConsistencyWithGithubPrState:
    """Verify github_pr_state.py CI allowlist excludes all non-CI contexts."""

    def test_ci_allowlist_excludes_non_ci_contexts(self) -> None:
        """The CI allowlist in scripts/internal must not contain any non-CI context."""
        # Add scripts/internal to path for import
        scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "internal"
        sys.path.insert(0, str(scripts_dir))
        try:
            from github_pr_state import _CI_CHECK_NAMES

            for ctx in NON_CI_CONTEXTS:
                assert (
                    ctx not in _CI_CHECK_NAMES
                ), f"Non-CI context {ctx!r} found in _CI_CHECK_NAMES allowlist"
        finally:
            sys.path.pop(0)
