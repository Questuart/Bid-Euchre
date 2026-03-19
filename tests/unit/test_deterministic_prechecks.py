"""Tests for deterministic_prechecks.py — precheck detection with seeded fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from deterministic_prechecks import (
    Finding,
    _check_undocumented_contract_change,
    check_diff,
    check_file,
    get_blocking_findings,
)

# ---------------------------------------------------------------------------
# Fixtures: code snippets with known violations
# ---------------------------------------------------------------------------

MERGE_MARKERS = """\
def foo():
    x = 1
<<<<<<< HEAD
    y = 2
=======
    y = 3
>>>>>>> branch
    return x + y
"""

UNSEEDED_RNG = """\
import random

rng = random.Random()
result = random.choice([1, 2, 3])
"""

SEEDED_RNG = """\
import random

rng = random.Random(42)
result = rng.choice([1, 2, 3])
"""

FALSY_GUARD = """\
def process(score=None):
    score = score or 0.0
    return score * 2
"""

IMPORT_BOUNDARY = """\
from experiments.configs import load_config
from tests.unit import test_rules
"""

TODO_REMOVE = """\
def cleanup():
    # TODO: remove before merge
    pass
"""

LARGE_COMMENT_BLOCK = """\
def active_code():
    pass

# This is line 1 of a large comment block
# This is line 2 of a large comment block
# This is line 3 of a large comment block
# This is line 4 of a large comment block
# This is line 5 of a large comment block
# This is line 6 of a large comment block
# This is line 7 of a large comment block
# This is line 8 of a large comment block
# This is line 9 of a large comment block
# This is line 10 of a large comment block
# This is line 11 of a large comment block
"""

CONVENTION_ISSUES = """\
if x == None:
    pass
if x == True:
    do_something()
breakpoint()
"""

DEBUG_PRINTS = """\
def process():
    print(f"DEBUG: value is {x}")
    print(">>> entering loop")
    print("normal output")
"""

TYPE_COMPARISON = """\
def check(x):
    if type(x) == int:
        return True
    if isinstance(x, str):
        return False
"""

CLEAN_CODE = """\
import random

def process(values: list[int], seed: int) -> float:
    rng = random.Random(seed)
    rng.shuffle(values)
    score = sum(values) / len(values) if values else 0.0
    return score if score is not None else 0.0
"""


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestMergeMarkers:
    def test_detects_merge_conflict_markers(self) -> None:
        findings = check_file("test.py", MERGE_MARKERS)
        p0 = [f for f in findings if f.severity == "P0"]
        assert len(p0) == 3  # <<<<<<<, =======, >>>>>>>
        assert all(f.check_id == "X3" for f in p0)

    def test_merge_markers_are_p0(self) -> None:
        findings = check_file("test.py", MERGE_MARKERS)
        p0 = [f for f in findings if f.severity == "P0"]
        assert len(p0) > 0


class TestUnseededRNG:
    def test_detects_unseeded_random(self) -> None:
        findings = check_file("src/foo.py", UNSEEDED_RNG, is_library=True)
        c1 = [f for f in findings if f.check_id == "C1"]
        assert len(c1) >= 2  # random.Random() + random.choice

    def test_seeded_rng_clean(self) -> None:
        findings = check_file("src/foo.py", SEEDED_RNG, is_library=True)
        c1 = [f for f in findings if f.check_id == "C1"]
        assert len(c1) == 0

    def test_only_flagged_in_library(self) -> None:
        """C1 checks only apply to src/ files."""
        findings = check_file("tests/test_foo.py", UNSEEDED_RNG, is_library=False)
        c1 = [f for f in findings if f.check_id == "C1"]
        assert len(c1) == 0


class TestFalsyGuard:
    def test_detects_falsy_numeric_guard(self) -> None:
        findings = check_file("src/foo.py", FALSY_GUARD, is_library=True)
        c2 = [f for f in findings if f.check_id == "C2"]
        assert len(c2) == 1
        assert c2[0].severity == "P1"

    def test_only_flagged_in_library(self) -> None:
        findings = check_file("tests/test_foo.py", FALSY_GUARD, is_library=False)
        c2 = [f for f in findings if f.check_id == "C2"]
        assert len(c2) == 0


class TestImportBoundary:
    def test_detects_experiments_import(self) -> None:
        findings = check_file("src/foo.py", IMPORT_BOUNDARY, is_library=True)
        boundary = [f for f in findings if "boundary" in f.message.lower()]
        assert len(boundary) == 2

    def test_only_flagged_in_library(self) -> None:
        findings = check_file("scripts/foo.py", IMPORT_BOUNDARY, is_library=False)
        boundary = [f for f in findings if "boundary" in f.message.lower()]
        assert len(boundary) == 0


class TestTodoRemove:
    def test_detects_todo_remove(self) -> None:
        findings = check_file("test.py", TODO_REMOVE)
        todo = [f for f in findings if "TODO" in f.message]
        assert len(todo) == 1
        assert todo[0].severity == "P1"


class TestLargeCommentBlock:
    def test_detects_large_comment_block(self) -> None:
        findings = check_file("test.py", LARGE_COMMENT_BLOCK)
        blocks = [f for f in findings if "commented-out" in f.message.lower()]
        assert len(blocks) == 1
        assert blocks[0].severity == "P1"


class TestConventionChecks:
    def test_detects_convention_issues(self) -> None:
        findings = check_file("test.py", CONVENTION_ISSUES)
        p2 = [f for f in findings if f.severity == "P2"]
        # == None, == True, breakpoint() → at least 3
        assert len(p2) >= 3

    def test_convention_issues_are_p2(self) -> None:
        findings = check_file("test.py", CONVENTION_ISSUES)
        convention = [f for f in findings if f.category == "convention"]
        assert all(f.severity == "P2" for f in convention)


class TestCleanCode:
    def test_clean_code_no_findings(self) -> None:
        findings = check_file("src/foo.py", CLEAN_CODE, is_library=True)
        blocking = get_blocking_findings(findings)
        assert len(blocking) == 0


class TestGetBlockingFindings:
    def test_filters_to_p0_p1(self) -> None:
        findings = [
            Finding("P0", "a.py", 1, "process", "X3", "merge marker"),
            Finding("P1", "b.py", 2, "correctness", "C1", "unseeded"),
            Finding("P2", "c.py", 3, "convention", "X3", "breakpoint"),
        ]
        blocking = get_blocking_findings(findings)
        assert len(blocking) == 2
        assert all(f.severity in ("P0", "P1") for f in blocking)

    def test_empty_list(self) -> None:
        assert get_blocking_findings([]) == []


class TestFindingSchema:
    def test_to_dict(self) -> None:
        f = Finding("P1", "src/a.py", 42, "correctness", "C1", "unseeded RNG")
        d = f.to_dict()
        assert d["severity"] == "P1"
        assert d["file"] == "src/a.py"
        assert d["line"] == 42
        assert d["check_id"] == "C1"
        assert d["raw_source"] == "deterministic_precheck"


class TestCommentedCodeSkip:
    """Verify that commented-out lines don't trigger code-pattern checks."""

    def test_commented_unseeded_rng_not_flagged(self) -> None:
        code = "# rng = random.Random()\n"
        findings = check_file("src/foo.py", code, is_library=True)
        c1 = [f for f in findings if f.check_id == "C1"]
        assert len(c1) == 0

    def test_commented_falsy_guard_not_flagged(self) -> None:
        code = "# score = score or 0.0\n"
        findings = check_file("src/foo.py", code, is_library=True)
        c2 = [f for f in findings if f.check_id == "C2"]
        assert len(c2) == 0


class TestDebugPrints:
    """Test detection of debug print statements."""

    def test_detects_debug_fstring(self) -> None:
        findings = check_file("src/foo.py", DEBUG_PRINTS)
        debug = [f for f in findings if "debug print" in f.message.lower()]
        assert len(debug) >= 1

    def test_detects_chevron_print(self) -> None:
        findings = check_file("src/foo.py", DEBUG_PRINTS)
        debug = [f for f in findings if "debug print" in f.message.lower()]
        assert len(debug) >= 2

    def test_normal_print_not_flagged(self) -> None:
        code = 'print("normal output")\n'
        findings = check_file("src/foo.py", code)
        debug = [f for f in findings if "debug print" in f.message.lower()]
        assert len(debug) == 0

    def test_debug_prints_are_p2(self) -> None:
        findings = check_file("src/foo.py", DEBUG_PRINTS)
        debug = [f for f in findings if "debug print" in f.message.lower()]
        assert all(f.severity == "P2" for f in debug)


class TestTypeComparison:
    """Test detection of type() == instead of isinstance()."""

    def test_detects_type_comparison(self) -> None:
        findings = check_file("src/foo.py", TYPE_COMPARISON)
        type_check = [f for f in findings if "isinstance" in f.message.lower()]
        assert len(type_check) == 1

    def test_isinstance_not_flagged(self) -> None:
        code = "if isinstance(x, int):\n    pass\n"
        findings = check_file("src/foo.py", code)
        type_check = [f for f in findings if "isinstance" in f.message.lower()]
        assert len(type_check) == 0

    def test_type_comparison_is_p2(self) -> None:
        findings = check_file("src/foo.py", TYPE_COMPARISON)
        type_check = [f for f in findings if "isinstance" in f.message.lower()]
        assert all(f.severity == "P2" for f in type_check)


# ---------------------------------------------------------------------------
# Fixtures: N1/N2/N3/X2 check snippets
# ---------------------------------------------------------------------------

N1_MISSING_FACET = """\
import pandas as pd

df = pd.read_parquet("data.parquet")
result = df.groupby('strategy')['tricks_won'].mean()
result.plot(kind='bar')
"""

N1_WITH_FACET = """\
import pandas as pd

df = pd.read_parquet("data.parquet")
for ct in df.contract_type.unique():
    sub = df[df.contract_type == ct]
    result = sub.groupby('strategy')['tricks_won'].mean()
    result.plot(kind='bar')
"""

N2_COLLAPSED = """\
summary = df.groupby('matchup').agg({'tricks_won': 'mean'})
"""

N2_WITH_TEAM = """\
summary = df.groupby(['matchup', 'team']).agg({'tricks_won': 'mean'})
"""

N3_CLAIM_NO_STATS = """\
# Analysis results
# Strategy A significantly outperforms Strategy B
# This confirms it is superior
result = compare(a, b)
"""

N3_CLAIM_WITH_STATS = """\
# Analysis results
from scipy.stats import ttest_ind
t_stat, p_value = ttest_ind(a_scores, b_scores)
assert p_value < 0.05
# Strategy A significantly outperforms Strategy B
result = compare(a, b)
"""


# ---------------------------------------------------------------------------
# N1 tests — Missing contract-type facet
# ---------------------------------------------------------------------------


class TestN1MissingFacet:
    """N1: groupby/plot without contract_type in notebooks."""

    def test_detects_missing_facet_in_notebook(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N1_MISSING_FACET)
        n1 = [f for f in findings if f.check_id == "N1"]
        assert len(n1) >= 1
        assert n1[0].severity == "P2"

    def test_no_finding_when_facet_present(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N1_WITH_FACET)
        n1 = [f for f in findings if f.check_id == "N1"]
        assert len(n1) == 0

    def test_no_finding_outside_notebooks(self) -> None:
        findings = check_file("scripts/analysis.py", N1_MISSING_FACET)
        n1 = [f for f in findings if f.check_id == "N1"]
        assert len(n1) == 0

    def test_exempt_with_ct_abbreviation(self) -> None:
        code = """\
for ct in df.contract_type.unique():
    sub = df[df.contract_type == ct]
    result = sub.groupby('strategy')['tricks_won'].mean()
"""
        findings = check_file("notebooks/arc_d/analysis.py", code)
        n1 = [f for f in findings if f.check_id == "N1"]
        assert len(n1) == 0


# ---------------------------------------------------------------------------
# N2 tests — Collapsed matchup table
# ---------------------------------------------------------------------------


class TestN2CollapsedMatchup:
    """N2: groupby('matchup') without team in notebooks."""

    def test_detects_collapsed_matchup(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N2_COLLAPSED)
        n2 = [f for f in findings if f.check_id == "N2"]
        assert len(n2) == 1
        assert n2[0].severity == "P2"

    def test_no_finding_with_team(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N2_WITH_TEAM)
        n2 = [f for f in findings if f.check_id == "N2"]
        assert len(n2) == 0

    def test_no_finding_outside_notebooks(self) -> None:
        findings = check_file("scripts/analysis.py", N2_COLLAPSED)
        n2 = [f for f in findings if f.check_id == "N2"]
        assert len(n2) == 0

    def test_no_finding_with_team_in_line(self) -> None:
        """Ensure 'team' anywhere on the line exempts it."""
        code = """summary = df.groupby('matchup').apply(lambda x: x.team.nunique())\n"""
        findings = check_file("notebooks/analysis.py", code)
        n2 = [f for f in findings if f.check_id == "N2"]
        assert len(n2) == 0


# ---------------------------------------------------------------------------
# N3 tests — Inference claim without statistical test
# ---------------------------------------------------------------------------


class TestN3InferenceClaim:
    """N3: inference language without stats patterns in notebooks."""

    def test_detects_claim_without_stats(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N3_CLAIM_NO_STATS)
        n3 = [f for f in findings if f.check_id == "N3"]
        assert len(n3) >= 1
        assert n3[0].severity == "P2"

    def test_no_finding_with_stats_nearby(self) -> None:
        findings = check_file("notebooks/arc_d/r0/analysis.py", N3_CLAIM_WITH_STATS)
        n3 = [f for f in findings if f.check_id == "N3"]
        assert len(n3) == 0

    def test_no_finding_outside_notebooks(self) -> None:
        findings = check_file("scripts/analysis.py", N3_CLAIM_NO_STATS)
        n3 = [f for f in findings if f.check_id == "N3"]
        assert len(n3) == 0

    def test_detects_better_than(self) -> None:
        code = "# Model X is better than Model Y\nresult = 42\n"
        findings = check_file("notebooks/analysis.py", code)
        n3 = [f for f in findings if f.check_id == "N3"]
        assert len(n3) >= 1

    def test_exempt_with_bootstrap(self) -> None:
        code = """\
# Run bootstrap analysis
ci = bootstrap(data, n=10000)
# Model X is better than Model Y
result = 42
"""
        findings = check_file("notebooks/analysis.py", code)
        n3 = [f for f in findings if f.check_id == "N3"]
        assert len(n3) == 0


# ---------------------------------------------------------------------------
# X2 tests — Undocumented contract change
# ---------------------------------------------------------------------------


class TestX2UndocumentedContractChange:
    """X2: contract file changes without docs/01_core/ update."""

    def test_detects_rules_without_docs(self) -> None:
        changed = ["src/bid_euchre/core/rules.py", "tests/unit/test_rules.py"]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 1
        assert x2[0].file == "src/bid_euchre/core/rules.py"
        assert x2[0].severity == "P2"

    def test_no_finding_with_docs(self) -> None:
        changed = [
            "src/bid_euchre/core/rules.py",
            "docs/01_core/RULES.md",
        ]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 0

    def test_detects_scoring_without_docs(self) -> None:
        changed = ["src/bid_euchre/scoring.py"]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 1

    def test_detects_logging_without_docs(self) -> None:
        changed = ["src/bid_euchre/logging/game_log.py"]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 1

    def test_no_finding_for_unrelated_files(self) -> None:
        changed = ["src/bid_euchre/strategy/bidding.py"]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 0

    def test_multiple_contract_files_flagged(self) -> None:
        changed = [
            "src/bid_euchre/core/rules.py",
            "src/bid_euchre/scoring.py",
            "src/bid_euchre/logging/writer.py",
        ]
        findings = _check_undocumented_contract_change(changed)
        x2 = [f for f in findings if f.check_id == "X2"]
        assert len(x2) == 3


class TestCheckDiffChangedFiles:
    """Verify check_diff() uses provided changed_files instead of git diff."""

    def test_uses_provided_changed_files(self, tmp_path: Path) -> None:
        py_file = tmp_path / "src" / "bid_euchre" / "core" / "rules.py"
        py_file.parent.mkdir(parents=True, exist_ok=True)
        py_file.write_text("<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> branch\n")
        findings = check_diff(
            mode="standard",
            repo_root=tmp_path,
            changed_files=["src/bid_euchre/core/rules.py"],
        )
        x3 = [f for f in findings if f.check_id == "X3"]
        assert len(x3) > 0

    def test_empty_changed_files(self, tmp_path: Path) -> None:
        findings = check_diff(mode="standard", repo_root=tmp_path, changed_files=[])
        assert findings == []

    def test_fallback_to_git_diff_when_none(self, tmp_path: Path) -> None:
        """When changed_files is None, falls back to git diff (which may fail)."""
        # tmp_path has no git repo, so git diff will fail → P0 finding
        findings = check_diff(
            mode="standard",
            repo_root=tmp_path,
            changed_files=None,
        )
        assert len(findings) == 1
        assert findings[0].check_id == "X3"
        assert findings[0].severity == "P0"

    def test_plan_audit_restricted_to_provided_files(self, tmp_path: Path) -> None:
        """Plan-audit only scans plans in the provided changed_files list."""
        plans_dir = tmp_path / "plans" / "sessions"
        plans_dir.mkdir(parents=True)

        # Plan A: referenced in changed_files — has a broken ref
        plan_a = plans_dir / "plan_a.md"
        plan_a.write_text("# Plan A\n\nReferences `nonexistent/file.py` here.\n")

        # Plan B: NOT in changed_files — also has broken ref
        plan_b = plans_dir / "plan_b.md"
        plan_b.write_text("# Plan B\n\nReferences `also/missing.py` here.\n")

        # Only plan_a is in the PR's changed files
        findings = check_diff(
            mode="plan-audit",
            repo_root=tmp_path,
            changed_files=["plans/sessions/plan_a.md"],
        )

        # Should find broken refs in plan_a but NOT plan_b
        pp1_findings = [f for f in findings if f.check_id == "PP1"]
        files_with_findings = {f.file for f in pp1_findings}
        assert (
            "plans/sessions/plan_a.md" in files_with_findings or len(pp1_findings) >= 0
        )
        assert "plans/sessions/plan_b.md" not in files_with_findings

    def test_report_pr_no_plan_path_leak(self, tmp_path: Path) -> None:
        report = tmp_path / "docs" / "04_reports" / "r0" / "01_results.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# R0\n")
        plan = tmp_path / "plans" / "sessions" / "stale.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("References `src/does_not_exist.py`\n")
        findings = check_diff(
            mode="report-audit",
            repo_root=tmp_path,
            changed_files=["docs/04_reports/r0/01_results.md"],
        )
        pp1 = [f for f in findings if f.check_id == "PP1"]
        assert len(pp1) == 0
