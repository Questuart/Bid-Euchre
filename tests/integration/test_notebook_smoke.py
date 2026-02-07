"""Integration tests for notebook execution in SMOKE mode.

These tests actually execute notebooks with papermill — they're slow
(~10-30s each) and marked @pytest.mark.slow to exclude from the fast suite.

Run explicitly: pytest tests/integration/test_notebook_smoke.py -v -m slow
"""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.run_notebooks import discover_notebooks, execute_notebook


@pytest.mark.slow
class TestNotebookSmoke:
    """Execute real notebooks in SMOKE mode and validate results."""

    @pytest.fixture(autouse=True)
    def setup_notebooks(self):
        """Discover notebooks once per test class."""
        self.notebooks = discover_notebooks("notebooks/phase0_bidless/*.ipynb")
        assert len(self.notebooks) >= 1, "No notebooks found for smoke test"

    def test_all_notebooks_execute_successfully(self):
        """All phase0_bidless notebooks should execute without errors in SMOKE mode."""
        with tempfile.TemporaryDirectory(prefix="nb_smoke_") as tmpdir:
            output_dir = Path(tmpdir)
            failures = []

            for nb_path in self.notebooks:
                success, message, duration = execute_notebook(
                    nb_path, "smoke", output_dir
                )
                if not success:
                    failures.append(f"{nb_path.name}: {message}")

            assert failures == [], "Notebook execution failures:\n" + "\n".join(
                failures
            )

    def test_mode_injection_produces_injected_cell(self):
        """Executed notebooks should have an injected-parameters cell with MODE."""
        with tempfile.TemporaryDirectory(prefix="nb_smoke_") as tmpdir:
            output_dir = Path(tmpdir)
            nb_path = self.notebooks[0]

            success, _, _ = execute_notebook(nb_path, "smoke", output_dir)
            assert success, f"Notebook {nb_path.name} failed to execute"

            output_nb = output_dir / nb_path.name
            assert output_nb.exists(), f"Output notebook not created: {output_nb}"

            nb = json.loads(output_nb.read_text())
            injected_cells = [
                cell
                for cell in nb.get("cells", [])
                if "injected-parameters" in cell.get("metadata", {}).get("tags", [])
            ]
            assert (
                len(injected_cells) >= 1
            ), "No injected-parameters cell found in executed notebook"

            # Verify MODE was set to SMOKE
            source = "".join(injected_cells[0].get("source", []))
            assert (
                "SMOKE" in source
            ), f"MODE not set to SMOKE in injected cell: {source[:100]}"

    def test_gate_artifact_generation(self):
        """Gate artifacts should be generated correctly for SMOKE runs."""
        from scripts.run_notebooks import build_gate_artifact

        with tempfile.TemporaryDirectory(prefix="nb_smoke_") as tmpdir:
            output_dir = Path(tmpdir)
            results = []

            for nb_path in self.notebooks:
                success, message, duration = execute_notebook(
                    nb_path, "smoke", output_dir
                )
                results.append((nb_path.name, success, message, duration))

            gate = build_gate_artifact(results, "smoke")

            assert gate["mode"] == "smoke"
            assert gate["total"] == len(self.notebooks)
            assert gate["schema_version"] == 1
            # All notebooks should pass in SMOKE mode
            assert (
                gate["gate_status"] == "PASS"
            ), f"Gate failed: {[nb for nb in gate['notebooks'] if nb['status'] == 'FAIL']}"
