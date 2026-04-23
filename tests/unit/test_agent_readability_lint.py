"""Unit tests for scripts/internal/agent_readability_lint.py.

Covers the shared plan-walker core and the two rule-set sub-commands
(verification-contract, load-bearing-ownership). Fixtures are inline and
seeded so the test is hermetic.

Pattern 10 — see ``plans/steward_platform/governing_plan.md`` §10.9 and
``plans/steward_platform/verification_contract/shaping.md`` §3.2(iii).
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "agent_readability_lint",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "agent_readability_lint.py",
)
assert _SPEC is not None and _SPEC.loader is not None
arl = importlib.util.module_from_spec(_SPEC)
sys.modules["agent_readability_lint"] = arl
_SPEC.loader.exec_module(arl)


def _write_plan(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"))
    return path


# ---------------------------------------------------------------------------
# Plan-walker core
# ---------------------------------------------------------------------------


def test_walker_finds_work_bullets(tmp_path: Path) -> None:
    p = _write_plan(
        tmp_path / "plans" / "x.md",
        """
        # Plan

        ## §5.3 Primitive X

        ### Work

        - Ship `src/foo.py`
        - Ship `src/bar.py`

        ### Readiness

        - `tests/unit/test_foo.py` passes
        """,
    )
    walk = arl.walk_plans([p.parent])
    assert p in walk.plans_walked
    section_nums = sorted({b.section_num for b in walk.deliverables})
    assert section_nums == ["5.3"]
    texts = {b.bullet_text for b in walk.deliverables}
    assert any("src/foo.py" in t for t in texts)
    assert any("test_foo.py" in t for t in texts)


def test_walker_parses_verification_plan_rows(tmp_path: Path) -> None:
    p = _write_plan(
        tmp_path / "plans" / "y.md",
        """
        ## §5.3 Primitive X

        ### Work

        - Ship `src/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `src/foo.py` | new Python module | `tests/unit/test_foo.py` | author | pytest passes |
        """,
    )
    walk = arl.walk_plans([p.parent])
    assert len(walk.verification_rows) == 1
    row = walk.verification_rows[0]
    assert row.deliverable.startswith("§5.3")
    assert "tests/unit/test_foo.py" in row.surface


def test_walker_skips_archive_dirs(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "_archive" / "old.md",
        """
        ## §1.1 Old

        ### Work
        - `src/old.py`
        """,
    )
    keep = _write_plan(
        tmp_path / "plans" / "live.md",
        """
        ## §2.1 Live

        ### Work
        - `src/live.py`
        """,
    )
    walk = arl.walk_plans([tmp_path / "plans"])
    paths = {p for p in walk.plans_walked}
    assert keep in paths
    # Check that _archive appears as a path *component* (directory),
    # not as a substring of ancestor dirs (e.g. pytest tmp_path).
    assert not any("_archive" in p.parts for p in paths)


# ---------------------------------------------------------------------------
# check verification-contract — rule VC1/VC2 (Verification Plan row sanity)
# ---------------------------------------------------------------------------


def test_vc1_flags_empty_surface(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `src/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `src/foo.py` | new module | — | author | pytest |
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    rule_ids = {f.rule_id for f in findings}
    assert "VC1" in rule_ids
    assert all(f.severity == arl.Severity.BLOCK for f in findings if f.rule_id == "VC1")


@pytest.mark.parametrize("token", ["TBD", "TODO", "FIXME", "XXX"])
def test_vc2_flags_placeholder_surface(tmp_path: Path, token: str) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        f"""
        ## §5.3 X

        ### Work
        - Ship `src/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `src/foo.py` | new module | {token} | author | pytest |
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    vc2 = [f for f in findings if f.rule_id == "VC2"]
    assert vc2, f"expected VC2 finding for token {token}"
    assert all(f.severity == arl.Severity.BLOCK for f in vc2)


def test_vc1_vc2_silent_when_surface_concrete(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `src/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `src/foo.py` | new module | tests/unit/test_foo.py | author | pytest passes |
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    assert not any(f.rule_id in {"VC1", "VC2"} for f in findings)


# ---------------------------------------------------------------------------
# check verification-contract — rule VC3 (coverage of Work/Readiness bullets)
# ---------------------------------------------------------------------------


def test_vc3_warns_on_uncovered_bullet(tmp_path: Path) -> None:
    # Bullet present in Work, no Verification Plan section, no global map.
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `scripts/foo.py`
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    vc3 = [f for f in findings if f.rule_id == "VC3"]
    assert vc3, "expected VC3 for uncovered bullet"
    assert all(f.severity == arl.Severity.WARN for f in vc3)


def test_vc3_satisfied_by_local_verification_plan(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `scripts/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `scripts/foo.py` | new script | tests/unit/test_foo.py | author | pytest |
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    assert not any(f.rule_id == "VC3" for f in findings)


def test_vc3_satisfied_by_global_map(tmp_path: Path) -> None:
    # Plan with a Work bullet but no local Verification Plan; global map
    # carries the row.
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `scripts/foo.py`
        """,
    )
    _write_plan(
        tmp_path / "plans" / "steward_platform" / "verification_contract" / "map.md",
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `scripts/foo.py` | new script | tests/unit/test_foo.py | author | pytest |
        """,
    )
    findings = arl.check_verification_contract([tmp_path / "plans"], repo_root=tmp_path)
    assert not any(f.rule_id == "VC3" for f in findings)


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_exit_zero_on_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_plan(
        tmp_path / "plans" / "clean.md",
        """
        ## §1.1 Just prose

        Nothing here to verify.
        """,
    )
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "verification-contract",
            str(tmp_path / "plans"),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 findings" in out


def test_cli_exit_two_on_block_finding(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `src/foo.py`

        ## Verification Plan

        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | §5.3 `src/foo.py` | new module | TBD | author | pytest |
        """,
    )
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "verification-contract",
            str(tmp_path / "plans"),
        ]
    )
    assert rc == 2


def test_cli_warnings_ok_passes_warns(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - Ship `scripts/foo.py`
        """,
    )
    # Default: WARN triggers exit 2.
    rc_strict = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "verification-contract",
            str(tmp_path / "plans"),
        ]
    )
    assert rc_strict == 2
    # With --warnings-ok: exit 0.
    rc_relaxed = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "--warnings-ok",
            "check",
            "verification-contract",
            str(tmp_path / "plans"),
        ]
    )
    assert rc_relaxed == 0


def test_cli_exit_one_on_missing_path(tmp_path: Path) -> None:
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "verification-contract",
            str(tmp_path / "does_not_exist"),
        ]
    )
    assert rc == 1


def test_cli_load_bearing_ownership_scaffold_exits_clean(tmp_path: Path) -> None:
    _write_plan(
        tmp_path / "plans" / "x.md",
        """
        ## §5.3 X

        ### Work
        - anything
        """,
    )
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "load-bearing-ownership",
            str(tmp_path / "plans"),
        ]
    )
    # Scaffold: no findings until the Pattern 9 rule set lands.
    assert rc == 0


# ---------------------------------------------------------------------------
# Self-run: the live plans/steward_platform/ tree must be clean at Packet 2b
# merge time (per shaping §11.2 step 9). We run the check as a smoke test.
# ---------------------------------------------------------------------------


def test_live_steward_platform_tree_is_clean() -> None:
    """Regression guard: Pattern 10 lint exits clean against the live tree.

    This is the §11.2 step-9 self-run check. If this test fails, a plan
    authored post-Pattern 10 has drifted off-contract; fix the plan or
    adjust the walker's heuristics (not the test).
    """
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "plans" / "steward_platform"
    if not target.exists():
        pytest.skip(f"steward_platform tree not found at {target}")
    findings = arl.check_verification_contract([target], repo_root=repo_root)
    blocks = [f for f in findings if f.severity == arl.Severity.BLOCK]
    assert not blocks, "BLOCK findings:\n" + "\n".join(f.format_line() for f in blocks)
