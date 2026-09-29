"""Papermill mode injection must control the actual dataset size."""

from pathlib import Path

import pytest
from papermill.iorw import load_notebook_node
from papermill.parameterize import parameterize_notebook

NOTEBOOKS = Path(__file__).resolve().parents[2] / "notebooks/phase0_bidless"


@pytest.mark.parametrize("mode", ["SMOKE", "QUICK", "FULL"])
@pytest.mark.parametrize(
    "name,variable,sizes",
    [
        (
            "10_feature_health_checks",
            "DEMO_N_DEALS",
            {"SMOKE": 100, "QUICK": 2000, "FULL": 50000},
        ),
        (
            "30_feature_outcome_eval",
            "N_DEALS",
            {"SMOKE": 100, "QUICK": 1000, "FULL": 10000},
        ),
    ],
)
def test_injected_mode_controls_derived_sample_size(name, variable, sizes, mode):
    notebook = load_notebook_node(str(NOTEBOOKS / f"{name}.ipynb"))
    injected = parameterize_notebook(notebook, {"MODE": mode})
    namespace = {}
    for cell in injected.cells:
        if cell.cell_type == "code":
            exec(cell.source, namespace)
        if variable in namespace:
            break
    assert namespace["MODE"] == mode
    assert namespace[variable] == sizes[mode]
