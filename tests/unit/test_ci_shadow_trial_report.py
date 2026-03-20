"""Tests for CI shadow sharding trial reporting."""

from __future__ import annotations

import sys
from pathlib import Path

# Import the script from scripts/internal
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"
sys.path.insert(0, str(SCRIPTS_DIR))

from ci_shadow_trial_report import (  # noqa: E402
    COMMENT_MARKER,
    ROLLING_SAMPLE_SIZE,
    build_rolling_summary,
    duration_seconds,
    extract_trial_record,
    find_existing_comment_id,
    format_duration,
    render_comment,
)


def _job(name: str, conclusion: str, started: str, completed: str) -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": completed,
    }


def _run(run_id: int, pr_number: int, conclusion: str = "success") -> dict:
    return {
        "id": run_id,
        "run_number": 100 + run_id,
        "html_url": f"https://github.com/example/repo/actions/runs/{run_id}",
        "conclusion": conclusion,
        "workflow_id": 1234,
        "pull_requests": [{"number": pr_number}],
    }


def test_duration_seconds_computes_wall_clock() -> None:
    assert duration_seconds("2026-03-20T12:00:00Z", "2026-03-20T12:04:17Z") == 257.0


def test_format_duration_renders_minutes_and_seconds() -> None:
    assert format_duration(257.0) == "4m17s"
    assert format_duration(466.0) == "7m46s"
    assert format_duration(None) == "n/a"


def test_extract_trial_record_picks_tracked_jobs_and_shards() -> None:
    run = _run(1, 1050)
    jobs = [
        _job("tests", "success", "2026-03-20T12:00:00Z", "2026-03-20T12:07:46Z"),
        _job(
            "governance",
            "success",
            "2026-03-20T12:00:00Z",
            "2026-03-20T12:00:07Z",
        ),
        _job(
            "tests-shadow-shard (1)",
            "success",
            "2026-03-20T12:00:00Z",
            "2026-03-20T12:04:17Z",
        ),
        _job(
            "tests-shadow-shard (2)",
            "success",
            "2026-03-20T12:00:00Z",
            "2026-03-20T12:03:55Z",
        ),
    ]

    record = extract_trial_record(run, jobs)

    assert record.pr_number == 1050
    assert record.tests is not None
    assert record.tests.duration_seconds == 466.0
    assert record.shards[1].duration_seconds == 257.0
    assert record.shards[2].duration_seconds == 235.0
    assert record.projected_wall_clock_seconds == 257.0
    assert record.savings_seconds == 209.0
    assert record.is_successful_datapoint is True


def test_build_rolling_summary_averages_successful_datapoints() -> None:
    run1 = extract_trial_record(
        _run(1, 1050),
        [
            _job("tests", "success", "2026-03-20T12:00:00Z", "2026-03-20T12:07:46Z"),
            _job(
                "tests-shadow-shard (1)",
                "success",
                "2026-03-20T12:00:00Z",
                "2026-03-20T12:04:17Z",
            ),
            _job(
                "tests-shadow-shard (2)",
                "success",
                "2026-03-20T12:00:00Z",
                "2026-03-20T12:03:55Z",
            ),
        ],
    )
    run2 = extract_trial_record(
        _run(2, 1051),
        [
            _job("tests", "success", "2026-03-21T12:00:00Z", "2026-03-21T12:08:00Z"),
            _job(
                "tests-shadow-shard (1)",
                "success",
                "2026-03-21T12:00:00Z",
                "2026-03-21T12:04:10Z",
            ),
            _job(
                "tests-shadow-shard (2)",
                "success",
                "2026-03-21T12:00:00Z",
                "2026-03-21T12:03:50Z",
            ),
        ],
    )

    summary = build_rolling_summary([run1, run2])

    assert summary["count"] == 2
    assert summary["avg_serial_seconds"] == 473.0
    assert summary["avg_projected_seconds"] == 253.5
    assert summary["avg_savings_seconds"] == 219.5
    assert round(summary["avg_savings_percent"], 1) == 46.4


def test_render_comment_contains_marker_and_summary_table() -> None:
    current = extract_trial_record(
        _run(1, 1050),
        [
            _job("tests", "success", "2026-03-20T12:00:00Z", "2026-03-20T12:07:46Z"),
            _job(
                "governance",
                "success",
                "2026-03-20T12:00:00Z",
                "2026-03-20T12:00:07Z",
            ),
            _job(
                "tests-shadow-shard (1)",
                "success",
                "2026-03-20T12:00:00Z",
                "2026-03-20T12:04:17Z",
            ),
            _job(
                "tests-shadow-shard (2)",
                "success",
                "2026-03-20T12:00:00Z",
                "2026-03-20T12:03:55Z",
            ),
        ],
    )
    rolling = build_rolling_summary([current])

    body = render_comment(current, rolling)

    assert COMMENT_MARKER in body
    assert "CI Shadow Shard Trial" in body
    assert "Projected sharded wall-clock: `4m17s`" in body
    assert "Projected savings vs serial: `3m29s`" in body
    assert "Successful data points collected: `1/5`" in body
    assert "| PR | Run | Serial | Shard 1 | Shard 2 | Projected | Savings |" in body


def test_rolling_summary_returns_full_count_when_current_not_successful() -> None:
    """B2 regression: rolling summary should return ROLLING_SAMPLE_SIZE records
    even when the current run is not a successful datapoint."""
    # Build 5 successful historical records
    records = []
    for i in range(ROLLING_SAMPLE_SIZE):
        record = extract_trial_record(
            _run(i + 1, 2000 + i),
            [
                _job(
                    "tests",
                    "success",
                    f"2026-03-2{i}T12:00:00Z",
                    f"2026-03-2{i}T12:08:00Z",
                ),
                _job(
                    "tests-shadow-shard (1)",
                    "success",
                    f"2026-03-2{i}T12:00:00Z",
                    f"2026-03-2{i}T12:04:00Z",
                ),
                _job(
                    "tests-shadow-shard (2)",
                    "success",
                    f"2026-03-2{i}T12:00:00Z",
                    f"2026-03-2{i}T12:03:50Z",
                ),
            ],
        )
        records.append(record)

    summary = build_rolling_summary(records)
    assert summary["count"] == ROLLING_SAMPLE_SIZE


def test_find_existing_comment_id_returns_none_for_empty_list(
    monkeypatch,
) -> None:
    """B1 regression: find_existing_comment_id should handle empty comment lists
    without errors."""
    import ci_shadow_trial_report as mod

    def mock_gh_get(_token, _path, *, params=None):
        return []

    monkeypatch.setattr(mod, "gh_get", mock_gh_get)
    result = find_existing_comment_id("fake-token", "owner/repo", 42)
    assert result is None
