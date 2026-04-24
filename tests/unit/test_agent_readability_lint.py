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


def test_cli_load_bearing_ownership_clean_tree_exits_clean(tmp_path: Path) -> None:
    """No plan references + no harness_assumptions.md → 0 findings."""
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
    assert rc == 0


# ---------------------------------------------------------------------------
# Pattern 9 — load-bearing-ownership (LBO1 / LBO2 / LBO3)
# ---------------------------------------------------------------------------


class TestPattern9:
    """Tests for concrete Pattern 9 rule set (§4.5.1)."""

    @staticmethod
    def _seed_script(repo_root: Path, relpath: str) -> Path:
        p = repo_root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# stub\n")
        return p

    def test_positive_clean_with_matching_bullet(self, tmp_path: Path) -> None:
        self._seed_script(tmp_path, "scripts/internal/kb_index.py")
        _write_plan(
            tmp_path / "plans" / "x.md",
            """
            # Plan

            ## §5.3 Primitive X

            Details reference `scripts/internal/kb_index.py`.

            ### Work
            - Ship `scripts/internal/kb_index.py` with deterministic regen
            """,
        )
        findings = arl.check_load_bearing_ownership(
            [tmp_path / "plans"], repo_root=tmp_path
        )
        lbo = [f for f in findings if f.rule_id.startswith("LBO")]
        assert lbo == []

    def test_negative_lbo1_in_block_scope_section(self, tmp_path: Path) -> None:
        self._seed_script(tmp_path, "scripts/internal/orphan.py")
        _write_plan(
            tmp_path / "plans" / "x.md",
            """
            # Plan

            ## §5.3 Primitive X

            See `scripts/internal/orphan.py` for details.

            ### Work
            - Do something unrelated
            """,
        )
        findings = arl.check_load_bearing_ownership(
            [tmp_path / "plans"], repo_root=tmp_path
        )
        ids = [f.rule_id for f in findings]
        assert "LBO1" in ids
        # BLOCK severity per §4.5.1.
        lbo1 = [f for f in findings if f.rule_id == "LBO1"]
        assert lbo1[0].severity == arl.Severity.BLOCK

    def test_negative_lbo2_outside_block_scope(self, tmp_path: Path) -> None:
        self._seed_script(tmp_path, "scripts/internal/offpath.py")
        _write_plan(
            tmp_path / "plans" / "x.md",
            """
            # Plan

            ## §9.1 Retrospective

            Incidental reference to `scripts/internal/offpath.py`.

            ### Work
            - Do something unrelated
            """,
        )
        findings = arl.check_load_bearing_ownership(
            [tmp_path / "plans"], repo_root=tmp_path
        )
        lbo2 = [f for f in findings if f.rule_id == "LBO2"]
        assert lbo2, f"expected LBO2 finding; got {[f.rule_id for f in findings]}"
        assert lbo2[0].severity == arl.Severity.WARN

    def test_negative_lbo3_archive_only_reference(self, tmp_path: Path) -> None:
        self._seed_script(tmp_path, "scripts/internal/legacy.py")
        # Reference lives only in an archival draft; walker excludes _archive
        # from bullet collection, but the LBO3 sweep re-visits those paths.
        _write_plan(
            tmp_path / "plans" / "_archive" / "old_draft3.md",
            """
            # Old plan draft

            ## §5.3 Primitive X

            Deep in the draft: `scripts/internal/legacy.py`.

            ### Work
            - legacy stuff
            """,
        )
        # Also walk the archive dir explicitly so the sweep sees it.
        findings = arl.check_load_bearing_ownership(
            [tmp_path / "plans" / "_archive"], repo_root=tmp_path
        )
        # Archive-only references produce LBO3 (the LBO1/LBO2 sweep skips
        # archive files via `_is_archive_reference`).
        lbo3 = [f for f in findings if f.rule_id == "LBO3"]
        assert lbo3, f"expected LBO3 finding; got {[f.rule_id for f in findings]}"
        assert lbo3[0].severity == arl.Severity.WARN


# ---------------------------------------------------------------------------
# Pattern 9 — HA1 brittleness-signal machine-observable check
# ---------------------------------------------------------------------------


class TestHA1:
    """Tests for HA1 (harness-assumption signal must be machine-observable)."""

    def test_ha1_passes_on_backtick_grep_pattern(self, tmp_path: Path) -> None:
        ha = tmp_path / "knowledge" / "harness_assumptions.md"
        ha.parent.mkdir(parents=True, exist_ok=True)
        ha.write_text(
            "# Harness assumptions\n\n"
            "### Example\n\n"
            "**Assumption:** x\n"
            "**Observation:** y\n"
            "**Brittleness signal:** `grep foo bar`\n"
            "**Refresh trigger:** on upgrade\n",
            encoding="utf-8",
        )
        findings = arl._check_harness_assumptions(tmp_path, [])
        assert [f for f in findings if f.rule_id == "HA1"] == []

    def test_ha1_fires_on_natural_language_signal(self, tmp_path: Path) -> None:
        ha = tmp_path / "knowledge" / "harness_assumptions.md"
        ha.parent.mkdir(parents=True, exist_ok=True)
        ha.write_text(
            "# Harness assumptions\n\n"
            "### Vague Entry\n\n"
            "**Assumption:** x\n"
            "**Observation:** y\n"
            "**Brittleness signal:** it feels wrong when the fleet gets slow\n"
            "**Refresh trigger:** on upgrade\n",
            encoding="utf-8",
        )
        findings = arl._check_harness_assumptions(tmp_path, [])
        ha1 = [f for f in findings if f.rule_id == "HA1"]
        assert ha1, "HA1 should fire on natural-language-only signal"
        assert ha1[0].severity == arl.Severity.WARN

    def test_ha1_passes_on_make_target(self, tmp_path: Path) -> None:
        ha = tmp_path / "knowledge" / "harness_assumptions.md"
        ha.parent.mkdir(parents=True, exist_ok=True)
        ha.write_text(
            "# Harness assumptions\n\n"
            "### Example\n\n"
            "**Assumption:** x\n"
            "**Observation:** y\n"
            "**Brittleness signal:** make check-gated exits 0\n"
            "**Refresh trigger:** on upgrade\n",
            encoding="utf-8",
        )
        findings = arl._check_harness_assumptions(tmp_path, [])
        assert [f for f in findings if f.rule_id == "HA1"] == []

    def test_ha1_passes_on_hook_reference(self, tmp_path: Path) -> None:
        ha = tmp_path / "knowledge" / "harness_assumptions.md"
        ha.parent.mkdir(parents=True, exist_ok=True)
        ha.write_text(
            "# Harness assumptions\n\n"
            "### Example\n\n"
            "**Assumption:** x\n"
            "**Observation:** y\n"
            "**Brittleness signal:** .claude/hooks/post-merge-notify.sh exits non-zero\n"
            "**Refresh trigger:** on upgrade\n",
            encoding="utf-8",
        )
        findings = arl._check_harness_assumptions(tmp_path, [])
        assert [f for f in findings if f.rule_id == "HA1"] == []


# ---------------------------------------------------------------------------
# Pattern 11 — shape-then-execute dispatch
# ---------------------------------------------------------------------------


class TestPattern11:
    """Tests for concrete Pattern 11 rule set (§4.5.2)."""

    def test_positive_shaping_md_present(self, tmp_path: Path) -> None:
        prim = tmp_path / "plans" / "steward_platform" / "3_primitive_C"
        prim.mkdir(parents=True)
        (prim / "shaping.md").write_text("# Shaping doc\n", encoding="utf-8")
        findings = arl.check_pattern_11([tmp_path / "plans"], repo_root=tmp_path)
        p11_1 = [f for f in findings if f.rule_id == "P11_1"]
        assert p11_1 == []

    def test_negative_p11_1_missing_shaping(self, tmp_path: Path) -> None:
        prim = tmp_path / "plans" / "steward_platform" / "3_primitive_C"
        prim.mkdir(parents=True)
        # No shaping.md written.
        (prim / "something.md").write_text("# Not shaping\n", encoding="utf-8")
        findings = arl.check_pattern_11([tmp_path / "plans"], repo_root=tmp_path)
        p11_1 = [f for f in findings if f.rule_id == "P11_1"]
        assert p11_1, f"expected P11_1; got {[f.rule_id for f in findings]}"
        assert p11_1[0].severity == arl.Severity.BLOCK

    def test_p11_3_fires_on_orphan_packet_reference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prim = tmp_path / "plans" / "steward_platform" / "3_primitive_C"
        prim.mkdir(parents=True)
        (prim / "shaping.md").write_text(
            "# Shaping\n\nPacket abcd1234 executes this shape.\n",
            encoding="utf-8",
        )

        # Monkey-patch subprocess.run inside the module to return "no match".
        import subprocess as sp

        class _FakeResult:
            def __init__(self):
                self.returncode = 1
                self.stdout = ""
                self.stderr = ""

        def _fake_run(*_args, **_kwargs):
            return _FakeResult()

        monkeypatch.setattr(sp, "run", _fake_run)
        findings = arl.check_pattern_11([tmp_path / "plans"], repo_root=tmp_path)
        p11_3 = [f for f in findings if f.rule_id == "P11_3"]
        assert p11_3, f"expected P11_3; got {[f.rule_id for f in findings]}"
        assert p11_3[0].severity == arl.Severity.WARN


# ---------------------------------------------------------------------------
# Plan-walker isolation (§4.5.3 shared-module discipline)
# ---------------------------------------------------------------------------


class TestPlanWalker:
    """Tests the shared plan-walker core independently of rule sets.

    Per §4.5.3 of Primitive C shaping: walker tests must pass independently
    of Pattern 9/10/11 rule-set tests. These tests exercise only
    ``walk_plans()`` and its dataclasses — no rule-set code paths.
    """

    def test_walk_returns_plan_walk(self, tmp_path: Path) -> None:
        _write_plan(
            tmp_path / "plans" / "x.md",
            """
            ## §1.1 Example

            ### Work
            - item one
            """,
        )
        walk = arl.walk_plans([tmp_path / "plans"])
        assert isinstance(walk, arl.PlanWalk)
        assert walk.deliverables
        assert len(walk.plans_walked) == 1

    def test_walk_dataclasses_populated(self, tmp_path: Path) -> None:
        _write_plan(
            tmp_path / "plans" / "p.md",
            """
            ## §2.0 Root

            ### Work
            - do X

            ## Verification Plan

            | Deliverable | Class | Verification surface | Owner | Acceptance |
            |---|---|---|---|---|
            | §2.0 do X | script | unit | author | test |
            """,
        )
        walk = arl.walk_plans([tmp_path / "plans"])
        # Deliverables: at least one bullet under a Work heading.
        assert any(isinstance(d, arl.DeliverableBullet) for d in walk.deliverables)
        # Verification rows: at least one row parsed.
        assert any(isinstance(r, arl.VerificationRow) for r in walk.verification_rows)

    def test_walker_isolation_does_not_invoke_rules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shared-module guard: walk_plans() must never call rule-set code."""
        _write_plan(
            tmp_path / "plans" / "p.md",
            """
            ## §3.0 Section

            ### Work
            - some item
            """,
        )

        # Tripwire: replace the rule-set functions with a poison pill.
        def _poison(*_a, **_kw):  # pragma: no cover - should not be called
            raise AssertionError("walker must not invoke rule-set functions")

        monkeypatch.setattr(arl, "check_verification_contract", _poison)
        monkeypatch.setattr(arl, "check_load_bearing_ownership", _poison)
        monkeypatch.setattr(arl, "check_pattern_11", _poison)
        # walk_plans should not touch any of them.
        walk = arl.walk_plans([tmp_path / "plans"])
        assert walk.deliverables


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
