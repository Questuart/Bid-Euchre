"""Tests for notebook execution logic in scripts/run_notebooks.py.

Covers discover_notebooks, execute_notebook, and main() CLI behavior.
Gate artifact tests are in test_notebook_gate.py (no duplication here).
"""

import json
from pathlib import Path
from unittest.mock import patch

import papermill
import pytest

from scripts.run_notebooks import discover_notebooks, execute_notebook

# ---------------------------------------------------------------------------
# discover_notebooks
# ---------------------------------------------------------------------------


class TestDiscoverNotebooks:
    """Tests for notebook discovery and filtering."""

    def test_discovers_real_notebooks(self):
        """Should find the actual phase0_bidless notebooks."""
        notebooks = discover_notebooks("notebooks/phase0_bidless/*.ipynb")
        assert len(notebooks) >= 1
        assert all(nb.suffix == ".ipynb" for nb in notebooks)

    def test_excludes_archive_directory(self):
        """Notebooks under archive/ subdirectory should be excluded."""
        fake_glob_results = [
            "/repo/notebooks/phase0_bidless/10_test.ipynb",
            "/repo/notebooks/phase0_bidless/20_test.ipynb",
            "/repo/notebooks/phase0_bidless/archive/old_test.ipynb",
        ]
        with patch("scripts.run_notebooks.glob.glob", return_value=fake_glob_results):
            notebooks = discover_notebooks("notebooks/phase0_bidless/*.ipynb")

        names = [nb.name for nb in notebooks]
        assert "10_test.ipynb" in names
        assert "20_test.ipynb" in names
        assert "old_test.ipynb" not in names

    def test_returns_sorted_paths(self):
        """Discovered notebooks should be sorted by path."""
        notebooks = discover_notebooks("notebooks/phase0_bidless/*.ipynb")
        names = [nb.name for nb in notebooks]
        assert names == sorted(names)

    def test_returns_path_objects(self):
        """Discovered items should be Path objects."""
        notebooks = discover_notebooks("notebooks/phase0_bidless/*.ipynb")
        assert all(isinstance(nb, Path) for nb in notebooks)

    def test_no_match_returns_empty(self):
        """Non-matching pattern should return empty list."""
        notebooks = discover_notebooks("notebooks/nonexistent_dir/*.ipynb")
        assert notebooks == []


# ---------------------------------------------------------------------------
# execute_notebook
# ---------------------------------------------------------------------------


class TestExecuteNotebook:
    """Tests for single notebook execution with papermill."""

    @patch("papermill.execute_notebook")
    def test_successful_execution(self, mock_exec, tmp_path):
        """Successful papermill execution returns (True, 'OK', duration)."""
        mock_exec.return_value = None

        nb_path = Path("notebooks/phase0_bidless/10_test.ipynb")
        success, message, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert success is True
        assert message == "OK"
        assert isinstance(duration, float)
        assert duration >= 0

    @patch("papermill.execute_notebook")
    def test_mode_mapping_smoke(self, mock_exec, tmp_path):
        """smoke mode should inject MODE='SMOKE' parameter."""
        nb_path = Path("notebooks/test.ipynb")
        execute_notebook(nb_path, "smoke", tmp_path)

        call_kwargs = mock_exec.call_args[1]
        assert call_kwargs["parameters"] == {"MODE": "SMOKE"}

    @patch("papermill.execute_notebook")
    def test_mode_mapping_quick(self, mock_exec, tmp_path):
        """quick mode should inject MODE='QUICK' parameter."""
        nb_path = Path("notebooks/test.ipynb")
        execute_notebook(nb_path, "quick", tmp_path)

        call_kwargs = mock_exec.call_args[1]
        assert call_kwargs["parameters"] == {"MODE": "QUICK"}

    @patch("papermill.execute_notebook")
    def test_output_path_in_output_dir(self, mock_exec, tmp_path):
        """Output notebook should be placed in output_dir with same name."""
        nb_path = Path("notebooks/phase0_bidless/10_test.ipynb")
        execute_notebook(nb_path, "smoke", tmp_path)

        call_args = mock_exec.call_args[0]
        output_path = call_args[1]
        assert output_path == str(tmp_path / "10_test.ipynb")

    @patch("papermill.execute_notebook")
    def test_uses_python3_kernel(self, mock_exec, tmp_path):
        """Should explicitly request python3 kernel."""
        nb_path = Path("notebooks/test.ipynb")
        execute_notebook(nb_path, "smoke", tmp_path)

        call_kwargs = mock_exec.call_args[1]
        assert call_kwargs["kernel_name"] == "python3"

    @patch("papermill.execute_notebook")
    def test_papermill_execution_error(self, mock_exec, tmp_path):
        """PapermillExecutionError should return (False, truncated_msg, duration)."""
        mock_exec.side_effect = papermill.PapermillExecutionError(
            cell_index=0,
            exec_count=1,
            source="x = 1/0",
            ename="ZeroDivisionError",
            evalue="division by zero",
            traceback=["Cell failed\nTraceback line 1\nline 2"],
        )

        nb_path = Path("notebooks/test.ipynb")
        success, message, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert success is False
        assert len(message) <= 200
        assert isinstance(duration, float)

    @patch("papermill.execute_notebook")
    def test_generic_exception(self, mock_exec, tmp_path):
        """Generic exceptions should return (False, truncated_msg, duration)."""
        mock_exec.side_effect = RuntimeError("Kernel died")

        nb_path = Path("notebooks/test.ipynb")
        success, message, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert success is False
        assert "Kernel died" in message
        assert isinstance(duration, float)

    @patch("papermill.execute_notebook")
    def test_error_message_truncated_to_200(self, mock_exec, tmp_path):
        """Long error messages should be truncated to 200 chars."""
        long_msg = "x" * 500
        mock_exec.side_effect = RuntimeError(long_msg)

        nb_path = Path("notebooks/test.ipynb")
        success, message, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert success is False
        assert len(message) <= 200

    @patch("papermill.execute_notebook")
    def test_duration_tracked_on_success(self, mock_exec, tmp_path):
        """Duration should be a positive float on success."""
        mock_exec.return_value = None

        nb_path = Path("notebooks/test.ipynb")
        _, _, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert duration >= 0

    @patch("papermill.execute_notebook")
    def test_duration_tracked_on_failure(self, mock_exec, tmp_path):
        """Duration should still be tracked even on failure."""
        mock_exec.side_effect = RuntimeError("boom")

        nb_path = Path("notebooks/test.ipynb")
        _, _, duration = execute_notebook(nb_path, "smoke", tmp_path)

        assert duration >= 0


# ---------------------------------------------------------------------------
# main() CLI behavior
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for main() CLI entry point."""

    @patch("scripts.run_notebooks.execute_notebook")
    @patch("scripts.run_notebooks.discover_notebooks")
    def test_exit_0_on_all_pass(self, mock_discover, mock_execute):
        """main() should exit 0 when all notebooks pass."""
        mock_discover.return_value = [Path("notebooks/10_test.ipynb")]
        mock_execute.return_value = (True, "OK", 1.0)

        with patch("sys.argv", ["run_notebooks.py", "--mode", "smoke"]):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.run_notebooks import main

                main()
            assert exc_info.value.code == 0

    @patch("scripts.run_notebooks.execute_notebook")
    @patch("scripts.run_notebooks.discover_notebooks")
    def test_exit_1_on_any_failure(self, mock_discover, mock_execute):
        """main() should exit 1 when any notebook fails."""
        mock_discover.return_value = [
            Path("notebooks/10_test.ipynb"),
            Path("notebooks/20_test.ipynb"),
        ]
        mock_execute.side_effect = [
            (True, "OK", 1.0),
            (False, "Error: cell failed", 2.0),
        ]

        with patch("sys.argv", ["run_notebooks.py", "--mode", "smoke"]):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.run_notebooks import main

                main()
            assert exc_info.value.code == 1

    @patch("scripts.run_notebooks.execute_notebook")
    @patch("scripts.run_notebooks.discover_notebooks")
    def test_exit_0_on_no_notebooks(self, mock_discover, mock_execute):
        """main() should exit 0 when no notebooks are found."""
        mock_discover.return_value = []

        with patch("sys.argv", ["run_notebooks.py", "--mode", "smoke"]):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.run_notebooks import main

                main()
            assert exc_info.value.code == 0

    @patch("scripts.run_notebooks.execute_notebook")
    @patch("scripts.run_notebooks.discover_notebooks")
    def test_gate_artifact_emitted(self, mock_discover, mock_execute, tmp_path):
        """--gate-output-dir should emit notebook_gate.json and NOTEBOOK_GATE.md."""
        mock_discover.return_value = [Path("notebooks/10_test.ipynb")]
        mock_execute.return_value = (True, "OK", 1.0)

        gate_dir = tmp_path / "gate"
        with patch(
            "sys.argv",
            [
                "run_notebooks.py",
                "--mode",
                "smoke",
                "--gate-output-dir",
                str(gate_dir),
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.run_notebooks import main

                main()
            assert exc_info.value.code == 0

        assert (gate_dir / "notebook_gate.json").exists()
        assert (gate_dir / "NOTEBOOK_GATE.md").exists()

        gate = json.loads((gate_dir / "notebook_gate.json").read_text())
        assert gate["gate_status"] == "PASS"
        assert gate["total"] == 1

    @patch("scripts.run_notebooks.execute_notebook")
    @patch("scripts.run_notebooks.discover_notebooks")
    def test_mode_passed_to_execute(self, mock_discover, mock_execute):
        """CLI --mode should be passed through to execute_notebook."""
        mock_discover.return_value = [Path("notebooks/10_test.ipynb")]
        mock_execute.return_value = (True, "OK", 1.0)

        with patch("sys.argv", ["run_notebooks.py", "--mode", "quick"]):
            with pytest.raises(SystemExit):
                from scripts.run_notebooks import main

                main()

        call_args = mock_execute.call_args
        assert call_args[0][1] == "quick"  # mode argument
