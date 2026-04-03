"""Tests for the steward session bootstrap script (.claude/tmux/steward-session.sh).

Covers update_last_active(), detached-mode support, and launchd recovery
infrastructure without requiring tmux to be running.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STEWARD_SCRIPT = REPO_ROOT / ".claude" / "tmux" / "steward-session.sh"
INSTALL_SCRIPT = REPO_ROOT / ".claude" / "launchd" / "install-launchd.sh"
PLIST_TEMPLATE = REPO_ROOT / ".claude" / "launchd" / "ensure-steward-session.plist"

STEWARD_SESSION = Path(".claude/tmux/steward-session.sh")


def _read_steward_script() -> str:
    """Read steward-session.sh, preferring the git-committed version in CI.

    In CI, the ``setup-uv`` cache restoration can overwrite ``.git/HEAD``,
    causing the working-tree copy of the script to revert to the base branch.
    When ``GITHUB_SHA`` is set (GitHub Actions), we read from the merge-commit
    blob to get the correct PR content. Locally we just read the file.
    """
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        try:
            return subprocess.check_output(
                [
                    "git",
                    "show",
                    f"{github_sha}:.claude/tmux/steward-session.sh",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            pass  # fall through to filesystem read
    return STEWARD_SCRIPT.read_text()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry_dir(tmp_path: Path) -> Path:
    """Create a temp registry dir with a sample JSON file."""
    reg = tmp_path / "worktree_registry"
    reg.mkdir()

    old_ts = "2026-01-01T00:00:00Z"
    entry = {
        "schema_version": 1,
        "role": "author",
        "worktree_path": "/tmp/fake-wt",
        "branch": "role/author",
        "class": "persistent",
        "created_at": old_ts,
        "last_active": old_ts,
        "session_id": None,
        "ttl_hours": None,
    }
    (reg / "author.json").write_text(json.dumps(entry, indent=2) + "\n")
    return reg


# ---------------------------------------------------------------------------
# update_last_active() tests (from main)
# ---------------------------------------------------------------------------


class TestUpdateLastActive:
    """Tests for the update_last_active() function in steward-session.sh."""

    def test_updates_last_active_timestamp(
        self, tmp_path: Path, registry_dir: Path
    ) -> None:
        """update_last_active() updates the last_active field in registry JSON."""
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "worktree_registry").symlink_to(registry_dir)

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
MAIN_DIR="{tmp_path}"
update_last_active() {{
    local registry_dir="$MAIN_DIR/.claude/runtime/worktree_registry"
    [ -d "$registry_dir" ] || return 0
    local now
    now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    for f in "$registry_dir"/*.json; do
        [ -f "$f" ] || continue
        python3 -c "
import json, sys
try:
    with open('$f') as fh:
        d = json.load(fh)
    d['last_active'] = '$now'
    with open('$f', 'w') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\\n')
except Exception:
    pass
" 2>/dev/null || true
    done
}}
update_last_active
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        # Verify the file was updated
        updated = json.loads((registry_dir / "author.json").read_text())
        assert updated["last_active"] != "2026-01-01T00:00:00Z"
        assert updated["created_at"] == "2026-01-01T00:00:00Z"  # preserved
        assert updated["schema_version"] == 1  # preserved

    def test_no_registry_dir_is_noop(self, tmp_path: Path) -> None:
        """update_last_active() is a no-op when registry dir doesn't exist."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
MAIN_DIR="{tmp_path}"
update_last_active() {{
    local registry_dir="$MAIN_DIR/.claude/runtime/worktree_registry"
    [ -d "$registry_dir" ] || return 0
    echo "SHOULD NOT REACH HERE"
}}
update_last_active
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "SHOULD NOT REACH HERE" not in result.stdout

    def test_uses_argv_not_shell_interpolation(self) -> None:
        """Inline Python must use sys.argv, not shell interpolation (#860)."""
        content = STEWARD_SCRIPT.read_text()
        # Find the update_last_active function body
        in_func = False
        func_lines: list[str] = []
        for line in content.split("\n"):
            if "update_last_active()" in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                if line.strip() == "}" and in_func:
                    break
        func_body = "\n".join(func_lines)
        assert "sys.argv[1]" in func_body, "Must pass file path via sys.argv[1]"
        assert "sys.argv[2]" in func_body, "Must pass timestamp via sys.argv[2]"

    def test_preserves_all_fields(self, tmp_path: Path, registry_dir: Path) -> None:
        """update_last_active() preserves all fields except last_active."""
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "worktree_registry").symlink_to(registry_dir)

        original = json.loads((registry_dir / "author.json").read_text())

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
MAIN_DIR="{tmp_path}"
update_last_active() {{
    local registry_dir="$MAIN_DIR/.claude/runtime/worktree_registry"
    [ -d "$registry_dir" ] || return 0
    local now
    now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    for f in "$registry_dir"/*.json; do
        [ -f "$f" ] || continue
        python3 -c "
import json, sys
try:
    with open('$f') as fh:
        d = json.load(fh)
    d['last_active'] = '$now'
    with open('$f', 'w') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\\n')
except Exception:
    pass
" 2>/dev/null || true
    done
}}
update_last_active
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        updated = json.loads((registry_dir / "author.json").read_text())
        for key in original:
            if key == "last_active":
                continue
            assert updated[key] == original[key], f"{key} changed unexpectedly"


# ---------------------------------------------------------------------------
# Steward session script structure tests
# ---------------------------------------------------------------------------


class TestStewardSessionScript:
    """Validate steward-session.sh structure and syntax."""

    def test_script_exists(self) -> None:
        assert STEWARD_SCRIPT.exists(), f"Missing: {STEWARD_SCRIPT}"

    def test_script_is_executable(self) -> None:
        assert STEWARD_SCRIPT.stat().st_mode & 0o111, "Script must be executable"

    def test_bash_syntax_valid(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(STEWARD_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_detached_mode_supported(self) -> None:
        """The script must support STEWARD_DETACHED=1 for non-interactive use."""
        content = STEWARD_SCRIPT.read_text()
        assert "STEWARD_DETACHED" in content, (
            "steward-session.sh must support STEWARD_DETACHED env var "
            "for launchd and other non-interactive contexts"
        )

    def test_detached_mode_skips_attach(self) -> None:
        """When STEWARD_DETACHED=1, script should not exec tmux attach."""
        content = STEWARD_SCRIPT.read_text()
        # Find the detached mode blocks — they should exit 0 instead of attaching
        lines = content.split("\n")
        in_detached_block = False
        detached_exits_found = 0
        for line in lines:
            stripped = line.strip()
            if "STEWARD_DETACHED" in stripped and "1" in stripped:
                in_detached_block = True
            if in_detached_block and "exit 0" in stripped:
                detached_exits_found += 1
                in_detached_block = False
        assert detached_exits_found >= 2, (
            f"Expected at least 2 detached-mode exit points (existing session + "
            f"new session), found {detached_exits_found}"
        )

    def test_writes_lane_metadata(self) -> None:
        """Script must write worktree registry metadata for each lane."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "write_lane_metadata" in content
        ), "steward-session.sh must call write_lane_metadata for lane registry"

    def test_has_boundary_validation(self) -> None:
        """Script must contain validate_worktree_path() for boundary enforcement."""
        content = STEWARD_SCRIPT.read_text()
        assert "validate_worktree_path" in content, (
            "steward-session.sh must define validate_worktree_path() for "
            "filesystem boundary enforcement"
        )

    def test_ensure_worktree_calls_boundary_check(self) -> None:
        """ensure_worktree() must call validate_worktree_path before creating."""
        content = STEWARD_SCRIPT.read_text()
        # Find ensure_worktree body and verify it calls validate_worktree_path
        in_func = False
        func_lines: list[str] = []
        for line in content.split("\n"):
            if "ensure_worktree()" in line and "validate" not in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                if line.strip() == "}" and in_func:
                    break
        func_body = "\n".join(func_lines)
        assert (
            "validate_worktree_path" in func_body
        ), "ensure_worktree() must call validate_worktree_path before creating"


class TestWindowLayout:
    """Validate the 5-window layout."""

    EXPECTED_WINDOWS = ["central-ops", "analyst", "platform", "browser", "flex"]

    # Windows that use 4 tiled panes
    TILED_4_WINDOWS = ["analyst", "platform", "browser"]

    EXPECTED_LANES = [
        # Central ops (3 panes)
        "orchestrator",
        "ops",
        "review",
        # Analyst pool (4 panes)
        "analyst-a",
        "analyst-b",
        "analyst-c",
        "analyst-d",
        # Platform workers
        "author-a",
        "author-b",
        "author-c",
        "author-d",
        # Browser-game workers
        "brws-author-a",
        "brws-author-b",
        "brws-author-c",
        "brws-author-d",
        # Flex pool
        "flex-a",
        "flex-b",
        "flex-c",
        "flex-d",
    ]

    # Lanes per window, in pane creation order (pane 1 = first, 1-based)
    WINDOW_PANES = {
        "central-ops": ["orchestrator", "ops", "review"],
        "analyst": ["analyst-a", "analyst-b", "analyst-c", "analyst-d"],
        "platform": ["author-a", "author-b", "author-c", "author-d"],
        "browser": [
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
        ],
        "flex": ["flex-a", "flex-b", "flex-c", "flex-d"],
    }

    def test_no_dashboard_window(self) -> None:
        """The script must not create a dashboard window."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "dashboard" not in content.lower()
        ), "steward-session.sh must not reference a 'dashboard' window"

    def test_no_issues_lane(self) -> None:
        """The issues lane must not appear in the launcher."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "--name issues" not in content
        ), "issues lane must be removed from the launcher"
        # Metadata should not include issues
        metadata_lines = [
            line
            for line in content.split("\n")
            if line.strip().startswith('write_lane_metadata "issues"')
        ]
        assert len(metadata_lines) == 0, "issues metadata must be removed"
        # No stale "issues" references in pane-index comments
        assert (
            "issues=" not in content
        ), "stale 'issues=' reference in pane-index comment"

    def test_no_scratch_window(self) -> None:
        """The scratch window must not exist (retired in analyst pool restructure)."""
        content = STEWARD_SCRIPT.read_text()
        # No scratch window creation
        assert "-n scratch" not in content, "scratch window must be retired"

    def test_no_author_scratch_lane(self) -> None:
        """The author-scratch lane must not be launched (retired)."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "--name author-scratch" not in content
        ), "author-scratch lane must not be launched"
        # No metadata entry for author-scratch
        metadata_lines = [
            line
            for line in content.split("\n")
            if line.strip().startswith('write_lane_metadata "author-scratch"')
        ]
        assert len(metadata_lines) == 0, "author-scratch metadata must be removed"

    def test_five_windows_created(self) -> None:
        """Exactly 5 tmux windows must be created (1 new-session + 4 new-window)."""
        content = STEWARD_SCRIPT.read_text()
        lines = content.split("\n")
        window_cmds = [
            line
            for line in lines
            if line.strip().startswith("tmux")
            and ("new-session" in line or "new-window" in line)
        ]
        assert (
            len(window_cmds) == 5
        ), f"Expected 5 window creation commands, found {len(window_cmds)}"
        for window_name in self.EXPECTED_WINDOWS:
            assert (
                f"-n {window_name}" in content
            ), f"Expected window named '{window_name}'"

    def test_central_ops_has_3_panes(self) -> None:
        """central-ops must have 2 split-window commands (for 3 panes total)."""
        content = STEWARD_SCRIPT.read_text()
        split_count = content.count('split-window -t "${SESSION}:central-ops"')
        assert (
            split_count == 2
        ), f"central-ops must have 2 split-window commands, found {split_count}"

    def test_central_ops_main_vertical(self) -> None:
        """central-ops must use main-vertical layout (orchestrator gets big left pane)."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'select-layout -t "${SESSION}:central-ops" main-vertical' in content
        ), "central-ops must use main-vertical layout"

    def test_analyst_window_has_4_panes(self) -> None:
        """analyst window must have 3 split-window commands (for 4 panes total)."""
        content = STEWARD_SCRIPT.read_text()
        split_count = content.count('split-window -t "${SESSION}:analyst"')
        assert (
            split_count == 3
        ), f"analyst window must have 3 split-window commands, found {split_count}"

    def test_analyst_window_tiled(self) -> None:
        """analyst window must use tiled layout."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'select-layout -t "${SESSION}:analyst" tiled' in content
        ), "analyst window must use tiled layout"

    def test_analyst_lanes_use_analyst_agent(self) -> None:
        """All analyst lanes must use the steward-analyst agent definition."""
        content = STEWARD_SCRIPT.read_text()
        for lane in ["analyst-a", "analyst-b", "analyst-c", "analyst-d"]:
            assert (
                f"--name {lane}" in content
            ), f"Analyst lane '{lane}' must be launched"
            # Each analyst lane launch line should reference steward-analyst agent
            lines = content.split("\n")
            for line in lines:
                if f"--name {lane}" in line:
                    assert (
                        "--agent steward-analyst" in line
                    ), f"Analyst lane '{lane}' must use --agent steward-analyst"

    def test_worker_windows_have_4_panes(self) -> None:
        """Each 4-pane worker window must have 3 split-window commands."""
        content = STEWARD_SCRIPT.read_text()
        for window_name in self.TILED_4_WINDOWS:
            split_count = content.count(f'split-window -t "${{SESSION}}:{window_name}"')
            assert split_count == 3, (
                f"Window '{window_name}' must have 3 split-window commands, "
                f"found {split_count}"
            )

    def test_worker_windows_tiled(self) -> None:
        """4-pane worker windows must use tiled layout."""
        content = STEWARD_SCRIPT.read_text()
        for window_name in self.TILED_4_WINDOWS:
            assert (
                f'select-layout -t "${{SESSION}}:{window_name}" tiled' in content
            ), f"Window '{window_name}' must have select-layout tiled"

    def test_flex_window_has_4_panes(self) -> None:
        """flex window must have 3 split-window commands (for 4 panes total)."""
        content = STEWARD_SCRIPT.read_text()
        split_count = content.count('split-window -t "${SESSION}:flex"')
        assert (
            split_count == 3
        ), f"flex window must have 3 split-window commands, found {split_count}"

    def test_flex_window_tiled(self) -> None:
        """flex window must use tiled layout."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'select-layout -t "${SESSION}:flex" tiled' in content
        ), "flex window must use tiled layout"

    def test_all_lanes_launched(self) -> None:
        """All 20 lanes must appear in new-session, new-window, or split-window."""
        content = STEWARD_SCRIPT.read_text()
        for lane in self.EXPECTED_LANES:
            assert (
                f"--name {lane}" in content
            ), f"Lane '{lane}' must be launched via --name argument"

    @staticmethod
    def _metadata_invocation_lines() -> list[str]:
        """Return write_lane_metadata invocation lines (not the function def)."""
        content = STEWARD_SCRIPT.read_text()
        return [
            line
            for line in content.split("\n")
            if line.strip().startswith('write_lane_metadata "')
        ]

    def test_metadata_count(self) -> None:
        """Must have exactly one metadata entry per lane."""
        metadata_lines = self._metadata_invocation_lines()
        assert len(metadata_lines) == len(self.EXPECTED_LANES), (
            f"Expected {len(self.EXPECTED_LANES)} write_lane_metadata calls, "
            f"found {len(metadata_lines)}"
        )

    def test_metadata_pane_indices(self) -> None:
        """All lanes must have valid pane indices in their metadata.

        Pane indices are 1-based to match tmux pane-base-index=1.
        3-pane windows use indices 1-3; 4-pane windows use 1-4.
        """
        metadata_lines = self._metadata_invocation_lines()
        for line in metadata_lines:
            has_pane_idx = any(f'"{i}"' in line for i in range(1, 5))
            assert (
                has_pane_idx
            ), f"Lane metadata must have a 1-based pane index: {line.strip()}"

    def test_metadata_window_names(self) -> None:
        """All metadata must reference one of the 5 window names."""
        metadata_lines = self._metadata_invocation_lines()
        for line in metadata_lines:
            has_window = any(f'"{w}"' in line for w in self.EXPECTED_WINDOWS)
            assert (
                has_window
            ), f"Lane metadata must reference a window name: {line.strip()}"

    def test_central_ops_foreground(self) -> None:
        """Central ops lanes must have foreground visibility."""
        metadata_lines = self._metadata_invocation_lines()
        central_ops_lanes = {"orchestrator", "ops", "review"}
        for line in metadata_lines:
            for lane in central_ops_lanes:
                if f'"{lane}"' in line and line.index(f'"{lane}"') < 30:
                    assert (
                        '"foreground"' in line
                    ), f"Central ops lane must be foreground: {line.strip()}"

    def test_worker_lanes_background(self) -> None:
        """Worker and analyst lanes must have background visibility."""
        metadata_lines = self._metadata_invocation_lines()
        worker_lanes = {
            "analyst-a",
            "analyst-b",
            "analyst-c",
            "analyst-d",
            "author-a",
            "author-b",
            "author-c",
            "author-d",
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
            "flex-a",
            "flex-b",
            "flex-c",
        }
        for line in metadata_lines:
            for lane in worker_lanes:
                if f'"{lane}"' in line and line.index(f'"{lane}"') < 30:
                    assert (
                        '"background"' in line
                    ), f"Worker lane must be background: {line.strip()}"

    def test_ops_monitoring_targets_correct_pane(self) -> None:
        """The ops monitoring loop must target central-ops.2 (ops pane).

        With pane-base-index=1: orchestrator=.1, ops=.2, review=.3.
        """
        content = STEWARD_SCRIPT.read_text()
        assert "central-ops.2" in content, "Ops monitoring must target central-ops.2"

    def test_review_loop_targets_correct_pane(self) -> None:
        """The merged-PR review loop must target central-ops.3 (review pane).

        With pane-base-index=1: orchestrator=.1, ops=.2, review=.3.
        """
        content = STEWARD_SCRIPT.read_text()
        assert "central-ops.3" in content, "Review loop must target central-ops.3"

    def test_review_pane_sends_natural_language_prompt(self) -> None:
        """The review pane auto-launch must send a natural-language prompt,
        not the old review-check CLI command."""
        content = STEWARD_SCRIPT.read_text()
        assert "review-check" not in content, (
            "Old review-check CLI command must be replaced with "
            "natural-language prompt for the review agent"
        )
        assert "Review recently merged PRs" in content, (
            "Review pane must receive a natural-language prompt "
            "to trigger the agent's startup behavior"
        )

    def test_ops_lane_has_own_worktree(self) -> None:
        """Ops lane must launch in its own detached worktree, not $MAIN_DIR.

        When ops runs in the same directory as the orchestrator, competing
        bun MCP server instances race on Telegram getUpdates, silently
        consuming inbound messages. See #1615.
        """
        content = STEWARD_SCRIPT.read_text()
        # OPS variable must be defined in the control plane section
        assert 'OPS="' in content, "OPS worktree variable must be defined"
        assert "steward-ops" in content, "OPS path must reference steward-ops"

        # The ops tmux pane must launch in $OPS, not $MAIN_DIR
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "--name ops" in line or "--agent steward-ops" in line:
                # Check this line and the preceding line for the working dir
                context = "\n".join(lines[max(0, i - 1) : i + 1])
                assert (
                    '"$OPS"' in context
                ), f"Ops pane must launch in $OPS, not $MAIN_DIR: {context}"
                break

    def test_ops_metadata_uses_detached_branch(self) -> None:
        """Ops lane metadata must specify 'detached' branch, not '--'."""
        content = STEWARD_SCRIPT.read_text()
        metadata_lines = [
            line
            for line in content.split("\n")
            if line.strip().startswith('write_lane_metadata "ops"')
        ]
        assert len(metadata_lines) == 1, "Expected exactly one ops metadata line"
        line = metadata_lines[0]
        assert '"$OPS"' in line, f"Ops metadata must use $OPS path: {line.strip()}"
        assert (
            '"detached"' in line
        ), f"Ops metadata must use 'detached' branch: {line.strip()}"

    def test_ensure_detached_worktree_used_for_control_plane(self) -> None:
        """Review and ops worktrees must use ensure_detached_worktree."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'ensure_detached_worktree "$REVIEW"' in content
        ), "Review worktree must use ensure_detached_worktree"
        assert (
            'ensure_detached_worktree "$OPS"' in content
        ), "Ops worktree must use ensure_detached_worktree"

    def test_ensure_detached_worktree_used_for_analysts(self) -> None:
        """All analyst worktrees must use ensure_detached_worktree."""
        content = STEWARD_SCRIPT.read_text()
        for var in ["$ANALYST_A", "$ANALYST_B", "$ANALYST_C", "$ANALYST_D"]:
            assert (
                f'ensure_detached_worktree "{var}"' in content
            ), f"Analyst worktree {var} must use ensure_detached_worktree"

    def test_browser_game_worktree_paths(self) -> None:
        """Script must define BRWS_A through BRWS_D worktree paths."""
        content = STEWARD_SCRIPT.read_text()
        for var in ["BRWS_A", "BRWS_B", "BRWS_C", "BRWS_D"]:
            assert var in content, f"Missing worktree path variable: {var}"

    def test_flex_worktree_paths(self) -> None:
        """Script must define FLEX_A through FLEX_C worktree paths."""
        content = STEWARD_SCRIPT.read_text()
        for var in ["FLEX_A", "FLEX_B", "FLEX_C"]:
            assert var in content, f"Missing worktree path variable: {var}"

    def test_analyst_worktree_paths(self) -> None:
        """Script must define ANALYST_A through ANALYST_D worktree paths."""
        content = STEWARD_SCRIPT.read_text()
        for var in ["ANALYST_A", "ANALYST_B", "ANALYST_C", "ANALYST_D"]:
            assert f'{var}="' in content, f"Missing worktree path variable: {var}"


class TestTelegramChannelConfig:
    """Tests for the Telegram channel configuration (Platform-8a)."""

    def test_telegram_autodetect_with_fallback_to_zero(self) -> None:
        """STEWARD_TELEGRAM_ENABLED must auto-detect from plugins, defaulting to 0."""
        content = STEWARD_SCRIPT.read_text()
        # Must check whether the env var is already set (explicit override)
        assert (
            "${STEWARD_TELEGRAM_ENABLED+x}" in content
        ), "Must check for explicit STEWARD_TELEGRAM_ENABLED override"
        # Must auto-detect by running 'plugins list'
        assert (
            "plugins list" in content
        ), "Must auto-detect Telegram plugin via 'plugins list'"
        # Must fall back to 0 when plugin is not enabled
        assert (
            'STEWARD_TELEGRAM_ENABLED="0"' in content
        ), "Must default STEWARD_TELEGRAM_ENABLED to 0 when plugin not enabled"

    def test_channels_flag_only_on_orchestrator(self) -> None:
        """--channels must only appear on the orchestrator pane launch, via ORCH_CHANNEL_FLAGS."""
        content = STEWARD_SCRIPT.read_text()
        # The orchestrator launch line must reference ORCH_CHANNEL_FLAGS
        assert (
            "--agent steward-orchestrator $ORCH_CHANNEL_FLAGS" in content
        ), "Orchestrator pane must append $ORCH_CHANNEL_FLAGS"

        # No other launch line should reference ORCH_CHANNEL_FLAGS or --channels
        launch_lines = [
            line.strip()
            for line in content.split("\n")
            if ("--name " in line or "--agent " in line) and "$CLAUDE_BIN" in line
        ]
        for line in launch_lines:
            if "steward-orchestrator" in line:
                continue
            assert (
                "ORCH_CHANNEL_FLAGS" not in line
            ), f"Non-orchestrator lane must not use ORCH_CHANNEL_FLAGS: {line}"
            assert (
                "--channels" not in line
            ), f"Non-orchestrator lane must not use --channels: {line}"

    def test_steward_channels_propagated_via_tmux(self) -> None:
        """STEWARD_CHANNELS must be propagated via tmux set-environment, not shell export."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "tmux set-environment" in content and "STEWARD_CHANNELS" in content
        ), "STEWARD_CHANNELS must be propagated via tmux set-environment"
        assert (
            "export STEWARD_CHANNELS" not in content
        ), "STEWARD_CHANNELS must not use shell export (tmux panes don't inherit it)"

    def test_channel_flags_empty_by_default(self) -> None:
        """ORCH_CHANNEL_FLAGS must be empty string by default."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'ORCH_CHANNEL_FLAGS=""' in content
        ), "ORCH_CHANNEL_FLAGS must default to empty string"

    def test_settings_json_does_not_enable_telegram_plugin(self) -> None:
        """Committed settings.json must NOT contain enabledPlugins (#1824).

        If enabledPlugins were in the committed settings.json, every lane
        would spawn its own Telegram plugin instance, competing for inbound
        messages.  Only the orchestrator should have the plugin enabled, via
        a per-worktree settings.local.json provisioned by the tmux script.
        """
        settings_path = REPO_ROOT / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        assert "enabledPlugins" not in settings, (
            "Committed .claude/settings.json must not contain enabledPlugins — "
            "the Telegram plugin must be enabled per-worktree via settings.local.json"
        )

    def test_settings_local_json_is_gitignored(self) -> None:
        """settings.local.json must be in .gitignore (#1824)."""
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        assert ".claude/settings.local.json" in gitignore, (
            ".claude/settings.local.json must be gitignored so that "
            "per-worktree plugin overrides are not committed"
        )

    def test_tmux_script_provisions_settings_local_for_orchestrator(self) -> None:
        """Tmux script must create settings.local.json in orchestrator worktree only (#1824)."""
        content = STEWARD_SCRIPT.read_text()
        # Must reference settings.local.json
        assert (
            "settings.local.json" in content
        ), "Tmux script must provision .claude/settings.local.json for orchestrator"
        # Must only create in MAIN_DIR (orchestrator worktree)
        assert (
            "MAIN_DIR" in content and "settings.local.json" in content
        ), "settings.local.json must be created in MAIN_DIR (orchestrator worktree)"
        # Must include enabledPlugins with telegram
        assert (
            "telegram@claude-plugins-official" in content
        ), "settings.local.json must enable the Telegram plugin"

    def test_channel_flags_conditional_on_enabled(self) -> None:
        """ORCH_CHANNEL_FLAGS must only be set inside the STEWARD_TELEGRAM_ENABLED=1 guard."""
        content = STEWARD_SCRIPT.read_text()
        lines = content.split("\n")
        in_guard = False
        guard_body: list[str] = []
        for line in lines:
            if "STEWARD_TELEGRAM_ENABLED" in line and '"1"' in line and "if" in line:
                in_guard = True
            if in_guard:
                guard_body.append(line)
                if line.strip() == "fi":
                    break
        guard_text = "\n".join(guard_body)
        assert (
            'ORCH_CHANNEL_FLAGS="--channels plugin:telegram@claude-plugins-official"'
            in guard_text
        ), "ORCH_CHANNEL_FLAGS assignment must be inside the STEWARD_TELEGRAM_ENABLED=1 guard"


class TestTelegramSingleReceiver:
    """Tests for single-receiver enforcement (#1824).

    Bug 1: Idempotency guard must use jq merge, not file-exists check.
    Bug 2: Non-orchestrator worktrees must get empty enabledPlugins.
    Bug 3: STEWARD_TELEGRAM_RECEIVER env var must be set for orchestrator.
    """

    def test_no_file_exists_guard_for_settings_local(self) -> None:
        """Bug 1: The old `if [ ! -f ]` guard must be replaced with jq merge."""
        content = STEWARD_SCRIPT.read_text()
        # The old pattern: `if [ ! -f "$_orch_settings_local" ]`
        assert (
            '! -f "$_orch_settings_local"' not in content
        ), "Old file-exists guard must be replaced with jq merge (#1824 Bug 1)"

    def test_merge_settings_local_function_exists(self) -> None:
        """A merge_settings_local() helper must exist for idempotent jq merge."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "merge_settings_local()" in content
        ), "merge_settings_local() function must be defined"
        # Must use jq for merging
        assert "jq" in content, "merge_settings_local must use jq for JSON merging"

    def test_orchestrator_settings_uses_merge(self) -> None:
        """Orchestrator settings.local.json must be provisioned via merge_settings_local."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'merge_settings_local "${MAIN_DIR}/.claude/settings.local.json"' in content
        ), "Orchestrator settings must use merge_settings_local, not cat"

    def test_non_orchestrator_worktrees_get_empty_plugins(self) -> None:
        """Bug 2: Every non-orchestrator worktree must get empty enabledPlugins."""
        content = STEWARD_SCRIPT.read_text()
        # Must iterate over all worktree variables
        for var in [
            "$AUTHOR_A",
            "$AUTHOR_B",
            "$AUTHOR_C",
            "$AUTHOR_D",
            "$BRWS_A",
            "$BRWS_B",
            "$BRWS_C",
            "$BRWS_D",
            "$ANALYST_A",
            "$ANALYST_B",
            "$ANALYST_C",
            "$ANALYST_D",
            "$FLEX_A",
            "$FLEX_B",
            "$FLEX_C",
            "$FLEX_D",
            "$REVIEW",
            "$OPS",
        ]:
            assert (
                f'"{var}"' in content
            ), f"Non-orchestrator worktree {var} must be covered by plugin disablement"
        # Must explicitly disable the Telegram plugin
        assert (
            '"telegram@claude-plugins-official":false' in content
            or '"telegram@claude-plugins-official": false' in content
        ), "Non-orchestrator worktrees must explicitly disable the Telegram plugin"

    def test_negative_enforcement_inside_enabled_guard(self) -> None:
        """Bug 2: Plugin disablement loop must be inside STEWARD_TELEGRAM_ENABLED=1 guard."""
        content = STEWARD_SCRIPT.read_text()
        lines = content.split("\n")
        in_guard = False
        guard_body: list[str] = []
        for line in lines:
            if "STEWARD_TELEGRAM_ENABLED" in line and '"1"' in line and "if" in line:
                in_guard = True
            if in_guard:
                guard_body.append(line)
                if line.strip() == "fi":
                    break
        guard_text = "\n".join(guard_body)
        assert (
            '"telegram@claude-plugins-official":false' in guard_text
            or '"telegram@claude-plugins-official": false' in guard_text
        ), "Non-orchestrator plugin disablement must be inside the TELEGRAM_ENABLED=1 guard"

    def test_telegram_receiver_env_set(self) -> None:
        """Bug 3: STEWARD_TELEGRAM_RECEIVER must be propagated via tmux set-environment."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            "STEWARD_TELEGRAM_RECEIVER" in content
        ), "STEWARD_TELEGRAM_RECEIVER must be set in the tmux script"
        assert (
            "tmux set-environment" in content and "STEWARD_TELEGRAM_RECEIVER" in content
        ), "STEWARD_TELEGRAM_RECEIVER must be propagated via tmux set-environment"

    def test_telegram_receiver_only_when_enabled(self) -> None:
        """Bug 3: STEWARD_TELEGRAM_RECEIVER must only be set when Telegram is enabled."""
        content = STEWARD_SCRIPT.read_text()
        # Find the STEWARD_TELEGRAM_RECEIVER set-environment line
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "STEWARD_TELEGRAM_RECEIVER" in line and "set-environment" in line:
                # Look backwards for the guarding if statement
                context = "\n".join(lines[max(0, i - 5) : i + 1])
                assert (
                    "STEWARD_TELEGRAM_ENABLED" in context
                ), "STEWARD_TELEGRAM_RECEIVER must be guarded by STEWARD_TELEGRAM_ENABLED check"
                break
        else:
            pytest.fail("Could not find tmux set-environment STEWARD_TELEGRAM_RECEIVER")

    def test_merge_settings_local_functional(self, tmp_path: Path) -> None:
        """Functional test: merge_settings_local creates and merges correctly."""
        # Test 1: Create from scratch
        target = tmp_path / ".claude" / "settings.local.json"
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
merge_settings_local() {{
    local file_path="$1"
    local fragment="$2"
    local dir
    dir="$(dirname "$file_path")"
    mkdir -p "$dir"
    if [ -f "$file_path" ]; then
        local merged
        merged="$(jq --argjson frag "$fragment" '. + $frag' "$file_path")"
        printf '%s\\n' "$merged" > "$file_path"
    else
        printf '%s\\n' "$fragment" | jq '.' > "$file_path"
    fi
}}
merge_settings_local "{target}" '{{"enabledPlugins":{{"telegram@claude-plugins-official":true}}}}'
cat "{target}"
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(target.read_text())
        assert data["enabledPlugins"]["telegram@claude-plugins-official"] is True

        # Test 2: Merge into existing (should preserve existing keys)
        target.write_text(json.dumps({"someOtherKey": 42}) + "\n")
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
merge_settings_local() {{
    local file_path="$1"
    local fragment="$2"
    local dir
    dir="$(dirname "$file_path")"
    mkdir -p "$dir"
    if [ -f "$file_path" ]; then
        local merged
        merged="$(jq --argjson frag "$fragment" '. + $frag' "$file_path")"
        printf '%s\\n' "$merged" > "$file_path"
    else
        printf '%s\\n' "$fragment" | jq '.' > "$file_path"
    fi
}}
merge_settings_local "{target}" '{{"enabledPlugins":{{"telegram@claude-plugins-official":true}}}}'
cat "{target}"
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(target.read_text())
        assert data["enabledPlugins"]["telegram@claude-plugins-official"] is True
        assert data["someOtherKey"] == 42, "Existing keys must be preserved"

    def test_merge_settings_local_explicit_disable(self, tmp_path: Path) -> None:
        """Functional test: explicit false overrides existing plugin enable via deep merge."""
        target = tmp_path / ".claude" / "settings.local.json"
        # Pre-populate with a plugin enabled
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"enabledPlugins": {"telegram@claude-plugins-official": True}})
            + "\n"
        )
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
merge_settings_local() {{
    local file_path="$1"
    local fragment="$2"
    local dir
    dir="$(dirname "$file_path")"
    mkdir -p "$dir"
    if [ -f "$file_path" ]; then
        local merged
        merged="$(jq --argjson frag "$fragment" '. * $frag' "$file_path")"
        printf '%s\\n' "$merged" > "$file_path"
    else
        printf '%s\\n' "$fragment" | jq '.' > "$file_path"
    fi
}}
merge_settings_local "{target}" '{{"enabledPlugins":{{"telegram@claude-plugins-official":false}}}}'
cat "{target}"
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(target.read_text())
        assert (
            data["enabledPlugins"]["telegram@claude-plugins-official"] is False
        ), "Explicit false must override existing plugin enable"


class TestAutoCompactWindow:
    """Tests for CLAUDE_CODE_AUTO_COMPACT_WINDOW in steward-session.sh (#2169)."""

    def test_auto_compact_window_set_via_tmux_env(self) -> None:
        """CLAUDE_CODE_AUTO_COMPACT_WINDOW must be propagated via tmux set-environment."""
        content = _read_steward_script()
        assert (
            'tmux set-environment -t "$SESSION" CLAUDE_CODE_AUTO_COMPACT_WINDOW'
            in content
        ), "CLAUDE_CODE_AUTO_COMPACT_WINDOW must be set via tmux set-environment"

    def test_auto_compact_window_value_is_200k(self) -> None:
        """Auto-compact window must be set to 200000 tokens."""
        content = _read_steward_script()
        assert (
            'CLAUDE_CODE_AUTO_COMPACT_WINDOW "200000"' in content
        ), "CLAUDE_CODE_AUTO_COMPACT_WINDOW must be set to 200000"

    def test_auto_compact_set_after_orchestrator_pane(self) -> None:
        """Auto-compact env var must be set AFTER orchestrator pane creation.

        The orchestrator should retain unlimited context. The env var is set
        via tmux set-environment after the orchestrator pane is created, so
        only panes spawned after that point inherit the limit.
        """
        content = _read_steward_script()
        orch_pos = content.find("--agent steward-orchestrator")
        compact_pos = content.find("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
        assert orch_pos > 0, "Orchestrator pane launch must exist"
        assert compact_pos > 0, "CLAUDE_CODE_AUTO_COMPACT_WINDOW must exist"
        assert compact_pos > orch_pos, (
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW must appear AFTER orchestrator "
            "pane creation so the orchestrator retains unlimited context"
        )

    def test_auto_compact_set_before_non_orch_panes(self) -> None:
        """Auto-compact env var must be set BEFORE non-orchestrator panes are created."""
        content = _read_steward_script()
        compact_pos = content.find("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
        # ops is the first non-orchestrator pane (split-window after orchestrator)
        ops_pos = content.find("--name ops")
        assert compact_pos > 0, "CLAUDE_CODE_AUTO_COMPACT_WINDOW must exist"
        assert ops_pos > 0, "Ops pane launch must exist"
        assert compact_pos < ops_pos, (
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW must appear BEFORE the first "
            "non-orchestrator pane (ops) so all non-orch lanes inherit it"
        )

    def test_auto_compact_not_shell_export(self) -> None:
        """Must use tmux set-environment, not shell export (panes don't inherit it)."""
        content = _read_steward_script()
        assert "export CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in content, (
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW must not use shell export "
            "(tmux panes don't inherit it)"
        )


class TestFleetEnvFlags:
    """Tests for fleet environment flags in steward-session.sh (#2255)."""

    # The six fleet flags and their expected values.
    FLEET_FLAGS = {
        "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
        "DISABLE_COST_WARNINGS": "1",
        "CLAUDE_CODE_RESUME_INTERRUPTED_TURN": "1",
        "MCP_CONNECTION_NONBLOCKING": "true",
    }

    @pytest.mark.parametrize("flag,value", FLEET_FLAGS.items())
    def test_flag_set_via_tmux_env(self, flag: str, value: str) -> None:
        """Each fleet flag must be propagated via tmux set-environment."""
        content = _read_steward_script()
        expected = f'tmux set-environment -t "$SESSION" {flag} "{value}"'
        assert (
            expected in content
        ), f"{flag} must be set via tmux set-environment with value {value!r}"

    @pytest.mark.parametrize("flag", FLEET_FLAGS)
    def test_flag_set_after_orchestrator_pane(self, flag: str) -> None:
        """Fleet flags must appear AFTER the orchestrator pane is created."""
        content = _read_steward_script()
        orch_pos = content.find("--agent steward-orchestrator")
        flag_pos = content.find(flag)
        assert orch_pos > 0, "Orchestrator pane launch must exist"
        assert flag_pos > 0, f"{flag} must exist in the script"
        assert (
            flag_pos > orch_pos
        ), f"{flag} must appear AFTER orchestrator pane creation"

    @pytest.mark.parametrize("flag", FLEET_FLAGS)
    def test_flag_set_before_non_orch_panes(self, flag: str) -> None:
        """Fleet flags must appear BEFORE the first non-orchestrator pane (ops)."""
        content = _read_steward_script()
        flag_pos = content.find(flag)
        ops_pos = content.find("--name ops")
        assert flag_pos > 0, f"{flag} must exist in the script"
        assert ops_pos > 0, "Ops pane launch must exist"
        assert (
            flag_pos < ops_pos
        ), f"{flag} must appear BEFORE the first non-orch pane (ops)"

    @pytest.mark.parametrize("flag", FLEET_FLAGS)
    def test_flag_not_shell_export(self, flag: str) -> None:
        """Must use tmux set-environment, not shell export."""
        content = _read_steward_script()
        assert (
            f"export {flag}" not in content
        ), f"{flag} must not use shell export (tmux panes don't inherit it)"


class TestBoundaryValidation:
    """Tests for validate_worktree_path() in steward-session.sh."""

    def test_accepts_path_in_parent_dir(self, tmp_path: Path) -> None:
        """Paths within PARENT_DIR should be accepted."""
        parent = tmp_path / "parent"
        parent.mkdir()
        wt_path = parent / "worktree"
        wt_path.mkdir()

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
PARENT_DIR="{parent}"
validate_worktree_path() {{
    local path="$1"
    local resolved
    if [ -e "$path" ]; then
        resolved="$(cd "$path" && pwd -P)"
    else
        local par
        par="$(dirname "$path")"
        if [ ! -d "$par" ]; then
            echo "Error: parent directory does not exist: $par" >&2
            return 1
        fi
        resolved="$(cd "$par" && pwd -P)/$(basename "$path")"
    fi
    local parent_resolved
    parent_resolved="$(cd "$PARENT_DIR" && pwd -P)"
    case "$resolved" in
        "${{parent_resolved}}"/*)
            return 0
            ;;
        *)
            echo "Error: worktree path is outside the repo boundary: $resolved" >&2
            return 1
            ;;
    esac
}}
validate_worktree_path "{wt_path}"
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_rejects_path_outside_parent_dir(self, tmp_path: Path) -> None:
        """Paths outside PARENT_DIR should be rejected."""
        parent = tmp_path / "parent"
        parent.mkdir()
        external = tmp_path / "external"
        external.mkdir()

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
PARENT_DIR="{parent}"
validate_worktree_path() {{
    local path="$1"
    local resolved
    if [ -e "$path" ]; then
        resolved="$(cd "$path" && pwd -P)"
    else
        local par
        par="$(dirname "$path")"
        if [ ! -d "$par" ]; then
            echo "Error: parent directory does not exist: $par" >&2
            return 1
        fi
        resolved="$(cd "$par" && pwd -P)/$(basename "$path")"
    fi
    local parent_resolved
    parent_resolved="$(cd "$PARENT_DIR" && pwd -P)"
    case "$resolved" in
        "${{parent_resolved}}"/*)
            return 0
            ;;
        *)
            echo "Error: worktree path is outside the repo boundary: $resolved" >&2
            return 1
            ;;
    esac
}}
validate_worktree_path "{external}"
""",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "outside the repo boundary" in result.stderr


# ---------------------------------------------------------------------------
# launchd template tests
# ---------------------------------------------------------------------------


class TestLaunchdTemplate:
    """Validate the launchd plist template."""

    def test_plist_exists(self) -> None:
        assert PLIST_TEMPLATE.exists(), f"Missing: {PLIST_TEMPLATE}"

    @pytest.mark.skipif(
        shutil.which("plutil") is None,
        reason="plutil is macOS-only; not available on Linux CI",
    )
    def test_plist_valid_xml(self) -> None:
        result = subprocess.run(
            ["plutil", "-lint", str(PLIST_TEMPLATE)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Invalid plist: {result.stderr}"

    def test_plist_contains_placeholder(self) -> None:
        content = PLIST_TEMPLATE.read_text()
        assert (
            "__REPO_PATH__" in content
        ), "Plist template must contain __REPO_PATH__ placeholder"

    def test_plist_references_steward_session(self) -> None:
        content = PLIST_TEMPLATE.read_text()
        assert (
            "steward-session.sh" in content
        ), "Plist must reference steward-session.sh"

    def test_plist_uses_detached_mode(self) -> None:
        content = PLIST_TEMPLATE.read_text()
        assert (
            "STEWARD_DETACHED=1" in content
        ), "Plist must use STEWARD_DETACHED=1 for non-interactive context"

    def test_plist_has_throttle_interval(self) -> None:
        content = PLIST_TEMPLATE.read_text()
        assert (
            "ThrottleInterval" in content
        ), "Plist must set ThrottleInterval to prevent rapid restarts"

    def test_plist_has_claude_bin_placeholder(self) -> None:
        """Plist template must include __CLAUDE_BIN__ for install-time resolution."""
        content = PLIST_TEMPLATE.read_text()
        assert (
            "__CLAUDE_BIN__" in content
        ), "Plist must contain __CLAUDE_BIN__ placeholder resolved at install time"

    def test_plist_has_launchd_path_placeholder(self) -> None:
        """Plist PATH must be resolved at install time, not hardcoded."""
        content = PLIST_TEMPLATE.read_text()
        assert (
            "__LAUNCHD_PATH__" in content
        ), "Plist must contain __LAUNCHD_PATH__ placeholder resolved at install time"


# ---------------------------------------------------------------------------
# Install script tests
# ---------------------------------------------------------------------------


class TestInstallScript:
    """Validate the launchd install helper."""

    def test_install_script_exists(self) -> None:
        assert INSTALL_SCRIPT.exists(), f"Missing: {INSTALL_SCRIPT}"

    def test_install_script_is_executable(self) -> None:
        assert INSTALL_SCRIPT.stat().st_mode & 0o111, "Script must be executable"

    def test_install_script_syntax_valid(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_install_script_supports_dry_run(self) -> None:
        content = INSTALL_SCRIPT.read_text()
        assert "--dry-run" in content, "Install script must support --dry-run"

    def test_install_script_supports_uninstall(self) -> None:
        content = INSTALL_SCRIPT.read_text()
        assert "--uninstall" in content, "Install script must support --uninstall"

    def test_install_script_resolves_claude_bin(self) -> None:
        """Installer must resolve claude binary path at install time."""
        content = INSTALL_SCRIPT.read_text()
        assert (
            "command -v claude" in content
        ), "Installer must resolve claude path via command -v at install time"
        assert (
            "__CLAUDE_BIN__" in content
        ), "Installer must substitute __CLAUDE_BIN__ placeholder"

    def test_install_script_resolves_path(self) -> None:
        """Installer must capture current shell PATH for launchd."""
        content = INSTALL_SCRIPT.read_text()
        assert (
            "__LAUNCHD_PATH__" in content
        ), "Installer must substitute __LAUNCHD_PATH__ placeholder"
        assert (
            "LAUNCHD_PATH" in content
        ), "Installer must build LAUNCHD_PATH from current shell environment"

    @pytest.mark.skipif(
        subprocess.run(["uname"], capture_output=True, text=True).stdout.strip()
        != "Darwin",
        reason="macOS-only test",
    )
    def test_dry_run_succeeds(self) -> None:
        """Dry run should succeed without side effects."""
        result = subprocess.run(
            [str(INSTALL_SCRIPT), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        assert "Would install to" in result.stdout, "Dry run should show target path"

    @pytest.mark.skipif(
        subprocess.run(["uname"], capture_output=True, text=True).stdout.strip()
        != "Darwin",
        reason="macOS-only test",
    )
    def test_dry_run_shows_claude_bin(self) -> None:
        """Dry run must show the resolved claude binary path."""
        result = subprocess.run(
            [str(INSTALL_SCRIPT), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        assert (
            "Claude bin:" in result.stdout
        ), "Dry run should display the resolved claude binary path"
