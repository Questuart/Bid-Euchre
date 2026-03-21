"""Regression tests for the post-push CI polling hook."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "post-push-ci-check.sh"


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _wait_for_file(path: Path, timeout_s: float = 3.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {path}")


def test_post_push_hook_uses_project_dir_and_sanitizes_branch(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "worktree"
    project_dir.mkdir()

    _run(["git", "init"], cwd=project_dir)
    _run(["git", "config", "user.name", "Test User"], cwd=project_dir)
    _run(["git", "config", "user.email", "test@example.com"], cwd=project_dir)

    (project_dir / "README.md").write_text("hook test\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=project_dir)
    _run(["git", "commit", "-m", "init"], cwd=project_dir)
    _run(["git", "checkout", "-b", "fix/test-poller"], cwd=project_dir)

    (project_dir / "scripts" / "internal").mkdir(parents=True)
    poller_cwd = project_dir / "poller.cwd"
    poller_args = project_dir / "poller.args"
    _write_executable(
        project_dir / "scripts" / "internal" / "ci_poller.sh",
        f"""#!/bin/bash
set -euo pipefail
printf '%s\\n' "$PWD" > "{poller_cwd}"
printf '%s\\n' "$@" > "{poller_args}"
""",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_cwd = project_dir / "gh.cwd"
    _write_executable(
        bin_dir / "gh",
        f"""#!/bin/bash
set -euo pipefail
printf '%s\\n' "$PWD" > "{gh_cwd}"
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
    echo 776
    exit 0
fi
echo "unexpected gh args: $*" >&2
exit 1
""",
    )

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    hook_input = json.dumps(
        {
            "tool_input": {"command": "git push origin fix/test-poller"},
            "tool_response": {"exit_code": 0},
        }
    )
    result = subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=hook_input,
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    _wait_for_file(gh_cwd)
    _wait_for_file(poller_cwd)
    _wait_for_file(poller_args)

    assert gh_cwd.read_text(encoding="utf-8").strip() == str(project_dir)
    assert poller_cwd.read_text(encoding="utf-8").strip() == str(project_dir)
    assert poller_args.read_text(encoding="utf-8").splitlines() == [
        "--pr",
        "776",
        "--repo-root",
        str(project_dir),
    ]
    assert "PR #776" in result.stdout
