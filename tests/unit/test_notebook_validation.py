"""Tests for notebook validation utilities."""

import json

from bid_euchre.diagnostics.notebook_validation import (
    ValidationResult,
    check_mode_parameter,
    extract_cell_errors,
    validate_notebook,
    validate_notebook_schema,
)


def _make_notebook(cells=None, nbformat=4, nbformat_minor=5):
    """Build a minimal valid notebook dict."""
    return {
        "cells": cells or [],
        "metadata": {},
        "nbformat": nbformat,
        "nbformat_minor": nbformat_minor,
    }


def _make_code_cell(source, tags=None, outputs=None):
    """Build a code cell dict."""
    return {
        "cell_type": "code",
        "source": [source],
        "metadata": {"tags": tags or []},
        "outputs": outputs or [],
    }


def _make_markdown_cell(source):
    """Build a markdown cell dict."""
    return {
        "cell_type": "markdown",
        "source": [source],
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# validate_notebook_schema
# ---------------------------------------------------------------------------


class TestValidateNotebookSchema:
    def test_valid_notebook(self):
        nb = _make_notebook(cells=[_make_markdown_cell("# Title")])
        assert validate_notebook_schema(nb) == []

    def test_missing_cells_key(self):
        nb = {"metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        errors = validate_notebook_schema(nb)
        assert any("cells" in e for e in errors)

    def test_missing_metadata_key(self):
        nb = {"cells": [], "nbformat": 4, "nbformat_minor": 5}
        errors = validate_notebook_schema(nb)
        assert any("metadata" in e for e in errors)

    def test_empty_cells(self):
        nb = _make_notebook(cells=[])
        errors = validate_notebook_schema(nb)
        assert any("no cells" in e for e in errors)

    def test_old_nbformat_rejected(self):
        nb = _make_notebook(cells=[_make_markdown_cell("x")], nbformat=3)
        errors = validate_notebook_schema(nb)
        assert any("nbformat" in e.lower() for e in errors)

    def test_cells_not_list(self):
        nb = _make_notebook()
        nb["cells"] = "not a list"
        errors = validate_notebook_schema(nb)
        assert any("not a list" in e for e in errors)


# ---------------------------------------------------------------------------
# check_mode_parameter
# ---------------------------------------------------------------------------


class TestCheckModeParameter:
    def test_valid_parameters_cell(self):
        cells = [
            _make_code_cell('MODE = "QUICK"\nDEMO_SEED = 42', tags=["parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        assert check_mode_parameter(nb) == []

    def test_no_parameters_cell(self):
        cells = [_make_code_cell("x = 1")]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb)
        assert any("parameters" in e for e in errors)

    def test_parameters_cell_missing_mode(self):
        cells = [_make_code_cell("SEED = 42", tags=["parameters"])]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb)
        assert any("MODE" in e for e in errors)

    def test_expected_mode_with_injection(self):
        cells = [
            _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
            _make_code_cell('MODE = "SMOKE"', tags=["injected-parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        assert check_mode_parameter(nb, expected_mode="SMOKE") == []

    def test_expected_mode_mismatch(self):
        cells = [
            _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
            _make_code_cell('MODE = "QUICK"', tags=["injected-parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb, expected_mode="SMOKE")
        assert any("SMOKE" in e for e in errors)

    def test_missing_injection_when_expected(self):
        cells = [_make_code_cell('MODE = "QUICK"', tags=["parameters"])]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb, expected_mode="SMOKE")
        assert any("injected-parameters" in e for e in errors)

    def test_injected_cell_no_mode_assignment(self):
        """injected-parameters cell with no MODE line should fail when expected_mode set."""
        cells = [
            _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
            _make_code_cell("SEED = 42", tags=["injected-parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb, expected_mode="SMOKE")
        assert any("not found or unparseable" in e for e in errors)

    def test_injected_cell_malformed_mode(self):
        """injected-parameters cell with malformed MODE should fail when expected_mode set."""
        cells = [
            _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
            # MODE without = is not parseable
            _make_code_cell("SOMETHING_ELSE = 1", tags=["injected-parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        errors = check_mode_parameter(nb, expected_mode="SMOKE")
        assert any("not found or unparseable" in e for e in errors)

    def test_injected_cell_no_mode_no_expected(self):
        """injected-parameters cell with no MODE should pass when no expected_mode."""
        cells = [
            _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
            _make_code_cell("SEED = 42", tags=["injected-parameters"]),
        ]
        nb = _make_notebook(cells=cells)
        # No expected_mode → no strict check on injected cell content
        errors = check_mode_parameter(nb)
        assert errors == []


# ---------------------------------------------------------------------------
# extract_cell_errors
# ---------------------------------------------------------------------------


class TestExtractCellErrors:
    def test_no_errors(self):
        cells = [_make_code_cell("x = 1", outputs=[{"output_type": "execute_result"}])]
        nb = _make_notebook(cells=cells)
        assert extract_cell_errors(nb) == []

    def test_single_error(self):
        error_output = {
            "output_type": "error",
            "ename": "ZeroDivisionError",
            "evalue": "division by zero",
            "traceback": ["..."],
        }
        cells = [_make_code_cell("1/0", outputs=[error_output])]
        nb = _make_notebook(cells=cells)
        errors = extract_cell_errors(nb)
        assert len(errors) == 1
        assert errors[0].ename == "ZeroDivisionError"
        assert errors[0].evalue == "division by zero"
        assert errors[0].cell_index == 0

    def test_multiple_errors(self):
        error_output = {
            "output_type": "error",
            "ename": "TypeError",
            "evalue": "bad type",
            "traceback": [],
        }
        cells = [
            _make_code_cell("x()", outputs=[error_output]),
            _make_markdown_cell("# text"),
            _make_code_cell("y()", outputs=[error_output]),
        ]
        nb = _make_notebook(cells=cells)
        errors = extract_cell_errors(nb)
        assert len(errors) == 2
        assert errors[0].cell_index == 0
        assert errors[1].cell_index == 2

    def test_markdown_cells_skipped(self):
        nb = _make_notebook(cells=[_make_markdown_cell("# Title")])
        assert extract_cell_errors(nb) == []

    def test_long_evalue_truncated(self):
        error_output = {
            "output_type": "error",
            "ename": "Error",
            "evalue": "x" * 500,
            "traceback": [],
        }
        cells = [_make_code_cell("fail()", outputs=[error_output])]
        nb = _make_notebook(cells=cells)
        errors = extract_cell_errors(nb)
        assert len(errors[0].evalue) <= 200


# ---------------------------------------------------------------------------
# validate_notebook (integration)
# ---------------------------------------------------------------------------


class TestValidateNotebook:
    def test_valid_notebook(self, tmp_path):
        nb = _make_notebook(
            cells=[
                _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
                _make_code_cell("x = 1"),
            ]
        )
        path = tmp_path / "test.ipynb"
        path.write_text(json.dumps(nb))

        result = validate_notebook(path)
        assert result.ok
        assert result.path == path

    def test_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.ipynb"
        result = validate_notebook(path)
        assert not result.ok
        assert any("Failed to load" in e for e in result.errors)

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "bad.ipynb"
        path.write_text("not json{")
        result = validate_notebook(path)
        assert not result.ok

    def test_notebook_with_errors(self, tmp_path):
        error_output = {
            "output_type": "error",
            "ename": "RuntimeError",
            "evalue": "test error",
            "traceback": [],
        }
        nb = _make_notebook(
            cells=[
                _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
                _make_code_cell("bad()", outputs=[error_output]),
            ]
        )
        path = tmp_path / "test.ipynb"
        path.write_text(json.dumps(nb))

        result = validate_notebook(path)
        assert not result.ok
        assert len(result.cell_errors) == 1

    def test_expected_mode_validated(self, tmp_path):
        nb = _make_notebook(
            cells=[
                _make_code_cell('MODE = "QUICK"', tags=["parameters"]),
                _make_code_cell('MODE = "SMOKE"', tags=["injected-parameters"]),
            ]
        )
        path = tmp_path / "test.ipynb"
        path.write_text(json.dumps(nb))

        result = validate_notebook(path, expected_mode="SMOKE")
        assert result.ok

    def test_validation_result_ok_property(self):
        result = ValidationResult(path="test.ipynb")
        assert result.ok

        result.errors.append("something wrong")
        assert not result.ok
