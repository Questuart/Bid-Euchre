# Plan Review Workflow — Implementation Plan

**Date:** 2026-03-06
**Goal:** Replace auto-invocation of EnterPlanMode with a file-based planning workflow where all plans are saved to `plans/`, and a PostToolUse hook auto-triggers a reviewer agent to check every plan against repo conventions.

## Context

### Problem
1. EnterPlanMode generates ephemeral plans in conversation context — they vanish after the session, losing traceability.
2. No automated review of plan quality against repo conventions before implementation begins.
3. No plan-to-PR audit trail — hard to compare what was planned vs. what was shipped.

### Current State
- `plans/` has 60+ files with `plans/archive/` for completed work
- `planning-code-first` skill governs *how* to plan (read code first)
- `CLAUDE.md` already says "Save plans as markdown files in a `plans/` directory"
- Existing PostToolUse hook pattern: `post-pr-review.sh` matches `Bash` → detects `gh pr create` → injects `additionalContext` → Claude auto-invokes `/reviewing-changes`
- EnterPlanMode is NOT being disabled — it remains available for manual `/plan` invocation

### Research: Official Claude Code Docs (code.claude.com/docs/en/hooks)

**PostToolUse input for Write tool:**
```json
{
  "session_id": "abc123",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

**PostToolUse output format (decision + additionalContext):**
```json
{
  "decision": "block",
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Claude"
  }
}
```

**Key facts:**
- Matcher `"Write"` is officially supported (regex against `tool_name`)
- `tool_input.file_path` available for path matching
- `additionalContext` in `hookSpecificOutput` injects context Claude can see and act on
- Exit 0 = success (JSON parsed from stdout); exit 2 = blocking error
- Default timeout: 600s for command hooks
- Multiple PostToolUse entries allowed with different matchers

## Plan

### File 1: `plans/sessions/.gitkeep`
Create empty file to establish the session plans directory.

### File 2: `.claude/hooks/post-plan-review.sh`

**Purpose:** PostToolUse hook that detects when a plan file is written to `plans/` and injects an `additionalContext` directive telling Claude to spawn a plan reviewer agent.

**Behavior:**
1. Read JSON from stdin
2. Extract `tool_input.file_path`
3. Check if path matches `*/plans/*.md` (but NOT `TEMPLATE.md` or `.gitkeep`)
4. If match: emit JSON with `additionalContext` directive
5. If no match: exit 0 silently

**Script (verified against official docs):**
```bash
#!/bin/bash
# PostToolUse hook — triggers /reviewing-plans after plan file creation
set -euo pipefail

INPUT=$(cat)

# Extract the file path from Write tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Only trigger for plan files (not templates or gitkeep)
if [[ "$FILE_PATH" == */plans/*.md ]] && \
   [[ "$FILE_PATH" != *TEMPLATE.md ]] && \
   [[ "$FILE_PATH" != *.gitkeep ]]; then

  PLAN_NAME=$(basename "$FILE_PATH" .md)

  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "A plan file was just created at ${FILE_PATH}. You MUST now invoke the /reviewing-plans skill immediately — do not wait for the user to ask. Pass the plan file path to the reviewer."
  }
}
EOF
fi

exit 0
```

**Design decisions:**
- Matches `*/plans/*.md` broadly (catches both `plans/sessions/` and `plans/` top-level) — all plans get reviewed
- Excludes `TEMPLATE.md` to avoid triggering on template creation
- Uses same pattern as `post-pr-review.sh` for consistency
- Exit 0 always (PostToolUse can't block — tool already ran)

### File 3: `.claude/skills/reviewing-plans/SKILL.md`

**Purpose:** Reviewer skill that spawns an agent to check a plan file against repo conventions and flag implementation risks.

**Skill frontmatter:**
```yaml
---
name: reviewing-plans
description: Reviews plan files against repo conventions, identifies implementation risks, and flags issues before coding begins. Auto-triggered by PostToolUse hook after plan file creation.
---
```

**Review Checklist (10 checks):**

| ID | Category | Check | Source Rule |
|----|----------|-------|-------------|
| P1 | Code-First | Plan references real file paths that exist on disk | `planning-code-first` skill |
| P2 | Code-First | Plan includes actual function signatures (not guessed) | `planning-code-first` skill |
| P3 | Determinism | Experiment/validation commands include `--seed` | `20_determinism.md` |
| P4 | Boundaries | No planned imports from `experiments/` or `tests/` into `src/` | `CLAUDE.md` Architecture |
| P5 | Scope | Plan is single-concept / single-PR sized (or explicitly multi-PR with dependency chain) | `40_prs.md` |
| P6 | Testing | Plan identifies which tier 1 tests to run during implementation | `15_testing_tiers.md` |
| P7 | Data Contract | If touching rules/logging/metrics: plan notes doc update requirement | `30_data_contract.md` |
| P8 | Rigor | If experiment: plan specifies sample size requirements and success criteria | `05_rigor.md` |
| P9 | Template | Plan has required sections: Goal, Plan/Steps, Files, Outcome placeholder | New convention |
| P10 | Notebook | If touching notebooks: plan notes jupytext sync requirement | `45_notebook_boundary.md` |

**Implementation Risk Flags (5 checks):**

| ID | Risk | Detection |
|----|------|-----------|
| R1 | Circular imports | Plan adds to `__init__.py` exports or creates cross-module dependencies |
| R2 | Stale training data | Plan changes feature names in `hand_eval.py` or `auction_context.py` |
| R3 | Missing exports | Plan adds new public classes/functions without noting `__init__.py` update |
| R4 | Scope creep | Plan touches >5 files without clear justification |
| R5 | Gate semantics | Plan modifies validation/diagnostic gates without noting SKIP/FAIL ordering |

**Reviewer workflow:**
1. Read the plan file
2. For P1/P2: Use Glob/Grep to verify referenced file paths exist and signatures match
3. For P3-P10: Pattern-match against plan content
4. For R1-R5: Analyze planned file changes for known risk patterns
5. Output structured report

**Output format:**
```markdown
## Plan Review: <plan-name>

### Convention Compliance
| ID | Status | Finding |
|----|--------|---------|
| P1 | PASS/WARN/SKIP | Detail |
| ... | ... | ... |

### Implementation Risks
| ID | Status | Finding |
|----|--------|---------|
| R1 | CLEAR/FLAG | Detail |
| ... | ... | ... |

### Summary
- Conventions: X/Y passed, Z warnings
- Risks: N flags
- Verdict: READY / NEEDS ATTENTION
```

### File 4: `.claude/settings.local.json` — Hook Registration

Add a new PostToolUse entry matching on `Write`:

```json
{
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post-pr-review.sh",
          "timeout": 5
        }
      ]
    },
    {
      "matcher": "Write",
      "hooks": [
        {
          "type": "command",
          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post-plan-review.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

**Note:** Multiple PostToolUse entries with different matchers are officially supported per the docs.

### File 5: `CLAUDE.md` — Workflow Section Updates

Update the `## Workflow` section:

**Add after "Save plans as markdown files in a `plans/` directory":**
```markdown
- **Do not auto-invoke EnterPlanMode** — only the user may invoke `/plan`. Claude must write plans as markdown files instead.
- For canonical multi-step plans (multi-PR, rung-level): save to `plans/<name>.md`
- For session-scoped plans (single PR, bugfix, small feature): save to `plans/sessions/YYYY-MM-DD_<slug>.md`
- Every plan file should include an `## Outcome` section (filled after implementation) linking to resulting PR(s) or noting abandonment.
- A PostToolUse hook auto-triggers `/reviewing-plans` after every plan file creation.
```

### File 6: `plans/sessions/TEMPLATE.md`

Reference template (not auto-reviewed due to hook exclusion):

```markdown
# <Title>
**Date:** YYYY-MM-DD
**Goal:** 1-2 sentence intent

## Plan
- Step 1
- Step 2

## Files
- `path/to/file.py` — what changes

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
```

### File 7: `.claude/hooks/README.md` — Update Documentation

Add section for the new hook following the existing pattern (worktree-guard, post-pr-review).

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `plans/sessions/.gitkeep` | Create | Establish session plans directory |
| `plans/sessions/TEMPLATE.md` | Create | Reference template for session plans |
| `.claude/hooks/post-plan-review.sh` | Create | PostToolUse hook detecting plan writes |
| `.claude/skills/reviewing-plans/SKILL.md` | Create | Plan reviewer skill with 10+5 checks |
| `.claude/settings.local.json` | Edit | Register new PostToolUse hook |
| `CLAUDE.md` | Edit | Update Workflow section with new rules |
| `.claude/hooks/README.md` | Edit | Document new hook |

## Design Decisions

### Why PostToolUse on Write (not Edit)?
- **Write** = new file creation (plan inception). This is the moment to review.
- **Edit** = incremental refinement. Re-reviewing after every edit would be noisy.
- User can manually invoke `/reviewing-plans` for re-review after edits.
- Matches the pattern: `post-pr-review.sh` fires on `gh pr create`, not on subsequent pushes.

### Why `plans/sessions/` (not `plans/tmp/` or `plans/simple/`)?
- `tmp/` implies deletion — these are permanent records
- `simple/` implies low quality — these are working documents
- `sessions/` signals temporal scope — one session's planning work
- Date prefix (`YYYY-MM-DD_slug.md`) enables chronological browsing

### Why keep EnterPlanMode available?
- User may want interactive planning for complex architectural exploration
- The rule prevents *auto-invocation*, not user-invoked `/plan`
- Both modes can coexist: `/plan` for interactive thinking, file-based for the record

### Why `additionalContext` (not `decision: "block"`)?
- PostToolUse **cannot block** (tool already ran) — exit 2 just shows stderr
- `additionalContext` is the correct mechanism per official docs
- It injects a directive into Claude's context, same pattern as post-pr-review

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Hook fires on MEMORY.md edits to plans/ dir | Matcher checks `*.md` under `plans/` specifically; MEMORY.md is elsewhere |
| Hook fires on plan edits (Edit tool) | Matcher is `Write` only, not `Edit\|Write` |
| Reviewer agent is slow, delays implementation | Agent uses read-only tools (Glob, Grep, Read); no experiments or builds |
| False positives on P1 (file path checks) | Reviewer uses WARN not BLOCK; doesn't auto-fix |
| Hook doesn't fire (known Claude Code issues) | Manual `/reviewing-plans` invocation as fallback |

## Outcome
<!-- Filled after implementation -->
- PR: TBD
- Notes: TBD
