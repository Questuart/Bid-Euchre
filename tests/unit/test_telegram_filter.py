"""Unit tests for ops.telegram_filter (issue #1824, part 2).

Tests cover:
- is_telegram_receiver(): env var priority, project dir detection, edge cases
- detect_lane_from_env(): lane identity inference from CLAUDE_PROJECT_DIR
"""

from __future__ import annotations

import pytest

from bid_euchre.ops.telegram_filter import (
    ORCHESTRATOR_WORKTREES,
    TELEGRAM_RECEIVER_ENV,
    detect_lane_from_env,
    is_telegram_receiver,
)

# ---------------------------------------------------------------------------
# is_telegram_receiver — env var priority
# ---------------------------------------------------------------------------


class TestIsTelegramReceiverEnvVar:
    """STEWARD_TELEGRAM_RECEIVER env var takes highest priority."""

    def test_explicit_receiver_1(self) -> None:
        assert is_telegram_receiver(receiver_env="1") is True

    def test_explicit_receiver_0(self) -> None:
        assert is_telegram_receiver(receiver_env="0") is False

    def test_explicit_receiver_1_overrides_non_orchestrator_dir(self) -> None:
        """Even on a non-orchestrator worktree, env=1 wins."""
        assert (
            is_telegram_receiver(
                receiver_env="1",
                project_dir="/some/path/Bid-Euchre-steward-author",
            )
            is True
        )

    def test_explicit_receiver_0_overrides_orchestrator_dir(self) -> None:
        """Even on the orchestrator worktree, env=0 wins."""
        assert (
            is_telegram_receiver(
                receiver_env="0",
                project_dir="/some/path/Bid-Euchre",
            )
            is False
        )


# ---------------------------------------------------------------------------
# is_telegram_receiver — project dir fallback
# ---------------------------------------------------------------------------


class TestIsTelegramReceiverProjectDir:
    """When no explicit env var, project dir basename determines the answer."""

    def test_main_checkout_is_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre",
            )
            is True
        )

    def test_author_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author",
            )
            is False
        )

    def test_brws_author_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-brws-author-d",
            )
            is False
        )

    def test_ops_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-ops",
            )
            is False
        )

    def test_review_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-review",
            )
            is False
        )

    def test_flex_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-flex-a",
            )
            is False
        )

    def test_analyst_lane_is_not_receiver(self) -> None:
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-analyst",
            )
            is False
        )


# ---------------------------------------------------------------------------
# is_telegram_receiver — edge cases
# ---------------------------------------------------------------------------


class TestIsTelegramReceiverEdgeCases:
    def test_no_env_no_dir(self) -> None:
        """No env var and no project dir → conservative: not a receiver."""
        assert is_telegram_receiver(receiver_env="", project_dir="") is False

    def test_unset_env_empty_dir(self) -> None:
        assert is_telegram_receiver(receiver_env=None, project_dir="") is False

    def test_trailing_slash_in_project_dir(self) -> None:
        """Path.name handles trailing slashes correctly."""
        assert (
            is_telegram_receiver(
                receiver_env="",
                project_dir="/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre/",
            )
            is True
        )

    def test_unknown_env_value_falls_through(self) -> None:
        """Env var values other than '0' or '1' fall through to dir check."""
        assert (
            is_telegram_receiver(
                receiver_env="yes",
                project_dir="/path/Bid-Euchre-steward-author",
            )
            is False
        )

    def test_orchestrator_worktrees_frozenset(self) -> None:
        """Verify the constant contains the expected entries."""
        assert "Bid-Euchre" in ORCHESTRATOR_WORKTREES


# ---------------------------------------------------------------------------
# detect_lane_from_env
# ---------------------------------------------------------------------------


class TestDetectLaneFromEnv:
    def test_main_checkout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CLAUDE_PROJECT_DIR",
            "/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre",
        )
        assert detect_lane_from_env() == "main-checkout"

    def test_steward_worktree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CLAUDE_PROJECT_DIR",
            "/Users/runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author",
        )
        assert detect_lane_from_env() == "Bid-Euchre-steward-author"

    def test_brws_worktree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CLAUDE_PROJECT_DIR",
            "/path/to/Bid-Euchre-steward-brws-author-d",
        )
        assert detect_lane_from_env() == "Bid-Euchre-steward-brws-author-d"

    def test_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert detect_lane_from_env() is None

    def test_empty_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "")
        assert detect_lane_from_env() is None

    def test_unrecognised_project_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/Users/someone/SomeProject")
        assert detect_lane_from_env() is None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_receiver_env_name(self) -> None:
        assert TELEGRAM_RECEIVER_ENV == "STEWARD_TELEGRAM_RECEIVER"

    def test_orchestrator_worktrees_type(self) -> None:
        assert isinstance(ORCHESTRATOR_WORKTREES, frozenset)
