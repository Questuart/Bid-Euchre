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
    "EVAL_RUN_DIR",
    "ARTIFACT_DIR",
    "RUNG_ID",
    "CHART_OUTPUT_DIR",
    "PROMOTION_DECISION_PATH",
]

REQUIRED_SECTIONS = [
    "§0 Setup",
    "§1 Deal Health",
    "§2 Auction Health",
    "§3 Gameplay Health",
    "§4 Auction Outcomes",
    "§5 Gameplay Outcomes",
    "§6 Model Specs",
    "§7 Model Performance",
    "§8 Dual-Arm",
    "§9 Seed Sensitivity",
    "§10 Promotion",
]

REQUIRED_CHART_FILENAMES = [
    "seat_balance_boxplot.png",
    "pred_vs_actual_scatter.png",
    "residual_distribution.png",
    "dual_arm_comparison.png",
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

    def test_eval_dataset_import_present(self):
        """Template must import from the JSONL eval dataset parser."""
        source = TEMPLATE_PATH.read_text()
        assert (
            "build_eval_dataset" in source
        ), "Template must import build_eval_dataset from eval_dataset module"

    def test_removed_parameters_absent(self):
        """Old parameters that were removed should not appear in the template."""
        source = TEMPLATE_PATH.read_text()
        removed = [
            "SPLIT_TYPE",
            "ACTIVE_SPLIT",
            "MODEL_ARTIFACT_PATH",
            "SEMANTIC_GATE_OUTPUT_DIR",
            "SPLIT_MANIFEST_PATH",
        ]
        # Check parameter declarations (not just any mention in comments)
        lines = source.split("\n")
        param_lines = [l for l in lines if "=" in l and not l.strip().startswith("#")]
        param_text = "\n".join(param_lines)
        for param in removed:
            assert (
                f"{param} =" not in param_text
            ), f"Removed parameter {param} should not be declared"
