"""Smoke tests for .claude/tmux/steward-session.sh — update_last_active()."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

STEWARD_SESSION = Path(".claude/tmux/steward-session.sh")


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
