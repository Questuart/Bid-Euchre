"""Tests for notebook gate artifact generation."""

from scripts.run_notebooks import (
    NOTEBOOK_GATE_REQUIRED_FIELDS,
    NOTEBOOK_GATE_SCHEMA_VERSION,
    NOTEBOOK_RESULT_REQUIRED_FIELDS,
    build_gate_artifact,
    build_gate_markdown,
)


def _make_results(*specs):
    """Create results list from (name, success) pairs."""
    return [
        (name, success, "OK" if success else "Error: test", 1.5)
        for name, success in specs
    ]


class TestBuildGateArtifact:
    """Tests for build_gate_artifact."""

    def test_gate_pass_all_notebooks(self):
        results = _make_results(
            ("10_seat_balance.ipynb", True),
            ("20_outcome_health.ipynb", True),
        )
        gate = build_gate_artifact(results, "smoke")
        assert gate["gate_status"] == "PASS"
        assert gate["passed"] == 2
        assert gate["failed"] == 0

    def test_gate_fail_any_notebook(self):
        results = _make_results(
            ("10_seat_balance.ipynb", True),
            ("20_outcome_health.ipynb", False),
        )
        gate = build_gate_artifact(results, "smoke")
        assert gate["gate_status"] == "FAIL"
        assert gate["passed"] == 1
        assert gate["failed"] == 1

    def test_gate_empty_results(self):
        gate = build_gate_artifact([], "smoke")
        assert gate["gate_status"] == "PASS"
        assert gate["total"] == 0
        assert gate["passed"] == 0
        assert gate["failed"] == 0
        assert gate["notebooks"] == []

    def test_gate_schema_version(self):
        gate = build_gate_artifact([], "smoke")
        assert gate["schema_version"] == NOTEBOOK_GATE_SCHEMA_VERSION

    def test_gate_has_all_required_fields(self):
        results = _make_results(("10_test.ipynb", True))
        gate = build_gate_artifact(results, "smoke")
        assert NOTEBOOK_GATE_REQUIRED_FIELDS <= set(gate.keys())

    def test_notebook_results_have_required_fields(self):
        results = _make_results(
            ("10_test.ipynb", True),
            ("20_test.ipynb", False),
        )
        gate = build_gate_artifact(results, "quick")
        for nb in gate["notebooks"]:
            assert NOTEBOOK_RESULT_REQUIRED_FIELDS <= set(
                nb.keys()
            ), f"Missing: {NOTEBOOK_RESULT_REQUIRED_FIELDS - set(nb.keys())}"

    def test_gate_mode_propagated(self):
        gate = build_gate_artifact([], "quick")
        assert gate["mode"] == "quick"

    def test_gate_created_at_utc_has_z_suffix(self):
        gate = build_gate_artifact([], "smoke")
        assert gate["created_at_utc"].endswith("Z")

    def test_gate_duration_rounded(self):
        results = [("test.ipynb", True, "OK", 1.23456)]
        gate = build_gate_artifact(results, "smoke")
        assert gate["notebooks"][0]["duration_seconds"] == 1.23

    def test_gate_fail_on_validation_failure(self):
        """Gate should be FAIL when execution passes but validation fails."""
        results = _make_results(("10_test.ipynb", True))
        validation_results = {
            "10_test.ipynb": {
                "ok": False,
                "errors": ["Cell 2: ZeroDivisionError: division by zero"],
            }
        }
        gate = build_gate_artifact(
            results, "smoke", validation_results=validation_results
        )
        assert gate["gate_status"] == "FAIL"
        assert gate["failed"] == 1
        assert gate["passed"] == 0
        nb_entry = gate["notebooks"][0]
        assert nb_entry["status"] == "FAIL"
        assert nb_entry["validation_status"] == "FAIL"
        assert "ZeroDivisionError" in nb_entry["validation_message"]

    def test_gate_pass_with_validation_pass(self):
        """Gate should be PASS when both execution and validation pass."""
        results = _make_results(("10_test.ipynb", True))
        validation_results = {
            "10_test.ipynb": {"ok": True, "errors": []},
        }
        gate = build_gate_artifact(
            results, "smoke", validation_results=validation_results
        )
        assert gate["gate_status"] == "PASS"
        assert gate["passed"] == 1
        nb_entry = gate["notebooks"][0]
        assert nb_entry["status"] == "PASS"
        assert nb_entry["validation_status"] == "PASS"

    def test_gate_no_validation_results_backward_compat(self):
        """Gate without validation_results should work as before (no validation_status key)."""
        results = _make_results(("10_test.ipynb", True))
        gate = build_gate_artifact(results, "smoke")
        nb_entry = gate["notebooks"][0]
        assert nb_entry["status"] == "PASS"
        assert "validation_status" not in nb_entry

    def test_gate_mixed_execution_and_validation_failures(self):
        """Gate counts both execution and validation failures correctly."""
        results = _make_results(
            ("10_test.ipynb", False),  # execution fail
            ("20_test.ipynb", True),  # execution pass, validation fail
            ("30_test.ipynb", True),  # all pass
        )
        validation_results = {
            "20_test.ipynb": {"ok": False, "errors": ["MODE mismatch"]},
            "30_test.ipynb": {"ok": True, "errors": []},
        }
        gate = build_gate_artifact(
            results, "smoke", validation_results=validation_results
        )
        assert gate["gate_status"] == "FAIL"
        assert gate["failed"] == 2
        assert gate["passed"] == 1


class TestBuildGateMarkdown:
    """Tests for build_gate_markdown."""

    def test_gate_markdown_format(self):
        results = _make_results(("10_test.ipynb", True))
        gate = build_gate_artifact(results, "smoke")
        md = build_gate_markdown(gate)
        assert "# Notebook Gate: PASS" in md
        assert "| Notebook | Status |" in md
        assert "10_test.ipynb" in md

    def test_gate_markdown_fail_status(self):
        results = _make_results(("10_test.ipynb", False))
        gate = build_gate_artifact(results, "smoke")
        md = build_gate_markdown(gate)
        assert "# Notebook Gate: FAIL" in md
        assert "FAIL" in md

    def test_gate_markdown_contains_mode(self):
        gate = build_gate_artifact([], "quick")
        md = build_gate_markdown(gate)
        assert "quick" in md
