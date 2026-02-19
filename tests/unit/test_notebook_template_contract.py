"""Static contract tests for the model-rung notebook template.

These tests validate the template's structural contract by reading the
.py source file directly — no notebook execution required.
"""

from pathlib import Path

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "notebooks"
    / "_templates"
    / "01_model_rung_template.py"
)

REQUIRED_PARAMETERS = [
    "MODE",
    "SEED",
    "SPLIT_TYPE",
    "ACTIVE_SPLIT",
    "MODEL_ARTIFACT_PATH",
    "SEMANTIC_GATE_OUTPUT_DIR",
    "CHART_OUTPUT_DIR",
    "RUN_DIR",
    "SPLIT_MANIFEST_PATH",
]

REQUIRED_SECTIONS = [
    "§0 Imports",
    "§1 Data Loading",
    "§2 Fairness",
    "§3 Directional Sanity",
    "§4 Performance",
    "§5 Feature",
    "§6 Semantic Gate",
    "§7 Summary",
]

REQUIRED_CHART_FILENAMES = [
    "seat_balance_boxplot.png",
    "pred_vs_actual_scatter.png",
    "residual_distribution.png",
]


class TestNotebookTemplateContract:
    def test_required_parameters_present(self):
        source = TEMPLATE_PATH.read_text()
        for param in REQUIRED_PARAMETERS:
            assert param in source, f"Missing parameter: {param}"

    def test_required_section_headers_present_and_ordered(self):
        source = TEMPLATE_PATH.read_text()
        last_pos = -1
        for section in REQUIRED_SECTIONS:
            pos = source.find(section)
            assert pos != -1, f"Missing section: {section}"
            assert (
                pos > last_pos
            ), f"Section {section} is out of order (pos={pos}, last={last_pos})"
            last_pos = pos

    def test_required_chart_filenames_referenced(self):
        source = TEMPLATE_PATH.read_text()
        for filename in REQUIRED_CHART_FILENAMES:
            assert filename in source, f"Missing chart filename reference: {filename}"
