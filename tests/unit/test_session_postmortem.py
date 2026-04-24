"""Unit tests for ``bid_euchre.ops.session_postmortem``.

Mirrors the Primitive D shape §4.4.4 test surface:

- ``test_render_memory_entry_against_template_fixture``
- ``test_render_candidate_entry_section_shape``
- ``test_run_postmortem_writes_both_outputs``
- ``test_run_postmortem_graceful_on_missing_session_id``
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.session_postmortem import (
    EXIT_EMPTY,
    EXIT_OK,
    SessionSignals,
    collect_session_signals,
    render_candidate_entry,
    render_memory_entry,
    run_postmortem,
)


@pytest.fixture()
def sample_events() -> list[dict]:
    """A small event stream covering incident + token outlier + explicit
    lesson signals.

    Baseline: 10 ``task_completed`` events at ~5000 token_delta with one
    outlier at 85000. The baseline count is enough that 85000 > mean+2σ
    (≈ 58k with these values), so the outlier-detector fires.
    """
    baseline = [
        {
            "timestamp": f"2026-04-20T10:{minute:02d}:00+00:00",
            "event_type": "task_completed",
            "source": "ops.hook",
            "lane_id": f"author-{chr(ord('a') + (minute % 4))}",
            "payload": {
                "packet_id": f"p{minute}",
                "token_delta": 5000 + (minute * 100),
            },
        }
        for minute in range(10)
    ]
    return baseline + [
        {
            "timestamp": "2026-04-20T10:10:00+00:00",
            "event_type": "task_completed",
            "source": "ops.hook",
            "lane_id": "author-a",
            "payload": {"packet_id": "p3", "token_delta": 85000, "lane": "author-a"},
        },
        {
            "timestamp": "2026-04-20T10:15:00+00:00",
            "event_type": "ci_failure",
            "source": "hook.ci",
            "lane_id": "author-b",
            "payload": {"incident_id": "inc-001", "pr": 42},
        },
        {
            "timestamp": "2026-04-20T10:20:00+00:00",
            "event_type": "task_completed",
            "source": "ops.hook",
            "lane_id": "author-c",
            "payload": {
                "packet_id": "p4",
                "token_delta": 4500,
                "lesson_learned": "Avoid duplicate foreground processes",
            },
        },
    ]


class TestRendering:
    """Cover shape §4.4.4 rows 1 and 2 (renderer tests)."""

    def test_render_memory_entry_against_template_fixture(
        self, sample_events: list[dict]
    ) -> None:
        """Memory entry shape matches the Phase-4 SKILL.md template."""
        signals = collect_session_signals(
            session_id="2026-04-20a",
            events=sample_events,
            prs_merged=["1234", "#1235"],
            lanes_parked=["author-a", "author-b"],
            session_start=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            session_end=datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc),
            goal="Ship Primitive D Phase 0",
            outstanding=["packet p9 still dispatched"],
            next_steps=["Run proving dispatch"],
            hazards=["CI flake on test_arc_d"],
        )
        entry = render_memory_entry(signals)

        # Required fields from shape §4.4.1 / SKILL.md Phase 4.
        assert "### Session 2026-04-20a" in entry
        assert "**Goal:** Ship Primitive D Phase 0" in entry
        assert "#1234" in entry and "#1235" in entry
        assert "author-a" in entry and "author-b" in entry
        assert "packet p9 still dispatched" in entry
        assert "Run proving dispatch" in entry
        assert "CI flake on test_arc_d" in entry

    def test_render_memory_entry_empty_sections_render_as_none(
        self,
    ) -> None:
        """Empty optional sections render as ``_(none)_`` — not blank."""
        signals = collect_session_signals(session_id="empty-session")
        entry = render_memory_entry(signals)
        assert "_(none)_" in entry
        assert "### Session empty-session" in entry

    def test_render_candidate_entry_section_shape(
        self, sample_events: list[dict]
    ) -> None:
        """Candidate entry section fits the lessons-file schema."""
        signals = collect_session_signals(
            session_id="2026-04-20a",
            events=sample_events,
            session_start=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            session_end=datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc),
        )
        section = render_candidate_entry(signals)

        # Header matches POSTMORTEM_SECTION_HEADER shape.
        assert "## Postmortem — session 2026-04-20a" in section
        # Three subsections.
        assert "### Incidents" in section
        assert "### Token outliers" in section
        assert "### Explicit lessons" in section
        # Signals derived correctly.
        assert "inc-001" in section
        assert "Avoid duplicate foreground processes" in section
        # Token outlier present (p3 @ 85000 is >=2σ above mean).
        assert "token_delta=85000" in section
        # Session-end ts is ISO-8601.
        assert "2026-04-20T18:00:00+00:00" in section


class TestRunPostmortem:
    """Cover shape §4.4.4 rows 3 and 4 (orchestrator tests)."""

    def test_run_postmortem_writes_both_outputs(
        self, tmp_path: Path, sample_events: list[dict]
    ) -> None:
        """``run_postmortem`` appends to MEMORY.md and writes the
        candidate file in a single call."""
        memory_md = tmp_path / "MEMORY.md"
        memory_md.write_text("# Bid Euchre Project Memory\n\n", encoding="utf-8")
        candidates_dir = tmp_path / "_candidates"

        signals = collect_session_signals(
            session_id="2026-04-20a",
            events=sample_events,
            prs_merged=["1234"],
            lanes_parked=["author-a"],
            goal="D.2 test",
            session_start=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            session_end=datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc),
        )
        result = run_postmortem(
            session_id="2026-04-20a",
            memory_md_path=memory_md,
            candidates_dir=candidates_dir,
            signals=signals,
            when=datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc),
        )

        assert result.exit_code == EXIT_OK
        assert result.memory_appended is True
        assert result.candidate_path is not None
        assert result.candidate_path.exists()

        # MEMORY.md appended, not overwritten.
        memory_body = memory_md.read_text(encoding="utf-8")
        assert memory_body.startswith("# Bid Euchre Project Memory")
        assert "### Session 2026-04-20a" in memory_body

        # Candidate file contains postmortem section.
        candidate_body = result.candidate_path.read_text(encoding="utf-8")
        assert "## Postmortem — session 2026-04-20a" in candidate_body
        assert "inc-001" in candidate_body

    def test_run_postmortem_appends_to_existing_candidate_file(
        self, tmp_path: Path
    ) -> None:
        """If the dated lessons candidate file already exists (from a
        prior lessons-mode run the same day), the postmortem section is
        appended with a ``---`` separator."""
        memory_md = tmp_path / "MEMORY.md"
        candidates_dir = tmp_path / "_candidates"
        candidates_dir.mkdir()
        dated = candidates_dir / "2026-04-20_lessons.md"
        dated.write_text(
            "# Archivist Candidate — Lessons — 2026-04-20\n\nExisting content\n",
            encoding="utf-8",
        )
        size_before = dated.stat().st_size

        signals = collect_session_signals(session_id="2026-04-20a")
        result = run_postmortem(
            session_id="2026-04-20a",
            memory_md_path=memory_md,
            candidates_dir=candidates_dir,
            signals=signals,
            when=datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc),
        )

        assert result.exit_code == EXIT_OK
        after = dated.read_text(encoding="utf-8")
        assert after.startswith("# Archivist Candidate — Lessons — 2026-04-20")
        assert "Existing content" in after
        assert "## Postmortem — session 2026-04-20a" in after
        assert "\n---\n\n" in after
        assert dated.stat().st_size > size_before

    def test_run_postmortem_graceful_on_missing_session_id(
        self, tmp_path: Path
    ) -> None:
        """Empty ``session_id`` → exit 1, no partial writes."""
        memory_md = tmp_path / "MEMORY.md"
        candidates_dir = tmp_path / "_candidates"

        result = run_postmortem(
            session_id="",
            memory_md_path=memory_md,
            candidates_dir=candidates_dir,
        )
        assert result.exit_code == EXIT_EMPTY
        assert result.memory_appended is False
        assert result.candidate_path is None
        # No file created by an empty-session invocation.
        assert not memory_md.exists()
        assert not candidates_dir.exists() or not any(candidates_dir.iterdir())

    def test_run_postmortem_dry_run_no_writes(self, tmp_path: Path) -> None:
        """``dry_run=True`` computes but does not write."""
        memory_md = tmp_path / "MEMORY.md"
        candidates_dir = tmp_path / "_candidates"

        signals = collect_session_signals(session_id="dryrun-session")
        result = run_postmortem(
            session_id="dryrun-session",
            memory_md_path=memory_md,
            candidates_dir=candidates_dir,
            signals=signals,
            dry_run=True,
        )
        assert result.exit_code == EXIT_OK
        assert not memory_md.exists()
        assert result.candidate_path is not None
        assert not result.candidate_path.exists()

    def test_collect_session_signals_derives_rollups(
        self, sample_events: list[dict]
    ) -> None:
        """Rollup derivation: incident_ids, token_outliers, lessons_explicit."""
        signals = collect_session_signals(
            session_id="derive-test", events=sample_events
        )
        assert isinstance(signals, SessionSignals)
        # One incident (ci_failure).
        assert any("inc-001" in iid for iid in signals.incident_ids)
        # One token outlier (p3 @ 85000).
        assert len(signals.token_outliers) >= 1
        assert signals.token_outliers[0]["packet_id"] == "p3"
        # One explicit lesson.
        assert any(
            "duplicate foreground processes" in lesson
            for lesson in signals.lessons_explicit
        )
