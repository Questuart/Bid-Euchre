---
name: proving-issues
description: Guides agents through the verified-close workflow for issues that need proving before closure. Use when closing Tier 2 issues or validating PR issue linkage.
---

# /proving-issues — Issue Verification Workflow

Close issues safely by posting verification evidence before closure.
This skill implements the Tier 2 (verified-close) workflow from the
tiered issue closure policy.

## When to Use

- You merged a PR that uses `Refs #N` and the issue needs proving
- You need to close an issue that has `needs-verification` label
- You want to validate that a PR uses the right `Fixes` vs `Refs` keyword
- An operator or orchestrator asks you to verify and close outstanding issues

## Quick Reference

```bash
# List issues needing verification
uv run python scripts/internal/verify_issue_closure.py list-pending

# Validate PR linkage (warns if Fixes is used for Tier 2 issues)
uv run python scripts/internal/verify_issue_closure.py check-pr <PR_NUMBER>

# Post evidence and close (dry-run first)
uv run python scripts/internal/verify_issue_closure.py prove <ISSUE_NUMBER> \
    --evidence "Verification text here" --dry-run

# Post evidence and close (for real)
uv run python scripts/internal/verify_issue_closure.py prove <ISSUE_NUMBER> \
    --evidence "Verification text here"
```

## Workflow

### Step 1 — Identify Issues Needing Verification

After merging a PR that uses `Refs #N`, the linked issue stays open.

```bash
uv run python scripts/internal/verify_issue_closure.py list-pending
```

Or manually check:
```bash
gh issue list --label needs-verification --state open
```

### Step 2 — Reproduce and Verify

Run the verification for the specific issue:

1. **Read the issue** to understand what needs proving:
   ```bash
   gh issue view <NUMBER>
   ```

2. **Run the proving command** — this varies by issue type:
   - **Code fix:** Run the failing test or repro command from the issue
   - **Fleet/production fix:** Check fleet status, run monitoring cycle
   - **UI fix:** Run Playwright smoke test or manual verification
   - **Process fix:** Demonstrate the improved workflow

3. **Capture the evidence** — exact command + output showing the fix works

### Step 3 — Post Evidence and Close

```bash
uv run python scripts/internal/verify_issue_closure.py prove <NUMBER> \
    --evidence "$(cat <<'EVIDENCE'
**Command:** uv run python -m pytest tests/unit/test_foo.py -k test_the_fix -v
**Result:** 1 passed in 0.5s
**Observation:** The regression no longer reproduces. Fix confirmed.
EVIDENCE
)"
```

This posts a structured verification comment and closes the issue.

### Step 4 — Validate PR Linkage (Pre-PR)

Before opening a PR, validate your issue linkage:

```bash
# After creating PR (or on an existing PR)
uv run python scripts/internal/verify_issue_closure.py check-pr <PR_NUMBER>
```

This checks each `Fixes #N` and `Refs #N` in the PR body:
- **Tier 1 issues** (simple, bounded, CI-testable) — `Fixes` is OK
- **Tier 2 issues** (complex, needs fleet verification) — warns if `Fixes` is used

## Tier Classification

The tool classifies issues automatically based on:

| Signal | Tier | Why |
|--------|------|-----|
| Has `needs-verification` label | 2 | Explicitly marked for verification |
| Has `needs-human` label | 2 | Requires human decision |
| Body mentions "acceptance criteria" | 2 | Has explicit done-when conditions |
| Body mentions "fleet" or "production" | 2 | Needs non-CI verification |
| Was previously reopened | 2 | History of premature closure |
| Substantial body (>1500 chars) | 2 | Likely complex requirements |
| None of the above | 1 | Simple fix, CI sufficient |

## Choosing `Fixes` vs `Refs`

| Situation | Keyword | Reason |
|-----------|---------|--------|
| Single-line fix, CI locks it | `Fixes #N` | Tier 1: auto-close is safe |
| Multi-PR resolution | `Refs #N` | Partial fix should not close tracker |
| Needs fleet/prod verification | `Refs #N` | CI alone is insufficient |
| Root cause uncertain | `Refs #N` | May resurface |
| Previously reopened | `Refs #N` | Pattern of premature closure |
| When in doubt | `Refs #N` | Cost of open issue is low |

## Evidence Format

Good verification evidence includes:

```markdown
**Command:** <exact reproduction command>
**Result:** <output showing fix works>
**Observation:** <1-2 sentence summary of what was verified>
```

Bad evidence:
- "Looks fixed" (no command/output)
- "PR was merged" (merge is not verification)
- "Tests pass" (only sufficient for Tier 1)

## Gotchas

- Never close an issue without posting evidence — even obvious fixes
  benefit from a quick verification note
- The `prove` subcommand posts AND closes — no separate step needed
- Use `--dry-run` first to preview what will be posted
- If you cannot reproduce or verify, add `needs-human` label instead
  of closing

## References

- `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` § Tiered Issue Closure
- `.claude/rules/deferred/55_issue_closure.md` — Deferred rule
- `scripts/internal/verify_issue_closure.py` — CLI tool
