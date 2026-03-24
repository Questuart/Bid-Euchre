"""Controller / reconciler — canonical actionable-state projection (SP-4-07).

Reads monitor findings, task packets, review verdicts, lane state, and
message bus records. Derives a single list of actionable items and writes
the result to ``.claude/runtime/fleet_status.json``.

This is the **only** control-plane truth for the steward platform. Hooks,
dashboards, and remote adapters consume this projection — they do not
build their own views of urgency.

Usage::

    from bid_euchre.ops.control_plane import reconcile, load_fleet_status

    items = reconcile()            # derive + persist
    status = load_fleet_status()   # read last persisted projection

Design constraints:

- Pure-function core: ``derive_items()`` takes pre-loaded data, returns items.
- Side-effecting shell: ``reconcile()`` loads data, calls ``derive_items()``,
  writes the output file.
- All items carry stable ``item_id`` values so consumers can track ack/clear
  across cycles.
- Severity levels align with ``MonitorFinding.severity`` (info/warn/high) plus
  an ``urgent`` level for escalated state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.control_plane")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RUNTIME_DIR = Path(".claude/runtime")
FLEET_STATUS_FILE = "fleet_status.json"

# Severity levels (ascending urgency).
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_HIGH = "high"
SEVERITY_URGENT = "urgent"

VALID_SEVERITIES = frozenset(
    {SEVERITY_INFO, SEVERITY_WARN, SEVERITY_HIGH, SEVERITY_URGENT}
)

# Item states.
STATE_OPEN = "open"
STATE_ACKED = "acked"
STATE_CLEARED = "cleared"
STATE_SUPPRESSED = "suppressed"

VALID_STATES = frozenset({STATE_OPEN, STATE_ACKED, STATE_CLEARED, STATE_SUPPRESSED})

# Categories.
CAT_LANE_HEALTH = "lane_health"
CAT_PR_STATUS = "pr_status"
CAT_STALE_DISPATCH = "stale_dispatch"
CAT_STALLED_LANE = "stalled_lane"
CAT_APPROVAL_STALL = "approval_stall"
CAT_IDLE_LANE = "idle_lane"
CAT_ESCALATION = "escalation"
CAT_MERGED_PR = "merged_pr"
CAT_CI_READY = "ci_ready"
CAT_UNACKED_MESSAGE = "unacked_message"
CAT_TASK_LIFECYCLE = "task_lifecycle"
CAT_REVIEW_VERDICT = "review_verdict"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ActionableItem:
    """A single actionable item in the fleet status projection.

    Attributes:
        item_id: Stable identifier for dedup/tracking across cycles.
        severity: One of ``VALID_SEVERITIES``.
        category: Grouping label (lane_health, pr_status, etc.).
        source: Which subsystem produced this (monitor, task_queue, etc.).
        summary: Human-readable one-liner.
        first_seen_at: ISO 8601 when first detected.
        last_seen_at: ISO 8601 when last confirmed present.
        state: One of ``VALID_STATES`` — starts ``open``.
        lane_id: Related lane identifier, if any.
        task_id: Related task packet ID, if any.
        pr_number: Related PR number, if any.
        recommended_action: Suggested next step.
        details: Extra structured data.
    """

    item_id: str
    severity: str
    category: str
    source: str
    summary: str
    first_seen_at: str
    last_seen_at: str
    state: str = STATE_OPEN
    lane_id: str | None = None
    task_id: str | None = None
    pr_number: int | None = None
    recommended_action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {self.severity!r}; "
                f"expected one of {sorted(VALID_SEVERITIES)}"
            )
        if self.state not in VALID_STATES:
            raise ValueError(
                f"Invalid state {self.state!r}; expected one of {sorted(VALID_STATES)}"
            )


@dataclass
class FleetStatus:
    """The complete fleet status projection.

    Written atomically to ``.claude/runtime/fleet_status.json``.
    """

    items: list[ActionableItem] = field(default_factory=list)
    generated_at: str = ""
    cycle_count: int = 0

    @property
    def open_items(self) -> list[ActionableItem]:
        return [i for i in self.items if i.state == STATE_OPEN]

    @property
    def urgent_items(self) -> list[ActionableItem]:
        return [
            i
            for i in self.items
            if i.severity == SEVERITY_URGENT and i.state == STATE_OPEN
        ]

    @property
    def high_items(self) -> list[ActionableItem]:
        return [
            i
            for i in self.items
            if i.severity in (SEVERITY_HIGH, SEVERITY_URGENT) and i.state == STATE_OPEN
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [asdict(item) for item in self.items],
            "generated_at": self.generated_at,
            "cycle_count": self.cycle_count,
            "summary": {
                "total": len(self.items),
                "open": len(self.open_items),
                "urgent": len(self.urgent_items),
                "high": len(self.high_items),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FleetStatus:
        items = [ActionableItem(**item) for item in data.get("items", [])]
        return cls(
            items=items,
            generated_at=data.get("generated_at", ""),
            cycle_count=data.get("cycle_count", 0),
        )


# ---------------------------------------------------------------------------
# Stable item ID generation
# ---------------------------------------------------------------------------


def _stable_id(category: str, *key_parts: str) -> str:
    """Generate a deterministic item_id from category + key parts.

    The hash ensures stable IDs across cycles for the same logical item.
    """
    raw = "|".join([category, *key_parts])
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# MonitorFinding → dict bridge
# ---------------------------------------------------------------------------


def monitor_findings_to_dicts(
    findings: list[Any],
) -> list[dict[str, Any]]:
    """Convert ``MonitorFinding`` dataclass instances to plain dicts.

    Accepts a list of ``MonitorFinding`` frozen dataclasses (from
    ``bid_euchre.ops.monitor``) and converts each to a plain dict
    using ``dataclasses.asdict()``.

    This bridges the monitor module's output type to the dict interface
    used by the controller's derivation functions, avoiding a hard
    import-time dependency on the monitor module.

    Example::

        from bid_euchre.ops.monitor import run_monitoring_cycle
        from bid_euchre.ops.control_plane import (
            monitor_findings_to_dicts, reconcile,
        )

        findings = run_monitoring_cycle(skip_pr_check=True)
        status = reconcile(monitor_findings=monitor_findings_to_dicts(findings))
    """
    return [asdict(f) for f in findings]


# ---------------------------------------------------------------------------
# Derivation: monitor findings → actionable items
# ---------------------------------------------------------------------------


def _finding_stable_id(
    category: str,
    details: dict[str, Any],
) -> str:
    """Generate a deterministic item_id from a monitor finding.

    Uses **category + key identifiers** (lane_id, pr_number, task_id)
    rather than volatile text (summary) so that the same logical condition
    maps to the same item_id even when details like check counts change.

    Falls back to including a summary prefix only when no identifying key
    is available, to avoid collapsing unrelated findings into one id.
    """
    lane_id = str(details.get("lane_id", ""))
    pr_number = str(details.get("pr_number", details.get("number", "")))
    task_id = str(details.get("task_id", ""))

    # If we have at least one identifying key, use it for dedup.
    if lane_id or pr_number or task_id:
        return _stable_id(category, lane_id, pr_number, task_id)

    # Fallback: include summary prefix for findings with no identifiers.
    summary = str(details.get("summary", ""))
    return _stable_id(category, summary[:60])


def items_from_monitor_findings(
    findings: list[dict[str, Any]],
    *,
    now_iso: str | None = None,
) -> list[ActionableItem]:
    """Convert monitor findings into actionable items.

    Accepts findings as plain dicts (the output of
    :func:`monitor_findings_to_dicts` or ``dataclasses.asdict``).

    Skips pure-info capacity summaries (routine noise).
    Maps monitor severities to control-plane severities.
    """
    if now_iso is None:
        now_iso = _now_iso()

    items: list[ActionableItem] = []
    for f in findings:
        severity = f.get("severity", SEVERITY_INFO)
        category = f.get("category", "unknown")
        summary = f.get("summary", "")
        details = f.get("details", {})

        # Skip routine info-only capacity summaries.
        if severity == SEVERITY_INFO and category == CAT_LANE_HEALTH:
            continue

        item_id = _finding_stable_id(category, details)

        lane_id = details.get("lane_id")
        pr_number = details.get("pr_number") or details.get("number")
        if pr_number is not None:
            pr_number = int(pr_number)
        task_id = details.get("task_id")

        recommended = _recommend_action(category, severity, details)

        items.append(
            ActionableItem(
                item_id=item_id,
                severity=severity,
                category=category,
                source="monitor",
                summary=summary,
                first_seen_at=now_iso,
                last_seen_at=now_iso,
                lane_id=lane_id,
                task_id=task_id,
                pr_number=pr_number,
                recommended_action=recommended,
                details=details,
            )
        )

    return items


def _recommend_action(category: str, severity: str, details: dict[str, Any]) -> str:
    """Generate a recommended action string for common finding categories."""
    if category == CAT_LANE_HEALTH and severity in (SEVERITY_HIGH, SEVERITY_URGENT):
        lane = details.get("lane_id", "unknown")
        return f"Investigate lane {lane!r} — check tmux pane and worktree state"
    if category == CAT_PR_STATUS:
        pr = details.get("number") or details.get("pr_number", "?")
        if details.get("mergeable") == "CONFLICTING":
            return f"Rebase PR #{pr} to resolve merge conflicts"
        return f"Review PR #{pr} check status"
    if category == CAT_STALE_DISPATCH:
        return "Check dispatched task — lane may need a nudge"
    if category == CAT_STALLED_LANE:
        return "Re-nudge or reassign stalled lane"
    if category == CAT_APPROVAL_STALL:
        return "Approve pending tool-use prompt in lane tmux pane"
    if category == CAT_ESCALATION:
        return "Triage escalated alert — ack or resolve the original"
    if category == CAT_CI_READY:
        return "Merge or review CI-ready PR"
    return "Review and triage"


# ---------------------------------------------------------------------------
# Derivation: task packets → actionable items
# ---------------------------------------------------------------------------


def items_from_task_packets(
    packets: list[dict[str, Any]],
    *,
    now_iso: str | None = None,
) -> list[ActionableItem]:
    """Derive actionable items from active task packets.

    Flags:
    - Dispatched packets with no owner or no ack (stale dispatch handled by monitor).
    - Approved packets waiting for dispatch.
    - Blocked/failed packets.
    """
    if now_iso is None:
        now_iso = _now_iso()

    items: list[ActionableItem] = []
    for pkt in packets:
        status = pkt.get("status", "")
        packet_id = pkt.get("packet_id", "")
        title = pkt.get("title", "")
        owner = pkt.get("owner")
        priority = pkt.get("priority", "normal")

        if status == "approved":
            # Approved but not yet dispatched — needs attention.
            items.append(
                ActionableItem(
                    item_id=_stable_id(CAT_TASK_LIFECYCLE, packet_id, "approved"),
                    severity=SEVERITY_WARN if priority == "high" else SEVERITY_INFO,
                    category=CAT_TASK_LIFECYCLE,
                    source="task_queue",
                    summary=f"Approved task awaiting dispatch: {title!r}",
                    first_seen_at=now_iso,
                    last_seen_at=now_iso,
                    task_id=packet_id,
                    lane_id=owner,
                    recommended_action="Dispatch to an idle lane",
                    details={"priority": priority, "status": status},
                )
            )

    return items


# ---------------------------------------------------------------------------
# Derivation: unacked bus messages → actionable items
# ---------------------------------------------------------------------------


def items_from_unacked_messages(
    messages: list[dict[str, Any]],
    *,
    now_iso: str | None = None,
    max_age_minutes: int = 10,
) -> list[ActionableItem]:
    """Derive actionable items from unacked high/urgent bus messages.

    Only surfaces messages older than ``max_age_minutes`` to avoid noise
    from messages that are about to be processed.
    """
    if now_iso is None:
        now_iso = _now_iso()

    items: list[ActionableItem] = []
    now_ts = time.time()

    for msg in messages:
        priority = msg.get("priority", "normal")
        if priority not in ("high", "urgent"):
            continue
        status = msg.get("status", "")
        if status not in ("pending", "delivered"):
            continue

        created_at = msg.get("created_at", "")
        try:
            created_ts = datetime.fromisoformat(created_at).timestamp()
        except (ValueError, TypeError):
            continue

        age_minutes = (now_ts - created_ts) / 60
        if age_minutes < max_age_minutes:
            continue

        msg_id = msg.get("id", msg.get("message_id", ""))
        from_lane = msg.get("from_lane", "")
        to_lane = msg.get("to_lane", "")
        summary_text = msg.get("summary", msg.get("payload", {}).get("summary", ""))

        severity = SEVERITY_URGENT if priority == "urgent" else SEVERITY_HIGH

        items.append(
            ActionableItem(
                item_id=_stable_id(CAT_UNACKED_MESSAGE, msg_id),
                severity=severity,
                category=CAT_UNACKED_MESSAGE,
                source="message_bus",
                summary=f"Unacked {priority} message from {from_lane}: {summary_text!r}",
                first_seen_at=now_iso,
                last_seen_at=now_iso,
                lane_id=to_lane,
                recommended_action=f"Ack or resolve message {msg_id[:8]}",
                details={
                    "message_id": msg_id,
                    "from_lane": from_lane,
                    "to_lane": to_lane,
                    "priority": priority,
                    "age_minutes": round(age_minutes, 1),
                },
            )
        )

    return items


# ---------------------------------------------------------------------------
# Merge with previous state (ack/clear persistence)
# ---------------------------------------------------------------------------


def merge_with_previous(
    new_items: list[ActionableItem],
    previous: FleetStatus | None,
) -> list[ActionableItem]:
    """Merge newly derived items with the previous projection.

    - Preserves ``first_seen_at`` from previous if the item was already known.
    - Carries forward ``acked``/``suppressed`` state for items that still exist.
    - Drops ``cleared`` items that no longer appear in new derivation.
    - Items in previous that are no longer detected are auto-cleared.
    """
    if previous is None:
        return new_items

    prev_by_id: dict[str, ActionableItem] = {i.item_id: i for i in previous.items}
    merged: list[ActionableItem] = []

    seen_ids: set[str] = set()
    for item in new_items:
        seen_ids.add(item.item_id)
        prev = prev_by_id.get(item.item_id)
        if prev is not None:
            # Preserve first_seen_at and carry forward acked/suppressed state.
            state = (
                prev.state
                if prev.state in (STATE_ACKED, STATE_SUPPRESSED)
                else item.state
            )
            merged.append(
                ActionableItem(
                    item_id=item.item_id,
                    severity=item.severity,
                    category=item.category,
                    source=item.source,
                    summary=item.summary,
                    first_seen_at=prev.first_seen_at,
                    last_seen_at=item.last_seen_at,
                    state=state,
                    lane_id=item.lane_id,
                    task_id=item.task_id,
                    pr_number=item.pr_number,
                    recommended_action=item.recommended_action,
                    details=item.details,
                )
            )
        else:
            merged.append(item)

    # Items that were in previous but not in new — auto-clear if open.
    for prev_id, prev_item in prev_by_id.items():
        if prev_id not in seen_ids:
            if prev_item.state in (STATE_OPEN, STATE_ACKED):
                merged.append(
                    ActionableItem(
                        item_id=prev_item.item_id,
                        severity=prev_item.severity,
                        category=prev_item.category,
                        source=prev_item.source,
                        summary=prev_item.summary,
                        first_seen_at=prev_item.first_seen_at,
                        last_seen_at=prev_item.last_seen_at,
                        state=STATE_CLEARED,
                        lane_id=prev_item.lane_id,
                        task_id=prev_item.task_id,
                        pr_number=prev_item.pr_number,
                        recommended_action=None,
                        details=prev_item.details,
                    )
                )
            # Already cleared/suppressed items that are no longer detected: drop.

    return merged


# ---------------------------------------------------------------------------
# Ack / clear / suppress API
# ---------------------------------------------------------------------------


def ack_item(status: FleetStatus, item_id: str) -> bool:
    """Mark an item as acknowledged. Returns True if found and updated."""
    for item in status.items:
        if item.item_id == item_id and item.state == STATE_OPEN:
            # Dataclass is not frozen, so we can mutate.
            object.__setattr__(item, "state", STATE_ACKED)
            return True
    return False


def clear_item(status: FleetStatus, item_id: str) -> bool:
    """Mark an item as cleared. Returns True if found and updated."""
    for item in status.items:
        if item.item_id == item_id and item.state in (STATE_OPEN, STATE_ACKED):
            object.__setattr__(item, "state", STATE_CLEARED)
            return True
    return False


def suppress_item(status: FleetStatus, item_id: str) -> bool:
    """Mark an item as suppressed (won't resurface). Returns True if found."""
    for item in status.items:
        if item.item_id == item_id and item.state in (STATE_OPEN, STATE_ACKED):
            object.__setattr__(item, "state", STATE_SUPPRESSED)
            return True
    return False


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _fleet_status_path(runtime_dir: Path | None = None) -> Path:
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR
    return runtime_dir / FLEET_STATUS_FILE


def load_fleet_status(runtime_dir: Path | None = None) -> FleetStatus | None:
    """Load the last persisted fleet status from disk.

    Returns None if the file doesn't exist or is corrupt.
    """
    path = _fleet_status_path(runtime_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return FleetStatus.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Could not load fleet status from %s: %s", path, exc)
        return None


def save_fleet_status(
    status: FleetStatus,
    runtime_dir: Path | None = None,
) -> Path:
    """Atomically write the fleet status projection to disk."""
    path = _fleet_status_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = status.to_dict()
    # Atomic write via temp file + rename.
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix="fleet_status_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        # Clean up temp file on failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return path


# ---------------------------------------------------------------------------
# Full derivation (pure function)
# ---------------------------------------------------------------------------


def derive_items(
    *,
    monitor_findings: list[dict[str, Any]] | None = None,
    monitor_finding_objects: list[Any] | None = None,
    task_packets: list[dict[str, Any]] | None = None,
    unacked_messages: list[dict[str, Any]] | None = None,
    now_iso: str | None = None,
    unacked_message_age_minutes: int = 10,
) -> list[ActionableItem]:
    """Derive actionable items from all input sources.

    This is a **pure function** — it takes pre-loaded data and returns items.
    No I/O, no side effects.

    Args:
        monitor_findings: Pre-converted dicts (legacy interface).
        monitor_finding_objects: ``MonitorFinding`` dataclass instances
            from the monitor module.  Automatically converted to dicts via
            :func:`monitor_findings_to_dicts`.  If both ``monitor_findings``
            and ``monitor_finding_objects`` are provided, they are combined.
        task_packets: Task packet dicts.
        unacked_messages: Bus message dicts.
        now_iso: Override for current time (ISO 8601).
        unacked_message_age_minutes: Age threshold for unacked messages.
    """
    if now_iso is None:
        now_iso = _now_iso()

    all_items: list[ActionableItem] = []

    # Combine dict-based and object-based monitor findings.
    combined_findings: list[dict[str, Any]] = []
    if monitor_findings:
        combined_findings.extend(monitor_findings)
    if monitor_finding_objects:
        combined_findings.extend(monitor_findings_to_dicts(monitor_finding_objects))

    if combined_findings:
        all_items.extend(
            items_from_monitor_findings(combined_findings, now_iso=now_iso)
        )

    if task_packets:
        all_items.extend(items_from_task_packets(task_packets, now_iso=now_iso))

    if unacked_messages:
        all_items.extend(
            items_from_unacked_messages(
                unacked_messages,
                now_iso=now_iso,
                max_age_minutes=unacked_message_age_minutes,
            )
        )

    return all_items


# ---------------------------------------------------------------------------
# Reconcile (side-effecting orchestration)
# ---------------------------------------------------------------------------


def reconcile(
    *,
    runtime_dir: Path | None = None,
    monitor_findings: list[dict[str, Any]] | None = None,
    monitor_finding_objects: list[Any] | None = None,
    task_packets: list[dict[str, Any]] | None = None,
    unacked_messages: list[dict[str, Any]] | None = None,
    now_iso: str | None = None,
) -> FleetStatus:
    """Run one reconciliation cycle.

    1. Load previous fleet status from disk.
    2. Derive new items from all input sources.
    3. Merge with previous state (preserve ack/clear).
    4. Persist the result.
    5. Return the new fleet status.

    Accepts monitor findings as either pre-converted dicts
    (``monitor_findings``) or ``MonitorFinding`` dataclass instances
    (``monitor_finding_objects``).  Both may be provided and are combined.

    If neither monitor input is provided, the caller is responsible
    for running the monitor cycle first and passing the results.
    """
    if now_iso is None:
        now_iso = _now_iso()

    previous = load_fleet_status(runtime_dir)
    cycle_count = (previous.cycle_count if previous else 0) + 1

    new_items = derive_items(
        monitor_findings=monitor_findings,
        monitor_finding_objects=monitor_finding_objects,
        task_packets=task_packets,
        unacked_messages=unacked_messages,
        now_iso=now_iso,
    )

    merged = merge_with_previous(new_items, previous)

    status = FleetStatus(
        items=merged,
        generated_at=now_iso,
        cycle_count=cycle_count,
    )

    save_fleet_status(status, runtime_dir)
    logger.info(
        "Reconciled fleet status: %d items (%d open, %d urgent), cycle %d",
        len(status.items),
        len(status.open_items),
        len(status.urgent_items),
        status.cycle_count,
    )

    return status


# ---------------------------------------------------------------------------
# CLI-friendly summary
# ---------------------------------------------------------------------------


def format_status_text(status: FleetStatus) -> str:
    """Format fleet status as human-readable text for CLI output."""
    if not status.items:
        return "Fleet status: all clear (0 items)"

    lines = [
        f"Fleet status — cycle {status.cycle_count} "
        f"({len(status.open_items)} open, {len(status.urgent_items)} urgent)",
        "",
    ]

    # Group by severity, highest first.
    severity_order = [SEVERITY_URGENT, SEVERITY_HIGH, SEVERITY_WARN, SEVERITY_INFO]
    for sev in severity_order:
        sev_items = [
            i for i in status.items if i.severity == sev and i.state == STATE_OPEN
        ]
        if not sev_items:
            continue
        lines.append(f"  [{sev.upper()}] ({len(sev_items)})")
        for item in sev_items:
            prefix = f"    {item.item_id[:8]}"
            lines.append(f"{prefix}  {item.summary}")
            if item.recommended_action:
                lines.append(f"             → {item.recommended_action}")
        lines.append("")

    # Acked / suppressed summary.
    acked = [i for i in status.items if i.state == STATE_ACKED]
    cleared = [i for i in status.items if i.state == STATE_CLEARED]
    if acked or cleared:
        lines.append(f"  (acked: {len(acked)}, cleared: {len(cleared)})")

    return "\n".join(lines)


def format_status_json(status: FleetStatus) -> str:
    """Format fleet status as JSON for programmatic consumption."""
    return json.dumps(status.to_dict(), indent=2)
