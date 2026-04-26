"""Tests for ops/scope.py — scope drift detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.scope import (
    ScopeDriftReport,
    ScopeEnforcementResult,
    _matches_any_pattern,
    check_scope_drift,
    emit_scope_drift_event,
    enforce_scope_drift,
    format_scope_drift_json,
    format_scope_drift_text,
    get_active_task_scope,
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

    def test_double_star_direct_child(self) -> None:
        """'src/**/*.py' should match direct children like 'src/a.py'."""
        assert _matches_any_pattern("src/a.py", ["src/**/*.py"]) is True

    def test_double_star_nested_child(self) -> None:
        """'src/**/*.py' should still match nested children."""
        assert _matches_any_pattern("src/ops/scope.py", ["src/**/*.py"]) is True

    def test_double_star_no_false_positive(self) -> None:
        """'src/**/*.py' should not match files outside the prefix."""
        assert _matches_any_pattern("tests/a.py", ["src/**/*.py"]) is False

    def test_double_star_multiple_levels(self) -> None:
        """'**/*.py' should match any .py file at any depth."""
        assert _matches_any_pattern("src/ops/deep/file.py", ["**/*.py"]) is True
        assert _matches_any_pattern("file.py", ["**/*.py"]) is True

    def test_annotated_pattern_matches(self) -> None:
        """Guard-time strip: annotated legacy pattern still matches a conforming path."""
        assert _matches_any_pattern("src/foo/bar.py", ["src/foo/*.py (READ)"]) is True

    def test_annotated_pattern_no_false_positive(self) -> None:
        """Guard-time strip: annotated pattern does not match an out-of-scope path."""
        assert (
            _matches_any_pattern("tests/foo/bar.py", ["src/foo/*.py (READ)"]) is False
        )


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


# --- Enforcement ---


class TestScopeEnforcementResult:
    """Tests for ScopeEnforcementResult dataclass."""

    def test_to_dict_serializable(self) -> None:
        result = ScopeEnforcementResult(
            action="block",
            task_id="t1",
            declared_patterns=["src/*.py"],
            staged_files=["docs/a.md"],
            out_of_scope=["docs/a.md"],
            drift_ratio=1.0,
            reason="all out of scope",
        )
        d = result.to_dict()
        assert d["action"] == "block"
        assert d["drift_ratio"] == 1.0
        json.dumps(d)


class TestEnforceScopeDrift:
    """Tests for enforce_scope_drift()."""

    def test_no_declared_patterns_skips(self) -> None:
        result = enforce_scope_drift(
            staged_files=["src/foo.py"],
            declared_patterns=[],
            task_id="t1",
        )
        assert result.action == "skip"
        assert "skipping" in result.reason.lower()

    def test_no_staged_files_allows(self) -> None:
        result = enforce_scope_drift(
            staged_files=[],
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        assert result.action == "allow"

    def test_all_in_scope_allows(self) -> None:
        result = enforce_scope_drift(
            staged_files=["src/ops/scope.py", "src/ops/events.py"],
            declared_patterns=["src/ops/*.py"],
            task_id="t1",
        )
        assert result.action == "allow"
        assert result.drift_ratio == 0.0
        assert result.out_of_scope == []

    def test_warn_threshold(self) -> None:
        """3 of 5 files out of scope → 60% → warn (> 50%, ≤ 80%)."""
        result = enforce_scope_drift(
            staged_files=[
                "src/a.py",
                "src/b.py",
                "docs/c.md",
                "docs/d.md",
                "docs/e.md",
            ],
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        assert result.action == "warn"
        assert result.drift_ratio == pytest.approx(0.6)
        assert len(result.out_of_scope) == 3

    def test_block_threshold(self) -> None:
        """9 of 10 files out of scope → 90% → block (> 80%)."""
        staged = [f"docs/file{i}.md" for i in range(9)] + ["src/a.py"]
        result = enforce_scope_drift(
            staged_files=staged,
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        assert result.action == "block"
        assert result.drift_ratio == pytest.approx(0.9)

    def test_exactly_at_warn_threshold_allows(self) -> None:
        """Exactly 50% → allow (thresholds are strict >)."""
        result = enforce_scope_drift(
            staged_files=["src/a.py", "docs/b.md"],
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        assert result.action == "allow"
        assert result.drift_ratio == pytest.approx(0.5)

    def test_exactly_at_block_threshold_warns(self) -> None:
        """Exactly 80% → warn (threshold is strict >)."""
        staged = ["src/a.py"] + [f"docs/f{i}.md" for i in range(4)]
        result = enforce_scope_drift(
            staged_files=staged,
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        # 4/5 = 80% exactly → warn (not block, since > is strict)
        assert result.action == "warn"
        assert result.drift_ratio == pytest.approx(0.8)

    def test_custom_thresholds(self) -> None:
        """Custom thresholds override defaults."""
        result = enforce_scope_drift(
            staged_files=["src/a.py", "docs/b.md"],
            declared_patterns=["src/*.py"],
            task_id="t1",
            warn_threshold=0.3,
            block_threshold=0.4,
        )
        # 1/2 = 50% > 40% block threshold
        assert result.action == "block"

    def test_minor_drift_allows_with_reason(self) -> None:
        """1 of 5 files out of scope (20%) → allow, but reason mentions it."""
        staged = ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "docs/e.md"]
        result = enforce_scope_drift(
            staged_files=staged,
            declared_patterns=["src/*.py"],
            task_id="t1",
        )
        assert result.action == "allow"
        assert "1 file(s) outside scope" in result.reason

    def test_block_narrow_scope_out_of_scope_file(self) -> None:
        """End-to-end: narrow scope with all staged files outside → block."""
        result = enforce_scope_drift(
            staged_files=["tests/unit/test_rules.py", "docs/readme.md"],
            declared_patterns=["src/bid_euchre/ops/scope.py"],
            task_id="t-narrow",
        )
        assert result.action == "block"
        assert result.drift_ratio == pytest.approx(1.0)
        assert len(result.out_of_scope) == 2


class TestGetActiveTaskScope:
    """Tests for get_active_task_scope()."""

    @pytest.fixture()
    def queue_root(self, tmp_path: Path) -> Path:
        """Create a task queue directory."""
        qr = tmp_path / "task_queue"
        qr.mkdir()
        return qr

    def _write_packet(
        self,
        queue_root: Path,
        packet_id: str,
        *,
        owner: str = "author-a",
        status: str = "dispatched",
        scope: list[str] | None = None,
    ) -> None:
        """Write a minimal task packet JSON."""
        pkt = {
            "packet_id": packet_id,
            "title": "Test",
            "description": "test",
            "owner": owner,
            "created_by": "orchestrator",
            "created_at": "2026-01-01T00:00:00Z",
            "status": status,
            "scope_declared": scope or [],
            "validation": [],
            "priority": "normal",
        }
        (queue_root / f"{packet_id}.json").write_text(json.dumps(pkt))

    def test_finds_dispatched_task(self, queue_root: Path) -> None:
        self._write_packet(
            queue_root, "pkt-1", scope=["src/ops/*.py", "tests/unit/test_ops_*.py"]
        )
        task_id, patterns = get_active_task_scope("author-a", queue_root)
        assert task_id == "pkt-1"
        assert patterns == ["src/ops/*.py", "tests/unit/test_ops_*.py"]

    def test_no_dispatched_task(self, queue_root: Path) -> None:
        self._write_packet(queue_root, "pkt-1", status="pending")
        task_id, patterns = get_active_task_scope("author-a", queue_root)
        assert task_id is None
        assert patterns == []

    def test_wrong_owner(self, queue_root: Path) -> None:
        self._write_packet(queue_root, "pkt-1", owner="author-b")
        task_id, patterns = get_active_task_scope("author-a", queue_root)
        assert task_id is None
        assert patterns == []

    def test_empty_scope(self, queue_root: Path) -> None:
        self._write_packet(queue_root, "pkt-1", scope=[])
        task_id, patterns = get_active_task_scope("author-a", queue_root)
        assert task_id == "pkt-1"
        assert patterns == []


# --- Hook contract regression tests ---


class TestScopeDriftGuardHookContract:
    """Regression tests for scope-drift-guard.sh hook.

    Issue #1379: the hook previously embedded LANE_ID directly into
    Python source via shell interpolation ('${LANE_ID}'). If the env
    var contained quotes, this would break the Python string literal.
    The fix passes LANE_ID as sys.argv[1] instead.
    """

    @pytest.fixture()
    def hook_content(self) -> str:
        """Read the scope-drift-guard hook source."""
        hook_path = (
            Path(__file__).resolve().parents[2]
            / ".claude"
            / "hooks"
            / "scope-drift-guard.sh"
        )
        assert hook_path.exists(), f"Hook not found at {hook_path}"
        return hook_path.read_text()

    def test_no_shell_interpolation_of_lane_id_in_python(
        self, hook_content: str
    ) -> None:
        """LANE_ID must not be shell-interpolated into Python source."""
        assert "'${LANE_ID}'" not in hook_content, (
            "Hook still uses unsafe shell interpolation of LANE_ID "
            "into Python source (issue #1379)"
        )

    def test_lane_id_passed_via_sys_argv(self, hook_content: str) -> None:
        """LANE_ID must be passed as a command-line argument."""
        assert (
            "sys.argv[1]" in hook_content
        ), "Hook should read LANE_ID from sys.argv[1]"
        # The shell argument should be double-quoted after the closing
        # quote of the -c string so the variable expands correctly
        assert (
            '"$LANE_ID"' in hook_content
        ), "Hook should pass $LANE_ID as a double-quoted shell argument to python -c"

    def test_no_single_quoted_lane_id_argument(self, hook_content: str) -> None:
        """Single-quoted '$LANE_ID' must not appear — it prevents expansion."""
        assert "'$LANE_ID'" not in hook_content, (
            "Hook uses single-quoted '$LANE_ID' which prevents shell "
            "variable expansion — use double quotes instead"
        )
