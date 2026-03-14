#!/usr/bin/env python
"""CLI wrapper for rung orchestrator.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.orchestration``.

CLI:
    uv run python scripts/internal/run_rung.py --rung r0 --mode smoke --dry-run
    uv run python scripts/internal/run_rung.py --rung r0 --mode quick --seeds 42
    uv run python scripts/internal/run_rung.py --rung r0 --mode all
    uv run python scripts/internal/run_rung.py --rung r0 --status
    uv run python scripts/internal/run_rung.py --rung r0 --rerun --from-step 2 --models gbt_av
"""

from __future__ import annotations

import argparse
import logging
import sys

from bid_euchre.arc_d_v2.orchestration import (
    MODE_SEEDS,
    _state_path,
    handle_rerun,
    print_status,
    run_all,
    run_steps,
)
from bid_euchre.arc_d_v2.schemas import (
    STEPS,
    RunState,
)

logger = logging.getLogger("run_rung")


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
