"""Tests for deterministic_prechecks.py — precheck detection with seeded fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from deterministic_prechecks import (
    Finding,
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
