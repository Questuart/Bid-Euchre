"""B.1 model-tier + safety-envelope awareness tests for the dispatch advisor.

Covers the Primitive B Phase 0 extensions to
:mod:`bid_euchre.ops.learning` per
``plans/steward_platform/2_primitive_B/shaping.md`` §3 and §10.2 step 6:

1. Model-tier pre-filter — an explicit ``required_model_tier`` drops
   lanes whose declared tier does not match.
2. Safety-envelope pre-filter — an explicit
   ``required_safety_envelope="auto-mode"`` drops bypass-envelope lanes.
3. Destructive-tool escalation — when ``required_tools`` contains a
   pattern whose tool-risk class is ``reject`` under bypass, B.1 forces
   the required envelope to ``auto-mode`` regardless of the caller's
   stated preference and records the override trace.
4. Fallback when ``.claude/lane_models.json`` is missing — a warning is
   emitted and lanes fall back to the conservative default (opus /
   auto-mode) so no crash occurs at dispatch time.
5. POLICY_VERSION ``"b1-v1"`` trace in emissions — the emitted
   ``dispatch_recommendation`` payload carries the current policy
   version verbatim.
6. ``lane_models.json`` coverage warning — when a candidate lane is
   absent from the config, the payload ``warnings`` field flags it.

Plus structural coverage of the B.1 score components
(``model_tier_match``, ``effort_match``, ``safety_envelope_penalty``)
and backward-compatibility of the :func:`recommend_lanes` wrapper.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from bid_euchre.ops.learning import (
    POLICY_VERSION,
    SCORE_WEIGHTS,
    VALID_SAFETY_ENVELOPES,
    LaneRecommendation,
    RecommendationResult,
    classify_tools,
    derive_required_envelope,
    get_lane_record,
    load_lane_models,
    load_tool_risk_registry,
    log_recommendation_for_dispatch,
    recommend_lanes,
    recommend_lanes_envelope_aware,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic lane_models.json and tool_risk_registry.md
# ---------------------------------------------------------------------------


def _write_lane_models(
    tmp_path: Path,
    lanes: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Write a synthetic lane_models.json and return its path.

    Schema matches the canonical file per #2767: ``{"lanes": {<id>: {"model": ...}}}``.
    Unknown lanes (by lane_id shape) pass through untouched; archetype
    derivation is internal to learning.py.
    """
    default_lanes = {
        "author-a": {"model": "opus"},
        "author-b": {"model": "sonnet"},
        "author-c": {"model": "opus"},
        "flex-a": {"model": "opus"},
        "ops": {"model": "haiku"},
    }
    payload = {
        "_schema_version": 1,
        "lanes": lanes if lanes is not None else default_lanes,
    }
    path = tmp_path / "lane_models.json"
    path.write_text(json.dumps(payload))
    return path


def _write_tool_risk_registry(tmp_path: Path) -> Path:
    """Write a minimal tool-risk registry with one reject-under-bypass row.

    The parser in ``learning.py`` reads any line matching
    ``| \\`<tool>\\` | <auto> | <bypass> | Notes |``. We author a table
    with enough rows to exercise:

    * A direct/direct tool (safe, no escalation).
    * An approve/approve tool (mild escalation, no forcing).
    * An approve/reject tool (destructive → force auto-mode envelope).
    * A reject/reject tool (hard-deny on both envelopes; B.1 does not use
      this specifically beyond filtering, but verifies the parser reads it).
    """
    body = (
        "# Tool Risk Registry (test fixture)\n\n"
        "| Tool | Auto | Bypass | Notes |\n"
        "|---|---|---|---|\n"
        "| `Bash(git *)` | direct | direct | Baseline safe |\n"
        "| `Bash(gh pr merge)` | approve (merge guard) | reject | Destructive under bypass |\n"
        "| `Bash(rm -rf *)` | approve | reject | Destructive under bypass |\n"
        "| `Bash(sudo *)` | reject | reject | Never sanctioned |\n"
    )
    path = tmp_path / "tool_risk_registry.md"
    path.write_text(body)
    return path


# ---------------------------------------------------------------------------
# Synthetic outcome record factory (mirrors test_ops_learning.py)
# ---------------------------------------------------------------------------


def _outcome(
    *,
    actual_lane: str,
    task_type: str | None = None,
    complexity: int | None = None,
    token_spend: int | None = 100_000,
    elapsed_seconds: float | None = 1800.0,
    review_rounds: int | None = 1,
    shipped_outcome: str | None = "merged",
    lane_total_tokens: int | None = None,
    packet_id: str = "pkt-test",
    completed_at: str = "2026-04-20T12:00:00+00:00",
) -> SimpleNamespace:
    return SimpleNamespace(
        packet_id=packet_id,
        title="",
        pr_number=None,
        completed_at=completed_at,
        actual_lane=actual_lane,
        recommended_lane=None,
        recommendation_match=None,
        task_type=task_type,
        complexity_estimate=complexity,
        model_hint=None,
        effort_hint=None,
        token_spend=token_spend,
        elapsed_seconds=elapsed_seconds,
        review_rounds=review_rounds,
        shipped_outcome=shipped_outcome,
        lane_total_tokens=lane_total_tokens,
    )


def _packet(
    *,
    packet_id: str = "pkt-ma",
    task_type: str | None = "implementation",
    complexity: int | None = 2,
    effort_hint: str | None = None,
    required_tools: list[str] | None = None,
) -> SimpleNamespace:
    metadata: dict[str, object] = {}
    if task_type is not None:
        metadata["task_type"] = task_type
    if complexity is not None:
        metadata["complexity_estimate"] = complexity
    if effort_hint is not None:
        metadata["effort_hint"] = effort_hint
    if required_tools is not None:
        metadata["required_tools"] = required_tools
    return SimpleNamespace(packet_id=packet_id, metadata=metadata)


# ---------------------------------------------------------------------------
# lane_models.json loader + get_lane_record
# ---------------------------------------------------------------------------


class TestLoadLaneModels:
    def test_reads_declared_lanes_with_derived_fields(self, tmp_path: Path) -> None:
        path = _write_lane_models(tmp_path)
        mapping, warnings = load_lane_models(path)

        assert warnings == []
        # author-a → opus → auto-mode, archetype author.
        assert mapping["author-a"] == {
            "model": "opus",
            "safety_envelope": "auto-mode",
            "archetype": "author",
        }
        # author-b → sonnet → bypass envelope.
        assert mapping["author-b"]["safety_envelope"] == "bypass"
        assert mapping["author-b"]["model"] == "sonnet"
        # ops → haiku → bypass. Archetype is "ops" (explicit lane-id).
        assert mapping["ops"]["archetype"] == "ops"
        assert mapping["ops"]["safety_envelope"] == "bypass"

    def test_missing_file_returns_empty_mapping_with_warning(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist.json"
        mapping, warnings = load_lane_models(missing)
        assert mapping == {}
        assert any("missing" in w for w in warnings)

    def test_malformed_json_returns_empty_mapping_with_warning(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "lane_models.json"
        path.write_text("{ not: valid json")
        mapping, warnings = load_lane_models(path)
        assert mapping == {}
        assert any("unreadable" in w for w in warnings)

    def test_invalid_model_tier_is_skipped_with_warning(self, tmp_path: Path) -> None:
        path = _write_lane_models(
            tmp_path,
            {
                "author-a": {"model": "opus"},
                "author-b": {"model": "gpt-7"},  # invalid
            },
        )
        mapping, warnings = load_lane_models(path)
        assert "author-a" in mapping
        assert "author-b" not in mapping
        assert any("invalid model" in w for w in warnings)

    def test_non_dict_entry_skipped_with_warning(self, tmp_path: Path) -> None:
        path = tmp_path / "lane_models.json"
        path.write_text(json.dumps({"lanes": {"author-a": "opus"}}))
        mapping, warnings = load_lane_models(path)
        assert mapping == {}
        assert any("not an object" in w for w in warnings)


class TestGetLaneRecord:
    def test_declared_lane_returns_record(self, tmp_path: Path) -> None:
        path = _write_lane_models(tmp_path)
        record, warnings = get_lane_record("author-a", config_path=path)
        assert record["model"] == "opus"
        assert record["safety_envelope"] == "auto-mode"
        assert warnings == []

    def test_missing_lane_falls_back_to_conservative_default_with_warning(
        self, tmp_path: Path
    ) -> None:
        path = _write_lane_models(tmp_path, {})  # empty lanes table
        record, warnings = get_lane_record("author-a", config_path=path)
        # Conservative default: opus / auto-mode, but archetype derived from lane_id.
        assert record["model"] == "opus"
        assert record["safety_envelope"] == "auto-mode"
        assert record["archetype"] == "author"
        assert any("missing from lane_models.json" in w for w in warnings)

    def test_unknown_lane_archetype_is_unknown(self, tmp_path: Path) -> None:
        path = _write_lane_models(tmp_path, {})
        record, _ = get_lane_record("some-weird-lane", config_path=path)
        assert record["archetype"] == "unknown"


# ---------------------------------------------------------------------------
# Tool-risk registry + destructive-tool escalation
# ---------------------------------------------------------------------------


class TestToolRiskRegistry:
    def test_parses_four_class_rows(self, tmp_path: Path) -> None:
        path = _write_tool_risk_registry(tmp_path)
        reg = load_tool_risk_registry(path)
        assert reg["Bash(git *)"] == {"auto_mode": "direct", "bypass": "direct"}
        assert reg["Bash(gh pr merge)"] == {"auto_mode": "approve", "bypass": "reject"}
        assert reg["Bash(rm -rf *)"]["bypass"] == "reject"
        assert reg["Bash(sudo *)"]["auto_mode"] == "reject"

    def test_missing_registry_returns_empty_dict(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.md"
        assert load_tool_risk_registry(missing) == {}

    def test_classify_tools_returns_none_for_unknown(self, tmp_path: Path) -> None:
        reg = load_tool_risk_registry(_write_tool_risk_registry(tmp_path))
        out = classify_tools(["Bash(git *)", "Bash(unknown-tool)"], registry=reg)
        assert out["Bash(git *)"]["bypass"] == "direct"
        assert out["Bash(unknown-tool)"] == {"auto_mode": None, "bypass": None}


class TestDeriveRequiredEnvelope:
    def test_no_tools_returns_no_escalation(self, tmp_path: Path) -> None:
        reg = load_tool_risk_registry(_write_tool_risk_registry(tmp_path))
        forced, reason, warnings = derive_required_envelope(None, registry=reg)
        assert forced is None
        assert reason is None
        assert warnings == []

    def test_safe_tools_return_no_escalation(self, tmp_path: Path) -> None:
        reg = load_tool_risk_registry(_write_tool_risk_registry(tmp_path))
        forced, reason, _ = derive_required_envelope(["Bash(git *)"], registry=reg)
        assert forced is None
        assert reason is None

    def test_reject_under_bypass_forces_auto_mode(self, tmp_path: Path) -> None:
        reg = load_tool_risk_registry(_write_tool_risk_registry(tmp_path))
        forced, reason, _ = derive_required_envelope(
            ["Bash(git *)", "Bash(rm -rf *)"], registry=reg
        )
        assert forced == "auto-mode"
        assert reason == "tool-risk-rejected-under-bypass"

    def test_unknown_tool_emits_warning(self, tmp_path: Path) -> None:
        reg = load_tool_risk_registry(_write_tool_risk_registry(tmp_path))
        forced, _, warnings = derive_required_envelope(
            ["Bash(unknown-tool)"], registry=reg
        )
        assert forced is None
        assert any("absent from tool_risk_registry.md" in w for w in warnings)


# ---------------------------------------------------------------------------
# Score / weight invariants
# ---------------------------------------------------------------------------


class TestB1ScoreWeights:
    def test_new_components_present(self) -> None:
        for key in ("model_tier_match", "effort_match", "safety_envelope_penalty"):
            assert key in SCORE_WEIGHTS, f"missing B.1 weight {key}"

    def test_policy_version_is_b1(self) -> None:
        assert POLICY_VERSION == "b1-v1"

    def test_valid_safety_envelopes_are_two_values(self) -> None:
        assert VALID_SAFETY_ENVELOPES == frozenset({"auto-mode", "bypass"})


# ---------------------------------------------------------------------------
# Pre-filter: model-tier mismatch
# ---------------------------------------------------------------------------


class TestModelTierPreFilter:
    def test_explicit_opus_drops_sonnet_lane(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_model_tier="opus",
            lane_models_path=lane_models_path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert "author-a" in ranked_ids  # opus
        assert "author-b" not in ranked_ids  # sonnet → filtered
        filtered_ids = [f["lane"] for f in result.filtered_lanes]
        assert "author-b" in filtered_ids
        (filtered_b,) = [f for f in result.filtered_lanes if f["lane"] == "author-b"]
        assert filtered_b["reason"] == "tier-mismatch"

    def test_any_tier_does_not_drop_anything(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_model_tier="any",
            lane_models_path=lane_models_path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert set(ranked_ids) == {"author-a", "author-b"}
        assert result.filtered_lanes == ()

    def test_explicit_sonnet_drops_opus_lane(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_model_tier="sonnet",
            lane_models_path=lane_models_path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert ranked_ids == ["author-b"]
        assert any(
            f["lane"] == "author-a" and f["reason"] == "tier-mismatch"
            for f in result.filtered_lanes
        )


# ---------------------------------------------------------------------------
# Pre-filter: safety-envelope mismatch
# ---------------------------------------------------------------------------


class TestSafetyEnvelopePreFilter:
    def test_required_auto_mode_drops_bypass_lanes(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b", "ops"],
            required_safety_envelope="auto-mode",
            lane_models_path=lane_models_path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        # author-a (opus) and author-c not in candidates; ops (haiku→bypass)
        # and author-b (sonnet→bypass) must be filtered.
        assert ranked_ids == ["author-a"]
        filtered_ids = {f["lane"] for f in result.filtered_lanes}
        assert filtered_ids == {"author-b", "ops"}
        for entry in result.filtered_lanes:
            # When the caller pre-declared auto-mode, reason is
            # ``envelope-mismatch`` (not ``risk-reject``).
            assert entry["reason"] == "envelope-mismatch"

    def test_required_bypass_drops_auto_mode_lanes(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_safety_envelope="bypass",
            lane_models_path=lane_models_path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert ranked_ids == ["author-b"]  # only sonnet (bypass) survives
        (filtered_a,) = [f for f in result.filtered_lanes if f["lane"] == "author-a"]
        assert filtered_a["reason"] == "envelope-mismatch"


# ---------------------------------------------------------------------------
# Destructive-tool escalation (shaping §3.5)
# ---------------------------------------------------------------------------


class TestDestructiveToolEscalation:
    def test_bypass_request_with_reject_tool_forces_auto_mode(
        self, tmp_path: Path
    ) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_safety_envelope="bypass",
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        # Effective envelope escalated from "bypass" to "auto-mode".
        assert result.required_safety_envelope == "bypass"
        assert result.effective_required_safety_envelope == "auto-mode"
        assert result.safety_envelope_override is True
        assert result.override_reason == "tool-risk-rejected-under-bypass"

        # Filter reason for dropped lanes is "risk-reject" (not "envelope-mismatch").
        filtered_b = [f for f in result.filtered_lanes if f["lane"] == "author-b"]
        assert filtered_b
        assert filtered_b[0]["reason"] == "risk-reject"

        # Only the opus lane survives.
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert ranked_ids == ["author-a"]

    def test_safe_tools_do_not_escalate(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_safety_envelope="bypass",
            required_tools=["Bash(git *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        # No escalation; bypass-tier lanes remain eligible.
        assert result.safety_envelope_override is False
        assert result.effective_required_safety_envelope == "bypass"
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert ranked_ids == ["author-b"]

    def test_any_envelope_plus_reject_tool_still_forces_auto_mode(
        self, tmp_path: Path
    ) -> None:
        """When caller is permissive ("any"), a reject-under-bypass tool
        still promotes to auto-mode because the override logic compares
        the caller's envelope against the forced envelope."""
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_safety_envelope="any",
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        assert result.safety_envelope_override is True
        assert result.effective_required_safety_envelope == "auto-mode"
        # author-b (sonnet → bypass) filtered out by forced envelope.
        filtered_ids = [f["lane"] for f in result.filtered_lanes]
        assert "author-b" in filtered_ids

    def test_auto_mode_plus_reject_tool_is_not_an_override(
        self, tmp_path: Path
    ) -> None:
        """If the caller already asked for auto-mode, no override trace is
        recorded (effective == required)."""
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_safety_envelope="auto-mode",
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        assert result.effective_required_safety_envelope == "auto-mode"
        assert result.safety_envelope_override is False
        assert result.override_reason is None


# ---------------------------------------------------------------------------
# Fallback — missing lane_models.json
# ---------------------------------------------------------------------------


class TestMissingConfigFallback:
    def test_no_lane_models_file_defaults_to_opus_auto_mode(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "lane_models-missing.json"
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            required_model_tier="opus",
            lane_models_path=missing,
            _records=[],
        )
        # All lanes default to opus → no tier-filtering happens, both survive.
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert set(ranked_ids) == {"author-a", "author-b"}
        # Warnings include the missing-file notice AND a per-lane
        # "missing from lane_models.json" notice for each candidate.
        assert any("missing at" in w for w in result.warnings)
        assert sum("missing from lane_models.json" in w for w in result.warnings) >= 2

    def test_missing_lane_in_config_warns_but_does_not_crash(
        self, tmp_path: Path
    ) -> None:
        path = _write_lane_models(tmp_path, {"author-a": {"model": "opus"}})
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-z"],  # author-z is absent from config
            lane_models_path=path,
            _records=[],
        )
        ranked_ids = [r.lane_id for r in result.recommendations]
        assert "author-a" in ranked_ids
        # author-z falls back to opus / auto-mode and is still ranked.
        assert "author-z" in ranked_ids
        assert any(
            "'author-z' missing from lane_models.json" in w for w in result.warnings
        )


# ---------------------------------------------------------------------------
# Score components: model_tier_match / effort_match / envelope_penalty
# ---------------------------------------------------------------------------


class TestModelTierMatchScore:
    def test_explicit_tier_match_adds_positive_contribution(
        self, tmp_path: Path
    ) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        # No outcome history → base score is 0 for both lanes.
        # author-a is opus → +1.0 * weight for explicit "opus" request.
        # author-c is opus → same boost.
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-c"],
            required_model_tier="opus",
            lane_models_path=lane_models_path,
            _records=[],
        )
        for rec in result.recommendations:
            assert rec.score >= SCORE_WEIGHTS["model_tier_match"]

    def test_any_tier_gives_opus_a_half_bump(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],  # opus vs sonnet
            required_model_tier="any",
            lane_models_path=lane_models_path,
            _records=[],
        )
        recs_by_lane = {r.lane_id: r for r in result.recommendations}
        opus_score = recs_by_lane["author-a"].score
        sonnet_score = recs_by_lane["author-b"].score
        # Opus gets +0.5 (half bump * weight 1.0 = 0.5); sonnet gets 0.
        assert opus_score > sonnet_score
        assert abs(opus_score - sonnet_score - 0.5) < 1e-9


class TestEffortMatchScore:
    def test_matching_effort_hint_adds_to_score(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        # flex + implementation → policy default xhigh (from effort_policy.md).
        result = recommend_lanes_envelope_aware(
            ["flex-a"],
            task_type="implementation",
            resolved_effort_hint="xhigh",
            lane_models_path=lane_models_path,
            _records=[],
        )
        (rec,) = result.recommendations
        # Should see the effort-policy reason in the reasons list.
        assert any("effort-policy match" in r for r in rec.reasons)

    def test_non_matching_effort_hint_yields_no_bonus(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["flex-a"],
            task_type="implementation",
            resolved_effort_hint="lower",  # policy default is xhigh
            lane_models_path=lane_models_path,
            _records=[],
        )
        (rec,) = result.recommendations
        assert not any("effort-policy match" in r for r in rec.reasons)


class TestSafetyEnvelopePenalty:
    def test_penalty_only_applies_when_lane_envelope_and_risk_mismatch(
        self, tmp_path: Path
    ) -> None:
        """A bypass-tier lane does not accrue the safety-envelope-penalty
        reason when the caller requested auto-mode — it's filtered out
        before scoring. This test confirms the filter precedence by
        asserting no "safety penalty" reason leaks into a ranked lane."""
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a"],
            required_safety_envelope="auto-mode",
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        (rec,) = result.recommendations
        # author-a is opus → auto-mode; penalty never applies to it.
        assert not any("safety penalty" in r for r in rec.reasons)


# ---------------------------------------------------------------------------
# Backward-compat: recommend_lanes() returns a plain list
# ---------------------------------------------------------------------------


class TestRecommendLanesBackwardCompat:
    def test_returns_list_of_lane_recommendations(self) -> None:
        recs = recommend_lanes(["author-a"], _records=[])
        assert isinstance(recs, list)
        assert all(isinstance(r, LaneRecommendation) for r in recs)

    def test_wrapper_ignores_envelope_context_by_default(self, tmp_path: Path) -> None:
        """With defaults (required_* == "any"), recommend_lanes returns the
        same lanes the envelope-aware function does — no pre-filter."""
        lane_models_path = _write_lane_models(tmp_path)
        compat = recommend_lanes(
            ["author-a", "author-b"],
            lane_models_path=lane_models_path,
            _records=[],
        )
        envelope_aware = recommend_lanes_envelope_aware(
            ["author-a", "author-b"],
            lane_models_path=lane_models_path,
            _records=[],
        )
        assert [r.lane_id for r in compat] == [
            r.lane_id for r in envelope_aware.recommendations
        ]


# ---------------------------------------------------------------------------
# RecommendationResult shape invariants
# ---------------------------------------------------------------------------


class TestRecommendationResultShape:
    def test_empty_candidates_returns_empty_result(self) -> None:
        result = recommend_lanes_envelope_aware([])
        assert isinstance(result, RecommendationResult)
        assert result.recommendations == ()
        assert result.filtered_lanes == ()
        assert result.required_safety_envelope == "any"
        assert result.required_model_tier == "any"

    def test_required_fields_present_on_result(self, tmp_path: Path) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a"],
            required_model_tier="opus",
            required_safety_envelope="auto-mode",
            lane_models_path=lane_models_path,
            _records=[],
        )
        # Echoed caller preferences.
        assert result.required_model_tier == "opus"
        assert result.required_safety_envelope == "auto-mode"
        # Effective == caller preference when no escalation.
        assert result.effective_required_safety_envelope == "auto-mode"
        assert result.effective_required_model_tier == "opus"
        # No override, no reason.
        assert result.safety_envelope_override is False
        assert result.override_reason is None


# ---------------------------------------------------------------------------
# Emission payload — POLICY_VERSION trace + B.1 fields
# ---------------------------------------------------------------------------


class TestEmissionPayloadB1Fields:
    def test_policy_version_b1_in_emission(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        packet = _packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-a",
            events_dir=events_dir,
            lane_models_path=lane_models_path,
        )
        assert result is not None
        assert result["payload"]["policy_version"] == "b1-v1"
        assert result["payload"]["policy_version"] == POLICY_VERSION

    def test_all_b1_fields_present_in_payload(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        packet = _packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-a",
            events_dir=events_dir,
            required_safety_envelope="auto-mode",
            required_model_tier="opus",
            lane_models_path=lane_models_path,
        )
        assert result is not None
        payload = result["payload"]
        for key in (
            "required_safety_envelope",
            "required_model_tier",
            "effective_required_safety_envelope",
            "filtered_lanes",
            "safety_envelope_override",
            "warnings",
            "resolved_effort_hint",
            "required_tools",
        ):
            assert key in payload, f"missing B.1 field {key}"

        # Echoed values.
        assert payload["required_safety_envelope"] == "auto-mode"
        assert payload["required_model_tier"] == "opus"
        assert payload["effective_required_safety_envelope"] == "auto-mode"
        assert payload["safety_envelope_override"] is False
        assert isinstance(payload["filtered_lanes"], list)
        assert isinstance(payload["warnings"], list)

    def test_filtered_lanes_recorded_in_payload(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        packet = _packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],  # b is sonnet → filtered
            selected_lane="author-a",
            events_dir=events_dir,
            required_model_tier="opus",
            lane_models_path=lane_models_path,
        )
        assert result is not None
        payload = result["payload"]
        lanes_in_filtered = [f["lane"] for f in payload["filtered_lanes"]]
        assert "author-b" in lanes_in_filtered
        (filtered_b,) = [
            f for f in payload["filtered_lanes"] if f["lane"] == "author-b"
        ]
        assert filtered_b["reason"] == "tier-mismatch"

    def test_override_reason_captured_on_tool_escalation(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        packet = _packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-a",
            events_dir=events_dir,
            required_safety_envelope="bypass",
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
        )
        assert result is not None
        payload = result["payload"]
        assert payload["safety_envelope_override"] is True
        assert payload["override_reason"] == "tool-risk-rejected-under-bypass"
        assert payload["effective_required_safety_envelope"] == "auto-mode"

    def test_coverage_warning_surfaces_in_payload(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        # Lane config knows only author-a.
        lane_models_path = _write_lane_models(tmp_path, {"author-a": {"model": "opus"}})
        packet = _packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-q"],  # author-q is absent
            selected_lane="author-a",
            events_dir=events_dir,
            lane_models_path=lane_models_path,
        )
        assert result is not None
        warnings = result["payload"]["warnings"]
        assert any("'author-q' missing from lane_models.json" in w for w in warnings)

    def test_effort_hint_propagated_from_packet_metadata(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        packet = _packet(effort_hint="xhigh")
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["flex-a"],
            selected_lane="flex-a",
            events_dir=events_dir,
            lane_models_path=lane_models_path,
        )
        assert result is not None
        assert result["payload"]["resolved_effort_hint"] == "xhigh"

    def test_explicit_effort_hint_overrides_packet_metadata(
        self, tmp_path: Path
    ) -> None:
        events_dir = tmp_path / "events"
        lane_models_path = _write_lane_models(tmp_path)
        packet = _packet(effort_hint="lower")  # packet says lower
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["flex-a"],
            selected_lane="flex-a",
            events_dir=events_dir,
            resolved_effort_hint="max",  # caller overrides to max
            lane_models_path=lane_models_path,
        )
        assert result is not None
        assert result["payload"]["resolved_effort_hint"] == "max"


# ---------------------------------------------------------------------------
# End-to-end behavior smoke — combined tier + envelope + tool escalation
# ---------------------------------------------------------------------------


class TestCombinedFiltering:
    def test_opus_only_plus_destructive_tool_retains_opus_lanes_only(
        self, tmp_path: Path
    ) -> None:
        lane_models_path = _write_lane_models(tmp_path)
        tool_risk_path = _write_tool_risk_registry(tmp_path)
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-b", "author-c", "ops", "flex-a"],
            required_model_tier="opus",
            required_safety_envelope="bypass",  # will be escalated
            required_tools=["Bash(rm -rf *)"],
            lane_models_path=lane_models_path,
            tool_risk_path=tool_risk_path,
            _records=[],
        )
        # Only opus lanes survive: author-a, author-c, flex-a.
        ranked_ids = sorted(r.lane_id for r in result.recommendations)
        assert ranked_ids == ["author-a", "author-c", "flex-a"]
        # Override traced.
        assert result.safety_envelope_override is True
        # author-b (sonnet), ops (haiku) filtered: both bypass envelope,
        # and tier-mismatch on author-b specifically.
        filtered_by_lane = {f["lane"]: f for f in result.filtered_lanes}
        assert "author-b" in filtered_by_lane
        assert "ops" in filtered_by_lane

    def test_ranks_best_history_among_eligible_opus_lanes(self, tmp_path: Path) -> None:
        """When pre-filter leaves multiple lanes, history + new B.1 score
        components determine ordering. author-a beats author-c on history."""
        lane_models_path = _write_lane_models(tmp_path)
        records = [
            _outcome(
                actual_lane="author-a",
                token_spend=50_000,
                elapsed_seconds=600,
                review_rounds=0,
                shipped_outcome="merged",
            )
            for _ in range(10)
        ] + [
            _outcome(
                actual_lane="author-c",
                token_spend=300_000,
                elapsed_seconds=3600,
                review_rounds=3,
                shipped_outcome="merged",
            )
            for _ in range(10)
        ]
        result = recommend_lanes_envelope_aware(
            ["author-a", "author-c"],
            required_model_tier="opus",
            lane_models_path=lane_models_path,
            _records=records,
        )
        ranked = [r.lane_id for r in result.recommendations]
        assert ranked == ["author-a", "author-c"]
