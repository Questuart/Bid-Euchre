"""Shadow-mode adaptive dispatch advisor (token economy Slice E, #2169).

This module is the SP-5-02 PR3/PR4 deliverable: a per-dispatch scorer that
reads token-economy outcome telemetry and emits a ranked lane recommendation
as a durable ``dispatch_recommendation`` event. The recommendation is
advisory only — it **never** alters the lane actually dispatched.

Architecture guardrails (enforced structurally, not just by convention):

1. **One-way dependency.** This module must NOT import
   :mod:`bid_euchre.ops.worker_pool`. The orchestrator side imports us; the
   inverse is forbidden. A future refactor that lets the advisor call
   :func:`dispatch_to_worker` directly would break the shadow-mode invariant.

2. **Purity of :func:`recommend_lanes`.** The scorer itself performs no file
   writes, no event emission, no tmux side-effects, and no network I/O.
   Its only inputs are the read-only token-economy / events substrate.

3. **Single side-effect function.** :func:`log_recommendation_for_dispatch`
   emits exactly one ``dispatch_recommendation`` event per call, and
   nothing else.

4. **Two-valued mode flag.** :data:`ADVISOR_MODE` accepts only ``"shadow"``
   (the default — log only) or ``"disabled"`` (skip logging). There is no
   ``"auto"`` value yet; adding it is a future PR whose safety depends on
   Slice F evaluation evidence.

Scoring policy is **deliberately unlocked** per
``plans/sessions/2026-04-20_token_economy_restart_plan.md §"Adaptive Dispatch
Policy Guardrails"``. Weights live in :data:`SCORE_WEIGHTS` and should be
tuned by editing the constants here; every change must bump
:data:`POLICY_VERSION` so historical recommendation logs remain interpretable.
``tests/unit/test_ops_learning.py::test_policy_version_matches_weights`` pins
the hash so weight drift without a version bump is caught mechanically.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.learning")


# ---------------------------------------------------------------------------
# Policy knobs — deliberately unlocked. Bump POLICY_VERSION on any change.
# ---------------------------------------------------------------------------

#: Weights applied to the four score components. Component definitions:
#: ``clean_rate`` (higher = cleaner merges), ``token_efficiency`` and
#: ``cycle_time`` (normalized inverses, higher = cheaper/faster),
#: ``rework_penalty`` (subtracts max(0, avg_review_rounds - 1.0)). Weights
#: intentionally do not sum to 1.0 so operators can read relative
#: contribution directly without renormalizing.
SCORE_WEIGHTS: dict[str, float] = {
    "clean_rate": 1.0,
    "token_efficiency": 0.5,
    "cycle_time": 0.3,
    "rework_penalty": 0.5,
}

#: Minimum observations before the scorer treats a lane's history as
#: informative. Lanes with fewer observations get ``confidence`` capped at
#: 0.3 (cold-start) regardless of their score magnitude.
MIN_OBS_FOR_CONFIDENCE: int = 5

#: Default rolling-window width for consuming historical outcomes.
WINDOW_DAYS_DEFAULT: int = 14

#: Cold-start confidence cap for lanes below MIN_OBS_FOR_CONFIDENCE.
_COLD_START_CONFIDENCE_CAP: float = 0.3

#: Human-readable policy version. Bump on any change to SCORE_WEIGHTS or
#: MIN_OBS_FOR_CONFIDENCE so recommendation logs remain interpretable.
POLICY_VERSION: str = "slice-e-v1"

#: Mode gate. Only two values exist in Slice E.
#:
#: - ``"shadow"``: emit ``dispatch_recommendation`` events but never alter
#:   the dispatched lane_id.
#: - ``"disabled"``: skip logging entirely. Useful for tests that wish to
#:   isolate the dispatch path.
ADVISOR_MODE: str = "shadow"

#: Permitted values for ADVISOR_MODE. Tested structurally.
_VALID_ADVISOR_MODES: frozenset[str] = frozenset({"shadow", "disabled"})


def policy_fingerprint() -> str:
    """Return a stable sha256 over the tunable policy knobs.

    Used by tests to detect weight drift without a corresponding
    :data:`POLICY_VERSION` bump.
    """
    payload = {
        "weights": {k: float(v) for k, v in sorted(SCORE_WEIGHTS.items())},
        "min_obs": MIN_OBS_FOR_CONFIDENCE,
        "cold_start_cap": _COLD_START_CONFIDENCE_CAP,
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Feature / recommendation dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaneFeatures:
    """Rolled-up observation features for a single candidate lane.

    Constructed by :func:`build_lane_features` from the outcome substrate.
    All numeric fields default to 0.0 when the lane has no observations, so
    downstream consumers never have to handle ``None``.
    """

    lane_id: str
    observations: int = 0
    clean_completion_rate: float = 0.0
    avg_tokens_per_packet: float = 0.0
    avg_elapsed_seconds: float = 0.0
    avg_review_rounds: float = 0.0
    confidence: float = 0.0


@dataclass(frozen=True)
class LaneRecommendation:
    """One ranked candidate in the advisor's output."""

    lane_id: str
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    features: LaneFeatures = field(default_factory=lambda: LaneFeatures(lane_id=""))


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _matches(
    record: Any,
    *,
    lane_id: str,
    task_type: str | None,
    complexity: int | None,
) -> bool:
    """Return True when an outcome record is in scope for this lane query."""
    if getattr(record, "actual_lane", None) != lane_id:
        return False
    if task_type is not None and getattr(record, "task_type", None) != task_type:
        return False
    if (
        complexity is not None
        and getattr(record, "complexity_estimate", None) != complexity
    ):
        return False
    return True


def build_lane_features(
    lane_id: str,
    *,
    task_type: str | None = None,
    complexity: int | None = None,
    window_days: int = WINDOW_DAYS_DEFAULT,
    events_dir: Path | None = None,
    output_dir: Path | None = None,
    _records: list[Any] | None = None,
) -> LaneFeatures:
    """Build rolling-window features for one candidate lane.

    Reads the task-completion outcome substrate via
    :func:`bid_euchre.ops.token_economy.join_outcomes_with_token_economy`,
    filters to the lane (optionally scoped to ``task_type`` / ``complexity``),
    and rolls into a :class:`LaneFeatures` summary.

    When ``token_spend`` is missing on an outcome, the lane-wide rollup
    (``lane_total_tokens / observations``) is used as a fallback denominator
    so the lane is not silently excluded. This matches the "Feature store
    skew" mitigation in the shaping comment.

    Parameters
    ----------
    lane_id
        Candidate lane identifier.
    task_type, complexity
        Optional scoping filters. When ``None``, the lane's entire window
        contributes.
    window_days
        Rolling-window width. Currently advisory: the underlying join reads
        the full events log, but we sort by ``completed_at`` descending and
        take the most recent observations so a bounded log stays bounded.
    events_dir, output_dir
        Overrides for the events directory and token-economy store. Forwarded
        to :func:`join_outcomes_with_token_economy`.
    _records
        Test-only override. When provided, skips the substrate read and
        operates directly on the supplied records. Not part of the public
        contract.

    Returns
    -------
    LaneFeatures
        Always well-formed; returns a zero-observation record when the lane
        has no in-scope outcomes.
    """
    if _records is None:
        # Deferred import to keep module import cheap and avoid circulars.
        from bid_euchre.ops.token_economy import (
            join_outcomes_with_token_economy,
        )

        try:
            _records = join_outcomes_with_token_economy(
                events_dir=events_dir,
                output_dir=output_dir,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug(
                "join_outcomes_with_token_economy unavailable: %s",
                exc,
            )
            _records = []

    # Future: honor window_days by parsing completed_at. Currently the outcome
    # log is bounded by drain_events() so full-log reads are already
    # window-bounded in practice. Left as an intentional no-op to keep
    # recommend_lanes() a pure function over its inputs.
    del window_days

    in_scope = [
        r
        for r in (_records or [])
        if _matches(r, lane_id=lane_id, task_type=task_type, complexity=complexity)
    ]
    observations = len(in_scope)

    if observations == 0:
        return LaneFeatures(lane_id=lane_id)

    # Clean completion rate: merged AND review_rounds <= 1. Missing
    # review_rounds is treated as "not clean" (conservative).
    clean = 0
    for r in in_scope:
        outcome = getattr(r, "shipped_outcome", None)
        rounds = getattr(r, "review_rounds", None)
        if outcome == "merged" and rounds is not None and rounds <= 1:
            clean += 1
    clean_rate = clean / observations

    # Token spend: per-packet mean when available, lane-wide fallback otherwise.
    token_spends = [
        float(r.token_spend)
        for r in in_scope
        if getattr(r, "token_spend", None) is not None
    ]
    if token_spends:
        avg_tokens = sum(token_spends) / len(token_spends)
    else:
        # Lane-wide fallback: use lane_total_tokens / observations from any
        # record that carries it. This is a coarse denominator — flagged by
        # the confidence cap below.
        lane_totals = [
            int(r.lane_total_tokens)
            for r in in_scope
            if getattr(r, "lane_total_tokens", None) is not None
        ]
        avg_tokens = (lane_totals[0] / observations) if lane_totals else 0.0

    # Elapsed time and review churn: treat missing fields as 0-contribution
    # but weight the averages by the count of present observations.
    elapsed_values = [
        float(r.elapsed_seconds)
        for r in in_scope
        if getattr(r, "elapsed_seconds", None) is not None
    ]
    avg_elapsed = sum(elapsed_values) / len(elapsed_values) if elapsed_values else 0.0

    rounds_values = [
        float(r.review_rounds)
        for r in in_scope
        if getattr(r, "review_rounds", None) is not None
    ]
    avg_rounds = sum(rounds_values) / len(rounds_values) if rounds_values else 0.0

    # Confidence: linear ramp up to MIN_OBS_FOR_CONFIDENCE, capped at 1.0.
    # Below the threshold, cap further at the cold-start ceiling so the
    # scorer can see "we lack evidence" without discarding the lane entirely.
    if observations >= MIN_OBS_FOR_CONFIDENCE:
        confidence = min(1.0, observations / float(MIN_OBS_FOR_CONFIDENCE))
    else:
        confidence = min(
            _COLD_START_CONFIDENCE_CAP,
            observations / float(MIN_OBS_FOR_CONFIDENCE),
        )

    return LaneFeatures(
        lane_id=lane_id,
        observations=observations,
        clean_completion_rate=clean_rate,
        avg_tokens_per_packet=avg_tokens,
        avg_elapsed_seconds=avg_elapsed,
        avg_review_rounds=avg_rounds,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score_one(
    feat: LaneFeatures,
    *,
    max_tokens: float,
    max_elapsed: float,
) -> tuple[float, tuple[str, ...]]:
    """Compute score and human-readable reasons for one lane."""
    reasons: list[str] = []

    clean_component = feat.clean_completion_rate * SCORE_WEIGHTS["clean_rate"]
    if feat.clean_completion_rate >= 0.8:
        reasons.append("high clean rate")
    elif feat.clean_completion_rate <= 0.4 and feat.observations > 0:
        reasons.append("low clean rate")

    # Normalized inverses: 0..1 where 1 is best (cheapest / fastest).
    if max_tokens > 0 and feat.avg_tokens_per_packet > 0:
        token_eff = max(0.0, 1.0 - (feat.avg_tokens_per_packet / max_tokens))
    else:
        token_eff = 0.0
    token_component = token_eff * SCORE_WEIGHTS["token_efficiency"]
    if feat.avg_tokens_per_packet > 0 and token_eff >= 0.5:
        reasons.append("low token avg")

    if max_elapsed > 0 and feat.avg_elapsed_seconds > 0:
        cycle_eff = max(0.0, 1.0 - (feat.avg_elapsed_seconds / max_elapsed))
    else:
        cycle_eff = 0.0
    cycle_component = cycle_eff * SCORE_WEIGHTS["cycle_time"]

    rework_excess = max(0.0, feat.avg_review_rounds - 1.0)
    rework_component = rework_excess * SCORE_WEIGHTS["rework_penalty"]
    if rework_excess >= 1.0:
        reasons.append("elevated review churn")

    score = clean_component + token_component + cycle_component - rework_component

    if feat.observations == 0:
        reasons.append("cold start — no observations")
    elif feat.observations < MIN_OBS_FOR_CONFIDENCE:
        reasons.append(f"cold start — {feat.observations}/{MIN_OBS_FOR_CONFIDENCE} obs")

    return score, tuple(reasons)


def recommend_lanes(
    candidates: list[str],
    *,
    task_type: str | None = None,
    complexity: int | None = None,
    window_days: int = WINDOW_DAYS_DEFAULT,
    events_dir: Path | None = None,
    output_dir: Path | None = None,
    _records: list[Any] | None = None,
) -> list[LaneRecommendation]:
    """Rank candidate lanes by learned score, best first.

    This function is **pure**: it reads the events and token-economy
    substrates (or the ``_records`` test override) and produces a ranked
    list. It performs no file writes, emits no events, and has no tmux
    side-effects. Null-safe: an empty substrate returns zero-score
    recommendations without raising.

    Deterministic ordering: ties are broken by ``lane_id`` ascending.

    Parameters
    ----------
    candidates
        Eligible lane identifiers to rank. An empty list returns an empty
        result.
    task_type, complexity
        Scoping filters forwarded to :func:`build_lane_features`.
    window_days
        Rolling-window width (advisory today — see
        :func:`build_lane_features`).
    events_dir, output_dir
        Substrate overrides.
    _records
        Test-only pre-joined outcome records. Not part of the public
        contract.

    Returns
    -------
    list[LaneRecommendation]
        Ranked best-first. Length equals ``len(candidates)``.
    """
    if not candidates:
        return []

    # Resolve substrate once so each lane sees the same snapshot. This is
    # what makes the function deterministic across the candidate set.
    if _records is None:
        from bid_euchre.ops.token_economy import (
            join_outcomes_with_token_economy,
        )

        try:
            _records = join_outcomes_with_token_economy(
                events_dir=events_dir,
                output_dir=output_dir,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("join_outcomes_with_token_economy unavailable: %s", exc)
            _records = []

    features = [
        build_lane_features(
            lane,
            task_type=task_type,
            complexity=complexity,
            window_days=window_days,
            _records=_records,
        )
        for lane in candidates
    ]

    # Normalization denominators are the per-set maxima of the positive
    # signals. Guard against a set where every lane is at 0.
    max_tokens = max((f.avg_tokens_per_packet for f in features), default=0.0)
    max_elapsed = max((f.avg_elapsed_seconds for f in features), default=0.0)

    recs: list[LaneRecommendation] = []
    for feat in features:
        score, reasons = _score_one(
            feat, max_tokens=max_tokens, max_elapsed=max_elapsed
        )
        recs.append(
            LaneRecommendation(
                lane_id=feat.lane_id,
                score=score,
                reasons=reasons,
                features=feat,
            )
        )

    # Deterministic ordering: score desc, then lane_id asc for tie-break.
    recs.sort(key=lambda r: (-r.score, r.lane_id))
    return recs


# ---------------------------------------------------------------------------
# Side-effect: emit one dispatch_recommendation event per dispatch.
# ---------------------------------------------------------------------------


def _feature_payload(feat: LaneFeatures) -> dict[str, Any]:
    return {
        "observations": feat.observations,
        "clean_completion_rate": feat.clean_completion_rate,
        "avg_tokens_per_packet": feat.avg_tokens_per_packet,
        "avg_elapsed_seconds": feat.avg_elapsed_seconds,
        "avg_review_rounds": feat.avg_review_rounds,
    }


def log_recommendation_for_dispatch(
    *,
    packet: Any,
    candidates: list[str],
    selected_lane: str,
    events_dir: Path | None = None,
    output_dir: Path | None = None,
    source: str = "ops.learning",
) -> dict[str, Any] | None:
    """Emit one ``dispatch_recommendation`` event for this dispatch.

    This is the **only** side-effect function in the module. It:

    1. Computes a ranked recommendation over ``candidates`` (via
       :func:`recommend_lanes`).
    2. Appends exactly one ``dispatch_recommendation`` event to the durable
       event log.
    3. Returns the event dict (or ``None`` when
       :data:`ADVISOR_MODE` is ``"disabled"``).

    The returned dict is informational — callers MUST NOT use it to change
    which lane gets dispatched. The shadow-mode invariant is enforced by
    the caller: ``dispatch_to_worker`` invokes this function and then
    continues with the caller-supplied ``lane_id`` unchanged.

    Parameters
    ----------
    packet
        The :class:`~bid_euchre.ops.task_queue.TaskPacket` being dispatched
        (read-only access to ``metadata`` for task_type / complexity).
    candidates
        Eligible lane IDs the advisor could have ranked. May or may not
        include ``selected_lane``.
    selected_lane
        The lane the dispatcher actually chose. Recorded verbatim.
    events_dir, output_dir
        Substrate / event-log overrides.
    source
        Producer tag for the event. Defaults to ``ops.learning``.

    Returns
    -------
    dict | None
        The event dict written to the log, or ``None`` when advisor mode is
        ``"disabled"``.
    """
    if ADVISOR_MODE == "disabled":
        return None
    if ADVISOR_MODE not in _VALID_ADVISOR_MODES:
        # Configuration error — log and skip rather than crash dispatch.
        logger.warning(
            "Unknown ADVISOR_MODE %r; skipping recommendation log",
            ADVISOR_MODE,
        )
        return None

    # Extract routing context from the packet. All accesses are defensive
    # because older packets may lack the Slice C metadata contract.
    try:
        from bid_euchre.ops.task_queue import get_complexity, get_task_type

        task_type = get_task_type(packet)
        complexity = get_complexity(packet)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Failed to extract packet routing metadata: %s", exc)
        task_type = None
        complexity = None

    recs = recommend_lanes(
        list(candidates),
        task_type=task_type,
        complexity=complexity,
        events_dir=events_dir,
        output_dir=output_dir,
    )

    ranked_payload = [
        {
            "lane_id": r.lane_id,
            "score": r.score,
            "confidence": r.features.confidence,
            "rank": idx + 1,
            "reasons": list(r.reasons),
            "features": _feature_payload(r.features),
        }
        for idx, r in enumerate(recs)
    ]

    # "override" flag: did the dispatcher pick something other than the
    # top-ranked candidate? Computed by the logger, not supplied by the
    # caller — this is the invariant enforcement point.
    top_lane = recs[0].lane_id if recs else None
    override = bool(top_lane and selected_lane != top_lane)

    packet_id = getattr(packet, "packet_id", None) or ""

    payload: dict[str, Any] = {
        "packet_id": packet_id,
        "task_type": task_type,
        "complexity_estimate": complexity,
        "candidates": ranked_payload,
        "selected_lane": selected_lane,
        "override": override,
        "override_reason": None,
        "policy_version": POLICY_VERSION,
        "window_days": WINDOW_DAYS_DEFAULT,
        "advisor_mode": ADVISOR_MODE,
    }

    try:
        from bid_euchre.ops.events import append_event

        return append_event(
            "dispatch_recommendation",
            source=source,
            lane_id=selected_lane,
            payload=payload,
            events_dir=events_dir,
        )
    except Exception as exc:
        # Best-effort: never fail dispatch because the advisor log failed.
        logger.warning(
            "Failed to emit dispatch_recommendation for %s: %s",
            packet_id,
            exc,
        )
        return None
