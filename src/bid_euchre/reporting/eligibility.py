"""Batch eligibility engine for promotion workflow.

Evaluates whether a batch of experiment runs meets promotion criteria
based on config membership, canonical summary health, notebook gate
status, and git SHA consistency.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from bid_euchre.experiments.meta import utc_now_iso


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
            Path(c["config_path"]).name
            for c in configs
            if c.get("status") == "ok"
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
    failed = [
        Path(c["config_path"]).name
        for c in configs
        if c.get("status") != "ok"
    ]
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
        summary_path = base / run_dir / "reports" / "canonical_summary.json"
        if not summary_path.exists():
            failures.append(f"{run_dir}: missing canonical_summary.json")
            continue
        try:
            with summary_path.open() as f:
                summary = json.load(f)
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
            nb["name"]
            for nb in gate.get("notebooks", [])
            if nb.get("status") != "PASS"
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
    shas = {
        c.get("git_sha", "unknown")
        for c in configs
        if c.get("status") == "ok"
    }
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


def compute_eligibility(
    rollup: dict,
    run_base_dir: str,
    batch_purpose: str,
    notebook_gate_path: Optional[str] = None,
    expected_configs: Optional[set[str]] = None,
) -> BatchGate:
    """Run all eligibility checks. eligible=True only if ALL checks PASS."""
    batch_id = rollup.get("batch", {}).get("batch_id", "unknown")

    results = [
        check_config_membership(rollup, expected_configs),
        check_canonical_summaries(rollup, run_base_dir),
        check_notebook_gate(notebook_gate_path, batch_purpose),
        check_git_sha_consistency(rollup),
    ]

    eligible = all(r.status == "PASS" for r in results)

    return BatchGate(
        eligible=eligible,
        reasons=results,
        batch_id=batch_id,
        batch_purpose=batch_purpose,
        created_at_utc=utc_now_iso(),
    )
