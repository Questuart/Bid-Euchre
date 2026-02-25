"""Bundle validation for Arc D rung bundles (arc_d_rung_bundle_v1).

Validates bundle JSON schema, file existence, and artifact hash integrity.
Bundle validation runs BEFORE Tier 1 checks in the promotion gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BUNDLE_SCHEMA = "arc_d_rung_bundle_v1"

REQUIRED_TOP_LEVEL_KEYS = {
    "bundle_schema",
    "rung_id",
    "arc",
    "timestamp",
    "olsa",
    "olsa_full",
    "incumbent",
    "split_manifest",
}

REQUIRED_ARM_KEYS = {
    "artifact_path",
    "artifact_sha256",
    "eval_seed42",
    "eval_seed43",
    "eval_seed44",
}

REQUIRED_INCUMBENT_KEYS = {
    "artifact_path",
    "rung_id",
}

VALID_RUNG_IDS = {f"r{i}" for i in range(6)}

# Keys required for R1+ bundles (not required for R0)
REQUIRED_R1_PLUS_KEYS = {
    "h2h_summary",
    "h2h_challenger_vs_incumbent",
    "gate_thresholds",
}

# Required sub-keys for h2h_challenger_vs_incumbent inline data
REQUIRED_H2H_INLINE_KEYS = {
    "challenger",
    "incumbent",
    "net_eppd_delta",
    "ci_low",
    "ci_high",
    "n_deals",
    "ci_method",
    "seat_directions",
}


def validate_bundle(bundle: dict) -> tuple[bool, list[str]]:
    """Validate arc_d_rung_bundle_v1 schema.

    Args:
        bundle: Loaded bundle JSON dict.

    Returns:
        (valid, errors) where valid is True if no errors found.
    """
    errors: list[str] = []

    # Check schema version
    schema = bundle.get("bundle_schema")
    if schema != BUNDLE_SCHEMA:
        errors.append(f"bundle_schema must be '{BUNDLE_SCHEMA}', got '{schema}'")

    # Check required top-level keys
    missing_top = REQUIRED_TOP_LEVEL_KEYS - set(bundle.keys())
    if missing_top:
        errors.append(f"Missing required top-level keys: {sorted(missing_top)}")

    # Check rung_id
    rung_id = bundle.get("rung_id")
    if rung_id is not None and rung_id not in VALID_RUNG_IDS:
        errors.append(
            f"rung_id must be one of {sorted(VALID_RUNG_IDS)}, got '{rung_id}'"
        )

    # Check timestamp format (ISO 8601 with Z suffix)
    timestamp = bundle.get("timestamp")
    if timestamp is not None:
        if not isinstance(timestamp, str) or not re.match(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", timestamp
        ):
            errors.append(
                f"timestamp must be ISO-8601 with Z suffix, got '{timestamp}'"
            )

    # Check arm sections
    for arm_name in ("olsa", "olsa_full"):
        arm = bundle.get(arm_name)
        if arm is None:
            continue  # Already caught by missing top-level keys
        if not isinstance(arm, dict):
            errors.append(f"{arm_name} must be a dict")
            continue
        missing_arm = REQUIRED_ARM_KEYS - set(arm.keys())
        if missing_arm:
            errors.append(f"{arm_name} missing required keys: {sorted(missing_arm)}")

    # Check incumbent section
    incumbent = bundle.get("incumbent")
    if incumbent is not None:
        if not isinstance(incumbent, dict):
            errors.append("incumbent must be a dict")
        else:
            missing_inc = REQUIRED_INCUMBENT_KEYS - set(incumbent.keys())
            if missing_inc:
                errors.append(f"incumbent missing required keys: {sorted(missing_inc)}")

    # Check optional comparator keys (type validation only — presence is optional)
    for comp_key in ("comparator_battery", "comparator_eval"):
        comp_val = bundle.get(comp_key)
        if comp_val is not None and not isinstance(comp_val, str):
            errors.append(
                f"{comp_key} must be a string path or null, got {type(comp_val).__name__}"
            )

    # R1+ required keys (not required for R0)
    if rung_id is not None and rung_id != "r0":
        missing_r1 = REQUIRED_R1_PLUS_KEYS - set(bundle.keys())
        if missing_r1:
            errors.append(f"R1+ bundle missing required keys: {sorted(missing_r1)}")

        # Enforce non-null values for R1+ required keys
        for r1_key in REQUIRED_R1_PLUS_KEYS:
            if r1_key in bundle and bundle[r1_key] is None:
                errors.append(f"R1+ key '{r1_key}' must not be null")

        # Type-validate h2h_challenger_vs_incumbent as dict with required sub-keys
        h2h_inline = bundle.get("h2h_challenger_vs_incumbent")
        if h2h_inline is not None:
            if not isinstance(h2h_inline, dict):
                errors.append(
                    f"h2h_challenger_vs_incumbent must be a dict, "
                    f"got {type(h2h_inline).__name__}"
                )
            else:
                missing_h2h = REQUIRED_H2H_INLINE_KEYS - set(h2h_inline.keys())
                if missing_h2h:
                    errors.append(
                        f"h2h_challenger_vs_incumbent missing required keys: "
                        f"{sorted(missing_h2h)}"
                    )

        # Type-validate h2h_summary and gate_thresholds as strings (paths)
        for path_key in ("h2h_summary", "gate_thresholds"):
            path_val = bundle.get(path_key)
            if path_val is not None and not isinstance(path_val, str):
                errors.append(
                    f"{path_key} must be a string path, got {type(path_val).__name__}"
                )

    return (len(errors) == 0, errors)


def validate_bundle_files_exist(bundle: dict, base_dir: str) -> tuple[bool, list[str]]:
    """Check that all file paths referenced in the bundle exist on disk.

    Args:
        bundle: Validated bundle dict.
        base_dir: Base directory to resolve relative paths against.

    Returns:
        (valid, errors) where valid is True if all files exist.
    """
    errors: list[str] = []
    base = Path(base_dir)

    # Collect all file paths from bundle
    file_paths: list[str] = []

    for arm_name in ("olsa", "olsa_full"):
        arm = bundle.get(arm_name, {})
        for key in ("artifact_path", "eval_seed42", "eval_seed43", "eval_seed44"):
            path = arm.get(key)
            if path:
                file_paths.append(path)
        for key in ("semantic_gate_val", "semantic_gate_test", "feature_selection_log"):
            path = arm.get(key)
            if path:
                file_paths.append(path)

    incumbent = bundle.get("incumbent", {})
    inc_path = incumbent.get("artifact_path")
    if inc_path:
        file_paths.append(inc_path)

    split_manifest = bundle.get("split_manifest")
    if split_manifest:
        file_paths.append(split_manifest)

    training_report = bundle.get("training_report")
    if training_report:
        file_paths.append(training_report)

    control = bundle.get("control", {})
    control_path = control.get("artifact_path") if isinstance(control, dict) else None
    if control_path:
        file_paths.append(control_path)

    for comp_key in ("comparator_battery", "comparator_eval"):
        comp_path = bundle.get(comp_key)
        if comp_path:
            file_paths.append(comp_path)

    # R1+ path keys (h2h_summary, gate_thresholds are paths; h2h_challenger_vs_incumbent is inline)
    for h2h_key in ("h2h_summary", "gate_thresholds"):
        h2h_path = bundle.get(h2h_key)
        if h2h_path and isinstance(h2h_path, str):
            file_paths.append(h2h_path)

    for fp in file_paths:
        full_path = base / fp
        if not full_path.exists():
            errors.append(f"File not found: {fp}")

    return (len(errors) == 0, errors)


def validate_bundle_hashes(bundle: dict, base_dir: str) -> tuple[bool, list[str]]:
    """Verify artifact_sha256 fields match actual file content hashes.

    Args:
        bundle: Validated bundle dict.
        base_dir: Base directory to resolve relative paths against.

    Returns:
        (valid, errors) where valid is True if all hashes match.
    """
    errors: list[str] = []
    base = Path(base_dir)

    for arm_name in ("olsa", "olsa_full"):
        arm = bundle.get(arm_name, {})
        artifact_path = arm.get("artifact_path")
        expected_sha = arm.get("artifact_sha256")
        if not artifact_path or not expected_sha:
            continue

        full_path = base / artifact_path
        if not full_path.exists():
            errors.append(
                f"{arm_name} artifact not found for hash check: {artifact_path}"
            )
            continue

        try:
            with open(full_path) as f:
                metadata = json.load(f)
            # Compute content hash the same way freeze.py does:
            # exclude frozen_at and artifact_sha256, then SHA256 the
            # deterministic JSON serialization.
            content = {
                k: v
                for k, v in metadata.items()
                if k not in ("frozen_at", "artifact_sha256")
            }
            canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
            actual_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if actual_sha != expected_sha:
                errors.append(
                    f"{arm_name} artifact_sha256 mismatch: "
                    f"expected {expected_sha[:12]}..., got {actual_sha[:12]}..."
                )
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{arm_name} artifact hash check failed: {e}")

    return (len(errors) == 0, errors)


def load_and_validate_bundle(
    bundle_path: str, check_files: bool = False, base_dir: str | None = None
) -> tuple[dict, bool, list[str]]:
    """Load a bundle JSON file and validate its schema.

    Args:
        bundle_path: Path to the bundle JSON file.
        check_files: If True, also check that referenced files exist.
        base_dir: Base directory for file existence checks.
            Defaults to parent of bundle_path's parent directory.

    Returns:
        (bundle_dict, valid, errors).
    """
    path = Path(bundle_path)
    if not path.exists():
        return ({}, False, [f"Bundle file not found: {bundle_path}"])

    try:
        with open(path) as f:
            bundle = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return ({}, False, [f"Failed to read bundle: {e}"])

    valid, errors = validate_bundle(bundle)

    if valid and check_files:
        resolved_base = base_dir or str(path.parent.parent.parent)
        files_valid, file_errors = validate_bundle_files_exist(bundle, resolved_base)
        if not files_valid:
            valid = False
            errors.extend(file_errors)

    return (bundle, valid, errors)
