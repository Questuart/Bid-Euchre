# Claude Code Project Memory — Bid Euchre

Project overview, commands, architecture, and constraints are in the root CLAUDE.md.
Domain docs live in docs/ — read them on-demand when working in relevant areas.
Skills in .claude/skills/ provide workflow guidance — invoke with /skill-name.
TUI task list conventions are in `.claude/rules/25_task_lists.md` — use for multi-step work.

## Implementation Handoff Protocol

When generating an implementation handoff for another Codex/Claude agent,
the prompt must require this sequence before code changes begin:
1. Refresh the governing/implementation plan context.
2. Draft or refresh a concrete execution plan.
3. Spawn at least one reviewer agent to review that plan.
4. Create a task list for implementation, validation, and PR shipping.
5. Assess the work for safe parallelism and delegate only disjoint write scopes.
6. Execute the work end to end autonomously:
   - implement
   - test
   - run smoke/failure-injection validation
   - commit
   - open/update the PR
   - include `Validation Performed` evidence in the PR body

Do not hand off implementation work with only a file list or goal summary.
The handoff must explicitly tell the next agent to plan, review the plan,
manage a task list, assess parallelism, and ship the work autonomously.

## Compaction Instructions

When compacting conversation context, preserve:
1. **Modified files list** — all files created/edited this session
2. **Goal + acceptance criteria** — what we're trying to achieve and how to verify
3. **Exact commands + outputs** — reproduction commands with seeds, test results, error messages
4. **Blocking issues** — any unresolved errors or decisions needed

Discard: exploration tangents, superseded plans, verbose file contents already summarized.

## Post-PR Review
- `/reviewing-changes` auto-triggers after `gh pr create` via PostToolUse hook
- Reviews code quality, conventions, generates handoff summary
- Auto-fixes are pushed as follow-up commits to the PR branch
- Handoff summary is designed for `/copy` into a new session

## Post-Merge Review
- After every `gh pr merge`, a PostToolUse hook triggers a comprehensive review
- A background Explore agent reviews merged code for correctness, contract compliance,
  architecture, and test coverage
- CRITICAL findings trigger immediate fix PRs
- This is a safety net — pre-merge review catches most issues, post-merge catches the rest

## Docs-Only CI
- CI uses `dorny/paths-filter` to gate job execution (PR #635, updated PR #1086)
- The `tests` aggregation gate always triggers and posts a status
- Docs/plans-only PRs skip heavy jobs via path-filter gating
