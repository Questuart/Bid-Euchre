"""Tests for confidence_scorer — P2 finding confidence scoring and filtering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The module under test lives in scripts/internal/, not in the installed package.
# Add it to sys.path so we can import it directly.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from confidence_scorer import (
    CONFIDENCE_THRESHOLD,
    ScoredFinding,
    _line_in_diff,
    save_scoring_report,
    score_findings,
)

# ---------------------------------------------------------------------------
# Sample diff for tests
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git a/src/bid_euchre/core/rules.py b/src/bid_euchre/core/rules.py
--- a/src/bid_euchre/core/rules.py
+++ b/src/bid_euchre/core/rules.py
@@ -10,6 +10,8 @@ def resolve_trick(cards):
     # existing code
+    new_line_at_12 = True
+    another_new_line = True
     # more existing code
diff --git a/docs/01_core/RULES.md b/docs/01_core/RULES.md
--- a/docs/01_core/RULES.md
+++ b/docs/01_core/RULES.md
@@ -1,3 +1,4 @@
 # Rules
+Updated rules section
 ## Section 1
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    severity: str = "P2",
    file: str = "src/bid_euchre/core/rules.py",
    line: int = 12,
    check_id: str = "X3",
    message: str = "Some convention issue",
    category: str = "convention",
) -> dict:
    """Create a finding dict matching the schema used by prechecks/Codex."""
    return {
        "severity": severity,
        "file": file,
        "line": line,
        "check_id": check_id,
        "message": message,
        "category": category,
    }


# ---------------------------------------------------------------------------
# P0/P1 pass-through
# ---------------------------------------------------------------------------


class TestP0P1Passthrough:
    """P0 and P1 findings must always pass through unchanged."""

    def test_p0_always_passes(self):
        findings = [_make_finding(severity="P0", check_id="X3")]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert len(passed) == 1
        assert passed[0] is findings[0]
        assert scored[0].confidence == 100
        assert not scored[0].filtered

    def test_p1_always_passes(self):
        findings = [_make_finding(severity="P1", check_id="C1")]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert len(passed) == 1
        assert passed[0] is findings[0]
        assert scored[0].confidence == 100
        assert not scored[0].filtered

    def test_mixed_severities_preserves_p0_p1(self):
        findings = [
            _make_finding(severity="P0"),
            _make_finding(severity="P1"),
            _make_finding(severity="P2", line=999),  # Not in diff -> filtered
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        # P0 and P1 always pass; P2 on unmodified line (999) gets penalized
        assert sum(1 for s in scored if s.finding["severity"] in ("P0", "P1")) == 2
        p0_p1_passed = [f for f in passed if f["severity"] in ("P0", "P1")]
        assert len(p0_p1_passed) == 2


# ---------------------------------------------------------------------------
# P2 filtering by diff context
# ---------------------------------------------------------------------------


class TestDiffAwareness:
    """P2 findings on unmodified lines should be filtered."""

    def test_p2_on_modified_line_passes(self):
        """Line 12 is added in the diff — finding should pass."""
        findings = [_make_finding(severity="P2", line=12)]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert len(passed) == 1
        assert scored[0].confidence >= CONFIDENCE_THRESHOLD

    def test_p2_on_unmodified_line_filtered(self):
        """Line 999 is not in the diff — confidence drops below threshold."""
        findings = [_make_finding(severity="P2", line=999)]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert len(passed) == 0
        assert scored[0].filtered
        assert scored[0].confidence < CONFIDENCE_THRESHOLD
        assert "unmodified line" in scored[0].reasoning

    def test_p2_no_diff_keeps_default(self):
        """With empty diff, no deduction for diff-awareness."""
        findings = [_make_finding(severity="P2", line=999)]
        passed, scored = score_findings(findings, "")
        # No diff -> no deduction -> default 80 >= threshold 75
        assert len(passed) == 1
        assert scored[0].confidence == 80


# ---------------------------------------------------------------------------
# C4 in known-complex files
# ---------------------------------------------------------------------------


class TestKnownComplexFiles:
    """C4 in known-complex files should get confidence penalty."""

    def test_c4_in_review_driver_filtered(self):
        findings = [
            _make_finding(
                severity="P2",
                file="scripts/internal/review_driver.py",
                check_id="C4",
                line=999,
            )
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        # -40 (unmodified) + -25 (known complex) = 15, well below threshold
        assert len(passed) == 0
        assert scored[0].filtered
        assert "legitimately complex" in scored[0].reasoning

    def test_c4_in_regular_file_not_penalized_for_complexity(self):
        """C4 in a regular file should not get the known-complex penalty."""
        findings = [
            _make_finding(
                severity="P2",
                file="src/bid_euchre/core/rules.py",
                check_id="C4",
                line=12,  # On a modified line
            )
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert len(passed) == 1
        assert "legitimately complex" not in scored[0].reasoning


# ---------------------------------------------------------------------------
# N3 penalty
# ---------------------------------------------------------------------------


class TestN3Penalty:
    """N3 findings should get a confidence penalty."""

    def test_n3_gets_penalty(self):
        findings = [
            _make_finding(
                severity="P2",
                file="notebooks/arc_d/r0/50_analysis.py",
                check_id="N3",
                line=12,
            )
        ]
        # N3 on a line that's not in the diff for this file -> -40 (unmod) + -15 (N3)
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert scored[0].confidence < 80
        assert "N3" in scored[0].reasoning

    def test_n3_on_modified_line_may_still_pass(self):
        """N3 with -15 from default 80 = 65, below threshold."""
        # Build a diff that includes the notebook file
        diff = (
            "diff --git a/notebooks/test.py b/notebooks/test.py\n"
            "--- a/notebooks/test.py\n"
            "+++ b/notebooks/test.py\n"
            "@@ -1,3 +1,4 @@\n"
            " existing\n"
            "+new line at 2\n"
            " more\n"
        )
        findings = [
            _make_finding(
                severity="P2",
                file="notebooks/test.py",
                check_id="N3",
                line=2,
            )
        ]
        passed, scored = score_findings(findings, diff)
        # 80 - 15 (N3) = 65 < 75 threshold -> filtered
        assert scored[0].confidence == 65
        assert scored[0].filtered


# ---------------------------------------------------------------------------
# X2 with docs changes
# ---------------------------------------------------------------------------


class TestX2WithDocs:
    """X2 should be penalized when docs/01_core/ changes are in the diff."""

    def test_x2_with_docs_change_filtered(self):
        """X2 flagged but docs/01_core/ was also modified -> penalty."""
        findings = [
            _make_finding(
                severity="P2",
                file="src/bid_euchre/core/rules.py",
                check_id="X2",
                line=12,
            )
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        # 80 - 30 (X2 + docs present) = 50 < 75
        assert scored[0].confidence == 50
        assert scored[0].filtered
        assert "docs/01_core/" in scored[0].reasoning

    def test_x2_without_docs_change_passes(self):
        """X2 without docs in diff should not get docs-related penalty."""
        diff_no_docs = (
            "diff --git a/src/foo.py b/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+new_line\n"
        )
        findings = [
            _make_finding(
                severity="P2",
                file="src/foo.py",
                check_id="X2",
                line=1,
            )
        ]
        passed, scored = score_findings(findings, diff_no_docs)
        assert "docs/01_core/" not in scored[0].reasoning


# ---------------------------------------------------------------------------
# Convention checks in test files
# ---------------------------------------------------------------------------


class TestTestFileConvention:
    """Convention checks in test code should be penalized."""

    def test_x3_in_tests_penalized(self):
        findings = [
            _make_finding(
                severity="P2",
                file="tests/unit/test_foo.py",
                check_id="X3",
                line=999,
            )
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        # -40 (unmodified) + -20 (test convention) = 20 < 75
        assert scored[0].filtered
        assert "test code" in scored[0].reasoning

    def test_c4_in_tests_penalized(self):
        findings = [
            _make_finding(
                severity="P2",
                file="tests/integration/test_bar.py",
                check_id="C4",
                line=999,
            )
        ]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        assert scored[0].filtered
        assert "test code" in scored[0].reasoning


# ---------------------------------------------------------------------------
# _line_in_diff
# ---------------------------------------------------------------------------


class TestLineInDiff:
    """Verify unified diff parsing."""

    def test_added_line_11_found(self):
        # @@ +10,8 @@: context at 10, then added lines at 11 and 12
        assert _line_in_diff("src/bid_euchre/core/rules.py", 11, SAMPLE_DIFF)

    def test_added_line_12_found(self):
        assert _line_in_diff("src/bid_euchre/core/rules.py", 12, SAMPLE_DIFF)

    def test_context_line_not_found(self):
        # Line 10 is a context line (not added), should not match
        assert not _line_in_diff("src/bid_euchre/core/rules.py", 10, SAMPLE_DIFF)

    def test_wrong_file_not_found(self):
        assert not _line_in_diff("src/other_file.py", 12, SAMPLE_DIFF)

    def test_line_zero_not_found(self):
        # Line 0 is never a valid line number
        assert not _line_in_diff("src/bid_euchre/core/rules.py", 0, SAMPLE_DIFF)

    def test_empty_diff(self):
        assert not _line_in_diff("src/foo.py", 1, "")

    def test_malformed_hunk_header(self):
        """Malformed @@ header should be skipped without crashing."""
        diff = "+++ b/src/foo.py\n@@ malformed header @@\n+added line\n"
        # Should not crash
        result = _line_in_diff("src/foo.py", 1, diff)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# save_scoring_report
# ---------------------------------------------------------------------------


class TestSaveScoringReport:
    """Verify JSON report output."""

    def test_writes_valid_json(self, tmp_path):
        scored = [
            ScoredFinding(
                finding=_make_finding(),
                confidence=85,
                reasoning="No deductions applied",
                filtered=False,
            ),
            ScoredFinding(
                finding=_make_finding(line=999),
                confidence=40,
                reasoning="Finding is on an unmodified line",
                filtered=True,
            ),
        ]
        output_path = tmp_path / "subdir" / "scoring_report.json"
        save_scoring_report(scored, output_path)

        assert output_path.exists()
        report = json.loads(output_path.read_text())
        assert report["total_findings"] == 2
        assert report["passed"] == 1
        assert report["filtered"] == 1
        assert report["threshold"] == CONFIDENCE_THRESHOLD
        assert len(report["findings"]) == 2

    def test_creates_parent_directories(self, tmp_path):
        output_path = tmp_path / "a" / "b" / "c" / "report.json"
        save_scoring_report([], output_path)
        assert output_path.exists()
        report = json.loads(output_path.read_text())
        assert report["total_findings"] == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_findings_list(self):
        passed, scored = score_findings([], SAMPLE_DIFF)
        assert passed == []
        assert scored == []

    def test_finding_without_file(self):
        finding = {"severity": "P2", "message": "orphan finding"}
        passed, scored = score_findings([finding], SAMPLE_DIFF)
        # No file -> no diff check deduction -> confidence 80 >= 75
        assert len(passed) == 1
        assert scored[0].confidence == 80

    def test_finding_without_line(self):
        finding = {
            "severity": "P2",
            "file": "src/foo.py",
            "message": "missing line",
        }
        passed, scored = score_findings([finding], SAMPLE_DIFF)
        # line defaults to 0, and line=0 skips diff check -> confidence 80
        assert len(passed) == 1

    def test_finding_without_check_id(self):
        finding = {
            "severity": "P2",
            "file": "src/foo.py",
            "line": 1,
            "message": "no check id",
        }
        passed, scored = score_findings([finding], SAMPLE_DIFF)
        # No check_id means no check-specific deductions
        # But line 1 not in diff for src/foo.py in SAMPLE_DIFF -> -40
        assert scored[0].confidence == 40

    def test_custom_threshold(self):
        """Custom threshold should override default."""
        findings = [_make_finding(severity="P2", line=999)]  # -40 -> confidence 40
        passed_low, _ = score_findings(findings, SAMPLE_DIFF, threshold=30)
        passed_high, _ = score_findings(findings, SAMPLE_DIFF, threshold=50)
        assert len(passed_low) == 1  # 40 >= 30
        assert len(passed_high) == 0  # 40 < 50

    def test_multiple_deductions_stack(self):
        """Multiple heuristic deductions should stack."""
        findings = [
            _make_finding(
                severity="P2",
                file="tests/unit/test_foo.py",
                check_id="X3",
                line=999,
            )
        ]
        _, scored = score_findings(findings, SAMPLE_DIFF)
        # -40 (unmodified) + -20 (test convention) = 20
        assert scored[0].confidence == 20
        assert "unmodified line" in scored[0].reasoning
        assert "test code" in scored[0].reasoning

    def test_confidence_clamped_to_zero(self):
        """Confidence should never go below 0."""
        # C4 in known-complex test file, not in diff
        findings = [
            _make_finding(
                severity="P2",
                file="tests/unit/review_driver.py",
                check_id="C4",
                line=999,
            )
        ]
        _, scored = score_findings(findings, SAMPLE_DIFF)
        # -40 (unmodified) + -20 (test C4) + -25 (known complex) = -5 -> clamped to 0
        assert scored[0].confidence >= 0

    def test_unknown_severity_treated_as_p2(self):
        """Findings with unknown severity default to P2 scoring."""
        findings = [{"severity": "P3", "file": "src/foo.py", "line": 1}]
        passed, scored = score_findings(findings, SAMPLE_DIFF)
        # Unknown severity not in ("P0", "P1") -> scored as P2
        assert scored[0].confidence < 100  # Not pass-through like P0/P1
