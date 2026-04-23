"""Capture Phase 0 steward platform baseline snapshot.

Writes a timestamped markdown snapshot to stdout composed of the named
capture sections in `plans/steward_platform/governing_plan.md` §4.3. The
intended caller redirects stdout to
`plans/steward_platform/0_hardening/baseline.md`.

Each section is a self-contained markdown block. If a data source is
unavailable, the section records "insufficient data at capture time"
per the §4.3 contract — no section is left blank.

Usage:
    uv run python scripts/internal/capture_steward_baseline.py \
        > plans/steward_platform/0_hardening/baseline.md

The script is intentionally narrow (stdlib + subprocess only) so it can
re-run deterministically under Primitive F whenever a post-reduction
re-baseline is triggered.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSUFFICIENT = "_Insufficient data at capture time._"


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def _ops_json(args: list[str]) -> object | None:
    """Call `ops.py --json <args>`; return parsed JSON or None on failure."""
    rc, out, _ = _run(
        ["uv", "run", "python", "scripts/internal/ops.py", "--json", *args]
    )
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def section_timestamp() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"## 1. Generated-at timestamp\n\n`{now}` (UTC)\n"


def section_fleet_state() -> str:
    data = _ops_json(["dashboard"])
    lines = ["## 2. Fleet lane state\n"]
    if not isinstance(data, dict):
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    summary = data.get("summary", {}) or {}
    lines.append("**Summary (ops.py dashboard):**\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for key in (
        "foreground_lanes",
        "background_lanes",
        "attention_items",
        "inbox_unacked",
        "active_tasks",
        "blocked_tasks",
        "warnings",
    ):
        lines.append(f"| `{key}` | {summary.get(key, 'n/a')} |")
    highlights = data.get("inbox_highlights", []) or []
    if highlights:
        lines.append("\n**Inbox highlights:**\n")
        lines.append("| Lane | Unacked | Oldest |")
        lines.append("|---|---|---|")
        for entry in highlights[:10]:
            lines.append(
                f"| {entry.get('lane_id', '?')} "
                f"| {entry.get('unacked_count', 0)} "
                f"| {entry.get('oldest_unacked_age', 'n/a')} |"
            )
    return "\n".join(lines) + "\n"


def section_token_snapshot() -> str:
    summary = _ops_json(["usage", "summary"])
    lines = ["## 3. Token economy snapshot\n"]
    if not isinstance(summary, dict):
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    store = summary.get("store_status", {}) or {}
    s = summary.get("summary", {}) or {}
    lines.append("**Store status:**\n")
    lines.append(f"- Session count: {store.get('session_count', 'n/a')}")
    lines.append(f"- Last import: `{store.get('last_import_timestamp', 'n/a')}`")
    lines.append(f"- Stale: `{store.get('stale', 'n/a')}`")
    lines.append("\n**Totals across observed window:**\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for key in (
        "session_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_tokens",
        "total_git_commits",
        "total_git_pushes",
        "total_duration_minutes",
        "time_range_start",
        "time_range_end",
    ):
        lines.append(f"| `{key}` | {s.get(key, 'n/a')} |")
    return "\n".join(lines) + "\n"


def section_pr_velocity() -> str:
    # Use git log-based gh pr list (no --search since portable). Fetch recent 100, filter by mergedAt in script.
    rc, out, _ = _run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,title,state,mergedAt,createdAt,closedAt",
        ],
        timeout=60,
    )
    lines = ["## 4. PR velocity (last 30 days)\n"]
    if rc != 0 or not out.strip():
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    try:
        prs = json.loads(out)
    except json.JSONDecodeError:
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    cutoff = datetime.now(timezone.utc).timestamp() - 30 * 86400
    counts: Counter[str] = Counter()
    for pr in prs:
        # Use mergedAt if present, else createdAt
        stamp = pr.get("mergedAt") or pr.get("closedAt") or pr.get("createdAt")
        if not stamp:
            continue
        try:
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ts < cutoff:
            continue
        counts[pr.get("state", "UNKNOWN")] += 1
    lines.append("| State | Count |")
    lines.append("|---|---|")
    for key in ("MERGED", "OPEN", "CLOSED"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines.append("\n_Sampled from most recent 200 PRs; window = 30d._\n")
    return "\n".join(lines) + "\n"


def section_issue_state() -> str:
    rc, out, _ = _run(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,state,labels,createdAt,author",
        ],
        timeout=60,
    )
    lines = ["## 5. Issue state (last 30 days)\n"]
    if rc != 0 or not out.strip():
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    try:
        issues = json.loads(out)
    except json.JSONDecodeError:
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    cutoff = datetime.now(timezone.utc).timestamp() - 30 * 86400
    state_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    author_type: Counter[str] = Counter()
    for issue in issues:
        stamp = issue.get("createdAt")
        if not stamp:
            continue
        try:
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ts < cutoff:
            continue
        state_counts[issue.get("state", "UNKNOWN")] += 1
        author = issue.get("author") or {}
        author_type["bot" if author.get("is_bot") else "human"] += 1
        for label in issue.get("labels", []) or []:
            label_counts[label.get("name", "?")] += 1
    lines.append("| State | Count |")
    lines.append("|---|---|")
    for key, val in state_counts.most_common():
        lines.append(f"| {key} | {val} |")
    lines.append("\n**Author breakdown (issue-discovery proxy):**\n")
    lines.append("| Source | Count |")
    lines.append("|---|---|")
    for key in ("human", "bot"):
        lines.append(f"| {key} | {author_type.get(key, 0)} |")
    if label_counts:
        lines.append("\n**Top labels:**\n")
        lines.append("| Label | Count |")
        lines.append("|---|---|")
        for key, val in label_counts.most_common(10):
            lines.append(f"| {key} | {val} |")
    return "\n".join(lines) + "\n"


def section_commit_velocity() -> str:
    rc, out, _ = _run(["git", "log", "--since=30 days ago", "--oneline"], timeout=30)
    lines = ["## 6. Commit velocity (last 30 days, current branch ancestry)\n"]
    if rc != 0:
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    count = sum(1 for line in out.splitlines() if line.strip())
    lines.append(f"- Commits in window: **{count}**")
    # Top authors
    rc2, out2, _ = _run(
        ["git", "log", "--since=30 days ago", "--format=%an"], timeout=30
    )
    if rc2 == 0 and out2.strip():
        authors = Counter(line.strip() for line in out2.splitlines() if line.strip())
        lines.append("\n**Top authors:**\n")
        lines.append("| Author | Commits |")
        lines.append("|---|---|")
        for name, n in authors.most_common(5):
            lines.append(f"| {name} | {n} |")
    return "\n".join(lines) + "\n"


def section_event_schema() -> str:
    events_path = REPO_ROOT / ".claude" / "runtime" / "events" / "events.jsonl"
    lines = ["## 7. Event schema shape (runtime events.jsonl)\n"]
    if not events_path.exists():
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    type_counts: Counter[str] = Counter()
    total = 0
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                total += 1
                type_counts[ev.get("event_type", "<missing>")] += 1
    except OSError:
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    lines.append(f"- Total events observed: **{total}**")
    lines.append(f"- Distinct event types: **{len(type_counts)}**")
    lines.append("\n**Top event types:**\n")
    lines.append("| Event type | Count |")
    lines.append("|---|---|")
    for name, n in type_counts.most_common(15):
        lines.append(f"| `{name}` | {n} |")
    return "\n".join(lines) + "\n"


def section_lane_model_effort() -> str:
    by_model = _ops_json(["usage", "by-model"])
    by_effort = _ops_json(["usage", "by-effort"])
    lanes = _ops_json(["usage", "lanes"])
    lines = ["## 8. Lane × model × effort rollup\n"]
    parts: list[str] = []
    if isinstance(by_model, dict) and by_model.get("buckets"):
        parts.append("**By model:**\n")
        parts.append("| Model | Sessions | Total tokens | Commits |")
        parts.append("|---|---|---|---|")
        for b in by_model["buckets"]:
            parts.append(
                f"| `{b.get('model', '?')}` | {b.get('session_count', 0)} "
                f"| {b.get('total_tokens', 0)} | {b.get('git_commits', 0)} |"
            )
        unk = by_model.get("unknown_fraction")
        if unk is not None:
            parts.append(f"\n_Unknown-model fraction: {unk:.2f}._")
    if isinstance(by_effort, dict) and by_effort.get("buckets"):
        parts.append("\n**By effort:**\n")
        parts.append("| Effort | Sessions | Total tokens | Commits |")
        parts.append("|---|---|---|---|")
        for b in by_effort["buckets"]:
            parts.append(
                f"| `{b.get('effort', '?')}` | {b.get('session_count', 0)} "
                f"| {b.get('total_tokens', 0)} | {b.get('git_commits', 0)} |"
            )
    if isinstance(lanes, list) and lanes:
        parts.append("\n**By lane (top 10 by total tokens):**\n")
        parts.append("| Lane | Pool | Sessions | Total tokens | Tokens/commit |")
        parts.append("|---|---|---|---|---|")
        for lane in sorted(lanes, key=lambda x: x.get("total_tokens", 0), reverse=True)[
            :10
        ]:
            tpc = lane.get("tokens_per_commit")
            tpc_s = f"{tpc:.0f}" if isinstance(tpc, (int, float)) else "n/a"
            parts.append(
                f"| `{lane.get('lane_id', '?')}` | {lane.get('pool') or '-'} "
                f"| {lane.get('session_count', 0)} | {lane.get('total_tokens', 0)} "
                f"| {tpc_s} |"
            )
    if not parts:
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    return lines[0] + "\n" + "\n".join(parts) + "\n"


def section_plan_inventory() -> str:
    plans_dir = REPO_ROOT / "plans"
    lines = ["## 9. Plan artifact inventory\n"]
    if not plans_dir.exists():
        return lines[0] + "\n" + INSUFFICIENT + "\n"
    subdir_counts: Counter[str] = Counter()
    total = 0
    for md in plans_dir.rglob("*.md"):
        total += 1
        # Bucket by first-level subdir under plans/
        try:
            rel = md.relative_to(plans_dir)
            top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        except ValueError:
            top = "(unknown)"
        subdir_counts[top] += 1
    lines.append(f"- Total `.md` files under `plans/`: **{total}**")
    lines.append("\n**By top-level subdir:**\n")
    lines.append("| Subdir | Count |")
    lines.append("|---|---|")
    for name, n in sorted(subdir_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{name}` | {n} |")
    return "\n".join(lines) + "\n"


def section_crons_note() -> str:
    return (
        "## 10. Active crons\n\n"
        "Cron state is session-scoped and not captured by this baseline "
        "(each tmux pane's `/loop` schedule is re-established per session "
        "and held in the Claude Code runtime). Operator-readable note: to "
        "inspect active crons, use `CronList` inside the relevant pane. "
        "Any durable scheduling invariants should live as checkpoints in the "
        "owning plan, not as a baseline metric.\n"
    )


SECTIONS = [
    section_timestamp,
    section_fleet_state,
    section_token_snapshot,
    section_pr_velocity,
    section_issue_state,
    section_commit_velocity,
    section_event_schema,
    section_lane_model_effort,
    section_plan_inventory,
    section_crons_note,
]


def build_baseline() -> str:
    header = (
        "# Steward Platform Phase 0 Baseline\n\n"
        "> Generated by `scripts/internal/capture_steward_baseline.py` per "
        "`plans/steward_platform/governing_plan.md` §4.3. Re-run to produce "
        "a structurally identical snapshot (timestamps vary; section shape "
        "is stable).\n\n"
        "> Sections reporting `Insufficient data at capture time` feed a "
        "Phase 2 Decision Input under the Re-evaluation tag (§4.3).\n"
    )
    body = "\n".join(fn() for fn in SECTIONS)
    return header + "\n" + body + "\n"


def main() -> int:
    print(build_baseline(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
