"""Shadow-mode adaptive dispatch advisor (token economy Slice E, #2169).

Extended by Primitive B Phase 0 (B.1 — adaptive dispatch, per
``plans/steward_platform/2_primitive_B/shaping.md`` §3). The B.1 extension
adds safety-envelope + model-tier awareness (per ADR 006) on top of the
existing shadow-mode advisor.

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
   Its only inputs are the read-only token-economy / events substrate and
   the ``.claude/lane_models.json`` config (read-only).

3. **Single side-effect function.** :func:`log_recommendation_for_dispatch`
   emits exactly one ``dispatch_recommendation`` event per call, and
   nothing else.

4. **Two-valued mode flag.** :data:`ADVISOR_MODE` accepts only ``"shadow"``
   (the default — log only) or ``"disabled"`` (skip logging). There is no
   ``"auto"`` value yet; adding it is a future PR whose safety depends on
   Slice F evaluation evidence.

B.1 additions (Primitive B Phase 0, POLICY_VERSION "b1-v1"):

* ``required_safety_envelope`` / ``required_model_tier`` kwargs on
  :func:`recommend_lanes` pre-filter candidate lanes against the ADR 006
  §Model-tier interaction table.
* Three new scoring inputs (``model_tier_match``, ``effort_match``,
  ``safety_envelope_penalty``) — advisory weights per §3.1.
* Destructive-tool escalation via :func:`derive_required_envelope` —
  tool-risk registry consultation per §3.5. Callers may pass
  ``required_tools`` so a ``reject-under-bypass`` tool forces auto-mode
  filtering regardless of the caller's envelope preference.
* :func:`log_recommendation_for_dispatch` payload adds
  ``required_safety_envelope``, ``required_model_tier``, ``filtered_lanes``,
  ``warnings``, ``safety_envelope_override``, ``override_reason`` fields.

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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("ops.learning")


# ---------------------------------------------------------------------------
# Policy knobs — deliberately unlocked. Bump POLICY_VERSION on any change.
# ---------------------------------------------------------------------------

#: Weights applied to the four score components.
#:
#: - ``clean_rate`` — higher clean-merge rate (shipped_outcome=="merged" AND
#:   review_rounds<=1) is better.
#: - ``token_efficiency`` — normalized inverse of ``avg_tokens_per_packet``
#:   across the current candidate set. Higher = cheaper.
#: - ``cycle_time`` — normalized inverse of ``avg_elapsed_seconds`` across
#:   the current candidate set. Higher = faster.
#: - ``rework_penalty`` — subtracts ``max(0, avg_review_rounds - 1.0)``.
#:
#: Weights intentionally do not sum to 1.0 so operators can read the
#: relative contribution directly without renormalizing.
SCORE_WEIGHTS: dict[str, float] = {
    "clean_rate": 1.0,
    "token_efficiency": 0.5,
    "cycle_time": 0.3,
    "rework_penalty": 0.5,
    # B.1 Primitive B Phase 0 additions (shaping §3.1 item 3):
    #
    # - ``model_tier_match``: +1.0 when lane tier matches the caller's
    #   ``required_model_tier`` strictly; +0.5 when the caller passed "any"
    #   and the lane is opus; 0 otherwise.
    # - ``effort_match``: +1.0 when the lane's per-archetype effort tier
    #   (from B.10 effort_policy) matches the packet's resolved effort hint.
    # - ``safety_envelope_penalty``: −2.0 when the caller requests a
    #   bypass-tier lane for a task whose tool-risk class is
    #   "reject-under-bypass". Hard-filter equivalent but surfaced as a
    #   penalty for audit clarity.
    "model_tier_match": 1.0,
    "effort_match": 1.0,
    "safety_envelope_penalty": 2.0,
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
#:
#: Version lineage:
#:
#: - ``slice-e-v1``: original four-component advisor (PR #2721 / #2169).
#: - ``b1-v1``: Primitive B Phase 0 — adds model-tier + safety-envelope
#:   pre-filter, three new score inputs, destructive-tool escalation, and
#:   the extended emission payload. Per shaping §3.1 item 4.
POLICY_VERSION: str = "b1-v1"

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
# B.1 Primitive B Phase 0 — envelope / model-tier pre-filter support
# ---------------------------------------------------------------------------
#
# Per shaping §3.2–§3.5 and ADR 006 §"Model tier interaction":
#
# - Opus lanes → ``safety_envelope = "auto-mode"`` (classifier-gated).
# - Sonnet / Haiku lanes → ``safety_envelope = "bypass"`` (no gate).
#
# The ``.claude/lane_models.json`` file (authored by #2767) declares each
# lane's model tier. This module derives safety_envelope and archetype from
# the tier; it does NOT re-read lane_models.json's schema richness (the
# file only carries ``model`` per #2767). Deriving here keeps the two
# concerns (launch-flag wiring vs. dispatch advisory) loosely coupled.
#
# Archetype derivation mirrors ``.claude/rules/effort_policy.md`` rows.

#: Repo-relative path to the canonical lane-models config.
_LANE_MODELS_RELPATH = Path(".claude/lane_models.json")

#: Permitted model tier literals. Must align with the shell + Python
#: loaders under ``.claude/tmux/steward-session.sh`` and
#: ``scripts/internal/lane_models.py``.
_VALID_MODEL_TIERS: frozenset[str] = frozenset({"opus", "sonnet", "haiku"})

#: Permitted safety-envelope literals. Exported for test cross-checks.
VALID_SAFETY_ENVELOPES: frozenset[str] = frozenset({"auto-mode", "bypass"})

#: Conservative default when ``.claude/lane_models.json`` is missing or the
#: lane has no row. Matches the 100%-Opus fleet baseline and the
#: shell+Python loaders' fallback. Emitted with a warning so operators
#: can triage the missing config.
_DEFAULT_LANE_RECORD: dict[str, str] = {
    "model": "opus",
    "safety_envelope": "auto-mode",
    "archetype": "unknown",
}


SafetyEnvelope = Literal["auto-mode", "bypass", "any"]
ModelTier = Literal["opus", "sonnet", "haiku", "any"]


def _default_lane_models_path() -> Path:
    """Return the canonical lane-models config path anchored at the repo root.

    Repo root is inferred from this file's location
    (``src/bid_euchre/ops/learning.py`` → three ``parent`` hops).
    """
    return Path(__file__).resolve().parent.parent.parent.parent / _LANE_MODELS_RELPATH


def _archetype_for_lane(lane_id: str) -> str:
    """Map a lane-id to its archetype per the §G13 8-archetype taxonomy.

    Mirrors the effort_policy.md table rows. Unknown lanes return
    ``"unknown"``; callers should treat this the same as a conservative
    default (no archetype-specific filtering).
    """
    if lane_id in ("orchestrator", "ops", "review"):
        return lane_id
    if lane_id.startswith("analyst-"):
        return "analyst"
    if lane_id.startswith("brws-author-"):
        return "brws-author"
    if lane_id.startswith("author-"):
        return "author"
    if lane_id.startswith("flex-"):
        return "flex"
    return "unknown"


def _safety_envelope_for_tier(model: str) -> str:
    """Per ADR 006 §Model-tier interaction: opus → auto-mode; else bypass."""
    return "auto-mode" if model == "opus" else "bypass"


def load_lane_models(
    config_path: Path | None = None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Load the lane → {model, safety_envelope, archetype} mapping.

    Returns a tuple ``(mapping, warnings)``.

    * ``mapping``: one entry per declared lane. Each entry is a dict with
      ``model``, ``safety_envelope``, and ``archetype`` keys. Safety envelope
      and archetype are derived from the declared model + lane-id per ADR
      006 and the §G13 archetype taxonomy.
    * ``warnings``: any parsing warnings surfaced during the read.

    Missing file / malformed JSON / missing ``lanes`` key all return an
    empty mapping with a warning so callers can fall back to the
    conservative default per shaping §3.3.
    """
    warnings: list[str] = []
    path = config_path if config_path is not None else _default_lane_models_path()
    if not path.exists():
        warnings.append(
            f"lane_models.json missing at {path}; using conservative fallback"
        )
        return {}, warnings

    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"lane_models.json unreadable at {path}: {exc}")
        return {}, warnings

    lanes = raw.get("lanes")
    if not isinstance(lanes, dict):
        warnings.append(f"lane_models.json at {path} missing or malformed 'lanes' key")
        return {}, warnings

    mapping: dict[str, dict[str, str]] = {}
    for lane_id, entry in lanes.items():
        if not isinstance(lane_id, str) or not lane_id:
            continue
        if not isinstance(entry, dict):
            warnings.append(
                f"lane_models.json: lane {lane_id!r} entry is not an object"
            )
            continue
        model = entry.get("model")
        if not isinstance(model, str) or model not in _VALID_MODEL_TIERS:
            warnings.append(
                f"lane_models.json: lane {lane_id!r} has invalid model {model!r}"
            )
            continue
        mapping[lane_id] = {
            "model": model,
            "safety_envelope": _safety_envelope_for_tier(model),
            "archetype": _archetype_for_lane(lane_id),
        }
    return mapping, warnings


def get_lane_record(
    lane_id: str,
    *,
    lane_models: dict[str, dict[str, str]] | None = None,
    config_path: Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return ``({model, safety_envelope, archetype}, warnings)`` for one lane.

    Falls back to ``_DEFAULT_LANE_RECORD`` with a warning when the lane is
    missing from the config (shaping §3.3 "conservative default"). The
    archetype in the fallback is derived from the lane_id even when the
    lane is absent from the config, so archetype-aware scoring still works.
    """
    warnings: list[str] = []
    if lane_models is None:
        lane_models, load_warnings = load_lane_models(config_path)
        warnings.extend(load_warnings)

    if lane_id in lane_models:
        return dict(lane_models[lane_id]), warnings

    warnings.append(
        f"lane {lane_id!r} missing from lane_models.json; using conservative default"
    )
    record = dict(_DEFAULT_LANE_RECORD)
    record["archetype"] = _archetype_for_lane(lane_id)
    return record, warnings


# ---------------------------------------------------------------------------
# Tool-risk registry read contract (shaping §3.5, §5.3)
# ---------------------------------------------------------------------------

#: Path to the tool-risk registry (authored by B.6 in Primitive B-exec.α).
_TOOL_RISK_REGISTRY_RELPATH = Path(".claude/rules/tool_risk_registry.md")

#: Approval classes the registry uses (shaping §5.2 / registry §"Approval
#: classes"). Listed here so downstream code can validate lookups.
_VALID_APPROVAL_CLASSES: frozenset[str] = frozenset(
    {"direct", "approve", "edit", "reject"}
)

_TOOL_RISK_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*([\w-]+(?:\s*\([^)]*\))?)\s*\|\s*([\w-]+(?:\s*\([^)]*\))?)\s*\|"
)


def _default_tool_risk_registry_path() -> Path:
    """Return the canonical tool-risk registry path anchored at the repo root."""
    return (
        Path(__file__).resolve().parent.parent.parent.parent
        / _TOOL_RISK_REGISTRY_RELPATH
    )


def _parse_approval_class(token: str) -> str | None:
    """Extract the approval class from a registry cell value.

    Cells may carry parenthetical detail like ``approve (classifier gates)``.
    The first word is the class; anything else is an explanatory annotation.
    Unknown classes return ``None`` (caller treats as "no classification").
    """
    token = token.strip()
    if not token:
        return None
    head = token.split()[0].strip()
    return head if head in _VALID_APPROVAL_CLASSES else None


def load_tool_risk_registry(
    registry_path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Load the tool-risk registry into ``tool → {auto_mode, bypass}`` classes.

    The registry is a markdown file with tables whose rows follow the shape::

        | `Tool(pattern)` | <auto-mode class> | <bypass class> | Notes |

    We parse any line matching that shape and keep the first token of each
    class cell (``direct`` / ``approve`` / ``edit`` / ``reject``). Rows
    outside the four-class vocabulary are skipped silently — the B.6
    ``check tool-risk`` lint owns schema enforcement; this module only
    needs the best-effort read contract described in shaping §5.3.

    Returns an empty dict when the registry is missing (degraded-but-
    functional fallback — shaping §10.4 "Dependency on Primitive C" notes
    that B.1 must not hard-require the registry at import time).
    """
    path = (
        registry_path
        if registry_path is not None
        else _default_tool_risk_registry_path()
    )
    mapping: dict[str, dict[str, str]] = {}
    if not path.exists():
        return mapping

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return mapping

    for line in text.splitlines():
        m = _TOOL_RISK_ROW_RE.match(line)
        if not m:
            continue
        tool, auto_raw, bypass_raw = m.group(1), m.group(2), m.group(3)
        auto_class = _parse_approval_class(auto_raw)
        bypass_class = _parse_approval_class(bypass_raw)
        if auto_class is None or bypass_class is None:
            continue
        mapping[tool] = {
            "auto_mode": auto_class,
            "bypass": bypass_class,
        }
    return mapping


def classify_tools(
    tools: list[str],
    *,
    registry: dict[str, dict[str, str]] | None = None,
    registry_path: Path | None = None,
) -> dict[str, dict[str, str | None]]:
    """Classify a list of tool patterns against the registry.

    Returns one entry per input tool with ``auto_mode`` and ``bypass``
    keys. Tools absent from the registry are recorded as ``None`` so the
    caller can surface them in the ``warnings`` payload.
    """
    if registry is None:
        registry = load_tool_risk_registry(registry_path)
    out: dict[str, dict[str, str | None]] = {}
    for tool in tools:
        row = registry.get(tool)
        if row is None:
            out[tool] = {"auto_mode": None, "bypass": None}
        else:
            out[tool] = {"auto_mode": row["auto_mode"], "bypass": row["bypass"]}
    return out


def derive_required_envelope(
    required_tools: list[str] | None,
    *,
    registry: dict[str, dict[str, str]] | None = None,
    registry_path: Path | None = None,
) -> tuple[str | None, str | None, list[str]]:
    """Determine whether the task's required-tools force an auto-mode envelope.

    Per shaping §3.5 (destructive-tool escalation): when any required tool
    carries ``approval_class_under_bypass == "reject"``, B.1 must coerce the
    safety-envelope requirement to ``"auto-mode"`` regardless of the
    caller's preference, and emit the override trace so the operator can
    audit the decision later.

    Returns ``(forced_envelope, override_reason, warnings)``:

    * ``forced_envelope``: ``"auto-mode"`` when escalation is triggered,
      ``None`` otherwise.
    * ``override_reason``: ``"tool-risk-rejected-under-bypass"`` when
      triggered; ``None`` otherwise.
    * ``warnings``: list of human-readable strings describing any tools
      that were missing from the registry (best-effort degraded path).
    """
    warnings: list[str] = []
    if not required_tools:
        return None, None, warnings
    classifications = classify_tools(
        required_tools, registry=registry, registry_path=registry_path
    )
    forced = False
    for tool, row in classifications.items():
        if row["bypass"] == "reject":
            forced = True
            break
        if row["bypass"] is None:
            warnings.append(f"tool {tool!r} absent from tool_risk_registry.md")
    if forced:
        return "auto-mode", "tool-risk-rejected-under-bypass", warnings
    return None, None, warnings


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


@dataclass(frozen=True)
class RecommendationResult:
    """Full result from :func:`recommend_lanes_envelope_aware`.

    Wraps the ranked :class:`LaneRecommendation` list with the B.1 envelope-
    awareness context (filtered lanes, forced-envelope trace, warnings).
    Callers that want just the ranked list can use :func:`recommend_lanes`,
    which returns the ranking unchanged for backward compatibility.
    """

    recommendations: tuple[LaneRecommendation, ...]
    filtered_lanes: tuple[dict[str, str], ...]
    required_safety_envelope: str
    required_model_tier: str
    effective_required_safety_envelope: str
    effective_required_model_tier: str
    safety_envelope_override: bool
    override_reason: str | None
    warnings: tuple[str, ...]


def _tier_match_score(lane_tier: str, required: str) -> tuple[float, str | None]:
    """Score the model-tier-match component for one candidate lane."""
    if required != "any":
        if lane_tier == required:
            return 1.0, "model-tier match"
        return 0.0, None
    # "any" preference: opus gets a partial bump (it is the fleet default +
    # runs auto-mode envelope so it is strictly safer than the alternatives).
    if lane_tier == "opus":
        return 0.5, "opus preferred on any-tier request"
    return 0.0, None


def _effort_match_score(
    archetype: str,
    task_type: str | None,
    resolved_effort_hint: str | None,
) -> tuple[float, str | None]:
    """Score the effort-match component against the B.10 policy table."""
    if resolved_effort_hint is None or task_type is None:
        return 0.0, None
    try:
        from bid_euchre.ops.effort_policy import effort_for
    except Exception:  # pragma: no cover — defensive
        return 0.0, None
    try:
        policy_default = effort_for(archetype, task_type)
    except ValueError:
        # `n/a` pairing or unknown archetype/task-type — no effort-match
        # signal available.
        return 0.0, None
    if policy_default == resolved_effort_hint:
        return 1.0, "effort-policy match"
    return 0.0, None


def _safety_envelope_penalty(
    lane_envelope: str,
    required_envelope: str,
    required_tools: list[str] | None,
    tool_risk_registry: dict[str, dict[str, str]] | None,
) -> tuple[float, str | None]:
    """Compute the −2.0 penalty for bypass-tier lanes on reject-under-bypass tasks.

    Separate from the hard pre-filter in :func:`recommend_lanes_envelope_aware`:
    the pre-filter drops obviously-unsafe lanes; this penalty is a score-space
    audit signal for the observability trail.
    """
    if lane_envelope != "bypass" or required_envelope == "bypass":
        return 0.0, None
    if not required_tools:
        return 0.0, None
    registry = (
        tool_risk_registry
        if tool_risk_registry is not None
        else load_tool_risk_registry()
    )
    for tool in required_tools:
        row = registry.get(tool)
        if row and row.get("bypass") == "reject":
            return 1.0, f"{tool} rejected under bypass envelope"
    return 0.0, None


def recommend_lanes(
    candidates: list[str],
    *,
    task_type: str | None = None,
    complexity: int | None = None,
    window_days: int = WINDOW_DAYS_DEFAULT,
    events_dir: Path | None = None,
    output_dir: Path | None = None,
    required_safety_envelope: SafetyEnvelope = "any",
    required_model_tier: ModelTier = "any",
    required_tools: list[str] | None = None,
    resolved_effort_hint: str | None = None,
    lane_models: dict[str, dict[str, str]] | None = None,
    tool_risk_registry: dict[str, dict[str, str]] | None = None,
    lane_models_path: Path | None = None,
    tool_risk_path: Path | None = None,
    _records: list[Any] | None = None,
) -> list[LaneRecommendation]:
    """Rank candidate lanes by learned score, best first.

    Backward-compatible convenience wrapper around
    :func:`recommend_lanes_envelope_aware`. Returns only the ranked list of
    recommendations; the envelope-awareness context (filtered lanes,
    forced-envelope trace, warnings) is available on the fuller
    :class:`RecommendationResult` returned by the envelope-aware function.

    The new B.1 kwargs default to ``"any"`` so pre-B.1 callers see
    unchanged behavior.
    """
    result = recommend_lanes_envelope_aware(
        candidates,
        task_type=task_type,
        complexity=complexity,
        window_days=window_days,
        events_dir=events_dir,
        output_dir=output_dir,
        required_safety_envelope=required_safety_envelope,
        required_model_tier=required_model_tier,
        required_tools=required_tools,
        resolved_effort_hint=resolved_effort_hint,
        lane_models=lane_models,
        tool_risk_registry=tool_risk_registry,
        lane_models_path=lane_models_path,
        tool_risk_path=tool_risk_path,
        _records=_records,
    )
    return list(result.recommendations)


def recommend_lanes_envelope_aware(
    candidates: list[str],
    *,
    task_type: str | None = None,
    complexity: int | None = None,
    window_days: int = WINDOW_DAYS_DEFAULT,
    events_dir: Path | None = None,
    output_dir: Path | None = None,
    required_safety_envelope: SafetyEnvelope = "any",
    required_model_tier: ModelTier = "any",
    required_tools: list[str] | None = None,
    resolved_effort_hint: str | None = None,
    lane_models: dict[str, dict[str, str]] | None = None,
    tool_risk_registry: dict[str, dict[str, str]] | None = None,
    lane_models_path: Path | None = None,
    tool_risk_path: Path | None = None,
    _records: list[Any] | None = None,
) -> RecommendationResult:
    """Rank candidate lanes with B.1 envelope + model-tier awareness.

    This is the Primitive B Phase 0 extension of :func:`recommend_lanes`.
    Pure (no file writes, no event emission) but may read
    ``.claude/lane_models.json`` and ``.claude/rules/tool_risk_registry.md``
    for envelope / tier resolution. Filtered lanes are retained in the
    result payload so the caller can emit them through
    :func:`log_recommendation_for_dispatch` per Pattern 8.

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
    required_safety_envelope
        ``"auto-mode"`` | ``"bypass"`` | ``"any"``. Per shaping §3.2:
        when the caller requests ``"auto-mode"``, B.1 filters out any
        lane whose declared envelope is ``"bypass"``.  When the caller
        requests ``"bypass"`` for a task whose tool-risk class is
        ``reject-under-bypass``, B.1 coerces the requirement back to
        ``"auto-mode"`` and records the override.
    required_model_tier
        ``"opus"`` | ``"sonnet"`` | ``"haiku"`` | ``"any"``. Per §3.2:
        explicit tier requests hard-filter mismatched lanes.
    required_tools
        Optional list of tool patterns (as used in ``permissions.allow``)
        the task will invoke.  When any tool is ``reject-under-bypass``,
        the required envelope escalates to ``"auto-mode"`` per §3.5.
    resolved_effort_hint
        Optional effort tier the orchestrator already resolved for this
        packet.  Fed into the ``effort_match`` score component (B.10
        integration, §3.1 item 3).
    lane_models, tool_risk_registry
        Test-only overrides. When provided, the config/registry reads are
        skipped. Not part of the public contract.
    lane_models_path, tool_risk_path
        Test-only path overrides.
    _records
        Test-only pre-joined outcome records. Not part of the public
        contract.
    """
    warnings: list[str] = []

    # Resolve lane-models config (warnings propagate to the payload for
    # operator visibility per shaping §3.3 "conservative default").
    if lane_models is None:
        lane_models, load_warnings = load_lane_models(lane_models_path)
        warnings.extend(load_warnings)

    # Determine the *effective* required envelope after tool-risk escalation
    # (shaping §3.5). The caller's preference may be overridden here.
    effective_required_envelope = required_safety_envelope
    safety_envelope_override = False
    override_reason: str | None = None

    forced_envelope, forced_reason, tool_warnings = derive_required_envelope(
        required_tools,
        registry=tool_risk_registry,
        registry_path=tool_risk_path,
    )
    warnings.extend(tool_warnings)
    if forced_envelope is not None and required_safety_envelope != forced_envelope:
        effective_required_envelope = forced_envelope
        safety_envelope_override = True
        override_reason = forced_reason

    if not candidates:
        return RecommendationResult(
            recommendations=(),
            filtered_lanes=(),
            required_safety_envelope=required_safety_envelope,
            required_model_tier=required_model_tier,
            effective_required_safety_envelope=effective_required_envelope,
            effective_required_model_tier=required_model_tier,
            safety_envelope_override=safety_envelope_override,
            override_reason=override_reason,
            warnings=tuple(warnings),
        )

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

    # ---- B.1 pre-filter: drop lanes that fail envelope / tier requirements.
    # Shaping §3.1 item 2. Filtered lanes retained in the emission payload
    # as ``filtered_lanes: list[{lane, reason}]`` for observability.
    eligible_candidates: list[str] = []
    filtered_lanes: list[dict[str, str]] = []
    lane_records: dict[str, dict[str, str]] = {}

    for lane in candidates:
        record, record_warnings = get_lane_record(lane, lane_models=lane_models)
        warnings.extend(record_warnings)
        lane_records[lane] = record

        if required_model_tier != "any" and record["model"] != required_model_tier:
            filtered_lanes.append(
                {
                    "lane": lane,
                    "reason": "tier-mismatch",
                    "detail": f"required={required_model_tier} declared={record['model']}",
                }
            )
            continue

        if (
            effective_required_envelope != "any"
            and record["safety_envelope"] != effective_required_envelope
        ):
            # The envelope filter name depends on whether we filtered because
            # of an explicit caller preference or a tool-risk escalation.
            reason = "risk-reject" if safety_envelope_override else "envelope-mismatch"
            filtered_lanes.append(
                {
                    "lane": lane,
                    "reason": reason,
                    "detail": (
                        f"required={effective_required_envelope} "
                        f"declared={record['safety_envelope']}"
                    ),
                }
            )
            continue

        eligible_candidates.append(lane)

    features = [
        build_lane_features(
            lane,
            task_type=task_type,
            complexity=complexity,
            window_days=window_days,
            _records=_records,
        )
        for lane in eligible_candidates
    ]

    # Normalization denominators are the per-set maxima of the positive
    # signals. Guard against a set where every lane is at 0.
    max_tokens = max((f.avg_tokens_per_packet for f in features), default=0.0)
    max_elapsed = max((f.avg_elapsed_seconds for f in features), default=0.0)

    recs: list[LaneRecommendation] = []
    for feat in features:
        base_score, base_reasons = _score_one(
            feat, max_tokens=max_tokens, max_elapsed=max_elapsed
        )

        # B.1 score extensions — model-tier match, effort match, and
        # safety-envelope penalty (shaping §3.1 item 3).
        record = lane_records.get(feat.lane_id, dict(_DEFAULT_LANE_RECORD))
        extra_reasons: list[str] = []

        tier_contrib, tier_reason = _tier_match_score(
            record["model"], required_model_tier
        )
        tier_component = tier_contrib * SCORE_WEIGHTS["model_tier_match"]
        if tier_reason:
            extra_reasons.append(tier_reason)

        effort_contrib, effort_reason = _effort_match_score(
            record["archetype"], task_type, resolved_effort_hint
        )
        effort_component = effort_contrib * SCORE_WEIGHTS["effort_match"]
        if effort_reason:
            extra_reasons.append(effort_reason)

        penalty_contrib, penalty_reason = _safety_envelope_penalty(
            record["safety_envelope"],
            effective_required_envelope,
            required_tools,
            tool_risk_registry,
        )
        penalty_component = penalty_contrib * SCORE_WEIGHTS["safety_envelope_penalty"]
        if penalty_reason:
            extra_reasons.append(f"safety penalty: {penalty_reason}")

        total_score = base_score + tier_component + effort_component - penalty_component
        reasons = tuple(list(base_reasons) + extra_reasons)

        recs.append(
            LaneRecommendation(
                lane_id=feat.lane_id,
                score=total_score,
                reasons=reasons,
                features=feat,
            )
        )

    # Deterministic ordering: score desc, then lane_id asc for tie-break.
    recs.sort(key=lambda r: (-r.score, r.lane_id))

    return RecommendationResult(
        recommendations=tuple(recs),
        filtered_lanes=tuple(filtered_lanes),
        required_safety_envelope=required_safety_envelope,
        required_model_tier=required_model_tier,
        effective_required_safety_envelope=effective_required_envelope,
        effective_required_model_tier=required_model_tier,
        safety_envelope_override=safety_envelope_override,
        override_reason=override_reason,
        warnings=tuple(warnings),
    )


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
    required_safety_envelope: SafetyEnvelope = "any",
    required_model_tier: ModelTier = "any",
    required_tools: list[str] | None = None,
    resolved_effort_hint: str | None = None,
    lane_models_path: Path | None = None,
    tool_risk_path: Path | None = None,
) -> dict[str, Any] | None:
    """Emit one ``dispatch_recommendation`` event for this dispatch.

    This is the **only** side-effect function in the module. It:

    1. Computes a ranked recommendation over ``candidates`` (via
       :func:`recommend_lanes_envelope_aware`).
    2. Appends exactly one ``dispatch_recommendation`` event to the durable
       event log.
    3. Returns the event dict (or ``None`` when
       :data:`ADVISOR_MODE` is ``"disabled"``).

    The returned dict is informational — callers MUST NOT use it to change
    which lane gets dispatched. The shadow-mode invariant is enforced by
    the caller: ``dispatch_to_worker`` invokes this function and then
    continues with the caller-supplied ``lane_id`` unchanged.

    B.1 payload additions (shaping §3.2):

    * ``required_safety_envelope``, ``required_model_tier`` — caller
      preferences echoed into the payload.
    * ``effective_required_safety_envelope`` — caller preference after
      tool-risk escalation (§3.5). Equal to
      ``required_safety_envelope`` unless a destructive tool forced the
      envelope up.
    * ``filtered_lanes`` — lanes dropped before scoring (tier-mismatch,
      envelope-mismatch, or risk-reject) per §3.1 item 2.
    * ``safety_envelope_override`` / ``override_reason`` — audit trail for
      the §3.5 escalation.
    * ``warnings`` — best-effort notices (missing lane_models.json entries,
      tools absent from tool-risk registry, etc.).

    Parameters
    ----------
    packet
        The :class:`~bid_euchre.ops.task_queue.TaskPacket` being dispatched
        (read-only access to ``metadata`` for task_type / complexity /
        effort hint / required tools).
    candidates
        Eligible lane IDs the advisor could have ranked. May or may not
        include ``selected_lane``.
    selected_lane
        The lane the dispatcher actually chose. Recorded verbatim.
    events_dir, output_dir
        Substrate / event-log overrides.
    source
        Producer tag for the event. Defaults to ``ops.learning``.
    required_safety_envelope, required_model_tier, required_tools
        B.1 envelope-awareness kwargs (shaping §3.2 / §3.5).
    resolved_effort_hint
        B.10 effort tier resolved for this packet. When ``None`` and the
        packet carries ``effort_hint`` metadata, the packet value is used
        (B.10 integration, §7.2).
    lane_models_path, tool_risk_path
        Test-only overrides for the config/registry paths.

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
    task_type: str | None = None
    complexity: int | None = None
    packet_effort_hint: str | None = None
    try:
        from bid_euchre.ops.task_queue import get_complexity, get_task_type

        task_type = get_task_type(packet)
        complexity = get_complexity(packet)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Failed to extract packet routing metadata: %s", exc)

    # Effort hint can come from packet metadata or from the caller. Caller
    # takes precedence when supplied (orchestrator may have already applied
    # B.10 resolution); packet metadata acts as a fallback.
    try:
        metadata = getattr(packet, "metadata", {}) or {}
        packet_effort_hint = metadata.get("effort_hint")
    except Exception:  # pragma: no cover — defensive
        packet_effort_hint = None
    effective_effort_hint = resolved_effort_hint or packet_effort_hint

    # Required tools: caller-supplied overrides any packet-embedded list.
    effective_required_tools = required_tools
    if effective_required_tools is None:
        try:
            metadata = getattr(packet, "metadata", {}) or {}
            maybe_tools = metadata.get("required_tools")
            if isinstance(maybe_tools, list):
                effective_required_tools = [str(t) for t in maybe_tools]
        except Exception:  # pragma: no cover — defensive
            effective_required_tools = None

    result = recommend_lanes_envelope_aware(
        list(candidates),
        task_type=task_type,
        complexity=complexity,
        events_dir=events_dir,
        output_dir=output_dir,
        required_safety_envelope=required_safety_envelope,
        required_model_tier=required_model_tier,
        required_tools=effective_required_tools,
        resolved_effort_hint=effective_effort_hint,
        lane_models_path=lane_models_path,
        tool_risk_path=tool_risk_path,
    )
    recs = result.recommendations

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
        "override_reason": result.override_reason,
        "policy_version": POLICY_VERSION,
        "window_days": WINDOW_DAYS_DEFAULT,
        "advisor_mode": ADVISOR_MODE,
        # B.1 additions (shaping §3.2):
        "required_safety_envelope": result.required_safety_envelope,
        "required_model_tier": result.required_model_tier,
        "effective_required_safety_envelope": result.effective_required_safety_envelope,
        "filtered_lanes": [dict(entry) for entry in result.filtered_lanes],
        "safety_envelope_override": result.safety_envelope_override,
        "warnings": list(result.warnings),
        "resolved_effort_hint": effective_effort_hint,
        "required_tools": list(effective_required_tools or []),
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
