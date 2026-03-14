"""Tests for rung report generation (generate_rung_report.py).

Covers:
- Report generates deterministically from fixture CSVs
- All required sections present
- Missing tables produce placeholders, not crashes
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"

# Import the scripts as modules
_tables_spec = importlib.util.spec_from_file_location(
    "generate_rung_tables",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "generate_rung_tables.py",
)
_tables_mod = importlib.util.module_from_spec(_tables_spec)
_tables_spec.loader.exec_module(_tables_mod)

_report_spec = importlib.util.spec_from_file_location(
    "generate_rung_report",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "generate_rung_report.py",
)
_report_mod = importlib.util.module_from_spec(_report_spec)
_report_spec.loader.exec_module(_report_mod)

generate_all_tables = _tables_mod.generate_all_tables
generate_report = _report_mod.generate_report


REQUIRED_SECTIONS = [
    "## 1. Data Sanity",
    "## 2. Offline Model Performance",
    "## 3. Offline Diagnostics",
    "## 4. Model Interpretability",
    "## 5. Cross-Model Decision Analysis",
    "## 6. Comparator Rankings",
    "## 7. H2H Battery",
    "## 8. Behavioral Analysis",
    "## 9. Sanity Bounds",
]


class TestReportGeneration:
    @pytest.fixture
    def report_dir(self, tmp_path):
        """Prepare a report directory with tables from fixtures."""
        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        generate_all_tables(FIXTURES_DIR, tables_dir)
        return report_dir

    def test_generates_non_empty(self, report_dir):
        content = generate_report(report_dir)
        assert len(content) > 100

    def test_has_title(self, report_dir):
        content = generate_report(report_dir)
        assert "# Rung Results Report" in content

    def test_has_all_sections(self, report_dir):
        content = generate_report(report_dir)
        for section in REQUIRED_SECTIONS:
            assert section in content, f"Missing section: {section}"

    def test_contains_model_data(self, report_dir):
        content = generate_report(report_dir)
        # Should contain model names from fixtures
        assert "gbt_av" in content or "gbt" in content
        assert "selected_ols_av" in content or "ols" in content

    def test_deterministic(self, report_dir):
        """Report generates identically on two runs."""
        content1 = generate_report(report_dir)
        content2 = generate_report(report_dir)
        assert content1 == content2

    def test_missing_charts_produce_placeholders(self, report_dir):
        """Missing chart PNGs produce placeholders, not crashes."""
        content = generate_report(report_dir)
        # Charts don't exist in our test, so placeholders should appear
        # (we check that the report renders without error)
        assert "not yet generated" in content or "![" in content


class TestReportWithEmptyTables:
    def test_graceful_with_no_tables(self, tmp_path):
        """Report renders gracefully with empty tables directory."""
        report_dir = tmp_path / "empty_report"
        tables_dir = report_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = report_dir / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        content = generate_report(report_dir)
        assert "# Rung Results Report" in content
        # Should have placeholders for missing tables
        assert "not yet generated" in content
