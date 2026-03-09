"""Tests for Codex CLI review adapter — output parsing and finding normalization."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts/internal to path for imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from codex_review_adapter import (
    CodexFinding,
    CodexReviewResult,
    get_blocking_findings,
    parse_codex_output,
)

# --- Fixture: Codex CLI output samples ---

STANDARD_OUTPUT = """\
Reviewing changes against main...

[P0] src/bid_euchre/core/rules.py:42 — Merge conflict marker found (X3)
[P1] src/bid_euchre/strategy/bidding.py:156 — Unseeded random.Random() — non-deterministic (C1)
[P1] src/bid_euchre/features/hand_eval.py:89 — Falsy numeric guard: x = x or 0.5 (C2)
[P2] src/bid_euchre/sim/engine.py:203 — Use 'is None' instead of '== None'
[P2] tests/unit/test_rules.py:44 — breakpoint() call in code

Review complete. 5 findings (1 P0, 2 P1, 2 P2).
"""

ALT_FORMAT_OUTPUT = """\
[CRITICAL][X3] src/bid_euchre/core/rules.py:42 — Merge conflict marker
[WARNING][C1] src/bid_euchre/strategy/bidding.py:156 — Unseeded random.Random()
[NIT] src/bid_euchre/sim/engine.py:203 — Use 'is None' instead of '== None'
"""

MIXED_OUTPUT = """\
Some preamble text that should be ignored.

[P1] src/foo.py:10 — Import boundary violation (X3)
[CRITICAL][C2] src/bar.py:20 — Falsy numeric guard

More text to ignore.

[P2] src/baz.py — Convention issue without line number
"""

CLEAN_OUTPUT = """\
Reviewing changes against main...

No issues found. The changes look good.

Review complete. 0 findings.
"""

EMPTY_OUTPUT = ""

DUPLICATE_OUTPUT = """\
[P1] src/foo.py:10 — Same issue
[P1] src/foo.py:10 — Same issue
[P1] src/foo.py:10 — Same issue
"""


class TestParseStandardFormat:
    """Test parsing of standard [P1] file:line — message format."""

    def test_parses_all_severities(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        severities = {f.severity for f in findings}
        assert severities == {"P0", "P1", "P2"}

    def test_correct_finding_count(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        assert len(findings) == 5

    def test_p0_finding(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        p0 = [f for f in findings if f.severity == "P0"]
        assert len(p0) == 1
        assert p0[0].file == "src/bid_euchre/core/rules.py"
        assert p0[0].line == 42
        assert p0[0].check_id == "X3"
        assert "merge conflict" in p0[0].message.lower()

    def test_p1_findings(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        p1 = [f for f in findings if f.severity == "P1"]
        assert len(p1) == 2
        check_ids = {f.check_id for f in p1}
        assert check_ids == {"C1", "C2"}

    def test_file_paths_extracted(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        files = {f.file for f in findings}
        assert "src/bid_euchre/core/rules.py" in files
        assert "src/bid_euchre/strategy/bidding.py" in files

    def test_line_numbers_extracted(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        lines = {f.file: f.line for f in findings}
        assert lines["src/bid_euchre/core/rules.py"] == 42
        assert lines["src/bid_euchre/strategy/bidding.py"] == 156


class TestParseAltFormat:
    """Test parsing of [CRITICAL][C1] format."""

    def test_parses_critical_as_p0(self):
        findings = parse_codex_output(ALT_FORMAT_OUTPUT)
        critical = [f for f in findings if f.severity == "P0"]
        assert len(critical) == 1
        assert critical[0].check_id == "X3"

    def test_parses_warning_as_p1(self):
        findings = parse_codex_output(ALT_FORMAT_OUTPUT)
        warnings = [f for f in findings if f.severity == "P1"]
        assert len(warnings) == 1
        assert warnings[0].check_id == "C1"

    def test_parses_nit_as_p2(self):
        findings = parse_codex_output(ALT_FORMAT_OUTPUT)
        nits = [f for f in findings if f.severity == "P2"]
        assert len(nits) == 1

    def test_correct_total_count(self):
        findings = parse_codex_output(ALT_FORMAT_OUTPUT)
        assert len(findings) == 3


class TestParseMixedFormat:
    """Test parsing of mixed format output."""

    def test_parses_both_formats(self):
        findings = parse_codex_output(MIXED_OUTPUT)
        assert len(findings) == 3

    def test_ignores_preamble(self):
        findings = parse_codex_output(MIXED_OUTPUT)
        # "Some preamble text" should not appear as a finding
        assert all("preamble" not in f.message.lower() for f in findings)

    def test_handles_missing_line_number(self):
        findings = parse_codex_output(MIXED_OUTPUT)
        no_line = [f for f in findings if f.file == "src/baz.py"]
        assert len(no_line) == 1
        assert no_line[0].line == 0  # Default when no line number


class TestParseEdgeCases:
    """Test edge cases in output parsing."""

    def test_clean_output_no_findings(self):
        findings = parse_codex_output(CLEAN_OUTPUT)
        assert len(findings) == 0

    def test_empty_output_no_findings(self):
        findings = parse_codex_output(EMPTY_OUTPUT)
        assert len(findings) == 0

    def test_deduplicates_findings(self):
        findings = parse_codex_output(DUPLICATE_OUTPUT)
        assert len(findings) == 1


class TestCategorization:
    """Test finding categorization logic."""

    def test_c1_is_correctness(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        c1 = [f for f in findings if f.check_id == "C1"]
        assert all(f.category == "correctness" for f in c1)

    def test_c2_is_correctness(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        c2 = [f for f in findings if f.check_id == "C2"]
        assert all(f.category == "correctness" for f in c2)

    def test_x3_is_process(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        x3 = [f for f in findings if f.check_id == "X3"]
        assert all(f.category == "process" for f in x3)


class TestBlockingFilter:
    """Test blocking findings filter."""

    def test_p0_is_blocking(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        blocking = get_blocking_findings(findings)
        assert any(f.severity == "P0" for f in blocking)

    def test_p1_is_blocking(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        blocking = get_blocking_findings(findings)
        assert any(f.severity == "P1" for f in blocking)

    def test_p2_not_blocking(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        blocking = get_blocking_findings(findings)
        assert all(f.severity != "P2" for f in blocking)

    def test_blocking_count(self):
        findings = parse_codex_output(STANDARD_OUTPUT)
        blocking = get_blocking_findings(findings)
        assert len(blocking) == 3  # 1 P0 + 2 P1


class TestCodexReviewResult:
    """Test CodexReviewResult serialization."""

    def test_to_dict_round_trip(self):
        result = CodexReviewResult(
            success=True,
            findings=[
                CodexFinding(
                    severity="P1",
                    file="test.py",
                    line=1,
                    category="correctness",
                    check_id="C1",
                    message="test finding",
                )
            ],
            raw_output="raw",
            latency_seconds=1.5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["findings"]) == 1
        assert d["findings"][0]["severity"] == "P1"
        assert d["latency_seconds"] == 1.5

    def test_error_result(self):
        result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=300.0,
            error="Timeout after 300s",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Timeout after 300s"
