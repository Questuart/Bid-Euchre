"""Tests for the review queue substrate (request/verdict models, file layout, staleness)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.review_queue import (
    DEFAULT_QUEUE_DIR,
    VALID_STATUSES,
    PrecheckFinding,
    ReviewRequest,
    ReviewVerdict,
    invalidate_stale_verdict,
    is_verdict_stale,
    pr_dir,
    precheck_to_verdict,
    read_request,
    read_verdict,
    request_path,
    verdict_path,
    write_request,
    write_verdict,
)

# ---------------------------------------------------------------------------
# Model round-trip tests
# ---------------------------------------------------------------------------


class TestReviewRequest:
    def test_to_dict_round_trip(self) -> None:
        req = ReviewRequest(
            pr_number=42,
            head_sha="abc123",
            branch="feat/foo",
            requester="author-a",
            created_at="2026-03-20T00:00:00+00:00",
        )
        d = req.to_dict()
        restored = ReviewRequest.from_dict(d)
        assert restored == req

    def test_from_dict_coerces_types(self) -> None:
        """PR number should be coerced from string to int."""
        d = {
            "pr_number": "99",
            "head_sha": "def456",
            "branch": "fix/bar",
            "requester": "review",
        }
        req = ReviewRequest.from_dict(d)
        assert req.pr_number == 99
        assert isinstance(req.pr_number, int)

    def test_created_at_defaults(self) -> None:
        req = ReviewRequest(
            pr_number=1,
            head_sha="aaa",
            branch="main",
            requester="test",
        )
        assert req.created_at  # Non-empty default


class TestReviewVerdict:
    def test_to_dict_round_trip(self) -> None:
        verdict = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc123",
            status="passed",
            reason="All good",
            findings=[{"check_id": "C1", "severity": "WARN", "message": "note"}],
            created_at="2026-03-20T00:00:00+00:00",
        )
        d = verdict.to_dict()
        restored = ReviewVerdict.from_dict(d)
        assert restored == verdict

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid verdict status"):
            ReviewVerdict(
                pr_number=1,
                reviewed_sha="aaa",
                status="invalid_status",
                reason="test",
            )

    def test_all_valid_statuses_accepted(self) -> None:
        for status in VALID_STATUSES:
            v = ReviewVerdict(
                pr_number=1,
                reviewed_sha="aaa",
                status=status,
                reason="test",
            )
            assert v.status == status


# ---------------------------------------------------------------------------
# File layout tests
# ---------------------------------------------------------------------------


class TestFileLayout:
    def test_pr_dir_default(self) -> None:
        d = pr_dir(42)
        assert d == DEFAULT_QUEUE_DIR / "pr_42"

    def test_pr_dir_custom(self, tmp_path: object) -> None:
        from pathlib import Path

        custom = Path(str(tmp_path)) / "custom"
        d = pr_dir(99, custom)
        assert d == custom / "pr_99"

    def test_request_path(self) -> None:
        p = request_path(42)
        assert p.name == "request.json"
        assert p.parent == pr_dir(42)

    def test_verdict_path(self) -> None:
        p = verdict_path(42)
        assert p.name == "verdict.json"
        assert p.parent == pr_dir(42)


# ---------------------------------------------------------------------------
# Read / write round-trip tests
# ---------------------------------------------------------------------------


class TestRequestReadWrite:
    def test_write_and_read_request(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        req = ReviewRequest(
            pr_number=42,
            head_sha="abc123def",
            branch="feat/review-queue",
            requester="author-a",
        )
        path = write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        assert path.exists()

        # Verify JSON is well-formed
        data = json.loads(path.read_text())
        assert data["pr_number"] == 42
        assert data["head_sha"] == "abc123def"

        # Round-trip
        restored = read_request(42, queue_dir)
        assert restored is not None
        assert restored.pr_number == req.pr_number
        assert restored.head_sha == req.head_sha
        assert restored.branch == req.branch
        assert restored.requester == req.requester

    def test_read_missing_request_returns_none(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        assert read_request(999, queue_dir) is None

    def test_write_request_emits_event(self, tmp_path: object) -> None:
        from pathlib import Path

        from bid_euchre.ops.events import read_events

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        req = ReviewRequest(
            pr_number=77,
            head_sha="sha777",
            branch="feat/test",
            requester="author-b",
        )
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)

        events = read_events(events_dir, event_type="review_request")
        assert len(events) == 1
        assert events[0]["payload"]["pr_number"] == 77
        assert events[0]["payload"]["head_sha"] == "sha777"
        assert events[0]["lane_id"] == "author-b"

    def test_write_request_no_event(self, tmp_path: object) -> None:
        from pathlib import Path

        from bid_euchre.ops.events import read_events

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        req = ReviewRequest(
            pr_number=88,
            head_sha="sha888",
            branch="feat/quiet",
            requester="review",
        )
        write_request(req, queue_dir, emit_event=False, events_dir=events_dir)

        events = read_events(events_dir, event_type="review_request")
        assert len(events) == 0


class TestVerdictReadWrite:
    def test_write_and_read_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        verdict = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc123def",
            status="passed",
            reason="Clean review",
            findings=[],
        )
        path = write_verdict(verdict, queue_dir, emit_event=True, events_dir=events_dir)
        assert path.exists()

        restored = read_verdict(42, queue_dir)
        assert restored is not None
        assert restored.pr_number == verdict.pr_number
        assert restored.reviewed_sha == verdict.reviewed_sha
        assert restored.status == verdict.status
        assert restored.reason == verdict.reason

    def test_read_missing_verdict_returns_none(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        assert read_verdict(999, queue_dir) is None

    def test_write_verdict_emits_event(self, tmp_path: object) -> None:
        from pathlib import Path

        from bid_euchre.ops.events import read_events

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        verdict = ReviewVerdict(
            pr_number=42,
            reviewed_sha="sha42",
            status="blocked",
            reason="Blocker found",
            findings=[{"check_id": "C1", "severity": "BLOCK", "message": "unseeded"}],
        )
        write_verdict(
            verdict,
            queue_dir,
            emit_event=True,
            lane_id="review",
            events_dir=events_dir,
        )

        events = read_events(events_dir, event_type="review_verdict")
        assert len(events) == 1
        assert events[0]["payload"]["status"] == "blocked"
        assert events[0]["payload"]["n_findings"] == 1


# ---------------------------------------------------------------------------
# Stale verdict detection
# ---------------------------------------------------------------------------


class TestStaleVerdict:
    def _write_verdict_at_sha(self, tmp_path: object, pr_number: int, sha: str) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"
        verdict = ReviewVerdict(
            pr_number=pr_number,
            reviewed_sha=sha,
            status="passed",
            reason="test",
        )
        write_verdict(verdict, queue_dir, emit_event=False, events_dir=events_dir)

    def test_stale_when_sha_differs(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        self._write_verdict_at_sha(tmp_path, 42, "old_sha")
        assert is_verdict_stale(42, "new_sha", queue_dir) is True

    def test_not_stale_when_sha_matches(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        self._write_verdict_at_sha(tmp_path, 42, "same_sha")
        assert is_verdict_stale(42, "same_sha", queue_dir) is False

    def test_not_stale_when_no_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        assert is_verdict_stale(42, "any_sha", queue_dir) is False

    def test_invalidate_removes_stale_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        self._write_verdict_at_sha(tmp_path, 42, "old_sha")

        removed = invalidate_stale_verdict(42, "new_sha", queue_dir)
        assert removed is True
        assert read_verdict(42, queue_dir) is None

    def test_invalidate_keeps_fresh_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        self._write_verdict_at_sha(tmp_path, 42, "current_sha")

        removed = invalidate_stale_verdict(42, "current_sha", queue_dir)
        assert removed is False
        assert read_verdict(42, queue_dir) is not None


# ---------------------------------------------------------------------------
# Deterministic precheck -> blocked verdict
# ---------------------------------------------------------------------------


class TestPrecheckToVerdict:
    def test_blocker_creates_blocked_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        findings = [
            PrecheckFinding(
                check_id="C1",
                severity="BLOCK",
                message="Unseeded randomness in strategy.py",
                file="src/bid_euchre/strategy/foo.py",
                line=42,
            ),
        ]
        verdict = precheck_to_verdict(
            pr_number=99,
            head_sha="sha_precheck",
            findings=findings,
            queue_dir=queue_dir,
            emit_event=True,
            events_dir=events_dir,
        )

        assert verdict.status == "blocked"
        assert "1 blocker" in verdict.reason
        assert verdict.reviewed_sha == "sha_precheck"
        assert len(verdict.findings) == 1
        assert verdict.findings[0]["check_id"] == "C1"

        # Verify persisted
        persisted = read_verdict(99, queue_dir)
        assert persisted is not None
        assert persisted.status == "blocked"

    def test_warn_only_creates_passed_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        findings = [
            PrecheckFinding(
                check_id="N1",
                severity="WARN",
                message="Missing contract-type facet",
            ),
            PrecheckFinding(
                check_id="T1",
                severity="WARN",
                message="Untested behavior change",
            ),
        ]
        verdict = precheck_to_verdict(
            pr_number=100,
            head_sha="sha_warn",
            findings=findings,
            queue_dir=queue_dir,
            emit_event=False,
            events_dir=events_dir,
        )

        assert verdict.status == "passed"
        assert "2 warning" in verdict.reason

    def test_no_findings_creates_clean_passed_verdict(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        verdict = precheck_to_verdict(
            pr_number=101,
            head_sha="sha_clean",
            findings=[],
            queue_dir=queue_dir,
            emit_event=False,
            events_dir=events_dir,
        )

        assert verdict.status == "passed"
        assert "clean" in verdict.reason
        assert verdict.findings == []

    def test_mixed_block_and_warn(self, tmp_path: object) -> None:
        from pathlib import Path

        queue_dir = Path(str(tmp_path)) / "queue"
        events_dir = Path(str(tmp_path)) / "events"

        findings = [
            PrecheckFinding(
                check_id="X3",
                severity="BLOCK",
                message="Merge conflict markers",
            ),
            PrecheckFinding(
                check_id="N2",
                severity="WARN",
                message="Collapsed matchup table",
            ),
            PrecheckFinding(
                check_id="C1",
                severity="BLOCK",
                message="Unseeded randomness",
            ),
        ]
        verdict = precheck_to_verdict(
            pr_number=102,
            head_sha="sha_mixed",
            findings=findings,
            queue_dir=queue_dir,
            emit_event=False,
            events_dir=events_dir,
        )

        assert verdict.status == "blocked"
        assert "2 blocker" in verdict.reason
        assert len(verdict.findings) == 3


class TestPrecheckFinding:
    def test_to_dict_minimal(self) -> None:
        f = PrecheckFinding(check_id="C1", severity="BLOCK", message="test")
        d = f.to_dict()
        assert d == {"check_id": "C1", "severity": "BLOCK", "message": "test"}
        assert "file" not in d
        assert "line" not in d

    def test_to_dict_with_location(self) -> None:
        f = PrecheckFinding(
            check_id="X3",
            severity="BLOCK",
            message="conflict markers",
            file="src/foo.py",
            line=10,
        )
        d = f.to_dict()
        assert d["file"] == "src/foo.py"
        assert d["line"] == 10

    def test_from_dict_round_trip(self) -> None:
        f = PrecheckFinding(
            check_id="C1",
            severity="BLOCK",
            message="unseeded randomness",
            file="src/strategy.py",
            line=42,
        )
        d = f.to_dict()
        restored = PrecheckFinding.from_dict(d)
        assert restored == f

    def test_from_dict_minimal(self) -> None:
        d = {"check_id": "N1", "severity": "WARN", "message": "missing facet"}
        f = PrecheckFinding.from_dict(d)
        assert f.check_id == "N1"
        assert f.file is None
        assert f.line is None


# ---------------------------------------------------------------------------
# Hardening tests (#1182, #1183, #1184)
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    """Verify write_request/write_verdict use atomic temp+fsync+replace."""

    def test_write_request_creates_valid_json(self, tmp_path: Path) -> None:
        req = ReviewRequest(
            pr_number=42, head_sha="sha1", branch="feat/x", requester="a"
        )
        write_request(req, tmp_path, emit_event=False)
        path = request_path(42, tmp_path)
        data = json.loads(path.read_text())
        assert data["pr_number"] == 42

    def test_write_verdict_creates_valid_json(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42, reviewed_sha="sha1", status="passed", reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)
        path = verdict_path(42, tmp_path)
        data = json.loads(path.read_text())
        assert data["status"] == "passed"

    def test_no_tmp_files_left_on_success(self, tmp_path: Path) -> None:
        """Atomic writes should not leave .tmp files on success."""
        v = ReviewVerdict(
            pr_number=42, reviewed_sha="sha1", status="passed", reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)
        pr_slot = tmp_path / "pr_42"
        tmp_files = list(pr_slot.glob("*.tmp"))
        assert tmp_files == []


class TestCorruptFileHandling:
    """Verify corrupt files return None instead of crashing (#1182)."""

    def test_corrupt_request_returns_none(self, tmp_path: Path) -> None:
        slot = tmp_path / "pr_42"
        slot.mkdir(parents=True)
        (slot / "request.json").write_text("not json {{{")
        result = read_request(42, tmp_path)
        assert result is None

    def test_corrupt_verdict_returns_none(self, tmp_path: Path) -> None:
        slot = tmp_path / "pr_42"
        slot.mkdir(parents=True)
        (slot / "verdict.json").write_text("not json {{{")
        result = read_verdict(42, tmp_path)
        assert result is None

    def test_empty_verdict_file_returns_none(self, tmp_path: Path) -> None:
        slot = tmp_path / "pr_42"
        slot.mkdir(parents=True)
        (slot / "verdict.json").write_text("")
        result = read_verdict(42, tmp_path)
        assert result is None

    def test_truncated_json_returns_none(self, tmp_path: Path) -> None:
        slot = tmp_path / "pr_42"
        slot.mkdir(parents=True)
        (slot / "verdict.json").write_text('{"pr_number": 42, "reviewed_sha"')
        result = read_verdict(42, tmp_path)
        assert result is None


class TestVerdictWriterField:
    """Verify writer field discrimination (#1184)."""

    def test_writer_field_round_trip(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="sha1",
            status="passed",
            reason="clean",
            writer="review_driver",
        )
        write_verdict(v, tmp_path, emit_event=False, lane_id="review_driver")
        loaded = read_verdict(42, tmp_path)
        assert loaded is not None
        assert loaded.writer == "review_driver"

    def test_writer_defaults_to_empty(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42, reviewed_sha="sha1", status="passed", reason="clean"
        )
        assert v.writer == ""

    def test_lane_id_threaded_to_writer(self, tmp_path: Path) -> None:
        """write_verdict should set writer from lane_id if not already set."""
        v = ReviewVerdict(
            pr_number=42, reviewed_sha="sha1", status="passed", reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False, lane_id="review")
        loaded = read_verdict(42, tmp_path)
        assert loaded is not None
        assert loaded.writer == "review"

    def test_explicit_writer_not_overridden(self, tmp_path: Path) -> None:
        """If verdict already has a writer, lane_id should not override it."""
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="sha1",
            status="passed",
            reason="clean",
            writer="original_writer",
        )
        write_verdict(v, tmp_path, emit_event=False, lane_id="other")
        loaded = read_verdict(42, tmp_path)
        assert loaded is not None
        assert loaded.writer == "original_writer"
