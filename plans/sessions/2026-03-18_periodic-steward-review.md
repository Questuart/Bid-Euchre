# Periodic Steward-Review via `/loop` or `CronCreate`

**Date:** 2026-03-18
**Status:** EXPLORATION (author-scratch)
**Goal:** Configure recurring steward-review of recently merged PRs to catch cross-PR patterns that per-diff agents miss.

---

## 1. Problem Statement

The repo has **per-merge review** (3 specialized agents: correctness, architecture, coverage) that runs on each `gh pr merge` via PostToolUse hook. These agents review a single PR diff against `main~1...main`.

**What they miss:** Cross-PR patterns — security anti-patterns spanning multiple PRs, pagination bugs in related workflows, process compliance drift (e.g., all 5 recent PRs merging with unchecked review boxes), and compound effects visible only when reviewing a batch.

The **steward-review** agent type is designed for exactly this — it "reviews author branches against main and prioritizes findings first." Running it periodically on batches of merged PRs fills the gap.

## 2. Available Mechanisms

### 2.1 `/loop` Skill (Built-in)

**Syntax:** `/loop <interval> <prompt-or-command>` (e.g., `/loop 30m Check PRs`)

- Runs prompt on a recurring interval in the current conversation
- Each tick is like a user message — Claude processes it and can call tools
- Simple interval syntax (5m, 30m, 1h, etc.), defaults to 10m
- Session-scoped — dies when Claude session ends

### 2.2 `CronCreate` Tool (Built-in)

**Syntax:** `CronCreate(cron="*/30 * * * *", prompt="...")`

- Standard 5-field cron in local timezone
- **Fires only while REPL is idle** (not mid-query) — won't interrupt active work
- Session-scoped, **auto-expires after 3 days**
- Supports one-shot (`recurring: false`) and recurring (`recurring: true`)
- Returns job ID for `CronDelete` cleanup

### 2.3 PostToolUse Hook (Existing Pattern)

The repo already uses event-driven hooks (`post-merge-review.sh`). A periodic hook isn't possible — hooks fire on tool events, not on timers.

### Comparison

| Property | `/loop` | `CronCreate` | PostToolUse Hook |
|----------|---------|-------------|-----------------|
| Trigger | Interval timer | Cron schedule | Tool output match |
| Persistence | Session | Session (3d max) | Permanent (settings.json) |
| Fires while busy | Yes (interrupts) | **No (waits for idle)** | Yes (hook msg) |
| Context cost | Each tick adds context | Each tick adds context | Small hook message |
| Scheduling precision | Simple intervals | Full cron (weekday, hour, etc.) | N/A (event-driven) |
| Best for | Active monitoring | **Periodic background** | Event-driven |

## 3. Recommendation: `CronCreate`

`CronCreate` is the better mechanism for periodic steward review because:

1. **Non-interruptive** — fires during idle time, won't disrupt active coding
2. **Precise scheduling** — standard cron syntax supports "every 2 hours on weekdays" etc.
3. **Explicit lifecycle** — job ID enables cleanup, auto-expires after 3 days
4. **Prompt-based** — the full review logic can be embedded in the prompt

`/loop` would work but interrupts active work. For a background quality gate, idle-time firing is preferable.

### Interval Recommendation

| Interval | Ticks/day | Ticks/3d session | Context impact |
|----------|-----------|------------------|----------------|
| 30 min | 48 | 144 | **Too many** — exhausts context |
| 1 hour | 24 | 72 | Heavy but manageable |
| 2 hours | 12 | 36 | **Recommended** — balances coverage vs cost |
| 4 hours | 6 | 18 | Conservative, good for low-merge-rate periods |

**Recommended: Every 2 hours** (`"17 */2 * * *"` — off-peak minute per CronCreate best practice).

## 4. Review Scope Per Invocation

### PR Discovery

```bash
gh pr list --state merged --limit 10 --json number,mergedAt,title
```

### Dedup via Tracking File

**Path:** `.claude/runtime/steward_review/last_batch.json`

```json
{
  "last_reviewed_at": "2026-03-18T10:30:00Z",
  "reviewed_prs": [813, 814, 815, 816, 817],
  "highest_pr": 817,
  "batch_count": 5,
  "findings_summary": "1 WARN (script injection), 1 WARN (pagination), 3 INFO"
}
```

**Logic:**
1. Read tracking file (if missing, default `highest_pr = 0`)
2. Filter merged PRs to those with `number > highest_pr`
3. If none, skip this tick (no output, minimal context cost)
4. If found, spawn steward-review agent with the batch
5. Update tracking file after agent completes

**Fallback for new sessions:** If tracking file doesn't exist, review the last 5 merged PRs (avoids re-reviewing everything, but ensures coverage).

## 5. Agent Spawning Pattern

### Batching Rule

Per `.claude/rules/70_agent_reliability.md`: agents die after ~15 min / ~700KB output. Keep review scope small.

| PRs in batch | Strategy |
|--------------|----------|
| 1-3 | Single steward-review agent |
| 4-6 | Single agent (stretch — monitor for timeouts) |
| 7+ | Split into 2 agents (PRs 1-4, PRs 5-N), consolidate after |

### Agent Prompt Template

```
Review the following recently merged PRs for cross-PR patterns and
issues that per-diff reviewers miss:

PRs to review: #818, #819, #820

For each PR, run `gh pr diff <N>` to see the changes. Then analyze
the BATCH as a whole for:

1. **Security anti-patterns** — script injection (${{ }} in JS/YAML),
   missing input sanitization, hardcoded secrets
2. **Pagination bugs** — API calls without pagination (listForRepo,
   listIssues, etc.) that fail at scale
3. **Process compliance** — review gate bypasses, unchecked review
   boxes (trend analysis), missing test coverage for behavior changes
4. **Cross-PR compound effects** — changes in one PR that invalidate
   assumptions in another, duplicated logic, divergent patterns
5. **Contract violations** — undocumented schema changes, missing
   doc updates for core/ changes

Return findings as:
- CRITICAL: Immediate fix required (security, data loss)
- WARN: Follow-up issue needed (pagination, process gaps)
- INFO: Worth noting, no action needed

Include PR number and file path for each finding.
```

## 6. Output Routing

### Options Compared

| Option | Visibility | Persistence | Noise Level |
|--------|-----------|-------------|-------------|
| A: PR comments | Per-PR | GitHub | Spammy for batch |
| **B: Batch issue** | **Repo-wide** | **GitHub** | **One issue per batch** |
| C: Local file | Local only | Session | Invisible to team |
| D: PR comment + issue | Both | GitHub | Redundant |

### Recommendation: Option B — Batch GitHub Issue

Create one issue per review batch with findings:

```bash
gh issue create \
  --title "Steward Review: PRs #818-#820 (2026-03-18)" \
  --body "$(cat <<'EOF'
## Steward Review Batch

**PRs reviewed:** #818, #819, #820
**Reviewed at:** 2026-03-18 10:30 UTC

### Findings

| Severity | PR | File | Finding |
|----------|-----|------|---------|
| WARN | #819 | `path/to/file.py` | Script injection via `${{ }}` |
| INFO | #820 | `path/to/other.py` | No pagination on listForRepo |

### Process Compliance

- 2/3 PRs merged with unchecked review boxes (advisory, consistent with current policy)
- No contract violations detected

---
*Generated by periodic steward-review (CronCreate)*
EOF
)" --label "steward-review"
```

**Label setup** (one-time): `gh label create steward-review --color "#8B5CF6" --description "Periodic steward review findings"`

### No-Findings Behavior

If the batch has **zero findings**, do NOT create an issue. Just update the tracking file. Avoid noise.

## 7. Full Implementation

### 7.1 Cron Setup (per session)

```
CronCreate(
  cron="17 */2 * * *",
  prompt="... (see 7.2 below)"
)
```

### 7.2 Cron Prompt

```
Periodic steward review tick. Execute these steps:

1. Run: gh pr list --state merged --limit 10 --json number,mergedAt,title
2. Read .claude/runtime/steward_review/last_batch.json
   - If file missing, set highest_pr=0 (will review last 5 PRs)
3. Filter to PRs with number > highest_pr
4. If no new PRs: do nothing, skip silently
5. If new PRs found (≤6): spawn ONE steward-review agent (subagent_type: steward-review)
   in the background with the review prompt from the plan
6. If >6 new PRs: spawn TWO agents, split the batch, consolidate after
7. After agent(s) complete:
   a. If findings exist, create GitHub issue with label 'steward-review'
   b. Update .claude/runtime/steward_review/last_batch.json with reviewed PRs
   c. If CRITICAL findings, also post a comment on the affected PR(s)
```

### 7.3 Session Bootstrap

Each new steward session should:
1. Create the runtime directory: `mkdir -p .claude/runtime/steward_review`
2. Set up the cron: invoke CronCreate with the prompt above
3. Verify with CronList

This could be added to `/recovering-context` skill or done manually.

### 7.4 Tracking File Initialization

```bash
mkdir -p .claude/runtime/steward_review
cat > .claude/runtime/steward_review/last_batch.json << 'EOF'
{
  "last_reviewed_at": null,
  "reviewed_prs": [],
  "highest_pr": 0,
  "batch_count": 0,
  "findings_summary": null
}
EOF
```

## 8. Constraints & Gotchas

### Session Lifetime
- CronCreate is **session-only** — dies when Claude exits
- Must be re-established each session
- Not a persistent daemon — user accepts this tradeoff
- Auto-expires after 3 days even if session persists

### Context Budget
- Each tick adds to conversation context even if no PRs found
- The "skip silently" path for no-new-PRs should be as terse as possible
- 2-hour interval = ~12 ticks/day = manageable
- If context pressure becomes an issue, increase to 4-hour interval

### Agent Reliability
- steward-review agents inherit the same context window limits
- Keep batch size ≤6 PRs per agent
- Don't combine review + fix in one agent

### Dedup Guarantees
- Tracking file provides dedup across ticks within a session
- Tracking file is in `.claude/runtime/` (gitignored) — not shared across sessions
- New sessions fall back to "last 5 merged PRs" — acceptable overlap
- Sentinel files in `/tmp/` provide additional dedup (consistent with existing hooks)

### `.gitignore` Verification
- `.claude/runtime/` should already be gitignored (it contains review_loops/)
- Verify: `grep -n runtime .gitignore`

## 9. What This Does NOT Cover

- **Persistent daemon** — requires OS-level cron or systemd, outside Claude Code scope
- **Cross-repo review** — steward-review operates on one repo at a time
- **Auto-fix of findings** — steward-review reports only; fixes are manual or separate PRs
- **Notification outside GitHub** — no Slack/email integration; GitHub issues are the notification channel

## 10. Next Steps

1. **Decide interval** — 2h recommended, user may prefer 1h or 4h
2. **Create label** — `gh label create steward-review --color "#8B5CF6"`
3. **Test one-shot** — Run the steward-review agent manually on PRs #813-#817 to validate prompt
4. **Wire CronCreate** — Set up the cron in a steward session
5. **Optional: Add to session bootstrap** — Include in `/recovering-context` or CLAUDE.md

## Outcome

**Executed 2026-03-18 in author-scratch session.**

### What was done:
1. ✅ **GitHub label created:** `steward-review` (#8B5CF6)
2. ✅ **Tracking directory + file initialized:** `.claude/runtime/steward_review/last_batch.json`
3. ✅ **One-shot test completed:** steward-review agent reviewed PRs #818-#821
   - Found 3 WARNs (R2 absolute paths, mode=QUICK mislabel, decision report title bug)
   - Found 5 INFOs (process compliance, cross-PR sequencing, security clean)
   - GitHub issue created: #824
4. ✅ **CronCreate wired:** Job `352ce154`, every 2h at :17, auto-expires after 3 days
   - Fires while idle, spawns steward-review agent for unreviewed PRs
   - Posts GitHub issues for WARN/CRITICAL findings

### Constraints accepted:
- Session-only cron (must re-establish each session)
- 3-day auto-expiry
- Not a persistent daemon
