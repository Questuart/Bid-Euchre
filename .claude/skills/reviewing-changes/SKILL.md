---
name: reviewing-changes
description: Dispatches the post-PR review by publishing pending status and generating a handoff summary. The autonomous review loop handles all quality checks asynchronously.
---

# /reviewing-changes — Post-PR Review Dispatcher

You are dispatching the post-PR review. This skill is fast (~5s).
All quality review happens asynchronously via the autonomous review loop (`review_driver.py`).

## Phase 0 — Pre-flight

1. Verify you are in a worktree (not main checkout):
   ```bash
   git rev-parse --show-toplevel
   git branch --show-current
   ```
   If on `main`, stop and warn: "Cannot review from main checkout. Switch to a worktree."

2. Get the diff scope:
   ```bash
   git diff --name-only origin/main...HEAD
   git diff --stat origin/main...HEAD
   ```

3. Classify changed files into categories:
   - **library**: `src/bid_euchre/**/*.py`
   - **test**: `tests/**/*.py`
   - **notebook**: `notebooks/**/*.py` or `*.ipynb`
   - **config**: `experiments/configs/**`, `experiments/suites/**`, `*.yaml`, `*.json`
   - **doc**: `docs/**`, `*.md`
   - **other**: everything else

4. Identify the PR:
   ```bash
   gh pr view --json number,title,url
   ```

5. Get HEAD SHA:
   ```bash
   git rev-parse HEAD
   ```

## Phase 1 — Publish Pending Status

Publish the review status as pending:
```bash
scripts/internal/set_review_status.sh pending "Review loop starting"
```

If the script is not found, skip and note in the handoff.

The autonomous review loop is triggered by the PostToolUse hook (`post-pr-review-loop.sh`).
It runs asynchronously and handles:
- Deterministic prechecks (C1/C2/N1/N2/N3/X2/X3)
- `make check-gated`
- Codex CLI review + auto-fix loop (max 3 iterations)
- Final status publishing (success/failure)
- Follow-up issue creation for P2 findings

If the loop hook did not fire (check `.claude/runtime/review_loops/` for state),
invoke manually:
```bash
python scripts/internal/review_driver.py --pr <N> --branch <branch> --trigger pr_created
```

## Phase 2 — Handoff Summary

Generate the handoff block using [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md).
Populate with pre-flight data from Phase 0.
Mark the review loop as **SPAWNED** (not COMPLETE — it runs asynchronously).

Output the handoff after a horizontal rule.

## Gotchas

- This skill is ONLY a dispatcher (~5s) — do NOT manually run review checks, read files, or create issues; the autonomous loop handles all of that
- If `gh pr view` fails, you may not be in a worktree with an open PR — push and create the PR first
- The review status is advisory (not required for merge) — a stuck `pending` won't block merging
- The PostToolUse hook triggers `review_driver.py` asynchronously — if it doesn't fire, check `.claude/runtime/review_loops/` for state
- Don't confuse this dispatcher with the post-MERGE review (different hook, different scope)

## Important Notes

- **Do NOT read changed files** or apply manual review checks — the loop handles this.
- **Do NOT poll for Codex response** — the loop handles this.
- **Do NOT create follow-up issues** — the loop handles this.
- **Do NOT run make check** — the loop handles this.
- If the loop fails, it publishes a failure status with a recovery command.
- The CHECKLIST.md file is retained as the authoritative reference for check definitions.
  The loop's `deterministic_prechecks.py` module implements these checks programmatically.
