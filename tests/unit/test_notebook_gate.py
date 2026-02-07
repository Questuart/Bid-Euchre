"""Tests for notebook gate artifact generation."""

import importlib.util
import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def run_notebooks_mod():
    """Import run_notebooks.py as a module."""
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts", "run_notebooks.py"
    )
    spec = importlib.util.spec_from_file_location("run_notebooks", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gate_json_all_pass(tmp_path, run_notebooks_mod):
    """Gate JSON has correct structure when all notebooks pass."""
    results = [
        ("nb1.ipynb", True, "OK", 1.5),
        ("nb2.ipynb", True, "OK", 2.3),
    ]

    with patch.object(run_notebooks_mod, "utc_now_iso", return_value="2026-02-10T12:00:00Z"), \
         patch.object(run_notebooks_mod, "get_git_sha", return_value="abc1234"):
        gate = run_notebooks_mod.write_gate_artifacts(tmp_path, "smoke", results)

    assert gate["gate_type"] == "notebook_execution"
    assert gate["gate_version"] == 1
    assert gate["mode"] == "smoke"
    assert gate["overall_status"] == "PASS"
    assert gate["pass_count"] == 2
    assert gate["fail_count"] == 0
    assert len(gate["notebooks"]) == 2
    assert gate["notebooks"][0]["status"] == "PASS"
    assert gate["notebooks"][0]["error"] is None

    # Verify file was written correctly
    loaded = json.loads((tmp_path / "notebook_gate.json").read_text())
    assert loaded == gate


def test_gate_json_with_failure(tmp_path, run_notebooks_mod):
    """Gate JSON correctly records failures."""
    results = [
        ("nb1.ipynb", True, "OK", 1.5),
        ("nb2.ipynb", False, "NameError: foo", 0.8),
    ]

    with patch.object(run_notebooks_mod, "utc_now_iso", return_value="2026-02-10T12:00:00Z"), \
         patch.object(run_notebooks_mod, "get_git_sha", return_value="abc1234"):
        gate = run_notebooks_mod.write_gate_artifacts(tmp_path, "quick", results)

    assert gate["overall_status"] == "FAIL"
    assert gate["pass_count"] == 1
    assert gate["fail_count"] == 1
    assert gate["notebooks"][1]["status"] == "FAIL"
    assert gate["notebooks"][1]["error"] == "NameError: foo"


def test_gate_markdown_content(tmp_path, run_notebooks_mod):
    """NOTEBOOK_GATE.md has expected content."""
    results = [
        ("nb1.ipynb", True, "OK", 1.5),
        ("nb2.ipynb", False, "Error msg", 0.8),
    ]

    with patch.object(run_notebooks_mod, "utc_now_iso", return_value="2026-02-10T12:00:00Z"), \
         patch.object(run_notebooks_mod, "get_git_sha", return_value="abc1234"):
        run_notebooks_mod.write_gate_artifacts(tmp_path, "smoke", results)

    content = (tmp_path / "NOTEBOOK_GATE.md").read_text()
    assert "# Notebook Execution Gate" in content
    assert "SMOKE" in content
    assert "nb1.ipynb" in content
    assert "nb2.ipynb" in content
    assert "1 passed, 1 failed" in content


def test_gate_creates_nested_directory(tmp_path, run_notebooks_mod):
    """Gate writing creates nested output directory."""
    nested = tmp_path / "a" / "b"
    results = [("nb1.ipynb", True, "OK", 1.0)]

    with patch.object(run_notebooks_mod, "utc_now_iso", return_value="2026-02-10T12:00:00Z"), \
         patch.object(run_notebooks_mod, "get_git_sha", return_value="abc1234"):
        run_notebooks_mod.write_gate_artifacts(nested, "smoke", results)

    assert (nested / "notebook_gate.json").exists()
    assert (nested / "NOTEBOOK_GATE.md").exists()


def test_gate_empty_results(tmp_path, run_notebooks_mod):
    """Gate handles empty results list."""
    with patch.object(run_notebooks_mod, "utc_now_iso", return_value="2026-02-10T12:00:00Z"), \
         patch.object(run_notebooks_mod, "get_git_sha", return_value="abc1234"):
        gate = run_notebooks_mod.write_gate_artifacts(tmp_path, "smoke", [])

    assert gate["overall_status"] == "PASS"
    assert gate["pass_count"] == 0
    assert gate["fail_count"] == 0
    assert gate["notebooks"] == []
