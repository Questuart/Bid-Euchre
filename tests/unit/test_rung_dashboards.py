"""Tests for dashboard chart generation.

Covers:
- Each dashboard renders without error on fixture-generated CSV data
- Missing chart_data panels show graceful fallback (no crash)
- Dashboard files are created in the output directory
- Works with R0-style data (no moon/loner) and R3-style data (bid_type)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"

from bid_euchre.arc_d_v2.tables import generate_all_tables

# Import the dashboard generators under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))
from generate_rung_charts import (
    generate_all_charts,
    generate_dashboard_competitive,
    generate_dashboard_health,
    generate_dashboard_model_eval,
)


@pytest.fixture
def tables_dir(tmp_path):
    """Generate tables from fixture data into tmp_path."""
    tables = tmp_path / "tables"
    tables.mkdir()
    generate_all_tables(FIXTURES_DIR, tables)
    return tables


@pytest.fixture
def output_dir(tmp_path):
    """Output directory for chart PNGs."""
    out = tmp_path / "charts"
    out.mkdir()
    return out


@pytest.fixture
def chart_data_dir(tmp_path):
    """Empty chart_data directory (simulates missing optional CSVs)."""
    cd = tmp_path / "chart_data"
    cd.mkdir()
    return cd


class TestDashboardCompetitive:
    def test_renders_without_error(self, tables_dir, output_dir):
        result = generate_dashboard_competitive(tables_dir, output_dir)
        assert result is True
        assert (output_dir / "dashboard_competitive.png").exists()

    def test_renders_with_empty_tables(self, tmp_path):
        empty_tables = tmp_path / "empty_tables"
        empty_tables.mkdir()
        out = tmp_path / "empty_out"
        out.mkdir()
        result = generate_dashboard_competitive(empty_tables, out)
        assert result is True
        assert (out / "dashboard_competitive.png").exists()


class TestDashboardHealth:
    def test_renders_without_error(self, tables_dir, output_dir):
        result = generate_dashboard_health(tables_dir, output_dir)
        assert result is True
        assert (output_dir / "dashboard_health.png").exists()

    def test_renders_with_empty_tables(self, tmp_path):
        empty_tables = tmp_path / "empty_tables"
        empty_tables.mkdir()
        out = tmp_path / "empty_out"
        out.mkdir()
        result = generate_dashboard_health(empty_tables, out)
        assert result is True
        assert (out / "dashboard_health.png").exists()

    def test_renders_with_outcome_distributions(
        self, tables_dir, output_dir, chart_data_dir
    ):
        """When outcome_distributions.csv exists, panel 3 renders it."""
        df = pd.DataFrame(
            {
                "contract": ["suit"] * 20 + ["high"] * 20,
                "value": list(range(20)) + list(range(20)),
            }
        )
        df.to_csv(chart_data_dir / "outcome_distributions.csv", index=False)
        result = generate_dashboard_health(tables_dir, output_dir, chart_data_dir)
        assert result is True
        assert (output_dir / "dashboard_health.png").exists()

    def test_renders_with_bid_type_data(self, tables_dir, output_dir, tmp_path):
        """When behavior_by_bid_type.csv exists with bid_type column, panel 4 renders."""
        bid_type_df = pd.DataFrame(
            {
                "model": ["gbt_av", "gbt_av", "ols_av", "ols_av"],
                "bid_type": ["regular", "moon", "regular", "moon"],
                "bid_rate": [0.9, 0.1, 0.95, 0.05],
                "make_rate": [0.8, 0.5, 0.85, 0.4],
            }
        )
        bid_type_df.to_csv(tables_dir / "behavior_by_bid_type.csv", index=False)
        result = generate_dashboard_health(tables_dir, output_dir)
        assert result is True
        assert (output_dir / "dashboard_health.png").exists()


class TestDashboardModelEval:
    def test_renders_without_error(self, tables_dir, output_dir):
        result = generate_dashboard_model_eval(tables_dir, output_dir)
        assert result is True
        assert (output_dir / "dashboard_model_eval.png").exists()

    def test_renders_with_empty_tables(self, tmp_path):
        empty_tables = tmp_path / "empty_tables"
        empty_tables.mkdir()
        out = tmp_path / "empty_out"
        out.mkdir()
        result = generate_dashboard_model_eval(empty_tables, out)
        assert result is True
        assert (out / "dashboard_model_eval.png").exists()

    def test_renders_with_selection_paths(self, tables_dir, output_dir, chart_data_dir):
        """When selection_paths.csv exists, panel 3 renders it."""
        sel_df = pd.DataFrame(
            {
                "model": ["gbt_av"] * 5 + ["ols_av"] * 5,
                "contract": ["suit"] * 5 + ["suit"] * 5,
                "step": list(range(1, 6)) * 2,
                "oof_r2": [0.1, 0.3, 0.45, 0.55, 0.60, 0.1, 0.25, 0.40, 0.50, 0.55],
            }
        )
        sel_df.to_csv(chart_data_dir / "selection_paths.csv", index=False)
        result = generate_dashboard_model_eval(tables_dir, output_dir, chart_data_dir)
        assert result is True
        assert (output_dir / "dashboard_model_eval.png").exists()

    def test_renders_with_cross_rung_deltas(self, tables_dir, output_dir):
        """Cross-rung progression panel renders from cross_rung_deltas.csv."""
        # This CSV is generated by generate_all_tables from fixtures
        assert (tables_dir / "cross_rung_deltas.csv").exists()
        result = generate_dashboard_model_eval(tables_dir, output_dir)
        assert result is True


class TestGenerateAllCharts:
    def test_includes_dashboards(self, tables_dir, output_dir):
        """generate_all_charts produces all three dashboards."""
        generated = generate_all_charts(tables_dir, output_dir)
        assert "dashboard_competitive.png" in generated
        assert "dashboard_health.png" in generated
        assert "dashboard_model_eval.png" in generated

    def test_standalone_charts_still_generated(self, tables_dir, output_dir):
        """Existing standalone charts are still generated alongside dashboards."""
        generated = generate_all_charts(tables_dir, output_dir)
        # At least some standalone charts should be present
        standalone = [c for c in generated if not c.startswith("dashboard_")]
        assert len(standalone) >= 4  # ranking, delta, heatmap, tail risk, etc.


class TestDashboardsInReport:
    """Verify that report.py embeds dashboards when they exist."""

    def test_report_embeds_dashboards(self, tmp_path):
        from bid_euchre.arc_d_v2.report import generate_report

        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True)

        # Generate tables
        generate_all_tables(FIXTURES_DIR, tables_dir)

        # Generate charts (including dashboards)
        generate_all_charts(tables_dir, charts_dir)

        content = generate_report(report_dir)
        assert "## Dashboards" in content
        assert "dashboard_competitive.png" in content
        assert "dashboard_health.png" in content
        assert "dashboard_model_eval.png" in content

    def test_report_without_dashboards_still_works(self, tmp_path):
        from bid_euchre.arc_d_v2.report import generate_report

        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True)

        generate_all_tables(FIXTURES_DIR, tables_dir)
        # Do NOT generate charts — dashboards won't exist
        content = generate_report(report_dir)
        # Dashboards section should not appear if no dashboard PNGs exist
        assert "## Dashboards" not in content
        # But the rest of the report should still render
        assert "# Rung Results Report" in content
