#!/usr/bin/env python3
"""UserPromptSubmit hook: inject high/urgent fleet alerts as additionalContext.

Reads ``.claude/runtime/fleet_status.json`` (written by the controller/reconciler)
and injects open HIGH or URGENT items into the conversation context so the
orchestrator cannot miss them.

Design constraints:
- stdlib-only (no project imports) for speed -- cold start ~100ms.
- Outputs nothing (exit 0) when no actionable alerts exist.
- Outputs ``{"additionalContext": "..."}`` when alerts are present.

Closes #1608.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def read_fleet_status(path: Path) -> dict | None:
    """Read and parse fleet_status.json.  Returns None on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def extract_alerts(data: dict) -> list[dict]:
    """Return open items with severity 'high' or 'urgent'."""
    items = data.get("items", [])
    return [
        i
        for i in items
        if i.get("severity") in ("high", "urgent") and i.get("state") == "open"
    ]


def format_alert_context(alerts: list[dict]) -> str:
    """Format alerts into a human-readable context string."""
    lines = [f"FLEET ALERTS ({len(alerts)} unresolved):"]
    for a in alerts:
        sev = a.get("severity", "high").upper()
        summary = a.get("summary", "(no summary)")
        lines.append(f"  [{sev}] {summary}")
        rec = a.get("recommended_action")
        if rec:
            lines.append(f"    -> {rec}")
    return "\n".join(lines)


def main(project_dir: str | None = None) -> int:
    """Entry point.  Returns 0 always (never blocks prompt submission)."""
    if project_dir is None:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    status_path = Path(project_dir) / ".claude" / "runtime" / "fleet_status.json"

    if not status_path.exists():
        return 0

    data = read_fleet_status(status_path)
    if data is None:
        return 0

    alerts = extract_alerts(data)
    if not alerts:
        return 0

    context = format_alert_context(alerts)
    print(json.dumps({"additionalContext": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
