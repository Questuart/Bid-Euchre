"""Orchestrator brief — deterministic cron-fire input (Fixes #2806).

Builds a single JSON document that the orchestrator cron consumes via the
``/read-ops-brief`` skill. Replaces the ad-hoc combination of ``gh pr
list``, ``ops.py task list``, ``ops.py inbox``, and ignored ops
``supervisor_alert`` payloads that the orchestrator previously ran each
fire.

The design rationale and finding-category routing table live in
``docs/01_core/orchestrator_brief_schema.md``. This module is the
**producer**; the skill is the consumer.

Invariants (enforced by tests):

* Every top-level schema key is always present.
* Partial data-source failure never raises; failed sources emit
  empty-state values (``[]``, ``{}``, or ``null`` per schema).
* Output is deterministic given identical filesystem + GitHub state
  (modulo ``generated_at`` and derived ``age_minutes``).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.orchestrator_brief")

SCHEMA_VERSION: int = 1

# File the --mark-read flag writes to, relative to runtime_dir.
_STATE_FILENAME: str = "orchestrator_brief_state.json"

# Unknown-category log, relative to runtime_dir. Written by the skill
# side; the brief only documents the path.
UNKNOWN_CATEGORY_LOG_FILENAME: str = "orchestrator_brief_unknown_categories.jsonl"

# Priority → derived severity mapping (see schema doc).
_PRIORITY_TO_SEVERITY: dict[str, str] = {
    "urgent": "high",
    "high": "high",
    "normal": "warn",
    "low": "info",
}

# Registered finding categories. Keep in sync with the routing table in
# docs/01_core/orchestrator_brief_schema.md and the skill. Categories
# enumerated here are those emitted by src/bid_euchre/ops/monitor.py as
# of 2026-04-24; new categories added there MUST be registered here and
# in the skill's routing table in the same PR.
KNOWN_FINDING_CATEGORIES: frozenset[str] = frozenset(
    {
        "pr_merged",
        "pr_ready",
        "pr_status",
        "ci_status",
        "stale_dispatch",
        "lane_idle",
        "lane_health",
        "fleet_idle",
        "approval_stall",
        "stall_detection",
        "stall_recovery",
        "merged_dispatch",
        "auto_dispatch",
        "escalation",
    }
)


def _now_utc(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_minutes(ts: str | None, now: datetime) -> float | None:
    if not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(s)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return round((now - parsed).total_seconds() / 60.0, 1)


def _state_path(runtime_dir: Path) -> Path:
    return runtime_dir / _STATE_FILENAME


def read_last_read_at(runtime_dir: Path) -> str | None:
    """Read persisted ``last_read_at`` timestamp. Returns ``None`` on
    missing file, malformed JSON, or schema mismatch."""
    path = _state_path(runtime_dir)
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    ts = data.get("last_read_at")
    return ts if isinstance(ts, str) else None


def mark_read(runtime_dir: Path, now: datetime | None = None) -> str:
    """Persist the current UTC timestamp as ``last_read_at``.

    Returns the timestamp that was written. Atomic write via ``os.replace``.
    """
    now_dt = _now_utc(now)
    ts = _iso_z(now_dt)
    path = _state_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "last_read_at": ts}) + "\n"
    )
    os.replace(tmp, path)
    return ts


# ---------------------------------------------------------------------------
# Individual data sources
# ---------------------------------------------------------------------------


def _collect_recent_ops_alerts(
    limit: int,
    now: datetime,
    bus_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Read unacked ``supervisor_alert`` messages for the orchestrator."""
    try:
        from bid_euchre.ops.message_bus import read_inbox
    except Exception as exc:  # pragma: no cover — import failure only
        logger.warning("Could not import read_inbox: %s", exc)
        return []

    messages: list[dict[str, Any]] = []
    for status in ("pending", "delivered"):
        try:
            batch = read_inbox(
                "orchestrator",
                bus_root=bus_root,
                status=status,
                message_type="supervisor_alert",
                limit=max(limit * 2, 20),
            )
        except Exception as exc:
            logger.warning("read_inbox(%s) failed: %s", status, exc)
            continue
        messages.extend(batch)

    # Deduplicate on message_id (latest status wins implicitly — both
    # reads return the same record; keep first occurrence).
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for m in messages:
        mid = m.get("message_id")
        if not isinstance(mid, str) or mid in seen:
            continue
        seen.add(mid)
        deduped.append(m)

    # Sort newest-first by created_at (string sort is safe for ISO-Z).
    deduped.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    deduped = deduped[:limit]

    alerts: list[dict[str, Any]] = []
    for m in deduped:
        payload = m.get("payload") or {}
        raw_findings = payload.get("findings") or []
        findings: list[dict[str, Any]] = []
        for f in raw_findings:
            if not isinstance(f, dict):
                continue
            findings.append(
                {
                    "category": f.get("category") or "unknown",
                    "severity": f.get("severity") or "info",
                    "summary": f.get("summary") or "",
                    "details": f.get("details") or {},
                }
            )

        priority = m.get("priority") or "normal"
        alerts.append(
            {
                "message_id": m.get("message_id"),
                "created_at": m.get("created_at"),
                "age_minutes": _age_minutes(m.get("created_at"), now),
                "severity": _PRIORITY_TO_SEVERITY.get(priority, "warn"),
                "priority": priority,
                "status": m.get("status"),
                "summary": m.get("summary") or "",
                "high_count": payload.get("high_count", 0),
                "warn_count": payload.get("warn_count", 0),
                "info_count": payload.get("info_count", 0),
                "findings": findings,
            }
        )
    return alerts


def _gh_pr_list(
    state: str,
    json_fields: str,
    limit: int,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Thin wrapper around ``gh pr list``. Returns ``[]`` on any failure."""
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                state,
                "--json",
                json_fields,
                "--limit",
                str(limit),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("gh pr list --state %s failed: %s", state, exc)
        return []
    if result.returncode != 0:
        logger.warning(
            "gh pr list --state %s exit=%d: %s",
            state,
            result.returncode,
            result.stderr[:200],
        )
        return []
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        logger.warning("gh pr list JSON decode failed: %s", exc)
        return []
    return data if isinstance(data, list) else []


def _ci_state(checks: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Derive ``(ci_state, failing_check_names)`` from a statusCheckRollup."""
    if not checks:
        return ("unknown", [])
    failing = [
        c for c in checks if c.get("conclusion") in ("FAILURE", "ERROR", "CANCELLED")
    ]
    if failing:
        names = [c.get("name") or "?" for c in failing[:5]]
        return ("blocked", names)
    all_complete = all(
        c.get("conclusion") == "SUCCESS" or c.get("status") == "COMPLETED"
        for c in checks
    )
    if all_complete:
        return ("green", [])
    return ("pending", [])


def _collect_open_prs() -> list[dict[str, Any]]:
    prs = _gh_pr_list(
        "open",
        "number,title,headRefName,statusCheckRollup,mergeable",
        limit=20,
    )
    out: list[dict[str, Any]] = []
    for pr in prs:
        checks = pr.get("statusCheckRollup") or []
        state, failing = _ci_state(checks)
        out.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title") or "",
                "branch": pr.get("headRefName") or "",
                "mergeable": pr.get("mergeable") or "UNKNOWN",
                "ci_state": state,
                "failing_checks": failing,
            }
        )
    return out


def _collect_merged_prs_since(last_read_at: str | None) -> list[dict[str, Any]]:
    """Return merged PRs more recent than ``last_read_at``.

    When ``last_read_at`` is ``None`` (first-ever read), returns the most
    recent 10 merges.
    """
    prs = _gh_pr_list(
        "merged",
        "number,title,headRefName,mergedAt",
        limit=20,
    )
    if last_read_at is None:
        filtered = prs[:10]
    else:
        # ISO-Z strings compare correctly; keep merges strictly after
        # last_read_at.
        filtered = [pr for pr in prs if (pr.get("mergedAt") or "") > last_read_at]
    out: list[dict[str, Any]] = []
    for pr in filtered:
        out.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title") or "",
                "branch": pr.get("headRefName") or "",
                "merged_at": pr.get("mergedAt"),
            }
        )
    return out


def _collect_pending_inbox_by_type(bus_root: Path | None = None) -> dict[str, int]:
    try:
        from bid_euchre.ops.message_bus import read_inbox
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not import read_inbox: %s", exc)
        return {}
    counts: Counter[str] = Counter()
    for status in ("pending", "delivered"):
        try:
            batch = read_inbox(
                "orchestrator",
                bus_root=bus_root,
                status=status,
                limit=500,
            )
        except Exception as exc:
            logger.warning("read_inbox(%s) for pending_inbox failed: %s", status, exc)
            continue
        for m in batch:
            mt = m.get("message_type") or "unknown"
            counts[mt] += 1
    return dict(sorted(counts.items()))


def _collect_dispatched_packets(
    runtime_dir: Path,
    now: datetime,
) -> list[dict[str, Any]]:
    try:
        from bid_euchre.ops.task_queue import list_packets
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not import list_packets: %s", exc)
        return []
    try:
        packets = list_packets(
            runtime_dir / "task_queue",
            status_filter="dispatched",
        )
    except Exception as exc:
        logger.warning("list_packets failed: %s", exc)
        return []
    out: list[dict[str, Any]] = []
    for pkt in packets:
        out.append(
            {
                "packet_id": pkt.packet_id,
                "owner": pkt.owner,
                "title": pkt.title,
                "priority": pkt.priority,
                "age_minutes": _age_minutes(pkt.created_at, now),
            }
        )
    return out


def _collect_tui_task_status(runtime_dir: Path) -> dict[str, int]:
    """Aggregate counts from ``.claude/runtime/task_state/*.json``.

    Returns a dict with keys: ``pending``, ``in_progress``, ``blocked``,
    ``completed``, ``abandoned``, ``total``. Missing status buckets are
    reported as ``0`` so the schema stays stable.
    """
    buckets = {
        "pending": 0,
        "in_progress": 0,
        "blocked": 0,
        "completed": 0,
        "abandoned": 0,
    }
    try:
        from bid_euchre.ops.status import load_tasks
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not import load_tasks: %s", exc)
        return {**buckets, "total": 0}
    try:
        tasks = load_tasks(runtime_dir=runtime_dir)
    except Exception as exc:
        logger.warning("load_tasks failed: %s", exc)
        return {**buckets, "total": 0}
    for t in tasks:
        st = t.get("status") or "pending"
        if st in buckets:
            buckets[st] += 1
    buckets["total"] = sum(buckets.values())
    return buckets


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------


def build_brief(
    runtime_dir: Path,
    *,
    now: datetime | None = None,
    recent_alerts_limit: int = 5,
    bus_root: Path | None = None,
) -> dict[str, Any]:
    """Assemble the orchestrator brief.

    See ``docs/01_core/orchestrator_brief_schema.md`` for the schema
    contract.
    """
    now_dt = _now_utc(now)
    last_read_at = read_last_read_at(runtime_dir)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_z(now_dt),
        "last_read_at": last_read_at,
        "recent_ops_alerts": _collect_recent_ops_alerts(
            recent_alerts_limit, now_dt, bus_root=bus_root
        ),
        "open_prs": _collect_open_prs(),
        "merged_prs_since_last_read": _collect_merged_prs_since(last_read_at),
        "pending_inbox_by_type": _collect_pending_inbox_by_type(bus_root=bus_root),
        "dispatched_packets": _collect_dispatched_packets(runtime_dir, now_dt),
        "tui_task_status": _collect_tui_task_status(runtime_dir),
    }


def format_brief_text(brief: dict[str, Any]) -> str:
    """Short human-readable summary for ``--json=false`` debugging."""
    from bid_euchre.ops.time_util import fmt_operator_iso

    lines: list[str] = []
    lines.append(
        f"Orchestrator brief — generated_at="
        f"{fmt_operator_iso(brief['generated_at'])}"
    )
    last_read_at = brief["last_read_at"]
    last_read_disp = fmt_operator_iso(last_read_at) if last_read_at else "(never)"
    lines.append(f"  last_read_at: {last_read_disp}")
    lines.append(f"  recent_ops_alerts: {len(brief['recent_ops_alerts'])}")
    for a in brief["recent_ops_alerts"]:
        lines.append(
            f"    [{a['severity']}] {a['message_id']}  "
            f"{a['high_count']}H/{a['warn_count']}W/{a['info_count']}I  "
            f"{len(a['findings'])} findings"
        )
    lines.append(f"  open_prs: {len(brief['open_prs'])}")
    for pr in brief["open_prs"]:
        lines.append(f"    #{pr['number']} [{pr['ci_state']}] {pr['title'][:60]}")
    lines.append(
        f"  merged_prs_since_last_read: {len(brief['merged_prs_since_last_read'])}"
    )
    for pr in brief["merged_prs_since_last_read"]:
        lines.append(f"    #{pr['number']} {pr['title'][:60]}")
    lines.append(f"  pending_inbox_by_type: {brief['pending_inbox_by_type']}")
    lines.append(f"  dispatched_packets: {len(brief['dispatched_packets'])}")
    for p in brief["dispatched_packets"]:
        lines.append(
            f"    {p['packet_id'][:12]} → {p['owner']}  "
            f"age={p['age_minutes']}m  {p['title'][:50]}"
        )
    lines.append(f"  tui_task_status: {brief['tui_task_status']}")
    return "\n".join(lines)
