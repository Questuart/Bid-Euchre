"""Tests for codex plan review adapter -- tier detection, output parsing, and failsafe."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add scripts/internal to path for imports
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "internal")
)

from codex_plan_review_adapter import (
    PlanReviewFinding,
    _build_claude_review_prompt,
    _check_codex_auth,
    detect_plan_tier,
    invoke_claude_failsafe,
    parse_plan_findings,
    plan_state_key,
)

# --- Tier Detection Tests ---


class TestTierOverrideFrontmatter:
    """Test that frontmatter override always wins."""

    def test_tier_override_frontmatter_small(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("<!-- review-tier: small -->\n# Big Plan\n" + "x\n" * 500)
        assert detect_plan_tier(plan) == "small"

    def test_tier_override_frontmatter_governing(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("<!-- review-tier: governing -->\n# Tiny Plan\n")
        assert detect_plan_tier(plan) == "governing"

    def test_tier_override_frontmatter_medium(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("# Header\n<!-- review-tier: medium -->\nShort plan.\n")
        assert detect_plan_tier(plan) == "medium"

    def test_override_not_in_first_10_lines_ignored(self, tmp_path: Path) -> None:
        """Override past line 10 is not detected; file is >80 lines so medium."""
        plan = tmp_path / "test.md"
        content = "\n".join([f"Line {i}" for i in range(85)])
        content += "\n<!-- review-tier: governing -->\n"
        plan.write_text(content)
        # Should NOT be governing since override is past line 10
        # But >80 lines triggers medium
        assert detect_plan_tier(plan) == "medium"


class TestTierInitiativePath:
    """Test initiative path detection."""

    def test_tier_initiative_path(self, tmp_path: Path) -> None:
        initiative_dir = tmp_path / "plans" / "arc_d_v2"
        initiative_dir.mkdir(parents=True)
        plan = initiative_dir / "foo.md"
        plan.write_text("# Some plan\n")
        assert detect_plan_tier(plan) == "governing"

    def test_tier_templates_excluded(self, tmp_path: Path) -> None:
        """plans/_templates/ should NOT be treated as governing."""
        template_dir = tmp_path / "plans" / "_templates"
        template_dir.mkdir(parents=True)
        plan = template_dir / "foo.md"
        plan.write_text("# Template\n")
        assert detect_plan_tier(plan) == "small"

    def test_tier_sessions_not_governing(self, tmp_path: Path) -> None:
        """plans/sessions/ should NOT be treated as governing."""
        session_dir = tmp_path / "plans" / "sessions"
        session_dir.mkdir(parents=True)
        plan = session_dir / "2026-03-15_test.md"
        plan.write_text("# Short session plan\n")
        assert detect_plan_tier(plan) == "small"


class TestTierContentEscalation:
    """Test content-based tier escalation."""

    def test_tier_session_short(self, tmp_path: Path) -> None:
        """Short (<80 lines) plan in sessions/ -> small."""
        session_dir = tmp_path / "plans" / "sessions"
        session_dir.mkdir(parents=True)
        plan = session_dir / "short.md"
        plan.write_text("# Short Plan\n\nJust a few lines.\n")
        assert detect_plan_tier(plan) == "small"

    def test_tier_session_medium(self, tmp_path: Path) -> None:
        """100 lines with 5 file references -> medium."""
        session_dir = tmp_path / "plans" / "sessions"
        session_dir.mkdir(parents=True)
        plan = session_dir / "medium.md"
        content = "# Medium Plan\n\n"
        content += (
            "Files: `src/a.py`, `src/b.py`, `src/c.py`, `src/d.py`, `src/e.py`\n\n"
        )
        content += "x\n" * 100
        plan.write_text(content)
        assert detect_plan_tier(plan) == "medium"

    def test_tier_session_large_no_research(self, tmp_path: Path) -> None:
        """350 lines, no research signals -> medium (NOT governing)."""
        session_dir = tmp_path / "plans" / "sessions"
        session_dir.mkdir(parents=True)
        plan = session_dir / "large.md"
        content = "# Large Refactor Plan\n\n"
        content += "This plan covers a large refactoring effort.\n"
        content += "x\n" * 350
        plan.write_text(content)
        assert detect_plan_tier(plan) == "medium"

    def test_tier_session_large_with_research(self, tmp_path: Path) -> None:
        """350 lines + '## Hypotheses' section -> governing."""
        session_dir = tmp_path / "plans" / "sessions"
        session_dir.mkdir(parents=True)
        plan = session_dir / "research.md"
        content = "# Research Plan\n\n"
        content += "## Hypotheses\n\n"
        content += "H1: Model capacity matters more than label quality.\n"
        content += "x\n" * 350
        plan.write_text(content)
        assert detect_plan_tier(plan) == "governing"

    def test_tier_governing_header(self, tmp_path: Path) -> None:
        """Plan with ## Governing Plan header -> governing."""
        plan = tmp_path / "test.md"
        plan.write_text("# Arc E\n\n## Governing Plan\n\nPhase 1...\n")
        assert detect_plan_tier(plan) == "governing"

    def test_tier_rung_ladder_signal(self, tmp_path: Path) -> None:
        """>300 lines + 'rung ladder' keyword -> governing."""
        plan = tmp_path / "test.md"
        content = "# Plan\n\nThe rung ladder defines progression.\n"
        content += "x\n" * 310
        plan.write_text(content)
        assert detect_plan_tier(plan) == "governing"

    def test_tier_promotion_gate_signal(self, tmp_path: Path) -> None:
        """>300 lines + 'promotion gate' keyword -> governing."""
        plan = tmp_path / "test.md"
        content = "# Plan\n\nThe promotion gate checks quality.\n"
        content += "x\n" * 310
        plan.write_text(content)
        assert detect_plan_tier(plan) == "governing"

    def test_tier_multi_pr_medium(self, tmp_path: Path) -> None:
        """Short plan with PR-1, PR-2 references -> medium."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n\nPR-1 adds adapter. PR-2 adds tests.\n")
        assert detect_plan_tier(plan) == "medium"

    def test_tier_over_80_lines_medium(self, tmp_path: Path) -> None:
        """Plan with >80 lines but no research signals -> medium."""
        plan = tmp_path / "test.md"
        content = "# Plan\n" + "x\n" * 85
        plan.write_text(content)
        assert detect_plan_tier(plan) == "medium"

    def test_tier_unreadable_file(self, tmp_path: Path) -> None:
        """Unreadable file defaults to small."""
        plan = tmp_path / "nonexistent.md"
        assert detect_plan_tier(plan) == "small"


# --- State Key Tests ---


class TestPlanStateKey:
    """Test plan_state_key for stability and uniqueness."""

    def test_state_key_different_paths(self) -> None:
        k1 = plan_state_key(Path("plans/arc_d_v2/plan.md"))
        k2 = plan_state_key(Path("plans/browser_game/plan.md"))
        assert k1 != k2

    def test_state_key_same_path_stable(self) -> None:
        p = Path("plans/sessions/2026-03-15_test.md")
        k1 = plan_state_key(p)
        k2 = plan_state_key(p)
        assert k1 == k2

    def test_state_key_same_basename_different_dirs(self) -> None:
        k1 = plan_state_key(Path("plans/arc_d_v2/amendments.md"))
        k2 = plan_state_key(Path("plans/browser_game/amendments.md"))
        assert k1 != k2

    def test_state_key_length(self) -> None:
        """Key should be exactly 12 hex chars."""
        k = plan_state_key(Path("plans/test.md"))
        assert len(k) == 12
        assert all(c in "0123456789abcdef" for c in k)


# --- Output Parsing Tests ---


class TestParsePlanFindings:
    """Test parse_plan_findings with standard Codex output."""

    def test_parse_standard_findings(self) -> None:
        output = (
            "[P1] plans/test.md:42 -- Missing seed in experiment command (P3)\n"
            "[P0] plans/test.md:10 -- Referenced path does not exist (P1)\n"
        )
        findings = parse_plan_findings(output)
        assert len(findings) == 2
        assert findings[0].severity == "WARNING"  # P1 -> WARNING
        assert findings[1].severity == "CRITICAL"  # P0 -> CRITICAL

    def test_parse_clean_review(self) -> None:
        findings = parse_plan_findings("No issues found.")
        assert findings == []

    def test_parse_empty_output(self) -> None:
        findings = parse_plan_findings("")
        assert findings == []

    def test_parsed_findings_have_source(self) -> None:
        output = "[P2] plans/test.md:5 -- Convention issue\n"
        findings = parse_plan_findings(output, source="test_source")
        assert len(findings) == 1
        assert findings[0].source == "test_source"


# --- Finding Dataclass Tests ---


class TestPlanReviewFinding:
    """Test PlanReviewFinding serialization."""

    def test_finding_to_dict_roundtrip(self) -> None:
        original = PlanReviewFinding(
            severity="WARNING",
            category="convention",
            file="plans/test.md",
            line=42,
            description="Missing seed in experiment command",
            check_id="P3",
            source="codex_cli",
        )
        d = original.to_dict()
        restored = PlanReviewFinding.from_dict(d)
        assert restored.severity == original.severity
        assert restored.category == original.category
        assert restored.file == original.file
        assert restored.line == original.line
        assert restored.description == original.description
        assert restored.check_id == original.check_id
        assert restored.source == original.source

    def test_finding_from_dict_ignores_unknown(self) -> None:
        data = {
            "severity": "INFO",
            "category": "risk",
            "file": "test.md",
            "line": 1,
            "description": "test",
            "check_id": None,
            "source": "test",
            "unknown_field": "ignored",
        }
        finding = PlanReviewFinding.from_dict(data)
        assert finding.description == "test"

    def test_finding_default_source(self) -> None:
        finding = PlanReviewFinding(
            severity="INFO",
            category="convention",
            file="test.md",
            line=1,
            description="test",
            check_id=None,
        )
        assert finding.source == "codex_cli"

    def test_finding_to_dict_all_fields(self) -> None:
        finding = PlanReviewFinding(
            severity="CRITICAL",
            category="research",
            file="plans/foo.md",
            line=99,
            description="Sample size below minimum",
            check_id="P8",
            source="claude_failsafe",
        )
        d = finding.to_dict()
        assert d["severity"] == "CRITICAL"
        assert d["category"] == "research"
        assert d["file"] == "plans/foo.md"
        assert d["line"] == 99
        assert d["description"] == "Sample size below minimum"
        assert d["check_id"] == "P8"
        assert d["source"] == "claude_failsafe"

    def test_finding_json_roundtrip(self) -> None:
        """Verify JSON serialization roundtrip."""
        original = PlanReviewFinding(
            severity="WARNING",
            category="risk",
            file="plans/test.md",
            line=10,
            description="Rollback plan missing",
            check_id="R2",
            source="codex_cli",
        )
        json_str = json.dumps(original.to_dict())
        restored = PlanReviewFinding.from_dict(json.loads(json_str))
        assert restored.severity == original.severity
        assert restored.check_id == original.check_id


# --- Auth Check Tests ---


class TestCheckCodexAuth:
    """Test _check_codex_auth for credential presence detection."""

    def test_auth_valid_chatgpt(self, tmp_path: Path) -> None:
        """ChatGPT auth with tokens returns None (valid)."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(
            json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "fake"}})
        )
        assert _check_codex_auth(auth_path=auth_file) is None

    def test_auth_valid_api_key(self, tmp_path: Path) -> None:
        """API key auth returns None (valid)."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"OPENAI_API_KEY": "sk-fake"}))
        assert _check_codex_auth(auth_path=auth_file) is None

    def test_auth_missing_file(self, tmp_path: Path) -> None:
        """Missing auth file returns error string."""
        auth_file = tmp_path / "auth.json"
        result = _check_codex_auth(auth_path=auth_file)
        assert result is not None
        assert "not found" in result

    def test_auth_empty_tokens(self, tmp_path: Path) -> None:
        """Auth file with empty tokens returns error string."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {}}))
        result = _check_codex_auth(auth_path=auth_file)
        assert result is not None
        assert "no valid credentials" in result


# --- Claude Failsafe Tests ---


class TestBuildClaudeReviewPrompt:
    """Test prompt construction for Claude CLI failsafe."""

    def test_prompt_includes_tier(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("# My Plan\n\nDo the thing.\n")
        prompt = _build_claude_review_prompt(plan, "medium")
        assert "medium-tier" in prompt

    def test_prompt_includes_plan_content(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("# My Plan\n\nStep 1: do X.\n")
        prompt = _build_claude_review_prompt(plan, "small")
        assert "Step 1: do X" in prompt

    def test_prompt_handles_unreadable_file(self) -> None:
        plan = Path("/nonexistent/path/plan.md")
        prompt = _build_claude_review_prompt(plan, "small")
        assert "could not read" in prompt

    def test_prompt_requests_json_output(self, tmp_path: Path) -> None:
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")
        prompt = _build_claude_review_prompt(plan, "small")
        assert "JSON array" in prompt


class TestClaudeFailsafeResolution:
    """Test Claude failsafe resolution order: env var -> claude CLI -> error."""

    def test_env_var_takes_priority(self, tmp_path: Path) -> None:
        """CLAUDE_REVIEW_CMD is used when set."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")

        with patch.dict(os.environ, {"CLAUDE_REVIEW_CMD": "echo"}):
            with patch("codex_plan_review_adapter.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                mock_run.return_value.stderr = ""
                result = invoke_claude_failsafe(plan, "small")
                # Should invoke the env var command, not claude CLI
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "echo"
                assert result.success is True

    @patch("codex_plan_review_adapter.shutil.which", return_value="/usr/bin/claude")
    def test_auto_detects_claude_cli(self, mock_which, tmp_path: Path) -> None:
        """When CLAUDE_REVIEW_CMD not set, auto-detects claude CLI."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")

        env = os.environ.copy()
        env.pop("CLAUDE_REVIEW_CMD", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("codex_plan_review_adapter.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                mock_run.return_value.stderr = ""
                result = invoke_claude_failsafe(plan, "small")
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "claude"
                assert "--print" in cmd
                assert "-p" in cmd
                assert result.success is True

    @patch("codex_plan_review_adapter.shutil.which", return_value=None)
    def test_returns_error_when_nothing_available(
        self, mock_which, tmp_path: Path
    ) -> None:
        """When neither env var nor claude CLI available, returns error."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")

        env = os.environ.copy()
        env.pop("CLAUDE_REVIEW_CMD", None)
        with patch.dict(os.environ, env, clear=True):
            result = invoke_claude_failsafe(plan, "small")
            assert result.success is False
            assert "not in PATH" in result.error

    @patch("codex_plan_review_adapter.shutil.which", return_value="/usr/bin/claude")
    def test_parses_json_findings(self, mock_which, tmp_path: Path) -> None:
        """Claude CLI JSON output is parsed into PlanReviewFinding objects."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")

        findings_json = json.dumps(
            [
                {
                    "severity": "WARNING",
                    "category": "convention",
                    "file": "test.md",
                    "line": 5,
                    "description": "Missing seed",
                    "check_id": None,
                }
            ]
        )

        env = os.environ.copy()
        env.pop("CLAUDE_REVIEW_CMD", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("codex_plan_review_adapter.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = findings_json
                mock_run.return_value.stderr = ""
                result = invoke_claude_failsafe(plan, "small")
                assert result.success is True
                assert len(result.findings) == 1
                assert result.findings[0].severity == "WARNING"
                assert result.findings[0].description == "Missing seed"

    @patch("codex_plan_review_adapter.shutil.which", return_value="/usr/bin/claude")
    def test_handles_empty_json_array(self, mock_which, tmp_path: Path) -> None:
        """Empty JSON array means no findings (clean review)."""
        plan = tmp_path / "test.md"
        plan.write_text("# Plan\n")

        env = os.environ.copy()
        env.pop("CLAUDE_REVIEW_CMD", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("codex_plan_review_adapter.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                mock_run.return_value.stderr = ""
                result = invoke_claude_failsafe(plan, "small")
                assert result.success is True
                assert len(result.findings) == 0
