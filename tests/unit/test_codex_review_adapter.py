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
    _resolve_codex_binary,
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
