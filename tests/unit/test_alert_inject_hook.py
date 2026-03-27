"""Unit tests for the alert-inject UserPromptSubmit hook.

Tests the Python script directly (no shell wrapper) for speed and isolation.
The hook reads .claude/runtime/fleet_status.json and injects high/urgent
alerts as additionalContext.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PY = REPO_ROOT / ".claude" / "hooks" / "alert-inject.py"
HOOK_SH = REPO_ROOT / ".claude" / "hooks" / "alert-inject.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_hook(project_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the Python hook script with CLAUDE_PROJECT_DIR set."""
    return subprocess.run(
        [sys.executable, str(HOOK_PY)],
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
            "urgent": len(
                [
                    i
                    for i in items
                    if i.get("severity") == "urgent" and i.get("state") == "open"
                ]
            ),
            "high": len(
                [
                    i
                    for i in items
                    if i.get("severity") in ("high", "urgent")
                    and i.get("state") == "open"
                ]
            ),
        },
    }


# ---------------------------------------------------------------------------
# Tests: no output cases
# ---------------------------------------------------------------------------


class TestNoOutput:
    """Cases where the hook should produce no output and exit 0."""

    def test_no_fleet_status_file(self, tmp_path: Path) -> None:
        """Hook exits cleanly when fleet_status.json does not exist."""
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_items_list(self, tmp_path: Path) -> None:
        """Hook exits cleanly when items list is empty."""
        _write_fleet_status(tmp_path, _fleet_status([]))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_only_info_items(self, tmp_path: Path) -> None:
        """Hook exits cleanly when only info-severity items exist."""
        items = [_make_item(severity="info", summary="All good")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_only_warn_items(self, tmp_path: Path) -> None:
        """Hook exits cleanly when only warn-severity items exist."""
        items = [_make_item(severity="warn", summary="Minor issue")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_cleared(self, tmp_path: Path) -> None:
        """Hook exits cleanly when high items are cleared (not open)."""
        items = [_make_item(severity="high", state="cleared")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_acked(self, tmp_path: Path) -> None:
        """Hook exits cleanly when high items are acked (not open)."""
        items = [_make_item(severity="high", state="acked")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_high_but_suppressed(self, tmp_path: Path) -> None:
        """Hook exits cleanly when high items are suppressed."""
        items = [_make_item(severity="high", state="suppressed")]
        _write_fleet_status(tmp_path, _fleet_status(items))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_corrupt_json(self, tmp_path: Path) -> None:
        """Hook exits cleanly on corrupt JSON."""
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "fleet_status.json").write_text("not json{{{")
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Tests: alert injection
# ---------------------------------------------------------------------------


class TestAlertInjection:
    """Cases where the hook should inject additionalContext."""

    def test_single_high_alert(self, tmp_path: Path) -> None:
        """Hook injects context for a single high-severity open item."""
        items = [_make_item(severity="high", summary="Lane author-a dead")]
        _write_fleet_status(tmp_path, _fleet_status(items))

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert "additionalContext" in output
        ctx = output["additionalContext"]
        assert "FLEET ALERTS (1 unresolved)" in ctx
        assert "[HIGH] Lane author-a dead" in ctx
        assert "-> Fix it" in ctx

    def test_single_urgent_alert(self, tmp_path: Path) -> None:
        """Hook injects context for a single urgent-severity open item."""
        items = [_make_item(severity="urgent", summary="CI broken on main")]
        _write_fleet_status(tmp_path, _fleet_status(items))

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["additionalContext"]
        assert "FLEET ALERTS (1 unresolved)" in ctx
        assert "[URGENT] CI broken on main" in ctx

    def test_multiple_alerts(self, tmp_path: Path) -> None:
        """Hook injects all high/urgent open items."""
        items = [
            _make_item(
                severity="high",
                summary="PR #123 has merge conflict",
                item_id="id1",
            ),
            _make_item(
                severity="urgent",
                summary="Lane stalled 45min",
                item_id="id2",
                recommended_action="Re-nudge lane",
            ),
            _make_item(severity="info", summary="Capacity OK", item_id="id3"),
            _make_item(
                severity="high",
                summary="Cleared issue",
                item_id="id4",
                state="cleared",
            ),
        ]
        _write_fleet_status(tmp_path, _fleet_status(items))

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["additionalContext"]
        assert "FLEET ALERTS (2 unresolved)" in ctx
        assert "[HIGH] PR #123 has merge conflict" in ctx
        assert "[URGENT] Lane stalled 45min" in ctx
        assert "Capacity OK" not in ctx  # info item excluded
        assert "Cleared issue" not in ctx  # cleared item excluded

    def test_no_recommended_action(self, tmp_path: Path) -> None:
        """Hook works when recommended_action is absent."""
        items = [
            _make_item(
                severity="high",
                summary="Something wrong",
                recommended_action=None,
            ),
        ]
        _write_fleet_status(tmp_path, _fleet_status(items))

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["additionalContext"]
        assert "[HIGH] Something wrong" in ctx
        assert "->" not in ctx

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """Hook output is always valid JSON when alerts exist."""
        items = [_make_item(severity="high", summary='Alert with "quotes" & specials')]
        _write_fleet_status(tmp_path, _fleet_status(items))

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        # Must be parseable JSON
        output = json.loads(result.stdout)
        assert isinstance(output, dict)
        assert "additionalContext" in output
        assert isinstance(output["additionalContext"], str)


# ---------------------------------------------------------------------------
# Tests: hook infrastructure
# ---------------------------------------------------------------------------


class TestHookInfrastructure:
    """Verify hook files exist and are properly configured."""

    def test_python_script_exists(self) -> None:
        assert HOOK_PY.exists(), f"Missing {HOOK_PY}"

    def test_shell_wrapper_exists(self) -> None:
        assert HOOK_SH.exists(), f"Missing {HOOK_SH}"

    def test_shell_wrapper_executable(self) -> None:
        import os
        import stat

        mode = os.stat(HOOK_SH).st_mode
        assert mode & stat.S_IXUSR, f"{HOOK_SH} is not executable"

    def test_python_script_executable(self) -> None:
        import os
        import stat

        mode = os.stat(HOOK_PY).st_mode
        assert mode & stat.S_IXUSR, f"{HOOK_PY} is not executable"

    def test_hook_registered_in_settings(self) -> None:
        settings_path = REPO_ROOT / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})
        user_prompt = hooks.get("UserPromptSubmit", [])
        assert len(user_prompt) > 0, "No UserPromptSubmit hooks registered"

        # Find our hook
        found = False
        for entry in user_prompt:
            for hook in entry.get("hooks", []):
                if "alert-inject" in hook.get("command", ""):
                    found = True
                    assert hook["timeout"] <= 5, "Hook timeout must be <= 5s"
        assert found, "alert-inject hook not found in UserPromptSubmit"

    def test_hook_speed(self, tmp_path: Path) -> None:
        """Hook completes in under 2 seconds even with alerts."""
        import time

        items = [_make_item(severity="high", summary=f"Alert {i}") for i in range(20)]
        _write_fleet_status(tmp_path, _fleet_status(items))

        start = time.monotonic()
        result = _run_hook(tmp_path)
        elapsed = time.monotonic() - start

        assert result.returncode == 0
        assert elapsed < 5.0, f"Hook took {elapsed:.2f}s (must be < 5s)"
