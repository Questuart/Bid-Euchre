"""Tests for the shadow-mode adaptive dispatch advisor (Slice E, #2169).

These tests pin the scorer's behavioural contract:

* Ranking is well-ordered given synthetic histories with one obviously
  better lane.
* Cold-start lanes (< MIN_OBS_FOR_CONFIDENCE observations) receive
  confidence capped at the cold-start ceiling.
* Null-safety: an empty outcome store does not raise and returns
  zero-score recommendations for every candidate.
* Deterministic ordering under ties.
* :data:`POLICY_VERSION` bumps whenever :data:`SCORE_WEIGHTS` changes
  (enforced via a sha256 fingerprint assertion).
* :func:`log_recommendation_for_dispatch` emits exactly one
  ``dispatch_recommendation`` event.
* ``learning.py`` does not import ``worker_pool`` (one-way dependency).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bid_euchre.ops import learning
from bid_euchre.ops.learning import (
    ADVISOR_MODE,
    MIN_OBS_FOR_CONFIDENCE,
    POLICY_VERSION,
    SCORE_WEIGHTS,
    LaneFeatures,
    build_lane_features,
    log_recommendation_for_dispatch,
    policy_fingerprint,
    recommend_lanes,
)

# ---------------------------------------------------------------------------
# Synthetic outcome record factory
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
    """Build a namespace that quacks like TaskOutcomeRecord for the scorer."""
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


# ---------------------------------------------------------------------------
# Policy version / weights
# ---------------------------------------------------------------------------


# Expected fingerprint committed alongside POLICY_VERSION. Bumping
# SCORE_WEIGHTS or MIN_OBS_FOR_CONFIDENCE without updating this value fails
# the test, which is the structural guardrail against silent weight drift.
#
# Version history:
#
# - slice-e-v1: 25c10be1af9d55d2bbbbe0c0d16823704ce5fb421a737d7d204e552832051857
# - b1-v1:      6687b86128073d1f672d25a761816685dbd594bf391faa69db6a9146c4a148d9
#   (Primitive B Phase 0 — added model_tier_match, effort_match,
#   safety_envelope_penalty weights.)
_EXPECTED_POLICY_FINGERPRINT = (
    "6687b86128073d1f672d25a761816685dbd594bf391faa69db6a9146c4a148d9"
)


class TestPolicyVersion:
    def test_policy_version_is_set(self) -> None:
        # Accepts the Primitive B Phase 0 "b1-v*" series (current) plus the
        # legacy "slice-e-v*" series so a partial rollback does not
        # silently pass this test.
        assert POLICY_VERSION.startswith(("b1-v", "slice-e-v"))

    def test_policy_fingerprint_pins_weights(self) -> None:
        """If this fails, bump POLICY_VERSION and update the expected hash."""
        actual = policy_fingerprint()
        assert actual == _EXPECTED_POLICY_FINGERPRINT, (
            f"SCORE_WEIGHTS or MIN_OBS_FOR_CONFIDENCE changed without a "
            f"POLICY_VERSION bump. Current fingerprint: {actual}. "
            f"If the change is intentional, bump POLICY_VERSION and update "
            f"_EXPECTED_POLICY_FINGERPRINT in this test."
        )

    def test_score_weights_include_all_components(self) -> None:
        required = {"clean_rate", "token_efficiency", "cycle_time", "rework_penalty"}
        assert required.issubset(SCORE_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Advisor mode gate
# ---------------------------------------------------------------------------


class TestAdvisorMode:
    def test_default_is_shadow(self) -> None:
        assert ADVISOR_MODE == "shadow"

    def test_valid_modes_are_two_values(self) -> None:
        assert learning._VALID_ADVISOR_MODES == frozenset({"shadow", "disabled"})
        assert "auto" not in learning._VALID_ADVISOR_MODES


# ---------------------------------------------------------------------------
# build_lane_features
# ---------------------------------------------------------------------------


class TestBuildLaneFeatures:
    def test_empty_substrate_returns_zero_features(self) -> None:
        feat = build_lane_features("author-a", _records=[])
        assert feat == LaneFeatures(lane_id="author-a")

    def test_observations_counted_correctly(self) -> None:
        records = [_outcome(actual_lane="author-a") for _ in range(3)]
        feat = build_lane_features("author-a", _records=records)
        assert feat.observations == 3

    def test_only_matching_lane_included(self) -> None:
        records = [
            _outcome(actual_lane="author-a"),
            _outcome(actual_lane="author-b"),
            _outcome(actual_lane="author-a"),
        ]
        feat_a = build_lane_features("author-a", _records=records)
        feat_b = build_lane_features("author-b", _records=records)
        assert feat_a.observations == 2
        assert feat_b.observations == 1

    def test_clean_completion_rate(self) -> None:
        records = [
            _outcome(actual_lane="author-a", shipped_outcome="merged", review_rounds=0),
            _outcome(actual_lane="author-a", shipped_outcome="merged", review_rounds=1),
            _outcome(actual_lane="author-a", shipped_outcome="merged", review_rounds=3),
            _outcome(
                actual_lane="author-a", shipped_outcome="abandoned", review_rounds=0
            ),
        ]
        feat = build_lane_features("author-a", _records=records)
        # 2 of 4 are "merged AND review_rounds <= 1"
        assert feat.clean_completion_rate == 0.5

    def test_avg_tokens_uses_token_spend_when_available(self) -> None:
        records = [
            _outcome(actual_lane="author-a", token_spend=50_000),
            _outcome(actual_lane="author-a", token_spend=150_000),
        ]
        feat = build_lane_features("author-a", _records=records)
        assert feat.avg_tokens_per_packet == 100_000

    def test_avg_tokens_falls_back_to_lane_total(self) -> None:
        records = [
            _outcome(
                actual_lane="author-a",
                token_spend=None,
                lane_total_tokens=200_000,
            ),
            _outcome(
                actual_lane="author-a",
                token_spend=None,
                lane_total_tokens=200_000,
            ),
        ]
        feat = build_lane_features("author-a", _records=records)
        # 200_000 / 2 observations
        assert feat.avg_tokens_per_packet == 100_000

    def test_task_type_filter(self) -> None:
        records = [
            _outcome(actual_lane="author-a", task_type="convention"),
            _outcome(actual_lane="author-a", task_type="ops"),
            _outcome(actual_lane="author-a", task_type="convention"),
        ]
        feat = build_lane_features("author-a", task_type="convention", _records=records)
        assert feat.observations == 2

    def test_complexity_filter(self) -> None:
        records = [
            _outcome(actual_lane="author-a", complexity=1),
            _outcome(actual_lane="author-a", complexity=3),
            _outcome(actual_lane="author-a", complexity=3),
        ]
        feat = build_lane_features("author-a", complexity=3, _records=records)
        assert feat.observations == 2

    def test_confidence_cold_start_capped(self) -> None:
        records = [_outcome(actual_lane="author-a")]
        feat = build_lane_features("author-a", _records=records)
        # 1 observation, MIN_OBS_FOR_CONFIDENCE=5 → cold-start cap 0.3
        assert feat.confidence <= 0.3
        assert feat.observations < MIN_OBS_FOR_CONFIDENCE

    def test_confidence_saturates_when_sufficient(self) -> None:
        records = [
            _outcome(actual_lane="author-a") for _ in range(MIN_OBS_FOR_CONFIDENCE + 3)
        ]
        feat = build_lane_features("author-a", _records=records)
        assert feat.confidence == 1.0


# ---------------------------------------------------------------------------
# recommend_lanes
# ---------------------------------------------------------------------------


class TestRecommendLanes:
    def test_empty_candidates_returns_empty(self) -> None:
        assert recommend_lanes([], _records=[]) == []

    def test_empty_substrate_is_null_safe(self) -> None:
        # Note: Primitive B.1 adds an "any → +0.5 for opus" model-tier
        # bonus that applies even without observations. We still rely on
        # recommend_lanes() not raising on empty substrate and returning
        # deterministic tie-broken output.
        recs = recommend_lanes(
            ["author-a", "author-b"],
            _records=[],
            lane_models={},  # force conservative fallback (opus default)
        )
        assert len(recs) == 2
        # Sorted deterministically by (score desc, lane_id asc). Under the
        # B.1 "any" bonus both lanes tie at the same opus-fallback score,
        # so ordering collapses to lane_id ascending.
        assert [r.lane_id for r in recs] == ["author-a", "author-b"]

    def test_ranks_obviously_better_lane_first(self) -> None:
        # author-a: 10 clean merges, cheap
        # author-b: 10 dirty merges, expensive
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
                actual_lane="author-b",
                token_spend=300_000,
                elapsed_seconds=3600,
                review_rounds=3,
                shipped_outcome="merged",
            )
            for _ in range(10)
        ]
        recs = recommend_lanes(["author-a", "author-b"], _records=records)
        assert recs[0].lane_id == "author-a"
        assert recs[1].lane_id == "author-b"
        assert recs[0].score > recs[1].score

    def test_deterministic_ordering_under_ties(self) -> None:
        # All lanes identical → ordering is by lane_id ascending.
        records = (
            [_outcome(actual_lane="author-a") for _ in range(3)]
            + [_outcome(actual_lane="author-b") for _ in range(3)]
            + [_outcome(actual_lane="author-c") for _ in range(3)]
        )
        recs = recommend_lanes(["author-c", "author-a", "author-b"], _records=records)
        assert [r.lane_id for r in recs] == ["author-a", "author-b", "author-c"]

    def test_confidence_preserved_on_recommendation(self) -> None:
        records = [_outcome(actual_lane="author-a")]  # 1 obs
        recs = recommend_lanes(["author-a"], _records=records)
        assert recs[0].features.confidence <= 0.3

    def test_reasons_populated(self) -> None:
        records = [
            _outcome(actual_lane="author-a", shipped_outcome="merged", review_rounds=0)
            for _ in range(10)
        ]
        recs = recommend_lanes(["author-a"], _records=records)
        assert "high clean rate" in recs[0].reasons

    def test_rework_penalty_applied(self) -> None:
        # Two lanes with identical positive signals, different churn.
        records = [
            _outcome(
                actual_lane="author-a",
                review_rounds=0,
                shipped_outcome="merged",
            )
            for _ in range(10)
        ] + [
            _outcome(
                actual_lane="author-b",
                review_rounds=5,
                shipped_outcome="merged",
            )
            for _ in range(10)
        ]
        recs = recommend_lanes(["author-a", "author-b"], _records=records)
        assert recs[0].lane_id == "author-a"
        # author-a has review_rounds=0 → clean rate 1.0, no churn penalty.
        # author-b has review_rounds=5 → clean rate 0.0, churn penalty 2.0.
        assert recs[0].score > recs[1].score


# ---------------------------------------------------------------------------
# Purity — recommend_lanes has no side effects
# ---------------------------------------------------------------------------


class TestRecommendLanesIsPure:
    def test_does_not_touch_filesystem(self, tmp_path: Path) -> None:
        """Calling recommend_lanes with explicit records must not write anywhere."""
        records = [_outcome(actual_lane="author-a")]
        before = set(tmp_path.rglob("*"))
        recommend_lanes(
            ["author-a"],
            _records=records,
            events_dir=tmp_path / "events",
            output_dir=tmp_path / "runs",
        )
        after = set(tmp_path.rglob("*"))
        assert before == after


# ---------------------------------------------------------------------------
# log_recommendation_for_dispatch — single side-effect function
# ---------------------------------------------------------------------------


def _make_packet(
    *,
    packet_id: str = "pkt-log-test",
    task_type: str | None = "convention",
    complexity: int | None = 2,
) -> SimpleNamespace:
    """Build a packet-like object with the metadata get_* accessors expect."""
    metadata: dict[str, object] = {}
    if task_type is not None:
        metadata["task_type"] = task_type
    if complexity is not None:
        metadata["complexity_estimate"] = complexity
    return SimpleNamespace(packet_id=packet_id, metadata=metadata)


class TestLogRecommendationForDispatch:
    def test_emits_exactly_one_event(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        packet = _make_packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-a",
            events_dir=events_dir,
        )
        assert result is not None
        assert result["event_type"] == "dispatch_recommendation"

        # Exactly one line in the log.
        log_file = events_dir / "events.jsonl"
        lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "dispatch_recommendation"

    def test_payload_shape(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        packet = _make_packet(packet_id="pkt-shape", task_type="ops", complexity=3)
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-b",
            events_dir=events_dir,
        )
        assert result is not None
        payload = result["payload"]
        # Always-present keys
        for key in (
            "packet_id",
            "task_type",
            "complexity_estimate",
            "candidates",
            "selected_lane",
            "override",
            "override_reason",
            "policy_version",
            "window_days",
            "advisor_mode",
        ):
            assert key in payload, f"missing {key}"
        assert payload["packet_id"] == "pkt-shape"
        assert payload["task_type"] == "ops"
        assert payload["complexity_estimate"] == 3
        assert payload["selected_lane"] == "author-b"
        assert payload["policy_version"] == POLICY_VERSION
        assert payload["advisor_mode"] == "shadow"

    def test_override_flag_computed_by_logger(self, tmp_path: Path) -> None:
        """override = (selected != top-ranked). Caller does not supply it."""
        events_dir = tmp_path / "events"
        packet = _make_packet()
        # Empty records → both lanes tie at 0 → top-ranked is sorted by lane_id.
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-b",  # Not top (author-a sorts first)
            events_dir=events_dir,
        )
        assert result is not None
        assert result["payload"]["override"] is True
        # And conversely:
        result2 = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a", "author-b"],
            selected_lane="author-a",
            events_dir=events_dir,
        )
        assert result2 is not None
        assert result2["payload"]["override"] is False

    def test_disabled_mode_skips_logging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(learning, "ADVISOR_MODE", "disabled")
        events_dir = tmp_path / "events"
        packet = _make_packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a"],
            selected_lane="author-a",
            events_dir=events_dir,
        )
        assert result is None
        assert not (events_dir / "events.jsonl").exists()

    def test_unknown_mode_skips_logging_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(learning, "ADVISOR_MODE", "auto")  # not yet valid
        events_dir = tmp_path / "events"
        packet = _make_packet()
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a"],
            selected_lane="author-a",
            events_dir=events_dir,
        )
        assert result is None

    def test_missing_packet_metadata_does_not_crash(self, tmp_path: Path) -> None:
        events_dir = tmp_path / "events"
        # Packet with no metadata at all
        packet = SimpleNamespace(packet_id="pkt-bare", metadata={})
        result = log_recommendation_for_dispatch(
            packet=packet,
            candidates=["author-a"],
            selected_lane="author-a",
            events_dir=events_dir,
        )
        assert result is not None
        assert result["payload"]["task_type"] is None
        assert result["payload"]["complexity_estimate"] is None


# ---------------------------------------------------------------------------
# Structural: one-way dependency (learning does NOT import worker_pool)
# ---------------------------------------------------------------------------


class TestOneWayDependency:
    def test_learning_does_not_import_worker_pool(self) -> None:
        """Structural guardrail: learning.py must not depend on worker_pool.

        The shadow-mode invariant relies on worker_pool being the only module
        that ever calls log_recommendation_for_dispatch. Letting learning.py
        import worker_pool would create a path for the advisor to call the
        dispatch lifecycle directly — which is exactly what shadow mode
        forbids.
        """
        src = Path(learning.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert (
                        "worker_pool" not in alias.name
                    ), f"learning.py must not import worker_pool (found: {alias.name})"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert (
                    "worker_pool" not in module
                ), f"learning.py must not import from worker_pool (found: {module})"
