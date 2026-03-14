#!/usr/bin/env python
"""
Rung orchestrator for Arc D v2 lineage.

Executes the 9-step rung runbook:
  0. Precondition check + verify artifacts
  1. Generate training dataset
  2. Train all roster models
  3. Offline eval + data sanity
  3b. Interpretability (SHAP, feature selection)
  4. H2H battery
  5. Comparator battery + CI extraction
  6. Generate canonical tables
  7. Generate charts + reports + manifest
  8. Advance check
  9. Narrative marker

CLI:
    uv run python scripts/internal/run_rung.py --rung r0 --mode smoke --dry-run
    uv run python scripts/internal/run_rung.py --rung r0 --mode quick --seeds 42
    uv run python scripts/internal/run_rung.py --rung r0 --mode all
    uv run python scripts/internal/run_rung.py --rung r0 --status
    uv run python scripts/internal/run_rung.py --rung r0 --rerun --from-step 2 --models gbt_av
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("run_rung")

# ---------------------------------------------------------------------------
# Constants — re-export from rung_state for backward compat
# ---------------------------------------------------------------------------

# Import step/DAG definitions from the state module (single source of truth)
from rung_state import (
    DAG_DOWNSTREAM,
    MODEL_SCOPED_STEPS,
    STEPS,
    RunState,
)

# Mode → seed contract
MODE_SEEDS: dict[str, list[int]] = {
    "smoke": [42],
    "quick": [42],
    "full": [42, 123, 456],
}

# Mode → n_deals for dataset generation
MODE_DEALS: dict[str, int] = {
    "smoke": 500,
    "quick": 2500,
    "full": 50000,
}

# Step descriptions for logging
STEP_DESCRIPTIONS: dict[str, str] = {
    "0": "Precondition check",
    "1": "Generate training dataset",
    "2": "Train roster models",
    "3": "Offline eval + data sanity",
    "3b": "Interpretability (SHAP)",
    "4": "H2H battery",
    "5": "Comparator battery + CI extraction",
    "6": "Generate canonical tables",
    "7": "Generate charts + reports + manifest",
    "8": "Advance check",
    "9": "Narrative marker",
}

# Scripts called by each step (for fingerprinting)
STEP_SCRIPTS: dict[str, list[str]] = {
    "0": [],
    "1": ["scripts/internal/generate_action_value_dataset.py"],
    "2": ["scripts/internal/train_action_value.py"],
    "3": ["scripts/internal/generate_rung_tables.py"],
    "3b": ["scripts/internal/generate_interpretability.py"],
    "4": ["scripts/internal/run_arc_d_h2h_battery.py"],
    "5": [
        "scripts/internal/run_auction_comparator.py",
        "scripts/internal/extract_comparator_cis.py",
    ],
    "6": ["scripts/internal/generate_rung_tables.py"],
    "7": [
        "scripts/internal/generate_rung_charts.py",
        "scripts/internal/generate_rung_report.py",
        "scripts/internal/generate_evidence_manifest.py",
    ],
    "8": ["scripts/internal/generate_advance_check.py"],
    "9": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Find the repo root (directory containing .git)."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / ".git").exists() or (p / ".git").is_file():
            return p
        p = p.parent
    return Path.cwd()


def _plans_dir(rung: str) -> Path:
    return _repo_root() / "plans" / "arc_d_v2" / rung


def _state_path(rung: str) -> Path:
    return _plans_dir(rung) / "state.json"


def _log_path(rung: str) -> Path:
    return _plans_dir(rung) / "execution_log.jsonl"


def _step_log_dir(rung: str) -> Path:
    d = _plans_dir(rung) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc_now_iso() -> str:
    from bid_euchre.core.time import utc_now_iso

    return utc_now_iso()


def _append_log(rung: str, event: dict) -> None:
    """Append a JSONL event to the execution log."""
    event.setdefault("ts", _utc_now_iso())
    log_path = _log_path(rung)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")


def _hash_file(path: Path) -> str | None:
    """SHA256 hash of a file, or None if missing."""
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _get_script_mtime(script_path: str) -> float | None:
    """Get mtime of a script, or None if missing."""
    p = _repo_root() / script_path
    if p.exists():
        return p.stat().st_mtime
    return None


def compute_fingerprint(
    step: str,
    model_name: str | None,
    seed: int,
    rung: str,
    mode: str,
    roster_path: Path | None = None,
    plan_path: Path | None = None,
) -> dict:
    """Lightweight provenance check to detect stale outputs."""
    fp: dict = {
        "seed": seed,
        "mode": mode,
        "step": step,
    }
    if model_name:
        fp["model"] = model_name
    if roster_path and roster_path.exists():
        fp["roster_hash"] = _hash_file(roster_path)
    if plan_path and plan_path.exists():
        fp["plan_sha"] = _hash_file(plan_path)
    scripts = STEP_SCRIPTS.get(step, [])
    for s in scripts:
        mtime = _get_script_mtime(s)
        if mtime is not None:
            fp[f"script_mtime_{Path(s).stem}"] = mtime
    return fp


def fingerprint_matches(state: RunState, step: str, seed: int, **kwargs) -> bool:
    """Check if current fingerprint matches the stored one."""
    stored = state.get_step_fingerprint(step, seed)
    if stored is None:
        return False
    current = compute_fingerprint(
        step=step,
        seed=seed,
        rung=state.rung,
        mode=state.mode,
        **kwargs,
    )
    # Compare relevant keys (ignore extra keys in stored)
    for key in ["seed", "mode", "step", "roster_hash", "plan_sha"]:
        if key in current and current[key] != stored.get(key):
            return False
    return True


# ---------------------------------------------------------------------------
# Roster loading
# ---------------------------------------------------------------------------


def load_roster(rung: str) -> dict:
    """Load lineage roster with optional rung overlay.

    Roster file: plans/arc_d_v2/roster.json (lineage-level)
    Overlay file: plans/arc_d_v2/<rung>/roster_overlay.json (optional)
    """
    roster_path = _repo_root() / "plans" / "arc_d_v2" / "roster.json"
    if not roster_path.exists():
        logger.warning("No lineage roster found at %s", roster_path)
        return {"models": {}}

    roster = json.loads(roster_path.read_text())

    overlay_path = _plans_dir(rung) / "roster_overlay.json"
    if overlay_path.exists():
        overlay = json.loads(overlay_path.read_text())
        for name in overlay.get("exclude", []):
            if name in roster.get("models", {}):
                roster["models"][name]["status"] = "excluded"
        for entry in overlay.get("add", []):
            name = entry.get("name", entry.get("id"))
            if name:
                roster["models"][name] = entry

    return roster


def get_trainable_models(roster: dict) -> list[dict]:
    """Get list of trainable models from roster."""
    models = []
    for name, spec in roster.get("models", {}).items():
        if spec.get("status") == "excluded":
            continue
        if spec.get("trainable", True):
            model = dict(spec)
            model["name"] = name
            models.append(model)
    return models


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


def run_subprocess(
    cmd: list[str],
    step: str,
    rung: str,
    detail: str = "",
    timeout: int | None = None,
) -> tuple[bool, str]:
    """Run a subprocess, capturing output to step log.

    Returns (success, error_message).
    """
    log_detail = detail or step
    log_file = _step_log_dir(rung) / f"step_{step}_{log_detail}.log"

    logger.info("Running: %s", " ".join(cmd))
    _append_log(
        rung,
        {"event": "subprocess_start", "step": step, "cmd": " ".join(cmd)},
    )

    start_time = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_repo_root()),
        )
        elapsed = time.monotonic() - start_time

        # Write combined output to log
        with open(log_file, "w") as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Exit code: {result.returncode}\n")
            f.write(f"Duration: {elapsed:.1f}s\n")
            f.write("--- STDOUT ---\n")
            f.write(result.stdout)
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)

        if result.returncode != 0:
            error = (
                result.stderr[-500:]
                if result.stderr
                else f"Exit code {result.returncode}"
            )
            _append_log(
                rung,
                {
                    "event": "subprocess_failed",
                    "step": step,
                    "exit_code": result.returncode,
                    "duration_s": round(elapsed, 1),
                    "error": error[:200],
                },
            )
            return False, error

        _append_log(
            rung,
            {
                "event": "subprocess_complete",
                "step": step,
                "duration_s": round(elapsed, 1),
            },
        )
        return True, ""

    except subprocess.TimeoutExpired:
        _append_log(
            rung,
            {"event": "subprocess_timeout", "step": step, "timeout": timeout},
        )
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        _append_log(
            rung,
            {"event": "subprocess_error", "step": step, "error": str(e)},
        )
        return False, str(e)


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def execute_step_0(state: RunState, dry_run: bool = False) -> bool:
    """Step 0: Precondition check — verify plan.md, hypotheses.json, checkpoints.md exist."""
    rung = state.rung
    plan_dir = _plans_dir(rung)
    required_files = {
        "plan.md": plan_dir / "plan.md",
        "hypotheses.json": plan_dir / "hypotheses.json",
    }
    optional_files = {
        "checkpoints.md": plan_dir / "checkpoints.md",
    }

    _append_log(rung, {"event": "step_start", "step": "0"})
    state.mark_step_started("0")

    missing = []
    for label, path in required_files.items():
        if not path.exists():
            missing.append(label)
            logger.error("Missing required file: %s", path)
        else:
            logger.info("Found: %s", path)

    for label, path in optional_files.items():
        if not path.exists():
            logger.warning("Optional file missing: %s (will create stub)", path)
        else:
            logger.info("Found: %s", path)

    # Validate hypotheses.json schema
    hyp_path = required_files["hypotheses.json"]
    if hyp_path.exists():
        try:
            hyp = json.loads(hyp_path.read_text())
            if "hypotheses" not in hyp:
                logger.error("hypotheses.json missing 'hypotheses' key")
                missing.append("hypotheses.json (invalid schema)")
            else:
                logger.info(
                    "hypotheses.json: %d hypotheses loaded",
                    len(hyp["hypotheses"]),
                )
        except json.JSONDecodeError as e:
            logger.error("hypotheses.json parse error: %s", e)
            missing.append("hypotheses.json (parse error)")

    if missing:
        error = f"Missing: {', '.join(missing)}"
        state.mark_step_failed("0", error, retryable=False)
        _append_log(rung, {"event": "step_failed", "step": "0", "error": error})
        return False

    if dry_run:
        logger.info("Step 0: dry-run passed — all preconditions met")
        state.mark_step_complete("0")
        _append_log(rung, {"event": "step_complete", "step": "0", "dry_run": True})
        return True

    state.mark_step_complete("0")
    _append_log(rung, {"event": "step_complete", "step": "0"})
    return True


def execute_step_1(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 1: Generate training dataset."""
    rung = state.rung
    mode = state.mode.upper()
    n_deals = MODE_DEALS.get(state.mode, 500)

    _append_log(rung, {"event": "step_start", "step": "1", "seed": seed})
    state.mark_step_started("1", seed)

    # Check for continuation artifact
    continuation = (
        _repo_root()
        / "data"
        / "artifacts"
        / "arc_d"
        / rung
        / f"hybrid_{rung}_full.json"
    )
    if not continuation.exists():
        # Try common alternative paths
        alt = (
            _repo_root() / "data" / "artifacts" / "arc_d" / "r0" / "hybrid_r0_full.json"
        )
        if alt.exists():
            continuation = alt
        else:
            logger.warning("No continuation artifact found at %s", continuation)

    output_dir = _repo_root() / "data" / "runs" / f"av_{rung}_{state.mode}_{seed}"

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/internal/generate_action_value_dataset.py",
        "--seed",
        str(seed),
        "--n-deals",
        str(n_deals),
        "--mode",
        mode,
        "--output-dir",
        str(output_dir),
    ]
    if continuation.exists():
        cmd.extend(["--continuation-artifact", str(continuation)])

    if dry_run:
        logger.info("Step 1: would run: %s", " ".join(cmd))
        state.mark_step_complete("1", seed)
        return True

    ok, error = run_subprocess(cmd, "1", rung, f"seed_{seed}")
    if ok:
        state.mark_step_complete(
            "1",
            seed,
            fingerprint=compute_fingerprint("1", None, seed, rung, state.mode),
        )
        _append_log(rung, {"event": "step_complete", "step": "1", "seed": seed})
    else:
        state.mark_step_failed("1", error, seed=seed)
        _append_log(
            rung,
            {"event": "step_failed", "step": "1", "seed": seed, "error": error[:200]},
        )
    state.save(_state_path(rung))
    return ok


def execute_step_2(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 2: Train all roster models for one seed."""
    rung = state.rung
    roster = load_roster(rung)
    trainable = get_trainable_models(roster)

    _append_log(rung, {"event": "step_start", "step": "2", "seed": seed})
    state.mark_step_started("2", seed)

    if not trainable:
        logger.warning("No trainable models in roster")
        state.mark_step_complete("2", seed)
        return True

    dataset_dir = _repo_root() / "data" / "runs" / f"av_{rung}_{state.mode}_{seed}"
    dataset_path = dataset_dir / "datasets" / "action_value.parquet"

    all_ok = True
    for model in trainable:
        model_name = model["name"]

        # Idempotency: skip if already complete with matching fingerprint
        if state.model_status(seed, "2", model_name) == "complete":
            if fingerprint_matches(
                state,
                "2",
                seed,
                model_name=model_name,
                roster_path=_repo_root() / "plans" / "arc_d_v2" / "roster.json",
            ):
                logger.info(
                    "Step 2: %s seed=%d already complete, skipping", model_name, seed
                )
                continue

        state.update_model("2", model_name, seed, "running")

        output_dir = (
            _repo_root()
            / "data"
            / "runs"
            / f"av_{model_name}_{rung}_{state.mode}_{seed}"
        )

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/internal/train_action_value.py",
            "--seed",
            str(seed),
            "--dataset",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
        ]

        # Add model-class if specified
        model_class = model.get("model_class", "ols")
        if model_class != "ols":
            cmd.extend(["--model-class", model_class])

        # Add feature-set if specified
        feature_set = model.get("feature_set", "full")
        if feature_set != "full":
            cmd.extend(["--feature-set", feature_set])

        # Add continuation artifact if specified
        continuation = model.get("continuation_artifact")
        if continuation:
            cmd.extend(["--continuation-artifact", str(_repo_root() / continuation)])

        if dry_run:
            logger.info("Step 2: would train %s: %s", model_name, " ".join(cmd))
            state.update_model("2", model_name, seed, "complete")
            continue

        _append_log(
            rung,
            {"event": "step_start", "step": "2", "seed": seed, "model": model_name},
        )
        ok, error = run_subprocess(cmd, "2", rung, f"{model_name}_seed_{seed}")

        if ok:
            state.update_model("2", model_name, seed, "complete")
            _append_log(
                rung,
                {
                    "event": "step_complete",
                    "step": "2",
                    "seed": seed,
                    "model": model_name,
                },
            )
        else:
            state.update_model("2", model_name, seed, "failed", error=error[:200])
            _append_log(
                rung,
                {
                    "event": "step_failed",
                    "step": "2",
                    "seed": seed,
                    "model": model_name,
                    "error": error[:200],
                    "retryable": True,
                },
            )
            all_ok = False
            break  # Stop on blocking failure

        state.save(_state_path(rung))

    if all_ok:
        state.mark_step_complete(
            "2",
            seed,
            fingerprint=compute_fingerprint("2", None, seed, rung, state.mode),
        )
    state.save(_state_path(rung))
    return all_ok


def execute_step_3(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 3: Offline eval + data sanity (generate_rung_tables.py for model_performance, data_sanity)."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "3", "seed": seed})
    state.mark_step_started("3", seed)

    # PR 3a dependency: generate_rung_tables.py
    script = _repo_root() / "scripts" / "internal" / "generate_rung_tables.py"
    if not script.exists():
        logger.warning(
            "Step 3: generate_rung_tables.py not found (PR 3a dependency). Skipping."
        )
        state.mark_step_skipped(
            "3", "generate_rung_tables.py not found (PR 3a dependency)"
        )
        _append_log(
            rung, {"event": "step_skipped", "step": "3", "reason": "PR 3a dependency"}
        )
        return True

    output_dir = (
        _plans_dir(rung).parent.parent.parent
        / "docs"
        / "04_reports"
        / "arc_d_v2"
        / rung
        / "canonical"
        / "tables"
    )
    cmd = [
        "uv",
        "run",
        "python",
        str(script),
        "--rung",
        rung,
        "--mode",
        state.mode,
        "--seed",
        str(seed),
        "--output-dir",
        str(output_dir),
        "--tables",
        "model_performance,data_sanity",
    ]

    if dry_run:
        logger.info("Step 3: would run: %s", " ".join(cmd))
        state.mark_step_complete("3", seed)
        return True

    ok, error = run_subprocess(cmd, "3", rung, f"seed_{seed}")
    if ok:
        state.mark_step_complete("3", seed)
        _append_log(rung, {"event": "step_complete", "step": "3", "seed": seed})
    else:
        state.mark_step_failed("3", error, seed=seed)
        _append_log(
            rung,
            {"event": "step_failed", "step": "3", "seed": seed, "error": error[:200]},
        )
    state.save(_state_path(rung))
    return ok


def execute_step_3b(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 3b: Interpretability (SHAP, feature selection). Graceful skip if script missing."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "3b", "seed": seed})
    state.mark_step_started("3b", seed)

    script = _repo_root() / "scripts" / "internal" / "generate_interpretability.py"
    if not script.exists():
        logger.warning(
            "Step 3b: generate_interpretability.py not found (PR 3b dependency). Skipping."
        )
        state.mark_step_skipped(
            "3b", "generate_interpretability.py not found (PR 3b dependency)"
        )
        _append_log(
            rung, {"event": "step_skipped", "step": "3b", "reason": "PR 3b dependency"}
        )
        return True

    cmd = [
        "uv",
        "run",
        "python",
        str(script),
        "--rung",
        rung,
        "--mode",
        state.mode,
        "--seed",
        str(seed),
    ]

    if dry_run:
        logger.info("Step 3b: would run: %s", " ".join(cmd))
        state.mark_step_complete("3b", seed)
        return True

    ok, error = run_subprocess(cmd, "3b", rung, f"seed_{seed}")
    if ok:
        state.mark_step_complete("3b", seed)
        _append_log(rung, {"event": "step_complete", "step": "3b", "seed": seed})
    else:
        state.mark_step_failed("3b", error, seed=seed)
        _append_log(
            rung,
            {"event": "step_failed", "step": "3b", "seed": seed, "error": error[:200]},
        )
    state.save(_state_path(rung))
    return ok


def execute_step_4(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 4: H2H battery."""
    rung = state.rung
    mode = state.mode.upper()

    _append_log(rung, {"event": "step_start", "step": "4", "seed": seed})
    state.mark_step_started("4", seed)

    n_per = {"smoke": 100, "quick": 2000, "full": 10000}.get(state.mode, 100)
    output = (
        _repo_root()
        / "data"
        / "artifacts"
        / "arc_d_v2"
        / rung
        / f"h2h_battery_{state.mode}_{seed}.json"
    )

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/internal/run_arc_d_h2h_battery.py",
        "--mode",
        mode,
        "--seed",
        str(seed),
        "--n-per",
        str(n_per),
        "--output",
        str(output),
    ]

    if dry_run:
        logger.info("Step 4: would run: %s", " ".join(cmd))
        state.mark_step_complete("4", seed)
        return True

    ok, error = run_subprocess(cmd, "4", rung, f"seed_{seed}")
    if ok:
        state.mark_step_complete("4", seed)
        _append_log(rung, {"event": "step_complete", "step": "4", "seed": seed})
    else:
        state.mark_step_failed("4", error, seed=seed)
        _append_log(
            rung,
            {"event": "step_failed", "step": "4", "seed": seed, "error": error[:200]},
        )
    state.save(_state_path(rung))
    return ok


def execute_step_5(state: RunState, seed: int, dry_run: bool = False) -> bool:
    """Step 5: Comparator battery + CI extraction."""
    rung = state.rung
    mode = state.mode.upper()

    _append_log(rung, {"event": "step_start", "step": "5", "seed": seed})
    state.mark_step_started("5", seed)

    artifacts_dir = _repo_root() / "data" / "artifacts" / "arc_d_v2" / rung
    runs_dir = _repo_root() / "data" / "runs"

    # Step 5a: Run comparator
    cmd_comparator = [
        "uv",
        "run",
        "python",
        "scripts/internal/run_auction_comparator.py",
        "--mode",
        mode,
        "--seed",
        str(seed),
    ]

    if dry_run:
        logger.info("Step 5: would run comparator: %s", " ".join(cmd_comparator))
        logger.info("Step 5: would run CI extraction")
        state.mark_step_complete("5", seed)
        return True

    ok, error = run_subprocess(cmd_comparator, "5", rung, f"comparator_seed_{seed}")
    if not ok:
        state.mark_step_failed("5", f"Comparator failed: {error}", seed=seed)
        return False

    # Step 5b: Extract CIs
    cmd_cis = [
        "uv",
        "run",
        "python",
        "scripts/internal/extract_comparator_cis.py",
        "--artifacts-dir",
        str(artifacts_dir),
        "--runs-dir",
        str(runs_dir),
        "--seed",
        str(seed),
        "--n-bootstrap",
        "10000",
        "--output",
        str(artifacts_dir / f"comparator_cis_{rung}_{seed}.json"),
    ]

    ok, error = run_subprocess(cmd_cis, "5", rung, f"cis_seed_{seed}")
    if ok:
        state.mark_step_complete("5", seed)
        _append_log(rung, {"event": "step_complete", "step": "5", "seed": seed})
    else:
        state.mark_step_failed("5", f"CI extraction failed: {error}", seed=seed)
        _append_log(
            rung,
            {"event": "step_failed", "step": "5", "seed": seed, "error": error[:200]},
        )
    state.save(_state_path(rung))
    return ok


def execute_step_6(state: RunState, dry_run: bool = False) -> bool:
    """Step 6: Generate canonical tables (aggregates across seeds for FULL)."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "6"})
    state.mark_step_started("6")

    script = _repo_root() / "scripts" / "internal" / "generate_rung_tables.py"
    if not script.exists():
        logger.warning(
            "Step 6: generate_rung_tables.py not found (PR 3a dependency). Skipping."
        )
        state.mark_step_skipped(
            "6", "generate_rung_tables.py not found (PR 3a dependency)"
        )
        return True

    output_dir = (
        _repo_root()
        / "docs"
        / "04_reports"
        / "arc_d_v2"
        / rung
        / "canonical"
        / "tables"
    )
    seeds_str = ",".join(str(s) for s in state.seeds)

    cmd = [
        "uv",
        "run",
        "python",
        str(script),
        "--rung",
        rung,
        "--mode",
        state.mode,
        "--seeds",
        seeds_str,
        "--output-dir",
        str(output_dir),
    ]

    if dry_run:
        logger.info("Step 6: would run: %s", " ".join(cmd))
        state.mark_step_complete("6")
        return True

    ok, error = run_subprocess(cmd, "6", rung)
    if ok:
        state.mark_step_complete("6")
        _append_log(rung, {"event": "step_complete", "step": "6"})
    else:
        state.mark_step_failed("6", error)
        _append_log(rung, {"event": "step_failed", "step": "6", "error": error[:200]})
    state.save(_state_path(rung))
    return ok


def execute_step_7(state: RunState, dry_run: bool = False) -> bool:
    """Step 7: Generate charts + reports + manifest."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "7"})
    state.mark_step_started("7")

    report_dir = _repo_root() / "docs" / "04_reports" / "arc_d_v2" / rung / "canonical"

    # 7a: Charts (existing script)
    chart_script = _repo_root() / "scripts" / "internal" / "generate_rung_charts.py"
    if chart_script.exists():
        cmd = [
            "uv",
            "run",
            "python",
            str(chart_script),
            "--rung",
            rung,
            "--output-dir",
            str(report_dir / "charts"),
        ]
        if not dry_run:
            ok, error = run_subprocess(cmd, "7", rung, "charts")
            if not ok:
                logger.warning("Chart generation failed: %s", error[:200])
        else:
            logger.info("Step 7: would run charts: %s", " ".join(cmd))
    else:
        logger.warning("Step 7: generate_rung_charts.py may need --eval-dir (PR 3a)")

    # 7b: Report generation (PR 3a dependency)
    report_script = _repo_root() / "scripts" / "internal" / "generate_rung_report.py"
    if report_script.exists():
        cmd = [
            "uv",
            "run",
            "python",
            str(report_script),
            "--rung",
            rung,
            "--mode",
            state.mode,
            "--output-dir",
            str(report_dir),
        ]
        if not dry_run:
            ok, error = run_subprocess(cmd, "7", rung, "report")
            if not ok:
                logger.warning("Report generation failed: %s", error[:200])
        else:
            logger.info("Step 7: would run report: %s", " ".join(cmd))
    else:
        logger.warning("Step 7: generate_rung_report.py not found (PR 3a dependency)")

    # 7c: Evidence manifest (PR 3a dependency)
    manifest_script = (
        _repo_root() / "scripts" / "internal" / "generate_evidence_manifest.py"
    )
    if manifest_script.exists():
        cmd = [
            "uv",
            "run",
            "python",
            str(manifest_script),
            "--rung",
            rung,
            "--output",
            str(report_dir / ".." / "evidence_manifest.json"),
        ]
        if not dry_run:
            ok, error = run_subprocess(cmd, "7", rung, "manifest")
            if not ok:
                logger.warning("Manifest generation failed: %s", error[:200])
        else:
            logger.info("Step 7: would run manifest: %s", " ".join(cmd))
    else:
        logger.warning(
            "Step 7: generate_evidence_manifest.py not found (PR 3a dependency)"
        )

    state.mark_step_complete("7")
    _append_log(rung, {"event": "step_complete", "step": "7"})
    state.save(_state_path(rung))
    return True


def execute_step_8(state: RunState, dry_run: bool = False) -> bool:
    """Step 8: Advance check — complete machine decision boundary."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "8"})
    state.mark_step_started("8")

    hyp_path = _plans_dir(rung) / "hypotheses.json"
    tables_dir = (
        _repo_root()
        / "docs"
        / "04_reports"
        / "arc_d_v2"
        / rung
        / "canonical"
        / "tables"
    )
    output = _plans_dir(rung) / "advance_check.json"

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/internal/generate_advance_check.py",
        "--hypotheses",
        str(hyp_path),
        "--tables-dir",
        str(tables_dir),
        "--output",
        str(output),
        "--mode",
        state.mode,
        "--rung",
        rung,
    ]

    if dry_run:
        logger.info("Step 8: would run: %s", " ".join(cmd))
        state.mark_step_complete("8")
        return True

    ok, error = run_subprocess(cmd, "8", rung)
    if ok:
        state.mark_step_complete("8")
        _append_log(rung, {"event": "step_complete", "step": "8"})
    else:
        state.mark_step_failed("8", error)
        _append_log(rung, {"event": "step_failed", "step": "8", "error": error[:200]})
    state.save(_state_path(rung))
    return ok


def execute_step_9(state: RunState, dry_run: bool = False) -> bool:
    """Step 9: Narrative marker — check if 02_decision.md exists."""
    rung = state.rung

    _append_log(rung, {"event": "step_start", "step": "9"})
    state.mark_step_started("9")

    decision_path = (
        _repo_root()
        / "docs"
        / "04_reports"
        / "arc_d_v2"
        / rung
        / "canonical"
        / "04_rung_decision.md"
    )

    if decision_path.exists():
        logger.info("Step 9: Decision report found at %s", decision_path)
        state.mark_step_complete("9")
        _append_log(rung, {"event": "step_complete", "step": "9", "status": "complete"})
    else:
        logger.info(
            "Step 9: Decision report not yet written at %s — marking pending",
            decision_path,
        )
        state.mark_step_skipped(
            "9", "04_rung_decision.md not yet written (narrative pending)"
        )
        _append_log(
            rung, {"event": "step_complete", "step": "9", "status": "pending_narrative"}
        )

    state.save(_state_path(rung))
    return True


# ---------------------------------------------------------------------------
# Step dispatch
# ---------------------------------------------------------------------------

# Steps that are per-seed (run once per seed)
PER_SEED_STEPS = {"1", "2", "3", "3b", "4", "5"}

# Steps that are holistic (run once, aggregate across seeds)
HOLISTIC_STEPS = {"0", "6", "7", "8", "9"}

STEP_FUNCTIONS = {
    "0": execute_step_0,
    "1": execute_step_1,
    "2": execute_step_2,
    "3": execute_step_3,
    "3b": execute_step_3b,
    "4": execute_step_4,
    "5": execute_step_5,
    "6": execute_step_6,
    "7": execute_step_7,
    "8": execute_step_8,
    "9": execute_step_9,
}


def run_step(state: RunState, step: str, dry_run: bool = False) -> bool:
    """Execute a single step, handling per-seed vs holistic dispatch."""
    desc = STEP_DESCRIPTIONS.get(step, step)
    logger.info("=== Step %s: %s ===", step, desc)

    if step in PER_SEED_STEPS:
        # Run for each seed
        for seed in state.seeds:
            if state.step_is_complete(step, seed):
                logger.info("Step %s seed=%d already complete, skipping", step, seed)
                continue
            fn = STEP_FUNCTIONS[step]
            ok = fn(state, seed, dry_run=dry_run)
            if not ok:
                return False
        # Mark aggregate as complete
        if not dry_run:
            state.mark_step_complete(step)
            state.save(_state_path(state.rung))
        return True
    else:
        # Holistic steps
        fn = STEP_FUNCTIONS[step]
        if step == "0":
            return fn(state, dry_run=dry_run)
        return fn(state, dry_run=dry_run)


def run_steps(
    state: RunState,
    from_step: str | None = None,
    to_step: str | None = None,
    single_step: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Run a range of steps."""
    if single_step:
        return run_step(state, single_step, dry_run)

    start_idx = STEPS.index(from_step) if from_step else 0
    end_idx = STEPS.index(to_step) + 1 if to_step else len(STEPS)

    for step in STEPS[start_idx:end_idx]:
        # Skip completed steps (idempotency)
        if state.step_is_complete(step) and not dry_run:
            logger.info("Step %s already complete, skipping", step)
            continue

        ok = run_step(state, step, dry_run)
        if not ok:
            logger.error("Step %s failed, stopping", step)
            return False

    return True


# ---------------------------------------------------------------------------
# Rerun logic
# ---------------------------------------------------------------------------


def handle_rerun(
    state: RunState,
    from_step: str,
    models: list[str] | None = None,
) -> None:
    """Reset a step and all its downstream dependencies for rerun.

    Lifecycle integration point: when full lifecycle management is wired up,
    this function should additionally:
      1. Call ``lifecycle.generate_run_id()`` to create a new run ID
      2. Call ``lifecycle.supersede_run()`` to mark the old run and create
         a rerun manifest linking old -> new
      3. Record affected_models and affected_steps on the RerunManifest
    See ``bid_euchre.arc_d_v2.lifecycle`` for the API.
    """
    affected = [from_step] + DAG_DOWNSTREAM[from_step]
    logger.info("Rerun from step %s: resetting steps %s", from_step, affected)

    for step in affected:
        if models and step in MODEL_SCOPED_STEPS:
            for model in models:
                logger.info("  Resetting model %s in step %s", model, step)
                state.reset_model(step, model)
        else:
            logger.info("  Resetting step %s (holistic)", step)
            state.reset_step(step)

    state.supersession = {
        "from_step": from_step,
        "models": models,
        "timestamp": _utc_now_iso(),
    }
    state.save(_state_path(state.rung))


# ---------------------------------------------------------------------------
# Mode=all: QUICK -> FULL pipeline
# ---------------------------------------------------------------------------


def run_all(state: RunState, dry_run: bool = False) -> bool:
    """Run QUICK -> FULL pipeline with advance check gate."""
    rung = state.rung

    # Phase 1: QUICK
    logger.info("=== PHASE 1: QUICK ===")
    state.mode = "quick"
    state.seeds = MODE_SEEDS["quick"]
    state.reset_for_mode("quick", state.seeds)
    state.save(_state_path(rung))

    ok = run_steps(state, dry_run=dry_run)
    if not ok:
        return False

    # Check advance result
    advance_path = _plans_dir(rung) / "advance_check.json"
    if advance_path.exists() and not dry_run:
        advance = json.loads(advance_path.read_text())
        decision = advance.get("advance_decision", "UNKNOWN")
        if decision not in ("PROCEED", "INVESTIGATE"):
            state.blocker = f"QUICK advance check: {decision}"
            state.save(_state_path(rung))
            logger.error("QUICK advance check failed: %s", decision)
            return False
        logger.info("QUICK advance check: %s", decision)

    # Phase 2: FULL
    logger.info("=== PHASE 2: FULL ===")
    state.reset_for_mode("full", MODE_SEEDS["full"])
    state.save(_state_path(rung))

    ok = run_steps(state, dry_run=dry_run)
    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_status(rung: str) -> None:
    """Print current state for a rung."""
    state_path = _state_path(rung)
    if state_path.exists():
        state = RunState.load(state_path)
        print(state.summary())
    else:
        print(f"No state file found for rung {rung}.")
        print(f"Expected at: {state_path}")
        print("Creating fresh state...")
        state = RunState.create_fresh(rung, "smoke", [42])
        state.save(state_path)
        print(state.summary())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rung orchestrator for Arc D v2 lineage"
    )
    parser.add_argument(
        "--rung",
        required=True,
        choices=["r0", "r1", "r2", "r3"],
        help="Rung to execute",
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick", "full", "all"],
        default="smoke",
        help="Execution mode (default: smoke)",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated seeds (default: per-mode contract)",
    )
    parser.add_argument(
        "--step",
        type=str,
        default=None,
        help="Run only this step",
    )
    parser.add_argument(
        "--from-step",
        type=str,
        default=None,
        help="Resume from this step",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Rerun mode: reset from-step and downstream",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model names for scoped rerun",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print current state and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check preconditions without executing",
    )

    args = parser.parse_args(argv)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Status mode
    if args.status:
        print_status(args.rung)
        return 0

    # Parse seeds
    if args.seeds:
        seeds = [int(s.strip()) for s in args.seeds.split(",")]
    elif args.mode == "all":
        seeds = MODE_SEEDS["quick"]  # Start with QUICK seeds
    else:
        seeds = MODE_SEEDS.get(args.mode, [42])

    # Load or create state
    state_path = _state_path(args.rung)
    if state_path.exists():
        state = RunState.load(state_path)
        # Update mode/seeds if different
        if state.mode != args.mode and args.mode != "all":
            logger.info("Mode changed from %s to %s", state.mode, args.mode)
            state.mode = args.mode
            state.seeds = seeds
    else:
        mode = args.mode if args.mode != "all" else "quick"
        state = RunState.create_fresh(args.rung, mode, seeds)
        state.save(state_path)

    # Rerun mode
    if args.rerun:
        if not args.from_step:
            logger.error("--rerun requires --from-step")
            return 1
        if args.from_step not in STEPS:
            logger.error("Invalid step: %s (valid: %s)", args.from_step, STEPS)
            return 1
        models = args.models.split(",") if args.models else None
        handle_rerun(state, args.from_step, models)
        logger.info("Rerun state reset complete. Re-run without --rerun to execute.")
        return 0

    # Validate step args
    if args.step and args.step not in STEPS:
        logger.error("Invalid step: %s (valid: %s)", args.step, STEPS)
        return 1
    if args.from_step and args.from_step not in STEPS:
        logger.error("Invalid step: %s (valid: %s)", args.from_step, STEPS)
        return 1

    # Execute
    if args.mode == "all":
        ok = run_all(state, dry_run=args.dry_run)
    else:
        ok = run_steps(
            state,
            from_step=args.from_step,
            single_step=args.step,
            dry_run=args.dry_run,
        )

    state.save(state_path)

    if ok:
        logger.info("Run complete.")
        return 0
    else:
        logger.error("Run failed. Check state: --rung %s --status", args.rung)
        return 1


if __name__ == "__main__":
    sys.exit(main())
