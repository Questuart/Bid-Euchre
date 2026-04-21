"""Unit tests for scripts/internal/hooks/permission_denied_alert.sh.

The hook fires on PermissionDenied events emitted by the Sonnet 4.6 auto-mode
classifier (Claude Code v2.1.89+). It converts a classifier denial into:
  - an ops-lane escalation message (via ops.py message send)
  - a JSONL audit record under .claude/runtime/classifier_denials/YYYY-MM-DD.jsonl

Tests cover:
  - Happy path (fixture → escalation invoked, JSONL record with expected schema).
  - Empty stdin (exit 0, no crash).
  - Malformed JSON stdin (exit 0, no crash).
  - Message truncation for oversized payloads.
  - Lane fallback when env vars are unset.

The ops.py invocation is mocked by prepending a directory with a stub `uv`
shim to PATH. The stub records the argv it received so we can assert the
expected flags (--from, --to ops, --type escalation, --summary).
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_SH = REPO_ROOT / "scripts" / "internal" / "hooks" / "permission_denied_alert.sh"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "classifier_denial_sample.json"
RESOLVE_LANE_LIB = REPO_ROOT / ".claude" / "hooks" / "lib" / "resolve-lane-id.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_mock_uv(bin_dir: Path, capture_file: Path) -> Path:
    """Write a mock `uv` executable to bin_dir that records argv to capture_file.

    The hook invokes: `uv run python scripts/internal/ops.py message send ...`.
    The mock records the full argv then exits 0, which simulates a successful
    ops.py call without actually sending a message.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "uv"
    shim.write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" >> "{capture_file}"\nexit 0\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


def _write_failing_construct_jq(bin_dir: Path) -> Path:
    """Shim `jq` that forces the hand-rolled fallback path.

    The hook invokes jq twice:
      1. To parse stdin fields (`jq -r '.tool_name // ...'`).
      2. To build the final JSON record (`jq -nc --arg ...`).

    This shim passes (1) through to the real jq but fails (2) by exiting
    non-zero whenever `-nc` is present in argv. That forces RECORD="" inside
    the hook, which activates the `_esc`-based hand-rolled fallback that
    this test suite is exercising.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "jq"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = "-nc" ]; then\n'
        "    exit 1\n"
        "  fi\n"
        "done\n"
        "# Fall through to the real jq on the system PATH (without bin_dir).\n"
        'PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin" exec jq "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


def _run_hook(
    tmp_path: Path,
    *,
    stdin_payload: str,
    lane_env: str | None = "author-b",
    project_dir: Path | None = None,
    force_fallback: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run the hook with a controlled PATH, env, and CLAUDE_PROJECT_DIR.

    Returns (completed_process, uv_capture_path, project_dir) so callers can
    assert on the JSONL log contents and the ops.py argv.

    When ``force_fallback`` is True, installs a jq shim that breaks only the
    JSON-construction call (`jq -nc ...`) so the hook's hand-rolled ``_esc``
    fallback runs. This is how the control-char escape tests exercise the
    fallback path that #2691 targets.
    """
    project_dir = project_dir or tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    # Stage the canonical lane-id resolver library under the tmp project
    # dir so the hook can source it the same way it does in production
    # (#2690 — resolver previously lived inline in each hook).
    lib_dst = project_dir / ".claude" / "hooks" / "lib" / "resolve-lane-id.sh"
    lib_dst.parent.mkdir(parents=True, exist_ok=True)
    lib_dst.write_text(RESOLVE_LANE_LIB.read_text(encoding="utf-8"), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    uv_capture = tmp_path / "uv_argv.log"
    _write_mock_uv(bin_dir, uv_capture)
    if force_fallback:
        _write_failing_construct_jq(bin_dir)

    # Keep the minimal PATH the hook needs (jq, sed, date, bash builtins, the
    # mock uv). Use /usr/bin + /bin for coreutils and prepend bin_dir so the
    # stub is picked up instead of any real uv on the system.
    env: dict[str, str] = {
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    if lane_env is not None:
        env["CLAUDE_AGENT_NAME"] = f"steward-{lane_env}"

    result = subprocess.run(
        ["bash", str(HOOK_SH)],
        input=stdin_payload,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result, uv_capture, project_dir


def _read_denial_record(project_dir: Path) -> dict:
    """Find today's JSONL file and return the first record as a dict."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = project_dir / ".claude" / "runtime" / "classifier_denials" / f"{today}.jsonl"
    assert log.exists(), f"expected JSONL log at {log}"
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, f"JSONL log at {log} was empty"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Fixture input produces escalation + JSONL record."""

    def test_hook_exits_zero_with_fixture(self, tmp_path: Path) -> None:
        payload = FIXTURE.read_text(encoding="utf-8")
        result, _, _ = _run_hook(tmp_path, stdin_payload=payload)
        assert result.returncode == 0, result.stderr

    def test_jsonl_record_has_expected_fields(self, tmp_path: Path) -> None:
        payload = FIXTURE.read_text(encoding="utf-8")
        _, _, project_dir = _run_hook(tmp_path, stdin_payload=payload)
        record = _read_denial_record(project_dir)
        # Schema contract — treat changes as breaking (see hook docstring).
        assert set(record.keys()) == {"ts", "lane", "tool", "rule", "message"}
        assert record["tool"] == "Bash"
        assert record["rule"] == "Self-Modification"
        assert "settings.json" in record["message"]
        assert record["lane"] == "author-b"
        # ts should be ISO-8601 UTC
        assert record["ts"].endswith("Z")

    def test_ops_message_send_invoked(self, tmp_path: Path) -> None:
        payload = FIXTURE.read_text(encoding="utf-8")
        _, uv_capture, _ = _run_hook(tmp_path, stdin_payload=payload)
        assert uv_capture.exists(), "mock uv was not invoked"
        argv = uv_capture.read_text(encoding="utf-8").splitlines()
        # Expect: run python scripts/internal/ops.py message send --from <lane>
        #         --to ops --type escalation --summary ... --priority high --no-nudge
        assert argv[:2] == ["run", "python"], argv
        assert "scripts/internal/ops.py" in argv[2]
        assert "message" in argv
        assert "send" in argv
        assert "--from" in argv
        assert argv[argv.index("--from") + 1] == "author-b"
        assert "--to" in argv
        assert argv[argv.index("--to") + 1] == "ops"
        assert "--type" in argv
        assert argv[argv.index("--type") + 1] == "escalation"
        # Summary must name the tool and the rule
        summary = argv[argv.index("--summary") + 1]
        assert "Bash" in summary
        assert "Self-Modification" in summary


# ---------------------------------------------------------------------------
# Defensive input handling
# ---------------------------------------------------------------------------


class TestDefensiveStdin:
    """Hook must exit 0 regardless of stdin shape — never block the lane."""

    def test_empty_stdin_exits_zero(self, tmp_path: Path) -> None:
        result, _, project_dir = _run_hook(tmp_path, stdin_payload="")
        assert result.returncode == 0, result.stderr
        # A record is still written with tool="unknown" / rule="unknown"
        record = _read_denial_record(project_dir)
        assert record["tool"] == "unknown"
        assert record["rule"] == "unknown"

    def test_malformed_json_exits_zero(self, tmp_path: Path) -> None:
        result, _, project_dir = _run_hook(tmp_path, stdin_payload="not json")
        assert result.returncode == 0, result.stderr
        record = _read_denial_record(project_dir)
        assert record["tool"] == "unknown"
        assert record["rule"] == "unknown"

    def test_partial_json_missing_keys_exits_zero(self, tmp_path: Path) -> None:
        result, _, project_dir = _run_hook(
            tmp_path, stdin_payload=json.dumps({"tool_name": "Edit"})
        )
        assert result.returncode == 0, result.stderr
        record = _read_denial_record(project_dir)
        assert record["tool"] == "Edit"
        assert record["rule"] == "unknown"


# ---------------------------------------------------------------------------
# Message truncation
# ---------------------------------------------------------------------------


class TestMessageTruncation:
    """Oversized message fields are truncated to keep JSONL + ops args small."""

    def test_long_message_is_truncated(self, tmp_path: Path) -> None:
        long_msg = "A" * 500
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "rule_matched": "TestRule",
                "message": long_msg,
            }
        )
        _, _, project_dir = _run_hook(tmp_path, stdin_payload=payload)
        record = _read_denial_record(project_dir)
        assert len(record["message"]) < len(long_msg), record["message"]
        assert record["message"].endswith("...")


# ---------------------------------------------------------------------------
# Lane derivation
# ---------------------------------------------------------------------------


class TestLaneDerivation:
    """Lane id falls back gracefully when env vars are missing."""

    def test_lane_from_project_dir_when_agent_name_unset(self, tmp_path: Path) -> None:
        # Simulate the author-b worktree layout
        project_dir = tmp_path / "Bid-Euchre-steward-author-b"
        project_dir.mkdir()
        result, _, _ = _run_hook(
            tmp_path,
            stdin_payload=FIXTURE.read_text(encoding="utf-8"),
            lane_env=None,
            project_dir=project_dir,
        )
        assert result.returncode == 0
        record = _read_denial_record(project_dir)
        assert record["lane"] == "author-b"

    def test_lane_falls_back_to_nonempty_string(self, tmp_path: Path) -> None:
        # Unknown project dir shape + no CLAUDE_AGENT_NAME → hostname fallback
        project_dir = tmp_path / "unrecognized-layout"
        project_dir.mkdir()
        result, _, _ = _run_hook(
            tmp_path,
            stdin_payload=FIXTURE.read_text(encoding="utf-8"),
            lane_env=None,
            project_dir=project_dir,
        )
        assert result.returncode == 0
        record = _read_denial_record(project_dir)
        # Must never be empty (would break ops.py --from validation)
        assert record["lane"], record


# ---------------------------------------------------------------------------
# Hand-rolled fallback JSON escaping (#2691)
# ---------------------------------------------------------------------------


class TestFallbackControlCharEscape:
    """When jq is unavailable for record construction, the hand-rolled
    fallback must still emit valid JSON even if the classifier message
    contains control characters (newlines, tabs, CR, other C0 controls).

    Regression for #2691: pre-fix, the fallback only escaped ``\\`` and ``"``,
    so a single multi-line classifier message would corrupt every subsequent
    line in the JSONL file, silently breaking jq-based tooling.
    """

    def test_fallback_with_embedded_newline_produces_valid_jsonl(
        self, tmp_path: Path
    ) -> None:
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "rule_matched": "MultilineRule",
                "message": "first line\nsecond line\nthird line",
            }
        )
        result, _, project_dir = _run_hook(
            tmp_path, stdin_payload=payload, force_fallback=True
        )
        assert result.returncode == 0, result.stderr
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = (
            project_dir
            / ".claude"
            / "runtime"
            / "classifier_denials"
            / f"{today}.jsonl"
        )
        raw = log.read_text(encoding="utf-8")
        # Each non-empty line in the JSONL file must parse on its own — if
        # the newline in "message" leaked through, the second line would be
        # an orphan fragment and json.loads would fail.
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        assert (
            len(lines) == 1
        ), f"expected exactly one JSONL line, got {len(lines)}: {raw!r}"
        record = json.loads(lines[0])
        assert record["message"] == "first line\nsecond line\nthird line"
        assert record["rule"] == "MultilineRule"

    def test_fallback_escapes_tab_and_carriage_return(self, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "rule_matched": "WhitespaceRule",
                "message": "col1\tcol2\rwrap",
            }
        )
        result, _, project_dir = _run_hook(
            tmp_path, stdin_payload=payload, force_fallback=True
        )
        assert result.returncode == 0, result.stderr
        record = _read_denial_record(project_dir)
        # After json.loads, the original bytes should be restored exactly.
        assert record["message"] == "col1\tcol2\rwrap"

    def test_fallback_escapes_c0_controls_as_unicode(self, tmp_path: Path) -> None:
        # U+0001 and U+001F — arbitrary C0 control chars that should be
        # emitted as \u0001 / \u001f, not passed through raw.
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "rule_matched": "CtrlRule",
                "message": "before\u0001mid\u001fafter",
            }
        )
        result, _, project_dir = _run_hook(
            tmp_path, stdin_payload=payload, force_fallback=True
        )
        assert result.returncode == 0, result.stderr
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = (
            project_dir
            / ".claude"
            / "runtime"
            / "classifier_denials"
            / f"{today}.jsonl"
        )
        raw_line = log.read_text(encoding="utf-8").strip()
        # The raw file content must contain escaped unicode, not the raw bytes
        assert "\\u0001" in raw_line, raw_line
        assert "\\u001f" in raw_line, raw_line
        # And the record must still round-trip through json.loads
        record = json.loads(raw_line)
        assert record["message"] == "before\u0001mid\u001fafter"

    def test_fallback_preserves_existing_backslash_and_quote_escapes(
        self, tmp_path: Path
    ) -> None:
        # Regression guard: the extended _esc must not break the two original
        # escape cases (`\` and `"`).
        payload = json.dumps(
            {
                "tool_name": "Write",
                "rule_matched": "QuoteRule",
                "message": 'path="C:\\temp" says "hello"',
            }
        )
        result, _, project_dir = _run_hook(
            tmp_path, stdin_payload=payload, force_fallback=True
        )
        assert result.returncode == 0, result.stderr
        record = _read_denial_record(project_dir)
        assert record["message"] == 'path="C:\\temp" says "hello"'

    def test_fallback_is_actually_taken(self, tmp_path: Path) -> None:
        # Sanity check that the shim forces the fallback branch. We can't
        # directly assert which branch ran, but the construct-jq shim exits
        # non-zero on `-nc`, which forces RECORD="" and activates _esc. If
        # the jq-shim ever stopped working, every other test in this class
        # would silently start covering only the jq-happy-path.
        import subprocess as sp

        bin_dir = tmp_path / "bin"
        _write_failing_construct_jq(bin_dir)
        # The shim must exit 1 for -nc
        r = sp.run(
            [str(bin_dir / "jq"), "-nc", "."], capture_output=True, text=True, timeout=5
        )
        assert r.returncode != 0, "shim should fail on -nc"
        # The shim must pass through non-construct calls
        r2 = sp.run(
            [str(bin_dir / "jq"), "-r", '.foo // "x"'],
            input='{"foo":"bar"}',
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r2.returncode == 0 and r2.stdout.strip() == "bar", r2


# ---------------------------------------------------------------------------
# Executable bit (smoke)
# ---------------------------------------------------------------------------


def test_hook_script_is_executable() -> None:
    assert HOOK_SH.exists(), HOOK_SH
    mode = HOOK_SH.stat().st_mode
    assert mode & stat.S_IXUSR, f"hook script not executable: {oct(mode)}"


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Fixture shape sanity — skipped in CI to avoid duplicate coverage",
)
def test_fixture_is_valid_json() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Required fields per the packet's declared schema
    assert "tool_name" in data
    assert "rule_matched" in data
    assert "message" in data
