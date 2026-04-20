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
        "#!/usr/bin/env bash\n" f'printf "%s\\n" "$@" >> "{capture_file}"\n' "exit 0\n",
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
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run the hook with a controlled PATH, env, and CLAUDE_PROJECT_DIR.

    Returns (completed_process, uv_capture_path, project_dir) so callers can
    assert on the JSONL log contents and the ops.py argv.
    """
    project_dir = project_dir or tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "bin"
    uv_capture = tmp_path / "uv_argv.log"
    _write_mock_uv(bin_dir, uv_capture)

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
