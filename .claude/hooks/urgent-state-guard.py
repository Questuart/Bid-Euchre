#!/usr/bin/env python3
"""PreToolUse guard: block risky actions when fleet has unresolved urgent state.

Reads ``.claude/runtime/fleet_status.json`` and blocks merge/dispatch commands
when open HIGH or URGENT items exist.  Integrates into the ``pre-bash-dispatch``
pipeline as a sub-hook.

Design constraints:
- stdlib-only (no project imports) for speed — cold start ~100ms.
- Reads command JSON from stdin (PreToolUse hook contract).
- Exit 0 = allow, exit 2 = block (Claude Code PreToolUse convention).
- Outputs blocking message on stdout when blocking.

Closes #1753.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Commands that are blocked when urgent state is unresolved.
GUARDED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*gh\s+pr\s+merge\b"),
    re.compile(r"uv\s+run\s+python\s+scripts/internal/ops\.py\s+task\s+dispatch\b"),
    re.compile(r"uv\s+run\s+python\s+scripts/internal/ops\.py\s+workers\s+dispatch\b"),
    re.compile(r"(?:uv\s+run\s+)?python[3]?\s.*dispatch_to_worker\s*\("),
]


def read_fleet_status(path: Path) -> dict | None:
    """Read and parse fleet_status.json.  Returns None on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def extract_urgent_alerts(data: dict) -> list[dict]:
    """Return open items with severity 'high' or 'urgent'."""
    items = data.get("items", [])
    return [
        i
        for i in items
        if i.get("severity") in ("high", "urgent") and i.get("state") == "open"
    ]


def is_guarded_command(command: str) -> bool:
    """Check if the command matches any guarded pattern."""
    return any(pattern.search(command) for pattern in GUARDED_PATTERNS)


def format_block_message(alerts: list[dict]) -> str:
    """Format a blocking message for the user."""
    lines = [
        f"BLOCKED: {len(alerts)} unresolved fleet alert(s) — resolve before proceeding.",
        "",
        "Unresolved alerts:",
    ]
    for a in alerts:
        sev = a.get("severity", "high").upper()
        summary = a.get("summary", "(no summary)")
        lines.append(f"  [{sev}] {summary}")
        rec = a.get("recommended_action")
        if rec:
            lines.append(f"    -> {rec}")
    lines.extend(
        [
            "",
            "Resolve or ack alerts before running risky commands:",
            "  uv run python scripts/internal/ops.py fleet --ack <item_id>",
        ]
    )
    return "\n".join(lines)


def main(stdin_text: str | None = None, project_dir: str | None = None) -> int:
    """Entry point.  Returns 0 to allow, 2 to block.

    Parameters are injectable for testing; production callers leave them None.
    """
    raw = stdin_text if stdin_text is not None else sys.stdin.read()

    # Parse hook input from stdin
    try:
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0  # Can't parse input — allow by default

    command = ""
    tool_input = hook_input.get("tool_input", {})
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")

    if not command or not is_guarded_command(command):
        return 0

    if project_dir is None:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    status_path = Path(project_dir) / ".claude" / "runtime" / "fleet_status.json"

    if not status_path.exists():
        return 0

    data = read_fleet_status(status_path)
    if data is None:
        return 0

    alerts = extract_urgent_alerts(data)
    if not alerts:
        return 0

    # Block the action
    print(format_block_message(alerts))
    return 2


if __name__ == "__main__":
    sys.exit(main())
