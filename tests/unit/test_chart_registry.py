"""Tests for chart registry, numbered report headings, and manifest chart inventory.

Covers:
- Chart registry has exactly 22 entries with unique numbers and filenames
- get_chart_by_number() and get_chart_by_filename() work correctly
- Report rendering uses numbered headings (Chart N. Title)
- Report rendering emits placeholders for missing optional charts
- H2H table rendering uses team0/team1 labels
- Long tables are truncated at ~12 rows
- Manifest includes chart number and presence status
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bid_euchre.arc_d_v2.chart_registry import (
    CHART_REGISTRY,
    ChartEntry,
    get_chart_by_filename,
    get_chart_by_number,
)
from bid_euchre.arc_d_v2.manifest import render_manifest_markdown
from bid_euchre.arc_d_v2.report import (
    _H2H_COLUMN_RENAMES,
    _TABLE_ROW_LIMIT,
    _TABLE_ROW_SHOW,
    _chart_embed,
    _chart_placeholder,
    _df_to_markdown,
    generate_report,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"


# ──────────────────────────────────────────────
#  Chart Registry
# ──────────────────────────────────────────────


class TestChartRegistry:
    def test_exactly_22_entries(self):
        assert len(CHART_REGISTRY) == 22

    def test_unique_numbers(self):
        numbers = [e.number for e in CHART_REGISTRY]
        assert len(numbers) == len(set(numbers))

    def test_unique_filenames(self):
        filenames = [e.filename for e in CHART_REGISTRY]
        assert len(filenames) == len(set(filenames))

    def test_numbers_are_1_to_22(self):
        numbers = sorted(e.number for e in CHART_REGISTRY)
        assert numbers == list(range(1, 23))

    def test_all_filenames_end_with_png(self):
        for entry in CHART_REGISTRY:
            assert entry.filename.endswith(".png"), f"{entry.filename} is not a PNG"

    def test_entries_are_frozen(self):
        entry = CHART_REGISTRY[0]
        with pytest.raises(AttributeError):
            entry.number = 99  # type: ignore[misc]

    def test_entry_is_dataclass(self):
        entry = CHART_REGISTRY[0]
        assert isinstance(entry, ChartEntry)
        assert hasattr(entry, "number")
        assert hasattr(entry, "filename")
        assert hasattr(entry, "title")
        assert hasattr(entry, "required")
        assert hasattr(entry, "source")


class TestGetChartByNumber:
    def test_returns_correct_entry(self):
        entry = get_chart_by_number(1)
        assert entry is not None
        assert entry.filename == "dashboard_competitive.png"

    def test_returns_none_for_invalid(self):
        assert get_chart_by_number(0) is None
        assert get_chart_by_number(23) is None
        assert get_chart_by_number(-1) is None

    def test_all_numbers_resolve(self):
        for n in range(1, 23):
            entry = get_chart_by_number(n)
            assert entry is not None, f"Chart number {n} not found"
            assert entry.number == n


class TestGetChartByFilename:
    def test_returns_correct_entry(self):
        entry = get_chart_by_filename("dashboard_competitive.png")
        assert entry is not None
        assert entry.number == 1

    def test_returns_none_for_unknown(self):
        assert get_chart_by_filename("nonexistent.png") is None
        assert get_chart_by_filename("") is None

    def test_all_filenames_resolve(self):
        for reg_entry in CHART_REGISTRY:
            entry = get_chart_by_filename(reg_entry.filename)
            assert entry is not None
            assert entry.number == reg_entry.number


# ──────────────────────────────────────────────
#  Report — Numbered Headings
# ──────────────────────────────────────────────


class TestReportNumberedHeadings:
    @pytest.fixture
    def charts_dir(self, tmp_path):
        charts = tmp_path / "report" / "charts"
        charts.mkdir(parents=True)
        return charts

    def test_chart_embed_uses_numbered_heading(self, charts_dir):
        """When a chart PNG exists, _chart_embed uses 'Chart N. Title' heading."""
        (charts_dir / "dashboard_competitive.png").write_bytes(b"PNG")
        result = _chart_embed(charts_dir, "dashboard_competitive.png")
        assert "### Chart 1. Competitive Dashboard" in result
        assert "![Competitive Dashboard]" in result

    def test_chart_embed_numbered_for_various_charts(self, charts_dir):
        """Multiple chart types get their correct numbered headings."""
        test_cases = [
            ("r2_by_contract.png", 14, "R-squared by Contract"),
            ("h2h_heatmap.png", 7, "H2H Heatmap"),
            ("contract_mix_bars.png", 11, "Contract Mix"),
        ]
        for filename, expected_num, expected_title in test_cases:
            (charts_dir / filename).write_bytes(b"PNG")
            result = _chart_embed(charts_dir, filename)
            assert f"### Chart {expected_num}. {expected_title}" in result


class TestReportPlaceholders:
    @pytest.fixture
    def charts_dir(self, tmp_path):
        charts = tmp_path / "report" / "charts"
        charts.mkdir(parents=True)
        return charts

    def test_missing_registered_chart_has_numbered_placeholder(self, charts_dir):
        """Missing chart from registry shows Chart N. Title + absence note."""
        result = _chart_placeholder("dashboard_competitive.png")
        assert "### Chart 1. Competitive Dashboard" in result
        assert "source data absent" in result

    def test_missing_unregistered_chart_has_generic_placeholder(self, charts_dir):
        """Charts not in registry get the generic placeholder."""
        result = _chart_placeholder("unknown_chart.png")
        assert "not yet generated" in result
        assert "Chart" not in result or "unknown_chart.png" in result

    def test_full_report_has_placeholders_for_missing_charts(self, tmp_path):
        """Full report generation emits placeholders for optional missing charts."""
        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        tables_dir.mkdir(parents=True)
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True)

        content = generate_report(report_dir)
        # Missing registered charts should get numbered placeholders
        assert "source data absent" in content or "not yet generated" in content


# ──────────────────────────────────────────────
#  Report — H2H team0/team1 Labels
# ──────────────────────────────────────────────


class TestH2HTeamLabels:
    def test_column_renames_mapping(self):
        """The rename mapping is model_a -> team0, model_b -> team1."""
        assert _H2H_COLUMN_RENAMES == {"model_a": "team0", "model_b": "team1"}

    def test_df_to_markdown_with_column_renames(self):
        """_df_to_markdown applies column renames to headers."""
        df = pd.DataFrame(
            {
                "model_a": ["gbt", "ols"],
                "model_b": ["smart", "smart"],
                "delta": [1.5, 0.8],
            }
        )
        result = _df_to_markdown(
            df, column_renames={"model_a": "team0", "model_b": "team1"}
        )
        assert "team0" in result
        assert "team1" in result
        # Original column names should NOT appear in headers
        lines = result.split("\n")
        header = lines[0]
        assert "model_a" not in header
        assert "model_b" not in header

    def test_h2h_table_in_report_uses_team_labels(self, tmp_path):
        """H2H delta matrix table uses team0/team1 in rendered report."""
        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        tables_dir.mkdir(parents=True)
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True)

        # Write a minimal H2H delta matrix CSV
        h2h_df = pd.DataFrame(
            {
                "model_a": ["gbt_av", "gbt_av"],
                "model_b": ["smart_bid", "ols_av"],
                "facet": ["pooled", "pooled"],
                "net_eppd_delta": [1.5, 0.8],
                "ci_low": [1.0, 0.3],
                "ci_high": [2.0, 1.3],
                "win_rate_a": [0.62, 0.55],
                "deals_total": [500, 500],
            }
        )
        h2h_df.to_csv(tables_dir / "h2h_delta_matrix.csv", index=False)

        content = generate_report(report_dir)
        # The rendered table should use team0/team1
        assert "| team0 |" in content or "| team0 " in content
        assert "| team1 |" in content or "| team1 " in content

    def test_data_values_preserved_with_renames(self):
        """Renaming columns does not change cell values."""
        df = pd.DataFrame(
            {
                "model_a": ["gbt"],
                "model_b": ["smart"],
                "value": [1.0],
            }
        )
        result = _df_to_markdown(
            df, column_renames={"model_a": "team0", "model_b": "team1"}
        )
        assert "gbt" in result
        assert "smart" in result


# ──────────────────────────────────────────────
#  Report — Long Table Truncation
# ──────────────────────────────────────────────


class TestLongTableTruncation:
    def test_short_table_not_truncated(self):
        """Table with <= 12 rows is not truncated."""
        df = pd.DataFrame({"a": range(10), "b": range(10)})
        result = _df_to_markdown(df, table_name="test.csv")
        assert "Full table omitted" not in result
        # All 10 data rows present (+ header + separator = 12 lines)
        data_lines = [
            line for line in result.strip().split("\n") if line.startswith("|")
        ]
        assert len(data_lines) == 12  # 10 data + header + separator

    def test_long_table_truncated(self):
        """Table with > 12 rows is truncated to 10 rows with a note."""
        df = pd.DataFrame({"a": range(20), "b": range(20)})
        result = _df_to_markdown(df, table_name="test.csv")
        assert "Full table omitted from markdown" in result
        assert "tables/test.csv" in result
        # Only 10 data rows present
        data_lines = [
            line
            for line in result.strip().split("\n")
            if line.startswith("|") and "---" not in line and "a" not in line
        ]
        assert len(data_lines) == _TABLE_ROW_SHOW

    def test_exactly_at_limit_not_truncated(self):
        """Table with exactly 12 rows is not truncated."""
        df = pd.DataFrame({"a": range(_TABLE_ROW_LIMIT), "b": range(_TABLE_ROW_LIMIT)})
        result = _df_to_markdown(df, table_name="test.csv")
        assert "Full table omitted" not in result

    def test_one_over_limit_truncated(self):
        """Table with 13 rows IS truncated."""
        df = pd.DataFrame(
            {"a": range(_TABLE_ROW_LIMIT + 1), "b": range(_TABLE_ROW_LIMIT + 1)}
        )
        result = _df_to_markdown(df, table_name="test.csv")
        assert "Full table omitted" in result

    def test_no_truncation_without_table_name(self):
        """Without table_name, tables are never truncated (backward compat)."""
        df = pd.DataFrame({"a": range(50), "b": range(50)})
        result = _df_to_markdown(df)
        assert "Full table omitted" not in result
        data_lines = [
            line for line in result.strip().split("\n") if line.startswith("|")
        ]
        assert len(data_lines) == 52  # 50 data + header + separator


# ──────────────────────────────────────────────
#  Manifest — Chart Inventory
# ──────────────────────────────────────────────


class TestManifestChartInventory:
    def test_manifest_chart_inventory_has_all_22(self, tmp_path):
        """Chart inventory includes all 22 registry entries."""
        from bid_euchre.arc_d_v2.manifest import _inventory_chart_dir

        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        # Create a few chart PNGs
        (charts_dir / "dashboard_competitive.png").write_bytes(b"PNG" * 100)
        (charts_dir / "h2h_heatmap.png").write_bytes(b"PNG" * 50)

        inventory = _inventory_chart_dir(charts_dir)
        # Should have at least 22 entries (registry) + 0 extras
        assert len(inventory) >= 22

        # Check that all 22 numbers are present
        numbers = [e.get("number") for e in inventory if "number" in e]
        assert sorted(numbers) == list(range(1, 23))

    def test_present_charts_have_size(self, tmp_path):
        from bid_euchre.arc_d_v2.manifest import _inventory_chart_dir

        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        (charts_dir / "dashboard_competitive.png").write_bytes(b"X" * 42)

        inventory = _inventory_chart_dir(charts_dir)
        entry = next(e for e in inventory if e["name"] == "dashboard_competitive.png")
        assert entry["present"] is True
        assert entry["size_bytes"] == 42
        assert "path" in entry

    def test_absent_charts_marked_absent(self, tmp_path):
        from bid_euchre.arc_d_v2.manifest import _inventory_chart_dir

        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        inventory = _inventory_chart_dir(charts_dir)
        # All should be absent
        for entry in inventory:
            if "number" in entry:
                assert entry["present"] is False
                assert entry["size_bytes"] == 0

    def test_manifest_markdown_includes_chart_number(self):
        """Rendered manifest markdown includes chart number and status."""
        manifest = {
            "schema_version": "arc_d_evidence_manifest_v1",
            "lineage_id": "arc_d_v2",
            "rung_id": "r0",
            "provenance_sha": "abc123",
            "governing_plan": "",
            "anchor": "",
            "roster": [],
            "seeds": [],
            "mode": "QUICK",
            "run_ids": [],
            "artifacts": [],
            "tables": [],
            "charts": [
                {
                    "number": 1,
                    "name": "dashboard_competitive.png",
                    "title": "Competitive Dashboard",
                    "required": True,
                    "present": True,
                    "size_bytes": 1024,
                    "path": "/tmp/charts/dashboard_competitive.png",
                },
                {
                    "number": 7,
                    "name": "h2h_heatmap.png",
                    "title": "H2H Heatmap",
                    "required": True,
                    "present": False,
                    "size_bytes": 0,
                },
            ],
            "chart_data": [],
        }
        md = render_manifest_markdown(manifest)
        assert "## Charts" in md
        assert "| # |" in md
        assert "| 1 |" in md
        assert "Competitive Dashboard" in md
        assert "present" in md
        assert "| 7 |" in md
        assert "absent" in md


# ──────────────────────────────────────────────
#  Full Report Integration (with fixtures)
# ──────────────────────────────────────────────


@pytest.mark.skipif(not FIXTURES_DIR.exists(), reason="Fixture directory not available")
class TestReportWithFixtures:
    @pytest.fixture
    def report_dir(self, tmp_path):
        """Prepare a report directory with tables from fixtures."""
        from bid_euchre.arc_d_v2.tables import generate_all_tables

        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        generate_all_tables(FIXTURES_DIR, tables_dir)
        return report_dir

    def test_has_all_sections(self, report_dir):
        content = generate_report(report_dir)
        for section in [
            "## 1. Data Sanity",
            "## 2. Offline Model Performance",
            "## 6. Comparator Rankings",
            "## 7. H2H Battery",
            "## 8. Behavioral Analysis",
        ]:
            assert section in content, f"Missing section: {section}"

    def test_h2h_uses_team_labels(self, report_dir):
        """H2H section uses team0/team1 labels."""
        content = generate_report(report_dir)
        # The H2H table is rendered with team0/team1
        if "h2h_delta_matrix" not in content or "not yet generated" in content:
            pytest.skip("H2H data not available in fixtures")
        assert "team0" in content
        assert "team1" in content
