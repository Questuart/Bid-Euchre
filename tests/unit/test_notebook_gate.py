"""
Unit tests for notebook gate artifact generation.

Tests:
- Gate JSON structure and fields
- Pass/fail counting
- Markdown generation
- Backward compat (no --gate-output-dir = no artifacts)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from run_notebooks import build_gate_json, build_gate_markdown, write_gate_artifacts


class TestBuildGateJson:
    """Test build_gate_json structure and counting."""

    def test_all_pass(self) -> None:
        results = [
            ("10_health.ipynb", True, "OK", 3.2),
            ("20_outcome.ipynb", True, "OK", 5.1),
        ]
        gate = build_gate_json(results, "smoke")

        assert gate["gate_type"] == "notebook_execution"
        assert gate["gate_version"] == 1
        assert gate["mode"] == "smoke"
        assert gate["overall_status"] == "PASS"
        assert gate["pass_count"] == 2
        assert gate["fail_count"] == 0
        assert len(gate["notebooks"]) == 2
        assert gate["notebooks"][0]["name"] == "10_health.ipynb"
        assert gate["notebooks"][0]["status"] == "PASS"
        assert gate["notebooks"][0]["error"] is None
        assert "timestamp_utc" in gate
        assert "git_sha" in gate

    def test_one_failure(self) -> None:
        results = [
            ("10_health.ipynb", True, "OK", 3.0),
            ("20_outcome.ipynb", False, "AssertionError: bad", 1.5),
        ]
        gate = build_gate_json(results, "quick")

        assert gate["overall_status"] == "FAIL"
        assert gate["pass_count"] == 1
        assert gate["fail_count"] == 1
        assert gate["notebooks"][1]["status"] == "FAIL"
        assert gate["notebooks"][1]["error"] == "AssertionError: bad"

    def test_all_fail(self) -> None:
        results = [
            ("10_health.ipynb", False, "Error 1", 0.5),
            ("20_outcome.ipynb", False, "Error 2", 0.3),
        ]
        gate = build_gate_json(results, "smoke")

        assert gate["overall_status"] == "FAIL"
        assert gate["pass_count"] == 0
        assert gate["fail_count"] == 2

    def test_empty_results(self) -> None:
        gate = build_gate_json([], "smoke")

        assert gate["overall_status"] == "PASS"
        assert gate["pass_count"] == 0
        assert gate["fail_count"] == 0
        assert gate["notebooks"] == []

    def test_duration_rounded(self) -> None:
        results = [("nb.ipynb", True, "OK", 3.14159)]
        gate = build_gate_json(results, "smoke")
        assert gate["notebooks"][0]["duration_sec"] == 3.14

    def test_mode_preserved(self) -> None:
        gate = build_gate_json([], "quick")
        assert gate["mode"] == "quick"


class TestBuildGateMarkdown:
    """Test NOTEBOOK_GATE.md generation."""

    def test_contains_header_and_status(self) -> None:
        gate = build_gate_json(
            [("nb.ipynb", True, "OK", 1.0)], "smoke"
        )
        md = build_gate_markdown(gate)
        assert "# Notebook Gate" in md
        assert "SMOKE" in md
        assert "**Status**: PASS" in md

    def test_contains_table(self) -> None:
        gate = build_gate_json(
            [("10_health.ipynb", True, "OK", 3.0)], "smoke"
        )
        md = build_gate_markdown(gate)
        assert "| 10_health.ipynb | PASS | 3.0s |" in md

    def test_failure_shows_errors_section(self) -> None:
        gate = build_gate_json(
            [("nb.ipynb", False, "ImportError: no pandas", 0.5)], "quick"
        )
        md = build_gate_markdown(gate)
        assert "## Errors" in md
        assert "ImportError: no pandas" in md

    def test_no_errors_section_when_all_pass(self) -> None:
        gate = build_gate_json(
            [("nb.ipynb", True, "OK", 1.0)], "smoke"
        )
        md = build_gate_markdown(gate)
        assert "## Errors" not in md


class TestWriteGateArtifacts:
    """Test file writing."""

    def test_creates_files(self, tmp_path: Path) -> None:
        results = [("nb.ipynb", True, "OK", 1.0)]
        write_gate_artifacts(results, "smoke", str(tmp_path))

        json_path = tmp_path / "notebook_gate.json"
        md_path = tmp_path / "NOTEBOOK_GATE.md"

        assert json_path.exists()
        assert md_path.exists()

        gate = json.loads(json_path.read_text())
        assert gate["gate_type"] == "notebook_execution"
        assert gate["overall_status"] == "PASS"

        md = md_path.read_text()
        assert "# Notebook Gate" in md

    def test_creates_missing_directory(self, tmp_path: Path) -> None:
        nested_dir = tmp_path / "a" / "b" / "c"
        results = [("nb.ipynb", True, "OK", 1.0)]
        write_gate_artifacts(results, "smoke", str(nested_dir))

        assert (nested_dir / "notebook_gate.json").exists()
        assert (nested_dir / "NOTEBOOK_GATE.md").exists()

    def test_json_is_valid(self, tmp_path: Path) -> None:
        results = [
            ("10.ipynb", True, "OK", 2.5),
            ("20.ipynb", False, "Error", 1.0),
        ]
        write_gate_artifacts(results, "quick", str(tmp_path))

        gate = json.loads((tmp_path / "notebook_gate.json").read_text())
        assert gate["pass_count"] == 1
        assert gate["fail_count"] == 1
        assert gate["overall_status"] == "FAIL"
