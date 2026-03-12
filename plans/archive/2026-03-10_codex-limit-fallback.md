# Codex Usage Limit Detection + CLI Fallback

## Goal

When GitHub Codex hits usage limits during `/reviewing-changes`, detect the
limit error immediately (stop wasting 10 minutes polling) and optionally fall
back to local Codex CLI review. Maintain distinct audit statuses for each state.

## Design Constraints (from user)

Never collapse these states:
- `clean review` — Codex reviewed and found no issues
- `UNAVAILABLE_LIMIT` — GitHub Codex hit usage limits
- `codex_cli` fallback — local CLI used as substitute

Each must have its own status in the review report and validation evidence.
Option 1 (pre-check stale heuristic) is explicitly rejected — too fragile.

## Implementation: Two PRs

### PR 1: Early Usage-Limit Detection (Option 2)

**Problem:** When Codex hits usage limits, the skill polls for 10 minutes
waiting for a response that will never come. The limit error appears as a
regular comment (channel 3), but the current polling only exits on channel 1
(inline review) or channel 2 (PR review body).

**Fix:** During polling, also check channel 3 (regular comments) for known
error patterns. If a limit/error message is detected, stop polling immediately.

**Files changed:**

1. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 3 polling logic
   - Add early exit: check channel 3 for error patterns during each poll cycle
   - Known error patterns:
     - "You have reached your Codex usage limits"
     - "Codex is temporarily unavailable"
   - On match: stop polling, set status to `UNAVAILABLE_LIMIT`

2. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 4 metadata
   - Add `UNAVAILABLE_LIMIT` as a valid Codex review status (alongside
     COMPLETE, PENDING, NOT AVAILABLE)
   - Update report template to show the distinct status

3. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 5 report
   - Update report template: Codex review status field now has 4 values:
     - `COMPLETE` — Codex responded with review content
     - `PENDING` — timed out, no response
     - `NOT AVAILABLE` — `gh pr comment` failed or no PR
     - `UNAVAILABLE_LIMIT` — usage limit error detected

**Changes to polling logic (pseudocode):**

```bash
# Current: poll channels 1+2 only, exit on content
# New: also check channel 3 for error patterns each cycle

for i in $(seq 1 20); do
  sleep 30

  # Channels 1+2 (unchanged)
  INLINE=$(gh api .../pulls/N/comments ...)
  REVIEWS=$(gh pr view N --json reviews ...)

  # NEW: Channel 3 error detection
  ERROR_MSG=$(gh pr view N --json comments \
    --jq '.comments[] | select(.author.login == "chatgpt-codex-connector") | .body' \
    | grep -i "usage limit\|temporarily unavailable" || true)

  if [ -n "$ERROR_MSG" ]; then
    echo "CODEX UNAVAILABLE: usage limit detected"
    # Record: codex_status=UNAVAILABLE_LIMIT, channel=none
    break
  fi

  # ... existing channel 1/2 checks ...
done
```

**Validation:**
- Manually verify by checking PR #594's Codex response (which was a limit error)
- The skill is procedural (SKILL.md instructions), not executable code — changes
  are to the polling procedure Claude follows

### PR 2: Local Codex CLI Fallback (Option 3, behind guard)

**Depends on:** PR 1 merged.

**Problem:** When GitHub Codex is unavailable, we get zero external review
signal. The local Codex CLI (`npx @openai/codex review --base main`) uses a
separate usage pool and still works.

**Fix:** After detecting `UNAVAILABLE_LIMIT`, optionally invoke local Codex CLI
as a fallback. Record the result under a distinct channel (`codex_cli`), never
as equivalent to GitHub Codex.

**Files changed:**

1. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 3
   - After `UNAVAILABLE_LIMIT` detection, add fallback step:
     ```
     If UNAVAILABLE_LIMIT and codex_cli_fallback is enabled:
       1. Run: invoke_codex_cli(mode=<review_mode>, base="main")
       2. Parse findings using codex_review_adapter
       3. Record as channel=codex_cli (NOT channel=github_codex)
       4. Include findings in report under separate "Codex CLI Fallback" section
     ```

2. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 4 metadata
   - Add `codex_cli` as a valid `codex_response_channel` value
   - Add `codex_cli_fallback_used: yes/no` field to metadata table

3. `.claude/skills/reviewing-changes/SKILL.md` — Phase 3 Step 5 report
   - Add new report section for CLI fallback findings (separate from GitHub
     Codex findings):
     ```markdown
     ### Codex CLI Fallback (used when GitHub Codex unavailable)
     - Invoked: yes / no
     - Latency: N seconds
     - Findings: ...
     ```

4. `.claude/rules/60_review_gate.md` — Document the fallback behavior
   - Add section explaining the two Codex channels and when fallback activates

**Guard:** The fallback is enabled by default but can be disabled by setting
`CODEX_CLI_FALLBACK=false` in the environment. This lets us disable it if the
CLI becomes unreliable without removing the code.

**Validation:**
- Run `/reviewing-changes` on a PR when GitHub Codex limits are hit
- Verify CLI fallback invokes and results appear under correct channel
- Verify report distinguishes GitHub Codex from CLI findings

## Status Values (Complete Picture)

| Status | Meaning | Channel | Polling behavior |
|--------|---------|---------|-----------------|
| `COMPLETE` | GitHub Codex reviewed | `inline_review` or `comment` | Found response, stopped |
| `PENDING` | No response in 10 min | `none` | Timed out |
| `NOT AVAILABLE` | Comment failed / no PR | `none` | Never started |
| `UNAVAILABLE_LIMIT` | Usage limit hit | `none` or `codex_cli` | Early exit on error |

When CLI fallback is used after `UNAVAILABLE_LIMIT`:
- GitHub Codex status: `UNAVAILABLE_LIMIT`
- CLI fallback status: `COMPLETE` or `FAILED`
- Channel: `codex_cli`
- Both recorded separately in report

## What This Does NOT Change

- Deterministic prechecks — unchanged
- Commit status publishing — unchanged (based on BLOCK findings, not Codex)
- Merge eligibility — unchanged (Codex is observe-only)
- Review driver / state machine — unchanged (uses CLI directly, not affected)
- Follow-up issue creation — unchanged

## Outcome

- **PR 1:** #597 — Early Codex usage-limit detection (merged 2026-03-10)
  - SKILL.md: channel 3 error pattern matching, early exit, UNAVAILABLE_LIMIT status
  - HANDOFF_TEMPLATE.md: new status values
- **PR 2:** #598 — Codex CLI fallback (merged 2026-03-10)
  - SKILL.md: Step 3b CLI fallback invocation, separate report section, metadata fields
  - HANDOFF_TEMPLATE.md: CLI fallback fields
  - 60_review_gate.md: two-channel documentation table
- **PR 3:** #600 — Timestamp scoping + channel value fix (merged 2026-03-10)
  - SKILL.md: channel 3 filtered by `CODEX_REQUEST_TS` to prevent stale false exits
  - SKILL.md + HANDOFF_TEMPLATE.md: `codex_cli` added to allowed `codex_response_channel` values
- **Note:** Environment guard (`CODEX_CLI_FALLBACK=false`) from plan was not
  implemented — the fallback is always-on since the CLI is confirmed working.
  Can be added later if reliability issues emerge.
