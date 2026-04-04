---
name: check-reviews
description: Checks for merged PRs needing post-merge review, runs the review driver on unreviewed PRs, and updates the high-water mark. Use from the review lane via durable cron (/loop 10m /check-reviews).
---

# /check-reviews -- Review Lane PR Sweep

Check for recently merged PRs that need post-merge review, run the review
driver on any unreviewed PRs, and update the high-water mark. Designed for
durable cron invocation (`/loop 10m /check-reviews`) that survives `/clear`.

## When to Use

- You are the review lane and need to run a periodic review sweep
- The orchestrator has set up `/loop 10m /check-reviews` as a durable cron
- After a `/clear`, the review lane needs to resume its review duties
- You want a one-shot check of unreviewed merged PRs

## Arguments

None. Uses sensible defaults for production review sweeps.

## Workflow

### Step 1 -- Check for unreviewed merged PRs

```bash
uv run python scripts/internal/ops.py review-check --limit 10
```

This scans recently merged PRs and identifies those that:
- Have no post-merge review verdict on file
- Were merged since the last high-water mark
- Touch code paths (not docs/plans-only)

### Step 2 -- Run the review driver on each unreviewed PR

For each PR identified in Step 1, the review driver runs:

```bash
python scripts/internal/review_driver.py --pr <N> --trigger post-merge
```

The review driver performs:
- **Deterministic prechecks:** C1/C2/C5/N1/N2/N3/T1/X2/X3 pattern checks
- **Codex CLI review:** `codex review --base main` (if available)
- **Auto-fix:** Applies deterministic fixes for convention patterns
- **Verdict writing:** Records pass/block/warn verdict to review queue
- **Status publishing:** Updates the advisory `reviewing-changes` status
- **Follow-up issues:** Creates GitHub issues for non-blocking findings

### Step 3 -- Update the high-water mark

After processing all identified PRs, update the high-water mark via the
subprocess-safe CLI (never use Claude's Write tool for `.claude/` paths):

```bash
uv run python scripts/internal/ops.py review-hwm set <HIGHEST_PR_NUMBER>
```

### Step 4 -- Report findings

If any PRs had blocking findings, send an alert:

```bash
uv run python scripts/internal/ops.py message send \
  --from review --to orchestrator --type supervisor_alert \
  --priority high \
  --summary "Post-merge review: PR #NNN has blocking findings"
```

For non-blocking findings, the review driver creates follow-up issues
automatically.

## Manual Review of a Specific PR

To manually review a specific PR (outside the cron cycle):

```bash
# Check review queue state
uv run python scripts/internal/ops.py queue

# Run review driver on a specific PR
python scripts/internal/review_driver.py --pr <N> --trigger manual

# Check verdict
cat .claude/runtime/review_queue/pr_<N>/verdict.json
```

## Durable Cron Setup

The review lane should run this skill on a repeating schedule:

```
/loop 10m /check-reviews
```

This survives `/clear` because the skill is registered in `.claude/skills/`
and the cron job references it by name.

## Gotchas

- This skill is for the **review lane only**. Other lanes should not run
  review sweeps.
- The review driver has a 15-minute max runtime per PR. If multiple PRs are
  queued, they are processed sequentially.
- Codex CLI requires a ChatGPT subscription. If unavailable, the driver falls
  back to deterministic prechecks only.
- Permission prompts can stall the review lane. The skill handles this
  gracefully by using only registered CLI commands.
- Docs/plans-only PRs are skipped (no code to review).

## References

- `scripts/internal/review_driver.py` -- canonical review coordinator
- `scripts/internal/ops.py review-check` -- merged PR scanner
- `.claude/rules/deferred/60_review_gate.md` -- review gate rules and verdicts
- `.claude/skills/monitor-pr/SKILL.md` -- single-PR health check (ops lane)
