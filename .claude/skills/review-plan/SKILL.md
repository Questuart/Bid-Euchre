---
name: review-plan
description: Runs independent plan review loop with Codex CLI primary reviewer and Claude failsafe. Supports tiered rubrics (small/medium/governing). Manual invocation only.
---

# /review-plan -- Independent Plan Review

Reviews a plan file using the Codex CLI (primary) with Claude agent fallback.
Runs up to 5 review iterations with automated fixes between rounds.

## Usage

```
/review-plan [path]
/review-plan plans/sessions/2026-03-15_my-plan.md
/review-plan  # reviews most recently modified plan file
```

## Process

1. **Identify plan file:**
   - Use the path from `$ARGUMENTS` if provided
   - Otherwise find the most recently modified plan: `ls -t plans/sessions/*.md plans/*/*.md 2>/dev/null | grep -v TEMPLATE | grep -v '.review.md' | head -1`
   - If no plan found, stop: "No plan file found to review."

2. **Run the review loop:**
   Use the Agent tool to spawn a background plan review agent:

   ```
   Agent(
     description="plan review loop",
     prompt="Run the plan review loop on <plan-path>. Execute: cd <repo-root> && PYTHONPATH=scripts/internal uv run python -c \"
import sys; sys.path.insert(0, 'scripts/internal')
from plan_review_driver import run_plan_review_loop
from pathlib import Path
result = run_plan_review_loop(Path('<plan-path>'))
import json; print(json.dumps(result.to_dict(), indent=2))
\"
Report the full result back.",
     run_in_background=true
   )
   ```

3. **Report results:**
   When the agent completes, present the results:
   - Tier detected
   - Reviewer used (codex_cli or claude_failsafe)
   - Iteration count
   - Verdict (READY / NEEDS_ATTENTION / NOT_READY)
   - Findings table (if any)
   - Sidecar file location

## Important Notes

- This is a **manual-only** skill. It is NOT auto-triggered by hooks.
- The review runs as an independent agent, separate from the plan author.
- If Codex CLI is unavailable, the Claude failsafe reviewer runs instead and a GitHub issue is created.
- Results are written to `.claude/runtime/plan_reviews/<hash>/review.md`
- Tier can be overridden with `<!-- review-tier: small|medium|governing -->` in the plan file.
- See `docs/02_agent/PLAN_REVIEW_TIERS.md` for the full rubric specification.
