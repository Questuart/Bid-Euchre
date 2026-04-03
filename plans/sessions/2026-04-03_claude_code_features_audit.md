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
permission management. However, research into external practices reveals two
powerful mechanisms we're not using: **`dontAsk` mode** (auto-denies everything
not in our allowlist, eliminating stalls entirely) and **native sandbox**
(`/sandbox` with auto-allow, which reduces permission prompts by 84% while
enforcing OS-level isolation). The newer `auto` mode (classifier-based, March
2026) is a useful complement but not a primary mechanism for our fleet.

**Key recommendations:**
1. **Switch to `defaultMode: "dontAsk"`** — auto-denies unlisted tools instead of stalling (game-changer for fleet)
2. **Evaluate native sandbox** (`/sandbox` + auto-allow) — OS-level isolation + 84% fewer prompts
3. **Add defense-in-depth PreToolUse hook** — block dangerous commands at OS level, not just config
4. Keep `permissions.allow` as the allowlist (no change to patterns, but add gaps)
5. Adopt 6 new env flags in steward-session.sh (per companion #2244 research)
6. **Do NOT rely on `permissions.deny`** — known enforcement bugs (multiple open GitHub issues)
7. Evaluate `auto` mode as a complement (requires Team/Enterprise plan)
8. Monitor 1M context window benefits — may allow raising auto-compact threshold

---

## Part 1: Auto-Accept Evaluation

### 1.1 Permission Mechanisms — Complete Landscape

Claude Code provides **nine** distinct mechanisms for controlling permission
prompts. External research (Trail of Bits, Docker, OWASP, community fleet
managers) reveals several we weren't evaluating:

| # | Mechanism | Granularity | Persistence | Safety | Fleet Suitability |
|---|-----------|-------------|-------------|--------|-------------------|
| 1 | `permissions.allow` in settings.json | Per-tool + file pattern | Permanent, version-controlled | **Best** | **Current — keep** |
| 2 | **`dontAsk` mode** | Allow-only (denies unlisted) | Permanent via defaultMode | **Best** | **★ Recommended for fleet** |
| 3 | **Native sandbox** (`/sandbox` + auto-allow) | OS-level filesystem + network | Session (enable per session) | **Excellent** | **★ Evaluate immediately** |
| 4 | `--allowedTools` / `--disallowedTools` CLI flags | Per-tool + pattern | Session only | Good | Useful for one-off sessions |
| 5 | `auto` mode (classifier) | AI-evaluated per call | Session (until mode change) | Good | Evaluate as complement |
| 6 | `acceptEdits` mode | All file edits | Session or defaultMode | Good | Superseded by dontAsk |
| 7 | **PreToolUse hooks** (defense-in-depth) | Per-command regex | Permanent, version-controlled | **Excellent** | **★ Add for dangerous commands** |
| 8 | `bypassPermissions` mode | Everything (except .git/.claude) | Session only | Low | Only with sandbox |
| 9 | `--dangerously-skip-permissions` | Everything | Session only | **None** | **Never for fleet** |

**Key insight from external research:** The combination of `dontAsk` mode +
`permissions.allow` + PreToolUse hooks + native sandbox is the
defense-in-depth pattern used by security-conscious teams like Trail of Bits.
Our current approach uses only layer 1.

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

**Valid values:** `default`, `acceptEdits`, `plan`, `auto`, **`dontAsk`**,
**`bypassPermissions`**

**Fleet relevance of `acceptEdits`:** Medium. Auto-approves file edits only.

**Fleet relevance of `dontAsk`:** **★ HIGH — This is the game-changer.**

`dontAsk` mode auto-denies every tool call that is NOT explicitly in your
`permissions.allow` list. This is the inverse of `acceptEdits`:
- `acceptEdits`: approves all edits, asks about everything else
- `dontAsk`: denies everything not explicitly allowed, never prompts

**Why `dontAsk` solves our permission stall problem:**
Our fleet stalls because unlisted tools trigger a blocking permission prompt.
With `dontAsk`, unlisted tools are silently denied — the agent adapts and
tries a different approach instead of hanging. The lane never stalls.

```json
{
  "permissions": {
    "defaultMode": "dontAsk",
    "allow": [ /* our existing allowlist */ ]
  }
}
```

**Tradeoff:** If our allowlist has gaps, agents will be denied tools they need
(silent failure instead of stall). This is strictly better for autonomous
operation — a denied tool produces an error message the agent can react to,
while a stalled prompt produces nothing.

**Recommendation:** Switch from unset (default) to `"defaultMode": "dontAsk"`.
This is the single highest-impact change in this document.

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

**Fleet relevance:** Low — superseded by `dontAsk` mode for fleet use. `dontAsk`
provides the same file-edit auto-accept (via allowlist) while also eliminating
stalls for unlisted tools.

#### Mechanism 6: Native Sandbox (`/sandbox`)

> Source: [Anthropic Engineering Blog](https://www.anthropic.com/engineering/claude-code-sandboxing),
> [Claude Code Docs](https://code.claude.com/docs/en/sandboxing),
> [Trail of Bits Config](https://github.com/trailofbits/claude-code-config)

**How it works:** OS-level filesystem and network isolation using Seatbelt
(macOS) or bubblewrap (Linux). Enable with `/sandbox` command in a session.

**Filesystem isolation:**
- Read + write access to the current working directory (and subdirs)
- Read-only access to system files outside CWD
- Cannot modify files outside the project directory

**Network isolation:**
- All network traffic routed through a validating proxy
- Only explicitly allowed domains can be reached
- Configurable domain allowlist/denylist

**Auto-allow mode:** When enabled, Bash commands that stay within sandbox
boundaries run WITHOUT permission prompts. This reduces permission prompts
by **84%** in Anthropic's internal testing — the sandbox boundary replaces the
per-tool allowlist for Bash commands.

**How external teams use it:**

*Trail of Bits approach:*
> "We run Claude Code in bypass-permissions mode, which means understanding
> sandboxing options is essential — the agent executes commands without asking,
> so the sandbox keeps it from doing damage."
> — [trailofbits/claude-code-config](https://github.com/trailofbits/claude-code-config)

Trail of Bits uses `bypassPermissions` + `/sandbox` — maximum autonomy within
a security boundary. This is the "sandbox-first" model: trust the OS-level
isolation, not the permission prompts.

**Fleet relevance:** **★ HIGH.** Our fleet runs on macOS (Seatbelt supported).
The sandbox would:
- Eliminate most Bash permission prompts within the project directory
- Provide OS-level protection against prompt injection (even if an agent
  is compromised, it can't escape CWD or phone home to unauthorized domains)
- Allow us to simplify our Bash allowlist significantly

**Key limitation:** Sandbox must be enabled per session — there's no persistent
setting to auto-enable it. This means either:
- A SessionStart hook that runs `/sandbox`
- Fleet launch scripts that activate sandbox mode

**Docker Sandbox alternative:** For maximum isolation, Docker provides
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) that run each
agent in a microVM with its own Docker daemon, filesystem, and network.
This is overkill for our use case but worth noting for future scale.

#### Mechanism 7: PreToolUse Hooks (Defense-in-Depth)

> Source: [claude-code-bash-guardian](https://github.com/RoaringFerrum/claude-code-bash-guardian),
> [claude-code-damage-control](https://github.com/disler/claude-code-damage-control),
> [Guardrails That Actually Work](https://paddo.dev/blog/claude-code-hooks-guardrails/)

**How it works:** A PreToolUse hook runs a script before every tool call. The
script can inspect the command and return:
- Exit code 0 → allow
- Exit code 2 → **block** (deny the tool call)
- JSON `{"permissionDecision": "deny"}` → block with message

**⚠️ Critical implementation detail:** Exit code **2** is required for blocking.
Exit code 1 only logs a warning and does NOT prevent execution. Multiple blog
posts from the community warn about this subtle but critical distinction.

**What external teams block:**

From [claude-code-bash-guardian](https://github.com/RoaringFerrum/claude-code-bash-guardian)
(15+ categories of dangerous patterns):

```bash
# Patterns to block:
rm -rf /           # Recursive delete from root
git push --force   # Force push (our pre-merge guard already catches this)
sudo *             # Privilege escalation
curl * | sh        # Pipe-to-shell attacks
chmod 777          # Overly permissive file permissions
> /etc/*           # System file overwrites
kill -9            # Aggressive process killing
```

**Why hooks are essential (even with deny rules):**
> "Deny rules only block Claude's built-in tools — Bash commands bypass them.
> With /sandbox enabled, the same rules are enforced at the OS level."
> — Trail of Bits

Without sandbox or hooks, a Bash command like `cat ~/.ssh/id_rsa` is not
blocked by `permissions.deny` rules (see deny rules bug below). PreToolUse
hooks are the **only reliable** way to block specific Bash commands.

**Our existing hooks:** We already have `pre-bash-dispatch.sh` as a PreToolUse
matcher for Bash. We should extend it (or add a parallel hook) to block
dangerous command patterns.

**Fleet relevance:** **★ HIGH.** We should add a bash guardian hook that blocks:
- `rm -rf` patterns
- `git push --force` / `git push -f`
- `sudo` commands
- Pipe-to-shell patterns (`curl|sh`, `wget|sh`)
- Direct credential access patterns

#### Mechanism 8: `bypassPermissions` Mode

**How it works:** Approves ALL tool calls without prompting, EXCEPT writes to
`.git/`, `.vscode/`, `.idea/`, `.husky/`, and `.claude/` (except commands,
agents, skills subdirs).

**Fleet relevance:** **Only with sandbox.** Trail of Bits uses this mode
paired with `/sandbox` for maximum autonomy within OS-level boundaries.
Without sandbox, this is essentially `--dangerously-skip-permissions` with
a few extra guardrails.

#### Mechanism 9: `--dangerously-skip-permissions`

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

Our research into external fleet patterns reveals a clear **defense-in-depth**
architecture that security-conscious teams use. We should adopt it in layers:

#### Layer 1: `dontAsk` + `permissions.allow` (★ Immediate — Highest Impact)

**Switch `defaultMode` from unset to `"dontAsk"`.**

This single change eliminates all permission stalls fleet-wide. With `dontAsk`:
- Tools in `permissions.allow` execute without prompting (same as today)
- Tools NOT in `permissions.allow` are **silently denied** instead of stalling
- The agent sees a denial message and adapts (tries a different approach)
- No lane ever hangs on a permission prompt again

```json
{
  "permissions": {
    "defaultMode": "dontAsk",
    "allow": [ /* our existing allowlist — expanded */ ]
  }
}
```

**Why this is better than `acceptEdits`:** `acceptEdits` only auto-approves
file edits. `dontAsk` handles ALL tool types — Bash, MCP, WebFetch, etc.
It's the strict-whitelist model that fleet operations need.

**Risk:** If our allowlist has gaps, agents lose a tool silently. This is
strictly better than the current behavior (lane hangs indefinitely). We can
monitor denied tools via a PermissionDenied hook and iteratively expand the
allowlist.

#### Layer 2: PreToolUse Bash Guardian Hook (★ Immediate)

Add a defense-in-depth hook that blocks dangerous Bash command patterns,
regardless of what the allowlist permits:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-guardian.sh",
          "timeout": 5
        }]
      }
    ]
  }
}
```

The hook should block (exit code 2):
- `rm -rf /` or `rm -rf ~` (catastrophic deletion)
- `git push --force` to main/master
- `sudo` commands
- `curl|sh` / `wget|sh` (pipe-to-shell)
- `chmod 777` (overly permissive)
- Direct credential access (`cat ~/.ssh/*`, `cat ~/.aws/*`)

This is the pattern used by [claude-code-bash-guardian](https://github.com/RoaringFerrum/claude-code-bash-guardian)
and [claude-code-damage-control](https://github.com/disler/claude-code-damage-control).

#### Layer 3: Native Sandbox (Evaluate — High Impact)

Test `/sandbox` with auto-allow on one lane. If it works with our workflow:
- 84% fewer permission prompts (Anthropic's internal measurement)
- OS-level filesystem isolation (Seatbelt on macOS)
- OS-level network isolation (proxy-based domain allowlist)
- Even prompt injection can't escape the sandbox boundary

**Blocker to evaluate:** Sandbox must be enabled per session — no persistent
config. Need to test if a SessionStart hook or fleet launch script can
reliably activate it.

#### Layer 4: `auto` Mode (Evaluate — Complement)

If on Team/Enterprise plan, test auto mode as a complement:
```bash
claude --enable-auto-mode --permission-mode auto
```

Auto mode's classifier catches intent-mismatch attacks that pattern-based
allowlists can't detect. But it adds latency and may abort headless sessions.

#### Layer 5: PermissionDenied Hook (Observability)

Add a hook that logs every denied tool call for fleet monitoring:

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

This creates a feedback loop: denied tools are logged → operator reviews →
allowlist is expanded for legitimate patterns → fleet throughput improves.

### 1.4 ⚠️ Critical Warning: `permissions.deny` Rules Are Broken

> **Multiple open GitHub issues confirm that deny rules in settings.json are
> not reliably enforced.** Do not rely on deny rules for security.

| Issue | Status | Description |
|-------|--------|-------------|
| [#6699](https://github.com/anthropics/claude-code/issues/6699) | Open | Critical: deny permissions not enforced |
| [#8961](https://github.com/anthropics/claude-code/issues/8961) | Open | settings.local.json deny rules ignored |
| [#24846](https://github.com/anthropics/claude-code/issues/24846) | Open | Read deny not enforced for .env files |
| [#27040](https://github.com/anthropics/claude-code/issues/27040) | Open | Deny permissions in settings.json ignored |
| [#31925](https://github.com/anthropics/claude-code/issues/31925) | Open | Managed settings deny rules not enforced |

**Implications for our fleet:**
- We are NOT currently using deny rules, so this doesn't affect us today
- If we ever add deny rules (e.g., to block .env access), use PreToolUse hooks
  instead — they are the **only reliable blocking mechanism**
- The `/sandbox` native sandbox enforces restrictions at the OS level,
  bypassing this bug entirely

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
| **`dontAsk` mode** | Available now | Permissions | **★ Critical** | Switch immediately — eliminates stalls |
| **Native sandbox** (`/sandbox` + auto-allow) | Available now | Security | **★ Critical** | Evaluate immediately — 84% fewer prompts |
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

### Tier 1 — Immediate (This Sprint) ★

| # | Change | Files | Risk | Effort |
|---|--------|-------|------|--------|
| 1 | **Switch to `defaultMode: "dontAsk"`** | `.claude/settings.json` | Low-Med | 5 min + monitoring |
| 2 | **Add bash-guardian PreToolUse hook** | `.claude/hooks/bash-guardian.sh`, `.claude/settings.json` | Low | 1 PR |
| 3 | Fill permission gaps: add `Bash(cat *)`, `Bash(python *)`, etc. | `.claude/settings.json` | Low | 5 min |
| 4 | Add 6 fleet env flags to steward-session.sh (per #2244 research) | `.claude/tmux/steward-session.sh` | Low | 1 PR |
| 5 | Add PermissionDenied hook for observability | `.claude/hooks/permission-denied-log.sh` | Low | 1 PR |
| 6 | Audit hook matchers for tool renames (`View`→`Read`, `LSTool`→`LS`) | `.claude/settings.json` | Low | 15 min |

### Tier 2 — Short-Term (Next 2 Weeks)

| # | Change | Dependency | Effort |
|---|--------|------------|--------|
| 7 | **Evaluate native sandbox** (`/sandbox` + auto-allow) on one lane | Test per-session activation | 1-2 days |
| 8 | Test raising auto-compact to 300K on one lane | Monitor for 24h | 1 day |
| 9 | Evaluate auto mode on one interactive lane | Team/Enterprise plan | 2 days |
| 10 | Audit skills for `TaskOutput` references | Grep + fix | 30 min |

### Tier 3 — Evaluate (Next Month)

| # | Change | Dependency | Effort |
|---|--------|------------|--------|
| 11 | Evaluate deferred permissions for orchestrator-mediated approval | Orchestrator changes | 1 week |
| 12 | Evaluate plugin system for fleet-specific extensions | Plugin API stability | 1 week |
| 13 | Evaluate remote control for mobile fleet monitoring | Remote control GA | 2 days |
| 14 | Evaluate sandbox + bypassPermissions (Trail of Bits model) | Sandbox proven stable | 3 days |

---

## Part 4: Immediate Config Changes

### 4.1 settings.json Updates

```json
{
  "permissions": {
    "defaultMode": "dontAsk",
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
- `defaultMode: "dontAsk"` — auto-denies unlisted tools instead of stalling (eliminates ALL permission stalls)
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

## Part 5: External Ecosystem & Best Practices

### 5.1 How Other Teams Solve Auto-Accept

| Team / Tool | Approach | Key Insight |
|-------------|----------|-------------|
| **Trail of Bits** ([claude-code-config](https://github.com/trailofbits/claude-code-config)) | `bypassPermissions` + `/sandbox` + deny rules for secrets | "The sandbox keeps it from doing damage" — trust OS isolation, not prompts |
| **claude-squad** ([smtg-ai](https://github.com/smtg-ai/claude-squad)) | Per-lane tmux sessions with permission presets | "Pre-approve common operations before spawning teammates" |
| **ai-fleet** ([nachoal](https://github.com/nachoal/ai-fleet)) | `--dangerously-skip-permissions` in config.toml | Simple but risky — no defense-in-depth |
| **agtx** ([fynnfluegge](https://github.com/fynnfluegge/agtx)) | Orchestrator validates `allowed_actions` per phase | Action validation at the orchestrator level |
| **dmux** ([brightcoding](https://blog.brightcoding.dev/2026/03/21/dmux-the-revolutionary-dev-agent-multiplexer-for-parallel-ai)) | Git worktree isolation + parallel tmux panes | Isolation through workspace separation (similar to our model) |
| **Docker Sandboxes** ([Docker](https://docs.docker.com/ai/sandboxes/)) | MicroVM per agent + `--dangerously-skip-permissions` | Hardware-level isolation makes permission bypass safe |
| **OpenAI Codex CLI** ([OpenAI](https://developers.openai.com/codex/agent-approvals-security)) | Seatbelt/Docker sandbox on by default + auto-approve within workspace | "Sandboxing first" — sandbox is not optional, it's the default |

**Key pattern across security-conscious teams:** Nobody relies on permission
prompts alone. The winning pattern is:

1. **Allowlist** (what the agent CAN do) — permissions.allow or auto-approve
2. **Blocklist** (what the agent CANNOT do) — PreToolUse hooks, not deny rules
3. **Boundary** (where the agent operates) — sandbox, Docker, or worktree isolation
4. **Audit** (what the agent DID do) — git history, hooks, logging

Our fleet currently has strong layers 1 and 4 but is missing layers 2 and 3.

### 5.2 Competitor Permission Models

| Tool | Default Sandbox | Permission Modes | Network Isolation | Audit Trail |
|------|----------------|------------------|-------------------|-------------|
| **Claude Code** | Optional (`/sandbox`) | 6 modes + hooks | Proxy-based allowlist | Git + hooks |
| **OpenAI Codex** | **On by default** | auto/suggest/ask | Blocked by default | Git |
| **Cursor** | Added early 2026 | Agent/normal modes | Limited | IDE-level |
| **Windsurf** | None documented | User approval only | None | IDE-level |
| **Google Antigravity** | Built-in | Multi-agent orchestration | Per-agent | Built-in |

**Notable:** OpenAI Codex CLI has sandboxing on by default — it's not optional.
Claude Code's sandbox is more capable (network isolation, auto-allow mode) but
must be explicitly enabled.

### 5.3 Industry Best Practices (OWASP, AWS, BeyondTrust)

From the [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html),
[AWS GenAI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/gensec05-bp01.html),
and [BeyondTrust](https://www.beyondtrust.com/blog/entry/ai-agent-identity-governance-least-privilege):

| Principle | Our Current State | Gap |
|-----------|------------------|-----|
| **Least privilege** — minimum permissions needed | ✅ Allowlist-based | ✅ Good |
| **Deny by default** — unlisted actions are blocked | ❌ Unlisted = stall (prompt) | **Fix: `dontAsk` mode** |
| **Defense-in-depth** — multiple independent layers | ⚠️ Only allowlist | **Add: hooks + sandbox** |
| **Audit trail** — every action is logged and reviewable | ✅ Git + PR review | ✅ Good |
| **Credential isolation** — agents can't access secrets | ⚠️ No enforcement | **Add: hook or sandbox** |
| **Network isolation** — agents can't phone home | ❌ Full network access | **Evaluate: sandbox** |
| **Blast radius containment** — one agent can't affect others | ✅ Git worktrees | ✅ Good |
| **Short-lived credentials** — rotate tokens, use JIT access | ⚠️ Long-lived GH token | Future consideration |

### 5.4 Community Hook Patterns Worth Adopting

From [claude-code-bash-guardian](https://github.com/RoaringFerrum/claude-code-bash-guardian),
[Guardrails That Actually Work](https://paddo.dev/blog/claude-code-hooks-guardrails/), and
[Building Guardrails for AI Coding Assistants](https://dev.to/mikelane/building-guardrails-for-ai-coding-assistants-a-pretooluse-hook-system-for-claude-code-ilj):

**Pattern 1: Bash Command Guardian**
Block dangerous commands regardless of allowlist:
```bash
#!/bin/bash
# Exit 2 = block, Exit 0 = allow
COMMAND="$CLAUDE_TOOL_INPUT"
# Block catastrophic deletions
echo "$COMMAND" | grep -qP '\brm\s+.*-[rRf].*/' && exit 2
# Block force pushes to main
echo "$COMMAND" | grep -qP 'git\s+push\s+.*--force.*main' && exit 2
# Block sudo
echo "$COMMAND" | grep -qP '^\s*sudo\s' && exit 2
# Block pipe-to-shell
echo "$COMMAND" | grep -qP 'curl.*\|\s*(ba)?sh' && exit 2
exit 0
```

**Pattern 2: Credential Access Guardian**
Block reads of sensitive files:
```bash
#!/bin/bash
# For Read/Edit tool calls
FILE="$CLAUDE_TOOL_INPUT"
echo "$FILE" | grep -qP '\.(env|pem|key)$' && exit 2
echo "$FILE" | grep -qP '(\.ssh|\.aws|\.gnupg)/' && exit 2
exit 0
```

**Pattern 3: PermissionDenied Logger**
Log all denied actions for fleet observability:
```bash
#!/bin/bash
# Append to JSONL log for ops monitoring
echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"tool\":\"$CLAUDE_TOOL\",\"denied\":true}" \
  >> "$CLAUDE_PROJECT_DIR/.claude/runtime/permission_denials.jsonl"
```

### 5.5 Security Vulnerability Awareness

**Check Point CVE (Feb 2026):** Hooks in `.claude/settings.json` were part of
an attack vector where malicious project files could define hooks that execute
automatically when Claude loads an untrusted repo. Mitigation: we control our
repo and settings.json — this affects untrusted repo cloning, not our fleet.

**Deny Rules Bug:** See §1.4 above. Multiple open issues confirm deny rules
are unreliable. Never rely on them for security.

**Rule Cap Bug ([The Register, Apr 2026](https://www.theregister.com/2026/04/01/claude_code_rule_cap_raises/)):**
Claude Code has an internal cap of ~50 security subcommands in bashPermissions.ts,
after which it falls back to asking permission. This means very long allowlists
may have diminishing effectiveness. Our current list of ~30 patterns is within
the safe range.

---

## Part 6: Security Analysis

### 6.1 Threat Model for Permission Mechanisms (Expanded)

| Threat | `allow` + `dontAsk` | `allow` + sandbox | `auto` mode | PreToolUse hooks | `--dangerously-skip` |
|--------|---------------------|-------------------|-------------|-----------------|---------------------|
| Prompt injection | Blocks unlisted tools | OS-level containment | Classifier detects | Pattern blocks | **No protection** |
| Scope escalation | Pattern-bounded | CWD-bounded | Classifier detects | Pattern blocks | **No protection** |
| Subagent inheritance | Same patterns | Same sandbox | Same classifier | Same hooks | Full access inherited |
| Credential access | Only if allowed | CWD-only reads | Classifier may block | Regex blocks | **Full access** |
| Network exfiltration | No protection | **Proxy blocks** | Classifier may block | No protection | **No protection** |
| Audit trail | Git-tracked config | OS audit log | Logs + hook events | Hook logging | None |
| Recovery | Revert commit | Kill process | Disable mode | Revert hook | Kill process |

### 6.2 Fleet-Specific Risks

**Risk 1: Self-modifying permissions**
Our settings.json allows editing itself. This is intentional (#1927) but means
a compromised lane could widen its own permissions. Mitigation: git audit trail
+ PR review. See `.claude/rules/80_permission_model.md`.

**Risk 2: `dontAsk` silent denials may cause agent confusion**
With `dontAsk`, unlisted tools are silently denied. If an agent tries a tool
it needs and gets denied, it may retry or get confused. Mitigation: the denial
produces an error message the agent can read. PermissionDenied hook logs the
denial for operator review. Iteratively expand allowlist based on logs.

**Risk 3: Auto mode classifier false negatives**
If adopted, the classifier could approve a dangerous action our allowlist
would have blocked. Mitigation: use auto mode as complement (fallback), not
replacement for allowlist.

**Risk 4: Deny rules are unreliable (known bugs)**
Multiple open GitHub issues (§1.4) confirm `permissions.deny` rules are not
reliably enforced. Never use deny rules as a security mechanism. Use PreToolUse
hooks (exit code 2) or native sandbox instead.

**Risk 5: Hook security (Check Point CVE)**
Hooks in settings.json can be exploited if Claude clones and loads an untrusted
repo. Our fleet only works with our own repo — not affected. But worth noting
for any future "open random repo" workflows.

---

## References

### Official Documentation
- [Permission Modes](https://code.claude.com/docs/en/permission-modes)
- [Configure Permissions](https://code.claude.com/docs/en/permissions)
- [Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Auto Mode Engineering Blog](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [Sandboxing Engineering Blog](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Auto Mode Blog Post](https://claude.com/blog/auto-mode)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [CLI Reference](https://code.claude.com/docs/en/cli-reference)
- [Changelog](https://code.claude.com/docs/en/changelog)
- [MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Server-Managed Settings](https://code.claude.com/docs/en/server-managed-settings)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Environment Variables](https://code.claude.com/docs/en/env-vars)
- [Docker Sandboxes for Claude Code](https://docs.docker.com/ai/sandboxes/agents/claude-code/)
- [Codex CLI Agent Approvals & Security](https://developers.openai.com/codex/agent-approvals-security)

### External Fleet & Security Implementations
- [Trail of Bits Claude Code Config](https://github.com/trailofbits/claude-code-config) — Security-focused opinionated config (sandbox + bypass)
- [claude-code-bash-guardian](https://github.com/RoaringFerrum/claude-code-bash-guardian) — Automated PreToolUse Bash filtering
- [claude-code-damage-control](https://github.com/disler/claude-code-damage-control) — Defense-in-depth guardrails
- [claude-squad (smtg-ai)](https://github.com/smtg-ai/claude-squad) — Multi-agent terminal manager with tmux
- [ai-fleet (nachoal)](https://github.com/nachoal/ai-fleet) — Parallel agent fleet manager
- [agtx (fynnfluegge)](https://github.com/fynnfluegge/agtx) — Multi-session AI coding terminal manager
- [Anthropic sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) — OS-level sandbox library

### Security Best Practices & Standards
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [AWS Well-Architected GenAI Lens — Least Privilege](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/gensec05-bp01.html)
- [BeyondTrust — AI Agent Identity & Least Privilege](https://www.beyondtrust.com/blog/entry/ai-agent-identity-governance-least-privilege)
- [InfoQ — Least-Privilege AI Agent Gateway](https://www.infoq.com/articles/building-ai-agent-gateway-mcp/)
- [How to Sandbox AI Agents (Northflank)](https://northflank.com/blog/how-to-sandbox-ai-agents)
- [AI Agent Security Framework (Substack)](https://manveerc.substack.com/p/ai-agent-security-framework)

### Third-Party Analysis & Guides
- [Claude Code Auto-Accept Guide (SmartScope)](https://smartscope.blog/en/generative-ai/claude/claude-code-auto-permission-guide/)
- [Auto Mode Explained (MindStudio)](https://www.mindstudio.ai/blog/what-is-claude-code-auto-mode-permission-classifier)
- [Guardrails That Actually Work (paddo.dev)](https://paddo.dev/blog/claude-code-hooks-guardrails/)
- [Building Guardrails for AI Coding Assistants (DEV Community)](https://dev.to/mikelane/building-guardrails-for-ai-coding-assistants-a-pretooluse-hook-system-for-claude-code-ilj)
- [Claude Code Configuration Blueprint (DEV Community)](https://dev.to/mir_mursalin_ankur/claude-code-configuration-blueprint-the-complete-guide-for-production-teams-557p)
- [How to Fix Claude Code's Broken Permissions With Hooks (DEV Community)](https://dev.to/boucle2026/how-to-fix-claude-codes-broken-permissions-with-hooks-23gl)
- [Claude Code Updates March 2026 (Builder.io)](https://www.builder.io/blog/claude-code-updates)
- [1M Context Window (ClaudeFast)](https://claudefa.st/blog/guide/mechanics/1m-context-ga)
- [Every Claude Code Update (ClaudeFast Changelog)](https://claudefa.st/blog/guide/changelog)
- [Sandboxing Claude Code on macOS (Infralovers)](https://www.infralovers.com/blog/2026-02-15-sandboxing-claude-code-macos/)

### Known Bugs — Deny Rules
- [#6699 — Critical: deny permissions not enforced](https://github.com/anthropics/claude-code/issues/6699)
- [#8961 — settings.local.json deny rules ignored](https://github.com/anthropics/claude-code/issues/8961)
- [#24846 — Read deny not enforced for .env files](https://github.com/anthropics/claude-code/issues/24846)
- [#27040 — Deny permissions in settings.json ignored](https://github.com/anthropics/claude-code/issues/27040)
- [#31925 — Managed settings deny rules not enforced](https://github.com/anthropics/claude-code/issues/31925)

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
- **9 permission mechanisms** evaluated with tradeoffs (up from 6 — added dontAsk, sandbox, hooks)
- **External ecosystem audit:** 7 fleet tools, 4 security frameworks, 6 community hook patterns
- **Critical finding:** `dontAsk` mode eliminates all permission stalls (the #1 fleet pain point)
- **Critical finding:** `permissions.deny` rules have known enforcement bugs — never rely on them
- **Defense-in-depth recommendation:** dontAsk + allowlist + PreToolUse hooks + sandbox
- Fleet recommendation: switch to `defaultMode: "dontAsk"` (highest-impact single change)
- 18 features audited from Jan–Apr 2026 releases
- 14-item priority adoption list across 3 tiers
- Immediate config changes specified (settings.json + steward-session.sh + hooks)
- Security analysis with expanded threat model

Implementation PRs recommended:
1. **PR 1:** settings.json — switch to `defaultMode: "dontAsk"`, fill Bash pattern gaps
2. **PR 2:** bash-guardian.sh — PreToolUse hook blocking dangerous commands
3. **PR 3:** steward-session.sh — add 6 fleet env flags (combine with #2244 recommendations)
4. **PR 4:** permission-denied-log.sh — PermissionDenied hook for observability
5. **PR 5 (evaluate):** Native sandbox activation via SessionStart hook
