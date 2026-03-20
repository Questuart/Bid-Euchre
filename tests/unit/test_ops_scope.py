"""Tests for ops/scope.py — scope drift detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.scope import (
    ScopeDriftReport,
    _matches_any_pattern,
    check_scope_drift,
    emit_scope_drift_event,
    format_scope_drift_json,
    format_scope_drift_text,
)

# --- Pattern matching ---


class TestMatchesAnyPattern:
    """Tests for _matches_any_pattern()."""

    def test_exact_match(self) -> None:
        assert _matches_any_pattern("src/foo.py", ["src/foo.py"]) is True

    def test_glob_star(self) -> None:
        assert _matches_any_pattern("src/foo.py", ["src/*.py"]) is True

    def test_glob_double_star(self) -> None:
        assert _matches_any_pattern("src/ops/scope.py", ["src/**/*.py"]) is True

    def test_basename_pattern(self) -> None:
        """Pattern without '/' matches against basename."""
        assert _matches_any_pattern("src/ops/scope.py", ["*.py"]) is True

    def test_no_match(self) -> None:
        assert _matches_any_pattern("src/foo.py", ["tests/*.py"]) is False

    def test_multiple_patterns(self) -> None:
        patterns = ["tests/*.py", "src/*.py"]
        assert _matches_any_pattern("src/foo.py", patterns) is True
        assert _matches_any_pattern("tests/test_foo.py", patterns) is True
        assert _matches_any_pattern("docs/readme.md", patterns) is False

    def test_empty_patterns(self) -> None:
        assert _matches_any_pattern("src/foo.py", []) is False

    def test_question_mark_wildcard(self) -> None:
        assert _matches_any_pattern("src/f.py", ["src/?.py"]) is True
        assert _matches_any_pattern("src/foo.py", ["src/?.py"]) is False

    def test_bracket_wildcard(self) -> None:
        assert _matches_any_pattern("src/a.py", ["src/[abc].py"]) is True
        assert _matches_any_pattern("src/d.py", ["src/[abc].py"]) is False


# --- ScopeDriftReport dataclass ---


class TestScopeDriftReport:
    """Tests for ScopeDriftReport properties."""

    def test_has_drift_true(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/foo.py", "docs/readme.md"],
            in_scope=["src/foo.py"],
            out_of_scope=["docs/readme.md"],
        )
        assert report.has_drift is True

    def test_has_drift_false(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/foo.py"],
            in_scope=["src/foo.py"],
            out_of_scope=[],
        )
        assert report.has_drift is False

    def test_drift_ratio_some_drift(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/a.py", "src/b.py", "docs/c.md", "docs/d.md"],
            in_scope=["src/a.py", "src/b.py"],
            out_of_scope=["docs/c.md", "docs/d.md"],
        )
        assert report.drift_ratio == pytest.approx(0.5)

    def test_drift_ratio_no_files(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=[],
            touched_files=[],
            in_scope=[],
            out_of_scope=[],
        )
        assert report.drift_ratio == 0.0

    def test_to_dict(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["*.py"],
            touched_files=["a.py", "b.md"],
            in_scope=["a.py"],
            out_of_scope=["b.md"],
        )
        d = report.to_dict()
        assert d["task_id"] == "t1"
        assert d["has_drift"] is True
        assert d["drift_ratio"] == pytest.approx(0.5)
        # Verify JSON-serializable
        json.dumps(d)


# --- check_scope_drift ---


class TestCheckScopeDrift:
    """Tests for check_scope_drift()."""

    @pytest.fixture()
    def runtime_dir(self, tmp_path: Path) -> Path:
        """Create a runtime dir with task_state directory."""
        rd = tmp_path / "runtime"
        (rd / "task_state").mkdir(parents=True)
        return rd

    def _write_task_state(
        self,
        runtime_dir: Path,
        task_id: str,
        declared: list[str],
        touched: list[str],
    ) -> None:
        """Write a task state file with scope data."""
        state = {
            "task_id": task_id,
            "scope": {
                "declared_files": declared,
                "touched_files": touched,
            },
        }
        state_file = runtime_dir / "task_state" / f"{task_id}.json"
        state_file.write_text(json.dumps(state))

    def test_no_drift(self, runtime_dir: Path) -> None:
        self._write_task_state(
            runtime_dir, "t1", ["src/ops/*.py"], ["src/ops/scope.py"]
        )
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is False
        assert report.in_scope == ["src/ops/scope.py"]
        assert report.out_of_scope == []

    def test_drift_detected(self, runtime_dir: Path) -> None:
        self._write_task_state(
            runtime_dir,
            "t1",
            ["src/ops/*.py"],
            ["src/ops/scope.py", "tests/test_scope.py"],
        )
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is True
        assert "src/ops/scope.py" in report.in_scope
        assert "tests/test_scope.py" in report.out_of_scope

    def test_no_declared_patterns(self, runtime_dir: Path) -> None:
        """No declared scope → all files in-scope (nothing to drift from)."""
        self._write_task_state(runtime_dir, "t1", [], ["src/a.py", "src/b.py"])
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is False
        assert report.in_scope == ["src/a.py", "src/b.py"]

    def test_no_touched_files(self, runtime_dir: Path) -> None:
        self._write_task_state(runtime_dir, "t1", ["src/*.py"], [])
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is False
        assert report.drift_ratio == 0.0

    def test_multiple_patterns(self, runtime_dir: Path) -> None:
        self._write_task_state(
            runtime_dir,
            "t1",
            ["src/ops/*.py", "tests/unit/test_ops_*.py"],
            [
                "src/ops/scope.py",
                "tests/unit/test_ops_scope.py",
                "docs/readme.md",
            ],
        )
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is True
        assert len(report.in_scope) == 2
        assert len(report.out_of_scope) == 1
        assert "docs/readme.md" in report.out_of_scope

    def test_task_not_found_raises(self, runtime_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            check_scope_drift("nonexistent", runtime_dir=runtime_dir)

    def test_no_scope_in_state(self, runtime_dir: Path) -> None:
        """Task state exists but has no scope key → no drift."""
        state_file = runtime_dir / "task_state" / "t1.json"
        state_file.write_text(json.dumps({"task_id": "t1"}))
        report = check_scope_drift("t1", runtime_dir=runtime_dir)
        assert report.has_drift is False


# --- emit_scope_drift_event ---


class TestEmitScopeDriftEvent:
    """Tests for emit_scope_drift_event()."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def test_emits_on_drift(self, events_dir: Path) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/a.py", "docs/b.md"],
            in_scope=["src/a.py"],
            out_of_scope=["docs/b.md"],
        )
        result = emit_scope_drift_event(report, "author-a", events_dir)
        assert result is not None
        assert result["event_type"] == "watchdog_finding"
        assert result["source"] == "ops.scope"
        assert result["lane_id"] == "author-a"
        assert result["payload"]["finding"] == "scope_drift"
        assert result["payload"]["task_id"] == "t1"
        assert result["payload"]["out_of_scope_count"] == 1

    def test_no_event_when_no_drift(self, events_dir: Path) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/a.py"],
            in_scope=["src/a.py"],
            out_of_scope=[],
        )
        result = emit_scope_drift_event(report, "author-a", events_dir)
        assert result is None

    def test_event_persisted_to_jsonl(self, events_dir: Path) -> None:
        """Verify the emitted event is readable from the log."""
        from bid_euchre.ops.events import read_events

        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["docs/b.md"],
            in_scope=[],
            out_of_scope=["docs/b.md"],
        )
        emit_scope_drift_event(report, "author-a", events_dir)

        events = read_events(events_dir)
        assert len(events) == 1
        assert events[0]["event_type"] == "watchdog_finding"
        assert events[0]["payload"]["finding"] == "scope_drift"


# --- Formatters ---


class TestFormatScopeDriftText:
    """Tests for format_scope_drift_text()."""

    def test_no_files(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=[],
            in_scope=[],
            out_of_scope=[],
        )
        text = format_scope_drift_text(report)
        assert "No files touched" in text

    def test_no_declared_scope(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=[],
            touched_files=["a.py"],
            in_scope=["a.py"],
            out_of_scope=[],
        )
        text = format_scope_drift_text(report)
        assert "No declared scope" in text

    def test_drift_detected(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/a.py", "docs/b.md"],
            in_scope=["src/a.py"],
            out_of_scope=["docs/b.md"],
        )
        text = format_scope_drift_text(report)
        assert "DRIFT DETECTED" in text
        assert "docs/b.md" in text

    def test_clean(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["src/*.py"],
            touched_files=["src/a.py"],
            in_scope=["src/a.py"],
            out_of_scope=[],
        )
        text = format_scope_drift_text(report)
        assert "Clean" in text


class TestFormatScopeDriftJSON:
    """Tests for format_scope_drift_json()."""

    def test_serializable(self) -> None:
        report = ScopeDriftReport(
            task_id="t1",
            declared_patterns=["*.py"],
            touched_files=["a.py"],
            in_scope=["a.py"],
            out_of_scope=[],
        )
        d = format_scope_drift_json(report)
        assert d["task_id"] == "t1"
        assert d["has_drift"] is False
        json.dumps(d)
