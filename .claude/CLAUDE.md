# Claude Code Project Memory — Bid Euchre

Project overview, commands, architecture, and constraints are in the root CLAUDE.md.
Domain docs live in docs/ — read them on-demand when working in relevant areas.
Skills in .claude/skills/ provide workflow guidance — invoke with /skill-name.

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

## Docs-Only CI Workaround
- Docs-only PRs (`docs/**`, `plans/**`, `*.md`) don't trigger CI due to `paths-ignore`
- Branch protection requires the `tests` check, creating a deadlock
- Workaround: include a `.claude/` file change to trigger CI
# trigger CI: fix-archive-overreach
# trigger CI
# trigger CI: play-policy-sanity-check
