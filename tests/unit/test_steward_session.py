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
