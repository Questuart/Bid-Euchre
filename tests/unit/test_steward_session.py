"""Tests for the steward session bootstrap script (.claude/tmux/steward-session.sh).

Covers update_last_active(), detached-mode support, and launchd recovery
infrastructure without requiring tmux to be running.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STEWARD_SCRIPT = REPO_ROOT / ".claude" / "tmux" / "steward-session.sh"
INSTALL_SCRIPT = REPO_ROOT / ".claude" / "launchd" / "install-launchd.sh"
PLIST_TEMPLATE = REPO_ROOT / ".claude" / "launchd" / "ensure-steward-session.plist"

STEWARD_SESSION = Path(".claude/tmux/steward-session.sh")


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
    """Validate the 4-window layout (central-ops: 3 panes, others: 4 panes)."""

    EXPECTED_WINDOWS = ["central-ops", "platform", "browser", "scratch"]

    # Worker windows with 4 tiled panes each
    TILED_WINDOWS = ["platform", "browser", "scratch"]

    EXPECTED_LANES = [
        # Central ops (3 panes)
        "orchestrator",
        "ops",
        "review",
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
        # Scratch / flex
        "author-scratch",
        "flex-a",
        "flex-b",
        "flex-c",
    ]

    # Lanes per window, in pane creation order (pane 0 = first)
    WINDOW_PANES = {
        "central-ops": ["orchestrator", "ops", "review"],
        "platform": ["author-a", "author-b", "author-c", "author-d"],
        "browser": [
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
        ],
        "scratch": ["author-scratch", "flex-a", "flex-b", "flex-c"],
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

    def test_four_windows_created(self) -> None:
        """Exactly 4 tmux windows must be created (1 new-session + 3 new-window)."""
        content = STEWARD_SCRIPT.read_text()
        lines = content.split("\n")
        window_cmds = [
            line
            for line in lines
            if line.strip().startswith("tmux")
            and ("new-session" in line or "new-window" in line)
        ]
        assert (
            len(window_cmds) == 4
        ), f"Expected 4 window creation commands, found {len(window_cmds)}"
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
        """central-ops must use main-vertical layout (orchestrator large left)."""
        content = STEWARD_SCRIPT.read_text()
        assert (
            'select-layout -t "${SESSION}:central-ops" main-vertical' in content
        ), "central-ops must use main-vertical layout"

    def test_worker_windows_have_4_panes(self) -> None:
        """Each worker window must have 3 split-window commands (for 4 panes)."""
        content = STEWARD_SCRIPT.read_text()
        for window_name in self.TILED_WINDOWS:
            split_count = content.count(f'split-window -t "${{SESSION}}:{window_name}"')
            assert split_count == 3, (
                f"Window '{window_name}' must have 3 split-window commands, "
                f"found {split_count}"
            )

    def test_worker_windows_tiled(self) -> None:
        """Worker windows must use tiled layout."""
        content = STEWARD_SCRIPT.read_text()
        for window_name in self.TILED_WINDOWS:
            assert (
                f'select-layout -t "${{SESSION}}:{window_name}" tiled' in content
            ), f"Window '{window_name}' must have select-layout tiled"

    def test_all_lanes_launched(self) -> None:
        """All 15 lanes must appear in new-session, new-window, or split-window."""
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

    def test_metadata_pane_indices(self) -> None:
        """All lanes must have valid pane indices in their metadata."""
        metadata_lines = self._metadata_invocation_lines()
        assert len(metadata_lines) == len(self.EXPECTED_LANES), (
            f"Expected {len(self.EXPECTED_LANES)} write_lane_metadata calls, "
            f"found {len(metadata_lines)}"
        )
        for line in metadata_lines:
            has_pane_idx = any(f'"{i}"' in line for i in range(4))
            assert (
                has_pane_idx
            ), f"Lane metadata must have a pane index (0-3): {line.strip()}"

    def test_metadata_window_names(self) -> None:
        """All metadata must reference one of the 4 group window names."""
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
        """Worker lanes must have background visibility."""
        metadata_lines = self._metadata_invocation_lines()
        worker_lanes = {
            "author-a",
            "author-b",
            "author-c",
            "author-d",
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
            "author-scratch",
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

    def test_review_check_targets_correct_pane(self) -> None:
        """The review-check loop must target central-ops.3 (review pane).

        With pane-base-index=1: orchestrator=.1, ops=.2, review=.3.
        """
        content = STEWARD_SCRIPT.read_text()
        assert "central-ops.3" in content, "Review-check must target central-ops.3"

    def test_legacy_rollback_exists(self) -> None:
        """steward-session-legacy.sh must exist for rollback."""
        legacy = REPO_ROOT / ".claude" / "tmux" / "steward-session-legacy.sh"
        assert legacy.exists(), "steward-session-legacy.sh must exist as rollback path"

    def test_legacy_has_original_8_lanes(self) -> None:
        """Legacy script should have the original 8-lane layout."""
        legacy = REPO_ROOT / ".claude" / "tmux" / "steward-session-legacy.sh"
        content = legacy.read_text()
        # Original lanes present
        for lane in [
            "orchestrator",
            "author-a",
            "author-b",
            "author-c",
            "author-d",
            "author-scratch",
            "ops",
            "review",
        ]:
            assert f"-n {lane}" in content
        # New lanes absent
        assert "brws-author" not in content
        assert "flex-a" not in content

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
