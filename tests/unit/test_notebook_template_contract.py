"""Static contract tests for the model-rung notebook template.

These tests validate the template's structural contract by reading the
.py source file directly — no notebook execution required.
"""

import re
from pathlib import Path

import pytest

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

    def test_artifact_path_bundle_key(self):
        """Template must use 'artifact_path' (not 'model_artifact') to load model."""
        source = TEMPLATE_PATH.read_text()
        # Must use the correct bundle key
        assert (
            'get("artifact_path")' in source
        ), "Template must use arm_block.get('artifact_path') for model loading"
        # Must NOT use the wrong key
        assert (
            'get("model_artifact")' not in source
        ), "Template must not reference 'model_artifact' — bundles use 'artifact_path'"

    def test_r0_baseline_has_analysis_sections(self):
        """R0 baseline notebook must contain all analysis sections (not just params)."""
        r0_path = (
            Path(__file__).resolve().parents[2]
            / "notebooks"
            / "arc_d"
            / "r0"
            / "40_r0_baseline.py"
        )
        source = r0_path.read_text()
        for section in REQUIRED_SECTIONS:
            assert section in source, (
                f"R0 baseline missing section: {section} — "
                "notebook must be a complete standalone copy of the template"
            )

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


# ──────────────────────────────────────────────
#  R0 notebook enrichment contract tests
# ──────────────────────────────────────────────

R0_PATH = (
    Path(__file__).resolve().parents[2]
    / "notebooks"
    / "arc_d"
    / "r0"
    / "40_r0_baseline.py"
)


class TestR0NotebookEnrichment:
    def test_r0_notebook_imports_diagnostics(self):
        """R0 notebook must import from bid_euchre.diagnostics for enriched analysis."""
        source = R0_PATH.read_text()
        assert (
            "from bid_euchre.diagnostics" in source
        ), "R0 notebook must import diagnostics functions"
        assert "compute_health_scorecard" in source
        assert "plot_hand_value_by_seat" in source

    def test_r0_notebook_has_health_scorecard(self):
        """§0 must call compute_health_scorecard for data quality summary."""
        source = R0_PATH.read_text()
        assert (
            "compute_health_scorecard" in source
        ), "R0 notebook must call compute_health_scorecard in setup"
        assert "display_scorecard" in source

    def test_r0_notebook_has_comparator_section(self):
        """§11 must reference comparator_battery for cross-bidder comparison."""
        source = R0_PATH.read_text()
        assert "§11 Comparator Battery" in source
        assert "comparator_battery" in source

    def test_r0_notebook_drift_detection_attributes(self):
        """R0 notebook must use mannwhitney_stat/mannwhitney_pvalue (not .statistic/.p_value)."""
        source = R0_PATH.read_text()
        assert (
            "mannwhitney_stat" in source
        ), "R0 notebook must use batch_result.mannwhitney_stat"
        assert (
            "mannwhitney_pvalue" in source
        ), "R0 notebook must use batch_result.mannwhitney_pvalue"
        # Ensure the wrong attribute names are not used (outside comments)
        code_lines = [
            line for line in source.split("\n") if not line.strip().startswith("#")
        ]
        code_text = "\n".join(code_lines)
        assert "batch_result.statistic" not in code_text, (
            "R0 notebook must NOT use .statistic — "
            "BatchComparisonResult uses .mannwhitney_stat"
        )
        assert "batch_result.p_value" not in code_text, (
            "R0 notebook must NOT use .p_value — "
            "BatchComparisonResult uses .mannwhitney_pvalue"
        )

    def test_r0_auction_health_notebook_exists(self):
        """25_auction_health.py must exist with required section markers and library imports."""
        auction_path = (
            Path(__file__).resolve().parents[2]
            / "notebooks"
            / "arc_d"
            / "r0"
            / "25_auction_health.py"
        )
        assert auction_path.exists(), "25_auction_health.py must exist"
        source = auction_path.read_text()
        required_sections = [
            "S0: Configuration",
            "S1: Fail-Fast Validation",
            "S2: Bid Distribution",
            "S3: Bidder & Dealer Seat",
            "S4: Make Rate & Surplus",
            "S5: Seat-Faceted Bid Accuracy",
            "S6: Auction Length & Pass Rate",
            "S7: Summary",
        ]
        for section in required_sections:
            assert section in source, f"25_auction_health missing section: {section}"
        # Must use library chart functions, not inline code
        assert (
            "plot_auction_health" in source
        ), "25_auction_health must call plot_auction_health()"
        assert (
            "plot_bidder_performance" in source
        ), "25_auction_health must call plot_bidder_performance()"

    def test_r0_matchup_notebook_exists(self):
        """50_r0_matchups.py must exist with required section markers."""
        matchup_path = (
            Path(__file__).resolve().parents[2]
            / "notebooks"
            / "arc_d"
            / "r0"
            / "50_r0_matchups.py"
        )
        assert matchup_path.exists(), "50_r0_matchups.py must exist"
        source = matchup_path.read_text()
        required_sections = [
            "§0 Setup",
            "§1 Matchup Overview",
            "§2 Tricks Distribution",
            "§3 Self-Play Fairness",
            "§4 Seat Rotation",
            "§5 Per-Opponent",
            "§6 Performance by Contract",
            "§7 Summary Table",
        ]
        for section in required_sections:
            assert section in source, f"Matchup notebook missing section: {section}"

    def test_r0_matchup_notebook_uses_model_name_param(self):
        """Matchup notebook must use MODEL_NAME param and R0 team-resolution helpers."""
        matchup_path = (
            Path(__file__).resolve().parents[2]
            / "notebooks"
            / "arc_d"
            / "r0"
            / "50_r0_matchups.py"
        )
        source = matchup_path.read_text()

        # MODEL_NAME parameter must exist
        assert (
            "MODEL_NAME" in source
        ), "Matchup notebook must declare MODEL_NAME parameter"

        # Team-resolution helpers must be defined
        assert (
            "def _r0_team(" in source
        ), "Matchup notebook must define _r0_team() helper"
        assert (
            "def _r0_sign(" in source
        ), "Matchup notebook must define _r0_sign() helper"

        # §6 and §7 must NOT use hardcoded team == 0 filter
        # (§3 self-play is allowed to use team == 0 since it checks symmetry)
        section6_start = source.find("§6 Performance by Contract")
        section7_end = len(source)
        assert section6_start != -1
        post_s6_source = source[section6_start:section7_end]
        # Strip comments to avoid false positives from old comment references
        code_lines = [
            line
            for line in post_s6_source.split("\n")
            if not line.strip().startswith("#")
        ]
        code_text = "\n".join(code_lines)
        assert (
            '[team"] == 0]' not in code_text
        ), "§6/§7 must use _r0_team() instead of hardcoded team == 0"

    def test_r0_matchup_notebook_no_hardcoded_team0_in_rankings(self):
        """§7 summary must use r0_tricks/opp_tricks, not team0_tricks/team1_tricks."""
        matchup_path = (
            Path(__file__).resolve().parents[2]
            / "notebooks"
            / "arc_d"
            / "r0"
            / "50_r0_matchups.py"
        )
        source = matchup_path.read_text()

        # Find §7 section
        section7_start = source.find("§7 Summary Table")
        assert section7_start != -1, "§7 Summary Table section must exist"
        s7_source = source[section7_start:]

        # Must NOT use old team0/team1 column names
        assert (
            '"team0_tricks"' not in s7_source
        ), "§7 must use 'r0_tricks' instead of 'team0_tricks'"
        assert (
            '"team1_tricks"' not in s7_source
        ), "§7 must use 'opp_tricks' instead of 'team1_tricks'"

        # Must use R0-relative column names
        assert '"r0_tricks"' in s7_source, "§7 must include 'r0_tricks' column"
        assert '"opp_tricks"' in s7_source, "§7 must include 'opp_tricks' column"

        # Chart label must reference R0, not Team0
        assert (
            "R0 Advantage" in s7_source
        ), "§7 chart must label ME delta as 'R0 Advantage'"


# ──────────────────────────────────────────────
#  Required R0 notebook set (on-disk gate)
# ──────────────────────────────────────────────

# Canonical set of R0 notebooks that must exist on disk.
# Adding a new notebook → add it here. Deleting/renaming → test fails.
REQUIRED_R0_NOTEBOOKS = [
    "10_feature_health.py",
    "20_outcome_health.py",
    "25_auction_health.py",
    "30_feature_outcome_eval.py",
    "40_r0_baseline.py",
    "50_r0_matchups.py",
]

R0_NOTEBOOK_DIR = Path(__file__).resolve().parents[2] / "notebooks" / "arc_d" / "r0"


class TestRequiredR0NotebookSet:
    """Gate: every notebook in the canonical R0 set must exist on disk with paired .ipynb."""

    @pytest.mark.parametrize("notebook", REQUIRED_R0_NOTEBOOKS)
    def test_notebook_py_exists(self, notebook):
        path = R0_NOTEBOOK_DIR / notebook
        assert path.exists(), f"Required R0 notebook missing: {notebook}"

    @pytest.mark.parametrize("notebook", REQUIRED_R0_NOTEBOOKS)
    def test_notebook_ipynb_paired(self, notebook):
        ipynb = R0_NOTEBOOK_DIR / notebook.replace(".py", ".ipynb")
        assert (
            ipynb.exists()
        ), f"Paired .ipynb missing for {notebook} — run `make notebook-sync`"


# ──────────────────────────────────────────────
#  Arc D template contract tests
# ──────────────────────────────────────────────

ARC_D_TEMPLATES = {
    "10_feature_health": Path(__file__).resolve().parents[2]
    / "notebooks"
    / "_templates"
    / "arc_d"
    / "10_feature_health.py",
    "20_outcome_health": Path(__file__).resolve().parents[2]
    / "notebooks"
    / "_templates"
    / "arc_d"
    / "20_outcome_health.py",
    "30_feature_outcome_eval": Path(__file__).resolve().parents[2]
    / "notebooks"
    / "_templates"
    / "arc_d"
    / "30_feature_outcome_eval.py",
}

_ALL_TEMPLATE_IDS = list(ARC_D_TEMPLATES.keys())


class TestArcDTemplateContract:
    def test_templates_exist(self):
        for name, path in ARC_D_TEMPLATES.items():
            assert path.exists(), f"Template missing: {name} at {path}"

    @pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
    def test_required_parameters_present(self, template_id):
        source = ARC_D_TEMPLATES[template_id].read_text()
        common_params = ["EVAL_LOG_PATH", "MODE", "RUNG_ID", "CHART_OUTPUT_DIR"]
        for param in common_params:
            assert (
                f"{param} =" in source
            ), f"{template_id} missing parameter declaration: {param}"
        if template_id == "30_feature_outcome_eval":
            assert (
                "ARTIFACT_DIR =" in source
            ), "30_feature_outcome_eval must declare ARTIFACT_DIR"

    @pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
    def test_removed_parameters_absent(self, template_id):
        source = ARC_D_TEMPLATES[template_id].read_text()
        removed = ["SPLIT_TYPE", "ACTIVE_SPLIT", "MODEL_ARTIFACT_PATH"]
        lines = source.split("\n")
        param_lines = [l for l in lines if "=" in l and not l.strip().startswith("#")]
        param_text = "\n".join(param_lines)
        for param in removed:
            assert (
                f"{param} =" not in param_text
            ), f"{template_id} should not declare removed parameter {param}"

    @pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
    def test_jupytext_header_present(self, template_id):
        source = ARC_D_TEMPLATES[template_id].read_text()
        first_20 = "\n".join(source.split("\n")[:20])
        assert "# ---" in first_20, f"{template_id} missing Jupytext header (# ---)"
        assert "jupytext:" in first_20, f"{template_id} missing jupytext: key in header"

    @pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
    def test_directory_resolution_pattern(self, template_id):
        source = ARC_D_TEMPLATES[template_id].read_text()
        assert (
            ".is_dir()" in source
        ), f"{template_id} must use .is_dir() for directory auto-resolution"

    @pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
    def test_eval_dataset_import(self, template_id):
        source = ARC_D_TEMPLATES[template_id].read_text()
        assert (
            "build_eval_dataset" in source
        ), f"{template_id} must import build_eval_dataset"

    def test_feature_health_imports(self):
        source = ARC_D_TEMPLATES["10_feature_health"].read_text()
        assert (
            "from bid_euchre.diagnostics.charts import" in source
        ), "10_feature_health must import from bid_euchre.diagnostics.charts"

    def test_outcome_health_imports(self):
        source = ARC_D_TEMPLATES["20_outcome_health"].read_text()
        assert (
            "from bid_euchre.diagnostics.auction_charts import" in source
        ), "20_outcome_health must import from bid_euchre.diagnostics.auction_charts"

    def test_feature_outcome_eval_imports(self):
        source = ARC_D_TEMPLATES["30_feature_outcome_eval"].read_text()
        assert "load_eval_metrics" in source, (
            "30_feature_outcome_eval must import load_eval_metrics "
            "from reporting.evaluator"
        )

    def test_feature_outcome_eval_resolve_path(self):
        source = ARC_D_TEMPLATES["30_feature_outcome_eval"].read_text()
        assert (
            "def _resolve_path" in source
        ), "30_feature_outcome_eval must define _resolve_path helper"

    def test_feature_outcome_eval_handles_directory_error(self):
        source = ARC_D_TEMPLATES["30_feature_outcome_eval"].read_text()
        assert (
            "IsADirectoryError" in source
        ), "30_feature_outcome_eval must handle IsADirectoryError"


# ──────────────────────────────────────────────
#  C59 prefix-convention contract tests
# ──────────────────────────────────────────────


class TestC59PrefixConvention:
    """Validate no feat_-prefix anti-patterns exist in R0 notebooks.

    The diagnostics chart API (plot_feature_distributions,
    plot_feature_outcome_correlation, plot_feature_heatmap_by_suit)
    expects UNPREFIXED feature names and internally re-adds the feat_
    prefix. Passing feat_-prefixed names causes a double-prefix bug
    (feat_feat_*) → no matching columns → empty/broken charts.

    These tests catch regressions by detecting the anti-pattern.
    """

    R0_NOTEBOOK_DIR = Path(__file__).resolve().parents[2] / "notebooks" / "arc_d" / "r0"

    PLOT_FUNCTIONS_NEEDING_UNPREFIXED = [
        "plot_feature_distributions",
        "plot_feature_outcome_correlation",
        "plot_feature_heatmap_by_suit",
    ]

    def _get_r0_notebooks(self):
        """Return all .py notebook files in the R0 directory."""
        nbs = sorted(self.R0_NOTEBOOK_DIR.glob("*.py"))
        assert nbs, f"No .py notebooks found in {self.R0_NOTEBOOK_DIR}"
        return nbs

    def test_no_double_prefix_literal(self):
        """No notebook should contain the literal string 'feat_feat_'."""
        for nb_path in self._get_r0_notebooks():
            source = nb_path.read_text()
            # Skip comments
            code_lines = [
                line for line in source.split("\n") if not line.strip().startswith("#")
            ]
            code_text = "\n".join(code_lines)
            assert (
                "feat_feat_" not in code_text
            ), f"{nb_path.name} contains 'feat_feat_' — double-prefix bug detected"

    @pytest.mark.parametrize(
        "func_name",
        [
            "plot_feature_distributions",
            "plot_feature_outcome_correlation",
            "plot_feature_heatmap_by_suit",
        ],
    )
    def test_plot_calls_use_unprefixed_features(self, func_name):
        """Plot functions that expect unprefixed names must not receive feat_-prefixed args.

        For each R0 notebook that calls a prefix-sensitive plot function with
        features=<var>, verify that the variable was built with prefix stripping
        (removeprefix or replace).
        """
        pattern = re.compile(
            rf"{func_name}\s*\([^)]*features\s*=\s*(\w+)",
            re.MULTILINE,
        )
        strip_patterns = [
            r'removeprefix\s*\(\s*["\']feat_',
            r'\.replace\s*\(\s*["\']feat_["\']\s*,\s*["\']["\']',
            r'\.lstrip\s*\(\s*["\']feat_',
        ]

        for nb_path in self._get_r0_notebooks():
            source = nb_path.read_text()
            # Find all calls to this function with features= argument
            for match in pattern.finditer(source):
                var_name = match.group(1)
                # Check if this variable name appears near a prefix-strip operation.
                # Search the whole file for "var_name = ... removeprefix ..."
                # Use re.DOTALL so .* spans newlines (multi-line list comprehensions).
                has_strip = False
                for sp in strip_patterns:
                    if re.search(
                        rf"{var_name}\s*=.*?{sp}",
                        source,
                        re.DOTALL,
                    ):
                        has_strip = True
                        break
                # Also accept if the variable is built from unprefixed literals
                # e.g., features=["hand_value", "trump_count"]
                if re.search(
                    rf'{var_name}\s*=\s*\[(?:["\'][a-z_]+["\'],?\s*)+\]',
                    source,
                ):
                    has_strip = True

                if not has_strip:
                    # This catches: top5 = df[feat_cols].var().nlargest(5).index
                    # Without: top5_names = [c.removeprefix("feat_") for c in top5]
                    assert False, (
                        f"{nb_path.name}: {func_name}(features={var_name}) — "
                        f"variable '{var_name}' may contain feat_-prefixed names. "
                        f"Ensure prefix is stripped before passing to {func_name}()."
                    )
