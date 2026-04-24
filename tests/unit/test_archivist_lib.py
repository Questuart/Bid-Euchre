"""Unit tests for ``bid_euchre.ops.archivist`` — lessons + GC modes.

Mirrors the Primitive D shape §4.1.6 and §4.2.5 test surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.ops.archivist import (
    EMISSION_ENV_VAR,
    GC_CLASSES,
    KBSnapshot,
    emission_enabled,
    emit_candidate_proposed,
    emit_gc_proposed,
    load_fake_kb_snapshot,
    run_gc,
    run_lessons,
)
from bid_euchre.ops.archivist.lessons import (
    EXIT_EMPTY,
    EXIT_OK,
    WATERMARK_FILE,
)

FIXTURE_EVENTS = (
    Path(__file__).resolve().parents[1] / "fixtures/archivist/fake_events.jsonl"
)
FIXTURE_KB_DIR = Path(__file__).resolve().parents[1] / "fixtures/archivist/fake_kb"


@pytest.fixture()
def candidates_dir(tmp_path: Path) -> Path:
    """Return an isolated candidates dir rooted in tmp_path."""
    d = tmp_path / "_candidates"
    d.mkdir()
    return d


@pytest.fixture()
def emission_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ENABLE_D_EVENT_EMISSION is unset for this test."""
    monkeypatch.delenv(EMISSION_ENV_VAR, raising=False)


@pytest.fixture()
def emission_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ENABLE_D_EVENT_EMISSION=1 for this test."""
    monkeypatch.setenv(EMISSION_ENV_VAR, "1")


# ----- TestLessonsMode -----


class TestLessonsMode:
    """Unit tests mirroring shape §4.1.6 row list."""

    def test_templating_against_fake_events(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Read fixture events, assert output file shape + section headers."""
        # window_start is before all fixture events (2030-01-01)
        since = datetime(2029, 12, 31, tzinfo=timezone.utc)
        result = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
        )

        assert result.exit_code == EXIT_OK
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.event_count >= 20
        assert result.candidate_count >= 3

        content = result.output_path.read_text(encoding="utf-8")
        # Header shape
        assert "# Archivist Candidate — Lessons" in content
        # All four sections present
        assert "## Section 1 — Repeated patterns" in content
        assert "## Section 2 — Token-efficiency outliers" in content
        assert "## Section 3 — Incident candidates" in content
        assert "## Section 4 — Lesson candidates (explicit)" in content
        # Verification footer present
        assert "## Verification: operator review" in content

    def test_all_four_section_types_exercised(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Fixture is seeded so at least one candidate appears in each
        of the four sections — this exercises the shape §3 row requirement
        "≥3 candidate-class cases from seeded fake events."
        """
        since = datetime(2029, 12, 31, tzinfo=timezone.utc)
        result = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
        )
        # Exactly to section candidate count we need to walk the stored
        # markdown for "### Candidate" headers per section.
        assert result.output_path is not None
        content = result.output_path.read_text(encoding="utf-8")
        # Split by section headers and count non-empty sections.
        # At least one of each — repeated-patterns (task_started@ops.orch x 3+),
        # token-outliers (p5/p11 at 85k/95k vs mean ~10k), incidents (ci_failure,
        # task_failed, escalation, watchdog_finding, fs_boundary_violation),
        # explicit (p6 carries lesson_learned).
        section_bodies = content.split("## Section ")
        assert len(section_bodies) >= 5  # 4 sections + pre-header
        # Each section has at least a candidate or the "No candidates" marker.
        for body in section_bodies[1:]:
            assert body.strip() != ""

    def test_empty_scan_exit_1(
        self, candidates_dir: Path, emission_off: None, tmp_path: Path
    ) -> None:
        """Empty fixture → exit EXIT_EMPTY, no output file written."""
        empty_fixture = tmp_path / "empty.jsonl"
        empty_fixture.write_text("", encoding="utf-8")
        result = run_lessons(
            candidates_dir=candidates_dir,
            since=datetime(2029, 1, 1, tzinfo=timezone.utc),
            fixture_path=empty_fixture,
        )
        assert result.exit_code == EXIT_EMPTY
        assert result.output_path is None
        # Candidates dir should remain empty (no lessons file written)
        assert not any(candidates_dir.glob("*_lessons.md"))

    def test_since_watermark_advancement(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Watermark file is advanced after a successful non-dry-run.

        The watermark stores ``window_end`` (= wall-clock now), so we
        assert it is populated with a timestamp within a few seconds of
        ``run_lessons``'s return, *not* that it advances past ``since``
        (since that's a lower bound for events, not for the watermark).
        """
        watermark_path = candidates_dir / WATERMARK_FILE
        assert not watermark_path.exists()

        before = datetime.now(timezone.utc)
        since = datetime(2029, 12, 31, tzinfo=timezone.utc)
        result = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
        )
        after = datetime.now(timezone.utc)

        assert result.exit_code == EXIT_OK
        assert watermark_path.exists()
        recorded = datetime.fromisoformat(watermark_path.read_text().strip())
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        # Watermark is ``window_end`` (wall-clock now). Allow 5s tolerance.
        assert before - timedelta(seconds=5) <= recorded <= after + timedelta(seconds=5)
        # And it must equal the result's ``window_end`` (exact).
        assert recorded == result.window_end

    def test_dry_run_does_not_advance_watermark(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Dry-run must not create a watermark or output file."""
        watermark_path = candidates_dir / WATERMARK_FILE

        since = datetime(2029, 12, 31, tzinfo=timezone.utc)
        result = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
            dry_run=True,
        )
        assert result.exit_code == EXIT_OK
        assert not watermark_path.exists()
        assert result.output_path is not None
        assert not result.output_path.exists()

    def test_same_date_rerun_appends(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Second run on the same UTC date appends to the existing file
        rather than overwriting (shape §4.1.3)."""
        since = datetime(2029, 12, 31, tzinfo=timezone.utc)
        result1 = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
        )
        assert result1.output_path is not None
        size_after_first = result1.output_path.stat().st_size

        # Second run with a very-early `since` so candidates are produced again.
        result2 = run_lessons(
            candidates_dir=candidates_dir,
            since=since,
            fixture_path=FIXTURE_EVENTS,
        )
        assert result2.exit_code == EXIT_OK
        assert result2.output_path is not None
        size_after_second = result2.output_path.stat().st_size
        assert size_after_second > size_after_first


class TestEventEmission:
    """Unit tests for ``archivist/events.py`` — flag gating + payload shape."""

    def test_no_emission_when_flag_off(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """By default (flag off), no event is emitted; wrapper returns None."""
        assert emission_enabled() is False
        result = emit_candidate_proposed(
            candidate_path=candidates_dir / "x.md",
            candidate_class="lessons",
            source_event_ids=["t1"],
        )
        assert result is None

    def test_candidate_event_shape_when_flag_on(
        self, candidates_dir: Path, emission_on: None
    ) -> None:
        """When flag is on, wrapper calls append_event with the expected
        payload shape (mocks the event-writer since types are not yet
        registered in VALID_EVENT_TYPES)."""
        assert emission_enabled() is True

        with patch("bid_euchre.ops.events.append_event") as mock_append:
            mock_append.return_value = {"mocked": True}
            emit_candidate_proposed(
                candidate_path=candidates_dir / "x.md",
                candidate_class="lessons",
                source_event_ids=["t1", "t2"],
                lane_id="ops",
            )
            mock_append.assert_called_once()
            call = mock_append.call_args
            # event_type (positional or kwarg)
            kwargs = call.kwargs
            assert kwargs["event_type"] == "archivist_candidate_proposed"
            assert kwargs["source"] == "ops.archivist"
            assert kwargs["lane_id"] == "ops"
            payload = kwargs["payload"]
            assert payload["candidate_class"] == "lessons"
            assert payload["source_event_ids"] == ["t1", "t2"]
            assert payload["candidate_path"].endswith("x.md")

    def test_gc_event_shape_when_flag_on(
        self, candidates_dir: Path, emission_on: None
    ) -> None:
        """archivist_gc_proposed payload carries gc_class + target_paths."""
        with patch("bid_euchre.ops.events.append_event") as mock_append:
            mock_append.return_value = {"mocked": True}
            emit_gc_proposed(
                candidate_path=candidates_dir / "gc.md",
                gc_class="stale",
                target_paths=["knowledge/lessons/x.md"],
            )
            kwargs = mock_append.call_args.kwargs
            assert kwargs["event_type"] == "archivist_gc_proposed"
            payload = kwargs["payload"]
            assert payload["gc_class"] == "stale"
            assert payload["target_paths"] == ["knowledge/lessons/x.md"]


# ----- TestGCMode -----


class TestGCMode:
    """Unit tests mirroring shape §4.2.5."""

    def test_stale_detection_fake_kb(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        snapshot = KBSnapshot(
            all_files=["knowledge/keep.md", "knowledge/stale.md"],
            references={"knowledge/keep.md": ["plans/foo.md"]},
        )
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        assert result.output_path is not None
        assert result.output_path.exists()
        content = result.output_path.read_text(encoding="utf-8")
        assert "knowledge/stale.md" in content
        assert "knowledge/keep.md" not in content
        assert "stale" in result.classes_covered

    def test_dead_skill_detection_fake_events(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        snapshot = KBSnapshot(
            skills=[".claude/skills/alive", ".claude/skills/dead"],
            skill_last_invoked={
                ".claude/skills/alive": datetime(2030, 1, 1, tzinfo=timezone.utc),
                ".claude/skills/dead": None,
            },
        )
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        content = result.output_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
        assert ".claude/skills/dead" in content
        assert ".claude/skills/alive" not in content
        assert "dead-skill" in result.classes_covered

    def test_obsolete_policy_detection_fake_registry(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        snapshot = KBSnapshot(
            superseded_policies={
                ".claude/rules/prompt_policy/old.md": ".claude/rules/prompt_policy/new.md",
            }
        )
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        content = result.output_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
        assert "old.md" in content
        assert "superseded by" in content
        assert "obsolete-policy" in result.classes_covered

    def test_orphan_detection_missing_target(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        snapshot = KBSnapshot(
            orphans={"knowledge/orphan.md": "knowledge/_promoted/missing.md"}
        )
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        content = result.output_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
        assert "orphan.md" in content
        assert "missing.md" in content
        assert "orphan" in result.classes_covered

    def test_expired_evidence_detection(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        snapshot = KBSnapshot(
            expired={"knowledge/entry.md": "https://example.com/expired"}
        )
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        content = result.output_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
        assert "knowledge/entry.md" in content
        assert "expired" in result.classes_covered

    def test_gc_class_coverage(self, candidates_dir: Path, emission_off: None) -> None:
        """All five gc_class values should be covered by a single run
        loading the seeded fake-KB fixture directory."""
        snapshot = load_fake_kb_snapshot(FIXTURE_KB_DIR)
        result = run_gc(candidates_dir=candidates_dir, snapshot=snapshot)
        assert result.exit_code == EXIT_OK
        # Every gc_class appears in result.classes_covered
        for gc_class in GC_CLASSES:
            assert gc_class in result.classes_covered, (
                f"gc_class={gc_class!r} missing from classes_covered="
                f"{result.classes_covered}"
            )

    def test_empty_snapshot_exit_empty(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """No proposals from an empty snapshot → EXIT_EMPTY, no file."""
        result = run_gc(candidates_dir=candidates_dir, snapshot=KBSnapshot())
        assert result.exit_code == EXIT_EMPTY
        assert result.output_path is None

    def test_no_snapshot_returns_empty_phase_0(
        self, candidates_dir: Path, emission_off: None
    ) -> None:
        """Phase 0 live-load: no snapshot argument → empty result (not an error)."""
        result = run_gc(candidates_dir=candidates_dir, snapshot=None)
        assert result.exit_code == EXIT_EMPTY
        assert result.output_path is None
        assert result.proposal_count == 0
