---
name: reviewing-repo
description: Performs a comprehensive 5-phase repository review following docs/02_agent/REPO_REVIEW_PROMPT.md. Spawns parallel agents for discovery, verification, and issue detection, then synthesizes a scored report. Use when the user wants a full repo health check.
---

# Repo Review — 5-Phase Protocol

Comprehensive repo health check following the protocol in `docs/02_agent/REPO_REVIEW_PROMPT.md`.

## Pre-flight

1. **Verify branch**: Confirm you are on `main` at HEAD. Reviews should assess the current canonical state.
   ```bash
   git branch --show-current
   git log --oneline -1
   ```
2. **Warn if not on main**: If on a feature branch, warn the user that the review will cover that branch's state, not the canonical repo.
3. **Read the protocol**: Read `docs/02_agent/REPO_REVIEW_PROMPT.md` to confirm it exists and note its version.

## Wave 1 — Parallel Data Gathering (Phases 1-3)

Spawn **3 sub-agents in parallel** using the Task tool (`subagent_type: general-purpose`). Each agent works from the repo root and is **read-only** (no file edits).

**Important:** Launch all 3 in a single message so they run concurrently.

### Agent 1: Discovery (Phase 1)

Use the prompt template from [DISCOVERY_TEMPLATE.md](DISCOVERY_TEMPLATE.md).

Set `max_turns` to 30.

### Agent 2: Verification (Phase 2)

Use the prompt template from [VERIFICATION_TEMPLATE.md](VERIFICATION_TEMPLATE.md).

Set `max_turns` to 40.

### Agent 3: Issue Discovery (Phase 3)

Use the prompt template from [ISSUES_TEMPLATE.md](ISSUES_TEMPLATE.md).

Set `max_turns` to 35.

## Gate Check

After all 3 agents return:

1. **Check Phase 2 result for `make check` status**
2. **If `make check` FAILED**: Stop the review. Output a failure summary with the error details from Agent 2. Do not proceed to synthesis.
3. **If any agent failed to return**: Mark that phase as "NOT COMPLETED" and continue with available data.

## Phase 4 — Analysis (Main Thread)

Using the combined output from all 3 agents:

1. **Classify issues by severity**:
   - **CRITICAL**: Breaks functionality, violates hard gates, introduces nondeterminism
   - **HIGH**: Documentation drift causing confusion, missing rigor validation
   - **MEDIUM**: TODOs in production code, stale references, incomplete tests
   - **LOW**: Cosmetic issues, informational gaps, minor doc improvements

2. **Assess each issue**:
   - Affected workflows (CI, experiments, analysis, onboarding)
   - Risk (high/medium/low)
   - Effort (trivial/small/medium/large)

3. **Rank by impact**: Top 5 issues by default (expand only if user requests).

## Phase 5 — Output (Main Thread)

Assemble the **7-section report** per the protocol's output format:

1. **Executive Summary** — Health score table (X/100 per component), key achievements, blockers, top 5 issues
2. **Verification Evidence** — Command/Output/Status table from Phase 2
3. **Issue Registry** — ID/Severity/Location/Issue/Evidence/Recommendation table (top 5 by impact)
4. **Cleanup Plan** (optional) — Only if issues warrant PR sequencing
5. **Rigor Assessment** — Sample sizes, statistical test coverage, fail-fast gates, anti-patterns
6. **Documentation Roadmap** (optional) — Only if critical doc drift found
7. **Development Roadmap** (optional) — Only if requested or critical issues need sequencing

### Write Report

Save the full report to: `docs/03_TODO/REPO_REVIEW_<YYYY-MM-DD>.md`

**Important:** This is the one write operation in the review. Create a worktree if needed:
```bash
git worktree add ../Bid-Euchre-review -b codex/review-<date>
```

### Chat Summary

After writing the report, output to chat:
- The executive summary (health score table + top 5 issues)
- The file path where the full report was saved
- Offer follow-up options

### Follow-Up

Ask the user:
1. **Commit as PR** — commit the report and open a PR
2. **Dive deeper** — investigate specific issues in more detail
3. **Generate cleanup plan** — create a prioritized PR sequence for fixes
4. **Done** — end the review

## Error Handling

- **Sub-agent failure**: Mark the phase as "NOT COMPLETED — agent failed to return". Continue with available data. Note the gap in the executive summary.
- **`make check` failure**: Abort review. Output failure summary with error details. Do not proceed to synthesis.
- **Unrunnable commands**: Mark as "NOT RUN" with reason in verification evidence table.
- **Stale protocol references**: If a command from the protocol fails, note it as a prompt staleness issue in the issue registry.

## Anti-Patterns to Avoid

- Embedding the full 40KB protocol text in sub-agent prompts (agents read it at runtime)
- Hardcoding counts, PR numbers, or file lists (use discovery)
- Making code changes during the review (read-only, except the final report write)
- Skipping `make check` or proceeding after it fails
- Inventing issues not backed by evidence (every claim needs a command output or file quote)
- Running the review from a feature branch without warning the user

## Notes

- Total estimated tool calls across all agents: 60-90
- The review is read-only — only the final report file is written
- Sub-agents use `general-purpose` type because they need Bash for `make check`, `uv run`, and `gh`
- The protocol version is in `docs/02_agent/REPO_REVIEW_PROMPT.md` — check it at runtime
