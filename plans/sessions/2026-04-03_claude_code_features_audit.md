# Research: Claude Code Auto-Accept + Recent Features Audit

> **Issue:** [#2249](https://github.com/Questuart/Bid-Euchre/issues/2249)
> **Date:** 2026-04-03
> **Lane:** analyst-a
> **Task:** 97ff6914ed50
> **Companion:** [env flags research](2026-04-03_claude_code_env_flags_research.md) (#2244)
> **Fleet version:** Claude Code 2.1.91
> **Status:** COMPLETE

## Executive Summary

Our steward fleet currently uses `permissions.allow` patterns in
`.claude/settings.json` to prevent permission stalls. This is the **correct
approach** for our use case — it provides granular, auditable, version-controlled
permission management. The newer `auto` mode (classifier-based, March 2026) is
not a replacement but could be a useful complement. Several other recently
released features are directly relevant to fleet operations.

**Key recommendations:**
1. Keep `permissions.allow` as primary permission mechanism (no change)
2. Evaluate `auto` mode as a fallback for unlisted tools (requires Team/Enterprise plan)
3. Add `defaultMode: "acceptEdits"` to settings.json for interactive sessions
4. Adopt 5 new env flags in steward-session.sh (per companion #2244 research)
5. Evaluate plugin system for fleet-specific extensions
6. Monitor 1M context window benefits — may allow raising auto-compact threshold

---

## Part 1: Auto-Accept Evaluation

### 1.1 Permission Mechanisms — Complete Landscape

Claude Code provides **six** distinct mechanisms for controlling permission
prompts, from most granular to most permissive:

| # | Mechanism | Granularity | Persistence | Safety | Fleet Suitability |
|---|-----------|-------------|-------------|--------|-------------------|
| 1 | `permissions.allow` in settings.json | Per-tool + file pattern | Permanent, version-controlled | **Best** | **Current — keep** |
| 2 | `--allowedTools` / `--disallowedTools` CLI flags | Per-tool + pattern | Session only | Good | Useful for one-off sessions |
| 3 | `defaultMode: "acceptEdits"` in settings.json | All file edits | Permanent | Good | Recommended addition |
| 4 | `auto` mode (classifier) | AI-evaluated per call | Session (until mode change) | Good | Evaluate as complement |
| 5 | `acceptEdits` mode (Shift+Tab) | All file edits | Session only | Medium | Interactive use only |
| 6 | `--dangerously-skip-permissions` | Everything | Session only | **None** | **Never for fleet** |

### 1.2 Deep Dive: Each Mechanism

#### Mechanism 1: `permissions.allow` (Our Current Approach)

**How it works:** Pattern-based allowlist in `.claude/settings.json`. Rules are
evaluated in order: deny > ask > allow. First match wins.

```json
{
  "permissions": {
    "allow": [
      "Edit(src/**)",
      "Write(src/**)",
      "Bash(git *)",
      "Bash(make *)"
    ]
  }
}
```

**Strengths for fleet:**
- Version-controlled in git — full audit trail
- Granular: per-tool, per-file-pattern, per-command-pattern
- Shared across all lanes via project settings
- Self-documenting (the allowlist IS the permission policy)
- Survives session restarts, compactions, reconnects

**Weaknesses:**
- Reactive: new tools/paths cause stalls until added to allowlist
- Pattern coverage gaps: we've hit this with review lane (#2238) and
  skill files (#1708, #1927)
- No wildcard for "all Bash commands" without enumerating patterns

**Current coverage gaps identified:**
- `.claude/runtime/review_state/**` — added in #2238 fix
- New MCP tools — must be added as they're adopted
- Any new tool types added by Claude Code updates

#### Mechanism 2: `--allowedTools` / `--disallowedTools` CLI Flags

**How it works:** Per-session overrides passed at startup.

```bash
claude --allowedTools "Bash(npm *)" "Grep" "Glob"
claude --disallowedTools "Bash(rm *)" "Bash(sudo *)"
```

**Fleet relevance:** Low for normal operation (settings.json is better), but
useful for:
- One-off debugging sessions with elevated permissions
- Testing new tool patterns before adding to settings.json
- Restricting a specific lane during incident response

**Key detail:** `--disallowedTools` always takes precedence over
`--allowedTools`, providing a safety floor.

#### Mechanism 3: `defaultMode` in settings.json

**How it works:** Sets the default permission mode when Claude Code starts.

```json
{
  "permissions": {
    "defaultMode": "acceptEdits"
  }
}
```

**Valid values:** `default`, `acceptEdits`, `plan`, `auto`

**Fleet relevance:** Medium. Setting `acceptEdits` as default would auto-approve
all file edits without prompting, while still requiring approval for Bash
commands and other tools. This is a reasonable middle ground — our
`permissions.allow` patterns would still control Bash commands, and file edits
would never stall.

**Recommendation:** Add `"defaultMode": "acceptEdits"` to project settings.json.
This eliminates file-edit permission stalls without weakening Bash command
controls.

#### Mechanism 4: `auto` Mode (Classifier-Based)

**How it works:** Launched March 24, 2026. A separate AI classifier model
evaluates each tool call before execution. The classifier:
- Reviews conversation context and the proposed action
- Blocks actions that escalate beyond task scope
- Blocks actions targeting unrecognized infrastructure
- Detects and blocks prompt injection attempts
- Never sees tool results (injection-resistant by design)

**Activation:**
```bash
claude --enable-auto-mode          # Enable in mode cycle
# Then Shift+Tab to cycle to "auto"
# Or:
claude --permission-mode auto      # Start directly in auto mode
claude -p "task" --permission-mode auto  # Headless auto mode
```

**Availability:** Team plan (v2.1.38+) and Enterprise plan. **Not available**
for Pro/Max individual subscriptions or third-party providers (Bedrock, Vertex).

**Fleet relevance:** Potentially high as a complement to `permissions.allow`.
Auto mode catches tools/paths not covered by our allowlist patterns, providing
a safety net for the "reactive gap" problem.

**Tradeoffs:**
| Pro | Con |
|-----|-----|
| Catches unlisted tool/path combinations | Adds latency per tool call (classifier overhead) |
| Injection-resistant design | Token cost increase (small) |
| No maintenance burden (adapts automatically) | Requires Team/Enterprise plan |
| Works in headless mode (`-p`) | Classifier denials abort headless sessions |
| PermissionDenied hook allows retry logic | Not available on Haiku or claude-3 models |

**Critical detail for fleet:** In headless mode (`claude -p`), if the classifier
triggers a fallback, the session **aborts** since there's no user to prompt.
This means auto mode in headless fleet lanes could cause unexpected session
termination. The `PermissionDenied` hook (v2.1.89+) can mitigate this by
returning `{retry: true}`.

#### Mechanism 5: `acceptEdits` Mode (Interactive)

**How it works:** Press Shift+Tab to cycle to "Accept edits on". Auto-accepts
all file edit proposals. Does NOT auto-accept Bash commands, MCP tools, or
other state-changing operations.

**Fleet relevance:** Low — same as `defaultMode: "acceptEdits"` but requires
manual activation per session.

#### Mechanism 6: `--dangerously-skip-permissions`

**How it works:** Skips ALL permission prompts. Every file write, every Bash
command, every tool call runs without approval.

```bash
claude --dangerously-skip-permissions  # Nuclear option
```

**Recent breaking change (v2.1.78, Feb 2026):** Added protected directory
system — `.git/` and `.claude/` paths now trigger prompts even with this flag
enabled. This partially broke the flag for CI/automation use cases.

**Fleet relevance:** **NEVER USE.** Reasons:
- All subagents inherit full autonomous access — can't scope per-lane
- No audit trail for which actions were auto-approved
- No protection against prompt injection
- Protected paths override means it's not even fully functional
- Anthropic explicitly recommends auto mode as replacement

### 1.3 Recommendation for Steward Fleet

**Primary: Keep `permissions.allow` (no change)**

Our current approach is the gold standard for fleet permission management:
- Granular, auditable, version-controlled
- Self-documenting permission policy
- Works identically across all 19 lanes
- No external dependencies (no classifier, no plan tier)

**Addition 1: Set `defaultMode: "acceptEdits"`**

Add to `.claude/settings.json`:
```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [ /* existing patterns */ ]
  }
}
```

This eliminates all file-edit permission stalls. Our `permissions.allow` patterns
still control Bash commands and other tools. Risk: minimal — file edits are
the least dangerous operation class, and all edits are committed via git
(audit trail).

**Addition 2: Evaluate `auto` mode (if on Team/Enterprise plan)**

If our Anthropic plan supports auto mode, test it on one lane:
```bash
claude --enable-auto-mode --permission-mode auto
```

Monitor for:
- Classifier false positives (blocking legitimate operations)
- Latency impact on tool calls
- Session abort frequency in headless mode
- Token cost delta

If stable, consider as fleet default for interactive lanes (not headless).

**Addition 3: Add PermissionDenied hook (defensive)**

Even without auto mode, add a PermissionDenied hook that logs classifier
denials for observability:

```json
{
  "hooks": {
    "PermissionDenied": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/permission-denied-log.sh",
        "timeout": 5
      }]
    }]
  }
}
```

### 1.4 Permission Stall Prevention Checklist

Based on historical stalls (#2238, #1708, #1927):

- [x] `.claude/skills/**` — Edit + Write allowed
- [x] `.claude/rules/**` — Edit + Write allowed
- [x] `.claude/settings.json` — Edit + Write allowed (self-modifying)
- [x] `.claude/hooks/**` — Edit + Write allowed
- [x] `.claude/runtime/**` — Edit + Write allowed
- [x] `MEMORY.md` — Edit + Write allowed
- [x] `plans/**` — Edit + Write allowed
- [x] `src/**`, `tests/**`, `scripts/**`, `experiments/**`, `docs/**` — Edit + Write allowed
- [x] Common Bash patterns: `git`, `gh`, `make`, `uv run`, `ruff`, `codex`, `pwd`, `ls`, `wc`, `mkdir`
- [ ] **Gap:** No `Bash(cat *)` — could stall on cat commands
- [ ] **Gap:** No `Bash(python *)` — lanes using raw python instead of `uv run` would stall
- [ ] **Gap:** No MCP tool patterns — new MCP tools could stall
- [ ] **Gap:** `defaultMode` not set — file edits for uncovered paths stall

---

## Part 2: Recent Features Audit

### 2.1 Feature Audit Table

Features from Claude Code releases January–April 2026, evaluated for fleet
relevance.

| Feature | Version / Date | Category | Fleet Relevance | Recommendation |
|---------|---------------|----------|-----------------|----------------|
| **Auto mode** (classifier permissions) | v2.1.38+ / Mar 24, 2026 | Permissions | **High** | Evaluate on one lane |
| **PermissionDenied hook** | v2.1.89 / Mar 2026 | Hooks | **High** | Add to settings.json |
| **Deferred permissions** (`defer` in PreToolUse) | v2.1.89 / Mar 2026 | Hooks | **High** | Evaluate for headless ops |
| **1M context window GA** | Mar 2026 | Context | **High** | Already available; evaluate raising auto-compact |
| **Computer use** | Mar 23, 2026 | Capability | Medium | Not needed for CLI fleet |
| **Remote control** | Feb 2026 | Session | Medium | Could enable mobile monitoring |
| **Plugin system** (public beta) | 2026 | Extensibility | Medium | Evaluate for fleet-specific plugins |
| **Named subagents** in @-mention | v2.1.89 / Mar 2026 | Agents | Medium | Useful for orchestrator dispatch |
| **MCP_CONNECTION_NONBLOCKING** | v2.1.89 / Mar 2026 | MCP | Medium | Evaluate for `-p` mode |
| **X-Claude-Code-Session-Id header** | Mar 2026 | Observability | Medium | Useful for proxy/monitoring |
| **Server-side compaction** (beta) | 2026 | Context | Medium | Monitor for GA |
| **Managed settings / MDM** | 2026 | Enterprise | Low | Not needed (we use git) |
| **Cowork / scheduled tasks** | 2026 | Scheduling | Low | We have our own `/loop` |
| **/powerup** (interactive lessons) | Mar 2026 | Learning | Low | Not relevant for fleet |
| **/buddy** (April Fools) | Apr 1, 2026 | Fun | None | Ignore |
| **CLAUDE_CODE_NO_FLICKER** | v2.1.89 / Mar 2026 | UI | Already set | No change |
| **Voice STT** (10 new languages) | Mar 2026 | Input | None | Not relevant for CLI fleet |
| **.jj/.sl VCS exclusion** | Mar 2026 | VCS | None | Not using Jujutsu/Sapling |

### 2.2 Deep Dive: High-Relevance Features

#### Deferred Permissions (v2.1.89+)

**What:** PreToolUse hooks can return `permissionDecision: "defer"`, causing
the process to exit with `stop_reason: "tool_deferred"`. The calling process
reads `deferred_tool_use` from the SDK result, handles the decision externally,
then resumes with `claude -p --resume <session-id>`.

**Fleet relevance:** This enables a pattern where headless lane processes can
pause for human/orchestrator review of specific operations, rather than
aborting entirely. Useful for:
- Orchestrator-mediated approval for high-risk operations
- Fleet-wide policy gates (e.g., "no force pushes without orchestrator ack")
- Graceful handling of classifier denials in auto mode

**Implementation complexity:** Medium — requires changes to how we launch
headless sessions and orchestrator logic to process deferred tool calls.

#### 1M Context Window GA

**What:** 1M token context window is now generally available for Opus 4.6 and
Sonnet 4.6 with no pricing premium. Anthropic reports 15% decrease in
compaction events across real usage.

**Fleet relevance:** Our current `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000`
setting is conservative relative to the 1M window. We could:
- Raise to 300K–400K for longer uninterrupted work sessions
- Monitor compaction frequency to find the sweet spot
- Benefit from fewer compaction-related context losses

**Recommendation:** Test raising to 300K on one lane, measure compaction
frequency and session quality over a 24h run.

#### Named Subagents

**What:** Subagents can now be referenced by name in @-mention typeahead.

**Fleet relevance:** Our orchestrator dispatches to named lanes. Named subagents
could improve intra-session agent management, making it easier to reference
and coordinate sub-tasks within a single lane's session.

#### MCP_CONNECTION_NONBLOCKING

**What:** Setting `MCP_CONNECTION_NONBLOCKING=true` prevents MCP server
connection failures from blocking Claude Code startup in `-p` mode.

**Fleet relevance:** Our fleet uses MCP servers (Telegram, GitHub, memory).
If an MCP server is temporarily unavailable, this flag prevents the entire
lane from stalling at startup. This is a resilience improvement.

**Recommendation:** Add to steward-session.sh env flags.

### 2.3 Deprecations and Breaking Changes

| Change | Version | Impact on Fleet | Action Required |
|--------|---------|-----------------|-----------------|
| Protected paths override `--dangerously-skip-permissions` for `.git/` and `.claude/` | v2.1.78 (Feb 2026) | None — we don't use this flag | None |
| Legacy SDK entrypoint removed (use `@anthropic-ai/claude-agent-sdk`) | 2026 | None — we don't use SDK directly | None |
| `TaskOutput` tool deprecated (use `Read` on output file) | 2026 | **Low** — update any scripts using TaskOutput | Audit skill files |
| Output styles deprecated then un-deprecated | 2026 | None — we don't use output styles | None |
| Tool renaming: `LSTool` → `LS`, `View` → `Read` | 2026 | **Low** — check hook matchers | Audit hook matchers |
| Windows managed settings path change | Mar 2026 | None — macOS fleet | None |

**Action items:**
1. Verify hook matchers in settings.json use current tool names (`Read` not `View`)
2. Check if any skills reference `TaskOutput` — migrate to `Read`

### 2.4 Features NOT to Adopt

| Feature | Why Not |
|---------|---------|
| `--dangerously-skip-permissions` | No safety net, subagent inheritance, partially broken |
| Computer use | CLI fleet doesn't need GUI interaction |
| Cowork | We have our own scheduling (`/loop`, cron) |
| Managed settings / MDM | Overkill for single-machine fleet; git-based settings work |
| `DISABLE_AUTO_COMPACT` | Compaction is critical for fleet longevity |
| `CLAUDE_CODE_SIMPLE` | Would strip tools from lanes |

---

## Part 3: Priority Adoption List

### Tier 1 — Immediate (This Sprint)

| # | Change | Files | Risk | Effort |
|---|--------|-------|------|--------|
| 1 | Add `defaultMode: "acceptEdits"` to settings.json | `.claude/settings.json` | Low | 5 min |
| 2 | Add 5 fleet env flags to steward-session.sh (per #2244 research) | `.claude/tmux/steward-session.sh` | Low | 1 PR |
| 3 | Add `MCP_CONNECTION_NONBLOCKING=true` to steward-session.sh | `.claude/tmux/steward-session.sh` | Low | Combine with #2 |
| 4 | Audit hook matchers for tool renames (`View`→`Read`, `LSTool`→`LS`) | `.claude/settings.json` | Low | 15 min |
| 5 | Fill permission gaps: add `Bash(cat *)`, `Bash(python *)` | `.claude/settings.json` | Low | 5 min |

### Tier 2 — Short-Term (Next 2 Weeks)

| # | Change | Dependency | Effort |
|---|--------|------------|--------|
| 6 | Add PermissionDenied hook for observability | Hook script | 1 PR |
| 7 | Test raising auto-compact to 300K on one lane | Monitor for 24h | 1 day |
| 8 | Evaluate auto mode on one interactive lane | Team/Enterprise plan | 2 days |
| 9 | Audit skills for `TaskOutput` references | Grep + fix | 30 min |

### Tier 3 — Evaluate (Next Month)

| # | Change | Dependency | Effort |
|---|--------|------------|--------|
| 10 | Evaluate deferred permissions for orchestrator-mediated approval | Orchestrator changes | 1 week |
| 11 | Evaluate plugin system for fleet-specific extensions | Plugin API stability | 1 week |
| 12 | Evaluate remote control for mobile fleet monitoring | Remote control GA | 2 days |

---

## Part 4: Immediate Config Changes

### 4.1 settings.json Updates

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Edit(.claude/skills/**)",
      "Write(.claude/skills/**)",
      "Edit(.claude/rules/**)",
      "Write(.claude/rules/**)",
      "Edit(.claude/settings.json)",
      "Write(.claude/settings.json)",
      "Edit(.claude/hooks/**)",
      "Write(.claude/hooks/**)",
      "Edit(.claude/runtime/**)",
      "Write(.claude/runtime/**)",
      "Edit(.claude/runtime/review_state/**)",
      "Write(.claude/runtime/review_state/**)",
      "Edit(MEMORY.md)",
      "Write(MEMORY.md)",
      "Edit(plans/**)",
      "Write(plans/**)",
      "Edit(src/**)",
      "Write(src/**)",
      "Edit(tests/**)",
      "Write(tests/**)",
      "Edit(scripts/**)",
      "Write(scripts/**)",
      "Edit(experiments/**)",
      "Write(experiments/**)",
      "Edit(docs/**)",
      "Write(docs/**)",
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(make *)",
      "Bash(uv run *)",
      "Bash(uv sync *)",
      "Bash(ruff *)",
      "Bash(codex *)",
      "Bash(pwd *)",
      "Bash(ls *)",
      "Bash(wc *)",
      "Bash(mkdir *)",
      "Bash(cat *)",
      "Bash(python *)",
      "Bash(head *)",
      "Bash(tail *)",
      "Bash(diff *)",
      "Bash(env *)",
      "Bash(echo *)",
      "Bash(tmux *)",
      "Bash(sleep *)"
    ]
  }
}
```

**New additions** (vs current):
- `defaultMode: "acceptEdits"` — eliminates file-edit stalls for uncovered paths
- `Bash(cat *)` — common read operation, frequently used
- `Bash(python *)` — fallback when `uv run` isn't used
- `Bash(head *)`, `Bash(tail *)` — common file inspection
- `Bash(diff *)` — common comparison
- `Bash(env *)` — environment inspection
- `Bash(echo *)` — common output/test
- `Bash(tmux *)` — orchestrator lane management
- `Bash(sleep *)` — timing operations

### 4.2 steward-session.sh Additions

Per companion research (#2244), add after the existing
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` line:

```bash
# Fleet UX: suppress terminal title changes in 19-pane layout
tmux set-environment -t "$SESSION" CLAUDE_CODE_DISABLE_TERMINAL_TITLE "1"

# Fleet stability: prevent auto-updates during active sessions
tmux set-environment -t "$SESSION" DISABLE_AUTOUPDATER "1"

# Fleet autonomy: suppress interactive feedback surveys
tmux set-environment -t "$SESSION" CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY "1"

# Fleet autonomy: suppress cost warning messages
tmux set-environment -t "$SESSION" DISABLE_COST_WARNINGS "1"

# Fleet resilience: auto-resume interrupted turns
tmux set-environment -t "$SESSION" CLAUDE_CODE_RESUME_INTERRUPTED_TURN "1"

# Fleet resilience: non-blocking MCP connections for headless startup
tmux set-environment -t "$SESSION" MCP_CONNECTION_NONBLOCKING "true"
```

---

## Part 5: Security Analysis

### 5.1 Threat Model for Permission Mechanisms

| Threat | `permissions.allow` | `auto` mode | `--dangerously-skip` |
|--------|-------------------|-------------|---------------------|
| Prompt injection | Blocks unlisted tools | Classifier detects | **No protection** |
| Scope escalation | Pattern-bounded | Classifier detects | **No protection** |
| Subagent inheritance | Same patterns apply | Same classifier | Full access inherited |
| Credential access | Only if pattern allows | Classifier may block | **Full access** |
| Audit trail | Git-tracked config | Logs + hook events | None |
| Recovery | Revert commit | Disable mode | Kill process |

### 5.2 Fleet-Specific Risks

**Risk 1: Self-modifying permissions**
Our settings.json allows editing itself. This is intentional (#1927) but means
a compromised lane could widen its own permissions. Mitigation: git audit trail
+ PR review. See `.claude/rules/80_permission_model.md`.

**Risk 2: Pattern coverage gaps cause stalls, not breaches**
Missing patterns in `permissions.allow` cause lanes to stall (blocking, not
dangerous). The failure mode is availability, not security.

**Risk 3: Auto mode classifier false negatives**
If adopted, the classifier could approve a dangerous action our allowlist
would have blocked. Mitigation: use auto mode as complement (fallback), not
replacement for allowlist.

---

## References

### Official Documentation
- [Permission Modes](https://code.claude.com/docs/en/permission-modes)
- [Configure Permissions](https://code.claude.com/docs/en/permissions)
- [Auto Mode Engineering Blog](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [Auto Mode Blog Post](https://claude.com/blog/auto-mode)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [CLI Reference](https://code.claude.com/docs/en/cli-reference)
- [Changelog](https://code.claude.com/docs/en/changelog)
- [MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Server-Managed Settings](https://code.claude.com/docs/en/server-managed-settings)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Environment Variables](https://code.claude.com/docs/en/env-vars)

### Third-Party Analysis
- [Claude Code Auto-Accept Guide (SmartScope)](https://smartscope.blog/en/generative-ai/claude/claude-code-auto-permission-guide/)
- [Auto Mode Explained (MindStudio)](https://www.mindstudio.ai/blog/what-is-claude-code-auto-mode-permission-classifier)
- [Dangerous Skip Permissions Guide (ksred)](https://www.ksred.com/claude-code-dangerously-skip-permissions-when-to-use-it-and-when-you-absolutely-shouldnt/)
- [Claude Code Updates March 2026 (Builder.io)](https://www.builder.io/blog/claude-code-updates)
- [1M Context Window (ClaudeFast)](https://claudefa.st/blog/guide/mechanics/1m-context-ga)
- [Every Claude Code Update (ClaudeFast Changelog)](https://claudefa.st/blog/guide/changelog)

### Internal
- #2249 — This research task
- #2238 — Review lane permission stalls
- #2244 — Env flags research (companion doc)
- #1708 — Original permission stall fix (SKILL.md)
- #1927 — Expanded auto-accept to full infrastructure set
- #1931 — Permission model documentation
- `.claude/rules/80_permission_model.md` — Permission model design doc
- `.claude/settings.json` — Current permission configuration

## Outcome

Research complete. Deliverable produced with:
- 6 permission mechanisms evaluated with tradeoffs table
- Fleet recommendation: keep `permissions.allow` + add `defaultMode: "acceptEdits"`
- 18 features audited from Jan–Apr 2026 releases
- 12-item priority adoption list across 3 tiers
- Immediate config changes specified (settings.json + steward-session.sh)
- Security analysis with threat model

Implementation PRs recommended:
1. **PR 1:** settings.json — add `defaultMode`, fill Bash pattern gaps
2. **PR 2:** steward-session.sh — add 6 fleet env flags (combine with #2244 recommendations)
3. **PR 3:** PermissionDenied hook for observability
