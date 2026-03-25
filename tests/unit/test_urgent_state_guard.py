"""Unit tests for the urgent-state-guard PreToolUse hook.

Tests the Python script directly for speed and isolation.
The hook reads .claude/runtime/fleet_status.json and blocks risky commands
(merge, dispatch) when unresolved HIGH/URGENT alerts exist.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PY = REPO_ROOT / ".claude" / "hooks" / "urgent-state-guard.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_hook(
    project_dir: Path,
    command: str,
    *,
    tool_name: str = "Bash",
) -> subprocess.CompletedProcess[str]:
    """Run the Python hook with simulated PreToolUse JSON on stdin."""
    hook_input = json.dumps(
        {"tool_name": tool_name, "tool_input": {"command": command}}
    )
    return subprocess.run(
        [sys.executable, str(HOOK_PY)],
        input=hook_input,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
        capture_output=True,
        text=True,
        timeout=5,
    )


def _write_fleet_status(project_dir: Path, data: dict) -> Path:
    """Write a fleet_status.json into the project dir structure."""
    runtime_dir = project_dir / ".claude" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / "fleet_status.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_item(
    *,
    severity: str = "high",
    state: str = "open",
    summary: str = "Test alert",
    recommended_action: str | None = "Fix it",
    item_id: str = "abc123",
    category: str = "lane_health",
) -> dict:
    """Create a minimal fleet status item dict."""
    item = {
        "item_id": item_id,
        "severity": severity,
        "state": state,
        "summary": summary,
        "category": category,
        "source": "monitor",
        "first_seen_at": "2026-03-24T22:00:00+00:00",
        "last_seen_at": "2026-03-24T22:00:00+00:00",
    }
    if recommended_action is not None:
        item["recommended_action"] = recommended_action
    return item


def _fleet_status(items: list[dict]) -> dict:
    """Wrap items in a fleet status envelope."""
    return {
        "items": items,
        "generated_at": "2026-03-24T22:00:00+00:00",
        "cycle_count": 1,
        "summary": {
            "total": len(items),
            "open": len([i for i in items if i.get("state") == "open"]),
        },
    }


# ---------------------------------------------------------------------------
# Tests: allow cases (exit 0)
# ---------------------------------------------------------------------------


class TestAllowCases:
    """Cases where the hook should allow the command (exit 0, no output)."""

    def test_no_fleet_status_file(self, tmp_path: Path) -> None:
        """Hook allows when fleet_status.json does not exist."""
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_items_list(self, tmp_path: Path) -> None:
        """Hook allows when items list is empty."""
        _write_fleet_status(tmp_path, _fleet_status([]))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_only_info_items(self, tmp_path: Path) -> None:
        """Hook allows when only info-severity items exist."""
        items = [_make_item(severity="info", summary="All good")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_only_warn_items(self, tmp_path: Path) -> None:
        """Hook allows when only warn-severity items exist."""
        items = [_make_item(severity="warn", summary="Minor issue")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_cleared(self, tmp_path: Path) -> None:
        """Hook allows when high items are cleared."""
        items = [_make_item(severity="high", state="cleared")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_acked(self, tmp_path: Path) -> None:
        """Hook allows when high items are acked."""
        items = [_make_item(severity="high", state="acked")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_suppressed(self, tmp_path: Path) -> None:
        """Hook allows when high items are suppressed."""
        items = [_make_item(severity="high", state="suppressed")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_guarded_command(self, tmp_path: Path) -> None:
        """Hook allows non-guarded commands even with active alerts."""
        items = [_make_item(severity="urgent", summary="Critical!")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "git status")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_guarded_git_push(self, tmp_path: Path) -> None:
        """Hook allows git push even with active alerts."""
        items = [_make_item(severity="high", summary="Something bad")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "git push -u origin feature-branch")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_corrupt_json(self, tmp_path: Path) -> None:
        """Hook allows on corrupt JSON (fail-open)."""
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "fleet_status.json").write_text("not json{{{")
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_command(self, tmp_path: Path) -> None:
        """Hook allows when command is empty."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_merge_substring_in_non_merge_command(self, tmp_path: Path) -> None:
        """Hook allows commands that mention merge but aren't gh pr merge."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "git merge main")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_dispatch_to_worker_in_grep_not_blocked(self, tmp_path: Path) -> None:
        """Hook allows grep/cat of dispatch_to_worker (not a real invocation)."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "grep -r dispatch_to_worker src/")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_dispatch_to_worker_in_cat_not_blocked(self, tmp_path: Path) -> None:
        """Hook allows reading files that contain dispatch_to_worker."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "cat src/bid_euchre/ops/worker_pool.py")
        assert result.returncode == 0
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Tests: block cases (exit 2)
# ---------------------------------------------------------------------------


class TestBlockCases:
    """Cases where the hook should block the command (exit 2)."""

    def test_blocks_merge_with_high_alert(self, tmp_path: Path) -> None:
        """Hook blocks gh pr merge when open high alert exists."""
        items = [_make_item(severity="high", summary="Lane author-a dead")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout
        assert "Lane author-a dead" in result.stdout

    def test_blocks_merge_with_urgent_alert(self, tmp_path: Path) -> None:
        """Hook blocks gh pr merge when open urgent alert exists."""
        items = [_make_item(severity="urgent", summary="CI broken on main")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout
        assert "[URGENT] CI broken on main" in result.stdout

    def test_blocks_task_dispatch_command(self, tmp_path: Path) -> None:
        """Hook blocks task dispatch when open high alert exists."""
        items = [_make_item(severity="high", summary="Stalled lane")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(
            tmp_path,
            "uv run python scripts/internal/ops.py task dispatch 6f2985cfd01b --lane author-a",
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout

    def test_blocks_workers_dispatch_command(self, tmp_path: Path) -> None:
        """Hook blocks workers dispatch when open high alert exists."""
        items = [_make_item(severity="high", summary="Stalled lane")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(
            tmp_path,
            "uv run python scripts/internal/ops.py workers dispatch 6f2985cfd01b author-a",
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout

    def test_blocks_dispatch_to_worker_call(self, tmp_path: Path) -> None:
        """Hook blocks dispatch_to_worker() function calls."""
        items = [_make_item(severity="high", summary="Stalled lane")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(
            tmp_path,
            "uv run python -c 'from bid_euchre.ops.worker_pool import dispatch_to_worker; dispatch_to_worker(...)'",
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout

    def test_blocks_merge_url_form(self, tmp_path: Path) -> None:
        """Hook blocks gh pr merge with URL argument."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(
            tmp_path,
            "gh pr merge https://github.com/Questuart/Bid-Euchre/pull/123 --squash",
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout

    def test_blocks_merge_no_args(self, tmp_path: Path) -> None:
        """Hook blocks bare gh pr merge (current branch)."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge --squash")
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout

    def test_block_message_includes_all_alerts(self, tmp_path: Path) -> None:
        """Block message shows all unresolved alerts."""
        items = [
            _make_item(
                severity="high",
                summary="PR conflict",
                item_id="id1",
            ),
            _make_item(
                severity="urgent",
                summary="Main broken",
                item_id="id2",
                recommended_action="Fix CI first",
            ),
            _make_item(severity="info", summary="Capacity OK", item_id="id3"),
        ]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2
        assert "2 unresolved fleet alert(s)" in result.stdout
        assert "[HIGH] PR conflict" in result.stdout
        assert "[URGENT] Main broken" in result.stdout
        assert "Fix CI first" in result.stdout
        assert "Capacity OK" not in result.stdout  # info excluded

    def test_block_message_includes_remediation(self, tmp_path: Path) -> None:
        """Block message shows the real fleet --ack command."""
        items = [_make_item(severity="high", summary="Alert")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2
        assert "fleet --ack" in result.stdout


# ---------------------------------------------------------------------------
# Tests: resolve-then-retry lifecycle
# ---------------------------------------------------------------------------


class TestResolveRetryLifecycle:
    """Verify the block → resolve → allow lifecycle."""

    def test_resolve_by_clearing(self, tmp_path: Path) -> None:
        """After clearing alerts, the hook allows."""
        # Step 1: Seed urgent alert — should block
        items = [_make_item(severity="urgent", summary="CI broken")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2

        # Step 2: Clear the alert — should allow
        items[0]["state"] = "cleared"
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_resolve_by_acking(self, tmp_path: Path) -> None:
        """After acking alerts, the hook allows."""
        items = [_make_item(severity="high", summary="Lane stalled")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2

        # Ack the alert
        items[0]["state"] = "acked"
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0

    def test_resolve_by_removing(self, tmp_path: Path) -> None:
        """After removing the fleet_status.json, the hook allows."""
        items = [_make_item(severity="high", summary="Alert")]
        status_path = _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 2

        # Remove the file
        status_path.unlink()
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Tests: hook infrastructure
# ---------------------------------------------------------------------------


class TestHookInfrastructure:
    """Verify hook file exists and is properly configured."""

    def test_python_script_exists(self) -> None:
        assert HOOK_PY.exists(), f"Missing {HOOK_PY}"

    def test_python_script_executable(self) -> None:
        mode = os.stat(HOOK_PY).st_mode
        assert mode & stat.S_IXUSR, f"{HOOK_PY} is not executable"

    def test_registered_in_dispatcher(self) -> None:
        """Verify the guard is called from pre-bash-dispatch.sh."""
        dispatcher = REPO_ROOT / ".claude" / "hooks" / "pre-bash-dispatch.sh"
        content = dispatcher.read_text()
        assert "urgent-state-guard.py" in content

    def test_hook_speed(self, tmp_path: Path) -> None:
        """Hook completes in under 2 seconds even with many alerts."""
        items = [
            _make_item(severity="high", summary=f"Alert {i}", item_id=f"id{i}")
            for i in range(20)
        ]
        _write_fleet_status(tmp_path, _fleet_status(items))

        start = time.monotonic()
        result = _run_hook(tmp_path, "gh pr merge 123 --squash")
        elapsed = time.monotonic() - start

        assert result.returncode == 2
        assert elapsed < 2.0, f"Hook took {elapsed:.2f}s (must be < 2s)"
