"""Unit tests for .claude/hooks/lib/resolve-lane-id.sh.

The resolver is a pure-bash sourced function that centralizes the
19-case fleet lane-id table previously duplicated across seven hook
scripts (#2690). These tests exercise every canonical fleet lane,
the CLAUDE_AGENT_NAME precedence rule, the case-pattern ordering
invariant (author-scratch before author), and the empty/unknown
fallback contract.

The tests invoke bash directly — no `uv run` — to match the hook
execution environment, where the heartbeat hook's 2s budget forbids
Python cold starts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_SH = REPO_ROOT / ".claude" / "hooks" / "lib" / "resolve-lane-id.sh"


# ---------------------------------------------------------------------------
# Helper — run the sourced function in a clean bash subprocess
# ---------------------------------------------------------------------------


def _resolve(
    *,
    agent_name: str | None = None,
    project_dir: str | None = None,
    strict: bool = True,
) -> str:
    """Source the library in a fresh bash shell and call resolve_lane_id.

    `strict=True` matches the six hooks that run with `set -euo pipefail`
    so we prove the helper is strict-mode safe.
    """
    env: dict[str, str] = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    if agent_name is not None:
        env["CLAUDE_AGENT_NAME"] = agent_name
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir

    strict_prefix = "set -euo pipefail\n" if strict else ""
    script = f"{strict_prefix}. {LIB_SH}\nresolve_lane_id\n"
    result = subprocess.run(
        ["bash", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"resolve_lane_id exited {result.returncode}: stderr={result.stderr!r}"
    return result.stdout


# ---------------------------------------------------------------------------
# Sanity: the library file exists and is syntactically valid
# ---------------------------------------------------------------------------


def test_lib_file_exists() -> None:
    assert LIB_SH.is_file(), f"Missing library: {LIB_SH}"


def test_lib_passes_bash_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(LIB_SH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr!r}"


# ---------------------------------------------------------------------------
# CLAUDE_AGENT_NAME path — simple prefix strip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "agent_name,expected",
    [
        ("steward-author-a", "author-a"),
        ("steward-author-b", "author-b"),
        ("steward-author-c", "author-c"),
        ("steward-author-d", "author-d"),
        ("steward-analyst-c", "analyst-c"),
        ("steward-flex-d", "flex-d"),
        ("steward-brws-author-d", "brws-author-d"),
        ("steward-review", "review"),
        ("steward-ops", "ops"),
        # No steward- prefix → passthrough (unusual, but the contract
        # is "strip the prefix if present", not "validate the value").
        ("orchestrator", "orchestrator"),
    ],
)
def test_agent_name_strip(agent_name: str, expected: str) -> None:
    assert _resolve(agent_name=agent_name) == expected


def test_agent_name_takes_precedence_over_project_dir() -> None:
    """When both env vars are set, AGENT_NAME wins."""
    out = _resolve(
        agent_name="steward-flex-a",
        project_dir="/x/y/Bid-Euchre-steward-author-d",
    )
    assert out == "flex-a"


# ---------------------------------------------------------------------------
# CLAUDE_PROJECT_DIR fallback — full fleet coverage
# ---------------------------------------------------------------------------


CANONICAL_LANES = [
    # (worktree dir basename, expected lane_id)
    ("Bid-Euchre-steward-author", "author-a"),
    ("Bid-Euchre-steward-author-b", "author-b"),
    ("Bid-Euchre-steward-author-c", "author-c"),
    ("Bid-Euchre-steward-author-d", "author-d"),
    ("Bid-Euchre-steward-author-scratch", "author-scratch"),
    ("Bid-Euchre-steward-brws-author-a", "brws-author-a"),
    ("Bid-Euchre-steward-brws-author-b", "brws-author-b"),
    ("Bid-Euchre-steward-brws-author-c", "brws-author-c"),
    ("Bid-Euchre-steward-brws-author-d", "brws-author-d"),
    ("Bid-Euchre-steward-analyst", "analyst-a"),
    ("Bid-Euchre-steward-analyst-b", "analyst-b"),
    ("Bid-Euchre-steward-analyst-c", "analyst-c"),
    ("Bid-Euchre-steward-analyst-d", "analyst-d"),
    ("Bid-Euchre-steward-flex-a", "flex-a"),
    ("Bid-Euchre-steward-flex-b", "flex-b"),
    ("Bid-Euchre-steward-flex-c", "flex-c"),
    ("Bid-Euchre-steward-flex-d", "flex-d"),
    ("Bid-Euchre-steward-review", "review"),
    ("Bid-Euchre-steward-ops", "ops"),
]


@pytest.mark.parametrize("basename,expected", CANONICAL_LANES)
def test_project_dir_all_canonical_lanes(
    tmp_path: Path, basename: str, expected: str
) -> None:
    project = tmp_path / basename
    project.mkdir()
    assert _resolve(project_dir=str(project)) == expected


def test_project_dir_works_with_absolute_path_prefix(tmp_path: Path) -> None:
    """Patterns use `*steward-...)` glob so any path prefix matches."""
    deep = tmp_path / "Projects" / "Meta" / "Bid-Euchre-steward-analyst-c"
    deep.mkdir(parents=True)
    assert _resolve(project_dir=str(deep)) == "analyst-c"


def test_project_dir_when_basename_alone_matches() -> None:
    """Even a bare basename (no leading dirs) must match."""
    # Use a real path for basename() to work — /tmp is safe.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "Bid-Euchre-steward-ops"
        proj.mkdir()
        assert _resolve(project_dir=str(proj)) == "ops"


def test_author_scratch_ordering_does_not_collide_with_author() -> None:
    """`*steward-author-scratch)` must precede `*steward-author)`.

    Without correct ordering, `Bid-Euchre-steward-author-scratch` would
    match `*steward-author)` first (since both globs apply) and resolve
    to "author-a". This test locks the invariant documented in the
    library preamble.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "Bid-Euchre-steward-author-scratch"
        proj.mkdir()
        assert _resolve(project_dir=str(proj)) == "author-scratch"


# ---------------------------------------------------------------------------
# Unknown / empty contract
# ---------------------------------------------------------------------------


def test_neither_env_var_set_returns_empty() -> None:
    """Contract: unresolved context returns empty string, not 'unknown'.

    Each caller owns its own fallback policy (hostname, "unknown",
    "main", etc.). This keeps the helper unopinionated.
    """
    assert _resolve() == ""


def test_unknown_dir_returns_empty(tmp_path: Path) -> None:
    """Dir names that don't match the fleet table return empty."""
    proj = tmp_path / "Bid-Euchre"
    proj.mkdir()
    assert _resolve(project_dir=str(proj)) == ""

    proj2 = tmp_path / "Bid-Euchre-foo"
    proj2.mkdir()
    assert _resolve(project_dir=str(proj2)) == ""

    proj3 = tmp_path / "some-other-repo"
    proj3.mkdir()
    assert _resolve(project_dir=str(proj3)) == ""


def test_empty_agent_name_falls_through_to_project_dir(tmp_path: Path) -> None:
    """AGENT_NAME="" must not short-circuit — project_dir should still resolve."""
    proj = tmp_path / "Bid-Euchre-steward-flex-b"
    proj.mkdir()
    assert _resolve(agent_name="", project_dir=str(proj)) == "flex-b"


# ---------------------------------------------------------------------------
# Strict-mode safety — six of seven callers run with set -euo pipefail
# ---------------------------------------------------------------------------


def test_resolver_safe_under_strict_mode(tmp_path: Path) -> None:
    """Caller hooks use `set -euo pipefail`; helper must not trip it."""
    proj = tmp_path / "Bid-Euchre-steward-review"
    proj.mkdir()
    # Already strict=True by default, but be explicit to document intent.
    assert _resolve(project_dir=str(proj), strict=True) == "review"


def test_resolver_strict_mode_with_no_env() -> None:
    """Empty resolution path must also be strict-mode safe."""
    assert _resolve(strict=True) == ""


# ---------------------------------------------------------------------------
# Single-source-of-truth invariant
# ---------------------------------------------------------------------------


def test_no_duplicate_steward_case_statement_in_callers() -> None:
    """After consolidation, no hook in the caller set should carry a
    duplicate `*steward-author-d)` case pattern.

    This guards against someone re-introducing a drifted copy. The
    canonical pattern appears exactly once: in resolve-lane-id.sh.
    """
    callers = [
        REPO_ROOT / ".claude" / "hooks" / "post-merge-notify.sh",
        REPO_ROOT / ".claude" / "hooks" / "lane-heartbeat-post-tool.sh",
        REPO_ROOT / ".claude" / "hooks" / "post-pr-review.sh",
        REPO_ROOT / ".claude" / "hooks" / "permission-denied-log.sh",
        REPO_ROOT / ".claude" / "hooks" / "scope-drift-guard.sh",
        REPO_ROOT / ".claude" / "hooks" / "post-task-event.sh",
        REPO_ROOT / "scripts" / "internal" / "hooks" / "permission_denied_alert.sh",
    ]
    for caller in callers:
        assert caller.is_file(), f"Missing caller: {caller}"
        text = caller.read_text(encoding="utf-8")
        # The signature pattern that appeared in every duplicate block.
        # After migration, this pattern lives only in the library.
        assert "*steward-author-d)" not in text, (
            f"{caller.name} still carries a duplicate lane-id case "
            f"statement — source lib/resolve-lane-id.sh instead."
        )
