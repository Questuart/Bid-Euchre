# SP-2-03: Agent Frontmatter Hardening

**Parent:** Phase 2 — Visible Operating Model
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Amendment:** A3 (agent frontmatter hardening and lane-boundary enforcement)
**Status:** completed
**Owner:** author-b
**Created:** 2026-03-22

## Goal

Add structural frontmatter boundaries to non-author agent profiles using
`allowedTools` — a runtime-supported agent frontmatter key — so that
non-implementation lanes cannot accidentally use implementation tools.

## Runtime Verification

The Claude Code agent runtime supports the following frontmatter keys
(verified from binary documentation strings 2026-03-22):

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Agent name |
| `description` | string | Agent description |
| `model` | string | Model ID |
| `color` | string | Display color |
| `allowedTools` | array | Tools the agent can use |
| `disallowedTools` | array | Tools to explicitly disallow |

Strategy: Use `allowedTools` (allowlist) for tightly scoped lanes, and
`disallowedTools` (denylist) where a broad capability set minus a few
dangerous tools is the right model.

## Design Decisions

1. **steward-review**: Allowlist approach. Needs read-only file access (Read,
   Grep, Glob, Bash for git commands) but should NOT have Edit, Write, or
   Agent capabilities. Also needs ToolSearch for deferred tool resolution.
2. **steward-ops**: Denylist approach. Needs broad monitoring capabilities
   (Bash for git/gh/ops.py, Read, Grep, Glob) but should NOT be able to
   Edit or Write code files. Uses disallowedTools since the ops lane needs
   many tools and an explicit denylist is clearer.
3. **issues**: Allowlist approach. Needs Bash (for gh issue operations),
   Read, Grep, Glob for searching, plus MCP GitHub tools for issue
   management. Should NOT have Edit, Write, or Agent.
4. **model annotations**: Ship `model: sonnet` for steward-review and
   steward-ops consistent with existing specialist agents. The issues agent
   already uses inherit (no model annotation) which is fine for its scope.

## File Changes

| File | Change |
|------|--------|
| `.claude/agents/steward-review.md` | Add `allowedTools` + `model: sonnet` |
| `.claude/agents/steward-ops.md` | Add `disallowedTools` + `model: sonnet` |
| `.claude/agents/issues.md` | Add `allowedTools` |
| `.claude/agents/README.md` | Add section on enforced boundaries |
| `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` | Add note about enforced tool boundaries |
| `plans/agent_ops/sub_plan_registry.md` | Register SP-2-03 |

## Validation

1. `make check-quiet` passes
2. `rg -n '^tools:|^model:|^allowedTools:|^disallowedTools:' .claude/agents/` shows expected restrictions
3. Unhappy-path: verify restricted lanes retain needed read/search/CLI capabilities

## Outcome

PR #1239: `ops: add structural frontmatter hardening to non-author agent lanes`

All three non-author lanes hardened:
- `steward-review`: `allowedTools` allowlist (Read, Grep, Glob, Bash, ToolSearch, Skill)
- `steward-ops`: `disallowedTools` denylist (Edit, Write, Agent)
- `issues`: `allowedTools` allowlist (Read, Grep, Glob, Bash, ToolSearch, Skill)

Runtime verification confirmed `allowedTools` and `disallowedTools` are
supported frontmatter keys in the Claude Code agent runtime (extracted from
binary documentation strings). YAML frontmatter parses correctly for all
three files. `make check-quiet` passes. No Batch C acceptance behavior changed.
