"""Tests for model-rung report template generator.

All tests are fixture-based — no real experiment runs or model artifacts required.
"""

import pytest

from bid_euchre.models.splits import SplitManifest
from bid_euchre.reporting.report_template import (
    REQUIRED_CHART_KEYS,
    generate_model_rung_report,
)


def _make_semantic_gate(gate_status="PASS"):
    """Minimal valid semantic gate dict."""
    return {
        "schema_version": 1,
        "gate_status": gate_status,
        "created_at_utc": "2026-02-18T12:00:00Z",
        "active_split": "val",
        "mode": "QUICK",
        "seed": 42,
        "total_hands": 2000,
        "total_checks": 12,
        "passed_checks": 12 if gate_status == "PASS" else 10,
        "failed_checks": 0 if gate_status == "PASS" else 2,
        "checks": [
            {
                "check_id": "feature_count",
                "category": "health",
                "status": "PASS",
                "threshold": 39,
                "observed": 39,
                "detail": "Feature count matches expected",
                "contract_type": "",
            },
            {
                "check_id": "seat_balance",
                "category": "fairness",
                "status": "PASS",
                "threshold": 0.05,
                "observed": 0.42,
                "detail": "ANOVA p=0.42",
                "contract_type": "suit",
            },
            {
                "check_id": "prediction_correlation",
                "category": "directional_sanity",
                "status": "PASS",
                "threshold": 0.1,
                "observed": 0.35,
                "detail": "Pearson r=0.35",
                "contract_type": "suit",
            },
        ],
    }


def _make_split_manifest():
    """Minimal valid SplitManifest with all 14 required fields."""
    return SplitManifest(
        schema_version=1,
        split_seed=42,
        split_type="three_way",
        train_fraction=0.6,
        val_fraction=0.2,
        test_fraction=0.2,
        total_hand_ids=1000,
        train_hand_ids=600,
        val_hand_ids=200,
        test_hand_ids=200,
        source_run_id="canonical_run_42_20260210",
        source_parquet_sha256="abc123def456",
        partition_hashes={"train": "aaa", "val": "bbb", "test": "ccc"},
        created_at_utc="2026-02-18T12:00:00Z",
    )


def _make_performance_metrics():
    """Minimal per-contract performance metrics."""
    return {
        "suit": {
            "r_squared": 0.22,
            "r_squared_ci": "(0.18, 0.26)",
            "mae": 1.3,
            "mae_ci": "(1.1, 1.5)",
            "n": 800,
        },
        "high": {
            "r_squared": 0.15,
            "r_squared_ci": "(0.10, 0.20)",
            "mae": 1.5,
            "mae_ci": "(1.3, 1.7)",
            "n": 100,
        },
        "low": {
            "r_squared": 0.12,
            "r_squared_ci": "(0.08, 0.16)",
            "mae": 1.6,
            "mae_ci": "(1.4, 1.8)",
            "n": 100,
        },
    }


def _make_model_identity():
    """Minimal model identity dict."""
    return {
        "artifact_path": "data/runs/test/artifacts/olsa_v1.json",
        "sha256": "deadbeef1234",
        "config": "experiments/configs/olsa_v1.yaml",
        "git_sha": "abc1234",
    }


class TestGenerateModelRungReport:
    def test_all_10_sections_present(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=["Sample size is small"],
            output_path=output,
        )
        content = output.read_text()
        for section_num in range(1, 11):
            header = f"§{section_num}"
            assert header in content, f"Missing section header: {header}"

    def test_gate_summary_table_format(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
        )
        content = output.read_text()
        assert "check_id" in content
        assert "status" in content
        assert "threshold" in content

    def test_performance_table_format(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
        )
        content = output.read_text()
        assert "suit" in content
        assert "high" in content
        assert "low" in content

    def test_split_manifest_table_format(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
        )
        content = output.read_text()
        assert "three_way" in content
        # Verify hand counts present
        assert "600" in content  # train_hand_ids
        assert "200" in content  # val/test_hand_ids

    def test_empty_limitations_still_has_section(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
        )
        content = output.read_text()
        assert "§10" in content
        assert "Known Limitations" in content

    def test_reproduction_commands_include_seed(self, tmp_path):
        output = tmp_path / "report.md"
        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
        )
        content = output.read_text()
        assert "--seed" in content or "-p SEED" in content

    def test_missing_chart_raises_valueerror(self, tmp_path):
        output = tmp_path / "report.md"
        chart_dir = tmp_path / "charts"
        chart_dir.mkdir()
        # Only create 1 of 3 required charts
        (chart_dir / "seat_balance_boxplot.png").write_bytes(b"fake png")

        with pytest.raises(ValueError, match="Required chart missing"):
            generate_model_rung_report(
                semantic_gate=_make_semantic_gate(),
                split_manifest=_make_split_manifest(),
                performance_metrics=_make_performance_metrics(),
                model_identity=_make_model_identity(),
                limitations=[],
                output_path=output,
                chart_dir=chart_dir,
            )

    def test_all_charts_present_embeds_references(self, tmp_path):
        output = tmp_path / "report.md"
        chart_dir = tmp_path / "charts"
        chart_dir.mkdir()
        for key in REQUIRED_CHART_KEYS:
            (chart_dir / f"{key}.png").write_bytes(b"fake png")

        generate_model_rung_report(
            semantic_gate=_make_semantic_gate(),
            split_manifest=_make_split_manifest(),
            performance_metrics=_make_performance_metrics(),
            model_identity=_make_model_identity(),
            limitations=[],
            output_path=output,
            chart_dir=chart_dir,
        )
        content = output.read_text()
        for key in REQUIRED_CHART_KEYS:
            assert f"![{key}]" in content, f"Missing chart reference: {key}"
