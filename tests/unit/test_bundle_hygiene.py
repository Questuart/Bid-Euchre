"""Bundle hygiene checks for committed Arc D v2 report bundles.

These tests verify the committed bundles under docs/04_reports/arc_d_v2/
conform to the reporting refactor contract (plans/arc_d_v2/reporting_refactor_full_plan.md).

Checks:
- No quick/full bundle contains outcome_summary.csv (§3.10)
- 02_decision.md is never PENDING in quick bundles (§3.7)
- 04_rung_decision.md is deprecated in full bundles (§3.1)
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPORTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "04_reports" / "arc_d_v2"
RUNGS = ["r0", "r1", "r2", "r3"]
MODES = ["quick", "full"]


class TestNoOutcomeSummary:
    """outcome_summary.csv must not appear in any quick or full bundle (§3.10)."""

    @pytest.mark.parametrize(
        "rung,mode",
        [(r, m) for r in RUNGS for m in MODES],
        ids=[f"{r}/{m}" for r in RUNGS for m in MODES],
    )
    def test_no_outcome_summary_csv(self, rung: str, mode: str):
        bundle = REPORTS_DIR / rung / mode / "chart_data" / "outcome_summary.csv"
        assert not bundle.exists(), (
            f"outcome_summary.csv should not be in {rung}/{mode}/chart_data/ "
            f"(removed per §3.10)"
        )


class TestDecisionReportNotPending:
    """02_decision.md must never show PENDING status in quick bundles (§3.7)."""

    @pytest.mark.parametrize("rung", RUNGS)
    def test_quick_decision_not_pending(self, rung: str):
        decision_path = REPORTS_DIR / rung / "quick" / "02_decision.md"
        if not decision_path.exists():
            pytest.skip(f"{rung}/quick/02_decision.md does not exist")
        content = decision_path.read_text()
        # Check the advancement decision line
        assert "**PENDING**" not in content, (
            f"{rung}/quick/02_decision.md contains PENDING status. "
            f"QUICK decisions must be ADVANCE, PRELIMINARY, or HALT (§3.7)"
        )


class TestDecisionReportIsCanonical:
    """04_rung_decision.md should be deprecated, not actively maintained (§3.1)."""

    @pytest.mark.parametrize("rung", RUNGS)
    def test_rung_decision_deprecated(self, rung: str):
        rung_decision = REPORTS_DIR / rung / "full" / "04_rung_decision.md"
        if not rung_decision.exists():
            pytest.skip(f"{rung}/full/04_rung_decision.md does not exist")
        content = rung_decision.read_text()
        assert "DEPRECATED" in content, (
            f"{rung}/full/04_rung_decision.md lacks deprecation notice. "
            f"Per §3.1, 02_decision.md is the sole canonical decision surface"
        )


class TestBundleStructure:
    """Basic structural checks for committed bundles."""

    @pytest.mark.parametrize(
        "rung,mode",
        [(r, m) for r in RUNGS for m in MODES],
        ids=[f"{r}/{m}" for r in RUNGS for m in MODES],
    )
    def test_canonical_files_present(self, rung: str, mode: str):
        """00_manifest.md, 01_results.md, 02_decision.md must exist."""
        bundle = REPORTS_DIR / rung / mode
        if not bundle.is_dir():
            pytest.skip(f"{rung}/{mode} bundle does not exist")
        for f in ["00_manifest.md", "01_results.md", "02_decision.md"]:
            assert (bundle / f).exists(), f"Missing canonical file: {rung}/{mode}/{f}"

    @pytest.mark.parametrize(
        "rung,mode",
        [(r, m) for r in RUNGS for m in MODES],
        ids=[f"{r}/{m}" for r in RUNGS for m in MODES],
    )
    def test_chart_data_dir_exists(self, rung: str, mode: str):
        """chart_data/ directory must exist in each bundle."""
        bundle = REPORTS_DIR / rung / mode
        if not bundle.is_dir():
            pytest.skip(f"{rung}/{mode} bundle does not exist")
        chart_data = bundle / "chart_data"
        assert chart_data.is_dir(), f"Missing chart_data/ in {rung}/{mode}"


class TestBundleDistinctness:
    """Bundles across rungs must be materially distinct (not copies)."""

    def test_quick_bundles_distinct(self):
        """02_decision.md should differ across quick bundles."""
        contents = {}
        for rung in RUNGS:
            p = REPORTS_DIR / rung / "quick" / "02_decision.md"
            if p.exists():
                contents[rung] = p.read_text()
        if len(contents) < 2:
            pytest.skip("Need at least 2 quick bundles to compare")
        # At minimum, titles should reference different rungs
        values = list(contents.values())
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                # Allow identical content only if both are short placeholder files
                if len(values[i]) > 200 and len(values[j]) > 200:
                    assert values[i] != values[j], (
                        "Two quick 02_decision.md files are identical — "
                        "bundles may be copies"
                    )

    def test_full_bundles_distinct(self):
        """02_decision.md should differ across full bundles."""
        contents = {}
        for rung in RUNGS:
            p = REPORTS_DIR / rung / "full" / "02_decision.md"
            if p.exists():
                contents[rung] = p.read_text()
        if len(contents) < 2:
            pytest.skip("Need at least 2 full bundles to compare")
        values = list(contents.values())
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                if len(values[i]) > 200 and len(values[j]) > 200:
                    assert values[i] != values[j], (
                        "Two full 02_decision.md files are identical — "
                        "bundles may be copies"
                    )
