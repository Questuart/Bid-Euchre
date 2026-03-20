#!/usr/bin/env python3
"""Post-CI reporter for the shadow sharding trial.

Triggered from a ``workflow_run`` event after the ``CI`` workflow completes on a
pull request. The reporter fetches the current run's job timings, computes the
serial-vs-sharded comparison, gathers a rolling sample from recent successful
PR CI runs, and upserts a machine-owned PR comment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import parse, request

API_ROOT = "https://api.github.com"
COMMENT_MARKER = "<!-- ci-shadow-trial-report -->"
SHADOW_JOB_RE = re.compile(r"^tests-shadow-shard \((\d+)\)$")
TRACKED_JOB_ORDER = ("tests", "governance", "changes", "prechecks")
ROLLING_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class JobTiming:
    name: str
    status: str
    duration_seconds: float | None


@dataclass(frozen=True)
class TrialRecord:
    pr_number: int | None
    run_id: int
    run_number: int | None
    run_url: str
    conclusion: str
    checks: dict[str, JobTiming]
    shards: dict[int, JobTiming]

    @property
    def tests(self) -> JobTiming | None:
        return self.checks.get("tests")

    @property
    def projected_wall_clock_seconds(self) -> float | None:
        durations = [
            job.duration_seconds
            for _group, job in sorted(self.shards.items())
            if job.duration_seconds is not None
        ]
        if len(durations) < 2:
            return None
        return max(durations)

    @property
    def savings_seconds(self) -> float | None:
        if self.tests is None or self.tests.duration_seconds is None:
            return None
        projected = self.projected_wall_clock_seconds
        if projected is None:
            return None
        return self.tests.duration_seconds - projected

    @property
    def savings_percent(self) -> float | None:
        if self.tests is None or self.tests.duration_seconds in (None, 0):
            return None
        savings = self.savings_seconds
        if savings is None:
            return None
        return (savings / self.tests.duration_seconds) * 100.0

    @property
    def shard_balance_percentages(self) -> tuple[float, float] | None:
        durations = [
            job.duration_seconds
            for _group, job in sorted(self.shards.items())
            if job.duration_seconds is not None
        ]
        if len(durations) < 2:
            return None
        total = sum(durations)
        if total <= 0:
            return None
        return tuple((value / total) * 100.0 for value in durations)  # type: ignore[return-value]

    @property
    def is_successful_datapoint(self) -> bool:
        if self.tests is None or self.tests.status != "success":
            return False
        if len(self.shards) != 2:
            return False
        return all(
            shard.status == "success" and shard.duration_seconds is not None
            for shard in self.shards.values()
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event-path",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="Path to the GitHub workflow_run event JSON.",
    )
    return parser.parse_args()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(UTC)


def duration_seconds(started_at: str | None, completed_at: str | None) -> float | None:
    start = _parse_dt(started_at)
    end = _parse_dt(completed_at)
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    rounded = int(round(seconds))
    minutes, secs = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"


def normalize_status(raw: str | None) -> str:
    return (raw or "unknown").lower()


def _request_json(
    token: str, method: str, url: str, data: dict[str, Any] | None = None
) -> Any:
    payload = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "ci-shadow-trial-report",
    }
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, method=method, headers=headers, data=payload)
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def gh_get(token: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_ROOT}{path}"
    if params:
        url += f"?{parse.urlencode(params, doseq=True)}"
    return _request_json(token, "GET", url)


def gh_post(token: str, path: str, data: dict[str, Any]) -> Any:
    return _request_json(token, "POST", f"{API_ROOT}{path}", data=data)


def gh_patch(token: str, path: str, data: dict[str, Any]) -> Any:
    return _request_json(token, "PATCH", f"{API_ROOT}{path}", data=data)


def extract_trial_record(
    run: dict[str, Any], jobs: list[dict[str, Any]]
) -> TrialRecord:
    checks: dict[str, JobTiming] = {}
    shards: dict[int, JobTiming] = {}
    for job in jobs:
        name = job.get("name", "")
        timing = JobTiming(
            name=name,
            status=normalize_status(job.get("conclusion") or job.get("status")),
            duration_seconds=duration_seconds(
                job.get("started_at"), job.get("completed_at")
            ),
        )

        if name in TRACKED_JOB_ORDER:
            checks[name] = timing
            continue

        match = SHADOW_JOB_RE.match(name)
        if match:
            shards[int(match.group(1))] = timing

    prs = run.get("pull_requests") or []
    pr_number = None
    if prs:
        pr_number = prs[0].get("number")

    return TrialRecord(
        pr_number=pr_number,
        run_id=int(run["id"]),
        run_number=run.get("run_number"),
        run_url=run.get("html_url", ""),
        conclusion=normalize_status(run.get("conclusion")),
        checks=checks,
        shards=shards,
    )


def build_rolling_summary(records: list[TrialRecord]) -> dict[str, Any]:
    datapoints = [record for record in records if record.is_successful_datapoint]
    if not datapoints:
        return {
            "count": 0,
            "avg_serial_seconds": None,
            "avg_projected_seconds": None,
            "avg_savings_seconds": None,
            "avg_savings_percent": None,
            "records": [],
        }

    avg_serial = sum(r.tests.duration_seconds or 0.0 for r in datapoints) / len(
        datapoints
    )
    avg_projected = sum(
        r.projected_wall_clock_seconds or 0.0 for r in datapoints
    ) / len(datapoints)
    avg_savings = sum(r.savings_seconds or 0.0 for r in datapoints) / len(datapoints)
    avg_savings_pct = sum(r.savings_percent or 0.0 for r in datapoints) / len(
        datapoints
    )

    return {
        "count": len(datapoints),
        "avg_serial_seconds": avg_serial,
        "avg_projected_seconds": avg_projected,
        "avg_savings_seconds": avg_savings,
        "avg_savings_percent": avg_savings_pct,
        "records": datapoints,
    }


def render_comment(current: TrialRecord, rolling: dict[str, Any]) -> str:
    lines = [
        COMMENT_MARKER,
        "## CI Shadow Shard Trial",
        "",
        f"Current CI run: [#{current.run_number or current.run_id}]({current.run_url})",
        "",
        "| Check | Status | Duration |",
        "|------|--------|----------|",
    ]

    for name in TRACKED_JOB_ORDER:
        if name in current.checks:
            timing = current.checks[name]
            lines.append(
                f"| `{timing.name}` | `{timing.status}` | `{format_duration(timing.duration_seconds)}` |"
            )

    for shard_id, timing in sorted(current.shards.items()):
        lines.append(
            f"| `{timing.name}` | `{timing.status}` | `{format_duration(timing.duration_seconds)}` |"
        )

    lines.extend(["", "### Current Projection", ""])
    projected = current.projected_wall_clock_seconds
    savings = current.savings_seconds
    savings_pct = current.savings_percent
    lines.append(f"- Projected sharded wall-clock: `{format_duration(projected)}`")
    if savings is not None and savings_pct is not None:
        lines.append(
            f"- Projected savings vs serial: `{format_duration(savings)}` ({savings_pct:.1f}%)"
        )
    balance = current.shard_balance_percentages
    if balance is not None:
        lines.append(f"- Shard balance: `{balance[0]:.1f}% / {balance[1]:.1f}%`")

    lines.extend(["", "### Rolling Summary", ""])
    lines.append(
        f"- Successful data points collected: `{rolling['count']}/{ROLLING_SAMPLE_SIZE}`"
    )
    if rolling["count"]:
        lines.extend(
            [
                "",
                "| Avg serial | Avg sharded wall-clock | Avg savings |",
                "|-----------|--------------------------|-------------|",
                (
                    f"| `{format_duration(rolling['avg_serial_seconds'])}` "
                    f"| `{format_duration(rolling['avg_projected_seconds'])}` "
                    f"| `{format_duration(rolling['avg_savings_seconds'])}` ({rolling['avg_savings_percent']:.1f}%) |"
                ),
                "",
                "| PR | Run | Serial | Shard 1 | Shard 2 | Projected | Savings |",
                "|----|-----|--------|---------|---------|-----------|---------|",
            ]
        )
        for record in rolling["records"]:
            shard1 = record.shards.get(1)
            shard2 = record.shards.get(2)
            pr_label = f"#{record.pr_number}" if record.pr_number is not None else "n/a"
            run_label = f"[#{record.run_number or record.run_id}]({record.run_url})"
            lines.append(
                "| "
                + " | ".join(
                    [
                        pr_label,
                        run_label,
                        f"`{format_duration(record.tests.duration_seconds if record.tests else None)}`",
                        f"`{format_duration(shard1.duration_seconds if shard1 else None)}`",
                        f"`{format_duration(shard2.duration_seconds if shard2 else None)}`",
                        f"`{format_duration(record.projected_wall_clock_seconds)}`",
                        f"`{format_duration(record.savings_seconds)}`",
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No successful shard data points recorded yet.")

    lines.extend(
        [
            "",
            "_This comment is updated automatically after each completed CI run for the shadow sharding trial._",
        ]
    )
    return "\n".join(lines)


def write_step_summary(body: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    Path(summary_path).write_text(body + "\n", encoding="utf-8")


def find_existing_comment_id(
    token: str, repo: str, pr_number: int, marker: str = COMMENT_MARKER
) -> int | None:
    page = 1
    while True:
        comments = gh_get(
            token,
            f"/repos/{repo}/issues/{pr_number}/comments",
            params={"per_page": 100, "page": page},
        )
        if not comments:
            break
        for comment in comments:
            if marker in comment.get("body", ""):
                return int(comment["id"])
        if len(comments) < 100:
            break
        page += 1
    return None


def upsert_comment(token: str, repo: str, pr_number: int, body: str) -> None:
    comment_id = find_existing_comment_id(token, repo, pr_number)
    if comment_id is None:
        gh_post(token, f"/repos/{repo}/issues/{pr_number}/comments", {"body": body})
        return
    gh_patch(token, f"/repos/{repo}/issues/comments/{comment_id}", {"body": body})


def fetch_jobs_for_run(token: str, repo: str, run_id: int) -> list[dict[str, Any]]:
    payload = gh_get(
        token, f"/repos/{repo}/actions/runs/{run_id}/jobs", params={"per_page": 100}
    )
    return payload.get("jobs", [])


def fetch_recent_trial_records(
    token: str,
    repo: str,
    workflow_id: int,
    *,
    current_run_id: int,
    seen_pr_numbers: set[int] | None = None,
    limit: int = ROLLING_SAMPLE_SIZE,
    scan_runs: int = 20,
) -> list[TrialRecord]:
    payload = gh_get(
        token,
        f"/repos/{repo}/actions/workflows/{workflow_id}/runs",
        params={"event": "pull_request", "status": "completed", "per_page": scan_runs},
    )
    records: list[TrialRecord] = []
    seen = set(seen_pr_numbers or set())
    for run in payload.get("workflow_runs", []):
        run_id = int(run["id"])
        if run_id == current_run_id:
            continue
        if normalize_status(run.get("conclusion")) == "cancelled":
            continue
        jobs = fetch_jobs_for_run(token, repo, run_id)
        record = extract_trial_record(run, jobs)
        if not record.is_successful_datapoint:
            continue
        if record.pr_number is not None and record.pr_number in seen:
            continue
        records.append(record)
        if record.pr_number is not None:
            seen.add(record.pr_number)
        if len(records) >= limit:
            break
    return records


def load_event(path: str | None) -> dict[str, Any]:
    if not path:
        raise SystemExit("ERROR: --event-path or GITHUB_EVENT_PATH is required")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    event = load_event(args.event_path)
    workflow_run = event.get("workflow_run", {})
    if workflow_run.get("event") != "pull_request":
        print("Skipping: workflow_run is not for a pull_request event")
        return 0

    prs = workflow_run.get("pull_requests") or []
    if not prs:
        print("Skipping: no PR associated with workflow_run")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY") or event.get("repository", {}).get(
        "full_name"
    )
    if not token or not repo:
        raise SystemExit("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    current_jobs = fetch_jobs_for_run(token, repo, int(workflow_run["id"]))
    current = extract_trial_record(workflow_run, current_jobs)
    if len(current.shards) != 2 or current.tests is None:
        print("Skipping: current run does not contain the shadow shard trial jobs")
        return 0

    current_is_datapoint = current.is_successful_datapoint
    seen_prs = (
        {current.pr_number}
        if current_is_datapoint and current.pr_number is not None
        else set()
    )
    # When the current run is a successful datapoint it will be prepended to
    # the rolling list, so fetch one fewer from history.
    history_limit = (
        ROLLING_SAMPLE_SIZE - 1 if current_is_datapoint else ROLLING_SAMPLE_SIZE
    )
    recent = fetch_recent_trial_records(
        token,
        repo,
        int(workflow_run["workflow_id"]),
        current_run_id=current.run_id,
        seen_pr_numbers=seen_prs,
        limit=history_limit,
    )
    rolling_records = [current] + recent if current_is_datapoint else recent
    rolling = build_rolling_summary(rolling_records)
    body = render_comment(current, rolling)
    upsert_comment(token, repo, int(prs[0]["number"]), body)
    write_step_summary(body)

    print(
        json.dumps(
            {
                "pr_number": prs[0]["number"],
                "run_id": current.run_id,
                "data_points": rolling["count"],
                "projected_seconds": current.projected_wall_clock_seconds,
                "savings_seconds": current.savings_seconds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
