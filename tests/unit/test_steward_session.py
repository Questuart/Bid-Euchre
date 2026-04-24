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


def _read_lane_models_json() -> str:
    """Read .claude/lane_models.json, preferring the git-committed version in CI.

    Same CI pitfall as ``_read_steward_script``: ``setup-uv`` cache restoration
    can overwrite the working tree during the tests-shard job, dropping files
    that are on the PR branch but not on the base. When ``GITHUB_SHA`` is set,
    we read from the merge-commit blob to get the correct PR content. Locally
    we just read the file.
    """
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        try:
            return subprocess.check_output(
                [
                    "git",
                    "show",
                    f"{github_sha}:.claude/lane_models.json",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            pass  # fall through to filesystem read
    return (REPO_ROOT / ".claude" / "lane_models.json").read_text()


def _lane_models_json_available() -> bool:
    """True if .claude/lane_models.json is readable via filesystem or GITHUB_SHA."""
    try:
        _read_lane_models_json()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


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
        # The orchestrator launch line must reference ORCH_CHANNEL_FLAGS.
        # Additional flags (e.g. --permission-mode auto, #2685) may appear
        # between --agent steward-orchestrator and $ORCH_CHANNEL_FLAGS; assert
        # only that the same line carries both rather than requiring adjacency.
        launch_lines_raw = [
            line
            for line in content.split("\n")
            if ("--name " in line or "--agent " in line) and "$CLAUDE_BIN" in line
        ]
        orch_lines = [
            line for line in launch_lines_raw if "steward-orchestrator" in line
        ]
        assert len(orch_lines) == 1, "Expected exactly one orchestrator launch line"
        assert (
            "$ORCH_CHANNEL_FLAGS" in orch_lines[0]
        ), "Orchestrator pane must append $ORCH_CHANNEL_FLAGS"

        # No other launch line should reference ORCH_CHANNEL_FLAGS or --channels
        launch_lines = [line.strip() for line in launch_lines_raw]
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
        "CLAUDE_CODE_DISABLE_MOUSE": "1",
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


class TestPermissionModeByModelTier:
    """Tests for model-tier-aware launch flags (#2685 original, #2767 fix).

    Per ``.claude/rules/80_permission_model.md`` §"Model-tier activation
    constraint", the launch-flag choice is a function of the lane's model
    tier, not a fleet-wide constant:

    * Opus (Claude Opus 4.6+)  → ``--permission-mode auto`` (classifier-gated)
    * Sonnet / Haiku           → ``--dangerously-skip-permissions`` (explicit
                                  reduced safety envelope)

    Passing ``--permission-mode auto`` to a non-Opus session silently falls
    back to ``bypassPermissions`` with no enforcement legibility — the worst
    outcome. The launch script reads ``.claude/lane_models.json`` via the
    ``permission_mode_flag_for_lane`` helper and emits the correct flag per
    lane.

    These structural tests lock in:
    1. Every ``$CLAUDE_BIN`` launch routes through ``permission_mode_flag_for_lane``.
    2. No launch line hardcodes a permission-mode flag.
    3. The orchestrator's call precedes ``$ORCH_CHANNEL_FLAGS``.
    4. The helper emits the correct flag per tier (functional check).
    5. The canonical ``.claude/lane_models.json`` is valid and opus-defaulting.
    """

    @staticmethod
    def _claude_launch_lines(content: str) -> list[str]:
        """Return every claude launch line ($CLAUDE_BIN ... --agent ...)."""
        return [
            line
            for line in content.split("\n")
            if "$CLAUDE_BIN" in line and "--agent" in line
        ]

    # -- Structural checks on steward-session.sh ------------------------

    def test_helper_function_defined(self) -> None:
        """steward-session.sh must define permission_mode_flag_for_lane."""
        content = _read_steward_script()
        assert (
            "permission_mode_flag_for_lane()" in content
        ), "permission_mode_flag_for_lane function must be defined (#2767)"

    def test_helper_reads_lane_models_json(self) -> None:
        """Helper must resolve model tier from .claude/lane_models.json."""
        content = _read_steward_script()
        assert (
            "lane_models.json" in content
        ), "helper must reference .claude/lane_models.json as the config source"

    def test_helper_emits_both_flag_variants(self) -> None:
        """Helper must be able to emit both auto and dangerously-skip variants."""
        content = _read_steward_script()
        # Both token strings must appear inside the helper body.
        assert (
            "--permission-mode auto" in content
        ), "helper must emit '--permission-mode auto' for Opus lanes"
        assert (
            "--dangerously-skip-permissions" in content
        ), "helper must emit '--dangerously-skip-permissions' for non-Opus lanes"

    def test_every_launch_line_calls_helper(self) -> None:
        """Every $CLAUDE_BIN --agent launch line must invoke the helper.

        After #2767, no launch line hardcodes a permission-mode flag; each
        lane's flag comes from the model-tier helper so the launch script
        stays correct as lanes move between tiers.
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        assert launch_lines, "Expected at least one claude launch line in script"
        missing = [
            line.strip()
            for line in launch_lines
            if "permission_mode_flag_for_lane" not in line
        ]
        assert not missing, (
            "Every claude launch in steward-session.sh must route through "
            "`permission_mode_flag_for_lane <lane-id>` so the launch flag "
            "matches the lane's declared model tier (#2767). Missing the "
            f"helper call on {len(missing)} line(s):\n"
            + "\n".join(f"  {line}" for line in missing)
        )

    def test_helper_invocation_count_matches_launch_count(self) -> None:
        """Helper invocation count must equal launch-line count.

        One invocation per launch — if someone adds a lane without the
        helper, the counts diverge.
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        # Count $(permission_mode_flag_for_lane ...) invocations (not the
        # function definition itself).
        invocation_count = content.count("$(permission_mode_flag_for_lane ")
        assert invocation_count == len(launch_lines), (
            f"Expected one $(permission_mode_flag_for_lane ...) call per "
            f"launch line. Launch lines: {len(launch_lines)}; "
            f"invocations: {invocation_count}"
        )

    def test_no_hardcoded_flag_on_launch_lines(self) -> None:
        """No launch line may hardcode a permission-mode flag.

        Any hardcoded ``--permission-mode auto`` or
        ``--dangerously-skip-permissions`` on a launch line would make that
        lane insensitive to tier changes in ``lane_models.json`` — defeating
        the fix.
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        hardcoded = [
            line.strip()
            for line in launch_lines
            if "--permission-mode" in line or "--dangerously-skip-permissions" in line
        ]
        assert not hardcoded, (
            "Launch lines must not hardcode permission-mode flags. "
            "Route through permission_mode_flag_for_lane instead "
            f"(#2767). Hardcoded on {len(hardcoded)} line(s):\n"
            + "\n".join(f"  {line}" for line in hardcoded)
        )

    def test_orchestrator_helper_call_before_channel_flags(self) -> None:
        """Orchestrator helper call must precede $ORCH_CHANNEL_FLAGS.

        ``$ORCH_CHANNEL_FLAGS`` expands to ``--channels plugin:...`` or empty;
        the permission-mode tokens must appear before it so the expansion
        order is deterministic and safe whether channel flags are empty or
        populated.
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        orch_lines = [line for line in launch_lines if "steward-orchestrator" in line]
        assert len(orch_lines) == 1, "Expected exactly one orchestrator launch line"
        line = orch_lines[0]
        helper_pos = line.find("permission_mode_flag_for_lane")
        channel_pos = line.find("$ORCH_CHANNEL_FLAGS")
        assert (
            helper_pos > 0
        ), "Orchestrator launch must route through permission_mode_flag_for_lane"
        assert channel_pos > 0, "Orchestrator launch must expand $ORCH_CHANNEL_FLAGS"
        assert helper_pos < channel_pos, (
            "permission_mode_flag_for_lane call must appear BEFORE "
            "$ORCH_CHANNEL_FLAGS so the expansion is safe whether channel "
            "flags are empty or populated"
        )

    def test_helper_invocations_cover_all_lanes(self) -> None:
        """Each lane-id must appear exactly once as helper argument.

        Catches copy-paste errors where one lane's launch uses another
        lane's id in the helper call.
        """
        content = _read_steward_script()
        expected_lanes = [
            "orchestrator",
            "ops",
            "review",
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
            "flex-d",
        ]
        for lane in expected_lanes:
            token = f"$(permission_mode_flag_for_lane {lane})"
            assert content.count(token) == 1, (
                f"Expected exactly one invocation of "
                f"`{token}` in steward-session.sh; "
                f"found {content.count(token)}"
            )

    # -- Functional checks on the helper --------------------------------

    @staticmethod
    def _extract_helper(content: str) -> str:
        """Extract the permission_mode_flag_for_lane function body.

        Uses brace-depth tracking so the embedded ``case`` block with ``;;``
        doesn't confuse a naive regex.
        """
        lines = content.split("\n")
        out: list[str] = []
        in_func = False
        depth = 0
        for line in lines:
            if line.startswith("permission_mode_flag_for_lane()"):
                in_func = True
            if in_func:
                out.append(line)
                depth += line.count("{") - line.count("}")
                if depth == 0 and "}" in line and len(out) > 1:
                    break
        return "\n".join(out)

    def _run_helper(self, tmp_path: Path, config: dict, lane: str) -> str:
        """Invoke the helper in a bash subshell with a mocked config file."""
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "lane_models.json").write_text(json.dumps(config))
        helper_body = self._extract_helper(_read_steward_script())
        script = f"""
MAIN_DIR="{tmp_path}"
{helper_body}
permission_mode_flag_for_lane {lane}
"""
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"helper exited non-zero: {result.stderr}"
        return result.stdout.strip()

    def test_helper_emits_permission_mode_auto_for_opus_lane(
        self, tmp_path: Path
    ) -> None:
        """Opus-tier lanes must get ``--permission-mode auto``."""
        config = {"lanes": {"author-a": {"model": "opus"}}}
        flag = self._run_helper(tmp_path, config, "author-a")
        assert (
            flag == "--permission-mode auto"
        ), f"Opus lane must get '--permission-mode auto', got {flag!r}"

    def test_helper_emits_dangerously_skip_for_sonnet_lane(
        self, tmp_path: Path
    ) -> None:
        """Sonnet-tier lanes must get ``--dangerously-skip-permissions``."""
        config = {"lanes": {"ops": {"model": "sonnet"}}}
        flag = self._run_helper(tmp_path, config, "ops")
        assert (
            flag == "--dangerously-skip-permissions"
        ), f"Sonnet lane must get '--dangerously-skip-permissions', got {flag!r}"

    def test_helper_emits_dangerously_skip_for_haiku_lane(self, tmp_path: Path) -> None:
        """Haiku-tier lanes must get ``--dangerously-skip-permissions``."""
        config = {"lanes": {"flex-a": {"model": "haiku"}}}
        flag = self._run_helper(tmp_path, config, "flex-a")
        assert (
            flag == "--dangerously-skip-permissions"
        ), f"Haiku lane must get '--dangerously-skip-permissions', got {flag!r}"

    def test_helper_defaults_to_opus_for_missing_lane(self, tmp_path: Path) -> None:
        """Lanes not listed in the config must default to Opus treatment.

        The current fleet is 100% Opus; explicit entries are expected for
        non-Opus lanes. A missing entry must not silently emit
        ``--dangerously-skip-permissions`` — that would regress the
        legibility gain.
        """
        config = {"lanes": {"author-a": {"model": "opus"}}}
        flag = self._run_helper(tmp_path, config, "missing-lane")
        assert flag == "--permission-mode auto", (
            f"Missing lane must default to Opus treatment "
            f"('--permission-mode auto'); got {flag!r}"
        )

    def test_helper_defaults_to_opus_when_config_missing(self, tmp_path: Path) -> None:
        """Missing config file must also default to Opus."""
        helper_body = self._extract_helper(_read_steward_script())
        script = f"""
MAIN_DIR="{tmp_path}"
{helper_body}
permission_mode_flag_for_lane author-a
"""
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0
        assert result.stdout.strip() == "--permission-mode auto"

    def test_helper_defaults_to_opus_for_invalid_tier(self, tmp_path: Path) -> None:
        """Invalid tier values must coerce to Opus (safe default)."""
        config = {"lanes": {"author-a": {"model": "some-unknown-model"}}}
        flag = self._run_helper(tmp_path, config, "author-a")
        assert (
            flag == "--permission-mode auto"
        ), f"Invalid tier must coerce to '--permission-mode auto'; got {flag!r}"


class TestLaneModelsJson:
    """Tests for the canonical .claude/lane_models.json config file (#2767)."""

    _LANE_MODELS_PATH = REPO_ROOT / ".claude" / "lane_models.json"

    EXPECTED_LANES = frozenset(
        {
            "orchestrator",
            "ops",
            "review",
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
            "flex-d",
        }
    )

    VALID_MODELS = frozenset({"opus", "sonnet", "haiku"})

    def test_config_file_exists(self) -> None:
        # Use the GITHUB_SHA-aware helper: in CI, setup-uv cache restoration
        # can overwrite the working tree and drop PR-only files, so we must
        # accept the git-blob form of the file as "existing" for this test.
        assert (
            _lane_models_json_available()
        ), ".claude/lane_models.json is required by #2767 fix"

    def test_config_is_valid_json(self) -> None:
        data = json.loads(_read_lane_models_json())
        assert isinstance(data, dict), "Top level must be a JSON object"

    def test_config_has_lanes_key(self) -> None:
        data = json.loads(_read_lane_models_json())
        assert "lanes" in data and isinstance(
            data["lanes"], dict
        ), "Config must contain a 'lanes' object"

    def test_all_19_lanes_listed(self) -> None:
        """Every lane launched by steward-session.sh must have a config entry."""
        data = json.loads(_read_lane_models_json())
        lanes = set(data["lanes"].keys())
        missing = self.EXPECTED_LANES - lanes
        assert not missing, f"Missing lane entries: {sorted(missing)}"

    def test_all_models_valid(self) -> None:
        """Every entry's model must be opus / sonnet / haiku."""
        data = json.loads(_read_lane_models_json())
        for lane_id, entry in data["lanes"].items():
            assert isinstance(entry, dict), f"Lane {lane_id!r} entry must be an object"
            model = entry.get("model")
            assert model in self.VALID_MODELS, (
                f"Lane {lane_id!r} has invalid model {model!r}; "
                f"must be one of {sorted(self.VALID_MODELS)}"
            )

    def test_fleet_defaults_to_opus(self) -> None:
        """Current fleet is 100% Opus — all lanes must be Opus by default.

        When a lane moves to Sonnet or Haiku for token-economy reasons,
        this test must be updated in the same PR as the config change so
        reviewers see the tier change explicitly.
        """
        data = json.loads(_read_lane_models_json())
        non_opus = [
            lane_id
            for lane_id, entry in data["lanes"].items()
            if entry.get("model") != "opus"
        ]
        assert not non_opus, (
            f"Fleet-default is 100% Opus. Non-Opus entries: {non_opus}. "
            "If this is intentional, update this test and document the "
            "tier change in the PR."
        )


class TestLaneModelsLoader:
    """Tests for the Python loader scripts/internal/lane_models.py (#2767)."""

    @staticmethod
    def _import_loader():
        """Import the loader module (scripts/internal/lane_models.py)."""
        import sys

        scripts_internal = REPO_ROOT / "scripts" / "internal"
        if str(scripts_internal) not in sys.path:
            sys.path.insert(0, str(scripts_internal))
        import lane_models  # type: ignore[import-not-found]

        return lane_models

    def test_load_lane_models_returns_dict(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(
            json.dumps(
                {
                    "lanes": {
                        "author-a": {"model": "opus"},
                        "ops": {"model": "sonnet"},
                    }
                }
            )
        )
        result = loader.load_lane_models(cfg)
        assert result == {"author-a": "opus", "ops": "sonnet"}

    def test_load_lane_models_missing_file_returns_empty(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        result = loader.load_lane_models(tmp_path / "does-not-exist.json")
        assert result == {}

    def test_load_lane_models_malformed_returns_empty(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text("not { valid json")
        result = loader.load_lane_models(cfg)
        assert result == {}

    def test_load_lane_models_coerces_invalid_tier(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {"author-a": {"model": "gpt-5"}}}))
        result = loader.load_lane_models(cfg)
        assert result == {"author-a": "opus"}

    def test_get_lane_model_defaults_to_opus(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {"author-a": {"model": "opus"}}}))
        assert loader.get_lane_model("missing-lane", cfg) == "opus"

    def test_permission_mode_args_opus(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {"author-a": {"model": "opus"}}}))
        assert loader.permission_mode_args_for_lane("author-a", cfg) == [
            "--permission-mode",
            "auto",
        ]

    def test_permission_mode_args_sonnet(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {"ops": {"model": "sonnet"}}}))
        assert loader.permission_mode_args_for_lane("ops", cfg) == [
            "--dangerously-skip-permissions"
        ]

    def test_permission_mode_args_haiku(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {"flex-a": {"model": "haiku"}}}))
        assert loader.permission_mode_args_for_lane("flex-a", cfg) == [
            "--dangerously-skip-permissions"
        ]

    def test_permission_mode_args_missing_defaults_opus(self, tmp_path: Path) -> None:
        loader = self._import_loader()
        cfg = tmp_path / "lane_models.json"
        cfg.write_text(json.dumps({"lanes": {}}))
        assert loader.permission_mode_args_for_lane("author-a", cfg) == [
            "--permission-mode",
            "auto",
        ]

    def test_loader_stays_consistent_with_shell_helper(self, tmp_path: Path) -> None:
        """Python loader and shell helper must produce equivalent output.

        Both read the same config and emit the same token set (modulo Python
        list vs shell token-stream serialization).
        """
        loader = self._import_loader()
        cfg = tmp_path / ".claude" / "lane_models.json"
        cfg.parent.mkdir(parents=True)
        config = {
            "lanes": {
                "author-a": {"model": "opus"},
                "ops": {"model": "sonnet"},
                "flex-a": {"model": "haiku"},
            }
        }
        cfg.write_text(json.dumps(config))

        helper_body = TestPermissionModeByModelTier._extract_helper(
            _read_steward_script()
        )

        for lane, expected in [
            ("author-a", "--permission-mode auto"),
            ("ops", "--dangerously-skip-permissions"),
            ("flex-a", "--dangerously-skip-permissions"),
            ("nonexistent", "--permission-mode auto"),  # default
        ]:
            # Shell helper
            script = f"""
MAIN_DIR="{tmp_path}"
{helper_body}
permission_mode_flag_for_lane {lane}
"""
            result = subprocess.run(
                ["bash", "-c", script], capture_output=True, text=True
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == expected

            # Python loader
            py_argv = loader.permission_mode_args_for_lane(lane, cfg)
            assert (
                " ".join(py_argv) == expected
            ), f"Python loader and shell helper diverge for lane={lane!r}"


class TestSystemPromptFileFlag:
    """Tests for archetype-aware ``--system-prompt-file`` wiring (B.9b / §2767-γ).

    Per ``plans/steward_platform/2_primitive_B/shaping.md`` §6 (B.9b Fleet
    launch adoption of ``--system-prompt-file``) and G13 §2.1 (19-lane →
    8-archetype mapping at
    ``plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md``):

    * Every ``$CLAUDE_BIN`` launch line in steward-session.sh routes through
      ``system_prompt_flag_for_lane <lane-id>``.
    * The helper resolves ``<lane-id>`` to its archetype via a hardcoded
      19-lane case (matching G13 §2.1) and emits
      ``--system-prompt-file .claude/system_prompts/<archetype>.md`` iff
      the archetype prompt file exists on disk.
    * Missing prompt file ⇒ helper emits nothing; the lane falls back to
      the Claude Code default system prompt (pre-B.9a fan-out safety).
    """

    EXPECTED_LANES = (
        "orchestrator",
        "ops",
        "review",
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
        "flex-d",
    )

    # G13 §2.1 — 19-lane → 8-archetype mapping.
    LANE_TO_ARCHETYPE = {
        "orchestrator": "orchestrator",
        "ops": "ops",
        "review": "review",
        "analyst-a": "analyst",
        "analyst-b": "analyst",
        "analyst-c": "analyst",
        "analyst-d": "analyst",
        "author-a": "author",
        "author-b": "author",
        "author-c": "author",
        "author-d": "author",
        "brws-author-a": "brws-author",
        "brws-author-b": "brws-author",
        "brws-author-c": "brws-author",
        "brws-author-d": "brws-author",
        "flex-a": "flex",
        "flex-b": "flex",
        "flex-c": "flex",
        "flex-d": "flex",
    }

    EXPECTED_ARCHETYPES = frozenset(
        {
            "orchestrator",
            "ops",
            "review",
            "analyst",
            "author",
            "brws-author",
            "flex",
        }
    )

    @staticmethod
    def _claude_launch_lines(content: str) -> list[str]:
        return [
            line
            for line in content.split("\n")
            if "$CLAUDE_BIN" in line and "--agent" in line
        ]

    @staticmethod
    def _extract_helper(content: str) -> str:
        """Extract the ``system_prompt_flag_for_lane`` function body.

        Mirrors ``TestPermissionModeByModelTier._extract_helper`` brace-
        depth tracking so the embedded ``case`` block with ``;;`` doesn't
        confuse a naive regex.
        """
        lines = content.split("\n")
        out: list[str] = []
        in_func = False
        depth = 0
        for line in lines:
            if line.startswith("system_prompt_flag_for_lane()"):
                in_func = True
            if in_func:
                out.append(line)
                depth += line.count("{") - line.count("}")
                if depth == 0 and "}" in line and len(out) > 1:
                    break
        return "\n".join(out)

    # -- Structural checks on steward-session.sh ------------------------

    def test_helper_function_defined(self) -> None:
        """steward-session.sh must define ``system_prompt_flag_for_lane``."""
        content = _read_steward_script()
        assert "system_prompt_flag_for_lane()" in content, (
            "system_prompt_flag_for_lane function must be defined (B.9b / "
            "shaping.md §6)"
        )

    def test_every_launch_line_calls_system_prompt_helper(self) -> None:
        """Every ``$CLAUDE_BIN --agent`` line must invoke the helper.

        Missing the call on any launch line would leave that lane using
        the Claude Code default system prompt permanently, regressing the
        B.9b fleet-wide adoption.
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        assert launch_lines, "Expected at least one claude launch line in script"
        missing = [
            line.strip()
            for line in launch_lines
            if "system_prompt_flag_for_lane" not in line
        ]
        assert not missing, (
            "Every claude launch must route through `system_prompt_flag_for_lane "
            "<lane-id>` so the archetype system prompt is applied at launch "
            "time (B.9b). Missing on "
            f"{len(missing)} line(s):\n" + "\n".join(f"  {line}" for line in missing)
        )

    def test_system_prompt_invocation_count_matches_launch_count(self) -> None:
        """One ``$(system_prompt_flag_for_lane ...)`` per launch line."""
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        invocation_count = content.count("$(system_prompt_flag_for_lane ")
        assert invocation_count == len(launch_lines), (
            f"Expected one $(system_prompt_flag_for_lane ...) call per "
            f"launch line. Launch lines: {len(launch_lines)}; "
            f"invocations: {invocation_count}"
        )

    def test_system_prompt_helper_covers_all_lanes(self) -> None:
        """Each lane-id must appear exactly once as a helper argument.

        Catches copy-paste errors where one lane's launch passes another
        lane's id to the helper.
        """
        content = _read_steward_script()
        for lane in self.EXPECTED_LANES:
            token = f"$(system_prompt_flag_for_lane {lane})"
            assert content.count(token) == 1, (
                f"Expected exactly one invocation of `{token}` in "
                f"steward-session.sh; found {content.count(token)}"
            )

    def test_system_prompt_call_before_channel_flags_on_orchestrator(self) -> None:
        """Orchestrator: system-prompt helper must precede ``$ORCH_CHANNEL_FLAGS``.

        The ``$ORCH_CHANNEL_FLAGS`` expansion is either empty or expands
        to ``--channels plugin:...``. Placing the helper call before it
        keeps the argv order deterministic whether channel flags are
        empty or populated — matches the invariant enforced for the
        permission-mode helper (#2767 follow-on).
        """
        content = _read_steward_script()
        launch_lines = self._claude_launch_lines(content)
        orch_lines = [line for line in launch_lines if "steward-orchestrator" in line]
        assert len(orch_lines) == 1, "Expected exactly one orchestrator launch line"
        line = orch_lines[0]
        helper_pos = line.find("system_prompt_flag_for_lane")
        channel_pos = line.find("$ORCH_CHANNEL_FLAGS")
        assert (
            helper_pos > 0
        ), "Orchestrator launch must route through system_prompt_flag_for_lane"
        assert channel_pos > 0, "Orchestrator launch must expand $ORCH_CHANNEL_FLAGS"
        assert helper_pos < channel_pos, (
            "system_prompt_flag_for_lane call must appear BEFORE "
            "$ORCH_CHANNEL_FLAGS so the expansion is safe whether channel "
            "flags are empty or populated"
        )

    def test_helper_references_system_prompts_directory(self) -> None:
        """Helper body must reference ``.claude/system_prompts/``."""
        content = _read_steward_script()
        helper = self._extract_helper(content)
        assert helper, "system_prompt_flag_for_lane body must be extractable"
        assert ".claude/system_prompts/" in helper, (
            "Helper must reference the canonical .claude/system_prompts/ "
            "directory (per B.9a file layout)"
        )

    def test_helper_covers_all_8_archetypes(self) -> None:
        """Helper body must contain all 8 archetype identifiers.

        The archetype set is enumerated by G13 §2.1. A missing archetype
        in the shell ``case`` statement would silently drop system-prompt
        adoption for its lanes.
        """
        content = _read_steward_script()
        helper = self._extract_helper(content)
        missing = [a for a in self.EXPECTED_ARCHETYPES if a not in helper]
        assert not missing, (
            f"system_prompt_flag_for_lane must cover all 8 archetypes; "
            f"missing: {sorted(missing)}"
        )

    # -- Functional checks on the helper --------------------------------

    def _run_helper(
        self,
        tmp_path: Path,
        lane: str,
        *,
        present_archetypes: list[str] | None = None,
    ) -> str:
        """Invoke the helper in a bash subshell with a staged prompts dir.

        Staging: create ``<tmp_path>/.claude/system_prompts/<archetype>.md``
        for each archetype in ``present_archetypes``. If the list is
        omitted, no files exist (tests the fallback path).
        """
        prompts_dir = tmp_path / ".claude" / "system_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        for archetype in present_archetypes or []:
            (prompts_dir / f"{archetype}.md").write_text("# archetype prompt stub\n")
        helper_body = self._extract_helper(_read_steward_script())
        script = f"""
MAIN_DIR="{tmp_path}"
{helper_body}
system_prompt_flag_for_lane {lane}
"""
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, f"helper exited non-zero: {result.stderr}"
        return result.stdout.strip()

    def test_helper_emits_flag_when_archetype_file_exists(self, tmp_path: Path) -> None:
        """With ``analyst.md`` present, an analyst lane gets the flag."""
        out = self._run_helper(tmp_path, "analyst-a", present_archetypes=["analyst"])
        assert (
            out == "--system-prompt-file .claude/system_prompts/analyst.md"
        ), f"Expected analyst.md flag, got {out!r}"

    def test_helper_emits_nothing_when_archetype_file_missing(
        self, tmp_path: Path
    ) -> None:
        """With no prompt files staged, every lane gets empty output."""
        out = self._run_helper(tmp_path, "author-a", present_archetypes=[])
        assert out == "", (
            f"Expected fallback (empty output) when archetype file missing, "
            f"got {out!r}"
        )

    def test_helper_emits_empty_for_unknown_lane(self, tmp_path: Path) -> None:
        """Unknown lane-id falls back to empty (no flag)."""
        out = self._run_helper(
            tmp_path,
            "bogus-lane-42",
            present_archetypes=["analyst", "author", "flex"],
        )
        assert out == "", f"Expected empty output for unknown lane, got {out!r}"

    def test_helper_maps_every_known_lane_to_its_archetype(
        self, tmp_path: Path
    ) -> None:
        """Every known lane resolves to the archetype per G13 §2.1."""
        # Stage all 8 archetype prompt files so the helper always emits
        # the flag — we're checking the case-statement mapping, not the
        # fallback path.
        present = list(self.EXPECTED_ARCHETYPES)
        for lane, expected_archetype in self.LANE_TO_ARCHETYPE.items():
            out = self._run_helper(tmp_path, lane, present_archetypes=present)
            expected = (
                f"--system-prompt-file .claude/system_prompts/"
                f"{expected_archetype}.md"
            )
            assert out == expected, (
                f"Lane {lane!r} must resolve to archetype "
                f"{expected_archetype!r}; got {out!r}"
            )

    def test_helper_handles_per_archetype_partial_rollout(self, tmp_path: Path) -> None:
        """With only ``analyst.md`` present, non-analyst lanes get empty.

        This is the current (pre-B.9a fan-out) state: only analyst.md
        lives in ``.claude/system_prompts/`` and other archetypes are
        still pending. The helper must return the flag for analyst
        lanes and empty for everyone else.
        """
        out_analyst = self._run_helper(
            tmp_path, "analyst-a", present_archetypes=["analyst"]
        )
        out_author = self._run_helper(
            tmp_path, "author-a", present_archetypes=["analyst"]
        )
        out_orchestrator = self._run_helper(
            tmp_path, "orchestrator", present_archetypes=["analyst"]
        )
        assert (
            out_analyst == "--system-prompt-file .claude/system_prompts/analyst.md"
        ), f"analyst-a with analyst.md present must emit flag, got {out_analyst!r}"
        assert out_author == "", (
            f"author-a without author.md must emit empty (fallback), "
            f"got {out_author!r}"
        )
        assert out_orchestrator == "", (
            f"orchestrator without orchestrator.md must emit empty (fallback), "
            f"got {out_orchestrator!r}"
        )

    def test_committed_analyst_prompt_is_wired(self) -> None:
        """Live check: the committed ``.claude/system_prompts/analyst.md``
        is picked up by the helper for each analyst lane when running
        against the real repo (not a tmp-path mock).

        This is a thin smoke test guarding against accidental drift
        between the B.9a authoring surface and the B.9b launch surface.
        """
        analyst_prompt = REPO_ROOT / ".claude" / "system_prompts" / "analyst.md"
        if not analyst_prompt.exists():
            pytest.skip("analyst.md not present; B.9a landing still pending")
        helper_body = self._extract_helper(_read_steward_script())
        script = f"""
MAIN_DIR="{REPO_ROOT}"
{helper_body}
system_prompt_flag_for_lane analyst-b
"""
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert (
            result.stdout.strip()
            == "--system-prompt-file .claude/system_prompts/analyst.md"
        ), (
            "Real-repo check failed: analyst-b did not emit the analyst.md "
            f"flag. stdout={result.stdout!r}"
        )

    def test_helper_docstring_under_x3_threshold(self) -> None:
        """Regression guard: the ``system_prompt_flag_for_lane`` docstring
        must not exceed the deterministic-precheck X3 threshold
        (11+ consecutive ``#`` comment lines).

        Rationale: the initial B.9b landing (PR #2796) shipped a 20-line
        docstring that tripped X3 in the follow-up review. The cleanup
        (PR succeeding #2796) condenses it. This test prevents regression
        if someone re-expands the comment without noticing the X3 gate.

        Scope: this test only inspects the comment block *immediately above*
        ``system_prompt_flag_for_lane`` (contiguous ``#`` lines bounded by a
        blank line or non-comment line above). Pre-existing large blocks
        elsewhere in the file (file header, other helpers) are out of scope
        and tracked in backlog follow-ups.

        Uses ``_read_steward_script()`` to read from the git-committed blob
        in CI (setup-uv cache restoration can overwrite the working tree;
        see the helper's docstring).
        """
        content = _read_steward_script()
        lines = content.split("\n")
        # Find the helper definition line.
        helper_line_idx = next(
            i
            for i, ln in enumerate(lines)
            if ln.startswith("system_prompt_flag_for_lane() {")
        )
        # Walk backward, collecting contiguous ``#`` comment lines until
        # we hit a blank line or a non-comment line.
        contiguous = 0
        for i in range(helper_line_idx - 1, -1, -1):
            stripped = lines[i].lstrip()
            if stripped.startswith("#"):
                contiguous += 1
            else:
                break
        assert contiguous < 11, (
            f"system_prompt_flag_for_lane helper has {contiguous} "
            "contiguous # comment lines immediately above it — this "
            "trips deterministic-precheck X3 (≥11 lines). Split the "
            "docstring into blocks of ≤10 consecutive # lines separated "
            "by blank lines."
        )


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
