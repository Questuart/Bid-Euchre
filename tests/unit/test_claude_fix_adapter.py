"""Tests for Claude fix adapter — auto-fix application and summary generation."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts/internal to path for imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from claude_fix_adapter import FixSummary, apply_fixes, save_fix_summary

# --- Test fixtures ---

NONE_COMPARISON_CODE = """\
def check_value(x):
    if x == None:
        return "missing"
    if x != None:
        return "present"
    return "unknown"
"""

TRUE_FALSE_CODE = """\
def check_flag(flag):
    if flag == True:
        do_something()
    if flag == False:
        do_other()
"""

BREAKPOINT_CODE = """\
def process():
    x = 1
    breakpoint()
    return x
"""

MIXED_CODE = """\
def mixed():
    if x == None:
        pass
    if flag == True:
        pass
    y = y or 0.5
"""

CLEAN_CODE = """\
def clean():
    if x is None:
        return True
    return False
"""


class TestApplyFixes:
    """Test fix application on individual patterns."""

    def test_fixes_eq_none(self, tmp_path):
        """== None should be replaced with 'is None'."""
        f = tmp_path / "test.py"
        f.write_text(NONE_COMPARISON_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 2,
                "check_id": "X3",
                "message": "Use 'is None' instead of '== None'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_applied >= 1

        content = f.read_text()
        assert "x is None" in content

    def test_fixes_ne_none(self, tmp_path):
        """!= None should be replaced with 'is not None'."""
        f = tmp_path / "test.py"
        f.write_text(NONE_COMPARISON_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 4,
                "check_id": "X3",
                "message": "Use 'is not None' instead of '!= None'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_applied >= 1

        content = f.read_text()
        assert "x is not None" in content

    def test_fixes_eq_true(self, tmp_path):
        """== True should be simplified."""
        f = tmp_path / "test.py"
        f.write_text(TRUE_FALSE_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 2,
                "check_id": "X3",
                "message": "Use 'if x:' instead of '== True'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_applied >= 1

        content = f.read_text()
        assert "if flag:" in content

    def test_fixes_eq_false(self, tmp_path):
        """== False should be simplified."""
        f = tmp_path / "test.py"
        f.write_text(TRUE_FALSE_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 4,
                "check_id": "X3",
                "message": "Use 'if not x:' instead of '== False'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_applied >= 1

        content = f.read_text()
        assert "if not flag" in content

    def test_removes_breakpoint(self, tmp_path):
        """breakpoint() lines should be removed."""
        f = tmp_path / "test.py"
        f.write_text(BREAKPOINT_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 3,
                "check_id": "X3",
                "message": "breakpoint() call in code",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_applied == 1

        content = f.read_text()
        assert "breakpoint()" not in content


class TestSkippedFindings:
    """Test that non-auto-fixable findings are properly skipped."""

    def test_skips_c1_correctness(self, tmp_path):
        """C1 (unseeded RNG) should not be auto-fixed."""
        f = tmp_path / "test.py"
        f.write_text("rng = random.Random()\n")

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 1,
                "check_id": "C1",
                "message": "Unseeded random.Random()",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_skipped == 1
        assert summary.fixes_applied == 0

    def test_skips_c2_correctness(self, tmp_path):
        """C2 (falsy guard) should not be auto-fixed."""
        f = tmp_path / "test.py"
        f.write_text("x = x or 0.5\n")

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 1,
                "check_id": "C2",
                "message": "Falsy numeric guard",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_skipped == 1
        assert summary.fixes_applied == 0

    def test_skips_p2_findings(self, tmp_path):
        """P2 (non-blocking) findings should be ignored entirely."""
        f = tmp_path / "test.py"
        f.write_text("if x == None:\n    pass\n")

        findings = [
            {
                "severity": "P2",
                "file": "test.py",
                "line": 1,
                "check_id": "X3",
                "message": "Use 'is None' instead of '== None'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        # P2 not in P0/P1, so filtered out
        assert summary.fixes_applied == 0


class TestEdgeCases:
    """Test edge cases in fix application."""

    def test_missing_file(self, tmp_path):
        """Missing file should be recorded as error."""
        findings = [
            {
                "severity": "P1",
                "file": "nonexistent.py",
                "line": 1,
                "check_id": "X3",
                "message": "breakpoint() call in code",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_errored == 1

    def test_line_out_of_range(self, tmp_path):
        """Line number beyond file length should be an error."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 999,
                "check_id": "X3",
                "message": "breakpoint() call in code",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        assert summary.fixes_errored == 1

    def test_no_findings(self, tmp_path):
        """Empty findings list should produce empty summary."""
        summary = apply_fixes([], repo_root=tmp_path)
        assert summary.fixes_applied == 0
        assert summary.fixes_skipped == 0
        assert summary.fixes_errored == 0

    def test_clean_code_no_change(self, tmp_path):
        """Code that already follows conventions should not be changed."""
        f = tmp_path / "test.py"
        f.write_text(CLEAN_CODE)

        findings = [
            {
                "severity": "P1",
                "file": "test.py",
                "line": 2,
                "check_id": "X3",
                "message": "Use 'is None' instead of '== None'",
            }
        ]
        summary = apply_fixes(findings, repo_root=tmp_path)
        # Pattern won't match because code already uses 'is None'
        assert summary.fixes_applied == 0

        content = f.read_text()
        assert content == CLEAN_CODE  # Unchanged


class TestFixSummary:
    """Test FixSummary serialization."""

    def test_to_dict(self):
        summary = FixSummary(fixes_applied=2, fixes_skipped=1)
        d = summary.to_dict()
        assert d["fixes_applied"] == 2
        assert d["fixes_skipped"] == 1
        assert d["actions"] == []

    def test_save_summary(self, tmp_path):
        """save_fix_summary should create both JSON and markdown files."""
        summary = FixSummary(fixes_applied=1, fixes_skipped=0)
        save_fix_summary(summary, pr_number=99, iteration=1, base_dir=tmp_path)

        rdir = tmp_path / "pr_99" / "round_1"
        assert (rdir / "fix_summary.json").exists()
        assert (rdir / "claude_fix_summary.md").exists()

        # Verify markdown content
        md = (rdir / "claude_fix_summary.md").read_text()
        assert "Round 1" in md
        assert "Fixes applied: 1" in md
