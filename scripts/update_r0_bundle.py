#!/usr/bin/env python
"""Update an R0 rung bundle with eval result paths.

After training (PR-R0a) writes the rung bundle with null eval placeholders,
and after running evaluations, this script fills in the eval_seed42/43/44
and semantic_gate_val/test fields.

Usage:
    PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
        --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
        --arm olsa \
        --eval-seed42 data/artifacts/arc_d/r0/eval_r0.json \
        --eval-seed43 data/artifacts/arc_d/r0/eval_r0_s43.json \
        --eval-seed44 data/artifacts/arc_d/r0/eval_r0_s44.json

    # With semantic gates:
    PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
        --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
        --arm olsa_full \
        --eval-seed42 data/artifacts/arc_d/r0/eval_r0_full.json \
        --semantic-gate-val data/artifacts/arc_d/r0/semantic_gate_val_full.json \
        --semantic-gate-test data/artifacts/arc_d/r0/semantic_gate_test_full.json
"""

import argparse
import json
import sys


def update_bundle(
    bundle_path: str,
    arm: str,
    eval_seed42: str | None = None,
    eval_seed43: str | None = None,
    eval_seed44: str | None = None,
    semantic_gate_val: str | None = None,
    semantic_gate_test: str | None = None,
) -> dict:
    """Update a rung bundle's arm block with eval/gate paths.

    Args:
        bundle_path: Path to rung_bundle_r0.json.
        arm: Which arm block to update ("olsa" or "olsa_full").
        eval_seed42: Path to seed-42 eval results.
        eval_seed43: Path to seed-43 eval results.
        eval_seed44: Path to seed-44 eval results.
        semantic_gate_val: Path to val semantic gate artifact.
        semantic_gate_test: Path to test semantic gate artifact.

    Returns:
        Updated bundle dict.

    Raises:
        ValueError: If arm is not "olsa" or "olsa_full".
        FileNotFoundError: If bundle_path doesn't exist.
    """
    if arm not in ("olsa", "olsa_full"):
        raise ValueError(f"arm must be 'olsa' or 'olsa_full', got '{arm}'")

    with open(bundle_path) as f:
        bundle = json.load(f)

    arm_block = bundle[arm]

    if eval_seed42 is not None:
        arm_block["eval_seed42"] = eval_seed42
    if eval_seed43 is not None:
        arm_block["eval_seed43"] = eval_seed43
    if eval_seed44 is not None:
        arm_block["eval_seed44"] = eval_seed44
    if semantic_gate_val is not None:
        arm_block["semantic_gate_val"] = semantic_gate_val
    if semantic_gate_test is not None:
        arm_block["semantic_gate_test"] = semantic_gate_test

    with open(bundle_path, "w") as f:
        json.dump(bundle, f, indent=2)

    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update R0 rung bundle with eval paths"
    )
    parser.add_argument("--bundle", required=True, help="Path to rung_bundle_r0.json")
    parser.add_argument(
        "--arm",
        required=True,
        choices=["olsa", "olsa_full"],
        help="Which arm block to update",
    )
    parser.add_argument("--eval-seed42", help="Path to seed-42 eval results")
    parser.add_argument("--eval-seed43", help="Path to seed-43 eval results")
    parser.add_argument("--eval-seed44", help="Path to seed-44 eval results")
    parser.add_argument("--semantic-gate-val", help="Path to val semantic gate")
    parser.add_argument("--semantic-gate-test", help="Path to test semantic gate")

    args = parser.parse_args()

    bundle = update_bundle(
        bundle_path=args.bundle,
        arm=args.arm,
        eval_seed42=args.eval_seed42,
        eval_seed43=args.eval_seed43,
        eval_seed44=args.eval_seed44,
        semantic_gate_val=args.semantic_gate_val,
        semantic_gate_test=args.semantic_gate_test,
    )

    print(f"Updated {args.arm} in {args.bundle}")
    arm_block = bundle[args.arm]
    for key in (
        "eval_seed42",
        "eval_seed43",
        "eval_seed44",
        "semantic_gate_val",
        "semantic_gate_test",
    ):
        print(f"  {key}: {arm_block.get(key)}")


if __name__ == "__main__":
    main()
    sys.exit(0)
