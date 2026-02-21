"""
Unit tests for R0 promotion scripts and eval configs.

Tests cover:
- write_r0_promotion.py: auto-promote logic, NaN rejection, arm validation
- update_r0_bundle.py: eval path filling, idempotency
- Promotion decision schema compliance
- Eval config loading
"""

import json
from pathlib import Path

import pytest

from scripts.update_r0_bundle import update_bundle
from scripts.write_r0_promotion import (
    _all_metrics_finite,
    write_r0_promotion,
)


def _make_frozen_artifact(path: Path, artifact_name: str = "hybrid_r0.json") -> str:
    """Create a minimal frozen hybrid_olsa_v1 artifact file.

    Returns the file path as a string.
    """
    artifact_path = path / artifact_name
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": {
            "suit": {
                "weights": [0.5, 0.3, 0.2],
                "bias": 4.5,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            },
        },
        "residual_variance": {"suit": 2.5},
        "risk_lambda": 0.0,
        "context_features": [],
        "training_seed": 42,
        "training_run_id": "test_run",
        "split_type": "three_way",
        "frozen_at": None,
        "artifact_sha256": None,
    }
    # Compute content hash and freeze manually
    import hashlib

    content = {
        k: v for k, v in artifact.items() if k not in ("frozen_at", "artifact_sha256")
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    artifact["frozen_at"] = "2026-02-20T00:00:00Z"
    artifact["artifact_sha256"] = content_hash

    with open(artifact_path, "w") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)

    return str(artifact_path)


def _make_eval_file(path: Path, filename: str = "eval_r0.json", **overrides) -> str:
    """Create a minimal eval result file with valid metrics."""
    eval_path = path / filename
    metrics = {
        "net_expected_points_per_deal": 0.35,
        "expected_points_per_deal": 1.80,
        "bid_rate": 0.55,
        "make_rate": 0.60,
        "cvar_5": -4.0,
        "downside_variance": 10.5,
        "std_bidder_team_points": 4.8,
        "n_deals": 50000,
    }
    metrics.update(overrides)
    with open(eval_path, "w") as f:
        json.dump(metrics, f, indent=2)
    return str(eval_path)


def _make_bundle(
    tmp_path: Path,
    olsa_artifact: str,
    olsa_full_artifact: str,
    olsa_eval: str | None = None,
    olsa_full_eval: str | None = None,
) -> str:
    """Create a minimal rung bundle JSON."""
    bundle_path = tmp_path / "rung_bundle_r0.json"

    with open(olsa_artifact) as f:
        olsa_art = json.load(f)
    with open(olsa_full_artifact) as f:
        full_art = json.load(f)

    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "timestamp": "2026-02-20T00:00:00Z",
        "olsa": {
            "artifact_path": olsa_artifact,
            "artifact_sha256": olsa_art.get("artifact_sha256"),
            "selected_features": {"suit": ["bowers", "trump_count", "offsuit_aces"]},
            "eval_seed42": olsa_eval,
            "eval_seed43": None,
            "eval_seed44": None,
            "semantic_gate_val": None,
            "semantic_gate_test": None,
        },
        "olsa_full": {
            "artifact_path": olsa_full_artifact,
            "artifact_sha256": full_art.get("artifact_sha256"),
            "selected_features": {"suit": ["bowers", "trump_count", "offsuit_aces"]},
            "eval_seed42": olsa_full_eval,
            "eval_seed43": None,
            "eval_seed44": None,
            "semantic_gate_val": None,
            "semantic_gate_test": None,
        },
        "split_manifest": str(tmp_path / "split_manifest_r0_suit.json"),
        "training_report": str(tmp_path / "training_report_r0.json"),
        "incumbent": None,
        "control": None,
    }

    with open(bundle_path, "w") as f:
        json.dump(bundle, f, indent=2)

    return str(bundle_path)


# ─── Test: write_r0_promotion auto-promote ───────────────────────────────


def test_write_r0_promotion_auto_promote(tmp_path):
    """With valid bundle + finite metrics, decision is PROMOTED."""
    olsa = _make_frozen_artifact(tmp_path, "hybrid_r0.json")
    olsa_full = _make_frozen_artifact(tmp_path, "hybrid_r0_full.json")
    olsa_eval = _make_eval_file(tmp_path, "eval_r0.json")
    olsa_full_eval = _make_eval_file(
        tmp_path,
        "eval_r0_full.json",
        net_expected_points_per_deal=0.40,
    )

    bundle_path = _make_bundle(
        tmp_path,
        olsa,
        olsa_full,
        olsa_eval=olsa_eval,
        olsa_full_eval=olsa_full_eval,
    )
    output = str(tmp_path / "promotion_decision_r0.json")

    record = write_r0_promotion(bundle_path, output)

    assert record["decision"] == "PROMOTED"
    assert record["schema_version"] == 3
    assert record["rung_id"] == "r0"
    assert record["arc"] == "arc_d"
    assert record["attribution_gap"] is not None
    assert "halt_reasons" not in record

    # Verify file was written
    with open(output) as f:
        written = json.load(f)
    assert written["decision"] == "PROMOTED"


# ─── Test: NaN/Inf metrics rejection ─────────────────────────────────────


def test_write_r0_promotion_rejects_nan_metrics(tmp_path):
    """If any metric is NaN, decision is HALT."""
    olsa = _make_frozen_artifact(tmp_path, "hybrid_r0.json")
    olsa_full = _make_frozen_artifact(tmp_path, "hybrid_r0_full.json")
    olsa_eval = _make_eval_file(tmp_path, "eval_r0.json")
    olsa_full_eval = _make_eval_file(
        tmp_path,
        "eval_r0_full.json",
        net_expected_points_per_deal=float("nan"),
    )

    bundle_path = _make_bundle(
        tmp_path,
        olsa,
        olsa_full,
        olsa_eval=olsa_eval,
        olsa_full_eval=olsa_full_eval,
    )
    output = str(tmp_path / "promotion_decision_r0.json")

    record = write_r0_promotion(bundle_path, output)

    assert record["decision"] == "HALT"
    assert "halt_reasons" in record
    assert any("not finite" in r for r in record["halt_reasons"])


# ─── Test: requires both arms ─────────────────────────────────────────────


def test_write_r0_promotion_requires_both_arms(tmp_path):
    """Bundle missing olsa_full arm raises ValueError."""
    bundle_path = tmp_path / "bad_bundle.json"
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {"artifact_path": "fake.json"},
    }
    with open(bundle_path, "w") as f:
        json.dump(bundle, f)

    with pytest.raises(ValueError, match="missing 'olsa_full'"):
        write_r0_promotion(str(bundle_path), str(tmp_path / "out.json"))


# ─── Test: update_bundle fills eval paths ──────────────────────────────────


def test_update_bundle_fills_eval_paths(tmp_path):
    """update_bundle correctly fills null eval_seed42/43/44 fields."""
    olsa = _make_frozen_artifact(tmp_path, "hybrid_r0.json")
    olsa_full = _make_frozen_artifact(tmp_path, "hybrid_r0_full.json")
    bundle_path = _make_bundle(tmp_path, olsa, olsa_full)

    # Verify initially null
    with open(bundle_path) as f:
        initial = json.load(f)
    assert initial["olsa"]["eval_seed42"] is None

    # Update
    updated = update_bundle(
        bundle_path,
        arm="olsa",
        eval_seed42="data/eval_r0.json",
        eval_seed43="data/eval_r0_s43.json",
        eval_seed44="data/eval_r0_s44.json",
    )

    assert updated["olsa"]["eval_seed42"] == "data/eval_r0.json"
    assert updated["olsa"]["eval_seed43"] == "data/eval_r0_s43.json"
    assert updated["olsa"]["eval_seed44"] == "data/eval_r0_s44.json"

    # Verify persisted to disk
    with open(bundle_path) as f:
        on_disk = json.load(f)
    assert on_disk["olsa"]["eval_seed42"] == "data/eval_r0.json"


# ─── Test: update_bundle idempotent ────────────────────────────────────────


def test_update_bundle_idempotent(tmp_path):
    """Running update twice with same paths doesn't corrupt."""
    olsa = _make_frozen_artifact(tmp_path, "hybrid_r0.json")
    olsa_full = _make_frozen_artifact(tmp_path, "hybrid_r0_full.json")
    bundle_path = _make_bundle(tmp_path, olsa, olsa_full)

    kwargs = {
        "bundle_path": bundle_path,
        "arm": "olsa_full",
        "eval_seed42": "data/eval_r0_full.json",
    }

    first = update_bundle(**kwargs)
    second = update_bundle(**kwargs)

    assert first["olsa_full"]["eval_seed42"] == second["olsa_full"]["eval_seed42"]
    assert first["bundle_schema"] == second["bundle_schema"]
    assert first["rung_id"] == second["rung_id"]


# ─── Test: promotion decision schema ──────────────────────────────────────


def test_promotion_decision_schema(tmp_path):
    """Written promotion decision has all required fields per schema v3."""
    olsa = _make_frozen_artifact(tmp_path, "hybrid_r0.json")
    olsa_full = _make_frozen_artifact(tmp_path, "hybrid_r0_full.json")
    olsa_eval = _make_eval_file(tmp_path, "eval_r0.json")
    olsa_full_eval = _make_eval_file(tmp_path, "eval_r0_full.json")
    bundle_path = _make_bundle(
        tmp_path, olsa, olsa_full, olsa_eval=olsa_eval, olsa_full_eval=olsa_full_eval
    )
    output = str(tmp_path / "promotion_decision_r0.json")

    write_r0_promotion(bundle_path, output)

    with open(output) as f:
        record = json.load(f)

    # Required top-level fields (schema v3)
    required_fields = [
        "schema_version",
        "rung_id",
        "arc",
        "decision",
        "timestamp",
        "evaluator_git_sha",
        "attribution_gap",
        "tier_1_checks",
        "challenger",
        "olsa_arm",
        "control",
        "gate_results",
    ]
    for field_name in required_fields:
        assert field_name in record, f"Missing field: {field_name}"

    assert record["schema_version"] == 3
    assert record["rung_id"] == "r0"
    assert record["arc"] == "arc_d"
    assert record["decision"] in ("PROMOTED", "HALT")
    assert record["timestamp"].endswith("Z")

    # Challenger block
    assert record["challenger"]["arm"] == "OLSa_Full"
    assert "artifact_path" in record["challenger"]
    assert "metrics_seed42" in record["challenger"]

    # OLSa arm block
    assert "artifact_path" in record["olsa_arm"]


# ─── Test: eval config loads ──────────────────────────────────────────────


def test_eval_config_loads():
    """Arc D eval YAML configs parse without errors via ExperimentConfig."""
    from bid_euchre.experiments.config import load_config

    configs = [
        "experiments/configs/arc_d_eval_r0.yaml",
        "experiments/configs/arc_d_eval_r0_full.yaml",
        "experiments/configs/arc_d_eval_r0_diagnostic.yaml",
    ]

    for config_path in configs:
        config = load_config(config_path)
        assert config.experiment_name.startswith("arc_d_eval_r0")
        assert len(config.bidding_policies) >= 1
        assert len(config.scenarios) >= 1

        # Verify bidding policies reference HybridOLSaBidder or OLSaBidder
        for policy in config.bidding_policies:
            assert policy.class_name in ("HybridOLSaBidder", "OLSaBidder")
            assert "artifact_path" in policy.params


# ─── Test: _all_metrics_finite helper ─────────────────────────────────────


def test_all_metrics_finite_valid():
    """Valid metrics pass the finiteness check."""
    metrics = {
        "net_expected_points_per_deal": 0.35,
        "expected_points_per_deal": 1.80,
        "bid_rate": 0.55,
        "make_rate": 0.60,
        "cvar_5": -4.0,
        "downside_variance": 10.5,
        "std_bidder_team_points": 4.8,
    }
    ok, failures = _all_metrics_finite(metrics)
    assert ok
    assert failures == []


def test_all_metrics_finite_inf():
    """Inf metric fails the finiteness check."""
    metrics = {
        "net_expected_points_per_deal": float("inf"),
        "expected_points_per_deal": 1.80,
        "bid_rate": 0.55,
        "make_rate": 0.60,
        "cvar_5": -4.0,
        "downside_variance": 10.5,
        "std_bidder_team_points": 4.8,
    }
    ok, failures = _all_metrics_finite(metrics)
    assert not ok
    assert len(failures) == 1
    assert "not finite" in failures[0]
