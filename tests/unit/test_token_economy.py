"""Tests for token_economy — JSONL project telemetry scanner (v2 schema).

Covers the new per-project JSONL import path added for #1770, plus
existing public API surface.
"""

from __future__ import annotations

import json
from pathlib import Path

from bid_euchre.ops.token_economy import (
    _STALE_THRESHOLD_SECONDS,
    SCHEMA_VERSION,
    SessionRecord,
    StoreStatus,
    _build_record_from_jsonl,
    _compute_duration_minutes,
    _infer_lane_from_slug,
    _JNLSessionAgg,
    _purge_jsonl_records,
    _safe_int,
    _scan_jsonl_file,
    import_project_jsonl,
    import_usage_data,
    infer_lane_from_path,
    store_status,
)

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_schema_version_is_2():
    """Schema version must be 2 after the JSONL scanner addition."""
    assert SCHEMA_VERSION == 2


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------


class TestSafeInt:
    def test_none_returns_zero(self):
        assert _safe_int(None) == 0

    def test_int_passthrough(self):
        assert _safe_int(42) == 42

    def test_string_number(self):
        assert _safe_int("10") == 10

    def test_non_numeric_string(self):
        assert _safe_int("abc") == 0

    def test_float_truncates(self):
        assert _safe_int(3.7) == 3

    def test_zero(self):
        assert _safe_int(0) == 0


# ---------------------------------------------------------------------------
# _compute_duration_minutes
# ---------------------------------------------------------------------------


class TestComputeDurationMinutes:
    def test_valid_timestamps(self):
        result = _compute_duration_minutes(
            "2026-03-25T10:00:00.000Z",
            "2026-03-25T10:30:00.000Z",
        )
        assert result == 30

    def test_minimum_one_minute(self):
        """Sessions shorter than 1 minute still return 1."""
        result = _compute_duration_minutes(
            "2026-03-25T10:00:00.000Z",
            "2026-03-25T10:00:10.000Z",
        )
        assert result == 1

    def test_empty_timestamps(self):
        assert _compute_duration_minutes("", "") is None
        assert _compute_duration_minutes("", "2026-03-25T10:00:00Z") is None
        assert _compute_duration_minutes("2026-03-25T10:00:00Z", "") is None

    def test_invalid_timestamps(self):
        assert _compute_duration_minutes("not-a-date", "also-not") is None


# ---------------------------------------------------------------------------
# _infer_lane_from_slug
# ---------------------------------------------------------------------------


class TestInferLaneFromSlug:
    def test_author_a(self):
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-author"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "author-a"
        assert wt_name == "Bid-Euchre-steward-author"

    def test_author_b(self):
        slug = (
            "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-author-b"
        )
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "author-b"
        assert wt_name == "Bid-Euchre-steward-author-b"

    def test_ops(self):
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-ops"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "ops"
        assert wt_name == "Bid-Euchre-steward-ops"

    def test_review(self):
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-review"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "review"
        assert wt_name == "Bid-Euchre-steward-review"

    def test_analyst_a(self):
        slug = (
            "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-analyst"
        )
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "analyst-a"
        assert wt_name == "Bid-Euchre-steward-analyst"

    def test_browser_author_a(self):
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre-steward-brws-author-a"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "brws-author-a"
        assert wt_name == "Bid-Euchre-steward-brws-author-a"

    def test_flex_b(self):
        slug = "-Users-foo-Bid-Euchre-steward-flex-b"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "flex-b"
        assert wt_name == "Bid-Euchre-steward-flex-b"

    def test_main_checkout(self):
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id == "main-checkout"
        assert wt_name == "Bid-Euchre"

    def test_unknown_project(self):
        slug = "-Users-someone-Projects-other-repo"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        assert lane_id is None
        assert wt_name is None

    def test_empty_slug(self):
        lane_id, wt_name = _infer_lane_from_slug("")
        assert lane_id is None
        assert wt_name is None

    def test_longest_match_wins(self):
        """author-b must not match author (shorter suffix)."""
        slug = "-X-Bid-Euchre-steward-author-b"
        lane_id, _ = _infer_lane_from_slug(slug)
        assert lane_id == "author-b"

    def test_worktree_slug_for_old_worktrees(self):
        """Claude worktree slugs (with --claude-worktrees-- component)."""
        slug = "-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre--claude-worktrees-fix-review"
        lane_id, wt_name = _infer_lane_from_slug(slug)
        # Not a known steward worktree → unmatched
        assert lane_id is None
        assert wt_name is None


# ---------------------------------------------------------------------------
# _scan_jsonl_file
# ---------------------------------------------------------------------------


def _make_assistant_msg(
    session_id: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation: int = 0,
    cache_read: int = 0,
    timestamp: str = "2026-03-25T10:00:00.000Z",
    cwd: str = "/Users/test/Bid-Euchre-steward-author",
) -> str:
    """Create a JSONL line for an assistant message with usage data."""
    obj = {
        "type": "assistant",
        "sessionId": session_id,
        "timestamp": timestamp,
        "cwd": cwd,
        "gitBranch": "main",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "service_tier": "standard",
            },
        },
    }
    return json.dumps(obj)


def _make_user_msg(
    session_id: str,
    timestamp: str = "2026-03-25T09:59:00.000Z",
    is_meta: bool = False,
) -> str:
    """Create a JSONL line for a user message."""
    obj = {
        "type": "user",
        "sessionId": session_id,
        "timestamp": timestamp,
        "cwd": "/Users/test/Bid-Euchre-steward-author",
        "isMeta": is_meta,
        "message": {"role": "user", "content": "test"},
    }
    return json.dumps(obj)


def _make_assistant_msg_with_tool(
    session_id: str,
    tool_name: str,
    command: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    timestamp: str = "2026-03-25T10:05:00.000Z",
) -> str:
    """Create a JSONL line for an assistant message containing a tool_use block."""
    obj = {
        "type": "assistant",
        "sessionId": session_id,
        "timestamp": timestamp,
        "cwd": "/Users/test/Bid-Euchre-steward-author",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Running command..."},
                {
                    "type": "tool_use",
                    "id": "tool-001",
                    "name": tool_name,
                    "input": {"command": command},
                },
            ],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        },
    }
    return json.dumps(obj)


def _make_system_msg(session_id: str) -> str:
    """Create a JSONL line for a system message."""
    obj = {
        "type": "system",
        "sessionId": session_id,
        "timestamp": "2026-03-25T09:58:00.000Z",
        "content": "system info",
    }
    return json.dumps(obj)


class TestScanJsonlFile:
    def test_basic_aggregation(self, tmp_path: Path):
        """Aggregates token counts across multiple assistant messages."""
        sid = "sess-001"
        lines = [
            _make_user_msg(sid, timestamp="2026-03-25T10:00:00Z"),
            _make_assistant_msg(
                sid,
                input_tokens=100,
                output_tokens=50,
                timestamp="2026-03-25T10:01:00Z",
            ),
            _make_user_msg(sid, timestamp="2026-03-25T10:02:00Z"),
            _make_assistant_msg(
                sid,
                input_tokens=200,
                output_tokens=75,
                timestamp="2026-03-25T10:03:00Z",
            ),
        ]
        f = tmp_path / "sess-001.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.session_id == sid
        assert agg.input_tokens == 300
        assert agg.output_tokens == 125
        assert agg.user_message_count == 2
        assert agg.assistant_message_count == 2

    def test_cache_tokens_accumulated(self, tmp_path: Path):
        sid = "sess-002"
        lines = [
            _make_assistant_msg(sid, cache_creation=5000, cache_read=1000),
            _make_assistant_msg(sid, cache_creation=3000, cache_read=2000),
        ]
        f = tmp_path / "sess-002.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.cache_creation_tokens == 8000
        assert agg.cache_read_tokens == 3000

    def test_meta_messages_not_counted_as_user(self, tmp_path: Path):
        """isMeta user messages should not increment user_message_count."""
        sid = "sess-003"
        lines = [
            _make_user_msg(sid, is_meta=True),
            _make_user_msg(sid, is_meta=False),
            _make_assistant_msg(sid),
        ]
        f = tmp_path / "sess-003.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.user_message_count == 1  # only non-meta

    def test_empty_file_returns_none(self, tmp_path: Path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        assert _scan_jsonl_file(f) is None

    def test_no_assistant_messages_returns_none(self, tmp_path: Path):
        sid = "sess-004"
        lines = [_make_user_msg(sid), _make_system_msg(sid)]
        f = tmp_path / "sess-004.jsonl"
        f.write_text("\n".join(lines) + "\n")

        assert _scan_jsonl_file(f) is None

    def test_malformed_json_lines_skipped(self, tmp_path: Path):
        sid = "sess-005"
        lines = [
            "not json at all",
            _make_assistant_msg(sid, input_tokens=100, output_tokens=50),
            "{invalid json",
            _make_assistant_msg(sid, input_tokens=200, output_tokens=25),
        ]
        f = tmp_path / "sess-005.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.input_tokens == 300
        assert agg.output_tokens == 75

    def test_timestamps_tracked(self, tmp_path: Path):
        sid = "sess-006"
        lines = [
            _make_user_msg(sid, timestamp="2026-03-25T10:00:00Z"),
            _make_assistant_msg(sid, timestamp="2026-03-25T10:30:00Z"),
        ]
        f = tmp_path / "sess-006.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.first_timestamp == "2026-03-25T10:00:00Z"
        assert agg.last_timestamp == "2026-03-25T10:30:00Z"

    def test_cwd_captured(self, tmp_path: Path):
        sid = "sess-007"
        lines = [
            _make_assistant_msg(sid, cwd="/Users/test/Projects/Bid-Euchre-steward-ops"),
        ]
        f = tmp_path / "sess-007.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.cwd == "/Users/test/Projects/Bid-Euchre-steward-ops"

    def test_nonexistent_file_returns_none(self, tmp_path: Path):
        f = tmp_path / "does-not-exist.jsonl"
        assert _scan_jsonl_file(f) is None

    def test_git_commits_counted(self, tmp_path: Path):
        """Scanner counts git commit tool_use blocks."""
        sid = "sess-gc-1"
        lines = [
            _make_assistant_msg(sid),
            _make_assistant_msg_with_tool(
                sid, "Bash", 'git commit -m "fix: something"'
            ),
            _make_assistant_msg_with_tool(sid, "Bash", 'git commit -m "feat: another"'),
        ]
        f = tmp_path / "sess-gc-1.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.git_commits == 2
        assert agg.git_pushes == 0

    def test_git_pushes_counted(self, tmp_path: Path):
        """Scanner counts git push tool_use blocks."""
        sid = "sess-gc-2"
        lines = [
            _make_assistant_msg(sid),
            _make_assistant_msg_with_tool(
                sid, "Bash", "git push -u origin fix/something"
            ),
        ]
        f = tmp_path / "sess-gc-2.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.git_commits == 0
        assert agg.git_pushes == 1

    def test_git_commit_and_push_in_single_command(self, tmp_path: Path):
        """A chained command with both git commit and git push counts both."""
        sid = "sess-gc-3"
        lines = [
            _make_assistant_msg(sid),
            _make_assistant_msg_with_tool(
                sid,
                "Bash",
                'git commit -m "fix: thing" && git push -u origin branch',
            ),
        ]
        f = tmp_path / "sess-gc-3.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.git_commits == 1
        assert agg.git_pushes == 1

    def test_non_bash_tool_not_counted(self, tmp_path: Path):
        """Only Bash tool invocations are checked for git commands."""
        sid = "sess-gc-4"
        # A non-Bash tool with "git commit" in its input should not count
        obj = {
            "type": "assistant",
            "sessionId": sid,
            "timestamp": "2026-03-25T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-x",
                        "name": "Edit",
                        "input": {"command": "git commit -m 'edit'"},
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }
        lines = [json.dumps(obj)]
        f = tmp_path / "sess-gc-4.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.git_commits == 0

    def test_zero_commits_when_no_tool_use(self, tmp_path: Path):
        """Sessions without tool_use blocks have zero git_commits."""
        sid = "sess-gc-5"
        lines = [
            _make_user_msg(sid),
            _make_assistant_msg(sid),
        ]
        f = tmp_path / "sess-gc-5.jsonl"
        f.write_text("\n".join(lines) + "\n")

        agg = _scan_jsonl_file(f)
        assert agg is not None
        assert agg.git_commits == 0
        assert agg.git_pushes == 0


# ---------------------------------------------------------------------------
# _build_record_from_jsonl
# ---------------------------------------------------------------------------


class TestBuildRecordFromJsonl:
    def test_basic_record(self, tmp_path: Path):
        agg = _JNLSessionAgg(
            session_id="sess-100",
            input_tokens=1000,
            output_tokens=500,
            user_message_count=5,
            assistant_message_count=10,
            first_timestamp="2026-03-25T10:00:00Z",
            last_timestamp="2026-03-25T10:30:00Z",
            cwd="/Users/test/Bid-Euchre-steward-author",
        )
        rec = _build_record_from_jsonl(
            agg,
            source_path=tmp_path / "test.jsonl",
            source_hash="abc123",
            now="2026-03-25T12:00:00Z",
            lane_id="author-a",
        )
        assert rec.session_id == "sess-100"
        assert rec.source_type == "project-jsonl"
        assert rec.input_tokens == 1000
        assert rec.output_tokens == 500
        assert rec.user_message_count == 5
        assert rec.assistant_message_count == 10
        assert rec.duration_minutes == 30
        assert rec.project_path == "/Users/test/Bid-Euchre-steward-author"
        assert rec.schema_version == 2

    def test_missing_cwd_uses_inferred_lane(self, tmp_path: Path):
        agg = _JNLSessionAgg(
            session_id="sess-101",
            input_tokens=100,
            output_tokens=50,
            cwd="",
        )
        rec = _build_record_from_jsonl(
            agg,
            source_path=tmp_path / "test.jsonl",
            source_hash="def456",
            now="2026-03-25T12:00:00Z",
            lane_id="author-b",
        )
        assert rec.project_path == "<inferred-lane:author-b>"

    def test_git_commits_propagated(self, tmp_path: Path):
        """Git commit counts from the scanner flow through to the record."""
        agg = _JNLSessionAgg(
            session_id="sess-102",
            input_tokens=500,
            output_tokens=200,
            git_commits=3,
            git_pushes=2,
        )
        rec = _build_record_from_jsonl(
            agg,
            source_path=tmp_path / "test.jsonl",
            source_hash="ghi789",
            now="2026-03-25T12:00:00Z",
            lane_id="author-a",
        )
        assert rec.git_commits == 3
        assert rec.git_pushes == 2

    def test_zero_git_commits_stored_as_none(self, tmp_path: Path):
        """Sessions with zero commits store git_commits as None (sparse)."""
        agg = _JNLSessionAgg(
            session_id="sess-103",
            input_tokens=100,
            output_tokens=50,
            git_commits=0,
            git_pushes=0,
        )
        rec = _build_record_from_jsonl(
            agg,
            source_path=tmp_path / "test.jsonl",
            source_hash="jkl012",
            now="2026-03-25T12:00:00Z",
            lane_id=None,
        )
        assert rec.git_commits is None
        assert rec.git_pushes is None


# ---------------------------------------------------------------------------
# _purge_jsonl_records
# ---------------------------------------------------------------------------


class TestPurgeJsonlRecords:
    def test_purges_project_jsonl_keeps_session_meta(self, tmp_path: Path):
        """Purge removes project-jsonl records but keeps session-meta."""
        usage_file = tmp_path / "session_usage.jsonl"
        records = [
            json.dumps({"session_id": "s1", "source_type": "session-meta"}),
            json.dumps({"session_id": "s2", "source_type": "project-jsonl"}),
            json.dumps({"session_id": "s3", "source_type": "project-jsonl"}),
            json.dumps({"session_id": "s4", "source_type": "session-meta"}),
        ]
        usage_file.write_text("\n".join(records) + "\n")

        removed = _purge_jsonl_records(tmp_path)
        assert removed == 2

        remaining = [
            json.loads(line) for line in usage_file.read_text().strip().splitlines()
        ]
        assert len(remaining) == 2
        assert all(r["source_type"] == "session-meta" for r in remaining)

    def test_purge_empty_store(self, tmp_path: Path):
        """Purge on empty store returns 0."""
        assert _purge_jsonl_records(tmp_path) == 0

    def test_purge_no_jsonl_records(self, tmp_path: Path):
        """Purge when all records are session-meta removes nothing."""
        usage_file = tmp_path / "session_usage.jsonl"
        records = [
            json.dumps({"session_id": "s1", "source_type": "session-meta"}),
        ]
        usage_file.write_text("\n".join(records) + "\n")

        removed = _purge_jsonl_records(tmp_path)
        assert removed == 0

        remaining = usage_file.read_text().strip().splitlines()
        assert len(remaining) == 1


# ---------------------------------------------------------------------------
# import_project_jsonl (integration with tmp_path)
# ---------------------------------------------------------------------------


class TestImportProjectJsonl:
    def _setup_project_dir(
        self, tmp_path: Path, slug: str, sessions: dict[str, list[str]]
    ) -> Path:
        """Create a fake project directory structure.

        Parameters
        ----------
        sessions
            Mapping of session_id -> list of JSONL lines.
        """
        projects_dir = tmp_path / "projects"
        slug_dir = projects_dir / slug
        slug_dir.mkdir(parents=True)
        for sid, lines in sessions.items():
            (slug_dir / f"{sid}.jsonl").write_text("\n".join(lines) + "\n")
        return projects_dir

    def test_basic_import(self, tmp_path: Path):
        sid = "sess-200"
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-author",
            {
                sid: [
                    _make_user_msg(sid),
                    _make_assistant_msg(sid, input_tokens=1000, output_tokens=500),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)
        assert result.sessions_imported == 1
        assert result.sessions_skipped == 0
        assert result.total_files_scanned == 1
        assert result.directories_scanned == 1

        # Verify the session was written to session_usage.jsonl
        usage_file = output_dir / "session_usage.jsonl"
        assert usage_file.exists()
        records = [json.loads(l) for l in usage_file.read_text().strip().split("\n")]
        assert len(records) == 1
        assert records[0]["session_id"] == sid
        assert records[0]["source_type"] == "project-jsonl"
        assert records[0]["input_tokens"] == 1000
        assert records[0]["output_tokens"] == 500

    def test_idempotent_import(self, tmp_path: Path):
        """Running import twice should not duplicate sessions."""
        sid = "sess-201"
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-ops",
            {
                sid: [
                    _make_assistant_msg(sid, input_tokens=100, output_tokens=50),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        r1 = import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)
        assert r1.sessions_imported == 1

        r2 = import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)
        assert r2.sessions_imported == 0
        assert r2.sessions_skipped == 1

        # Only one record in the file
        usage_file = output_dir / "session_usage.jsonl"
        lines = [l for l in usage_file.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 1

    def test_multiple_sessions_in_one_project(self, tmp_path: Path):
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-author-b",
            {
                "sess-300": [
                    _make_assistant_msg("sess-300", input_tokens=100, output_tokens=50),
                ],
                "sess-301": [
                    _make_assistant_msg("sess-301", input_tokens=200, output_tokens=75),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)
        assert result.sessions_imported == 2

    def test_empty_project_dir(self, tmp_path: Path):
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)
        assert result.sessions_imported == 0
        assert result.directories_scanned == 0

    def test_nonexistent_projects_dir(self, tmp_path: Path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = import_project_jsonl(
            projects_dir=tmp_path / "nonexistent", output_dir=output_dir
        )
        assert result.sessions_imported == 0
        assert result.total_files_scanned == 0

    def test_lane_inferred_from_slug(self, tmp_path: Path):
        """Lane should be inferrable via infer_lane_from_path on the cwd."""
        sid = "sess-400"
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-review",
            {
                sid: [
                    _make_assistant_msg(
                        sid,
                        cwd="/Users/test/Projects/Bid-Euchre-steward-review",
                    ),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)

        usage_file = output_dir / "session_usage.jsonl"
        records = [json.loads(l) for l in usage_file.read_text().strip().split("\n")]
        assert len(records) == 1
        assert (
            records[0]["project_path"]
            == "/Users/test/Projects/Bid-Euchre-steward-review"
        )

    def test_rollups_written(self, tmp_path: Path):
        """Rollup file should be created/updated after import."""
        sid = "sess-500"
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-author",
            {
                sid: [
                    _make_assistant_msg(sid, input_tokens=1000, output_tokens=500),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        import_project_jsonl(projects_dir=projects_dir, output_dir=output_dir)

        rollup_file = output_dir / "session_rollups.json"
        assert rollup_file.exists()
        rollup = json.loads(rollup_file.read_text())
        assert rollup["session_count"] == 1
        assert rollup["totals"]["input_tokens"] == 1000
        assert rollup["totals"]["output_tokens"] == 500

    def test_force_reimport_rebuilds_attributions(self, tmp_path: Path):
        """Force mode should recompute attributions after purging JSONL rows."""
        from unittest.mock import patch

        sid = "sess-600"
        projects_dir = self._setup_project_dir(
            tmp_path,
            "-Users-test-Bid-Euchre-steward-author",
            {
                sid: [
                    _make_assistant_msg(sid, input_tokens=200, output_tokens=100),
                ],
            },
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("bid_euchre.ops.token_economy.attribute_sessions") as mock_attr:
            import_project_jsonl(
                projects_dir=projects_dir,
                output_dir=output_dir,
                force=True,
            )

        mock_attr.assert_called_once_with(output_dir=output_dir)


# ---------------------------------------------------------------------------
# Existing infer_lane_from_path coverage (regression tests)
# ---------------------------------------------------------------------------


class TestInferLaneFromPath:
    def test_direct_worktree_match(self):
        lane, wt = infer_lane_from_path(
            "/Users/test/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author"
        )
        assert lane == "author-a"
        assert wt == "Bid-Euchre-steward-author"

    def test_ops_lane(self):
        lane, wt = infer_lane_from_path(
            "/Users/test/Projects/Bid-Euchre-meta/Bid-Euchre-steward-ops"
        )
        assert lane == "ops"
        assert wt == "Bid-Euchre-steward-ops"

    def test_none_path(self):
        lane, wt = infer_lane_from_path(None)
        assert lane is None
        assert wt is None

    def test_empty_path(self):
        lane, wt = infer_lane_from_path("")
        assert lane is None
        assert wt is None


# ---------------------------------------------------------------------------
# SessionRecord source_type field
# ---------------------------------------------------------------------------


class TestSessionRecordSourceType:
    def test_default_source_type(self):
        rec = SessionRecord(session_id="test-1")
        assert rec.source_type == "session-meta"

    def test_jsonl_source_type(self):
        rec = SessionRecord(session_id="test-2", source_type="project-jsonl")
        assert rec.source_type == "project-jsonl"


# ---------------------------------------------------------------------------
# import_usage_data (regression — existing functionality)
# ---------------------------------------------------------------------------


class TestImportUsageData:
    def test_no_session_meta_dir(self, tmp_path: Path):
        """When session-meta dir doesn't exist, returns zero counts."""
        usage_dir = tmp_path / "usage-data"
        usage_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_imported == 0
        assert result.total_sessions == 0

    def test_basic_session_meta_import(self, tmp_path: Path):
        """Import a single session-meta JSON file."""
        usage_dir = tmp_path / "usage-data"
        meta_dir = usage_dir / "session-meta"
        meta_dir.mkdir(parents=True)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Write a minimal session-meta file
        session = {
            "session_id": "meta-sess-001",
            "input_tokens": 500,
            "output_tokens": 200,
            "duration_minutes": 15,
        }
        (meta_dir / "meta-sess-001.json").write_text(json.dumps(session))

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_imported == 1
        assert result.sessions_skipped == 0


# ---------------------------------------------------------------------------
# store_status — staleness visibility and empty-store surfacing
# ---------------------------------------------------------------------------


def _write_session_rows(
    output_dir: Path, count: int, *, import_timestamp: str = "2026-04-20T00:00:00+00:00"
) -> None:
    """Write ``count`` minimal session rows with the given import_timestamp.

    Uses the public session_usage.jsonl schema (dict-per-line) so the tests
    exercise the same loader the production code uses.
    """
    usage_file = output_dir / "session_usage.jsonl"
    with usage_file.open("w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(
                json.dumps(
                    {
                        "session_id": f"s{i}",
                        "input_tokens": 100,
                        "output_tokens": 200,
                        "import_timestamp": import_timestamp,
                    }
                )
                + "\n"
            )


def _write_attr_rows(output_dir: Path, count: int) -> None:
    """Write ``count`` minimal attribution rows to session_attributions.jsonl."""
    attr_file = output_dir / "session_attributions.jsonl"
    with attr_file.open("w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(json.dumps({"session_id": f"s{i}", "lane_id": "author-a"}) + "\n")


class TestStoreStatus:
    """Verify store_status introspects without mutating and surfaces staleness."""

    def test_missing_store_reports_empty_and_stale(self, tmp_path: Path) -> None:
        status = store_status(output_dir=tmp_path)
        assert isinstance(status, StoreStatus)
        assert status.exists is False
        assert status.empty is True
        assert status.stale is True
        assert status.session_count == 0
        assert status.attributions_present is False
        assert status.usage_file_mtime is None
        assert status.age_seconds is None
        assert status.last_import_timestamp is None
        assert status.store_path == str(tmp_path)

    def test_empty_file_reports_empty(self, tmp_path: Path) -> None:
        (tmp_path / "session_usage.jsonl").write_text("")
        status = store_status(output_dir=tmp_path)
        assert status.exists is True
        assert status.empty is True
        # Empty file is still stale per the canonical predicate.
        assert status.stale is True
        assert status.session_count == 0

    def test_fresh_store_reports_not_stale(self, tmp_path: Path) -> None:
        _write_session_rows(tmp_path, count=3)
        _write_attr_rows(tmp_path, count=3)
        status = store_status(output_dir=tmp_path)
        assert status.exists is True
        assert status.empty is False
        assert status.stale is False
        assert status.session_count == 3
        assert status.attributions_present is True
        assert status.usage_file_mtime is not None
        # Just-written files should have near-zero age.
        assert status.age_seconds is not None
        assert status.age_seconds >= 0

    def test_aged_store_reports_stale(self, tmp_path: Path) -> None:
        """Staleness visibility: a usage file older than the threshold is stale.

        Simulates the "import ran a long time ago and was never refreshed"
        failure mode Slice A needs to make visible.
        """
        _write_session_rows(tmp_path, count=2)
        _write_attr_rows(tmp_path, count=2)
        usage_file = tmp_path / "session_usage.jsonl"
        # Backdate both mtime and atime beyond the stale threshold.
        old_ts = usage_file.stat().st_mtime - (_STALE_THRESHOLD_SECONDS + 60)
        import os as _os

        _os.utime(usage_file, (old_ts, old_ts))
        status = store_status(output_dir=tmp_path)
        assert status.exists is True
        assert status.empty is False
        assert (
            status.stale is True
        ), "Store older than threshold must be visible as stale"
        assert status.age_seconds is not None
        assert status.age_seconds > _STALE_THRESHOLD_SECONDS

    def test_missing_attributions_reports_stale(self, tmp_path: Path) -> None:
        """Usage present but attributions missing: store is stale."""
        _write_session_rows(tmp_path, count=1)
        # Intentionally omit attributions file.
        status = store_status(output_dir=tmp_path)
        assert status.attributions_present is False
        assert status.stale is True

    def test_last_import_timestamp_picks_maximum(self, tmp_path: Path) -> None:
        """last_import_timestamp is the max across all records."""
        usage_file = tmp_path / "session_usage.jsonl"
        rows = [
            {"session_id": "s1", "import_timestamp": "2026-04-18T10:00:00+00:00"},
            {"session_id": "s2", "import_timestamp": "2026-04-20T10:00:00+00:00"},
            {"session_id": "s3", "import_timestamp": "2026-04-19T10:00:00+00:00"},
        ]
        with usage_file.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        _write_attr_rows(tmp_path, count=3)
        status = store_status(output_dir=tmp_path)
        assert status.last_import_timestamp == "2026-04-20T10:00:00+00:00"

    def test_malformed_rows_do_not_crash_introspection(self, tmp_path: Path) -> None:
        """A single malformed line must not raise — introspection is best-effort."""
        usage_file = tmp_path / "session_usage.jsonl"
        usage_file.write_text(
            '{"session_id": "s1"}\n' "this is not json\n" '{"session_id": "s2"}\n',
            encoding="utf-8",
        )
        _write_attr_rows(tmp_path, count=2)
        status = store_status(output_dir=tmp_path)
        # Two valid rows counted; the malformed line is skipped.
        assert status.session_count == 2
        assert status.empty is False

    def test_introspection_does_not_mutate_store(self, tmp_path: Path) -> None:
        """Call twice and verify file mtimes are unchanged."""
        _write_session_rows(tmp_path, count=1)
        _write_attr_rows(tmp_path, count=1)
        usage_file = tmp_path / "session_usage.jsonl"
        attr_file = tmp_path / "session_attributions.jsonl"
        mtime_before = (usage_file.stat().st_mtime, attr_file.stat().st_mtime)
        store_status(output_dir=tmp_path)
        store_status(output_dir=tmp_path)
        mtime_after = (usage_file.stat().st_mtime, attr_file.stat().st_mtime)
        assert mtime_before == mtime_after
