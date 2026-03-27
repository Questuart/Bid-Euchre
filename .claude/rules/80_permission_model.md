# Permission Model — Self-Modifying Permissions

> `.claude/settings.json` includes itself in the auto-accept list. This is
> intentional. This document explains why.

## Design Choice

The `permissions.allow` list in `.claude/settings.json` includes:

```
Edit(.claude/settings.json)
Write(.claude/settings.json)
```

This means agents can modify the file that controls which edits are
auto-accepted — a self-modifying permission pattern. An agent could, in
theory, widen its own permissions without user confirmation.

**This is intentional for fleet operations.**

## Why It Exists

Permission prompts in Claude Code are blocking — the agent halts and waits
for a human to approve each file write. In a multi-lane steward fleet with
4+ parallel author lanes, permission prompts cause **permission stalls**:
lanes freeze waiting for approval, throughput drops to zero, and the
operator must manually intervene on each lane.

PR #1708 (`fix(ops): add SKILL.md edit permission to prevent lane stalls`)
first addressed this for skill files. PR #1927 expanded auto-accept to the
full set of infrastructure files that agents routinely modify during
autonomous operation.

## Safety Net: Git Audit Trail

The safety mechanism is **not** the permission gate — it is the git history.

- Every change to `.claude/settings.json` is committed and pushed
- PRs require CI and review before merge
- Post-merge review hooks detect unexpected changes
- `git log --follow .claude/settings.json` shows the full change history
- The orchestrator can revert any problematic change

The git audit trail provides stronger protection than a permission prompt
because it is durable, reviewable, and reversible. A permission prompt is
a one-time gate that leaves no record once approved.

## Full Auto-Accept Permission Set

For reference, the complete set of paths that agents may edit without
user confirmation:

| Pattern | Purpose |
|---------|---------|
| `.claude/skills/**` | Skill definitions (workflow guidance) |
| `.claude/rules/**` | Rule files (this file, conventions) |
| `.claude/settings.json` | Hook config and permissions (self-modifying) |
| `MEMORY.md` | Cross-session project memory |
| `plans/**` | Plan files (governing plans, sub-plans, sessions) |

All other paths require explicit user approval or hook-based auto-accept
logic (e.g., `pre-bash-dispatch.sh`).

## Operator Guidelines

- **Do not remove** `.claude/settings.json` from the auto-accept list unless
  you are switching to a supervised (non-fleet) operating mode
- **Monitor** permission set changes via `git log .claude/settings.json`
- **Review** any PR that modifies `permissions.allow` — treat scope widening
  as a security-relevant change
- If a lane is compromised or misbehaving, the remediation is to revert the
  commit and park the lane, not to re-add permission gates

## References

- #1708 — Original permission stall fix (SKILL.md)
- #1927 — Expanded auto-accept to full infrastructure set
- #1931 — This documentation follow-up
- `.claude/rules/75_worktree_protection.md` — Related infrastructure protection
