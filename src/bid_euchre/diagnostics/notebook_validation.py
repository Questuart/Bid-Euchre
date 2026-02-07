"""Notebook validation utilities for post-execution checks.

Validates executed notebook structure, parameter injection, and cell errors.
Used by scripts/run_notebooks.py --validate and CI gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CellError:
    """An error found in a notebook cell."""

    cell_index: int
    ename: str
    evalue: str
    source_preview: str


@dataclass
class ValidationResult:
    """Result of validating a single notebook."""

    path: Path
    errors: list[str] = field(default_factory=list)
    cell_errors: list[CellError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0 and len(self.cell_errors) == 0


def load_notebook(path: Path) -> dict:
    """Load a notebook JSON file."""
    with open(path) as f:
        return json.load(f)


def validate_notebook_schema(nb: dict) -> list[str]:
    """Check that a notebook has the expected top-level structure.

    Returns a list of error messages (empty if valid).
    """
    errors = []
    required_keys = {"cells", "metadata", "nbformat", "nbformat_minor"}
    missing = required_keys - set(nb.keys())
    if missing:
        errors.append(f"Missing top-level keys: {sorted(missing)}")

    if "cells" in nb:
        if not isinstance(nb["cells"], list):
            errors.append("'cells' is not a list")
        elif len(nb["cells"]) == 0:
            errors.append("Notebook has no cells")

    if "nbformat" in nb and nb["nbformat"] < 4:
        errors.append(f"Unsupported nbformat version: {nb['nbformat']}")

    return errors


def check_mode_parameter(nb: dict, expected_mode: str | None = None) -> list[str]:
    """Verify the notebook has a parameters cell with MODE.

    If expected_mode is provided, also checks that MODE was set to that value.
    Papermill creates an 'injected-parameters' tagged cell after the 'parameters' cell.

    Returns a list of error messages (empty if valid).
    """
    errors = []
    has_parameters_cell = False
    has_injected_cell = False
    injected_mode = None

    for cell in nb.get("cells", []):
        tags = cell.get("metadata", {}).get("tags", [])
        source = "".join(cell.get("source", []))

        if "parameters" in tags:
            has_parameters_cell = True
            if "MODE" not in source:
                errors.append("Parameters cell does not define MODE")

        if "injected-parameters" in tags:
            has_injected_cell = True
            # Parse injected MODE value
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("MODE"):
                    # e.g. MODE = "SMOKE"
                    parts = stripped.split("=", 1)
                    if len(parts) == 2:
                        injected_mode = parts[1].strip().strip("\"'")

    if not has_parameters_cell:
        errors.append("No cell tagged 'parameters' found")

    if expected_mode and not has_injected_cell:
        errors.append(
            f"No 'injected-parameters' cell found (expected MODE={expected_mode})"
        )

    if expected_mode and injected_mode and injected_mode != expected_mode:
        errors.append(f"Injected MODE={injected_mode!r}, expected {expected_mode!r}")

    return errors


def extract_cell_errors(nb: dict) -> list[CellError]:
    """Find all cells that produced error outputs during execution.

    Returns a list of CellError objects.
    """
    cell_errors = []
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                source = "".join(cell.get("source", []))
                cell_errors.append(
                    CellError(
                        cell_index=i,
                        ename=output.get("ename", "Unknown"),
                        evalue=output.get("evalue", "")[:200],
                        source_preview=source[:100],
                    )
                )
    return cell_errors


def validate_notebook(
    path: Path,
    expected_mode: str | None = None,
) -> ValidationResult:
    """Run all validations on an executed notebook.

    Args:
        path: Path to the executed notebook (.ipynb)
        expected_mode: If provided, verify MODE was injected with this value

    Returns:
        ValidationResult with any errors found
    """
    result = ValidationResult(path=path)

    try:
        nb = load_notebook(path)
    except (json.JSONDecodeError, OSError) as e:
        result.errors.append(f"Failed to load notebook: {e}")
        return result

    result.errors.extend(validate_notebook_schema(nb))
    result.errors.extend(check_mode_parameter(nb, expected_mode))
    result.cell_errors = extract_cell_errors(nb)

    return result
