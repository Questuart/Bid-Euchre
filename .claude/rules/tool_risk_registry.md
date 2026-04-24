# Tool Risk Registry

> Dual-envelope classification for every tool steward lanes may invoke.
> Per ADR 006, every tool is evaluated against BOTH the auto-mode
> classifier envelope AND the bypassPermissions envelope. Approval class
> may differ between envelopes; the registry captures both so Primitive
> B.1 adaptive dispatch can filter by envelope and so `PermissionDenied`
> events (Primitive A) carry a registry back-reference.

> Back-pointer: see `.claude/rules/80_permission_model.md` § Tool-risk
> registry for the operational guide to auto mode. This file is the
> *cross-envelope classification table*; `80_permission_model.md` is the
> *operational guide*. They coexist — do not merge.

## Version

`tool-risk-v1.0`

## Trigger

Initial registry version. Landed in Primitive B-exec.α (B.6 — tool risk
registry) per `plans/steward_platform/2_primitive_B/shaping.md` §5.1.
Covers every entry in `.claude/settings.json` `permissions.allow` as of
the landing commit. When `permissions.allow` changes, this registry
must be updated in the same PR; `agent_readability_lint.py check
tool-risk` BLOCKs on any allow-entry with no matching row.

## Expected effect

Primitive B.1 adaptive dispatch filters out lanes whose envelope fails
a task's required-tool set (§5.3 read contract). The
`.claude/hooks/permission-denied-log.sh` hook enriches every
`permission_denied` event with `approval_class_auto_mode`,
`approval_class_bypass`, and `registry_row_id` fields. Scaling signal:
≥95% of emitted `permission_denied` events carry a non-null
`registry_row_id` once the proving run is underway.

## Rollback

`git revert <commit SHA of this registry>` restores the prior state (no
tool_risk_registry.md). Trace signature that confirms rollback:
`permission_denied` events emitted after rollback carry
`registry_row_id = null` for every tool; `agent_readability_lint.py
check tool-risk` returns rule TR0 (registry missing). B.1 dispatch
falls back to model-tier filtering only.

## Approval classes

Four classes apply symmetrically across both envelopes:

- **`direct`** — tool executes without prompt; no operator involvement.
  The tool's impact is bounded and reversible under the envelope.
- **`approve`** — tool executes after classifier approval (auto-mode)
  or would require human confirmation (bypass); single-call gate.
  Under bypass-with-`--dangerously-skip-permissions` the gate is NOT
  enforced at runtime; the class reflects what the runtime gate
  *should* be and informs B.1 dispatch.
- **`edit`** — tool output requires human/classifier review before
  downstream consumption (e.g., a large-scope diff posted as a PR).
- **`reject`** — tool is not allowed under this envelope; B.1 dispatch
  refuses any lane whose envelope matches.

## Registry

Rows are grouped by tool family. Every entry in
`.claude/settings.json` `permissions.allow` appears in the `Tool`
column (backticked, exact string) so the TR4 allow-coverage lint can
grep-match cleanly.

### Read-type tools (always auto-approved — not in allow-list)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Read` | direct | direct | Read-only file access; no state change |
| `Glob` | direct | direct | Read-only pattern match over repo |
| `Grep` | direct | direct | Read-only content search |
| `LSP` | direct | direct | Read-only symbol/type lookup |
| `NotebookEdit` (read-only modes) | direct | direct | Read-only notebook inspection |

### File edits — infrastructure

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Edit(.claude/skills/**)` `Write(.claude/skills/**)` | direct | direct | Skill definitions; workflow guidance; reversible via git |
| `Edit(.claude/rules/**)` `Write(.claude/rules/**)` | direct | direct | Rule files; including this registry; reversible via git |
| `Edit(.claude/settings.json)` `Write(.claude/settings.json)` | approve (classifier gates self-modification; requires User Intent) | approve | Self-modifying; touches the permission model itself |
| `Edit(.claude/hooks/**)` `Write(.claude/hooks/**)` | direct | direct | Hook scripts; reversible via git; runtime-evaluated |
| `Edit(.claude/runtime/classifier_denials/**)` `Write(.claude/runtime/classifier_denials/**)` | direct | direct | Runtime log writes; non-committed artifacts |
| `Edit(.claude/runtime/lane_status/**)` `Write(.claude/runtime/lane_status/**)` | direct | direct | Runtime status writes; non-committed artifacts |

### File edits — project source and docs

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Edit(MEMORY.md)` `Write(MEMORY.md)` | direct | direct | Cross-session memory; reversible via git |
| `Edit(plans/**)` `Write(plans/**)` | direct | direct | Governing plans, sub-plans, sessions; reversible via git |
| `Edit(src/**)` `Write(src/**)` | direct | direct | Project source; reversible via git; CI + review gate |
| `Edit(tests/**)` `Write(tests/**)` | direct | direct | Test suite; reversible via git; CI + review gate |
| `Edit(scripts/**)` `Write(scripts/**)` | direct | direct | Blessed tooling; reversible via git |
| `Edit(experiments/**)` `Write(experiments/**)` | direct | direct | Experiment configs + runner; reversible via git |
| `Edit(docs/**)` `Write(docs/**)` | direct | direct | Documentation; reversible via git |

### File edits — sensitive paths (outside `permissions.allow`)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Write(~/.claude/**)` | approve (classifier gates; requires User Intent) | reject | Self-modification of user-scope settings (autoMode.environment) |
| `Edit(data/runs/**)` `Write(data/runs/**)` | reject | reject | Never-committed generated artifacts; writes here violate data policy |
| `Edit(data/reports/**)` `Write(data/reports/**)` | reject | reject | Never-committed generated artifacts; writes here violate data policy |
| `Edit(data/models/**)` `Write(data/models/**)` | reject | reject | Never-committed generated artifacts; writes here violate data policy |

### Git (version control)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(git *)` | direct | direct | Covers status/diff/log/fetch/add/commit/push-to-working-branch; destructive sub-commands below are classifier-gated at invocation time even though the settings pattern is broad |
| `Bash(git push --force)` | approve | reject | Destructive — overwrites remote history |
| `Bash(git push --force main)` | reject | reject | Destructive — overwrites shared main; never auto-approved |
| `Bash(git reset --hard)` | approve | reject | Destructive — local work loss |
| `Bash(git clean -f)` | approve | reject | Destructive — unstages + removes untracked files |
| `Bash(git branch -D)` | approve | reject | Destructive — unreachable branch deletion |
| `Bash(git worktree remove)` | approve (classifier checks persistent-worktree list) | reject | Destructive — removes worktree; protected paths enumerated in `.claude/rules/75_worktree_protection.md` |
| `Bash(git worktree prune)` | reject | reject | Indiscriminate — removes entries for temporarily-unmounted worktrees per `75_worktree_protection.md` |

### GitHub CLI

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(gh *)` | direct | direct | Covers read subcommands (pr view, issue view, api GET); state-changing subcommands below gate separately at invocation time |
| `Bash(gh pr create)` | direct | direct | State change is gated by review-driver merge guard downstream |
| `Bash(gh pr merge)` | approve (merge-guard + classifier) | reject | State change — writes to shared history; pre-merge-review-guard.sh enforces |
| `Bash(gh pr close)` | approve | reject | State change — closes PR |
| `Bash(gh issue close)` | approve | reject | State change — closes issue |
| `Bash(gh api --method DELETE)` `Bash(gh api --method POST)` `Bash(gh api --method PATCH)` | approve | reject | State change — arbitrary GitHub API writes |

### Build + test tooling (blessed)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(make *)` | direct | direct | Blessed project tooling (check-gated, test, lint, etc.); reversible; no network state change |
| `Bash(uv run *)` | direct | direct | Blessed Python runner; reversible; no persistent state change |
| `Bash(uv sync *)` | direct | direct | Dependency sync; writes `.venv/`; reversible via re-sync |
| `Bash(ruff *)` | direct | direct | Lint + format; read-only or local-file rewrites |
| `Bash(python -m pytest *)` | direct | direct | Test runner; no persistent state change |
| `Bash(python scripts/*)` | direct | direct | Blessed internal scripts; classifier inspects argv for destructive flags |
| `Bash(python experiments/*)` | direct | direct | Experiment runner; writes to `data/runs/` which is not committed |
| `Bash(codex *)` | direct | direct | Review tool; read-only repo access; no state change |

### Unix read + trivial utilities

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(cat *)` | direct | direct | Read-only |
| `Bash(head *)` | direct | direct | Read-only |
| `Bash(tail *)` | direct | direct | Read-only (ignoring `tail -f` stalls — classifier flags if present) |
| `Bash(diff *)` | direct | direct | Read-only comparison |
| `Bash(echo *)` | direct | direct | Side-effect-free; redirect-to-file is classifier-gated at invocation time |
| `Bash(env *)` | direct | direct | Read-only (arg-less); env modification below |
| `Bash(pwd *)` | direct | direct | Read-only |
| `Bash(ls *)` | direct | direct | Read-only |
| `Bash(wc *)` | direct | direct | Read-only |
| `Bash(mkdir *)` | direct | direct | Local directory creation; reversible via `rmdir` |
| `Bash(sleep *)` | direct | direct | No side effect beyond time |

### Tmux (orchestration IPC)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(tmux send-keys *)` | approve (orchestrator-only; classifier checks lane identity) | approve | Orchestrator-only IPC surface; sending keys to the wrong lane is disruptive but reversible |
| `Bash(tmux capture-pane *)` | direct | direct | Read-only pane snapshot |
| `Bash(tmux list-*)` | direct | direct | Read-only (list-sessions, list-windows, list-panes) |
| `Bash(tmux display-message *)` | direct | direct | Read-only status query |
| `Bash(tmux kill-session)` `Bash(tmux kill-server)` | approve | reject | Destructive — ends lane work; use `respawn-pane -k --continue` instead |
| `Bash(tmux respawn-pane *)` | approve | reject | Destructive — kills running lane; state-json + `--continue` mitigates |

### Destructive and exfiltrating patterns (outside `permissions.allow`)

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `Bash(rm -rf *)` | approve | reject | Destructive — data loss; narrow paths may clear |
| `Bash(curl *)` piped to `bash` / `sh` | reject | reject | Exfil + arbitrary execution — never sanctioned; classifier matches any curl-pipe-bash pattern |
| `Bash(wget *)` piped to `bash` / `sh` | reject | reject | Exfil + arbitrary execution — never sanctioned; classifier matches any wget-pipe-bash pattern |
| `Bash(chmod +x *)` | approve | reject | Privilege change — auditable via git |
| `Bash(sudo *)` | reject | reject | Privilege escalation — never sanctioned in fleet |
| `Bash(export <CREDENTIAL>=...)` | reject | reject | Credential exfil risk; use env files instead |

### MCP surfaces

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `mcp__github__get_*` `mcp__github__list_*` `mcp__github__search_*` `mcp__github__pull_request_read` `mcp__github__issue_read` | direct | direct | Read-only GitHub API |
| `mcp__github__push_files` `mcp__github__create_repository` `mcp__github__delete_file` `mcp__github__fork_repository` | approve | reject | State change — writes to GitHub |
| `mcp__github__create_pull_request` `mcp__github__update_pull_request` `mcp__github__add_issue_comment` `mcp__github__add_comment_to_pending_review` | approve | reject | State change — writes to GitHub |
| `mcp__github__merge_pull_request` | approve | reject | State change — merges PR; bypass merge-guard if invoked directly |
| `mcp__memory__add_observations` `mcp__memory__create_entities` `mcp__memory__create_relations` `mcp__memory__delete_*` | direct | direct | Local memory graph writes; reversible |
| `mcp__memory__search_nodes` `mcp__memory__read_graph` `mcp__memory__open_nodes` | direct | direct | Read-only memory graph |
| `mcp__playwright__browser_*` (read: `browser_snapshot`, `browser_console_messages`, `browser_network_requests`) | direct | direct | Read-only browser observation |
| `mcp__playwright__browser_*` (write: `browser_click`, `browser_type`, `browser_navigate`, `browser_evaluate`, `browser_fill_form`) | approve | reject | Arbitrary web interaction; exfil risk via `browser_evaluate` |

### Web surfaces

| Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
|---|---|---|---|
| `WebFetch` | direct | direct | Read-only; classifier inspects URL against `autoMode.environment` trust envelope |
| `WebSearch` | direct | direct | Read-only |

## Triage

Tools observed in `data/events/events-*.jsonl` (once Primitive A is
live) that have no registry row are flagged by `check tool-risk` TR4
at the next CI run. Operator adds the row with a classification
rationale in Notes; no backfill of historical events is required.

## References

- `plans/steward_platform/2_primitive_B/shaping.md` §5 — source of this
  registry's schema and lint rules
- `.claude/rules/80_permission_model.md` — operational guide to auto
  mode; dual-envelope safety comparison table
- `.claude/rules/75_worktree_protection.md` — persistent worktree list
  referenced by `git worktree remove` row
- `ADR 006` (`.claude/ADR-006-dual-envelope-safety-model.md`) —
  dual-envelope safety model that motivates this registry
- `plans/steward_platform/verification_contract/map.md` — Pattern 10
  surface for every B.6 deliverable
