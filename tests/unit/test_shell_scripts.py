"""Smoke tests for shell scripts in .claude/scripts/ and .claude/tmux/.

Tests invoke script fragments via subprocess to verify argument validation,
usage messages, and pure helper functions. Nothing here creates real git
worktrees or tmux sessions.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

# Resolve project root — the actual main checkout (not a worktree) is needed
# for some tests that invoke the script directly, but we also need the scripts
# themselves from the worktree we are in.
WORKTREE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = WORKTREE_ROOT / ".claude" / "scripts"
TMUX_DIR = WORKTREE_ROOT / ".claude" / "tmux"

START_ROLE_WORKTREE = SCRIPTS_DIR / "start-role-worktree.sh"
START_AGENT_ROLE = SCRIPTS_DIR / "start-agent-role.sh"
STEWARD_SESSION = TMUX_DIR / "steward-session.sh"


def _run(
    cmd: list[str] | str,
    *,
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the completed process."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        shell=shell,
        timeout=10,
    )


# ---------------------------------------------------------------------------
# TestStartRoleWorktree
# ---------------------------------------------------------------------------


class TestStartRoleWorktree:
    """Tests for .claude/scripts/start-role-worktree.sh."""

    def test_write_registry_produces_valid_json(self, tmp_path: Path) -> None:
        """Source write_registry and verify it produces valid JSON."""
        registry_dir = tmp_path / "registry"
        # Extract the write_registry and now_iso functions, override
        # REGISTRY_DIR, then call write_registry.
        script = f"""\
now_iso() {{
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}}

REGISTRY_DIR="{registry_dir}"

write_registry() {{
    local role="$1"
    local wt_path="$2"
    local branch="$3"
    local created="$4"

    mkdir -p "$REGISTRY_DIR"

    cat > "$REGISTRY_DIR/${{role}}.json" <<EOJSON
{{
  "schema_version": 1,
  "role": "${{role}}",
  "worktree_path": "${{wt_path}}",
  "branch": "${{branch}}",
  "class": "persistent",
  "created_at": "${{created}}",
  "last_active": "$(now_iso)",
  "session_id": null,
  "ttl_hours": null
}}
EOJSON
}}

write_registry "author" "/tmp/test-wt" "role/author" "2026-01-01T00:00:00Z"
"""
        result = _run(["bash", "-c", script])
        assert result.returncode == 0, f"write_registry failed: {result.stderr}"

        output_file = registry_dir / "author.json"
        assert output_file.exists(), "Registry JSON was not created"

        data = json.loads(output_file.read_text())
        assert data["schema_version"] == 1
        assert data["role"] == "author"
        assert data["worktree_path"] == "/tmp/test-wt"
        assert data["branch"] == "role/author"
        assert data["class"] == "persistent"
        assert data["created_at"] == "2026-01-01T00:00:00Z"
        assert data["session_id"] is None
        assert data["ttl_hours"] is None
        # last_active should be a timestamp string
        assert data["last_active"].endswith("Z")

    def test_is_valid_role_accepts_valid_roles(self) -> None:
        """is_valid_role should return 0 for author, review, ops."""
        func_body = """\
VALID_ROLES="author review ops"

is_valid_role() {
    local role="$1"
    for r in $VALID_ROLES; do
        if [ "$r" = "$role" ]; then
            return 0
        fi
    done
    return 1
}
"""
        for role in ("author", "review", "ops"):
            result = _run(["bash", "-c", f"{func_body}\nis_valid_role {role}"])
            assert (
                result.returncode == 0
            ), f"is_valid_role should accept '{role}' but exited {result.returncode}"

    def test_is_valid_role_rejects_invalid_role(self) -> None:
        """is_valid_role should return non-zero for an invalid role."""
        func_body = """\
VALID_ROLES="author review ops"

is_valid_role() {
    local role="$1"
    for r in $VALID_ROLES; do
        if [ "$r" = "$role" ]; then
            return 0
        fi
    done
    return 1
}
"""
        result = _run(["bash", "-c", f"{func_body}\nis_valid_role hacker"])
        assert result.returncode != 0, "is_valid_role should reject 'hacker'"

    def test_usage_prints_help(self) -> None:
        """--help should print usage text and exit 0."""
        # The script computes MAIN_DIR from its own location via git, so we
        # need to run it from the actual repo. It also checks that the
        # current toplevel matches MAIN_DIR — we run from the worktree root.
        result = _run(
            ["bash", str(START_ROLE_WORKTREE), "--help"],
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode == 0, f"--help should exit 0: {result.stderr}"
        assert "Usage:" in result.stdout

    def test_invalid_role_argument_exits_nonzero(self) -> None:
        """An invalid role argument should exit non-zero with an error."""
        result = _run(
            ["bash", str(START_ROLE_WORKTREE), "invalid_role"],
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode != 0
        assert "Invalid role" in result.stderr or "Invalid role" in result.stdout


# ---------------------------------------------------------------------------
# TestStartAgentRole
# ---------------------------------------------------------------------------


class TestStartAgentRole:
    """Tests for .claude/scripts/start-agent-role.sh."""

    def test_no_args_prints_usage(self) -> None:
        """Running with no arguments should print usage and exit 1."""
        result = _run(
            ["bash", str(START_AGENT_ROLE)],
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout

    def test_invalid_role_exits_nonzero(self) -> None:
        """An invalid role should exit 1 with an error."""
        result = _run(
            ["bash", str(START_AGENT_ROLE), "hacker"],
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode == 1
        assert "Invalid role" in result.stderr or "Invalid role" in result.stdout

    def test_missing_worktree_exits_nonzero(self, tmp_path: Path) -> None:
        """A valid role with a nonexistent worktree path should exit 1."""
        # Create a minimal git repo in tmp_path so the script's MAIN_DIR
        # resolves to it. The worktree sibling path will not exist.
        scripts_dir = tmp_path / "repo" / ".claude" / "scripts"
        scripts_dir.mkdir(parents=True)
        script_copy = scripts_dir / "start-agent-role.sh"
        script_copy.write_text(START_AGENT_ROLE.read_text())

        # Initialise a git repo so git rev-parse --show-toplevel works
        repo_dir = tmp_path / "repo"
        subprocess.run(
            ["git", "init"], cwd=str(repo_dir), capture_output=True, check=True
        )

        result = _run(
            ["bash", str(script_copy), "author"],
            cwd=str(repo_dir),
        )
        assert result.returncode == 1
        combined = result.stdout + result.stderr
        assert "not found" in combined or "worktree" in combined.lower()


# ---------------------------------------------------------------------------
# TestStewardSession
# ---------------------------------------------------------------------------


class TestStewardSession:
    """Tests for .claude/tmux/steward-session.sh."""

    def test_no_tmux_prints_error(self) -> None:
        """Without tmux in PATH the script should exit 1 with an error."""
        # The script checks for claude BEFORE tmux, so we must provide a
        # fake claude binary to get past the claude check and reach the
        # tmux check.
        minimal_env = os.environ.copy()
        # Use only /usr/bin and /bin — tmux is typically in /opt/homebrew/bin
        # or /usr/local/bin. If tmux happens to be in /usr/bin, skip this
        # test since we cannot exclude it without risking breaking bash.
        tmux_in_minimal = (
            subprocess.run(
                ["bash", "-c", 'PATH="/usr/bin:/bin" command -v tmux'],
                capture_output=True,
            ).returncode
            == 0
        )
        if tmux_in_minimal:
            pytest.skip("tmux is in /usr/bin or /bin — cannot exclude from PATH")

        minimal_env["PATH"] = "/usr/bin:/bin"
        # Set CLAUDE_BIN to a dummy value so the script passes the claude
        # check and reaches the tmux check.
        minimal_env["CLAUDE_BIN"] = "/usr/bin/true"
        result = _run(
            ["bash", str(STEWARD_SESSION)],
            env=minimal_env,
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode == 1
        combined = result.stdout + result.stderr
        assert "tmux" in combined.lower()

    def test_no_claude_prints_error(self) -> None:
        """Without claude binary the script should exit 1 with an error."""
        # The script uses ${CLAUDE_BIN:-$(command -v claude || true)}.
        # The :- operator substitutes the default when the variable is
        # unset OR empty, so we must also remove claude from PATH to
        # ensure `command -v claude` fails.
        #
        # claude may be installed in multiple PATH directories, so we
        # filter out every directory that contains a 'claude' binary.
        env = os.environ.copy()
        env.pop("CLAUDE_BIN", None)

        path_parts = []
        for p in env.get("PATH", "").split(":"):
            if not p:
                continue
            if (Path(p) / "claude").exists():
                continue
            path_parts.append(p)
        env["PATH"] = ":".join(path_parts)

        # Use a unique session name to avoid attaching to any existing
        # tmux session (the script short-circuits to attach if found).
        result = _run(
            ["bash", str(STEWARD_SESSION), "test_no_claude_session_nonexistent"],
            env=env,
            cwd=str(WORKTREE_ROOT),
        )
        assert result.returncode == 1
        combined = result.stdout + result.stderr
        assert "claude" in combined.lower()


# ---------------------------------------------------------------------------
# ci_poller.sh
# ---------------------------------------------------------------------------

CI_POLLER = WORKTREE_ROOT / "scripts" / "internal" / "ci_poller.sh"


class TestCiPoller:
    """Smoke tests for ci_poller.sh."""

    def test_syntax_valid(self) -> None:
        result = _run(["bash", "-n", str(CI_POLLER)])
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_merged_pr_check_present(self) -> None:
        """ci_poller.sh must detect merged/closed PRs (#862)."""
        content = CI_POLLER.read_text()
        assert "MERGED" in content, "Missing MERGED detection"
        assert "CLOSED" in content, "Missing CLOSED detection"

    def test_timeout_emits_ci_timeout_event(self) -> None:
        """Timeout branch must emit ci_timeout event (#991)."""
        content = CI_POLLER.read_text()
        # The emit_ci_event helper must document ci_timeout
        assert (
            "ci_timeout" in content
        ), "ci_poller.sh must emit ci_timeout on the timeout path"
        # Verify the timeout branch specifically calls emit_ci_event
        # Find the timeout block and verify it contains the emit call
        lines = content.split("\n")
        in_timeout_block = False
        found_emit_in_timeout = False
        for line in lines:
            if "ELAPSED" in line and "TIMEOUT" in line and "-ge" in line:
                in_timeout_block = True
            if in_timeout_block and "emit_ci_event" in line and "ci_timeout" in line:
                found_emit_in_timeout = True
                break
            if in_timeout_block and "fi" in line.strip():
                break
        assert (
            found_emit_in_timeout
        ), "Timeout branch must call emit_ci_event with ci_timeout"
