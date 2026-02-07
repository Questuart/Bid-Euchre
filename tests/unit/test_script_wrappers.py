"""Tests for deprecation wrappers that forward to scripts/internal/."""

import subprocess
import sys

WRAPPER_SCRIPTS = [
    "scripts/run_auction_comparator.py",
    "scripts/play_policy_gate.py",
    "scripts/evaluate_diagnostic_tricks.py",
]


def test_wrappers_emit_deprecation_warning():
    """Old-path wrappers should emit DeprecationWarning."""
    for script in WRAPPER_SCRIPTS:
        result = subprocess.run(
            [sys.executable, "-W", "all", script, "--help"],
            capture_output=True,
            text=True,
        )
        # The wrapper forwards to the real script, which may succeed or fail
        # depending on args. What matters is the deprecation warning was emitted.
        assert "has moved to scripts/internal/" in result.stderr, (
            f"{script} did not emit deprecation warning. stderr: {result.stderr[:200]}"
        )


def test_wrappers_forward_help_flag():
    """Old-path wrappers should forward --help to the internal script."""
    for script in WRAPPER_SCRIPTS:
        result = subprocess.run(
            [sys.executable, "-W", "all", script, "--help"],
            capture_output=True,
            text=True,
        )
        # The internal script should respond to --help with usage info
        assert "usage:" in result.stdout.lower() or "optional arguments" in result.stdout.lower() or "options:" in result.stdout.lower(), (
            f"{script} --help did not produce usage info. stdout: {result.stdout[:200]}"
        )


def test_internal_scripts_exist():
    """The actual scripts should exist at their new internal/ paths."""
    from pathlib import Path

    for script in WRAPPER_SCRIPTS:
        internal_path = Path(script.replace("scripts/", "scripts/internal/"))
        assert internal_path.exists(), f"Internal script not found: {internal_path}"
