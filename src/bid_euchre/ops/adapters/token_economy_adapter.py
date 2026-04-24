"""Token-economy adapter — per-deployment-cell knowledge boundary.

This module houses the Bid-Euchre-cell-specific literals that the generic
:mod:`bid_euchre.ops.token_economy` scanner depends on:

- :data:`_WORKTREE_TO_LANE` — the canonical worktree-basename → lane-id map.
- :func:`_infer_lane_from_slug` — slug-suffix lane-inference heuristic.
- :func:`infer_lane_from_path` — filesystem-path lane-inference heuristic.

Extracting these into the adapter layer is the Primitive G.2 portability
move (plan: ``plans/steward_platform/7_primitive_G/migrations/01_token_economy_to_native_usage.md``
§2.1). :mod:`bid_euchre.ops.token_economy` now delegates to this module
for lane inference; the 25 hard-block lines reported by
``scripts/internal/audit_portability.py`` against ``token_economy.py``
disappear.

The adapter is also the **cohort-dispatch boundary** for the
``STEWARD_TOKEN_ECONOMY_NATIVE_USAGE`` feature flag (plan §3). When the
flag is flipped on, :func:`read_session_records` invokes both the
bespoke and native cohort paths and emits a ``proving_run_cohort_sample``
event per invocation so the proving-run measurement method (§5) can
aggregate token-cost deltas from the event stream.

**Import-cycle invariant (plan §7.7 risk #4):** this module must NOT
import from :mod:`bid_euchre.ops.token_economy`. The dependency
direction is always ``token_economy → adapter``. Lane-inference
constants live HERE; scanner / rollup logic lives in ``token_economy``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag (per plan §3.1 + .claude/rules/feature_flags.md registry)
# ---------------------------------------------------------------------------

#: Feature-flag env var controlling dual-write to native `/usage` + `/cost`.
#:
#: - ``0`` / unset — bespoke-only path (Cohort A). Safe forward default.
#: - ``1`` — dual-write (both Cohort A and Cohort B emit the proving-run
#:   event). Flag flipped ON during the proving-run observation window
#:   only (plan §3.4 — 1 calendar week minimum).
#:
#: Rollback SLO: operator unsets → consumer resumes bespoke-only within
#: 1 minute. The flag is read on every invocation of
#: :func:`read_session_records`, so no cache invalidation is needed.
NATIVE_USAGE_FLAG = "STEWARD_TOKEN_ECONOMY_NATIVE_USAGE"


def native_usage_enabled() -> bool:
    """Return True if ``STEWARD_TOKEN_ECONOMY_NATIVE_USAGE`` is set to a truthy value."""
    value = os.environ.get(NATIVE_USAGE_FLAG, "")
    return value not in ("", "0", "false", "False", "FALSE", "no", "No", "NO")


# ---------------------------------------------------------------------------
# Worktree → lane canonical map (moved from token_economy.py:990-1016)
# ---------------------------------------------------------------------------

#: Canonical mapping from worktree directory basenames to lane IDs.
#:
#: Matches the pool definitions in
#: :data:`bid_euchre.ops.task_queue.KNOWN_AUTHOR_LANES` and
#: ``worktrees.PROTECTED_WORKTREE_NAMES``. Owned here (the adapter layer)
#: so the generic token-economy scanner is free of deployment-cell
#: literals.
_WORKTREE_TO_LANE: dict[str, str] = {
    # Platform pool
    "Bid-Euchre-steward-author": "author-a",
    "Bid-Euchre-steward-author-b": "author-b",
    "Bid-Euchre-steward-author-c": "author-c",
    "Bid-Euchre-steward-author-d": "author-d",
    # Browser-game pool
    "Bid-Euchre-steward-brws-author-a": "brws-author-a",
    "Bid-Euchre-steward-brws-author-b": "brws-author-b",
    "Bid-Euchre-steward-brws-author-c": "brws-author-c",
    "Bid-Euchre-steward-brws-author-d": "brws-author-d",
    # Analyst pool (analyst-a reuses the original steward-analyst worktree)
    "Bid-Euchre-steward-analyst": "analyst-a",
    "Bid-Euchre-steward-analyst-b": "analyst-b",
    "Bid-Euchre-steward-analyst-c": "analyst-c",
    "Bid-Euchre-steward-analyst-d": "analyst-d",
    # Flex pool
    "Bid-Euchre-steward-flex-a": "flex-a",
    "Bid-Euchre-steward-flex-b": "flex-b",
    "Bid-Euchre-steward-flex-c": "flex-c",
    "Bid-Euchre-steward-flex-d": "flex-d",
    # Control plane
    "Bid-Euchre-steward-review": "review",
    "Bid-Euchre-steward-ops": "ops",
    # Legacy (retired from active layout, kept for attribution)
    "Bid-Euchre-steward-author-scratch": "author-scratch",
}


#: Worktree class categorization by lane prefix.
#:
#: Consumed by :func:`bid_euchre.ops.token_economy._classify_pool`; kept
#: alongside :data:`_WORKTREE_TO_LANE` so both deployment-cell structures
#: live in a single file.
_LANE_POOL: dict[str, str] = {
    "author-": "platform",
    "brws-author-": "browser-game",
    "analyst-": "analyst",
    "flex-": "flex",
    "review": "control",
    "ops": "control",
}


#: Main checkout's bare project directory (no steward suffix).
#:
#: Consumed by :func:`_infer_lane_from_slug` and :func:`infer_lane_from_path`
#: when a session's path lacks any ``steward-`` marker. Folded into the
#: adapter literals so the token-economy scanner is deployment-cell free.
MAIN_CHECKOUT_BASENAME = "Bid-Euchre"
MAIN_CHECKOUT_LANE = "main-checkout"

#: Regex that recognizes the ``Bid-Euchre-steward-<suffix>`` pattern. Used
#: as a fallback in :func:`infer_lane_from_path` when a direct basename
#: lookup misses. Moved here from ``token_economy.py:1095`` to collect the
#: worktree-name-literal / steward-prefix-regex vocabulary in one place.
_STEWARD_PATTERN = re.compile(r"Bid-Euchre-steward-([a-z0-9-]+)")


# ---------------------------------------------------------------------------
# Lane inference (moved from token_economy.py:330-358 + 1060-1108)
# ---------------------------------------------------------------------------


def _infer_lane_from_slug(slug: str) -> tuple[str | None, str | None]:
    """Infer lane ID and worktree name from a project directory slug.

    Claude stores per-project telemetry under
    ``~/.claude/projects/<slug>/`` where *slug* is the project's absolute
    path with ``/`` replaced by ``-``.

    This function matches known worktree names against the slug suffix,
    preferring the longest match to avoid ambiguity (e.g., ``Bid-Euchre``
    vs ``Bid-Euchre-steward-author``).

    Returns
    -------
    tuple[str | None, str | None]
        ``(lane_id, worktree_name)`` if a known worktree is matched,
        ``(None, None)`` otherwise.
    """
    if not slug:
        return None, None

    # Try longest-first matching of known worktree names against slug suffix.
    for wt_name in sorted(_WORKTREE_TO_LANE, key=len, reverse=True):
        if slug.endswith(wt_name):
            return _WORKTREE_TO_LANE[wt_name], wt_name

    # Main checkout fallback: a slug ending in the bare project basename
    # (no ``steward-`` segment) is the shared checkout, not a steward lane.
    if slug.endswith(MAIN_CHECKOUT_BASENAME) and "steward" not in slug:
        return MAIN_CHECKOUT_LANE, MAIN_CHECKOUT_BASENAME

    return None, None


def infer_lane_from_path(project_path: str | None) -> tuple[str | None, str | None]:
    """Infer lane ID and worktree name from a session's project_path.

    Parameters
    ----------
    project_path
        The ``project_path`` field from a session record (absolute filesystem path).

    Returns
    -------
    tuple[str | None, str | None]
        ``(lane_id, worktree_name)`` if the path matches a known steward worktree,
        ``(None, None)`` otherwise.
    """
    if not project_path:
        return None, None

    # Extract directory basename from the path.
    # Handle paths that may end with / or contain subdirectories.
    path = Path(project_path)
    basename = path.name

    # Direct match against known worktree names.
    lane_id = _WORKTREE_TO_LANE.get(basename)
    if lane_id is not None:
        return lane_id, basename

    # Check parent directories — sessions may run from subdirectories.
    for parent in path.parents:
        parent_name = parent.name
        lane_id = _WORKTREE_TO_LANE.get(parent_name)
        if lane_id is not None:
            return lane_id, parent_name

    # Heuristic: look for the ``Bid-Euchre-steward-<suffix>`` pattern in
    # the path and reconstruct the canonical basename.
    match = _STEWARD_PATTERN.search(project_path)
    if match:
        suffix = match.group(1)
        worktree_name = f"{MAIN_CHECKOUT_BASENAME}-steward-{suffix}"
        lane_id = _WORKTREE_TO_LANE.get(worktree_name)
        if lane_id is not None:
            return lane_id, worktree_name

    # Main checkout fallback (bare project basename; not a steward lane).
    if (
        basename == MAIN_CHECKOUT_BASENAME
        or f"/{MAIN_CHECKOUT_BASENAME}/" in project_path
    ):
        return MAIN_CHECKOUT_LANE, MAIN_CHECKOUT_BASENAME

    return None, None


# ---------------------------------------------------------------------------
# Cohort dispatch + proving_run_cohort_sample emission (plan §3.2)
# ---------------------------------------------------------------------------


def _emit_cohort_sample(
    cohort: str,
    lane_id: str | None,
    task_id: str | None,
    token_cost: int,
    behavioral_divergence: bool,
    window_id: str | None,
) -> None:
    """Emit a ``proving_run_cohort_sample`` event via the Primitive A dispatcher.

    Best-effort per shaping §3.4 ADR 007 never-raises discipline: if the
    event-schema registry has not yet learned ``proving_run_cohort_sample``
    (the schema entry lands separately with the F.11 emitter package),
    :func:`bid_euchre.ops.events.emit` logs the rejection and returns.
    The adapter still functions; the event stream will pick up samples
    once the registry entry is present.

    Parameters mirror `bespoke_surface_audit.md` §3.7 Pattern-8 fields:
    ``(surface, cohort, lane_id, task_id, token_cost,
    behavioral_divergence_bool, window_id)``.
    """
    try:
        # Import lazily so the adapter module is importable even if
        # events is being refactored concurrently.
        from bid_euchre.ops import events as _events

        _events.emit(
            "proving_run_cohort_sample",
            surface="token_economy",
            cohort=cohort,
            lane_id=lane_id,
            task_id=task_id,
            token_cost=token_cost,
            behavioral_divergence_bool=behavioral_divergence,
            window_id=window_id,
        )
    except Exception as exc:  # pragma: no cover — emit is never-raises itself
        logger.debug(
            "proving_run_cohort_sample emission skipped: %s (%s)",
            type(exc).__name__,
            exc,
        )


# ---------------------------------------------------------------------------
# read_session_records — cohort-aware record reader (plan §3.2)
# ---------------------------------------------------------------------------


#: Valid cohort-source tags for :func:`read_session_records`.
_VALID_SOURCES = frozenset({"bespoke", "native", "auto"})


def _read_records_from_store(output_dir: Path | str) -> list[dict[str, Any]]:
    """Load normalized SessionRecord dicts from the token-economy store.

    Reads the ``session_usage.jsonl`` file written by
    :func:`bid_euchre.ops.token_economy.import_project_jsonl`. Skips
    malformed JSON lines so a partial store is still consumable; a
    missing or empty store returns an empty list.

    This is the bespoke cohort's record-source — lines 1119-1133 of
    ``token_economy.py`` (``_load_sessions``) implement the same read,
    kept duplicated here so the adapter has zero inbound imports from
    ``token_economy`` (plan §7.7 risk #4).
    """
    path = Path(output_dir) / "session_usage.jsonl"
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_session_records(
    output_dir: Path | str,
    *,
    source: str = "auto",
    lane_id: str | None = None,
    task_id: str | None = None,
    window_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return session-record dicts for token-economy rollups.

    This is the cohort-aware entry point for the Primitive G.2 migration.
    It reads the same ``session_usage.jsonl`` substrate regardless of
    cohort — per plan §5.1, both cohorts share the raw JSONL source and
    the delta we measure is the *migration-path overhead*, not a native
    token saving.

    Parameters
    ----------
    output_dir
        Token-economy store directory (usually
        ``.claude/runtime/token_economy/``).
    source
        One of ``"auto"`` (default — uses
        :func:`native_usage_enabled` to pick cohort), ``"bespoke"``
        (Cohort A), ``"native"`` (Cohort B; currently reads the same
        substrate and is structurally distinguishable via the emitted
        cohort sample). Plan §3.2 dual-write: when the flag is ON and
        ``source == "auto"``, both paths run; the bespoke path is
        authoritative for the return value and the native path's record
        list is compared for observability (proving-run only).
    lane_id, task_id, window_id
        Correlation fields threaded into the
        ``proving_run_cohort_sample`` event emission. All optional; the
        event schema tolerates ``None`` for each.

    Returns
    -------
    list[dict[str, Any]]
        The session-record dict list, same shape both cohorts.
    """
    if source not in _VALID_SOURCES:
        raise ValueError(f"Unknown source {source!r}; valid: {sorted(_VALID_SOURCES)}")

    # Cohort resolution — 'auto' reads the flag; explicit 'bespoke' /
    # 'native' overrides for test injection.
    if source == "auto":
        resolved_source = "native" if native_usage_enabled() else "bespoke"
        dual_write = native_usage_enabled()
    else:
        resolved_source = source
        dual_write = False

    # Bespoke path — always runs when dual-writing OR when it is the
    # resolved source. Authoritative for the return value.
    bespoke_records = _read_records_from_store(output_dir)

    if dual_write:
        # Native cohort also runs for observability. Today this reads the
        # same substrate (native /usage subprocess integration is a
        # follow-on; see plan §2.2 "usage import" row where the native
        # substitute is the raw JSONL read). The cohort tag on the
        # emitted sample still distinguishes the call paths.
        native_records = _read_records_from_store(output_dir)
        behavioral_divergence = bespoke_records != native_records
        bespoke_cost = sum(_record_token_total(r) for r in bespoke_records)
        native_cost = sum(_record_token_total(r) for r in native_records)

        _emit_cohort_sample(
            cohort="A",
            lane_id=lane_id,
            task_id=task_id,
            token_cost=bespoke_cost,
            behavioral_divergence=False,
            window_id=window_id,
        )
        _emit_cohort_sample(
            cohort="B",
            lane_id=lane_id,
            task_id=task_id,
            token_cost=native_cost,
            behavioral_divergence=behavioral_divergence,
            window_id=window_id,
        )
    else:
        # Single-cohort mode — emit only the active cohort's sample so
        # the event stream still carries attribution for the window.
        cohort_tag = "B" if resolved_source == "native" else "A"
        cost = sum(_record_token_total(r) for r in bespoke_records)
        _emit_cohort_sample(
            cohort=cohort_tag,
            lane_id=lane_id,
            task_id=task_id,
            token_cost=cost,
            behavioral_divergence=False,
            window_id=window_id,
        )

    return bespoke_records


def _record_token_total(record: dict[str, Any]) -> int:
    """Sum the per-session token counts that define the §5.1 counter.

    ``input_tokens + output_tokens + cache_creation_tokens +
    cache_read_tokens``. Missing fields default to 0 per the v2→v3
    schema-migration tolerance contract in ``token_economy.py``.
    """
    return (
        int(record.get("input_tokens") or 0)
        + int(record.get("output_tokens") or 0)
        + int(record.get("cache_creation_tokens") or 0)
        + int(record.get("cache_read_tokens") or 0)
    )


__all__ = [
    "MAIN_CHECKOUT_BASENAME",
    "MAIN_CHECKOUT_LANE",
    "NATIVE_USAGE_FLAG",
    "_LANE_POOL",
    "_WORKTREE_TO_LANE",
    "_infer_lane_from_slug",
    "infer_lane_from_path",
    "native_usage_enabled",
    "read_session_records",
]
