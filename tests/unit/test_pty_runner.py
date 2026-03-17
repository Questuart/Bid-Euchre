"""Tests for _run_with_pty — real subprocess execution, no mocks.

These tests exercise the actual PTY subprocess wrapper to verify
timeout behavior, output capture, and process cleanup.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Add scripts/internal to path for imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from codex_plan_review_adapter import _run_with_pty


class TestPTYBasic:
    """Basic PTY functionality: run a command, capture output."""

    def test_echo_captures_output(self):
        """Simple echo command produces output and exit code 0."""
        rc, output = _run_with_pty(["echo", "hello"], timeout=10)
        assert rc == 0
        assert "hello" in output

    def test_exit_code_propagated(self):
        """Non-zero exit code is returned correctly."""
        rc, output = _run_with_pty(["sh", "-c", "exit 42"], timeout=10)
        assert rc == 42

    def test_stderr_captured(self):
        """stderr output is captured through the PTY."""
        rc, output = _run_with_pty(
            ["sh", "-c", "echo error >&2"],
            timeout=10,
        )
        assert rc == 0
        assert "error" in output


class TestPTYTimeout:
    """Timeout behavior: process killed, partial output captured."""

    def test_timeout_kills_process(self):
        """A long-running command is killed when timeout expires."""
        start = time.monotonic()
        rc, output = _run_with_pty(["sleep", "30"], timeout=2)
        elapsed = time.monotonic() - start

        assert rc is None  # None = killed by timeout
        assert elapsed < 5  # Should complete in ~2s, not 30s

    def test_timeout_captures_partial_output(self):
        """Output produced before timeout is captured."""
        rc, output = _run_with_pty(
            ["sh", "-c", "echo before_timeout; sleep 30"],
            timeout=2,
        )
        assert rc is None
        assert "before_timeout" in output

    def test_fast_command_no_timeout(self):
        """A fast command completes well within timeout."""
        start = time.monotonic()
        rc, output = _run_with_pty(["echo", "fast"], timeout=60)
        elapsed = time.monotonic() - start

        assert rc == 0
        assert "fast" in output
        assert elapsed < 5  # Should be near-instant


class TestPTYEdgeCases:
    """Edge cases for PTY subprocess handling."""

    def test_command_not_found(self):
        """Non-existent command raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _run_with_pty(["nonexistent_command_xyz"], timeout=5)

    def test_empty_output_command(self):
        """Command that produces no output returns empty string."""
        rc, output = _run_with_pty(["true"], timeout=10)
        assert rc == 0
        # PTY may add minimal whitespace but no substantive content
        assert len(output.strip()) == 0 or output.strip() == ""

    def test_multiline_output(self):
        """Multi-line output is captured correctly."""
        rc, output = _run_with_pty(
            ["sh", "-c", "echo line1; echo line2; echo line3"],
            timeout=10,
        )
        assert rc == 0
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output
