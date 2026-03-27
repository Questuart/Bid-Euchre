"""Telegram lane routing filter (issue #1824, part 2).

When the steward fleet runs, every lane shares the same
``.claude/settings.json`` which enables the Telegram plugin.  Each lane
therefore spawns its own ``bun server.ts`` process that polls the same
Telegram bot.  Only one instance receives each inbound message
(non-deterministic), so non-orchestrator lanes may consume messages meant
for the orchestrator.

This module provides a lane-detection guard that hooks and library code
use to **skip Telegram processing on non-orchestrator lanes**.  It is the
code-level defence-in-depth complement to the config-level fix (part 1).

Detection strategy (in priority order):

1. **Explicit env var** ``STEWARD_TELEGRAM_RECEIVER=1`` — set by the tmux
   launcher on the orchestrator pane only.  Fastest check, no path parsing.
2. **Project directory** ``CLAUDE_PROJECT_DIR`` — falls back to matching the
   directory basename against known orchestrator worktree names.

Usage::

    from bid_euchre.ops.telegram_filter import is_telegram_receiver

    if not is_telegram_receiver():
        return  # Skip Telegram processing on non-orchestrator lanes

For shell hooks, use :func:`detect_lane_from_env` directly or check the
env var in bash before invoking Python.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("ops.telegram_filter")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Env var that, when ``"1"``, marks this lane as the Telegram receiver.
#: Set by the tmux launcher on the orchestrator pane.
TELEGRAM_RECEIVER_ENV = "STEWARD_TELEGRAM_RECEIVER"

#: Worktree directory basenames that correspond to the orchestrator lane.
#: The orchestrator typically runs from the main ``Bid-Euchre`` checkout
#: or from ``Bid-Euchre-steward-ops`` when the ops lane owns Telegram.
ORCHESTRATOR_WORKTREES: frozenset[str] = frozenset(
    {
        "Bid-Euchre",  # Main checkout — default orchestrator
    }
)


# ---------------------------------------------------------------------------
# Lane detection
# ---------------------------------------------------------------------------


def detect_lane_from_env() -> str | None:
    """Infer the current lane identity from environment variables.

    Checks ``CLAUDE_PROJECT_DIR`` and extracts the directory basename.
    Returns the basename if it looks like a steward worktree, the string
    ``"main-checkout"`` if it matches the main ``Bid-Euchre`` directory,
    or ``None`` if detection fails.
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return None

    basename = Path(project_dir).name

    if basename == "Bid-Euchre":
        return "main-checkout"

    if "steward" in basename:
        return basename

    return None


def is_telegram_receiver(
    *,
    receiver_env: str | None = None,
    project_dir: str | None = None,
) -> bool:
    """Return ``True`` if the current lane should process Telegram messages.

    This is the primary guard function.  Call it from hooks and library
    code to skip Telegram processing on non-orchestrator lanes.

    Detection order:

    1. If ``STEWARD_TELEGRAM_RECEIVER`` env var is ``"1"`` → True.
    2. If ``STEWARD_TELEGRAM_RECEIVER`` env var is ``"0"`` → False
       (explicit opt-out, e.g. for testing).
    3. If ``CLAUDE_PROJECT_DIR`` basename is in
       :data:`ORCHESTRATOR_WORKTREES` → True.
    4. Otherwise → False.

    Args:
        receiver_env: Override for the ``STEWARD_TELEGRAM_RECEIVER`` env var
            value.  When ``None``, reads from the real environment.
        project_dir: Override for ``CLAUDE_PROJECT_DIR``.  When ``None``,
            reads from the real environment.

    Returns:
        ``True`` if this lane is the designated Telegram receiver.
    """
    # Check 1 & 2: explicit env var
    env_val = (
        receiver_env
        if receiver_env is not None
        else os.environ.get(TELEGRAM_RECEIVER_ENV, "")
    )
    if env_val == "1":
        return True
    if env_val == "0":
        return False

    # Check 3: project directory
    dir_val = (
        project_dir
        if project_dir is not None
        else os.environ.get("CLAUDE_PROJECT_DIR", "")
    )
    if not dir_val:
        # No env var, no project dir — conservative: refuse to process.
        logger.debug(
            "telegram_filter: no %s or CLAUDE_PROJECT_DIR — defaulting to non-receiver",
            TELEGRAM_RECEIVER_ENV,
        )
        return False

    basename = Path(dir_val).name
    is_orch = basename in ORCHESTRATOR_WORKTREES

    if not is_orch:
        logger.debug(
            "telegram_filter: lane %r is not an orchestrator worktree — "
            "skipping Telegram processing",
            basename,
        )

    return is_orch
