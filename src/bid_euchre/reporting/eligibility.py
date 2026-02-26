"""Batch eligibility engine for promotion workflow.

Evaluates whether a batch of experiment runs meets promotion criteria
based on config membership, canonical summary health, notebook gate
status, semantic gate status, git SHA consistency, artifact freeze
status, and split manifest type.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from bid_euchre.core.time import utc_now_iso
from bid_euchre.models.freeze import verify_frozen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EligibilityResult:
    """Result of a single eligibility check."""

    rule: str
    status: str  # "PASS" or "FAIL"
    detail: str


@dataclass
class BatchGate:
    """Aggregated eligibility gate for a batch of runs."""

    eligible: bool
    reasons: list[EligibilityResult]
    batch_id: str
    batch_purpose: str
    created_at_utc: str

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "eligible": self.eligible,
            "batch_id": self.batch_id,
            "batch_purpose": self.batch_purpose,
            "created_at_utc": self.created_at_utc,
            "reasons": [asdict(r) for r in self.reasons],
        }


def check_config_membership(
    rollup: dict,
    expected_configs: Optional[set[str]] = None,
) -> EligibilityResult:
    """Verify all expected configs completed successfully in rollup.

    If expected_configs is None, verify all configs in rollup have status=ok.
    """
    configs = rollup.get("configs", [])

    if expected_configs is not None:
        completed = {
            Path(c["config_path"]).name for c in configs if c.get("status") == "ok"
        }
        missing = expected_configs - completed
        if missing:
            return EligibilityResult(
                rule="config_membership",
                status="FAIL",
                detail=f"Missing configs: {sorted(missing)}",
            )
        return EligibilityResult(
            rule="config_membership",
            status="PASS",
            detail=f"All {len(expected_configs)} expected configs completed",
        )

    # No expected set: verify all configs in rollup have status=ok
    failed = [Path(c["config_path"]).name for c in configs if c.get("status") != "ok"]
    if failed:
        return EligibilityResult(
            rule="config_membership",
            status="FAIL",
            detail=f"Configs with non-ok status: {sorted(failed)}",
        )
    return EligibilityResult(
        rule="config_membership",
        status="PASS",
        detail=f"All {len(configs)} configs completed",
    )


def check_canonical_summaries(
    rollup: dict,
    run_base_dir: str,
) -> EligibilityResult:
    """Verify all member runs have canonical_summary.json with fail_count==0."""
    configs = rollup.get("configs", [])
    base = Path(run_base_dir)
    failures = []

    for config in configs:
        if config.get("status") != "ok":
            continue
        run_dir = config.get("run_dir", "")

        # Try artifacts/ first (canonical path), then reports/ (legacy fallback)
        summary_path = base / run_dir / "artifacts" / "canonical_summary.json"
        if not summary_path.exists():
            legacy_path = base / run_dir / "reports" / "canonical_summary.json"
            if legacy_path.exists():
                summary_path = legacy_path
            else:
                failures.append(
                    f"{run_dir}: missing canonical_summary.json "
                    f"(tried artifacts/ and reports/)"
                )
                continue

        try:
            with summary_path.open() as f:
                summary = json.load(f)

            # Try nested schema first (production), then flat schema (legacy)
            fail_count = summary.get("sanity", {}).get("fail_count")
            if fail_count is None:
                # Legacy flat schema
                fail_count = summary.get("fail_count", -1)

            if fail_count != 0:
                failures.append(f"{run_dir}: fail_count={fail_count}")
        except (json.JSONDecodeError, KeyError) as e:
            failures.append(f"{run_dir}: parse error: {e}")

    if failures:
        return EligibilityResult(
            rule="canonical_summary_clean",
            status="FAIL",
            detail="; ".join(failures[:3]),
        )
    return EligibilityResult(
        rule="canonical_summary_clean",
        status="PASS",
        detail="All member runs have clean canonical summaries",
    )


def check_notebook_gate(
    gate_path: Optional[str],
    batch_purpose: str,
) -> EligibilityResult:
    """Check notebook gate JSON.

    - batch_purpose='promotion' + missing gate -> FAIL (gate required)
    - batch_purpose='promotion' + gate FAIL -> FAIL
    - batch_purpose!='promotion' + missing gate -> PASS (optional)
    - batch_purpose!='promotion' + gate FAIL -> FAIL
    """
    if gate_path is None or not Path(gate_path).exists():
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="notebook_gate",
                status="FAIL",
                detail="No notebook gate artifact found (required for promotion)",
            )
        return EligibilityResult(
            rule="notebook_gate",
            status="PASS",
            detail="No notebook gate artifact (optional for non-promotion)",
        )

    try:
        with open(gate_path) as f:
            gate = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return EligibilityResult(
            rule="notebook_gate",
            status="FAIL",
            detail=f"Failed to read gate artifact: {e}",
        )

    gate_status = gate.get("gate_status", "FAIL")
    if gate_status != "PASS":
        failed_nbs = [
            nb["name"] for nb in gate.get("notebooks", []) if nb.get("status") != "PASS"
        ]
        return EligibilityResult(
            rule="notebook_gate",
            status="FAIL",
            detail=f"Notebook gate FAIL: {failed_nbs}",
        )
    return EligibilityResult(
        rule="notebook_gate",
        status="PASS",
        detail=f"Notebook gate PASS ({gate.get('passed', 0)}/{gate.get('total', 0)})",
    )


def check_git_sha_consistency(
    rollup: dict,
) -> EligibilityResult:
    """Verify all member runs have matching git_sha."""
    configs = rollup.get("configs", [])
    shas = {c.get("git_sha", "unknown") for c in configs if c.get("status") == "ok"}
    shas.discard("unknown")

    if len(shas) == 0:
        return EligibilityResult(
            rule="git_sha_consistency",
            status="PASS",
            detail="No git SHAs to compare",
        )
    if len(shas) == 1:
        return EligibilityResult(
            rule="git_sha_consistency",
            status="PASS",
            detail=f"All runs: {shas.pop()}",
        )
    return EligibilityResult(
        rule="git_sha_consistency",
        status="FAIL",
        detail=f"Inconsistent git SHAs: {sorted(shas)}",
    )


def check_artifacts_frozen(
    artifact_dir: Optional[str],
    batch_purpose: str,
) -> EligibilityResult:
    """Check that model artifacts in artifact_dir are frozen via verify_frozen().

    Uses verify_frozen() from models.freeze to check both frozen_at and
    artifact_sha256 fields. Split manifest files are excluded from this check.

    - batch_purpose='promotion' + unfrozen artifacts -> FAIL
    - batch_purpose!='promotion' + unfrozen artifacts -> PASS with warning
    - No artifact_dir or no artifacts -> PASS (nothing to check)
    """
    if artifact_dir is None:
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="artifacts_frozen",
                status="FAIL",
                detail="No artifact directory provided (required for promotion)",
            )
        return EligibilityResult(
            rule="artifacts_frozen",
            status="PASS",
            detail="No artifact directory (optional for non-promotion)",
        )

    artifact_path = Path(artifact_dir)
    if not artifact_path.exists():
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="artifacts_frozen",
                status="FAIL",
                detail=f"Artifact directory not found: {artifact_dir}",
            )
        return EligibilityResult(
            rule="artifacts_frozen",
            status="PASS",
            detail="Artifact directory not found (optional for non-promotion)",
        )

    # Find model artifact JSON files (exclude infrastructure and split manifests)
    exempt = {
        "meta.json",
        "rollup.json",
        "canonical_summary.json",
        "training_metrics.json",
    }
    model_artifacts = [
        p
        for p in artifact_path.glob("*.json")
        if p.name not in exempt and not p.name.startswith("split_manifest")
    ]

    if not model_artifacts:
        return EligibilityResult(
            rule="artifacts_frozen",
            status="PASS",
            detail="No model artifacts found to check",
        )

    unfrozen = []
    for path in model_artifacts:
        if not verify_frozen(path):
            unfrozen.append(path.name)

    if unfrozen:
        detail = f"Unfrozen artifacts: {sorted(unfrozen)}"
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="artifacts_frozen",
                status="FAIL",
                detail=detail,
            )
        logger.warning("Unfrozen artifacts (non-promotion): %s", unfrozen)
        return EligibilityResult(
            rule="artifacts_frozen",
            status="PASS",
            detail=f"{detail} (non-promotion, warning only)",
        )

    return EligibilityResult(
        rule="artifacts_frozen",
        status="PASS",
        detail=f"All {len(model_artifacts)} model artifacts frozen",
    )


def check_split_manifests(
    split_manifest_dir: Optional[str],
    batch_purpose: str,
) -> EligibilityResult:
    """Check split manifests exist and have correct split type.

    - batch_purpose='promotion' -> require three_way splits
    - batch_purpose!='promotion' -> two_way or three_way both OK
    - No manifest dir -> PASS for non-promotion, FAIL for promotion
    """
    if split_manifest_dir is None:
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="split_manifests",
                status="FAIL",
                detail="No split manifest directory provided (required for promotion)",
            )
        return EligibilityResult(
            rule="split_manifests",
            status="PASS",
            detail="No split manifest directory (optional for non-promotion)",
        )

    manifest_path = Path(split_manifest_dir)
    if not manifest_path.exists():
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="split_manifests",
                status="FAIL",
                detail=f"Split manifest directory not found: {split_manifest_dir}",
            )
        return EligibilityResult(
            rule="split_manifests",
            status="PASS",
            detail="Split manifest directory not found (optional for non-promotion)",
        )

    manifests = list(manifest_path.glob("split_manifest*.json"))

    if not manifests:
        if batch_purpose == "promotion":
            return EligibilityResult(
                rule="split_manifests",
                status="FAIL",
                detail="No split manifests found (required for promotion)",
            )
        return EligibilityResult(
            rule="split_manifests",
            status="PASS",
            detail="No split manifests found (optional for non-promotion)",
        )

    issues = []
    for path in manifests:
        try:
            with open(path) as f:
                data = json.load(f)
            split_type = data.get("split_type", "unknown")
            if batch_purpose == "promotion" and split_type != "three_way":
                issues.append(f"{path.name}: split_type={split_type} (need three_way)")
        except (json.JSONDecodeError, OSError):
            issues.append(f"{path.name} (unreadable)")

    if issues:
        return EligibilityResult(
            rule="split_manifests",
            status="FAIL",
            detail="; ".join(issues[:3]),
        )

    return EligibilityResult(
        rule="split_manifests",
        status="PASS",
        detail=f"All {len(manifests)} split manifests valid",
    )


def check_semantic_gate(
    semantic_gate_dir: Optional[str],
    batch_purpose: str,
) -> list[EligibilityResult]:
    """Check semantic gate artifacts for val and test splits.

    Returns a list of EligibilityResult with distinct rule names:
    - ``rule="semantic_gate_val"`` for the val gate
    - ``rule="semantic_gate_test"`` for the test gate

    File naming convention:
    - ``semantic_gate_val.json`` for val split
    - ``semantic_gate_test.json`` for test split
    """
    results: list[EligibilityResult] = []

    # --- Val gate ---
    if semantic_gate_dir is None:
        if batch_purpose == "promotion":
            results.append(
                EligibilityResult(
                    rule="semantic_gate_val",
                    status="FAIL",
                    detail="No semantic gate directory provided (required for promotion)",
                )
            )
        else:
            results.append(
                EligibilityResult(
                    rule="semantic_gate_val",
                    status="PASS",
                    detail="No semantic gate directory (optional for non-promotion)",
                )
            )
        return results

    gate_dir = Path(semantic_gate_dir)

    # Check val gate
    val_path = gate_dir / "semantic_gate_val.json"
    if not val_path.exists():
        results.append(
            EligibilityResult(
                rule="semantic_gate_val",
                status="FAIL",
                detail=f"Val semantic gate not found: {val_path}",
            )
        )
    else:
        try:
            with open(val_path) as f:
                val_gate = json.load(f)
            val_status = val_gate.get("gate_status", "FAIL")
            if val_status == "PASS":
                results.append(
                    EligibilityResult(
                        rule="semantic_gate_val",
                        status="PASS",
                        detail=f"Val semantic gate PASS "
                        f"({val_gate.get('passed_checks', 0)}/{val_gate.get('total_checks', 0)})",
                    )
                )
            else:
                results.append(
                    EligibilityResult(
                        rule="semantic_gate_val",
                        status="FAIL",
                        detail=f"Val semantic gate {val_status} "
                        f"({val_gate.get('failed_checks', 0)} failed checks)",
                    )
                )
        except (json.JSONDecodeError, OSError) as e:
            results.append(
                EligibilityResult(
                    rule="semantic_gate_val",
                    status="FAIL",
                    detail=f"Failed to read val semantic gate: {e}",
                )
            )

    # --- Test gate ---
    test_path = gate_dir / "semantic_gate_test.json"
    if not test_path.exists():
        if batch_purpose == "promotion":
            results.append(
                EligibilityResult(
                    rule="semantic_gate_test",
                    status="FAIL",
                    detail=f"Test semantic gate not found: {test_path} "
                    "(required for promotion)",
                )
            )
        # For non-promotion, test gate is not emitted (list has only val result)
    else:
        try:
            with open(test_path) as f:
                test_gate = json.load(f)
            test_status = test_gate.get("gate_status", "FAIL")
            if test_status == "PASS":
                results.append(
                    EligibilityResult(
                        rule="semantic_gate_test",
                        status="PASS",
                        detail=f"Test semantic gate PASS "
                        f"({test_gate.get('passed_checks', 0)}/{test_gate.get('total_checks', 0)})",
                    )
                )
            else:
                results.append(
                    EligibilityResult(
                        rule="semantic_gate_test",
                        status="FAIL",
                        detail=f"Test semantic gate {test_status} "
                        f"({test_gate.get('failed_checks', 0)} failed checks)",
                    )
                )
        except (json.JSONDecodeError, OSError) as e:
            results.append(
                EligibilityResult(
                    rule="semantic_gate_test",
                    status="FAIL",
                    detail=f"Failed to read test semantic gate: {e}",
                )
            )

    return results


def compute_eligibility(
    rollup: dict,
    run_base_dir: str,
    batch_purpose: str,
    notebook_gate_path: Optional[str] = None,
    expected_configs: Optional[set[str]] = None,
    artifact_dir: Optional[str] = None,
    split_manifest_dir: Optional[str] = None,
    semantic_gate_dir: Optional[str] = None,
) -> BatchGate:
    """Run all eligibility checks. eligible=True only if ALL checks PASS."""
    batch_id = rollup.get("batch", {}).get("batch_id", "unknown")

    results = [
        check_config_membership(rollup, expected_configs),
        check_canonical_summaries(rollup, run_base_dir),
        check_notebook_gate(notebook_gate_path, batch_purpose),
    ]
    results.extend(check_semantic_gate(semantic_gate_dir, batch_purpose))
    results.extend(
        [
            check_git_sha_consistency(rollup),
            check_artifacts_frozen(artifact_dir, batch_purpose),
            check_split_manifests(split_manifest_dir, batch_purpose),
        ]
    )

    eligible = all(r.status == "PASS" for r in results)

    return BatchGate(
        eligible=eligible,
        reasons=results,
        batch_id=batch_id,
        batch_purpose=batch_purpose,
        created_at_utc=utc_now_iso(),
    )
