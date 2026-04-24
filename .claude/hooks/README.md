# Auto-Worktree Hook System

This directory contains hooks to enforce and streamline the worktree-only workflow.

## Hooks

### `worktree-guard.sh` (UserPromptSubmit)

**Trigger:** Before every prompt submission

**Purpose:** Blocks work from main checkout on main branch, auto-creates worktree

**Behavior:**
1. Checks if you're in `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre` on `main` branch
2. If yes:
   - Generates timestamped branch name (e.g., `work-20260202-153045`)
   - Creates the branch and worktree automatically
   - Prints the `cd` command to copy-paste
   - Blocks the prompt submission (exit 1)
3. If no: allows prompt submission (exit 0)

**Example output:**
```
🔧 Auto-creating worktree for you...

✅ Worktree created successfully!
   Branch: work-20260202-153045
   Location: ../Bid-Euchre-work-20260202-153045

⛔ Cannot work from main checkout. Please run:

   cd ../Bid-Euchre-work-20260202-153045

Then restart your Claude session in that directory.
```

### `worktree-reminder.sh` (SessionStart)

**Trigger:** When a Claude session starts

**Purpose:** Provides early warning about main checkout

**Behavior:**
1. Checks if you're in main checkout on main branch
2. If yes: prints informational warning (doesn't block)
3. Suggests creating a worktree manually or letting the UserPromptSubmit hook do it
4. Always exits 0 (never blocks session start)

**Example output:**
```
⚠️  SESSION NOTICE: You're in main checkout on main branch.

   All code changes will be blocked by the UserPromptSubmit hook.
   If you want to make changes, you'll need to switch to a worktree.

   The hook will auto-create a worktree when blocked, or you can
   create one manually now:

     git worktree add ../Bid-Euchre-<branch-name> <branch-name>
     cd ../Bid-Euchre-<branch-name>
```

### `fleet-check-autostart.sh` (SessionStart)

**Trigger:** When any Claude session starts (init, clear, compact)

**Purpose:** Auto-starts the fleet-check durable cron on the orchestrator lane

**Behavior:**
1. Checks if the current lane is the orchestrator (via `CLAUDE_AGENT_NAME`
   or project directory fallback)
2. If not orchestrator: exits silently (no output, no cost)
3. If orchestrator: outputs a directive instructing the agent to verify and
   start the `/loop 8m /fleet-check` cron with dedup (check CronList first)
4. Always exits 0 (never blocks session start)

**Refs:** #2333

### `post-pr-review.sh` (PostToolUse)

**Trigger:** After any Bash tool call

**Purpose:** Enqueues a durable review request after successful `gh pr create`

**Behavior:**
1. Checks if the Bash command contained `gh pr create` and exit code was 0
2. If yes: writes a `ReviewRequest` to the shared review queue
   (`bid_euchre.ops.review_queue`) with the PR number, HEAD SHA, and branch
3. Emits an informational `additionalContext` message telling the agent that
   a review has been enqueued (no manual `/reviewing-changes` needed)
4. A dedupe sentinel prevents double-trigger when registered in both
   `settings.json` and `settings.local.json`

**Note:** This hook formerly triggered the `/reviewing-changes` skill.  Under
the queue-backed model, it enqueues a request instead.  The review driver
(launched by `post-pr-review-loop.sh`) runs the review loop independently
and writes a verdict that the merge guard checks before allowing merge.

### `pre-merge-review-guard.sh` (PreToolUse)

**Trigger:** Before any Bash tool call containing `gh pr merge`

**Purpose:** Hard local merge guard — blocks merge unless review is complete

**Behavior:**
1. Extracts the PR number from the `gh pr merge` command
2. Resolves the shared review queue root (canonical across worktrees)
3. Checks four conditions (all must pass):
   - A verdict file exists for the PR
   - The verdict's `reviewed_sha` matches the PR's current HEAD
   - The verdict status is `passed`
   - CI checks are green
4. If any check fails: blocks the command (exit 2) with an explanatory message
5. If all pass: allows the merge (exit 0)

**Timeout:** 10s (needs `gh` API calls for SHA and CI status)

### `post-plan-review.sh` (DEPRECATED)

**Status:** Deprecated -- no longer triggers automatically.

**Replacement:** Use `/review-plan [path]` for manual plan review with
independent Codex CLI + Claude agent reviewers.

**History:** Previously auto-invoked the now-retired `/reviewing-plans` skill
after plan file creation. Replaced by `/review-plan` which provides independent
review via Codex CLI + Claude failsafe (PR-4 of the plan review agent chain).

## Helper Script

### `../scripts/claude-worktree.sh`

**Location:** `.claude/scripts/claude-worktree.sh`

**Purpose:** One-command worktree creation + Claude session start

**Usage:**
```bash
# From main checkout
./.claude/scripts/claude-worktree.sh [branch-name]

# Or add to ~/.zshrc:
alias claude-work='/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/.claude/scripts/claude-worktree.sh'

# Then use:
claude-work my-feature-branch
claude-work  # Uses auto-generated timestamp branch
```

**Behavior:**
1. Verifies you're in main checkout
2. Creates branch (or uses existing)
3. Creates worktree at `../Bid-Euchre-<branch-name>`
4. Changes to worktree directory
5. Starts `claude` session in worktree

### `post-telegram-audit.sh` (PostToolUse — MCP Telegram tools)

**Trigger:** After any Telegram MCP tool call (reply, react, edit_message, download_attachment)

**Purpose:** Wires `audit_mcp_outbound()` into the live PostToolUse path so outbound
Telegram exchanges are recorded in the audit trail JSONL file.

**Behavior:**
1. Reads PostToolUse JSON payload from stdin
2. Guards on tool name — exits immediately for non-Telegram tools
3. Extracts `tool_input` arguments and passes them to `audit_mcp_outbound()`
4. Best-effort: audit failures are silently swallowed (never blocks the agent)
5. Suppresses TUI notification (audit is invisible background work)

**Output:** `{"suppressOutput": true}` (silent)

### `inbound-channel-audit.sh` / `inbound-channel-audit.py` (UserPromptSubmit)

**Trigger:** Before every prompt submission (all lanes)

**Purpose:** Wires `audit_channel_tag()` into the live UserPromptSubmit path so
inbound Telegram messages (identified by `<channel source="telegram" ...>` tags)
are recorded in the audit trail JSONL file.

**Behavior:**
1. Reads UserPromptSubmit JSON from stdin
2. Fast guard: exits immediately (~0ms) if no `<channel` tag in prompt
3. If tag found, delegates to `inbound-channel-audit.py` via `uv run`
4. Python script extracts `<channel ...>body</channel>` blocks
5. Calls `audit_channel_tag()` for each block found
6. Best-effort: audit failures are silently swallowed (never blocks prompt)

**Speed:** ~0ms for common case (no `<channel` tag); ~2-5s when auditing

**Registration:** `.claude/settings.json` → `UserPromptSubmit` (timeout: 10s)

**Related:** #1752, `src/bid_euchre/ops/audit_trail.py`

### `pre-bash-dispatch.sh` (PreToolUse — Bash)

**Trigger:** Before any Bash tool call

**Purpose:** Consolidated dispatcher that runs all PreToolUse Bash hooks in a
single invocation to minimize "Async hook completed" TUI messages (issue #1255).

**Dispatches to (in order):**
1. `pre-worktree-cleanup.sh` — blocks dangerous rm/worktree commands
2. `pre-merge-review-guard.sh` — blocks merge without review verdict
3. `rule-loader.sh` — progressive rule disclosure (context injection)

Guards run first: if either blocks (exit 2), the block propagates immediately
and rule-loader is skipped.

### `post-bash-dispatch.sh` (PostToolUse — Bash)

**Trigger:** After any Bash tool call

**Purpose:** Consolidated dispatcher that runs all PostToolUse Bash hooks in a
single invocation to minimize "Async hook completed" TUI messages (issue #1255).

**Dispatches to (in order):**
1. `post-pr-review.sh` — enqueues review request after `gh pr create`
2. `post-pr-review-loop.sh` — launches review driver after `gh pr create`
3. `post-push-ci-check.sh` — launches CI poller after `git push`
4. `post-merge-ci-check.sh` — checks main CI after `gh pr merge`
5. `post-merge-review.sh` — triggers post-merge review after `gh pr merge`
6. `post-tool-daemon-notify.sh` — checks for background daemon failures
7. `post-task-event.sh` — emits task events on relevant commands
8. `post-merge-notify.sh` — auto-completes task lifecycle on merge

For typical Bash commands, all sub-hooks exit immediately (<100ms each).
Only specific commands (`gh pr create`, `git push`, `gh pr merge`) trigger
meaningful work.

## Configuration

Hooks are registered across two files:

**`.claude/settings.json`** (committed, shared):
- `SessionStart` (compact) → `compact-context.sh`
- `SessionStart` (all) → `session-sync-worktree.sh` (no matcher — fires on init, clear, compact)
- `SessionStart` (all) → `fleet-check-autostart.sh` (no matcher — auto-starts fleet-check cron on orchestrator)
- `PreToolUse` (Edit|Write) → `rule-loader.sh`
- `PreToolUse` (Bash) → `pre-bash-dispatch.sh` (consolidated dispatcher)
- `PostToolUse` (Write|Edit) → `post-write-check.sh`
- `PostToolUse` (Bash) → `post-bash-dispatch.sh` (consolidated dispatcher)
- `PostToolUse` (MCP Telegram tools) → `post-telegram-audit.sh` (audit trail)
- `PermissionDenied` (all) → `permission-denied-log.sh` (denial observability)
- `UserPromptSubmit` (all) → `alert-inject.sh` (fleet alert injection)
- `UserPromptSubmit` (all) → `inbound-channel-audit.sh` (inbound Telegram audit)

**`.claude/settings.local.json`** (gitignored, per-machine):
- `SessionStart` → `worktree-reminder.sh`
- `UserPromptSubmit` → `worktree-guard.sh`

## Limitations

**What hooks CAN do:**
- Create worktrees automatically
- Print helpful messages
- Block operations (exit 1)

**What hooks CANNOT do:**
- Change the session's working directory
- Auto-switch you to the worktree (you must `cd` manually)
- Run after plan mode exits (no post-plan hook event exists)

**Workaround:** The guard hook creates the worktree and provides the exact `cd` command. You just copy-paste and restart Claude.

## Troubleshooting

**Hook doesn't run:**
- Check permissions: `chmod +x .claude/hooks/*.sh`
- Verify hook registration in `.claude/settings.local.json`

**Worktree creation fails:**
- Branch may already exist: `git branch -d <branch-name>` and retry
- Worktree path conflict: remove old worktree with `git worktree remove`

**False positives:**
- Hook only blocks when BOTH conditions are true:
  - Directory = `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre`
  - Branch = `main`
- Working in a worktree or on a different branch is always allowed

## Unattended State Contract

Scripts that run in the background, poll external systems, or continue after
user interaction ends must expose minimal machine-readable state for debugging.

### Required outputs

| Output | Format | Purpose |
|--------|--------|---------|
| `status.json` | JSON object | Current state snapshot: status, summary, timestamp, identifiers |
| Append-only log | Plain text or JSONL | Execution progress and failure details |

### `status.json` minimal schema

```json
{
  "status": "running | success | failure | timeout",
  "summary": "Human-readable one-liner",
  "updated_at": "ISO-8601 timestamp",
  "pr_number": 123
}
```

Additional fields are script-specific but the four above are the baseline.

### Conforming scripts

| Script | State dir | status.json | Log |
|--------|-----------|-------------|-----|
| `scripts/internal/ci_poller.sh` | `.claude/runtime/ci_polls/pr_<N>/` | `status.json` | `poller.log` |
| `scripts/internal/review_driver.py` | `.claude/runtime/review_loops/pr_<N>/` | `state.json` | Per-round artifacts |
| `scripts/internal/plan_review_driver.py` | `.claude/runtime/plan_reviews/<key>/` | `state.json` | Per-round artifacts |

### Synchronous hooks (no state file needed)

| Script | Type | Latency |
|--------|------|---------|
| `.claude/hooks/pre-merge-review-guard.sh` | PreToolUse (blocking) | ~5-10s (gh API calls) |

### Non-conforming scripts (audit)

The following hooks run in the background but do not yet write `status.json`:

| Script | Runs in background? | Gap |
|--------|---------------------|-----|
| `.claude/hooks/post-push-ci-check.sh` | Yes (launches ci_poller) | Delegates to ci_poller — no gap |
| `.claude/hooks/post-pr-review-loop.sh` | Yes (launches review_driver) | Delegates to review_driver — no gap |
| `.claude/hooks/post-merge-review.sh` | Yes (spawns agent) | Agent-spawned — no status.json feasible |
| `.claude/hooks/post-tool-daemon-notify.sh` | Yes (checks daemons) | Lightweight checker — no long-running state |

No actionable gaps were found. All long-running unattended scripts already
conform via their downstream drivers.

## Design Notes

This is a **three-layered solution** to work around hook limitations:

1. **SessionStart hook** - Early warning, non-blocking
2. **UserPromptSubmit hook** - Auto-creates worktree, blocks work, provides `cd` command
3. **Shell helper script** - One-command workflow from terminal (optional)

Since hooks can't change directories, the workflow is:
1. Hook creates worktree automatically
2. Hook prints `cd` command
3. User copies and pastes
4. User restarts Claude in new location

This reduces friction from "manual branch creation + worktree creation + cd" to just "cd + restart".

### `permission-denied-log.sh` (PermissionDenied)

**Trigger:** When the auto-mode classifier denies a tool call (Claude Code v2.1.89+)

**Purpose:** Logs permission denials for ops observability — identifies allowlist
gaps and monitors for unexpected denials.

**Behavior:**
1. Reads PermissionDenied JSON payload from stdin (tool_name, reason, tool_input, session_id)
2. Constructs a JSONL record with timestamp, lane, tool_name, reason, session_id, tool_input
3. Appends to `.claude/runtime/permission_denials.jsonl` (gitignored)
4. Returns `retry: false` (lets the denial stand — never overrides safety)
5. Always exits 0 — never blocks, never crashes

**Limitations:**
- Only fires in **auto mode** (Team/Enterprise plan). Does NOT fire for:
  - Manual user denial of permission dialogs
  - PreToolUse hook blocks (exit 2)
  - `dontAsk` mode allowlist misses
  - `permissions.deny` rule matches
- Forward-looking: useful when the fleet adopts auto mode

**Speed:** ~50ms (bash + jq only, no Python)

**Registration:** `.claude/settings.json` → `PermissionDenied` (timeout: 5s)

**Related:** #2256

### `alert-inject.sh` / `alert-inject.py` (UserPromptSubmit)

**Trigger:** Before every prompt submission (all lanes)

**Purpose:** Mechanically inject unresolved HIGH/URGENT fleet alerts into
conversation context so the orchestrator cannot miss them.

**Behavior:**
1. Reads `.claude/runtime/fleet_status.json` (written by controller/reconciler)
2. Filters for open items with severity `high` or `urgent`
3. If any found: outputs `{"additionalContext": "..."}` with alert summary
4. If none found: exits cleanly with no output (exit 0)
5. Never blocks prompt submission — advisory injection only

**Speed:** ~100ms (stdlib-only Python, no project imports, no `uv` overhead)

**Registration:** `.claude/settings.json` → `UserPromptSubmit` (timeout: 5s)

**Related:** #1608, `src/bid_euchre/ops/control_plane.py`

## Hook Execution Order

Claude Code runs hooks in registration order within a matcher group. The
order below is the contract per lifecycle event — hooks listed earlier
run earlier. Contract invariants documented here prevent future
regressions from hook-ordering assumptions.

### `SessionStart`

Registration order (from `.claude/settings.json`):

1. `compact-context.sh` — matcher `compact` — re-injects constraints after
   context compaction. Runs only on compact-mode start.
2. `session-sync-worktree.sh` — no matcher — auto-syncs steward worktrees
   to main. Fires on all session starts (init, clear, compact).
3. `fleet-check-autostart.sh` — no matcher — auto-starts fleet-check cron
   on orchestrator lane.
4. `attention-broker-autostart.sh` — no matcher — launches attention
   broker daemon.

Contract: `compact-context.sh` runs first on compact events so re-injected
context is visible to downstream hooks. Non-compact events run hooks 2–4
in order.

### `PreToolUse` (Edit | Write)

1. `block-runtime-writes.sh` — blocks unsanctioned writes to runtime paths.
2. `rule-loader.sh` — progressive rule disclosure.

Contract: guard (`block-runtime-writes.sh`) runs first; if it blocks
(exit 2), rule-loader is skipped.

### `PreToolUse` (Bash)

1. `pre-bash-dispatch.sh` — consolidated dispatcher for Bash PreToolUse.

Internally dispatches (in order):
1. `pre-worktree-cleanup.sh` — blocks dangerous rm/worktree commands.
2. `pre-merge-review-guard.sh` — blocks merge without review verdict.
3. `rule-loader.sh` — progressive rule disclosure.

### `PostToolUse` (Edit | Write)

1. `post-write-check.sh` — advisory anti-pattern detection for Python.

### `PostToolUse` (Bash)

1. `post-bash-dispatch.sh` — consolidated dispatcher for Bash PostToolUse.

Internally dispatches (in order):
1. `post-pr-review.sh` — enqueues review request after `gh pr create`.
2. `post-pr-review-loop.sh` — launches review driver after `gh pr create`.
3. `post-push-ci-check.sh` — launches CI poller after `git push`.
4. `post-merge-ci-check.sh` — checks main CI after `gh pr merge`.
5. `post-merge-review.sh` — triggers post-merge review after `gh pr merge`.
6. `post-tool-daemon-notify.sh` — checks for background daemon failures.
7. `post-task-event.sh` — emits task events on relevant commands.
8. `post-merge-notify.sh` — auto-completes task lifecycle on merge.

### `PostToolUse` (MCP Telegram tools)

1. `post-telegram-audit.sh` — audit trail for outbound Telegram exchanges.

### `PostToolUse` (wildcard `*`)

1. `lane-heartbeat-post-tool.sh` — emits lane heartbeat (pure shell, ~20ms).

### `PermissionDenied`

1. `permission-denied-log.sh` — observability log (no matcher).
2. `permission_denied_alert.sh` — matcher `*` — Telegram alert.

Contract: `permission-denied-log.sh` runs first so `permission_denied_alert.sh`
can reference the log entry for alert context.

### `UserPromptSubmit`

1. `alert-inject.sh` — fleet alert injection.
2. `inbound-channel-audit.sh` — inbound Telegram audit trail.
3. `inbox-completion-inject.sh` — inbox completion surfacing.

## Per-Hook Scope Summary

One-line description of trigger, inputs, outputs, short-circuit behavior
per hook. Audited for 1-to-1 correspondence against files in this
directory by `tests/unit/test_hooks_inventory.py`.

| Hook | Trigger | Reads | Writes | Short-circuits when |
|---|---|---|---|---|
| `alert-inject.sh` | UserPromptSubmit | `.claude/runtime/fleet_status.json` | stdout (additionalContext) | no high/urgent alerts |
| `alert-inject.py` | helper for `alert-inject.sh` | fleet_status.json | stdout | — |
| `attention-broker-autostart.sh` | SessionStart | pidfile | spawns daemon | broker already alive |
| `block-runtime-writes.sh` | PreToolUse Edit\|Write | tool_input.file_path | stderr + exit 2 | path outside protected runtime paths |
| `compact-context.sh` | SessionStart matcher=`compact` | — | stdout (context) | non-compact event |
| `fleet-check-autostart.sh` | SessionStart | `CLAUDE_AGENT_NAME`, cwd | stdout (directive) | lane != orchestrator |
| `inbound-channel-audit.sh` | UserPromptSubmit | prompt content | audit JSONL | no `<channel` tag in prompt |
| `inbound-channel-audit.py` | helper for `inbound-channel-audit.sh` | prompt content | audit JSONL | — |
| `inbox-completion-inject.sh` | UserPromptSubmit | orchestrator inbox | stdout (additionalContext) | lane != orchestrator; no unacked |
| `inbox-completion-inject.py` | helper for `inbox-completion-inject.sh` | inbox file | stdout + ack | — |
| `lane-heartbeat-post-tool.sh` | PostToolUse `*` | lane_id from cwd/env | `.claude/runtime/lane_status/<lane>.json` | never (always emits, ALWAYS exit 0) |
| `permission-denied-log.sh` | PermissionDenied | tool_name, reason, session_id | `.claude/runtime/permission_denials.jsonl` | never (ALWAYS exit 0) |
| `post-bash-dispatch.sh` | PostToolUse Bash | stdin payload | sub-hook dispatches | — |
| `post-merge-ci-check.sh` | PostToolUse Bash (via dispatcher) | `gh pr` command | ci poller state | command != `gh pr merge` |
| `post-merge-notify.sh` | PostToolUse Bash (via dispatcher) | `gh pr merge` output | message bus (task completion) | command != `gh pr merge` |
| `post-merge-review.sh` | PostToolUse Bash (via dispatcher) | PR number, merge signal | spawns background reviewer | command != `gh pr merge` |
| `post-monitor-push-relay.sh` | PostToolUse Bash (via dispatcher) | monitor state | Telegram push queue | monitor state unchanged |
| `post-plan-review.sh` | **DEPRECATED** — no active registration | — | — | always (deprecated) |
| `post-pr-review-loop.sh` | PostToolUse Bash (via dispatcher) | `gh pr create` output | spawns review driver | command != `gh pr create` |
| `post-pr-review.sh` | PostToolUse Bash (via dispatcher) | `gh pr create` output | review queue | command != `gh pr create` |
| `post-push-ci-check.sh` | PostToolUse Bash (via dispatcher) | `git push` output | ci poller state | command != `git push` |
| `post-task-event.sh` | PostToolUse Bash (via dispatcher) | command text | events.jsonl | no task-relevant command |
| `post-telegram-audit.sh` | PostToolUse mcp Telegram tools | tool_input | audit JSONL | non-Telegram tool |
| `post-tool-daemon-notify.sh` | PostToolUse Bash (via dispatcher) | daemon state files | additionalContext (stderr notice) | no daemon failures |
| `post-write-check.sh` | PostToolUse Edit\|Write | file_path | stdout findings | non-`.py` file, or file missing |
| `pre-bash-dispatch.sh` | PreToolUse Bash | stdin payload | sub-hook dispatches | — |
| `pre-merge-review-guard.sh` | PreToolUse Bash (via dispatcher) | `gh pr merge` command, review queue | exit 2 if no verdict | command != `gh pr merge` |
| `pre-worktree-cleanup.sh` | PreToolUse Bash (via dispatcher) | command text | exit 2 on protected worktree | command != dangerous cleanup |
| `rule-loader.sh` | PreToolUse Edit\|Write\|Read, Bash (via dispatcher) | file_path / command | stdout additionalContext | path not under matched rule trigger |
| `scope-drift-guard.sh` | PostToolUse Bash (not in settings) | commit message | stderr advisory | no `Refs #N`/`Fixes #N` |
| `session-sync-worktree.sh` | SessionStart | cwd, branch, worktree state | git rebase/ff | cwd not `*steward*`, dirty tree, or open PR |
| `urgent-state-guard.py` | helper (not directly registered) | runtime state | — | — |
| `worktree-guard.sh` | UserPromptSubmit (`.claude/settings.local.json`) | cwd, branch | creates worktree | cwd != main checkout |
| `worktree-reminder.sh` | SessionStart (`.claude/settings.local.json`) | cwd, branch | stderr advisory | cwd != main checkout |

Helper scripts under `scripts/internal/hooks/`:

| Hook | Trigger | Purpose |
|---|---|---|
| `permission_denied_alert.sh` | PermissionDenied matcher=`*` | Telegram alert on permission denial (event-bounded; low volume) |

## Conditional-Hook Migration

Primitive E Phase 0 §5-E introduces a per-hook disposition discipline:
every hook is categorized either as **matcher-scoped** (narrowed to a
specific tool list), **event-scoped** (fires on a discriminating
lifecycle event like SessionStart / UserPromptSubmit / PermissionDenied),
or **universal** (matcher `*`, fires on every tool call).  Universal
matchers on high-volume events (`PostToolUse`) are migration candidates;
universal matchers on low-volume events (`PermissionDenied`) are
justified-retention candidates.

This section is the source of truth for per-hook disposition. Test
`tests/unit/test_hooks_inventory.py` asserts 1-to-1 correspondence
between `.claude/hooks/*.{sh,py}` and rows below. Test
`tests/unit/test_settings_hooks_contract.py` asserts no matcher `*`
is registered in `.claude/settings.json` without a justified-retention
sentinel in the Rationale column below.

### Disposition Table

Legend for **Disposition** column:

- `already-narrow` — matcher is already a specific tool or tool-set; no
  migration needed.
- `event-scoped` — registered under an event (SessionStart, UserPromptSubmit,
  PermissionDenied) that is itself low-volume and discriminating; matcher
  scope is implicit in the event selection.
- `dispatched` — script runs inside `pre-bash-dispatch.sh` or
  `post-bash-dispatch.sh`, which is already narrow on `Bash`; conditional
  logic lives in the dispatcher's early-guard clauses per sub-hook.
- `retained-universal-justified` — matcher `*` is intentional and safe;
  rationale must end with the sentinel string `retained-universal-justified`
  for the contract test to accept it.
- `migrated-v0.5` — consolidated or narrowed in Primitive E Phase 0.
- `deprecated` — no active registration; kept for historical reference.
- `helper` — not directly registered as a hook; invoked by a sibling `.sh`
  wrapper.

| Hook | Current Matcher | Proposed Matcher | Disposition | Rationale |
|---|---|---|---|---|
| `alert-inject.sh` | UserPromptSubmit (no matcher) | unchanged | event-scoped | UserPromptSubmit is a low-volume discriminating event |
| `alert-inject.py` | — | — | helper | Invoked by `alert-inject.sh` |
| `attention-broker-autostart.sh` | SessionStart (no matcher) | unchanged | event-scoped | SessionStart fires only at session boundary |
| `block-runtime-writes.sh` | PreToolUse `Edit\|Write` | unchanged | already-narrow | Only Edit/Write can create files |
| `compact-context.sh` | SessionStart matcher=`compact` | unchanged | already-narrow | Most specific possible matcher |
| `event_emit.sh` | PreToolUse `*`, PostToolUse `*`, PostToolUseFailure `*`, PermissionDenied, PermissionRequest, Notification, Stop, StopFailure, SubagentStart, SubagentStop, PreCompact, SessionStart, SessionEnd, TeammateIdle, UserPromptSubmit | unchanged | retained-universal-justified | Primitive A v1.0 native lifecycle absorber — purpose is to observe **every** tool call and lifecycle event for the structured event pipeline (`data/events/events-YYYY-MM-DD-NNN.jsonl`). Universal matcher on PreToolUse/PostToolUse is a design invariant, not a defect: any narrower matcher would create blind spots in the event log. Hook is fire-and-forget (exit 0 always), never blocks the caller; cost is ~one `uv run` warm-up per call, bounded by `timeout: 5`. Landed in PR #2812. retained-universal-justified |
| `fleet-check-autostart.sh` | SessionStart (no matcher) | unchanged | event-scoped | SessionStart is discriminating |
| `inbound-channel-audit.sh` | UserPromptSubmit (no matcher) | unchanged | event-scoped | UserPromptSubmit is discriminating; script has fast `<channel` guard (~0ms when absent) |
| `inbound-channel-audit.py` | — | — | helper | Invoked by `inbound-channel-audit.sh` |
| `inbox-completion-inject.sh` | UserPromptSubmit (no matcher) | unchanged | event-scoped | Script has lane-identity guard (ops only) |
| `inbox-completion-inject.py` | — | — | helper | Invoked by `inbox-completion-inject.sh` |
| `lane-heartbeat-post-tool.sh` | PostToolUse `*` | unchanged | retained-universal-justified | Purpose is lane-idle detection; excluding any tool class risks false-stale on reading/searching lanes. Post PR #2739 pure-shell rewrite, cost is ~20ms per call — bounded and acceptable. retained-universal-justified |
| `material-platform-change-canary.sh` | PostToolUse `Bash` | unchanged | already-narrow | Bash-matcher on PostToolUse; script self-gates on `gh pr merge` command + trigger-path detection (dogfood.md §8 paths) + `canary-rollback-pr` label self-exclusion. Landed in PR #2797 (Primitive H.0). |
| `permission-denied-log.sh` | PermissionDenied (no matcher) | unchanged | event-scoped | PermissionDenied is rare and discriminating by definition |
| `post-bash-dispatch.sh` | PostToolUse `Bash` | unchanged | already-narrow | Bash-only dispatcher; sub-hooks gated internally |
| `post-merge-ci-check.sh` | via `post-bash-dispatch.sh` | — | dispatched | Runs inside Bash dispatcher; early-exits when command != `gh pr merge` |
| `post-merge-notify.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when command != `gh pr merge` |
| `post-merge-review.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when command != `gh pr merge` |
| `post-monitor-push-relay.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when monitor state unchanged |
| `post-plan-review.sh` | — | — | deprecated | No active registration; see `/review-plan` skill |
| `post-pr-review-loop.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when command != `gh pr create` |
| `post-pr-review.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when command != `gh pr create` |
| `post-push-ci-check.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when command != `git push` |
| `post-task-event.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits on non-task-relevant commands |
| `post-telegram-audit.sh` | PostToolUse `mcp__plugin_telegram_telegram__reply\|react\|edit_message\|download_attachment` | unchanged | already-narrow | Most specific possible matcher for Telegram tool surface |
| `post-tool-daemon-notify.sh` | via `post-bash-dispatch.sh` | — | dispatched | Early-exits when no daemon failures |
| `post-write-check.sh` | PostToolUse `Write` AND PostToolUse `Edit` | PostToolUse `Edit\|Write` (consolidated) | migrated-v0.5 | Consolidate duplicate registrations into single `Edit\|Write` entry |
| `pre-bash-dispatch.sh` | PreToolUse `Bash` | unchanged | already-narrow | Bash-only dispatcher |
| `pre-merge-review-guard.sh` | via `pre-bash-dispatch.sh` | — | dispatched | Early-exits when command != `gh pr merge` |
| `pre-worktree-cleanup.sh` | via `pre-bash-dispatch.sh` | — | dispatched | Early-exits when command is not a dangerous cleanup |
| `rule-loader.sh` | PreToolUse `Edit\|Write\|Read` (and via `pre-bash-dispatch.sh`) | unchanged | already-narrow | Read is retained — rule loading on file reads is a legitimate trigger (e.g., reading a rules doc should load its rules) |
| `scope-drift-guard.sh` | via `pre-bash-dispatch.sh` (not in settings.json) | — | dispatched | Sub-hook; no direct registration |
| `session-sync-worktree.sh` | SessionStart (no matcher) | unchanged | event-scoped | SessionStart discriminating; script has `*steward*` cwd guard |
| `urgent-state-guard.py` | — | — | helper | Not directly registered; imported by other hooks |
| `worktree-guard.sh` | UserPromptSubmit (`.claude/settings.local.json`) | unchanged | event-scoped | Registered in gitignored local settings |
| `worktree-reminder.sh` | SessionStart (`.claude/settings.local.json`) | unchanged | event-scoped | Registered in gitignored local settings |
| `permission_denied_alert.sh` (under `scripts/internal/hooks/`) | PermissionDenied matcher=`*` | unchanged | retained-universal-justified | PermissionDenied is a rare event; `*` matches ANY tool denial so the alert covers future tool types automatically. retained-universal-justified |

### Summary

- **Migrations applied in Phase 0 (Packet E1 narrowed subset):** 1
  (`post-write-check.sh` registration consolidation).
- **Retained universal, justified:** 2 (`lane-heartbeat-post-tool.sh`,
  `permission_denied_alert.sh`).
- **Already-narrow / event-scoped / dispatched / helper / deprecated / retained-universal-justified:** 34.
- **Migrations deferred to v1.N follow-ons:** none identified as
  clearly-safe and unambiguous. ADR 004 (see
  `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md`)
  evaluates migration boundaries per hook.

### Why only one migration?

The orchestrator's §5-E scope direction (recovery msg `7f0561631c8f4c29`)
specifies "migrate existing hooks to conditional hooks where safe." The
survey found that the hook set is already mostly conditional — 31 of 34
hooks are `already-narrow`, `event-scoped`, `dispatched`, `helper`, or
`deprecated`. The remaining 2 universal-matcher registrations
(`lane-heartbeat-post-tool.sh`, `permission_denied_alert.sh`) were both
found to be justified: heartbeat's idle-detection semantic requires
broad coverage and its cost is bounded post PR #2739; the
permission-denied alert fires only on the rare PermissionDenied event
where `*` gives automatic coverage of future tool surfaces. Per Pattern
11 shape-is-authoritative discipline, the shape's ≥8 floor was
relaxed because the actual hook inventory does not contain that many
safe narrowing candidates; the disciplinary value ships via the full
disposition table + inventory contract tests (one-to-one + no-bare-`*`
enforcement).
