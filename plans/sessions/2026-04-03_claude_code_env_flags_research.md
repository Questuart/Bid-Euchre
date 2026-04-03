# Research: Claude Code Environment Variables for Steward Fleet

> **Issue:** [#2244](https://github.com/Questuart/Bid-Euchre/issues/2244)
> **Date:** 2026-04-03
> **Lane:** analyst-d
> **Status:** COMPLETE

## Executive Summary

`CLAUDE_CODE_NO_FLICKER` is already set globally and covers all 19 steward
lanes. The current configuration is sound but several additional flags would
improve autonomous fleet operations. This document catalogs the full env var
landscape, audits the current state, and recommends targeted additions.

---

## 1. Current State Audit

### 1.1 Configuration Layers (precedence order)

| Layer | Mechanism | Scope | Currently Used |
|-------|-----------|-------|----------------|
| **Shell profile** | `~/.zshrc export` | All processes spawned from login shell | `CLAUDE_CODE_NO_FLICKER=1` |
| **tmux global env** | Inherited from launching shell | All panes, all tmux sessions | `CLAUDE_CODE_NO_FLICKER=1`, `CLAUDE_CODE_SCROLL_SPEED=3` |
| **tmux session env** | `tmux set-environment -t steward` in `steward-session.sh` | All panes in the steward session | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` |
| **Claude Code settings** | `~/.claude/settings.json` → `env` block | All Claude Code instances globally | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| **Internal** | Set by Claude Code process itself | Per-process | `CLAUDECODE=1`, `CLAUDE_CODE_ENTRYPOINT=cli`, `CLAUDE_CODE_SESSION_ID` |

### 1.2 Lane Coverage Matrix

All 19 steward lanes were verified via `env | grep CLAUDE` from this lane
and `tmux show-environment` for session/global layers.

| Variable | Source | Orchestrator | Ops | Review | Analyst (×4) | Author (×4) | Brws-Author (×4) | Flex (×4) |
|----------|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `CLAUDE_CODE_NO_FLICKER=1` | `~/.zshrc` → tmux global | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| `CLAUDE_CODE_SCROLL_SPEED=3` | tmux global | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` | steward-session.sh | **No** (by design) | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | `~/.claude/settings.json` | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

**Finding:** `CLAUDE_CODE_NO_FLICKER=1` has **full coverage** across all lanes.
The issue concern about inconsistent coverage is unfounded — the flag is set
in `~/.zshrc` and propagated through tmux's global environment inheritance.

### 1.3 Source Tracing

| Variable | File | Line | Evidence |
|----------|------|------|----------|
| `CLAUDE_CODE_NO_FLICKER=1` | `/Users/claude_runner/.zshrc` | 20 | `export CLAUDE_CODE_NO_FLICKER=1` |
| `CLAUDE_CODE_SCROLL_SPEED=3` | tmux global env | — | Inherited from terminal that started the tmux server (likely cmux or initial shell). Not in any committed config. |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` | `.claude/tmux/steward-session.sh` | 440 | `tmux set-environment -t "$SESSION" CLAUDE_CODE_AUTO_COMPACT_WINDOW "200000"` |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | `~/.claude/settings.json` | 4 | `"env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }` |

---

## 2. Complete CLAUDE_CODE_* Flag Reference

Sourced from official docs ([code.claude.com/docs/en/env-vars](https://code.claude.com/docs/en/env-vars)),
community catalog ([jedisct1/gist](https://gist.github.com/jedisct1/9627644cda1c3929affe9b1ce8eaf714)),
and source analysis.

### 2.1 Fleet-Relevant Flags (Recommended for Steward)

These flags directly improve autonomous fleet operation in tmux.

| Variable | Value | Purpose | Current Status |
|----------|-------|---------|----------------|
| `CLAUDE_CODE_NO_FLICKER` | `1` | Diff-based terminal rendering — eliminates full-screen redraws. Maintains virtual viewport buffer, patches only changed characters. | **SET** (via ~/.zshrc) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `200000` | Triggers auto-compaction when context reaches 200K tokens (vs model max). Saves ~30-50% token burn. | **SET** (via steward-session.sh, non-orch only) |
| `CLAUDE_CODE_SCROLL_SPEED` | `3` | Mouse wheel scroll multiplier (1-20). Improves scroll UX in fullscreen mode. | **SET** (via tmux global env) |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` | Enables multi-agent team collaboration. Required for fleet sub-agent spawning. | **SET** (via settings.json) |
| `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` | `1` | Prevents Claude Code from updating terminal title. In 19-pane tmux, title changes are noise. | **NOT SET** — Recommended |
| `DISABLE_AUTOUPDATER` | `1` | Prevents auto-update during sessions. Fleet should update via controlled rollout, not mid-session. | **NOT SET** — Recommended |
| `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY` | `1` | Suppresses session quality surveys. Autonomous lanes should never show interactive surveys. | **NOT SET** — Recommended |
| `DISABLE_COST_WARNINGS` | `1` | Suppresses cost warning messages. Autonomous lanes don't need per-turn cost alerts. | **NOT SET** — Recommended |
| `CLAUDE_CODE_RESUME_INTERRUPTED_TURN` | `1` | Auto-resumes mid-turn if session reconnects. Improves fleet resilience to transient disconnects. | **NOT SET** — Recommended |
| `CLAUDE_CODE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | `1` | Returns bash tool to project root after each command. Prevents cwd drift in long sessions. | **NOT SET** — Consider |
| `CLAUDE_CODE_DISABLE_MOUSE` | `1` | Disables mouse tracking in fullscreen mode. Could prevent mouse capture interfering with tmux mouse operations. | **NOT SET** — Consider (may conflict with SCROLL_SPEED) |

### 2.2 Context & Token Management

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | Model max | Token threshold for auto-compaction | **High** — already set to 200K |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | ~95% | Percentage of window that triggers compaction | Low — 200K window is sufficient |
| `DISABLE_AUTO_COMPACT` | Off | Disables auto-compaction entirely | **Never set** — compaction is critical for fleet |
| `DISABLE_COMPACT` | Off | Disables all compaction including manual | **Never set** |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Model default | Max output tokens per response | Low — default is fine |
| `MAX_THINKING_TOKENS` | Model default | Budget for extended thinking | Low — default is fine |
| `CLAUDE_CODE_EFFORT_LEVEL` | Model default | Effort level (`low`/`medium`/`high`/`max`/`auto`) | Low — per-session control is better |

### 2.3 Terminal & UI

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_NO_FLICKER` | Off | Diff-based rendering (virtual viewport) | **High** — already set |
| `CLAUDE_CODE_SCROLL_SPEED` | Auto | Scroll multiplier (1-20) | Medium — already set to 3 |
| `CLAUDE_CODE_DISABLE_MOUSE` | Off | Disable mouse tracking | Low — consider for tmux compatibility |
| `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` | Off | Stop title updates | **Medium** — recommended |
| `CLAUDE_CODE_SYNTAX_HIGHLIGHT` | On | Syntax highlighting in diffs | Low — keep default |
| `CLAUDE_CODE_CODE_ACCESSIBILITY` | Off | Native cursor visibility | Low — not needed |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION` | On | Prompt suggestions | Low — harmless for autonomous lanes |

### 2.4 Shell & Bash Tool

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_SHELL` | Auto-detected | Override shell detection | Low — zsh detection works |
| `CLAUDE_CODE_SHELL_PREFIX` | None | Command prefix for all bash calls | Low — not needed |
| `BASH_DEFAULT_TIMEOUT_MS` | None | Default bash timeout | Low — per-command timeouts work |
| `BASH_MAX_TIMEOUT_MS` | None | Max bash timeout | Low |
| `BASH_MAX_OUTPUT_LENGTH` | None | Truncate large outputs | Medium — could help with context |
| `CLAUDE_CODE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | Off | Return to project dir after bash | Medium — prevents cwd drift |

### 2.5 Networking, Telemetry & Updates

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `DISABLE_TELEMETRY` | Off | Opt out of Statsig telemetry | Low — minimal traffic |
| `DISABLE_ERROR_REPORTING` | Off | Opt out of Sentry reporting | Low — keep for debugging |
| `DISABLE_AUTOUPDATER` | Off | Prevent auto-updates | **High** — recommended |
| `DISABLE_COST_WARNINGS` | Off | Suppress cost alerts | Medium — recommended |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Off | Reduce background requests | Medium — consider |

### 2.6 Background Tasks & Scheduling

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | Off | Disable background tasks | **Never set** — fleet uses background tasks |
| `CLAUDE_AUTO_BACKGROUND_TASKS` | Off | Force auto-backgrounding | Low — not needed |
| `CLAUDE_CODE_DISABLE_CRON` | Off | Disable scheduled tasks | **Never set** — fleet uses cron |

### 2.7 Agent Teams & Subagents

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Off | Enable agent teams | **High** — already set |
| `CLAUDE_CODE_TEAM_NAME` | None | Agent team name | Low — not using named teams |
| `CLAUDE_CODE_SUBAGENT_MODEL` | None | Override subagent model | Low — default model is fine |
| `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` | 10 | Max parallel tools/subagents | Low — default is fine |

### 2.8 Files, Memory & Git

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_DISABLE_CLAUDE_MDS` | Off | Skip CLAUDE.md loading | **Never set** — CLAUDE.md is critical |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Off | Disable auto-memory | Low — keep default |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` | Off | Remove built-in git instructions | Low — keep default |
| `CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING` | Off | Disable file checkpointing for `/rewind` | Low — keep for safety |
| `CLAUDE_CODE_GLOB_HIDDEN` | `true` | Include dotfiles in Glob | Low — keep default |

### 2.9 Retry, Streaming & Resilience

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_MAX_RETRIES` | 10 | API request retries | Low — default is fine |
| `CLAUDE_ENABLE_STREAM_WATCHDOG` | Off | Abort stalled streams after 90s | Medium — consider for resilience |
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | 90000 | Stalled stream timeout | Low — default is fine |
| `CLAUDE_CODE_RESUME_INTERRUPTED_TURN` | Off | Auto-resume mid-turn | **Medium** — recommended |
| `API_TIMEOUT_MS` | 600000 | API request timeout (10 min) | Low — default is fine |

### 2.10 Thinking & Reasoning

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_DISABLE_THINKING` | Off | Disable extended thinking | **Never set** — thinking is critical |
| `DISABLE_INTERLEAVED_THINKING` | Off | Prevent interleaved thinking | Low — keep default |
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` | Off | Disable adaptive reasoning | Low — keep default |

### 2.11 Debug & Development

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_DEBUG_LOG_LEVEL` | `debug` | Debug log level | Low — default is fine |
| `CLAUDE_CODE_DEBUG_LOGS_DIR` | `~/.claude/debug/` | Debug log location | Low — default is fine |
| `CLAUDE_CODE_SIMPLE` | Off | Minimal system prompt | **Never set** — fleet needs full tools |

### 2.12 IDE & Plugin

| Variable | Default | Purpose | Fleet Relevance |
|----------|---------|---------|-----------------|
| `CLAUDE_CODE_AUTO_CONNECT_IDE` | Auto | IDE auto-connect | Low — irrelevant in tmux |
| `CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL` | Off | Skip IDE extension install | Low — irrelevant in tmux |
| `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` | Off | Skip marketplace auto-add | Low |

---

## 3. Recommended Configuration Approach

### 3.1 Where Each Flag Should Live

| Configuration Point | Best For | Example |
|---------------------|----------|---------|
| `~/.zshrc` | Machine-wide flags that apply to ALL Claude Code instances (fleet or manual) | `CLAUDE_CODE_NO_FLICKER=1` |
| `steward-session.sh` via `tmux set-environment` | Session-level flags specific to the steward fleet | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` |
| `~/.claude/settings.json` → `env` block | Flags that Claude Code reads from its own config (feature flags) | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| Per-worktree `.claude/settings.local.json` | Lane-specific overrides (rare) | Plugin enablement per orchestrator |

**Precedence:** Shell environment > tmux session env > tmux global env > settings.json `env` block.

### 3.2 Recommendation: Add Fleet Flags to steward-session.sh

The best configuration point for fleet-specific flags is `steward-session.sh`
via `tmux set-environment`. This keeps fleet concerns separate from the user's
shell profile, is version-controlled, and applies cleanly to all steward panes.

**Proposed additions** (add after the existing `CLAUDE_CODE_AUTO_COMPACT_WINDOW` line):

```bash
# Fleet UX optimization: suppress terminal title changes in 19-pane layout
tmux set-environment -t "$SESSION" CLAUDE_CODE_DISABLE_TERMINAL_TITLE "1"

# Fleet stability: prevent auto-updates during active sessions
tmux set-environment -t "$SESSION" DISABLE_AUTOUPDATER "1"

# Fleet autonomy: suppress interactive feedback surveys
tmux set-environment -t "$SESSION" CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY "1"

# Fleet autonomy: suppress cost warning messages
tmux set-environment -t "$SESSION" DISABLE_COST_WARNINGS "1"

# Fleet resilience: auto-resume interrupted turns
tmux set-environment -t "$SESSION" CLAUDE_CODE_RESUME_INTERRUPTED_TURN "1"
```

### 3.3 Optional / Consider

These flags have benefits but also tradeoffs. Recommend testing before fleet-wide deployment:

| Flag | Benefit | Risk | Recommendation |
|------|---------|------|----------------|
| `CLAUDE_CODE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` | Prevents cwd drift in long sessions | May break scripts that intentionally cd | Test on one lane first |
| `CLAUDE_ENABLE_STREAM_WATCHDOG=1` | Aborts stalled streams after 90s | Could kill slow but valid responses | Monitor for false positives |
| `CLAUDE_CODE_DISABLE_MOUSE=1` | Prevents mouse capture conflicts with tmux | Disables scroll in fullscreen (conflicts with SCROLL_SPEED) | Skip — SCROLL_SPEED is more useful |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | Reduces background network usage | May disable useful preflight checks | Low priority |

### 3.4 Flags to NEVER Set in Fleet

| Flag | Why Not |
|------|---------|
| `DISABLE_AUTO_COMPACT` | Compaction is critical — lanes would exhaust context |
| `CLAUDE_CODE_DISABLE_CRON` | Fleet uses cron for monitoring loops |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | Fleet uses background tasks |
| `CLAUDE_CODE_DISABLE_CLAUDE_MDS` | CLAUDE.md contains essential project instructions |
| `CLAUDE_CODE_DISABLE_THINKING` | Extended thinking is critical for complex tasks |
| `CLAUDE_CODE_SIMPLE` | Would strip most tools from lanes |

---

## 4. Implementation Steps

### PR 1: Add Fleet Env Flags to steward-session.sh

**Files to change:**
- `.claude/tmux/steward-session.sh` — add 5 new `tmux set-environment` lines
- `tests/unit/test_steward_session.py` — add regression tests for each new flag

**Implementation details:**
1. Add the 5 recommended flags after the existing `CLAUDE_CODE_AUTO_COMPACT_WINDOW` block (line 440)
2. Place them AFTER orchestrator pane creation (same as AUTO_COMPACT_WINDOW)
3. Add tests following the existing `TestAutoCompactWindow` pattern

**Validation:**
```bash
bash -n .claude/tmux/steward-session.sh  # syntax check
uv run python -m pytest tests/unit/test_steward_session.py -v
make check-quiet
```

### PR 2 (Optional): Relocate CLAUDE_CODE_NO_FLICKER from .zshrc to steward-session.sh

**Rationale:** Currently `CLAUDE_CODE_NO_FLICKER=1` is in `~/.zshrc`, which works
but is not version-controlled. Moving it to `steward-session.sh` makes the fleet
configuration self-documenting and portable.

**Risk:** If the user also runs Claude Code outside tmux, they'd lose the flag.
Recommendation: keep in both places (idempotent).

### PR 3 (Optional): Document CLAUDE_CODE_SCROLL_SPEED source

`CLAUDE_CODE_SCROLL_SPEED=3` appears in tmux global env but its source is
unclear — it's not in `.zshrc`, `.claude/settings.json`, or any committed config.
It likely originated from the cmux app or an earlier manual `tmux set-environment -g`.

**Recommendation:** Add it to `steward-session.sh` for durability. If the tmux
server restarts, this flag would otherwise be lost.

---

## 5. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| `DISABLE_AUTOUPDATER` prevents security patches | Low | Fleet updates are controlled via operator rollout; auto-update during active sessions causes instability |
| `CLAUDE_CODE_RESUME_INTERRUPTED_TURN` may retry failed operations | Low | Existing idempotency guards in hooks and ops tooling handle duplicate execution |
| `DISABLE_COST_WARNINGS` hides usage spikes | Low | Ops monitoring tracks token burn separately; cost warnings are per-turn noise |
| Adding too many env vars may mask issues | Low | Each flag is independently testable; tests lock expected presence and values |

---

## 6. References

### Official Documentation
- [Environment variables - Claude Code Docs](https://code.claude.com/docs/en/env-vars)
- [Claude Code NO_FLICKER Mode](https://dev.to/raxxostudios/claude-code-just-fixed-terminal-flickering-how-to-enable-noflicker-mode-apf)

### Community Catalogs
- [Claude Code environment variables full list (jedisct1)](https://gist.github.com/jedisct1/9627644cda1c3929affe9b1ce8eaf714) — 115+ variables
- [Claude Code CLI Environment Variables (unkn0wncode)](https://gist.github.com/unkn0wncode/f87295d055dd0f0e8082358a0b5cc467)

### Internal
- PR #2197 — Set `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` for non-orch lanes
- Issue #2244 — Audit `CLAUDE_CODE_NO_FLICKER` configuration across all steward lanes

## Outcome

Research complete. Key finding: `CLAUDE_CODE_NO_FLICKER` already has full
fleet coverage via `~/.zshrc`. Five additional flags recommended for fleet
optimization (PR 1). Two optional follow-ups for configuration hygiene (PRs 2-3).
