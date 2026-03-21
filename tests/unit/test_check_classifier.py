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

    def test_enable_auto_merge_is_advisory(self) -> None:
        """enable-auto-merge is plumbing, not CI (#1036)."""
        assert classify_check("enable-auto-merge") == "advisory"

    def test_tests_is_ci(self) -> None:
        assert classify_check("tests") == "ci"

    def test_lint_is_ci(self) -> None:
        assert classify_check("lint") == "ci"

    def test_unknown_name_defaults_to_ci(self) -> None:
        """Unknown check names must default to 'ci' (fail-open denylist)."""
        assert classify_check("some-random-check") == "ci"

    def test_empty_name_is_ci(self) -> None:
        assert classify_check("") == "ci"


class TestConstants:
    """Tests for the check classification constants."""

    def test_review_gate_contains_reviewing_changes(self) -> None:
        assert "reviewing-changes" in REVIEW_GATE_CONTEXTS

    def test_advisory_contains_claude_review(self) -> None:
        assert "claude-review" in ADVISORY_CONTEXTS

    def test_advisory_contains_enable_auto_merge(self) -> None:
        """enable-auto-merge is plumbing — must be in advisory (#1036)."""
        assert "enable-auto-merge" in ADVISORY_CONTEXTS

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
    """Verify github_pr_state.py uses classify_check for CI classification."""

    def test_github_pr_state_uses_classify_check(self) -> None:
        """github_pr_state._classify_check must agree with ops.classify_check."""
        scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "internal"
        sys.path.insert(0, str(scripts_dir))
        try:
            from github_pr_state import _classify_check as pr_state_classify

            # All non-CI contexts must be excluded by both classifiers
            for ctx in NON_CI_CONTEXTS:
                assert (
                    pr_state_classify(ctx) != "ci"
                ), f"Non-CI context {ctx!r} classified as 'ci' by github_pr_state"

            # Known CI checks must be included by both
            for name in ("tests", "prechecks", "governance"):
                assert (
                    pr_state_classify(name) == "ci"
                ), f"CI check {name!r} not classified as 'ci' by github_pr_state"

            # Unknown checks must default to CI (fail-open)
            assert pr_state_classify("brand-new-workflow") == "ci"
        finally:
            sys.path.pop(0)


class TestDriftDetection:
    """Catch drift between CI_CHECK_NAMES (deprecated) and classify_check."""

    def test_ci_check_names_members_classify_as_ci(self) -> None:
        """Every name in the deprecated CI_CHECK_NAMES must classify as 'ci'.

        If this fails, a CI check was added to the allowlist but is being
        excluded by the denylist — an inconsistency that should be resolved.
        """
        from bid_euchre.ops import CI_CHECK_NAMES

        for name in CI_CHECK_NAMES:
            assert (
                classify_check(name) == "ci"
            ), f"CI_CHECK_NAMES member {name!r} does not classify as 'ci'"

    def test_fallback_denylist_matches_non_ci_contexts(self) -> None:
        """The inline fallback denylist in github_pr_state.py must cover all
        NON_CI_CONTEXTS from ops/__init__.py.

        If this fails, a new non-CI context was added to ops but not to the
        inline fallback, which would cause divergence when bid_euchre is not
        importable.
        """
        scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "internal"
        sys.path.insert(0, str(scripts_dir))
        try:
            from github_pr_state import _classify_check as pr_state_classify

            for ctx in NON_CI_CONTEXTS:
                result = pr_state_classify(ctx)
                assert result != "ci", (
                    f"NON_CI_CONTEXTS member {ctx!r} classified as 'ci' by "
                    f"github_pr_state fallback — update _FALLBACK_NON_CI"
                )
        finally:
            sys.path.pop(0)

    def test_fallback_actually_exercises_fallback_path(self) -> None:
        """Force ImportError to exercise the inline fallback classifier (#1094).

        The normal import succeeds because bid_euchre is installed in test env,
        so test_fallback_denylist_matches_non_ci_contexts tests the canonical
        path, not the fallback.  This test reloads the module with bid_euchre
        blocked to verify the inline fallback logic.
        """
        from unittest.mock import patch

        scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "internal"
        sys.path.insert(0, str(scripts_dir))
        try:
            # Remove cached module so reimport picks up the patched import
            if "github_pr_state" in sys.modules:
                saved_module = sys.modules.pop("github_pr_state")
            else:
                saved_module = None

            # Block bid_euchre.ops import to trigger the fallback branch
            original_import = (
                __builtins__.__import__
                if hasattr(__builtins__, "__import__")
                else __import__
            )

            def blocking_import(name, *args, **kwargs):
                if name == "bid_euchre.ops":
                    raise ImportError("Simulated: bid_euchre not installed")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=blocking_import):
                import github_pr_state as gps_fallback

            fallback_classify = gps_fallback._classify_check

            # Verify fallback returns "non_ci" for all NON_CI_CONTEXTS
            for ctx in NON_CI_CONTEXTS:
                result = fallback_classify(ctx)
                assert (
                    result != "ci"
                ), f"Fallback _classify_check classified {ctx!r} as 'ci'"
                # Fallback returns "non_ci" (not "review_gate"/"advisory")
                assert (
                    result == "non_ci"
                ), f"Fallback should return 'non_ci' for {ctx!r}, got {result!r}"

            # Verify fallback returns "ci" for unknown checks
            assert fallback_classify("tests") == "ci"
            assert fallback_classify("some-unknown-job") == "ci"
        finally:
            # Restore original module
            sys.modules.pop("github_pr_state", None)
            if saved_module is not None:
                sys.modules["github_pr_state"] = saved_module
            sys.path.pop(0)
