"""Verify compact-context.sh re-injects the correct default validation command."""

from __future__ import annotations

import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def test_compact_context_mentions_check_gated():
    """Compact context should recommend make check-gated (not check-quiet) as
    the default validation command, matching the fleet convention."""
    result = subprocess.run(
        ["bash", str(HOOKS_DIR / "compact-context.sh")],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert (
        "make check-gated" in result.stdout
    ), "compact-context.sh should mention make check-gated as the default"
