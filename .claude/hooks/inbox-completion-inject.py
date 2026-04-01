#!/usr/bin/env python3
"""UserPromptSubmit hook: inject unacked completion messages as additionalContext.

When author/analyst lanes complete tasks, they send ``completion`` messages to
the orchestrator's inbox via the message bus.  This hook reads those messages,
formats a summary, injects it as ``additionalContext``, and auto-acks the
injected messages so they are not re-injected on the next prompt.

Design constraints:
- Best-effort: failures never block prompt submission.
- Uses ``uv run`` to access project imports (bid_euchre.ops.message_bus).
- Lazy imports for project modules to keep the fast-exit path lightweight.
- Auto-acks injected messages to prevent re-injection.

Closes #1986.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Entry point.  Returns 0 always (never blocks prompt submission)."""
    # Lazy import — only load project modules when we actually run
    try:
        from bid_euchre.ops.message_bus import ack_message, read_inbox
    except ImportError:
        return 0

    # Read the orchestrator inbox for unacked completion messages.
    # Status "delivered" or "pending" are the actionable states.
    completions: list[dict] = []
    for status in ("delivered", "pending"):
        msgs = read_inbox(
            "orchestrator",
            status=status,
            message_type="completion",
            limit=20,
            auto_expire=True,
            auto_compact=False,  # Don't compact on every prompt
        )
        completions.extend(msgs)

    if not completions:
        return 0

    # Format the completion summary
    lines = [f"LANE COMPLETIONS ({len(completions)} unacked):"]
    acked_ids: list[str] = []

    for msg in completions:
        from_lane = msg.get("from_lane", "unknown")
        summary = msg.get("summary", "(no summary)")
        task_id = msg.get("task_id", "")
        msg_id = msg.get("message_id", "")

        task_suffix = f" [task:{task_id[:12]}]" if task_id else ""
        lines.append(f"  [{from_lane}] {summary}{task_suffix}")

        if msg_id:
            acked_ids.append(msg_id)

    lines.append("")
    lines.append(
        "These lanes have finished their tasks. Consider reviewing their PRs "
        "and dispatching new work."
    )

    context = "\n".join(lines)

    # Auto-ack the injected messages so they don't re-inject on the next prompt.
    for mid in acked_ids:
        try:
            ack_message(mid, "orchestrator")
        except Exception:  # noqa: BLE001 — best-effort
            pass

    # Output the additionalContext payload
    print(json.dumps({"additionalContext": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
