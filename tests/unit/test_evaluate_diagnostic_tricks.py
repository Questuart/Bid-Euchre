"""
Smoke test for the diagnostic tricks evaluation script.
"""

import subprocess
import sys


class TestEvaluateDiagnosticTricks:
    """Smoke tests for the evaluate script."""

    def test_script_has_help(self):
        """Test that the script prints help without errors."""
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_diagnostic_tricks.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--greedy-dir" in result.stdout
        assert "--glutton-dir" in result.stdout
        assert "--seed" in result.stdout

    def test_script_fails_on_missing_dirs(self, tmp_path):
        """Test that the script fails gracefully with missing data dirs."""
        result = subprocess.run(
            [
                sys.executable,
                "scripts/evaluate_diagnostic_tricks.py",
                "--greedy-dir",
                str(tmp_path / "nonexistent_greedy"),
                "--glutton-dir",
                str(tmp_path / "nonexistent_glutton"),
                "--seed",
                "42",
                "--output",
                str(tmp_path / "output.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Missing" in result.stderr or "FileNotFoundError" in result.stderr
