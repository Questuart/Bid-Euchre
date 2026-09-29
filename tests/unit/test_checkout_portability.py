"""Operator entry points must discover checkouts without a personal home path."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "--allow-empty",
        "-m",
        "initial",
    )
    return root


def run_script(relative, cwd, env=None):
    return subprocess.run(
        ["bash", str(REPO / relative)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_guard_creates_once_and_allows_linked_worktree(checkout):
    script = ".claude/hooks/worktree-guard.sh"
    first = run_script(script, checkout)
    assert first.returncode == 1
    paths = [
        line.removeprefix("worktree ")
        for line in git(checkout, "worktree", "list", "--porcelain").stdout.splitlines()
        if line.startswith("worktree ")
    ]
    assert len(paths) == 2
    second = run_script(script, checkout)
    assert second.returncode == 1
    assert "Existing worktree available" in second.stdout
    assert (
        git(checkout, "worktree", "list", "--porcelain").stdout.count("worktree ") == 2
    )
    assert run_script(script, Path(paths[1])).returncode == 0


def test_reminder_only_warns_in_primary_main(checkout):
    script = ".claude/hooks/worktree-reminder.sh"
    assert "SESSION NOTICE" in run_script(script, checkout).stdout
    linked = checkout.parent / "linked"
    git(checkout, "worktree", "add", "-b", "topic", str(linked))
    assert "SESSION NOTICE" not in run_script(script, linked).stdout


def test_helper_works_from_primary_and_rejects_linked(checkout, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text("#!/bin/sh\npwd\n")
    stub.chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    result = run_script(".claude/scripts/claude-worktree.sh", checkout, env)
    assert result.returncode == 0, result.stderr
    linked = Path(result.stdout.strip().splitlines()[-1])
    assert linked.is_dir() and linked != checkout
    assert run_script(".claude/scripts/claude-worktree.sh", linked, env).returncode == 1


def test_overnight_discovers_script_checkout_before_dispatch(checkout, tmp_path):
    # Stop at first uv invocation: test discovery without running a research campaign.
    script_dir = checkout / "scripts/internal"
    script_dir.mkdir(parents=True)
    script = script_dir / "overnight_full_orchestrator.sh"
    shutil.copy(REPO / "scripts/internal/overnight_full_orchestrator.sh", script)
    source = script.read_text()
    discovery = source.split("log() {", 1)[0]
    probe = script_dir / "discovery.sh"
    probe.write_text(discovery + '\nprintf "%s\\n" "$PWD"\n')
    result = subprocess.run(
        ["bash", str(probe)], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == str(checkout.resolve())
