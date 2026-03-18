"""Tests for Codex CLI review adapter — output parsing and finding normalization."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add scripts/internal to path for imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from codex_review_adapter import (
    _CLEAN_REVIEW_PATTERNS,
    CodexFinding,
    CodexReviewResult,
    _classify_error,
    _parse_reversed_format,
    _parse_standard_format,
    _resolve_codex_binary,
    _strip_to_relative,
    get_blocking_findings,
    invoke_codex_cli,
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

UNPARSEABLE_OUTPUT = """\
I've reviewed the changes and here are my thoughts:

The code looks generally well-structured. There are some concerns about
error handling in the main module that could be improved. The test coverage
seems adequate but could benefit from additional edge cases.

Overall this is a solid contribution.
"""

# --- Fixtures: Markdown table format (from AGENTS.md response template) ---

TABLE_FORMAT_OUTPUT = """\
## Codex Review

### Summary
- Files reviewed: 3 (2 library, 1 test)
- Findings: 1 CRITICAL, 1 WARNING, 1 NIT

### Findings

| Severity | File | Line | Check | Finding |
|----------|------|------|-------|---------|
| CRITICAL | src/bid_euchre/strategy/foo.py | 42 | C1 | random.Random() without seed |
| WARNING | src/bid_euchre/strategy/foo.py | 87 | C4 | Function compute_ev is 63 lines |
| NIT | src/bid_euchre/strategy/foo.py | 3 | — | Unused import os |

### Checks Performed
- [x] C1: Unseeded randomness
"""

TABLE_CLEAN_OUTPUT = """\
## Codex Review

### Summary
- Files reviewed: 2
- Findings: 0 CRITICAL, 0 WARNING, 0 NIT

No findings.

### Checks Performed
- [x] C1: Unseeded randomness
"""

TABLE_P_SEVERITY_OUTPUT = """\
| Severity | File | Line | Check | Finding |
|----------|------|------|-------|---------|
| P0 | src/bid_euchre/core/rules.py | 10 | X3 | Merge conflict marker |
| P1 | src/bid_euchre/sim/engine.py | 55 | C2 | Falsy numeric guard |
| P2 | tests/unit/test_rules.py | 20 | - | Minor style issue |
"""

# --- Fixtures: Prose/natural-language output ---

PROSE_WITH_FILES_OUTPUT = """\
I've reviewed the changes. Here are my observations:

- In src/bid_euchre/strategy/bidding.py:42, there's an unseeded random call
  that could affect determinism.
- The file src/bid_euchre/core/rules.py has a merge conflict marker at line 10.
- src/bid_euchre/sim/engine.py:55 could use some minor style improvements.
"""

PROSE_NO_FILES_OUTPUT = """\
I've reviewed the changes and everything looks good. The code is well-structured
and follows the project conventions. No concerns about the implementation.
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


class TestParseTableFormat:
    """Test parsing of markdown table row format from AGENTS.md template."""

    def test_parses_all_severities(self):
        findings = parse_codex_output(TABLE_FORMAT_OUTPUT)
        severities = {f.severity for f in findings}
        assert severities == {"P0", "P1", "P2"}

    def test_correct_finding_count(self):
        findings = parse_codex_output(TABLE_FORMAT_OUTPUT)
        assert len(findings) == 3

    def test_critical_maps_to_p0(self):
        findings = parse_codex_output(TABLE_FORMAT_OUTPUT)
        p0 = [f for f in findings if f.severity == "P0"]
        assert len(p0) == 1
        assert p0[0].check_id == "C1"
        assert p0[0].file == "src/bid_euchre/strategy/foo.py"
        assert p0[0].line == 42

    def test_warning_maps_to_p1(self):
        findings = parse_codex_output(TABLE_FORMAT_OUTPUT)
        p1 = [f for f in findings if f.severity == "P1"]
        assert len(p1) == 1
        assert p1[0].check_id == "C4"

    def test_nit_maps_to_p2(self):
        findings = parse_codex_output(TABLE_FORMAT_OUTPUT)
        p2 = [f for f in findings if f.severity == "P2"]
        assert len(p2) == 1
        assert p2[0].check_id is None  # "—" should become None

    def test_p_severity_in_table(self):
        """Tables using P0/P1/P2 directly instead of CRITICAL/WARNING/NIT."""
        findings = parse_codex_output(TABLE_P_SEVERITY_OUTPUT)
        assert len(findings) == 3
        assert findings[0].severity == "P0"
        assert findings[1].severity == "P1"
        assert findings[2].severity == "P2"

    def test_dash_check_id_becomes_none(self):
        """Check ID of '-' or '—' should be normalized to None."""
        findings = parse_codex_output(TABLE_P_SEVERITY_OUTPUT)
        nit = [f for f in findings if f.severity == "P2"]
        assert nit[0].check_id is None


class TestParseProseFallback:
    """Test prose/natural-language output parsing."""

    def test_extracts_findings_from_prose(self):
        findings = parse_codex_output(PROSE_WITH_FILES_OUTPUT)
        assert len(findings) >= 2  # At least the two clear file references

    def test_prose_file_paths_extracted(self):
        findings = parse_codex_output(PROSE_WITH_FILES_OUTPUT)
        files = {f.file for f in findings}
        assert "src/bid_euchre/strategy/bidding.py" in files
        assert "src/bid_euchre/core/rules.py" in files

    def test_prose_severity_inference(self):
        findings = parse_codex_output(PROSE_WITH_FILES_OUTPUT)
        bidding = [
            f for f in findings if f.file == "src/bid_euchre/strategy/bidding.py"
        ]
        assert len(bidding) == 1
        # "unseeded random" should infer P1
        assert bidding[0].severity == "P1"

    def test_prose_merge_conflict_is_p0(self):
        findings = parse_codex_output(PROSE_WITH_FILES_OUTPUT)
        rules = [f for f in findings if f.file == "src/bid_euchre/core/rules.py"]
        assert len(rules) == 1
        assert rules[0].severity == "P0"

    def test_prose_not_used_when_structured_found(self):
        """Prose fallback must NOT run when structured parsing succeeds."""
        findings = parse_codex_output(STANDARD_OUTPUT)
        # Should get exactly the 5 structured findings, not extra prose ones
        assert len(findings) == 5

    def test_prose_no_files_yields_no_findings(self):
        """Prose without file references produces zero findings."""
        findings = parse_codex_output(PROSE_NO_FILES_OUTPUT)
        assert len(findings) == 0


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


class TestCleanReviewDetection:
    """Test fail-safe: unparseable output must not be treated as clean."""

    def test_clean_output_matches_pattern(self):
        """Known clean-review phrases should be recognized."""
        assert _CLEAN_REVIEW_PATTERNS.search(CLEAN_OUTPUT) is not None

    def test_unparseable_output_no_match(self):
        """Prose output without clean-review signal should NOT match."""
        assert _CLEAN_REVIEW_PATTERNS.search(UNPARSEABLE_OUTPUT) is None

    def test_unparseable_yields_no_findings(self):
        """Unparseable output should produce zero parsed findings."""
        findings = parse_codex_output(UNPARSEABLE_OUTPUT)
        assert len(findings) == 0

    def test_lgtm_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("LGTM") is not None

    def test_zero_findings_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Review complete. 0 findings.") is not None

    def test_no_problems_found_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No problems found.") is not None

    def test_no_findings_without_found_matches(self):
        """'No findings.' (without 'found') should match — AGENTS.md uses this."""
        assert _CLEAN_REVIEW_PATTERNS.search("No findings.") is not None

    def test_no_issues_without_found_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No issues.") is not None

    def test_all_good_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("All good.") is not None

    def test_all_clear_matches(self):
        assert (
            _CLEAN_REVIEW_PATTERNS.search("All clear — nothing to report.") is not None
        )

    def test_ship_it_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Ship it!") is not None

    def test_approved_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Approved.") is not None

    def test_nothing_to_flag_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Nothing to flag.") is not None

    def test_changes_are_clean_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Changes are clean.") is not None

    def test_no_concerns_matches(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No concerns.") is not None

    def test_table_clean_output_detected(self):
        """AGENTS.md table format with 'No findings.' should be clean."""
        assert _CLEAN_REVIEW_PATTERNS.search(TABLE_CLEAN_OUTPUT) is not None

    def test_prose_no_files_matches_clean(self):
        """Positive prose without file references matches clean patterns."""
        assert _CLEAN_REVIEW_PATTERNS.search(PROSE_NO_FILES_OUTPUT) is not None


class TestExpandedCleanPatterns:
    """Test expanded clean-review patterns added for issue #799.

    Codex CLI produces varied phrasings for clean reviews. These tests
    cover patterns that were previously treated as "unparseable".
    """

    def test_no_significant_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No significant issues.") is not None

    def test_no_major_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No major issues found.") is not None

    def test_no_critical_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No critical issues.") is not None

    def test_no_blocking_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No blocking issues.") is not None

    def test_no_blockers(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No blockers.") is not None

    def test_no_violations(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No violations found.") is not None

    def test_everything_looks_good(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Everything looks good.") is not None

    def test_everything_checks_out(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Everything checks out.") is not None

    def test_i_found_no_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("I found no issues.") is not None

    def test_found_no_issues_without_i(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Found no issues.") is not None

    def test_i_dont_see_any_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("I don't see any issues.") is not None

    def test_do_not_see_issues(self):
        assert _CLEAN_REVIEW_PATTERNS.search("I do not see issues.") is not None

    def test_good_to_go(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Good to go.") is not None

    def test_ready_to_merge(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Ready to merge.") is not None

    def test_no_action_needed(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No action needed.") is not None

    def test_no_changes_required(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No changes required.") is not None

    def test_passes_all_checks(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Passes all checks.") is not None

    def test_code_is_correct(self):
        assert _CLEAN_REVIEW_PATTERNS.search("The code is correct.") is not None

    def test_plan_is_sound(self):
        assert _CLEAN_REVIEW_PATTERNS.search("The plan is sound.") is not None

    def test_changes_are_correct(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Changes are correct.") is not None

    def test_implementation_is_solid(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Implementation is solid.") is not None

    def test_looks_correct(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Looks correct.") is not None

    def test_nothing_stands_out(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Nothing stands out.") is not None

    def test_nothing_to_add(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Nothing to add.") is not None

    def test_no_problems_detected(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No problems detected.") is not None

    def test_no_errors_detected(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No errors detected.") is not None

    def test_satisfactory(self):
        assert _CLEAN_REVIEW_PATTERNS.search("satisfactory") is not None

    def test_no_items_to_flag(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No items to flag.") is not None

    def test_embedded_in_longer_output(self):
        """Clean signal embedded in a longer Codex response."""
        output = (
            "I've reviewed the plan file against the repo conventions.\n\n"
            "No significant issues found.\n\n"
            "The plan follows the standard template and references valid paths."
        )
        assert _CLEAN_REVIEW_PATTERNS.search(output) is not None

    def test_unparseable_still_rejected(self):
        """Expanded patterns must NOT match genuinely unparseable output."""
        assert _CLEAN_REVIEW_PATTERNS.search(UNPARSEABLE_OUTPUT) is None


# --- Tests for command construction (the bug that prompted this PR) ---


class TestBinaryResolution:
    """Test _resolve_codex_binary preference order."""

    @patch("codex_review_adapter.shutil.which", return_value="/usr/local/bin/codex")
    def test_prefers_path_binary(self, mock_which):
        assert _resolve_codex_binary() == ["codex"]

    @patch("codex_review_adapter.shutil.which", return_value=None)
    def test_falls_back_to_npx(self, mock_which):
        """When codex not in PATH, falls through to npx."""
        assert _resolve_codex_binary() == ["npx", "@openai/codex"]


class TestCommandConstruction:
    """Test that invoke_codex_cli builds valid CLI commands.

    The original bug was passing both --base and a positional prompt,
    which codex-cli v0.114.0 treats as mutually exclusive. These tests
    ensure the prompt is never included in the command.
    """

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_no_prompt_in_review_command(self, mock_resolve, mock_pty):
        """The review command must not include a positional prompt."""
        mock_pty.return_value = (0, "No issues found.")
        invoke_codex_cli(mode="standard", base="main")
        cmd = mock_pty.call_args[0][0]
        assert cmd == ["codex", "review", "--base", "main"]

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_mode_does_not_affect_command(self, mock_resolve, mock_pty):
        """Different modes must not change the command (prompt removed)."""
        mock_pty.return_value = (0, "LGTM")
        for mode in ("standard", "report-audit", "plan-audit"):
            invoke_codex_cli(mode=mode, base="main")
            cmd = mock_pty.call_args[0][0]
            assert cmd == ["codex", "review", "--base", "main"]

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch(
        "codex_review_adapter._resolve_codex_binary",
        return_value=["npx", "@openai/codex"],
    )
    def test_npx_fallback_command(self, mock_resolve, mock_pty):
        """When codex binary not found, falls back to npx."""
        mock_pty.return_value = (0, "LGTM")
        invoke_codex_cli(base="main")
        cmd = mock_pty.call_args[0][0]
        assert cmd == ["npx", "@openai/codex", "review", "--base", "main"]

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_custom_base_branch(self, mock_resolve, mock_pty):
        """Base branch argument is correctly passed."""
        mock_pty.return_value = (0, "LGTM")
        invoke_codex_cli(base="develop")
        cmd = mock_pty.call_args[0][0]
        assert cmd == ["codex", "review", "--base", "develop"]


class TestErrorClassification:
    """Test that CLI errors are classified correctly."""

    def test_argument_conflict_is_invocation_error(self):
        stderr = "error: the argument '--base <BRANCH>' cannot be used with '[PROMPT]'"
        assert _classify_error(stderr) == "cli_invocation_error"

    def test_unexpected_argument_is_invocation_error(self):
        stderr = "error: unexpected argument '--foo' found"
        assert _classify_error(stderr) == "cli_invocation_error"

    def test_usage_line_is_invocation_error(self):
        stderr = "Usage: codex review --base <BRANCH>"
        assert _classify_error(stderr) == "cli_invocation_error"

    def test_auth_failure_is_review_error(self):
        stderr = "Error: authentication failed"
        assert _classify_error(stderr) == "cli_review_error"

    def test_network_error_is_review_error(self):
        stderr = "Error: network timeout connecting to API"
        assert _classify_error(stderr) == "cli_review_error"

    def test_empty_stderr_is_review_error(self):
        assert _classify_error("") == "cli_review_error"

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_error_type_in_result(self, mock_resolve, mock_pty):
        """error_type must be set on failed results."""
        mock_pty.return_value = (
            2,
            "error: the argument '--base <BRANCH>' cannot be used with '[PROMPT]'",
        )
        result = invoke_codex_cli(base="main")
        assert not result.success
        assert result.error_type == "cli_invocation_error"

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_success_has_no_error_type(self, mock_resolve, mock_pty):
        """Successful results have no error_type."""
        mock_pty.return_value = (0, "LGTM")
        result = invoke_codex_cli(base="main")
        assert result.success
        assert result.error_type is None


class TestCodexReviewResultErrorType:
    """Test error_type field in serialization."""

    def test_error_type_in_to_dict(self):
        result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=3.0,
            error="Exit code 2",
            exit_code=2,
            error_type="cli_invocation_error",
        )
        d = result.to_dict()
        assert d["error_type"] == "cli_invocation_error"

    def test_none_error_type_in_to_dict(self):
        result = CodexReviewResult(
            success=True,
            findings=[],
            raw_output="LGTM",
            latency_seconds=60.0,
        )
        d = result.to_dict()
        assert d["error_type"] is None


class TestEnvVarLauncher:
    """Test CODEX_REVIEW_CMD env var configurable launcher."""

    def test_env_var_takes_priority(self):
        """CODEX_REVIEW_CMD overrides all other resolution paths."""
        with patch.dict(os.environ, {"CODEX_REVIEW_CMD": "my-codex"}):
            result = _resolve_codex_binary()
            assert result == ["my-codex"]

    def test_env_var_multi_word_split(self):
        """Multi-word commands are split by whitespace."""
        with patch.dict(
            os.environ,
            {"CODEX_REVIEW_CMD": "docker exec codex-container codex"},
        ):
            result = _resolve_codex_binary()
            assert result == ["docker", "exec", "codex-container", "codex"]

    @patch("codex_review_adapter.shutil.which", return_value="/usr/local/bin/codex")
    def test_env_var_overrides_path_binary(self, mock_which):
        """Env var wins even when codex is in PATH."""
        with patch.dict(os.environ, {"CODEX_REVIEW_CMD": "custom-codex"}):
            result = _resolve_codex_binary()
            assert result == ["custom-codex"]

    @patch("codex_review_adapter.shutil.which", return_value="/usr/local/bin/codex")
    def test_empty_env_var_falls_through(self, mock_which):
        """Empty env var is ignored, falls through to PATH binary."""
        with patch.dict(os.environ, {"CODEX_REVIEW_CMD": ""}):
            result = _resolve_codex_binary()
            assert result == ["codex"]

    @patch("codex_review_adapter.shutil.which", return_value="/usr/local/bin/codex")
    def test_whitespace_only_env_var_falls_through(self, mock_which):
        """Whitespace-only env var is ignored, falls through to PATH binary."""
        with patch.dict(os.environ, {"CODEX_REVIEW_CMD": "   "}):
            result = _resolve_codex_binary()
            assert result == ["codex"]

    @patch("codex_review_adapter.shutil.which", return_value=None)
    def test_unset_env_var_uses_existing_chain(self, mock_which):
        """When env var is not set, existing preference chain applies."""
        env = os.environ.copy()
        env.pop("CODEX_REVIEW_CMD", None)
        with patch.dict(os.environ, env, clear=True):
            result = _resolve_codex_binary()
            assert result == ["npx", "@openai/codex"]

    @patch("codex_plan_review_adapter._run_with_pty")
    def test_env_var_in_invoke_command(self, mock_pty):
        """Env-configured command appears in invoke_codex_cli() command."""
        mock_pty.return_value = (0, "LGTM")
        with patch.dict(
            os.environ,
            {"CODEX_REVIEW_CMD": "docker exec codex-container codex"},
        ):
            invoke_codex_cli(base="main")
            cmd = mock_pty.call_args[0][0]
            assert cmd == [
                "docker",
                "exec",
                "codex-container",
                "codex",
                "review",
                "--base",
                "main",
            ]


# --- Timeout and Error Path Tests ---


class TestCodexCLITimeout:
    """Test timeout handling in invoke_codex_cli."""

    @patch(
        "codex_plan_review_adapter._run_with_pty", return_value=(None, "partial output")
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_timeout_returns_failure(self, mock_resolve, mock_pty):
        """Timeout (returncode=None) produces success=False."""
        result = invoke_codex_cli(base="main")
        assert result.success is False
        assert "Timeout" in result.error

    @patch("codex_plan_review_adapter._run_with_pty", return_value=(None, ""))
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_timeout_with_empty_output(self, mock_resolve, mock_pty):
        """Timeout with no output still returns error."""
        result = invoke_codex_cli(base="main")
        assert result.success is False
        assert "Timeout" in result.error
        assert result.raw_output == ""

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(2, "error: bad argument"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_nonzero_exit_returns_failure(self, mock_resolve, mock_pty):
        """Non-zero exit code produces success=False."""
        result = invoke_codex_cli(base="main")
        assert result.success is False
        assert "Exit code 2" in result.error

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(0, "gibberish that matches nothing"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_unparseable_output_returns_advisory_success(self, mock_resolve, mock_pty):
        """Output matching no patterns returns success with parse_confidence=unparseable."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "unparseable"
        assert result.findings == []


# --- Parse Confidence Tests ---


class TestParseConfidence:
    """Test parse_confidence field is set correctly on all code paths."""

    @patch("codex_plan_review_adapter._run_with_pty", return_value=(0, STANDARD_OUTPUT))
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_structured_findings_set_structured(self, mock_resolve, mock_pty):
        """Parsed structured findings → parse_confidence=structured."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "structured"
        assert len(result.findings) > 0

    @patch("codex_plan_review_adapter._run_with_pty", return_value=(0, CLEAN_OUTPUT))
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_clean_output_set_clean_signal(self, mock_resolve, mock_pty):
        """Clean review output → parse_confidence=clean_signal."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "clean_signal"
        assert result.findings == []

    @patch("codex_plan_review_adapter._run_with_pty", return_value=(0, ""))
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_empty_output_set_clean_signal(self, mock_resolve, mock_pty):
        """Empty output → parse_confidence=clean_signal."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "clean_signal"

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(0, "gibberish that matches nothing"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_unparseable_output_set_unparseable(self, mock_resolve, mock_pty):
        """Unparseable output → parse_confidence=unparseable, success=True."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "unparseable"
        assert result.findings == []

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(1, "Review was interrupted. Please re-run /review"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_interrupted_codex_returns_backend_error(self, mock_resolve, mock_pty):
        """Codex 'interrupted' exit-1 → success=True, parse_confidence=backend_error."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "backend_error"
        assert result.findings == []
        assert result.exit_code == 1

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(1, "Please try again later"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_try_again_returns_backend_error(self, mock_resolve, mock_pty):
        """'try again' in output → backend_error, not hard failure."""
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.parse_confidence == "backend_error"

    @patch(
        "codex_plan_review_adapter._run_with_pty",
        return_value=(2, "error: the argument '--base' cannot be used with '[PROMPT]'"),
    )
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_real_cli_error_still_fails(self, mock_resolve, mock_pty):
        """Non-retryable CLI errors remain success=False."""
        result = invoke_codex_cli(base="main")
        assert result.success is False
        assert result.error_type == "cli_invocation_error"
        assert result.parse_confidence is None

    def test_parse_confidence_in_to_dict(self):
        """parse_confidence field appears in serialization."""
        result = CodexReviewResult(
            success=True,
            findings=[],
            raw_output="LGTM",
            latency_seconds=1.0,
            parse_confidence="clean_signal",
        )
        d = result.to_dict()
        assert d["parse_confidence"] == "clean_signal"

    def test_parse_confidence_none_in_to_dict(self):
        """parse_confidence=None when not set (error paths)."""
        result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=1.0,
            error="Timeout",
        )
        d = result.to_dict()
        assert d["parse_confidence"] is None


# =====================================================================
# Tests for empty-diff / stale-worktree detection (RC1 fix)
# =====================================================================

# Real Codex output captured from PR #800 (stale worktree, empty diff)
_RC1_FIXTURE_PR800 = (
    "`git diff 13ba62ee796891736b44b4bd5be380ab6b971938` is empty in this "
    "worktree, so there are no tracked code changes to review relative to "
    "the provided merge base. The only difference present is an untracked "
    "session plan file, which is outside the requested diff."
)

# Real Codex output captured from PR #820 (stale worktree, alternate phrasing)
_RC1_FIXTURE_PR820 = (
    "`git diff 3e77dcb74a2b9220ab97ba05ed2dd4dcfca3b295` is empty in this "
    "worktree, so there are no committed changes to review relative to "
    "`main`. I only see untracked plan-session files, which are outside "
    "the requested diff."
)

# Real Codex output captured from PR #809 (yet another phrasing)
_RC1_FIXTURE_PR809 = (
    "`git diff 13ba62ee796891736b44b4bd5be380ab6b971938` is empty for "
    "tracked files, so there are no code changes relative to `main` to "
    "review. The only visible differences are untracked local files, "
    "which are outside the requested diff."
)


class TestEmptyDiffDetection:
    """RC1 fix: empty-diff output from stale worktrees should be clean."""

    def test_pr800_empty_diff_is_clean(self):
        """PR #800 exact output: 'is empty in this worktree'."""
        assert _CLEAN_REVIEW_PATTERNS.search(_RC1_FIXTURE_PR800) is not None

    def test_pr820_empty_diff_is_clean(self):
        """PR #820 exact output: 'no committed changes to review'."""
        assert _CLEAN_REVIEW_PATTERNS.search(_RC1_FIXTURE_PR820) is not None

    def test_pr809_empty_diff_is_clean(self):
        """PR #809 exact output: 'no code changes relative to'."""
        assert _CLEAN_REVIEW_PATTERNS.search(_RC1_FIXTURE_PR809) is not None

    def test_no_changes_to_review_short(self):
        assert _CLEAN_REVIEW_PATTERNS.search("No changes to review.") is not None

    def test_nothing_to_review_short(self):
        assert _CLEAN_REVIEW_PATTERNS.search("Nothing to review.") is not None

    def test_empty_diff_yields_zero_findings(self):
        """Empty-diff output should produce zero parsed findings."""
        assert parse_codex_output(_RC1_FIXTURE_PR800) == []
        assert parse_codex_output(_RC1_FIXTURE_PR820) == []

    @patch("codex_plan_review_adapter._run_with_pty")
    @patch("codex_review_adapter._resolve_codex_binary", return_value=["codex"])
    def test_empty_diff_returns_success(self, mock_resolve, mock_pty):
        """Empty-diff output should produce success=True (not Unparseable)."""
        mock_pty.return_value = (0, _RC1_FIXTURE_PR800)
        result = invoke_codex_cli(base="main")
        assert result.success is True
        assert result.error is None
        assert len(result.findings) == 0


# =====================================================================
# Tests for reversed format parsing (RC2 fix)
# =====================================================================

# Real Codex output captured from PR #818 (reversed format with findings)
_RC2_FIXTURE_PR818 = (
    "The new tmux launcher has a default-configuration failure in its pane "
    "targeting, and it also derives steward worktree paths incorrectly when "
    "invoked from a linked worktree. Those issues are enough to make the new "
    "session bootstrap unreliable.\n"
    "\n"
    "Full review comments:\n"
    "\n"
    "- [P1] Use valid tmux pane indices for the dashboard layout \u2014 "
    "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/"
    ".claude/tmux/steward-session.sh:90-95\n"
    "  On a stock tmux setup, pane indices start at `0`, and this repo does "
    "not set `pane-base-index` anywhere.\n"
    "\n"
    "- [P2] Resolve the primary checkout before building steward worktree "
    "paths \u2014 /Users/claude_runner/Projects/Bid-Euchre-meta/"
    "Bid-Euchre-steward-author/.claude/tmux/steward-session.sh:36-42\n"
    "  If this launcher is started from an existing linked worktree such as "
    "`Bid-Euchre-steward-author`, `REPO_NAME` is captured from that checkout.\n"
    "\n"
    "- [P2] Guard the `caffeinate` wrapper on hosts that do not provide it "
    "\u2014 /Users/claude_runner/Projects/Bid-Euchre-meta/"
    "Bid-Euchre-steward-author/.claude/tmux/steward-session.sh:67-67\n"
    "  On Linux or any machine without the macOS-only `caffeinate` utility, "
    "both attach paths unconditionally run `exec caffeinate`."
)


class TestReversedFormatParsing:
    """RC2 fix: reversed format [P1] message — /abs/path:line-range."""

    def test_pr818_full_replay(self):
        """Full PR #818 raw output: should extract exactly 3 findings."""
        findings = parse_codex_output(_RC2_FIXTURE_PR818)
        assert len(findings) == 3
        assert findings[0].severity == "P1"
        assert findings[1].severity == "P2"
        assert findings[2].severity == "P2"

    def test_pr818_first_finding_details(self):
        findings = parse_codex_output(_RC2_FIXTURE_PR818)
        f = findings[0]
        assert f.severity == "P1"
        assert f.line == 90
        assert "tmux pane indices" in f.message

    def test_pr818_file_paths_stripped(self):
        """Absolute paths should be stripped to repo-relative."""
        # Mock cwd to the repo root embedded in the fixture paths
        repo_root = (
            "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author"
        )
        with patch("codex_review_adapter.os.getcwd", return_value=repo_root):
            findings = parse_codex_output(_RC2_FIXTURE_PR818)
        for f in findings:
            assert not f.file.startswith("/Users"), f"Path not stripped: {f.file}"
            assert ".claude/tmux/steward-session.sh" in f.file

    def test_reversed_single_line(self):
        """Single finding in reversed format."""
        line = "- [P1] Missing error handling \u2014 src/bid_euchre/core/rules.py:42"
        finding = _parse_reversed_format(line)
        assert finding is not None
        assert finding.severity == "P1"
        assert finding.file == "src/bid_euchre/core/rules.py"
        assert finding.line == 42
        assert "error handling" in finding.message

    def test_reversed_line_range_extracts_start(self):
        """Line range like 90-95 should extract just 90."""
        line = "- [P0] Critical bug \u2014 scripts/internal/foo.py:90-95"
        finding = _parse_reversed_format(line)
        assert finding is not None
        assert finding.line == 90

    def test_reversed_no_line_number(self):
        """Reversed format without line number."""
        line = "- [P2] Style issue \u2014 src/bid_euchre/sim/engine.py"
        finding = _parse_reversed_format(line)
        assert finding is not None
        assert finding.line == 0
        assert finding.file == "src/bid_euchre/sim/engine.py"

    def test_reversed_with_check_id_in_message(self):
        """Check ID in message should be extracted."""
        line = "- [P1] Unseeded random (C1) \u2014 src/bid_euchre/strategy/foo.py:10"
        finding = _parse_reversed_format(line)
        assert finding is not None
        assert finding.check_id == "C1"

    def test_reversed_does_not_match_standard(self):
        """Standard format should NOT be parsed by reversed regex."""
        line = "[P1] src/foo.py:42 \u2014 Some message"
        finding = _parse_reversed_format(line)
        # Standard format has no leading bullet, so reversed regex should not match
        assert finding is None

    def test_reversed_absolute_path_stripped(self):
        """Absolute path should be stripped to repo-relative via cwd."""
        line = "- [P1] Bug \u2014 /fake/repo/src/bid_euchre/core/rules.py:10"
        with patch("codex_review_adapter.os.getcwd", return_value="/fake/repo"):
            finding = _parse_reversed_format(line)
        assert finding is not None
        assert finding.file == "src/bid_euchre/core/rules.py"

    def test_strip_to_relative_with_cwd_match(self):
        """_strip_to_relative removes cwd prefix."""
        with patch("codex_review_adapter.os.getcwd", return_value="/a/b"):
            assert _strip_to_relative("/a/b/src/foo.py") == "src/foo.py"

    def test_strip_to_relative_no_match(self):
        """_strip_to_relative returns path unchanged if cwd doesn't match."""
        with patch("codex_review_adapter.os.getcwd", return_value="/other"):
            assert _strip_to_relative("/a/b/src/foo.py") == "/a/b/src/foo.py"


# =====================================================================
# Tests for expanded prose file extensions (RC2 prose fix)
# =====================================================================


class TestExpandedProseExtensions:
    """Prose fallback should match .sh, .yaml, .json, etc."""

    def test_prose_matches_sh_file(self):
        output = "The script scripts/internal/post-pr-review.sh has a bug at line 42."
        findings = parse_codex_output(output)
        assert len(findings) >= 1
        assert any("post-pr-review.sh" in f.file for f in findings)

    def test_prose_matches_yaml_file(self):
        output = "In experiments/configs/quick_test.yaml:10, the seed is missing."
        findings = parse_codex_output(output)
        assert len(findings) >= 1
        assert any("quick_test.yaml" in f.file for f in findings)

    def test_prose_matches_json_file(self):
        output = "The file src/bid_euchre/validation/schema.json has wrong format."
        findings = parse_codex_output(output)
        assert len(findings) >= 1

    def test_prose_matches_claude_dir(self):
        output = "Check .claude/hooks/post-pr-review.sh:5 for the sentinel logic."
        findings = parse_codex_output(output)
        assert len(findings) >= 1
        assert any("post-pr-review.sh" in f.file for f in findings)

    def test_prose_no_match_system_path(self):
        """System paths like /usr/bin/bash should NOT match prose regex."""
        output = "The /usr/bin/bash interpreter is version 5.2."
        findings = parse_codex_output(output)
        assert len(findings) == 0

    def test_prose_no_match_bare_absolute_path(self):
        """Bare absolute path without known prefix should not match."""
        output = "See /Users/someone/Desktop/notes.txt for details."
        findings = parse_codex_output(output)
        assert len(findings) == 0


# =====================================================================
# Tests for line range handling in all regexes (Step 4)
# =====================================================================


class TestLineRangeHandling:
    """All regex formats should handle line ranges like :10-20."""

    def test_standard_format_line_range(self):
        line = "[P1] src/bid_euchre/core/rules.py:10-20 \u2014 Bug found"
        finding = _parse_standard_format(line)
        assert finding is not None
        assert finding.line == 10
        assert finding.file == "src/bid_euchre/core/rules.py"

    def test_standard_format_single_line_still_works(self):
        line = "[P1] src/foo.py:42 \u2014 Some message"
        finding = _parse_standard_format(line)
        assert finding is not None
        assert finding.line == 42

    def test_table_format_line_range(self):
        output = "| P1 | src/bid_euchre/core/rules.py | 10-20 | C1 | Bug found |"
        findings = parse_codex_output(output)
        assert len(findings) == 1
        assert findings[0].line == 10

    def test_prose_format_line_range(self):
        output = "In src/bid_euchre/core/rules.py:10-20, there's a critical bug."
        findings = parse_codex_output(output)
        assert len(findings) >= 1
        assert any(f.line == 10 for f in findings)


# =====================================================================
# Tests for parse ordering (Pass 1 > Pass 1.5 > Pass 2)
# =====================================================================


class TestParseOrdering:
    """Ensure correct parse priority: standard > reversed > prose."""

    def test_standard_format_preferred_over_reversed(self):
        """If both standard and reversed could match, standard wins."""
        # Standard format: [P1] file:line — message
        output = "[P1] src/foo.py:42 \u2014 Some message"
        findings = parse_codex_output(output)
        assert len(findings) == 1
        assert findings[0].file == "src/foo.py"
        assert findings[0].line == 42

    def test_reversed_tried_before_prose(self):
        """When standard doesn't match, reversed should match before prose."""
        # This line matches reversed format AND contains a file ref for prose.
        # Reversed should win because it has higher fidelity (severity tag).
        output = "- [P1] Bug in the code \u2014 src/bid_euchre/core/rules.py:42"
        findings = parse_codex_output(output)
        assert len(findings) == 1
        assert findings[0].severity == "P1"
        assert findings[0].file == "src/bid_euchre/core/rules.py"

    def test_prose_only_when_nothing_else_matches(self):
        """Prose fallback fires only when standard and reversed find nothing."""
        output = (
            "I found a bug in src/bid_euchre/core/rules.py:42, it uses unseeded random."
        )
        findings = parse_codex_output(output)
        assert len(findings) >= 1
        # This should be parsed by prose (no [P1] tag)
        assert findings[0].severity == "P1"  # "unseeded" → P1
