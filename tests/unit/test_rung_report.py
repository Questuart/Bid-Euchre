"""Tests for rung report generation.

Covers:
- Report generates deterministically from fixture CSVs
- All required sections present
- Missing tables produce placeholders, not crashes
- Decision report generates valid markdown
- Decision report references chart numbers
- Decision report handles missing data gracefully
- Decision report uses team0/team1 labels
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"

from bid_euchre.arc_d_v2.report import generate_decision_report, generate_report
from bid_euchre.arc_d_v2.tables import generate_all_tables

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
        assert "not yet generated" in content


# ──────────────────────────────────────────────
#  Decision report tests
# ──────────────────────────────────────────────


def _make_hypothesis_outcomes(tmp_path, statuses):
    """Write a hypothesis_outcomes.csv with given statuses."""
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "hypothesis_id": [f"H{i}" for i in range(len(statuses))],
            "description": [f"Hypothesis {i}" for i in range(len(statuses))],
            "status": statuses,
            "evidence": ["observed=1.0"] * len(statuses),
            "notes": [""] * len(statuses),
        }
    )
    df.to_csv(tables_dir / "hypothesis_outcomes.csv", index=False)
    return tables_dir


def _make_comparator_rankings(tables_dir):
    """Write a comparator_rankings.csv fixture."""
    df = pd.DataFrame(
        {
            "model": ["gbt_av", "ols_av", "anchor_hybrid_r0_full"],
            "facet": ["pooled", "pooled", "pooled"],
            "net_eppd": [2.3, 1.8, 0.5],
            "ci_low": [2.0, 1.5, 0.2],
            "ci_high": [2.6, 2.1, 0.8],
            "bid_rate": [0.5, 0.4, 0.3],
            "make_rate": [0.6, 0.5, 0.4],
            "net_cvar_5": [-1.0, -1.2, -2.0],
            "rank": [1, 2, 3],
        }
    )
    df.to_csv(tables_dir / "comparator_rankings.csv", index=False)


def _make_h2h_tier_summary(tables_dir):
    """Write an h2h_tier_summary.csv fixture."""
    df = pd.DataFrame(
        {
            "model": ["gbt_av", "gbt_av", "ols_av", "ols_av"],
            "tier": ["smart", "anchor", "smart", "anchor"],
            "mean_delta": [1.2, 0.8, -0.3, 0.4],
            "mean_win_rate": [0.58, 0.55, 0.48, 0.52],
            "n_opponents": [3, 1, 3, 1],
        }
    )
    df.to_csv(tables_dir / "h2h_tier_summary.csv", index=False)


class TestDecisionReport:
    """Tests for generate_decision_report."""

    @pytest.fixture
    def tables_with_all_data(self, tmp_path):
        """Tables directory with hypothesis outcomes, comparator, and H2H tier."""
        tables_dir = _make_hypothesis_outcomes(tmp_path, ["PASS", "PASS", "PASS"])
        _make_comparator_rankings(tables_dir)
        _make_h2h_tier_summary(tables_dir)
        return tables_dir

    @pytest.fixture
    def charts_dir(self, tmp_path):
        charts = tmp_path / "charts"
        charts.mkdir(parents=True, exist_ok=True)
        return charts

    def test_generates_valid_markdown(self, tables_with_all_data, charts_dir):
        """Decision report produces valid non-empty markdown."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
            rung="R3",
            mode="QUICK",
        )
        assert len(content) > 100
        assert "# Rung R3 (QUICK) — Decision Report" in content

    def test_has_required_sections(self, tables_with_all_data, charts_dir):
        """Decision report contains all required sections."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
            rung="R3",
            mode="QUICK",
        )
        assert "## Advancement Decision" in content
        assert "## Evidence Summary" in content
        assert "### Comparator Standing" in content
        assert "### Head-to-Head Performance" in content
        assert "### Hypothesis Outcomes" in content
        assert "## Recommendation" in content
        assert "## Supporting Evidence" in content

    def test_references_chart_numbers(self, tables_with_all_data, charts_dir):
        """Decision report references specific chart numbers."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
        )
        assert "Chart 1" in content
        assert "Chart 3" in content
        assert "Chart 4" in content

    def test_advance_when_all_pass(self, tables_with_all_data, charts_dir):
        """Reports ADVANCE when all hypothesis checks pass."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
        )
        assert "**ADVANCE**" in content

    def test_halt_when_any_fail(self, tmp_path, charts_dir):
        """Reports HALT when any hypothesis check fails."""
        tables_dir = _make_hypothesis_outcomes(tmp_path, ["PASS", "FAIL", "PASS"])
        content = generate_decision_report(
            tables_dir=tables_dir,
            charts_dir=charts_dir,
        )
        assert "**HALT**" in content
        assert "1 hypothesis check(s) failed" in content

    def test_pending_when_no_hypothesis_outcomes(self, tmp_path, charts_dir):
        """Reports PENDING when hypothesis_outcomes.csv is missing."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        content = generate_decision_report(
            tables_dir=tables_dir,
            charts_dir=charts_dir,
        )
        assert "**PENDING**" in content
        assert "not yet available" in content

    def test_uses_team0_labels(self, tables_with_all_data, charts_dir):
        """Decision report uses team0/team1 labeling for H2H data."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
        )
        assert "team0_model" in content

    def test_top_3_comparator_table(self, tables_with_all_data, charts_dir):
        """Decision report includes top-3 comparator models."""
        content = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
        )
        assert "gbt_av" in content
        assert "ols_av" in content

    def test_writes_to_output_path(self, tables_with_all_data, charts_dir, tmp_path):
        """Decision report writes to the specified output path."""
        output_path = tmp_path / "output" / "02_decision.md"
        generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
            output_path=output_path,
            rung="R0",
            mode="FULL",
        )
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Rung R0 (FULL) — Decision Report" in content

    def test_deterministic(self, tables_with_all_data, charts_dir):
        """Decision report generates identically on two runs."""
        content1 = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
            rung="R3",
        )
        content2 = generate_decision_report(
            tables_dir=tables_with_all_data,
            charts_dir=charts_dir,
            rung="R3",
        )
        assert content1 == content2

    def test_graceful_with_empty_tables(self, tmp_path, charts_dir):
        """Decision report renders gracefully with empty tables directory."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        content = generate_decision_report(
            tables_dir=tables_dir,
            charts_dir=charts_dir,
        )
        assert "# Rung" in content
        assert "**PENDING**" in content
        # Should not crash, should have placeholder text
        assert "not yet generated" in content or "not yet available" in content
