"""
Unit tests for meta.py helper functions.
"""

import subprocess

from bid_euchre.experiments.meta import get_git_sha


def test_get_git_sha_unknown(monkeypatch):
    """Test that get_git_sha returns 'unknown' when git command fails."""
    def _boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert get_git_sha() == "unknown"


def test_get_git_sha_unknown_on_exception(monkeypatch):
    """Test that get_git_sha returns 'unknown' on any exception."""
    def _raise(*args, **kwargs):
        raise RuntimeError("Git not available")

    monkeypatch.setattr(subprocess, "check_output", _raise)
    assert get_git_sha() == "unknown"
