"""Unit tests for scripts/internal/capture_steward_baseline.py.

Covers each section renderer with mocked data sources so the test is
hermetic (no subprocess calls to gh/git/ops.py). Asserts the expected
markdown shape, heading hierarchy, and §4.3 contract behaviors — in
particular that failing data sources produce an "insufficient data"
notice rather than a blank section.

Pattern 10 — surface named in task packet `103e85a19496` Validation:
`uv run python -m pytest tests/unit/test_capture_steward_baseline.py`.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from unittest.mock import patch

_SPEC = importlib.util.spec_from_file_location(
    "capture_steward_baseline",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "capture_steward_baseline.py",
)
assert _SPEC is not None and _SPEC.loader is not None
csb = importlib.util.module_from_spec(_SPEC)
sys.modules["capture_steward_baseline"] = csb
_SPEC.loader.exec_module(csb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_heading_numbers(md: str) -> list[int]:
    """Return the numeric prefix of every ## heading in order."""
    out: list[int] = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            out.append(int(m.group(1)))
    return out


# ---------------------------------------------------------------------------
# Individual section tests
# ---------------------------------------------------------------------------


def test_section_timestamp_is_iso8601_utc():
    md = csb.section_timestamp()
    assert md.startswith("## 1. Generated-at timestamp")
    # Match 2026-04-23T20:26:45Z inside backticks
    m = re.search(r"`(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)`", md)
    assert m is not None, f"no ISO8601 UTC timestamp found in:\n{md}"


def test_section_fleet_state_renders_when_dashboard_ok():
    fake = {
        "summary": {
            "foreground_lanes": 2,
            "background_lanes": 10,
            "attention_items": 0,
            "inbox_unacked": 5,
            "active_tasks": 3,
            "blocked_tasks": 0,
            "warnings": 1,
        },
        "inbox_highlights": [
            {"lane_id": "author-a", "unacked_count": 3, "oldest_unacked_age": "1h ago"}
        ],
    }
    with patch.object(csb, "_ops_json", return_value=fake):
        md = csb.section_fleet_state()
    assert md.startswith("## 2. Fleet lane state")
    assert "foreground_lanes" in md and "| 2 |" in md
    assert "author-a" in md and "1h ago" in md


def test_section_fleet_state_handles_missing_data():
    with patch.object(csb, "_ops_json", return_value=None):
        md = csb.section_fleet_state()
    assert md.startswith("## 2. Fleet lane state")
    assert "Insufficient data at capture time" in md


def test_section_token_snapshot_renders_summary():
    fake = {
        "store_status": {
            "session_count": 100,
            "last_import_timestamp": "2026-04-01T00:00:00Z",
            "stale": False,
        },
        "summary": {
            "session_count": 100,
            "total_input_tokens": 1000,
            "total_output_tokens": 2000,
            "total_tokens": 3000,
            "total_git_commits": 10,
            "total_git_pushes": 8,
            "total_duration_minutes": 500,
            "time_range_start": "2026-03-01",
            "time_range_end": "2026-04-01",
        },
    }
    with patch.object(csb, "_ops_json", return_value=fake):
        md = csb.section_token_snapshot()
    assert md.startswith("## 3. Token economy snapshot")
    assert "3000" in md  # total_tokens


def test_section_token_snapshot_handles_missing_data():
    with patch.object(csb, "_ops_json", return_value=None):
        md = csb.section_token_snapshot()
    assert "Insufficient data at capture time" in md


def test_section_pr_velocity_filters_to_30d_window():
    import json as _json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=5)).isoformat().replace("+00:00", "Z")
    old = (now - timedelta(days=90)).isoformat().replace("+00:00", "Z")
    fake_prs = [
        {"number": 1, "state": "MERGED", "mergedAt": recent, "createdAt": recent},
        {"number": 2, "state": "MERGED", "mergedAt": recent, "createdAt": recent},
        {
            "number": 3,
            "state": "OPEN",
            "mergedAt": None,
            "createdAt": recent,
            "closedAt": None,
        },
        {
            "number": 4,
            "state": "MERGED",
            "mergedAt": old,
            "createdAt": old,
        },  # out of window
    ]
    with patch.object(csb, "_run", return_value=(0, _json.dumps(fake_prs), "")):
        md = csb.section_pr_velocity()
    assert md.startswith("## 4. PR velocity")
    # Two in-window merged
    assert "| MERGED | 2 |" in md
    assert "| OPEN | 1 |" in md


def test_section_pr_velocity_handles_gh_failure():
    with patch.object(csb, "_run", return_value=(1, "", "boom")):
        md = csb.section_pr_velocity()
    assert "Insufficient data at capture time" in md


def test_section_issue_state_counts_bot_vs_human():
    import json as _json
    from datetime import datetime, timedelta, timezone

    recent = (
        (datetime.now(timezone.utc) - timedelta(days=2))
        .isoformat()
        .replace("+00:00", "Z")
    )
    fake = [
        {
            "number": 1,
            "state": "OPEN",
            "labels": [{"name": "bug"}],
            "createdAt": recent,
            "author": {"is_bot": False},
        },
        {
            "number": 2,
            "state": "CLOSED",
            "labels": [{"name": "bug"}, {"name": "follow-up"}],
            "createdAt": recent,
            "author": {"is_bot": True},
        },
    ]
    with patch.object(csb, "_run", return_value=(0, _json.dumps(fake), "")):
        md = csb.section_issue_state()
    assert md.startswith("## 5. Issue state")
    assert "| human | 1 |" in md
    assert "| bot | 1 |" in md
    assert "| bug | 2 |" in md


def test_section_commit_velocity_counts_lines():
    # First call: git log --oneline
    # Second call: git log --format=%an
    def fake_run(cmd, **kw):
        if "--oneline" in cmd:
            return (0, "abc123 one\ndef456 two\nghi789 three\n", "")
        if "--format=%an" in cmd:
            return (0, "Alice\nAlice\nBob\n", "")
        return (1, "", "")

    with patch.object(csb, "_run", side_effect=fake_run):
        md = csb.section_commit_velocity()
    assert md.startswith("## 6. Commit velocity")
    assert "**3**" in md
    assert "| Alice | 2 |" in md
    assert "| Bob | 1 |" in md


def test_section_event_schema_reads_jsonl(tmp_path, monkeypatch):
    events_dir = tmp_path / ".claude" / "runtime" / "events"
    events_dir.mkdir(parents=True)
    events_file = events_dir / "events.jsonl"
    import json as _json

    with events_file.open("w", encoding="utf-8") as fh:
        fh.write(_json.dumps({"event_type": "message_sent"}) + "\n")
        fh.write(_json.dumps({"event_type": "message_sent"}) + "\n")
        fh.write(_json.dumps({"event_type": "task_started"}) + "\n")
        fh.write("\n")  # blank line ok
        fh.write("not json\n")  # malformed ok — skipped

    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    md = csb.section_event_schema()
    assert md.startswith("## 7. Event schema shape")
    assert "Total events observed: **3**" in md
    assert "Distinct event types: **2**" in md
    assert "`message_sent`" in md


def test_section_event_schema_handles_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    md = csb.section_event_schema()
    assert "Insufficient data at capture time" in md


def test_section_lane_model_effort_renders_all_three():
    def fake_ops(args):
        if args == ["usage", "by-model"]:
            return {
                "buckets": [
                    {
                        "model": "sonnet",
                        "session_count": 10,
                        "total_tokens": 1000,
                        "git_commits": 5,
                    }
                ],
                "unknown_fraction": 0.1,
            }
        if args == ["usage", "by-effort"]:
            return {
                "buckets": [
                    {
                        "effort": "medium",
                        "session_count": 10,
                        "total_tokens": 1000,
                        "git_commits": 5,
                    }
                ]
            }
        if args == ["usage", "lanes"]:
            return [
                {
                    "lane_id": "author-a",
                    "pool": "platform",
                    "session_count": 10,
                    "total_tokens": 1000,
                    "tokens_per_commit": 100.0,
                }
            ]
        return None

    with patch.object(csb, "_ops_json", side_effect=fake_ops):
        md = csb.section_lane_model_effort()
    assert md.startswith("## 8. Lane × model × effort rollup")
    assert "sonnet" in md
    assert "medium" in md
    assert "author-a" in md


def test_section_lane_model_effort_handles_all_missing():
    with patch.object(csb, "_ops_json", return_value=None):
        md = csb.section_lane_model_effort()
    assert "Insufficient data at capture time" in md


def test_section_plan_inventory_counts_md(tmp_path, monkeypatch):
    (tmp_path / "plans" / "alpha").mkdir(parents=True)
    (tmp_path / "plans" / "beta").mkdir(parents=True)
    (tmp_path / "plans" / "alpha" / "one.md").write_text("x")
    (tmp_path / "plans" / "alpha" / "two.md").write_text("x")
    (tmp_path / "plans" / "beta" / "three.md").write_text("x")
    (tmp_path / "plans" / "root.md").write_text("x")
    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    md = csb.section_plan_inventory()
    assert md.startswith("## 9. Plan artifact inventory")
    assert "Total `.md` files under `plans/`: **4**" in md
    assert "| `alpha` | 2 |" in md
    assert "| `beta` | 1 |" in md


def test_section_crons_note_is_constant():
    md = csb.section_crons_note()
    assert md.startswith("## 10. Active crons")
    assert "session-scoped" in md


# ---------------------------------------------------------------------------
# Top-level composition
# ---------------------------------------------------------------------------


def test_build_baseline_has_header_and_10_sections(monkeypatch, tmp_path):
    # Null out side-effecting calls
    monkeypatch.setattr(csb, "_ops_json", lambda args: None)
    monkeypatch.setattr(csb, "_run", lambda cmd, timeout=30: (1, "", ""))
    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    md = csb.build_baseline()
    assert md.startswith("# Steward Platform Phase 0 Baseline")
    assert "§4.3" in md
    nums = _all_heading_numbers(md)
    assert nums == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_build_baseline_at_least_8_sections_with_live_defaults(monkeypatch, tmp_path):
    # Even in total-failure mode (all adapters missing), contract says
    # ≥8 sections present — no blanks.
    monkeypatch.setattr(csb, "_ops_json", lambda args: None)
    monkeypatch.setattr(csb, "_run", lambda cmd, timeout=30: (1, "", ""))
    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    md = csb.build_baseline()
    section_count = md.count("\n## ")
    assert section_count >= 8, f"only {section_count} sections in:\n{md}"


def test_main_writes_to_stdout(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(csb, "_ops_json", lambda args: None)
    monkeypatch.setattr(csb, "_run", lambda cmd, timeout=30: (1, "", ""))
    monkeypatch.setattr(csb, "REPO_ROOT", tmp_path)
    rc = csb.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("# Steward Platform Phase 0 Baseline")
    assert "## 1." in captured.out
