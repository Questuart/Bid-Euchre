"""Lane model-tier loader for `.claude/lane_models.json`.

This module is the Python-side source of truth for the per-lane model-tier
mapping that drives the Claude Code launch-flag choice per
``.claude/rules/80_permission_model.md`` §"Model-tier activation constraint".

Schema::

    {
      "_comment": "...",
      "_schema_version": 1,
      "lanes": {
        "<lane-id>": {"model": "opus" | "sonnet" | "haiku"},
        ...
      }
    }

The shell-side loader in ``.claude/tmux/steward-session.sh`` reads the same
file via an inline ``python3`` invocation and must stay behaviorally
consistent with this module. The two loaders share a canonical config file;
any behavior change here requires a matching change in the shell.

Rationale
---------

* **Opus lanes** launch with ``--permission-mode auto`` so the Sonnet-4.6
  classifier gate is active. Passing this flag to a non-Opus session
  silently falls back to ``bypassPermissions`` with no enforcement
  legibility — the worst outcome (see §"Model tier interaction constraint"
  and #2767 for the live ops-lane gap).
* **Sonnet / Haiku lanes** launch with ``--dangerously-skip-permissions``
  so the reduced safety envelope is legible at every observation point
  (log output, ``gh pr checks``, operator-readable launch command).
* **Unknown / missing lanes** default to ``opus``. The fleet today is 100%
  Opus; new lanes are expected to declare a tier explicitly in the config.

Public API
----------

* :func:`load_lane_models` — parse the config file (or a test override).
* :func:`get_lane_model` — return the model tier for a single lane (with
  ``"opus"`` as the fallback).
* :func:`permission_mode_args_for_lane` — return the argv fragment (list)
  that should be spliced into a ``claude`` subprocess invocation for the
  given lane. Callers pass this through ``list.extend`` rather than
  string-splicing, avoiding shell-escape surprises.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("lane_models")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Valid model tiers. Unrecognized values coerce to ``DEFAULT_MODEL``.
VALID_MODELS: frozenset[str] = frozenset({"opus", "sonnet", "haiku"})

#: Default tier applied when a lane is missing from the config or the config
#: is unreadable. Chosen to match the current 100%-Opus fleet (#2767).
DEFAULT_MODEL: str = "opus"

#: Repo-relative path to the canonical config file.
_CONFIG_RELPATH = Path(".claude/lane_models.json")


def _default_config_path() -> Path:
    """Return the canonical config path anchored at the repo root.

    The repo root is inferred from this file's location
    (``scripts/internal/lane_models.py`` → two ``parent`` hops).
    """
    return Path(__file__).resolve().parent.parent.parent / _CONFIG_RELPATH


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_lane_models(config_path: Path | None = None) -> dict[str, str]:
    """Load the lane → model-tier mapping from the config file.

    Args:
        config_path: Optional override for the config file path. When omitted,
            the canonical path ``.claude/lane_models.json`` relative to the
            repo root is used.

    Returns:
        A dict keyed by lane id with tier-string values. Unrecognized tier
        values are coerced to :data:`DEFAULT_MODEL`. Missing or malformed
        config files yield an empty dict — callers should treat missing
        lookups as :data:`DEFAULT_MODEL` via :func:`get_lane_model`.
    """
    path = config_path if config_path is not None else _default_config_path()
    if not path.exists():
        logger.debug("lane_models.json not found at %s — returning empty mapping", path)
        return {}

    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not parse lane_models.json at %s: %s", path, exc)
        return {}

    lanes = raw.get("lanes")
    if not isinstance(lanes, dict):
        logger.warning("lane_models.json at %s missing or malformed 'lanes' key", path)
        return {}

    mapping: dict[str, str] = {}
    for lane_id, entry in lanes.items():
        if not isinstance(lane_id, str) or not lane_id:
            continue
        model = None
        if isinstance(entry, dict):
            model = entry.get("model")
        if not isinstance(model, str) or model not in VALID_MODELS:
            logger.warning(
                "lane_models.json: lane %r has invalid model %r — coercing to %r",
                lane_id,
                model,
                DEFAULT_MODEL,
            )
            model = DEFAULT_MODEL
        mapping[lane_id] = model
    return mapping


def get_lane_model(lane_id: str, config_path: Path | None = None) -> str:
    """Return the model tier for a single lane, defaulting to ``"opus"``.

    Args:
        lane_id: The lane identifier (e.g., ``"author-c"``).
        config_path: Optional override for the config file path.

    Returns:
        One of ``"opus"``, ``"sonnet"``, or ``"haiku"``. Falls back to
        :data:`DEFAULT_MODEL` when the lane is not listed or the config is
        unreadable.
    """
    mapping = load_lane_models(config_path)
    return mapping.get(lane_id, DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# Permission-mode argv emitter
# ---------------------------------------------------------------------------


def permission_mode_args_for_lane(
    lane_id: str, config_path: Path | None = None
) -> list[str]:
    """Return the argv fragment that activates the correct permission mode.

    The fragment is designed to be spliced into a ``claude`` subprocess
    argv list via ``list.extend``.

    * ``opus`` →  ``["--permission-mode", "auto"]``
    * ``sonnet`` / ``haiku`` → ``["--dangerously-skip-permissions"]``

    Never cross-wire these flags. Passing ``--permission-mode auto`` to a
    non-Opus session silently falls back to ``bypassPermissions`` with no
    enforcement legibility (the failure mode documented in #2767).

    Args:
        lane_id: The lane identifier (e.g., ``"review"``).
        config_path: Optional override for the config file path.

    Returns:
        A list of CLI tokens.
    """
    model = get_lane_model(lane_id, config_path)
    if model == "opus":
        return ["--permission-mode", "auto"]
    # sonnet / haiku — ``--dangerously-skip-permissions`` is the explicit
    # legible reduced-safety envelope.
    return ["--dangerously-skip-permissions"]
