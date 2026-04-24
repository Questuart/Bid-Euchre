"""Unit tests for ``scripts/internal/create_plan_refusal.py``.

Per Primitive C shaping §4.4.1 / §4.4.2 / §4.4.3
(``plans/steward_platform/3_primitive_C/shaping.md``). The shape
requires **exactly four tests** — one per refusal condition R1-R4 —
plus a happy-path test that the refusal does not fire on a clean plan.
This file carries all five tests plus two CLI smoke tests.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "internal" / "create_plan_refusal.py"


def _load_module():
    if "create_plan_refusal" in sys.modules:
        return sys.modules["create_plan_refusal"]
    spec = importlib.util.spec_from_file_location("create_plan_refusal", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["create_plan_refusal"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures — plan bodies for each refusal condition
# ---------------------------------------------------------------------------

_CLEAN_PLAN = """\
# Example Plan

## §2.0 Overview

## §2.1 Work

- §2.1.1 Implement X — delivers feature X
- §2.1.2 Write tests — exercises feature X

## Verification Plan

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance |
|---|---|---|---|---|
| §2.1.1 Implement X | unit-test | tests/unit/test_x.py::test_feature_x | author-b | pytest passes |
| §2.1.2 Write tests | unit-test | tests/unit/test_x.py | author-b | pytest collects ≥1 |
"""

_MISSING_SECTION = """\
# Example Plan

## §2.1 Work

- §2.1.1 Ship a thing

## Summary

No Verification Plan here at all.
"""

_EMPTY_TABLE = """\
# Example Plan

## §2.1 Work

- §2.1.1 Ship a thing

## Verification Plan

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance |
|---|---|---|---|---|
"""

_PLACEHOLDER_ROW = """\
# Example Plan

## §2.1 Work

- §2.1.1 Ship a thing
- §2.1.2 Prove it works

## Verification Plan

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance |
|---|---|---|---|---|
| §2.1.1 Ship a thing | unit-test | tests/unit/test_thing.py | author-b | passes |
| §2.1.2 Prove it works | review | TBD | operator | TBD |
"""

_MISSING_ROW_FOR_BULLET = """\
# Example Plan

## §2.1 Work

- §2.1.1 Implement feature A — must ship

## §3.1 Work

- §3.1.1 An orphan with no verification row

## Verification Plan

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance |
|---|---|---|---|---|
| §2.1.1 Implement feature A | unit-test | tests/unit/test_a.py | author-b | passes |
"""


def _write_plan(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "plan.md"
    target.write_text(body, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_clean_plan_is_not_refused(tmp_path: Path) -> None:
    mod = _load_module()
    path = _write_plan(tmp_path, _CLEAN_PLAN)
    refusals = mod.evaluate_plan(path, repo_root=tmp_path)
    assert refusals == []


# ---------------------------------------------------------------------------
# R1 — missing ## Verification Plan section
# ---------------------------------------------------------------------------


def test_r1_missing_verification_plan_section(tmp_path: Path) -> None:
    mod = _load_module()
    path = _write_plan(tmp_path, _MISSING_SECTION)
    refusals = mod.evaluate_plan(path, repo_root=tmp_path)
    codes = [r.code for r in refusals]
    assert codes == ["R1"]
    assert "Missing `## Verification Plan` section" in refusals[0].fragment


# ---------------------------------------------------------------------------
# R2 — section present but table empty
# ---------------------------------------------------------------------------


def test_r2_empty_table(tmp_path: Path) -> None:
    mod = _load_module()
    path = _write_plan(tmp_path, _EMPTY_TABLE)
    refusals = mod.evaluate_plan(path, repo_root=tmp_path)
    codes = [r.code for r in refusals]
    assert "R2" in codes
    r2 = next(r for r in refusals if r.code == "R2")
    assert "empty (header row only)" in r2.fragment


# ---------------------------------------------------------------------------
# R3 — placeholder token in Verification surface column
# ---------------------------------------------------------------------------


def test_r3_placeholder_token_in_surface(tmp_path: Path) -> None:
    mod = _load_module()
    path = _write_plan(tmp_path, _PLACEHOLDER_ROW)
    refusals = mod.evaluate_plan(path, repo_root=tmp_path)
    codes = [r.code for r in refusals]
    assert "R3" in codes
    r3 = next(r for r in refusals if r.code == "R3")
    assert "placeholder surface" in r3.fragment
    assert "TBD" in r3.fragment


# ---------------------------------------------------------------------------
# R4 — Work bullet without a matching row (or map.md coverage)
# ---------------------------------------------------------------------------


def test_r4_work_bullet_without_row(tmp_path: Path) -> None:
    mod = _load_module()
    path = _write_plan(tmp_path, _MISSING_ROW_FOR_BULLET)
    refusals = mod.evaluate_plan(path, repo_root=tmp_path)
    codes = [r.code for r in refusals]
    assert "R4" in codes, f"expected R4 in {codes}; refusals={refusals}"


# ---------------------------------------------------------------------------
# Message format (§4.4.2 exact format)
# ---------------------------------------------------------------------------


def test_format_refusal_message_matches_spec(tmp_path: Path) -> None:
    mod = _load_module()
    refusals = [
        mod.Refusal("R1", "Missing `## Verification Plan` section"),
        mod.Refusal(
            "R3", "Row for deliverable `§1.2` carries placeholder surface `TBD`"
        ),
    ]
    msg = mod.format_refusal_message(refusals)
    assert msg.startswith(
        "/create-plan REFUSED: Pattern 10 (§10.9) requires a complete Verification Plan section."
    )
    assert "Refusal reasons:" in msg
    assert "  R1: Missing `## Verification Plan` section" in msg
    assert "  R3: Row for deliverable `§1.2` carries placeholder surface `TBD`" in msg
    assert "plans/_templates/sub_plan.md" in msg
    assert "No plan file was written. Fix the above and re-invoke /create-plan." in msg


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_exits_zero_on_clean_plan(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, _CLEAN_PLAN)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--repo-root", str(tmp_path), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_exits_two_on_missing_section(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, _MISSING_SECTION)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--repo-root", str(tmp_path), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "/create-plan REFUSED" in result.stderr
    assert "R1" in result.stderr
