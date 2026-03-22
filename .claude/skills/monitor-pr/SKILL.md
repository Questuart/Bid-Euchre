---
name: monitor-pr
description: Monitors a PR through CI, review, and merge — surfaces blockers with severity and recommended actions. Use from the ops lane to track PR health.
---

# /monitor-pr — PR Health Monitor

Check a PR's CI status, review status, and merge readiness. Surface blockers
with severity and recommended next actions. This skill consumes existing
dashboard and GitHub surfaces — it does not format its own lane summary.

## When to Use

- You are ops and need to check the health of one or more open PRs
- A PR seems stuck (CI not progressing, review not landing)
- You need to report PR status as part of a periodic health check

## Workflow

### Phase 1 — Identify PRs

1. **List open PRs:**
   ```bash
   gh pr list --state open --json number,title,headRefName,statusCheckRollup
   ```

2. Or check a specific PR:
   ```bash
   gh pr view <PR_NUMBER> --json number,title,state,statusCheckRollup,reviews,mergeable
   ```

### Phase 2 — Check CI Status

3. **Get CI check details:**
   ```bash
   gh pr checks <PR_NUMBER>
   ```

4. **Classify CI state:**

   | CI State | Severity | Action |
   |----------|----------|--------|
   | All checks pass | None | PR is CI-ready |
   | Checks running | None | Wait; re-check in next cycle |
   | One or more checks failing | Attention | Read failure log, recommend fix |
   | No checks triggered | Attention | Verify push reached remote; check workflow triggers |
   | All checks skipped (docs-only) | None | Expected for docs/plans PRs |

### Phase 3 — Check Review Status

5. **Check review status from dashboard:**
   ```bash
   uv run python scripts/internal/ops.py dashboard --json
   ```
   Look at `attention_items` and `inbox_highlights` for review-related alerts.

6. **Check review verdict (if review loop ran):**
   ```bash
   cat .claude/runtime/review_queue/pr_<PR_NUMBER>/verdict.json 2>/dev/null
   ```

7. **Classify review state:**

   | Review State | Severity | Action |
   |-------------|----------|--------|
   | Verdict `passed`, SHA matches HEAD | None | Ready for merge |
   | Verdict `blocked` | Blocker | Read findings, fix on branch |
   | Status `pending` > 30 min | Attention | Check review loop state |
   | Status `pending` > 60 min | Blocker | Manual override or rerun |
   | No verdict file | Info | Review loop may not have triggered |

### Phase 4 — Report

8. **Summarize with severity flags:**
   - Blocker: must fix before merge
   - Attention: investigate soon
   - Info: noted, no action needed

   Report format:
   ```
   PR #NNN: <title>
     CI: [pass|fail|running]
     Review: [passed|blocked|pending|none]
     Merge: [ready|blocked — <reason>]
     Action: <recommended next step>
   ```

## Gotchas

- Use `ops.py dashboard --json` for lane/PR state — do not format your own
  competing lane summary view
- Use `gh pr checks` for CI detail — do not scrape workflow run logs unless
  a check is failing
- Review status `pending` is advisory, not merge-blocking — but prolonged
  pending (>60 min) suggests the review loop crashed
- Docs/plans-only PRs have all heavy CI checks skipped — this is expected,
  not a failure
- See `/debugging-ci` for detailed symptom-to-fix mappings when CI is red

## References

- `.claude/skills/debugging-ci/SKILL.md` — CI failure diagnosis runbook
- `.claude/rules/deferred/60_review_gate.md` — review status values and
  merge protocol
- `.claude/agents/steward-ops.md` — ops periodic health check template
